---
module: pcs-backend — api 层通用（守卫 `_guard.py`）
date: 2026-11-23
problem_type: security_issue
component: authorization
severity: low
tags: [authorization, 404-same-shape, enumeration, guard, ast-scan, P10-I, T2, TODO-187b]
symptoms: 同一个端点对「记录不存在」抛 `"PsychroResult not found"`，对「记录存在但无权」抛 `"Project not found: {project_id}"` ⇒ ⇒ 无权者拿两个 404 的 **code / message** 一比 ⇒ ⇒ 就知道那条记录**存不存在**
root_cause: 端点的写法是「**先按 id 取记录 ⇒ 再判授权**」⇒ ⇒ 「不存在」由端点自己抛（各端点各有各的文案），「无权」由守卫抛（**全仓一句** `"Project not found: …"`）⇒ ⇒ ⇒ **两层各抛一条 ⇒ ⇒ 文案必然分叉** ⇒ ⇒ ⇒ 分叉本身 = 存在性预言机
---

# 两种 404 文案就是存在性预言机 —— 让守卫**照抄**端点自己那条

## 形状

```python
# ❌ 分叉
record = await session.get(PsychroResult, result_id)
if record is None:
    raise HTTPException(404, detail="PsychroResult not found")   # ← 端点自己那条
await check_record_access_or_404(db, user_id=..., record=record)  # ← 无权："Project not found: …"
```

⇒ ⇒ 两条文案**必然不同** ⇒ ⇒ 攻击者探一个随机 id：
**拿到 "PsychroResult not found" ⇒ 不存在**；**拿到 "Project not found" ⇒ 存在但我无权**。

## 修法：守卫**照抄**端点自己那条（不是端点去迁就守卫）

守卫加**两个可选参数**（`not_found_code` / `not_found_message`）⇒ ⇒ 端点把
**自己抛的那条**原样传进去 ⇒ ⇒ 守卫抛同一个 ⇒ ⇒ **两种情况不可区分**。

| 参数 | 抛出的形状 | 适用 |
|---|---|---|
| 都不给 | `HTTPException(404, "Project not found: …")` | **默认 = 现状** ⇒ ⇒ 124 处零影响 |
| 给 `not_found_message` | `HTTPException(404, detail=<它>)` | 端点自己抛 `HTTPException` 的族 |
| 给 `not_found_code` | `PcsError(code=…, message=…, 404)` | 端点自己抛 `PcsError` 的族 |

⚠️ **code 与 message 必须**一起**对齐** ⇒ ⇒ 只对齐 message 而 code 不同
⇒ ⇒ 前端按 code 分流时**仍然能区分** ⇒ ⇒ ⇒ 那就没修掉。

⚠️ **默认文案一个字都不能改** ⇒ ⇒ 124 处 project 级调用依赖它
⇒ ⇒ 必须有**一条测试钉子**（不传参数 ⇒ ⇒ 仍抛 `"Project not found: {project_id}"`）。

## 三条容易踩空的地方

### ① 手写清单必然漏 ⇒ ⇒ 用 **AST 扫全 api 层**

实测：计划写「12 族 · 30~40 行」⇒ ⇒ **AST 实扫 = 47 个端点** ⇒ ⇒
漏的不是「某个族」而是**整个模式**：凡是「先抛 404 再调守卫」的端点都要改。

⇒ ⇒ 守卫写成 **AST 完整性守卫**：扫全 api 层 ⇒ ⇒ 每个端点比对
「它自己抛的那条」与「它传给守卫的那条」的 **AST 结构**（`ast.dump` 逐字比）
⇒ ⇒ 漏传 / 抄错一个字 ⇒ ⇒ 红。

⚠️ **扫描规则自己要先有效** ⇒ ⇒ 另加一条「扫到的端点数 ≥ 20」的断言
⇒ ⇒ 否则扫描规则一坏 ⇒ ⇒ 下面全**恒真**（假绿）。

### ② 「守卫在前 ⇒ ⇒ 自己的 404 不可达 ⇒ ⇒ **没有向量**」

不是所有「抛 404 + 调守卫」的端点都有枚举向量 ⇒ ⇒ 若守卫**先**跑
⇒ ⇒ 无权者拿到的**永远是守卫那条** ⇒ ⇒ 端点自己那条**不可达** ⇒ ⇒ 无需对齐。

⇒ ⇒ 扫描必须带**顺序判据**（own-404 的 `lineno` < 守卫调用的 `lineno`）
⇒ ⇒ 否则会把一批**本来就没向量**的端点也拖进改动面。

### ③ own-404 在 **helper** 里 ⇒ ⇒ 端点级扫描**看不见**

`supplier.py::_load_equipment` · `records_actions.py::load_record`
⇒ ⇒ 端点源码里只有「调 helper」⇒ ⇒ 端点级 AST 扫**扫不到**
⇒ ⇒ ⇒ **两个真向量被漏掉**。

⇒ ⇒ 判据 = **扫描单位是「抛 404 的函数」，不是「端点函数」**
⇒ ⇒ 本仓的做法：helper 自身调守卫时**自己传文案** ⇒ ⇒ 改一处 ⇒ ⇒ 那一族全对齐。

## 端到端怎么断

⇒ ⇒ 真发请求 ⇒ ⇒ 同一个**无权**用户探「**存在**」与「**不存在**」两个 id
⇒ ⇒ 断言两者的 `(code, message)` **逐字相同**。

⚠️ 必须用 **`strict_client`** ⇒ ⇒ 默认 `client` 把守卫 mock 成**永远 True**
⇒ ⇒ 「无权」这条路径压根走不到 ⇒ ⇒ 断言**恒真**（空断言）。

## 后果（值得提前知道）

前端会开始**按新 code 分流**（原本无权是 `HTTP_404`，现在也是资源专属 code）
⇒ ⇒ 这是**预期**的（前端早已在按 `SIM_STREAM_NOT_FOUND` / `HEAT_NOT_FOUND` /
`RECORD_NOT_FOUND` 分流 ⇒ ⇒ 对齐后端反而**与前端既有口径一致**）
⇒ ⇒ 但**新写的页面**别把「无权」当成「不存在」去做差异化文案。

## 关联

- **bug-2198**（本条的登记）· **TODO-187**（审计发现）· **TODO-187b**（落地条目）
- 计划：`docs/superpowers/plans/2026-11-23-p10-i-report-review-publish.md` · T2
- 判「已覆盖」的标准见 `docs/solutions/testing-issues/assertion-must-be-sensitive-to-named-defect.md`
  （⇒ ⇒ 「用了 `strict_client`」才是真覆盖）
