---
module: pcs-frontend 取数通道（src/pages/routeWrappers.tsx）
date: 2026-11-17
problem_type: frontend_issue
component: frontend / http
severity: high
symptoms:
  - "真后端通道下物流详情页**永远停在「加载中…」** —— 而同一页在 mock 通道下一切正常"
  - "控制台**没有**任何错误（axios 只对 401 报错 ⇒ 裸 fetch 的 401 被静默吞掉）"
  - "症状是「数据没来」，真因是「**没带 token**」⇒ ⇒ 排查方向一开始就跑偏"
root_cause: second_http_channel_bypasses_the_shared_interceptor
resolution_type: test_and_source_fix
framework_version: React 18 / axios 1.7 / MSW / Playwright
related_components:
  - frontend
  - http
  - testing
tags:
  - false-green
  - msw
  - token
  - dual-channel
---

# 裸 `fetch` 绕开了 axios 拦截器 ⇒ 两条取数通道 ⇒ 只有一条被测过

## 1. 现象：真后端通道下页面永远加载中

`routeWrappers.tsx::useFetch` 用**裸 `fetch`** ⇒ ⇒ 请求**不带
`Authorization` 头** ⇒ ⇒ 真后端回 **401** ⇒ ⇒ 代码里
`.then((r) => (r.ok ? r.json() : null))` ⇒ ⇒ **401 被吞成 null** ⇒ ⇒
页面永远「加载中…」。

⇒ 而 **mock 通道（MSW）不校验 token** ⇒ ⇒ 这条缺陷在 mock 通道**完全隐形**
⇒ ⇒ 只有「真后端 + 真后端通道」这条组合才抓到它（bug-2169）。

## 2. 根因：仓里有**两条** HTTP 通道

| 通道 | 谁在用 | 有没有拦截器 |
|---|---|---|
| `src/api/client.ts`（axios） | 所有业务页面 | ✅ 带 token · 401 ⇒ 清会话 · 统一错误信封 |
| **裸 `fetch`**（`routeWrappers.tsx`） | 路由层的 11 个共享组件 | ❌ **无 token** · 错误被吞 |

⇒ ⇒ axios 的拦截器（token + 401 处理 + 错误信封）**只覆盖第一条** ⇒ ⇒
**第二条**是个「影子通道」：它在真后端上**必然**失败，且失败是**静默**的。

## 3. 形状（可复用）

> **一个仓里有两条取数通道 ⇒ 拦截器只覆盖其中一条 ⇒ 那一条在 mock 下隐形。**
> ⇒ 新增通道时，先问：**认证、401、错误信封**要不要**再写一遍**？

⇒ 修法（最小）：`useFetch` 从 zustand 会话里取 token 并**显式带上**
（`useAuth.getState().accessToken`，没有会话时回退 `DEV_BEARER`）。

⚠️ **更彻底的修法**是让路由层也走 `src/api/client.ts` 的 axios ⇒ ⇒
但那是**另一次改动**（要处理 axios 的响应形状），本批只做前者。

## 4. 为什么 mock 通道抓不到（可复用的观察点）

⇒ MSW 的 handler 只判「有没有 `Authorization` 头」⇒ ⇒
`Bearer mock-jwt-token` 这种**写死的假 token**也能过 ⇒ ⇒
「假 token」与「不校验 token」在 mock 通道里**是同一件事**。

⇒ ⇒ **真后端通道是这类缺陷唯一的发现途径** ⇒ ⇒
它的价值不在「多跑一遍页面」，而在「**请求真的到了真后端**」。
（见
`docs/solutions/testing-issues/assertion-must-be-sensitive-to-named-defect.md`
—— 通道建好了，断言还得对被它命名的缺陷**敏感**。）

## 5. 怎么发现这类问题

⇒ 审计「所有发请求的地方」⇒ ⇒ 逐个问：**它带 token 吗？它把 401 当什么？**
⇒ ⇒ 凡是绕过 `src/api/client.ts` 的 ⇒ ⇒ 都要单独看一遍。
