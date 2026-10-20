---
description: session handoff, regenerate with /handoff when a quest finishes
budget_tokens: 1500
---
# STATUS — PCS

> Read this FIRST when starting a session. Last updated: 2026-10-20（P9A B lane 收口）。
> 保持 <2k tokens。历史细节查 `git log` / `docs/` / `TODOS.md` / `.wolf/memory.md`。

---

## ✅ Done

### 第 6 轮（本会话）：执行 P9A-2「交付物写面」lane（B0→B5）+ 终审修复

11 笔 commit（`a4cf1e5`→`8ae08b9`），全部在 main。落地：

| task | 产出 |
|---|---|
| B0 | `workflow_progress` 表（`p9_002`）+ 5 态/3 类枚举 + 16 例 |
| B1 | `POST /deliverables/{id}/issue`（doc_no 原子分配）+ 15 例 |
| B2 | `sign-step` + `workflow_progress_writer`（观测**唯一**写入口）+ 26 例 |
| B3 | `customer-approval/proxy` + `secondary_auth`（MFA 路径 B）+ 16 例 |
| B4a–d | records 7 端点（`records_actions.py`）+ `record_comments`（`p9_003`）+ 动作时间线 + 51 例 |
| B5 | `GET /workflow-progress/{type}/{id}` + 500ms 验收（实测值已打印）+ 12 例 |
| 终审 | `d669f9b` 修 F1 CRITICAL（`{module}` 列不齐 → 500）+ F3（`p9_004` 加宽列）+ F4 |

**基线**：后端 **4868 passed / 77 skipped / 0 failed**；前端 **704 passed / 0 failed**；
两端 typecheck + lint clean；裸字段仍 **71（未上涨）**；两库均在 `p9_004`（head），
`alembic check` 均 exit 0。

### 🔒 B4 Step 0 的判定（计划里唯一可能造成数据语义错误的地方）

`change_notice_service.approve_change_notice` **不等同** SPEC 的 `abandon-change`：
它作用于**交付物**、迁移 `PENDING → APPROVED`、审计 `CHANGE_NOTICE_APPROVED`
= 「批准变更单、变更生效」，与「放弃」**方向相反**。
`abandon-change` 改为转发既有的 `StateTransition.ABANDON_CHANGE`
（`CHANGE_PENDING → CHECKED` + 恢复 ACTIVE 快照 + 审计 `CHANGE_ABANDONED`）。
**终审的 fresh reviewer 独立重推了一遍这个判定，结论相同。**

### 顺带修的既有坏 fixture（bug-192）

`tests/conftest.py` 的 `workspace` fixture 传 `workspace_name=`（模型列叫 `name`）
且漏 `project_id` ⇒ 用它的测试全 TypeError、项目守卫被静默跳过。
**从没暴露是因为没有任何测试用过它** —— 未被执行的 fixture 与不存在的 fixture
在测试套件里是同一种东西：全绿。

---

## 🚀 Next quest

1. **P9A-3「通知待办」lane（C0→C4）** —— 与 A/B/D 无前置，可直接开工。
   读 `docs/PCS-PLAN-P9A-3-通知待办.md` + `docs/adr/0049-notification-and-todo-data-model.md`。
   ⚠️ 该 ADR §① 已锁「通知建表 + 待办**实时计算**（不建 `todos` 表）」、
   §④ 已锁 30 天清理挂 ARQ；§① 的**通知发送**同步/异步**明确未锁**。

2. **P9A-4「编辑锁与 CIA」lane（D0→D3）** —— **D1 必须在 B 之后**（现已完成，可开工）。
   D0 迁移与 A/B/C 并行不冲突；注意 `RECORD_TYPE_REGISTRY` 里 `CostEstResult`
   **没有 `record_hash` 列**（TODO-048）。

3. **需要用户裁决的一条**：**TODO-052** —— `workflow_progress` 这个表名在仓库里
   有**两个互不相容的定义**：SUP-008 §8.5 是 14 字段的「项目作业流程进度百分比表」，
   SPEC-P9 / ADR-0047 是 8（实 10）字段的「签署步骤观测表」；而 SPEC 与 ADR 都把
   对方**不存在的章节号**（§2.6 实为「反应器计算」）当依据引用。
   本 lane 建的是后者。要不要建前者 / 要不要另议表名，需用户定。

4. **P9A-1 的遗留项**（未变）：access token 不带 `tv`（停用后在手 access 仍可用至过期）；
   AD 同步需服务账号 `LDAP_BIND_DN`/`LDAP_BIND_PASSWORD`/`LDAP_USER_FILTER`/`LDAP_USER_ATTRS` ——
   运维给账号前 P9A-USR-002/003 只算**代码就绪**，不算验收通过。

---

## Context

- main，工作区干净。**不要建 worktree**（历史事故，见上轮 STATUS）。
- 两库均在 `p9_004`（head），`alembic check` 均 exit 0。改迁移的纪律见 CLAUDE.md
  （退出码 **255**；先 `current` vs `heads`；**每库各跑一次**）。
  ⚠️ `pcs_test` 的跑法：URL 从 `.env` 派生（`DATABASE_URL` 改库名），
  **不要把口令写在命令行**（会被权限分类器拦）。
- 契约产物由 G-08 钩子在 commit **之后**重生成，而 `git add` 在钩子之前
  ⇒ 偶尔漏提交，commit 后要 `git add -A && git commit --amend --no-edit` 补。
- 无 CI/CD（单人开发裁决，勿再建议）。本地 gate 走 `.githooks/`。
- 提交约定：conventional commits，**无 attribution 行**（本仓全局禁用）。

---

## 教训（本会话新增）

- **「注册表里的每个键都能用」是断言不是事实**。`RECORD_TYPE_REGISTRY` 混着几张
  列不齐的表，解析通过不等于能加载 —— 表现是 500 而非 422。写「X 取注册表的键」
  时，必须同时写「X 需要哪些列，缺了怎么办」。
- **未被执行的 fixture 与不存在的 fixture 同一种东西：全绿**。conftest 里放了
  4 年的 fixture 从没人用过，它就成了一个「看起来有覆盖」的空壳。
- **Pydantic 的 Rust regex 不支持 look-ahead**：想用 `^(?!\s*$).+$` 拒空白
  会得到 `SchemaError`（schema 编译失败，整个端点起不来），而不是校验失败。
  拒空白用 `field_validator`。
- **角色闸先于模块解析**：断言「模块解析错误码」时必须用对角色的 token，
  否则先吃 403，断言集被迫放宽而失去信息量。
- **三次「假绿」同一形状**：新端点的 404/422 断言若只断言状态码，会在
  **端点不存在时**就绿（FastAPI 对未注册路径也返 404）。⇒ 必须断言 error code。
  本 lane 因此抓到自己写反的一条测试。
