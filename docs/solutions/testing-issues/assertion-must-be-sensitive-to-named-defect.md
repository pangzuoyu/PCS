---
module: pcs-frontend 真后端通道（e2e/real_backend_flows.spec.ts）
date: 2026-11-17
problem_type: testing_issue
component: testing_framework
severity: high
symptoms:
  - "一条自称「验跨项目 ⇒ 与『不存在』同形」的用例 ⇒ **把项目守卫整段删掉也照样绿**"
  - "它比较的两个状态码都是**角色闸**给的 403 ⇒ ⇒ 被它命名的分支**一次都没执行**"
  - "同类：路由扫描断「`#root` 这个 div 存在」⇒ ⇒ 恒真 ⇒ ⇒ 「渲染了」证明不了任何事"
root_cause: assertion_does_not_reach_the_branch_it_names
resolution_type: test_and_source_fix
framework_version: Playwright / MSW / React 18
related_components:
  - testing_framework
  - frontend
  - security
tags:
  - false-green
  - assertion-shape
  - mutation-test
  - authorization
---

# 断言必须对它**命名的那个缺陷**敏感 —— 用变异测试证明

## 1. 现象：删掉被守卫的代码，用例照样绿

P10-B 的真后端通道里有一条「越权用户看不到别人的项目」：

```ts
expect(unauthorized.status()).toBe(nonexistent.status());
```

⇒ 看着在断「同形」⇒ ⇒ **把 `streams.py` 里的项目守卫
（`check_project_access_or_404`）整段删掉**，两个请求**仍然**都是 **403**
⇒ ⇒ 断言**照样绿** ⇒ ⇒ 它对它命名的缺陷**零覆盖**。

## 2. 根因：被测身份**走不到**那条分支

物流列表端点的闸门顺序是：

```python
require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")  # ① 角色闸
await check_project_access_or_404(...)                                  # ② 项目守卫
```

被测身份是 mock 登录的 **`bob` = CHECKER** ⇒ ⇒ **① 就 403** ⇒ ⇒
**② 一次都没执行** ⇒ ⇒ 「存在但没授权」与「压根不存在」**都是同一个闸门**
给的 403 ⇒ ⇒ 「同形」是**同义反复**。

⚠️ **四个 mock 账号没有一个能表达这个身份**：
`alice` 有授权行（200）· `bob`/`carol` 角色不够（403 在 ①）·
`dan` 是 SYSTEM_ADMIN（**项目守卫全局 bypass** ⇒ 200）。

## 3. 形状（可复用）

> **断言要断的分支，必须先「到达」那个分支。**
> ⇒ 「角色够 + 授权缺」才是「项目守卫」这类断言的**唯一**可用身份。

⇒ ⇒ 种子里补一个这样的用户（`erin` = DESIGNER · **故意不授权**）⇒ ⇒
断言改成：存在但无授权 ⇒ **404**（不是 403）+ `code` **逐字相同** +
`message` **模板逐字相同**（模板 = 归一化项目 id 后；消息里**带 id**）。

⇒ ⚠️ **同一条纪律的另两处**：
- 路由扫描断「页面**自己的** `data-testid`」而不是「`#root` 存在」（恒真）
- 白名单外**必须为空**（console error / 4xx）—— 只打印不断言 = 放弃 QA 闸门

## 4. 怎么证明一条断言**敏感**（变异测试）

⇒ **删掉被守卫的那段代码** ⇒ ⇒ 断言**必须红** ⇒ ⇒ 恢复。
⇒ 这条动作能把「断言恒等」这类假绿**当场揭穿**（本批就是靠它确认新断言有效）。

⚠️ 代价：要能安全地改回生产代码 ⇒ ⇒ 用「复制→改→跑→还原」的顺序
⇒ ⇒ 且**先跑一遍绿**（确认基线）再改。

## 5. 与既有的解法同族

⇒ `docs/solutions/testing-issues/narrow-declaration-is-not-a-constraint.md`
（窄声明不是约束）——
⇒ ⇒ 这里更进一步：**窄的断言**（只断状态码相等）**也不是**对缺陷的约束。
