# P9B-2 实施计划：签署流程前端 + ADMIN 前端（SPEC §6.3 / §6.17~§6.19 / §7.19 / §7.20）

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`
> （或 `superpowers:subagent-driven-development`）。
> ledger: `.superpowers/sdd/PCS-PLAN-P9B-2-签署流程与ADMIN前端/progress.md`
> ⚠️ **本计划尚未过 `/plan-eng-review`** —— 开工前应先过一轮（见文末「尚未解决的问题」）。

**Goal:** 兑现 SPEC §6.3（操作按钮组 RecordActions）、§7.19.1（批注面板 /
状态时间线）、§7.20（ADMIN 用户管理 / 审计日志）的**前端**，并补上 P9B-1
留下的两个后端前置（TODO-065 聚合进度端点 / TODO-066 按项目守卫的编辑审计读端点）。

**Architecture:** 「**三个薄壳 + 一条数据链**」——
① 记录级写面（操作栏 / 批注）挂在 **P9B-1 的结果记录页**上，走
`/records/{module}/{record_id}/…`（后端 7 个写端点已交付）；
② 交付物读面（聚合进度 / 动作时间线）挂在 **P9B-1 的交付物进度页**上，
走本批新建的 `/deliverables/{id}/progress`（TODO-065）；
③ ADMIN 两个页面走 `/admin/users`（3 端点已交付）与 `/audit-logs`（已交付）。
**按钮渲染的数据源是 `GET /meta/state-machine`（后端从 `ALLOWED_TRANSITIONS`
生成），不是前端硬编码的按钮表** ⇒ 后端加一个迁移，前端自动跟上。

**Tech Stack:** React 18 + TypeScript 5.5 + antd 5 + axios + zustand + vitest +
MSW（node 与 browser 两用）+ Playwright（e2e/ 已装）；后端 FastAPI + SQLAlchemy 2.x
async + pytest。

**Spec:**
- `docs/PCS-UI-SPEC.md` **V2.1** —— §5.1 / §5.2 / §5.5 / §6.2 / §6.3 / §6.17 /
  §6.18 / §6.19 / §6.21 / §7.19 / §7.20 / §12.3
- `spec/PCS-REQ-2026-002-SPEC-P9 …` **V2.1** §3.2.1（P9A-DLV-001/004/005/006/008）、
  §3.2.2（P9A-USR-001~007 / P9A-ADM-001/002）、§3.2.3（P9A-OBS-001~004）、
  §4.2（前端纪律）、§4.4（P9B 交付物）
- `docs/adr/0048-edit-lock-storage.md`（并发基线 / 编辑审计）、`0047`（观测层）、
  `0049`（通知 / 待办）、`0046`（身份与吊销）

---

## Global Constraints

1. **类型全部来自生成的 `src/types/api.d.ts`**（`components['schemas'][...]`），
   **不手写**（TODO-064 已删 18 个漂移手写类型）。⚠️ `src/types/*.ts` 仍有 57 个
   同名手写类型（TODO-064），**本批不碰**。
   ⚠️ 后端 `meta.py` 的 `StateTransition` 与 `models/enums.py` 的同名枚举**撞名** ⇒
   契约里的名字是 **`StateTransition-Output`**（不是 `StateTransition`）。
2. **mock 必须与真端点同形**：契约端点的 mock 响应体**用生成的类型标注**
   （`satisfies components['schemas'][...]`），**不得手写自由 dict**
   ⇒ 这正是 bug-2040 的根源。⚠️ 本仓**没有** orval / openapi-msw
   ⇒ **不引入新依赖**，用类型标注 + `satisfies` 兜住。
   ⚠️ `tests/mocks/handlers.test.ts` 的**棘轮清单**（`devOnly ∩ 契约`）必须同步更新
   —— 新增即红是**预期**。
3. **`record_type` 用 `RECORD_TYPE_REGISTRY` 的键**（不是表名）⇒ `/records/…` 与
   `/locks` 都**校验**，传错 ⇒ 404 / 422。
   ⚠️ `/records/{module}/{id}/<action>` 用 **`RECORD_TYPE_REGISTRY` 的键**
   （如 `CostEstResult` / `cooling_tower_result`），与 P9B-1 的 `records.ts` 同一套
   ⇒ **前端不得另起第二套**。
4. **9 态动作只对「有 9 态列」的记录开放**：`resolve_record_model(module,
   need_mixin=True)` 对缺 `sign_status` 的表返 **422 `RECORD_MODULE_UNSUPPORTED`**
   ⇒ 前端**不发注定失败的请求**（见 T3 的 `hasSignStatus` 判据）。
   ⚠️ `cost_est_results`（p9_007 后有 `project_id`，但**无** `sign_status`）
   ⇒ **无操作栏**、**但可批注**（批注走 `need_mixin=False`）。
5. **不得自动重试**任何 409 / 403 / 422。失败**明说**（错误码 + 文案），
   **不得**静默降级成「成功」或「没有」。
6. **时间戳一律原样透传**（PG `TIMESTAMPTZ` 是微秒，JS `Date` 只到毫秒）
   ⇒ 展示用格式化函数，**格式化值不得回传**。
7. **前端不得自行推导「某角色能不能审阅 / 能不能签」**（SPEC §5.5.1）⇒ 能力从
   `GET /meta/state-machine` 的 `allowed_roles` 与 `GET /meta/permissions` 的
   `frontend_behavior` 读，**不硬编码 ACL**。
8. **交付物级签署写面（`issue` / `sign-step` / `customer-approval/proxy`）本批不做**
   ⇒ `signature_matrices` **恒为 0 行**且全仓无创建方 ⇒ `sign-step` 无矩阵可推。
   见「事实基础」的 R-1。
9. 提交约定：conventional commits，**无 attribution 行**。长 commit message 写文件后
   `git commit -F <file>`（`!` `（）` 会被 shell 吃掉）。
10. ⚠️ **不要建 worktree**（本仓历史事故，见 `.wolf/STATUS.md`）。
11. ⚠️ **改了迁移必须在新库上验**（CLAUDE.md「漂移盲区」）—— 本批**不改迁移**。

## Review Focus

以下失败模式是 SPEC 蕴含、但**任何任务的测试若不专门写就不会覆盖**的。
每条都指派给了拥有该代码的任务。

| # | 失败模式 | 期望行为 | 归属 |
|---|---|---|---|
| RF-1 | **按钮只看状态、不看角色与前置条件** ⇒ 用户点了才吃 403 | 按钮由 `meta/state-machine` 驱动：`allowed_roles` 不含当前角色 ⇒ **禁用 + Tooltip 写明原因**（SPEC §5.1「门禁前置」） | T3 |
| RF-2 | **提交送审时选了等于自己角色的 `approval_role`** ⇒ 后端 403 `APPROVAL_SELF_REVIEW_FORBIDDEN` | 角色选择器**排除当前用户自己的角色**；后端 403 仍兜底 | T3 |
| RF-3 | **必填理由被空理由提交**（弃用 / 发起撤销）⇒ 422 | 理由为空时**提交按钮禁用**；文案说明「弃用理由必填（事后无从追溯）」 | T3 |
| RF-4 | **9 态动作发给没有 9 态列的模块**（`cost_est`）⇒ 422 `RECORD_MODULE_UNSUPPORTED` | 无 `sign_status` 的行**不渲染操作栏**（不发注定失败的请求） | T3 / T4 |
| RF-5 | **把 `workflow_progress` 当成「谁做了什么」** ⇒ 甘特图把「查过一眼」算成活动 | 记录状态时间线**只**取编辑审计（`RECORD_EDITED`）；交付物动作时间线**只**取 `/deliverables/{id}/actions`；两个数据源**不得混用** | T4 / T5 |
| RF-6 | **聚合端点里某类工作流不可用时返回空数组** ⇒ 用户以为「这条流程一个节点都没有」（与 404 长得一样） | 每类工作流都带 `available` + `reason`；`available=false` ⇒ 显示**原因**（不是空列表） | T0 / T5 |
| RF-7 | **批注提交纯空白** ⇒ 后端 422（字段校验拒空白）⇒ 用户以为没发出去 | 前端 `trim()` 后为空 ⇒ **禁用发送**；已发列表里**不出现**空白条目 | T4 |
| RF-8 | **批注分页漏条 / 重复** ⇒ 后端排序带 `comment_id` tiebreaker（秒级精度） | 前端按 `total` **分页**（不是「加载更多直到空」）⇒ 页数 = `ceil(total/limit)` | T4 |
| RF-9 | **停用用户后列表仍是旧状态** ⇒ 用户以为没生效 | 停用成功后**重新拉列表**（不乐观更新单行）；并显示新的 `token_version` | T6 |
| RF-10 | **AD 同步 `ok=false` / `skipped_empty=true`** ⇒ 前端显示「同步成功」 | `ok=false` ⇒ 显示**后端 `error` 原文**；`skipped_empty=true` ⇒ 显示「枚举到 0 个用户，未做任何写入」；**不得**显示成功 | T6 |
| RF-11 | **导出只导当前页，文案却说「全部」** ⇒ 用户拿到的数据是残缺的 | 导出**当前筛选下的全部行**（循环拉页，上限 5000 行）；超限**显式提示截断**；按钮文案写明范围 | T6 |
| RF-12 | **越权 403 / 404 混同** ⇒ 页面显示成「没有数据」 | 无权限 ⇒ 显式「无权查看」提示；**不得**渲染成空表 | T4 / T6 |
| RF-13 | **记录详情抽屉跨模块切换时残留上一个模块的记录** ⇒ P9B-1 的 bug-2043 同形复发 | 抽屉的 `key` 必须带 `recordType + recordId` ⇒ 换记录 = 整块重建 | T4 |

---

## P9B 全景与本批边界

P9 SPEC §4.3/§4.4 的 P9B 共 8 个工作项（7.5–10 人周）。P9B-1 做完并发控制 +
变更影响确认 + 结果页 + 观测/待办面板 + 交付物进度页。**本批做剩下三项**。

| P9B 工作项 | P9B-1 | **本批** | 去向 |
|---|---|---|---|
| 并发控制前端（§6.21） | ✅ | — | — |
| 变更影响分析前端（§6.7.1 确认动作） | ✅（确认动作） | — | 高亮 / 对比另批 |
| 6 类结果记录页 | ✅ | — | — |
| workflow_progress / 待办 / 实时状态 | ✅ | — | — |
| **签署流程前端（操作栏 / 批注 / 状态时间线）** | ❌ | ✅ **T3 / T4 / T5** | 交付物级签署写面见 R-1 |
| **ADMIN 用户管理前端** | ❌ | ✅ **T6** | — |
| **ADMIN 审计日志前端** | ❌（`AuditLogPage` 有雏形） | ✅ **T6**（扩成「查询 + 导出」） | — |
| ADMIN 系统参数前端 | ❌ | ❌ | P9B-3 |
| 物流手动创建向导 + 校对 UI | ❌ | ❌ | P9B-3 |

**本批另含两个后端前置**（P9B-1 明确延到本批）：

| 前置 | 内容 | 本批任务 |
|---|---|---|
| **TODO-065** | `GET /deliverables/{id}/progress` —— 三类工作流一次拿全 | **T0** |
| **TODO-066** | `GET /records/{module}/{record_id}/edits` —— 按项目守卫的编辑审计读端点 | **T1** |

---

## 事实基础（2026-10-21 实测，非推断）

### 后端：**记录级写端点已全部就绪**（`app/api/v1/records_actions.py`）

| 端点 | 请求体 | 响应 | 角色闸（`TRANSITION_ROLES`） |
|---|---|---|---|
| `POST /records/{module}/{id}/submit-approval` | `{approval_role, approval_depth}` | `{from_status,to_status,approval_step,approval_depth,approval_role}` | SUBMIT_FOR_CHECK = {DESIGNER, CHECKER, APPROVER, SYSTEM_ADMIN} |
| `POST /records/{module}/{id}/approval-step` | `{decision: PASS\|REJECT, reason}` | `{from_status,to_status,approval_step,approval_depth}` | PASS_CHECK / REJECT_CHECK = {CHECKER, APPROVER, SYSTEM_ADMIN} |
| `POST /records/{module}/{id}/obsolete` | `{reason}` **必填** | `{record_type,record_id,from_status,to_status}` | OBSOLETE = {DESIGNER, CHECKER, APPROVER, SYSTEM_ADMIN} |
| `POST /records/{module}/{id}/request-reversal` | `{reason}` **必填** | 同上 | REQUEST_REVERSAL = {DESIGNER, CHECKER, APPROVER, SYSTEM_ADMIN} |
| `POST /records/{module}/{id}/reversal-decision` | `{decision: APPROVE\|REJECT, reason}` | 同上 | APPROVE/REJECT_REVERSAL = {APPROVER, SYSTEM_ADMIN} |
| `POST /records/{module}/{id}/abandon-change` | `{reason}` | 同上 | ABANDON_CHANGE = {DESIGNER, SYSTEM_ADMIN} |
| `GET /records/{module}/{id}/comments` | `?limit&offset` | `{items,total}` | 读角色 5 个（DESIGNER/PROCESS_CONTROLLER/REVIEWER/APPROVER/SYSTEM_ADMIN） |
| `POST /records/{module}/{id}/comments` | `{body}`（**拒纯空白**，≤5000） | `{comment_id,record_type,record_id,body,author_id,created_at}` | 同上 |

⚠️ **13 个状态机事件里，只有 6 个有端点**：`MARK_STALE` / `INITIATE_CHANGE` /
`APPLY_CHANGE` / `RESOLVE_STALE_NO_CHANGE` / `RESOLVE_STALE_CHANGED` **无端点**
⇒ SPEC §6.3 的「变更申请」「创建交付物」「关闭凭证」**本批无后端可调**（见 R-6）。

⚠️ **端点层会映射异常**：`RoleForbidden` → 403 `RECORD_ROLE_FORBIDDEN`；
`InvalidTransition` → 409 `RECORD_INVALID_TRANSITION`；
不在审批中 → 409 `APPROVAL_NOT_ACTIVE`；待批角色不符 → 403 `APPROVAL_ROLE_MISMATCH`；
自审 → 403 `APPROVAL_SELF_REVIEW_FORBIDDEN`；未知模块 → 422 `RECORD_MODULE_UNKNOWN`；
缺 9 态列 → 422 `RECORD_MODULE_UNSUPPORTED`（报文点名缺哪些列）。

### 后端：**交付物读端点 + 观测层**

- `GET /deliverables/{id}/actions` → `{deliverable_id, items[], total}`；
  `items[]` = `{action, resource_type, resource_id, actor_user_id, detail_json(JSON 文本), created_at}`。
  ⚠️ `detail_json` 是 **JSON 文本**（结构随 action 变）⇒ 前端 `JSON.parse` 且**必须容错**。
- `GET /workflow-progress/{workflow_type}/{workflow_id}` → `{workflow_type, workflow_id, project_id,
  total, pending, in_progress, completed, skipped, failed, items[]}`；
  `items[]` = `{progress_id, step_order, step_role, step_status, started_at, completed_at,
  assignee, result_hash}`。未知 workflow_type ⇒ 422 `WORKFLOW_TYPE_UNKNOWN`；
  工作流不存在 ⇒ 404 `WORKFLOW_NOT_FOUND`。
- ⚠️ **三类工作流的 `workflow_id` 语义（2026-10-21 实测，与 P9B-1 计划所述不同）**：

  | 工作流 | `workflow_id` | 依据 |
  |---|---|---|
  | `SIGN` | **版本 id** | 写入点 `deliverable_service.py:641` `workflow_id=version_id` |
  | `CUSTOMER_APPROVAL_PROXY` | **交付物 id** | 写入点 `deliverable_service.py:931` `workflow_id=deliverable_id`；`workflow_progress_service._resolve` 亦证（非 SIGN ⇒ 查 `deliverables`） |
  | `CHANGE_NOTICE` | 变更单自身的 deliverable_id | 写入点在 `change_notice_service.py:388`，而 `create_change_notice` **抛 NotImplementedError**（P9A-DLV-007 / TODO-057 未做）⇒ **恒不产生观测行** |

  ⇒ **P9B-1 计划 §「事实基础」写的「CUSTOMER_APPROVAL_PROXY → 版本 ID」是错的**，
  本批按**代码**实现，并修订 `TODOS.md` TODO-065 的那张表（R-2）。

### 后端：**ADMIN**

- `GET /admin/users` → `AdminUserOut[]` = `{user_id, username, display_name, email,
  department, roles[], status, token_version, last_login_at}`；限 **SYSTEM_ADMIN**。
- `PUT /admin/users/{user_id}/disable` → `{user_id, username, status, token_version}`；
  同事务 `status=DISABLED` + `token_version += 1` + 写审计。
- `POST /admin/users/sync` → `{ok, created, updated, departed, unmapped, skipped_empty, error}`；
  未配置服务账号 ⇒ **503 `LDAP_SYNC_NOT_CONFIGURED`**。
- `GET /audit-logs` → `{items[], total, limit, offset}`；`items[]` = `{audit_id, user_id,
  action, resource_type, resource_id, detail_json(dict), occurred_at}`；限 **SYSTEM_ADMIN**。
  ⚠️ **`audit_logs` 表无 `project_id`** ⇒ 授权只能靠 `resource_type + resource_id` 反查
  ⇒ 这正是 TODO-066 要补的洞。

### 后端：**meta（操作栏的数据源）**

- `GET /meta/state-machine` → `{transitions: [{from, action, to, allowed_roles[],
  preconditions[], side_effects[]}], allowed: {状态: 事件[]}}`；
  ⚠️ 契约里的 schema 名是 **`StateTransition-Output`**（与 `models/enums.py` 的同名
  枚举撞名 ⇒ FastAPI 加了 `-Output` 后缀）。
- `GET /meta/permissions` → `PermissionItem[]` = `{role, resource, action,
  permission_code, frontend_behavior}`。
- ⚠️ **后端不发射 `x-permission`**（全仓 0 处）⇒ SPEC §5.1「权限码从 OpenAPI
  x-permission 读取」**当前不成立**；本批改用 `meta/permissions`（R-5）。

### 前端现状

- 已有可复用：`useAuth`（`role` / `userId`）、`api` 实例、`PageHeader` /
  `HashBadge` / `StateBadge` / `NumericCell` / `ApprovalStepBar` / `SignatureMatrix` /
  `RevTimeline` / `ConflictResolver`。
- **`Can` 组件不存在**（SPEC §5.1 提到 `<Can permission="...">`）⇒ 本批**不造**它，
  改用「状态机 `allowed_roles` + `meta/permissions`」的函数式判定（R-5）。
- `src/api/` 现有：`audit.ts` / `changeImpact.ts` / `client.ts` / `common.ts` /
  `errors.ts` / `heat.ts` / `locks.ts` / `notifications.ts` / `psv.ts` / `psychro.ts` /
  `records.ts` / `reportBuilder.ts` / `sepEquip.ts` / `sprint1.ts` / `stream.ts` /
  `todos.ts` / `util.ts` / `vessel.ts` ⇒ **无** `meta.ts` / `recordActions.ts` /
  `deliverables.ts` / `admin.ts`。
- `src/pages/audit/AuditLogPage.tsx` 已有（**F-P2-009** 的三 tab：config-audit /
  equipment-deletion / audit-logs），**无筛选表单、无导出**、标题写死
  「Audit Query (F-P2-009 Sprint 3)」⇒ T6 **扩展它**，不新建第二个审计页（R-8）。
- `src/api/records.ts` 有 `EditableRecordType`（6 个键）+
  `EDITABLE_RECORD_TYPES` + `RESULT_BASES` ⇒ **T1~T4 一律复用它**，不另起词表。
- `src/pages/results/resultModules.ts` 的 6 个描述符**已有**「本模块有无
  `sign_status`」的信息（P9B-1 Ruling 1：cost_est 无状态列）⇒ T3 直接用。

### 数据现状（2026-10-21 实测 dev 库）

`deliverables` / `signature_matrices` / `deliverable_versions` / `workflow_progress` /
`record_comments` / `audit_logs(RECORD_EDITED)` / `users` —— **全部 0 行**
⇒ 这批的面**在真库里没有数据**，验证靠**后端单测（造 fixture）** + **前端 MSW mock**；
浏览器回归验的是**交互与空态**，不是真数据。

---

## 裁决（本计划已定，执行时按此做）

| # | 裁决 | 理由 | 代价 |
|---|---|---|---|
| **R-1** | **交付物级签署写面（issue / sign-step / customer-approval/proxy）本批不做** | `signature_matrices` **恒 0 行**、全仓**无创建方**（`change_notice_service.py:153` 自陈）⇒ `sign-step` 无矩阵可推；`create_change_notice` 抛 `NotImplementedError`（TODO-057 未做）⇒ 做 UI 只能做出「永远 404/500」的死界面 | 交付物级签署推迟到 TODO-057 之后；本批的「签署」只到**记录级 9 态**与**交付物读面** |
| **R-2** | TODO-065 聚合端点按**代码实测**的 `workflow_id` 语义实现（CUSTOMER_APPROVAL_PROXY = **交付物 id**） | 写入点与 `_resolve` 双向印证；P9B-1 计划里的表**是错的** | 需同步修订 `TODOS.md` TODO-065 的表格（否则下一个人照旧表实现） |
| **R-3** | 聚合端点的每类工作流都带 `available` + `reason`；`CHANGE_NOTICE` 恒 `available=false` + 明确原因 | `parent_deliverable_id` **全仓从未被写** + 变更单创建链未接通 ⇒ 空数组会被读成「这条流程一个节点都没有」（与 404 长得一样，后端 `workflow_progress.py:65` 已为单条端点写过同样的警告） | 响应多两个字段；前端多一个分支 |
| **R-4** | 操作栏由 **`GET /meta/state-machine`** 驱动，**不硬编码** SPEC §6.3 的按钮表 | §6.3 是冻结快照，`meta` 是从 `ALLOWED_TRANSITIONS` 生成的**契约真源**；硬编码 = 第二份真相源 ⇒ 后端加迁移而前端不变 ⇒ 用户看到注定 409 的按钮 | 前端多一次 meta 请求（可缓存）；§6.3 与 meta 不一致时**以 meta 为准**并登记 SPEC 修订 |
| **R-5** | 权限判定用「`meta/state-machine` 的 `allowed_roles` + `meta/permissions` 的 `frontend_behavior`」，**不造 `Can` 组件、不硬编码 ACL** | SPEC §5.5.1 明令「前端不得自行推导能力」；后端**不发射 `x-permission`** ⇒ §5.1 的 `Can` 契约当前无源 | 无 `Can` 组件 ⇒ P9B-1 的 `Can` 计划项继续挂起（本仓至今**没有** `Can`） |
| **R-6** | §6.3 里**没有后端端点**的按钮（变更申请 / 创建交付物 / 关闭凭证）⇒ **禁用 + 写明「后端未提供该操作」**，并登记 `TODOS.md` | 静默隐藏 = 用户以为功能不存在；发假请求 = 用户吃 500。禁用 + 说明是唯一诚实的中间态 | UI 上有三个永远点不动的按钮；已登记待补 |
| **R-7** | 记录级**批注**对**有 `project_id` 的记录**开放（`need_mixin=False`）⇒ `cost_est`（p9_007 后有 `project_id`）**可批注但无操作栏** | 后端 `resolve_record_model(need_mixin=False)` 只要求 `project_id` | 前端要按「有无 sign_status」**分别**渲染操作栏与批注区 |
| **R-8** | 审计日志**扩展现有 `AuditLogPage`**（加筛选 + 导出），并把菜单从「审计」组移到「管理」组、标题改「审计日志」 | SPEC §7.20 的 ADMIN 项；新建第二个审计页 = 两个页面抢同一批端点 | 现有 e2e `e2e/audit_log.spec.ts` 的菜单项名与标题断言**必须同步改** |
| **R-9** | 审计导出的数据源是**前端循环拉页**（同一筛选条件，上限 5000 行），**不新增后端导出端点** | 后端已有 `/meta/permissions.csv` 但**没有** audit 导出端点；新增一个导出端点会把本批做大，且导出的权限边界与查询端点相同 | 大结果集会截断 ⇒ **必须显式提示**（RF-11） |
| **R-10** | 记录级状态时间线 = **编辑审计**（TODO-066）；交付物动作时间线 = `/deliverables/{id}/actions`。**两者不得混用** | 后端注释明写「这里回答『谁做了什么』，观测层回答『流程到哪一步了』。拿 actions 当进度来源，甘特图会把『查过一眼』也算成活动」 | 两条链路的空态文案必须不同（「尚无编辑记录」vs「尚无动作记录」） |

---

## 文件结构

**新建**（后端 4 个）：

| 文件 | 职责 |
|---|---|
| `pcs-backend/app/schemas/deliverable_progress.py` | 聚合进度响应（`DeliverableProgressResponse` + `WorkflowProgressSection`） |
| `pcs-backend/app/schemas/record_edits.py` | 编辑审计响应（`RecordEditsResponse` + `RecordEditItem`） |
| `pcs-backend/app/api/v1/record_edits.py` | TODO-066 的读端点（按项目守卫） |
| `pcs-backend/tests/api/v1/test_deliverables_progress_aggregate.py` | TODO-065 的测试 |
| `pcs-backend/tests/api/v1/test_record_edits_endpoint.py` | TODO-066 的测试 |

**修改**（后端 2 个）：`pcs-backend/app/api/v1/deliverables.py`（加聚合端点）、
`pcs-backend/app/api/v1/__init__.py`（挂 `record_edits` 路由）。

**新建**（前端 10 个）：

| 文件 | 职责 |
|---|---|
| `src/api/meta.ts` | `metaApi.stateMachine()` / `metaApi.permissions()` |
| `src/api/recordActions.ts` | 记录级 7 个动作 + 批注增删查 |
| `src/api/deliverables.ts` | 交付物聚合进度 + 动作时间线 |
| `src/api/admin.ts` | ADMIN 用户列表 / 停用 / AD 同步 |
| `src/components/common/RecordActions.tsx` | §6.3 操作按钮组（meta 驱动）+ 理由弹窗 + 送审角色选择 |
| `src/components/common/CommentPanel.tsx` | 批注面板（列表 + 新增 + 分页） |
| `src/components/common/RecordTimeline.tsx` | 记录状态时间线（编辑历史） |
| `src/pages/results/RecordDetailDrawer.tsx` | 记录详情抽屉（状态 + 哈希 + 操作栏 + 批注 + 时间线） |
| `src/pages/admin/UserAdminPage.tsx` | ADMIN 用户管理页 |
| `src/mocks/seed/signFlow.ts` | 签署流程 / 批注 / ADMIN 的 seed（**契约类型标注**） |

**修改**（前端 8 个）：

| 文件 | 改什么 |
|---|---|
| `src/pages/results/ResultListPage.tsx` | 每行加「详情」入口 → 打开 `RecordDetailDrawer` |
| `src/pages/results/resultModules.ts` | 描述符加 `hasSignStatus`（有无 9 态列）—— T3/T4 的判据来源 |
| `src/pages/deliverables/DeliverableProgressPage.tsx` | 用**聚合端点**替换逐行 `workflow-progress/SIGN`；加「动作时间线」区 |
| `src/pages/audit/AuditLogPage.tsx` | audit-logs tab 加**筛选 + 导出 CSV**；标题改「审计日志」 |
| `src/layouts/MainLayout.tsx` | 菜单：审计 → **管理**组（用户管理 + 审计日志）；结果页加「详情」无新菜单 |
| `src/App.tsx` | 加 `/admin/users` 路由 |
| `src/pages/routeWrappers.tsx` | 加 `UserAdminRoute` |
| `src/mocks/handlers.ts` | 新端点的 mock（**契约形状 + 生成类型标注**）+ 棘轮清单同步 |

**修改**（测试 4 个）：`tests/mocks/handlers.test.ts`（棘轮 + ajv 校验）、
`tests/layouts/MainLayout.test.tsx`（菜单组变动）、`e2e/audit_log.spec.ts`（菜单名 / 标题）、
`tests/pages/deliverables/deliverable_progress.test.tsx`（聚合端点替换 SIGN 直查）。

---

## Task T0：后端 —— TODO-065 聚合进度端点 `GET /deliverables/{id}/progress`

**Files:**
- Create: `pcs-backend/app/schemas/deliverable_progress.py`
- Modify: `pcs-backend/app/api/v1/deliverables.py`
- Test: `pcs-backend/tests/api/v1/test_deliverables_progress_aggregate.py`

**Interfaces:**
- Consumes: `WorkflowProgressService.get(db, workflow_type, workflow_id, project_id=...)`
  （`app/services/workflow_progress_service.py:82`）、`Deliverable.current_version_id`、
  `Deliverable.parent_deliverable_id`、`WorkflowType`（3 值枚举）。
- Produces: `GET /api/v1/deliverables/{deliverable_id}/progress` ⇒
  `DeliverableProgressResponse`（见下）。**T5 的前端消费它。**

**Step 1: 写失败测试**

```python
# pcs-backend/tests/api/v1/test_deliverables_progress_aggregate.py
"""TODO-065 聚合进度端点（2026-10-21 · P9B-2）。

## 为什么这个端点必须存在

`GET /workflow-progress/{workflow_type}/{workflow_id}` 是**单条**查询，
而三类工作流的 `workflow_id` 语义**各不相同**（实测 2026-10-21）：

| 工作流 | workflow_id | 依据 |
|---|---|---|
| SIGN | 版本 id | `deliverable_service.py:641` |
| CUSTOMER_APPROVAL_PROXY | **交付物 id** | `deliverable_service.py:931` |
| CHANGE_NOTICE | 变更单自身的 deliverable_id | `change_notice_service.py:388` |

⚠️ **P9B-1 计划把 CUSTOMER_APPROVAL_PROXY 写成「版本 ID」，与代码不符** ——
本测试把**代码的语义**钉死（R-2）。
"""
import uuid

import pytest


@pytest.mark.asyncio
async def test_progress_sections_cover_three_workflow_types(client, auth_headers, ...):
    ...
```

> **执行时**：按本仓 `tests/api/v1/` 的既有 fixture 写法落地上述断言
> （**先读** `pcs-backend/tests/api/v1/test_deliverables.py` 与
> `pcs-backend/tests/conftest.py`，**照抄**它的 client / 鉴权 / 造数方式，
> 不要自造）。必含的断言：
>
> 1. **三段都在**（`SIGN` / `CHANGE_NOTICE` / `CUSTOMER_APPROVAL_PROXY`），
>    顺序固定（按 `WorkflowType` 的枚举顺序）。
> 2. `SIGN` 段的 `workflow_id == deliverable.current_version_id`。
> 3. **`CUSTOMER_APPROVAL_PROXY` 段的 `workflow_id == deliverable.deliverable_id`**
>    （**不是** version_id —— 这是 R-2 的钉子）。
> 4. `CHANGE_NOTICE` 段 `available is False` 且 `reason` 非空
>    （恒不可用，见 R-3）。
> 5. 交付物**无版本**时 `SIGN` 段 `available is False` + `reason` 非空。
> 6. 5 态计数（`pending` / `in_progress` / `completed` / `skipped` / `failed`）
>    **恒存在**（含 0）。
> 7. **越权 404**：别的项目的交付物 ⇒ 404（不是 403）。
> 8. **查询数守卫**（禁 N+1）：整次请求的 SELECT 数 ≤ 5。

**Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_deliverables_progress_aggregate.py -q`
Expected: FAIL —— 端点不存在（404 / 路由未匹配）。

**Step 3: 写 schema**

```python
# pcs-backend/app/schemas/deliverable_progress.py
"""交付物工作流进度聚合响应（TODO-065 · P9B-2）。

## 为什么每段都带 `available` + `reason`

空数组会被读成「这条流程一个节点都没有」，而真相是「这类工作流对本交付物
不存在」—— 两者在界面上**长得一样**（`workflow_progress.py:65` 已为单条端点
写过同样的警告：未知工作流 ⇒ 404，**不是** 空数组）。

⇒ 每段显式给 `available`；`available=false` 时 `reason` **必填**（中文原文，
前端原样显示）。

## 三类工作流的 `workflow_id` 语义（2026-10-21 实测）

| 工作流 | workflow_id | 依据 |
|---|---|---|
| SIGN | 版本 id | `deliverable_service.py:641` |
| CUSTOMER_APPROVAL_PROXY | **交付物 id** | `deliverable_service.py:931` |
| CHANGE_NOTICE | 变更单自身的 deliverable_id | `change_notice_service.py:388` |

⚠️ **P9B-1 计划写的是「CUSTOMER_APPROVAL_PROXY → 版本 ID」，与代码不符** ——
本实现按**代码**（R-2），并同步修订 `TODOS.md` TODO-065 的那张表。
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field

from app.schemas.workflow_progress import WorkflowProgressItemResponse


class WorkflowProgressSection(BaseModel):
    """一类工作流在本交付物上的进度。"""

    workflow_type: str = Field(description="SIGN / CHANGE_NOTICE / CUSTOMER_APPROVAL_PROXY")
    workflow_id: uuid.UUID | None = Field(
        default=None,
        description="该类工作流的主键；不可用时为 null",
    )
    available: bool = Field(
        description="该类工作流是否可解析（false 时 reason 必填，不得返回空数组冒充「无步骤」）"
    )
    reason: str | None = Field(
        default=None,
        description="available=false 时的原因（中文原文，前端原样显示）",
    )
    total: int = 0
    pending: int = 0
    in_progress: int = 0
    completed: int = 0
    skipped: int = 0
    failed: int = 0
    items: list[WorkflowProgressItemResponse] = Field(default_factory=list)


class DeliverableProgressResponse(BaseModel):
    """一个交付物的三类工作流进度。"""

    deliverable_id: uuid.UUID
    sections: list[WorkflowProgressSection]
```

**Step 4: 写端点**

在 `pcs-backend/app/api/v1/deliverables.py` 追加（复用文件里已有的
`_authorize` / `_READ_ROLES` / `DeliverableService`）：

```python
@router.get(
    "/deliverables/{deliverable_id}/progress",
    response_model=DeliverableProgressResponse,
    summary="交付物的工作流进度聚合（三类工作流一次拿全）",
)
async def get_deliverable_progress(
    deliverable_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> DeliverableProgressResponse:
    """一次返回本交付物三类工作流的进度（TODO-065）。

    关联规则**留在后端**：三类工作流的 `workflow_id` 语义各不相同，
    「变更单怎么关联到本交付物」是**后端的业务规则**，不是前端的拼装活。
    """
    require_roles(actor, *_READ_ROLES)
    deliverable = await _authorize(db, actor, deliverable_id)
    sections = await DeliverableService.progress_sections(
        db, deliverable=deliverable
    )
    return DeliverableProgressResponse(
        deliverable_id=deliverable_id, sections=sections
    )
```

**Step 5: 写 service 方法**（`pcs-backend/app/services/deliverable_service.py`）

```python
@classmethod
async def progress_sections(
    cls, db: AsyncSession, *, deliverable: Deliverable
) -> list[WorkflowProgressSection]:
    """三类工作流各自的进度段（TODO-065）。

    ⚠️ **CHANGE_NOTICE 恒不可用**：`deliverables.parent_deliverable_id` 这一列
    **全仓从未被写**（只有 model + schema 声明），而变更单的创建链
    （`ChangeNoticeService.create_change_notice`）抛 `NotImplementedError`
    （P9A-DLV-007 / TODO-057）⇒ 本仓**不可能**有变更单工作流。

    ⇒ 这里**仍然实现关联规则**（`parent_deliverable_id` + `deliverable_type`），
    让 TODO-057 落地后**不用改端点**；现在它**如实返回不可用 + 原因**，
    而不是返回空数组冒充「这条流程一个节点都没有」（R-3）。
    """
    sections: list[WorkflowProgressSection] = []

    # ① SIGN —— workflow_id = 版本 id
    if deliverable.current_version_id is None:
        sections.append(
            WorkflowProgressSection(
                workflow_type=WorkflowType.SIGN.value,
                workflow_id=None,
                available=False,
                reason="尚未签发版本，无签署流程",
            )
        )
    else:
        sections.append(
            await cls._progress_section(
                db,
                workflow_type=WorkflowType.SIGN,
                workflow_id=deliverable.current_version_id,
                project_id=deliverable.project_id,
            )
        )

    # ② CHANGE_NOTICE —— workflow_id = 变更单自身的 deliverable_id
    change_notice_id = await cls._latest_change_notice_id(
        db, deliverable_id=deliverable.deliverable_id
    )
    if change_notice_id is None:
        sections.append(
            WorkflowProgressSection(
                workflow_type=WorkflowType.CHANGE_NOTICE.value,
                workflow_id=None,
                available=False,
                reason="未创建变更单（变更单创建链未接通：P9A-DLV-007）",
            )
        )
    else:
        sections.append(
            await cls._progress_section(
                db,
                workflow_type=WorkflowType.CHANGE_NOTICE,
                workflow_id=change_notice_id,
                project_id=deliverable.project_id,
            )
        )

    # ③ CUSTOMER_APPROVAL_PROXY —— workflow_id = **交付物 id**（实测 R-2）
    sections.append(
        await cls._progress_section(
            db,
            workflow_type=WorkflowType.CUSTOMER_APPROVAL_PROXY,
            workflow_id=deliverable.deliverable_id,
            project_id=deliverable.project_id,
        )
    )
    return sections
```

配套两个私有方法（同样写在 service 里）：

```python
@staticmethod
async def _latest_change_notice_id(
    db: AsyncSession, *, deliverable_id: uuid.UUID
) -> uuid.UUID | None:
    """本交付物的变更单（`deliverable_type=CHANGE_NOTICE` + `parent_deliverable_id`）。

    口径：**取最新一个**（`created_at desc, deliverable_id` 作 tiebreaker）。
    ⚠️ `parent_deliverable_id` 当前**全仓从未被写** ⇒ 本方法恒返回 None；
    口径先定下来，等 TODO-057 落地时不用重新讨论「多个变更单取哪个」。
    """
    row = (
        await db.execute(
            select(Deliverable.deliverable_id)
            .where(
                Deliverable.parent_deliverable_id == deliverable_id,
                Deliverable.deliverable_type == "CHANGE_NOTICE",
            )
            .order_by(Deliverable.created_at.desc(), Deliverable.deliverable_id)
            .limit(1)
        )
    ).scalar_one_or_none()
    return row


@staticmethod
async def _progress_section(
    db: AsyncSession,
    *,
    workflow_type: WorkflowType,
    workflow_id: uuid.UUID,
    project_id: uuid.UUID,
) -> WorkflowProgressSection:
    """一段进度。观测层 5 态计数恒存在（含 0）。"""
    data = await WorkflowProgressService.get(
        db, workflow_type=workflow_type, workflow_id=workflow_id, project_id=project_id
    )
    counts = data["counts"]
    return WorkflowProgressSection(
        workflow_type=workflow_type.value,
        workflow_id=workflow_id,
        available=True,
        reason=None,
        total=data["total"],
        pending=counts.get(WorkflowProgressState.PENDING, 0),
        in_progress=counts.get(WorkflowProgressState.IN_PROGRESS, 0),
        completed=counts.get(WorkflowProgressState.COMPLETED, 0),
        skipped=counts.get(WorkflowProgressState.SKIPPED, 0),
        failed=counts.get(WorkflowProgressState.FAILED, 0),
        items=[WorkflowProgressItemResponse.model_validate(r) for r in data["items"]],
    )
```

⚠️ 需要的 import：`WorkflowType` / `WorkflowProgressState`（`app.models.enums`）、
`WorkflowProgressService` / `WorkflowProgressItemResponse`。

**Step 6: 跑测试确认通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_deliverables_progress_aggregate.py -q`
Expected: PASS（8 条断言全绿）。

**Step 7: 契约重生成 + 守门**

```bash
cd pcs-backend && uv run python scripts/export_openapi.py
bash pcs-backend/scripts/gate_08_openapi_contract.sh
```
Expected: 阶段 1-3 全过；`pcs-frontend/openapi.snapshot.json` +
`pcs-frontend/src/types/api.d.ts` 已更新（**新增** `DeliverableProgressResponse`
与 `WorkflowProgressSection`）。

**Step 8: 提交**

```bash
cd pcs-backend && git add app/schemas/deliverable_progress.py app/api/v1/deliverables.py \
  app/services/deliverable_service.py tests/api/v1/test_deliverables_progress_aggregate.py \
  ../pcs-frontend/openapi.snapshot.json ../pcs-frontend/src/types/api.d.ts
git commit -m "feat(P9B-2): TODO-065 交付物工作流进度聚合端点"
```
⚠️ **契约产物由 G-08 钩子在 commit 之后重生成** ⇒ commit 后要
`git add -A && git commit --amend --no-edit` 补一次（见 `.wolf/STATUS.md` 的
「契约产物」条）。

---

## Task T1：后端 —— TODO-066 编辑审计读端点 `GET /records/{module}/{record_id}/edits`

**Files:**
- Create: `pcs-backend/app/schemas/record_edits.py`
- Create: `pcs-backend/app/api/v1/record_edits.py`
- Modify: `pcs-backend/app/api/v1/__init__.py`
- Test: `pcs-backend/tests/api/v1/test_record_edits_endpoint.py`

**Interfaces:**
- Consumes: `records_actions.resolve_record_model(module, need_mixin=False)` 与
  `records_actions._load_record(...)`（**复用，不重写**）、
  `AuditAction.RECORD_EDITED`、`AuditLog` 模型。
- Produces: `GET /api/v1/records/{module}/{record_id}/edits` ⇒
  `RecordEditsResponse`。**T4 的记录状态时间线消费它。**

**Step 1: 写失败测试**

必含断言：
1. 两条 `RECORD_EDITED` 审计 ⇒ `items` 2 条，`changed_fields` 正确。
2. **别的 action 的审计行不出现**（如 `CREATE` / `DELIVERABLE_ISSUED`）。
3. **越权 404**（别的项目的记录）。
4. **未知 module ⇒ 422** `RECORD_MODULE_UNKNOWN`。
5. **缺 9 态列的模块（`cost_est`）也能用**（`need_mixin=False`）⇒ 200。
6. `detail_json` **畸形**（不是 dict / 缺 `changed_fields`）⇒ `changed_fields == []`
   且**不 500**。
7. 分页：`?limit=1` ⇒ 1 条，`total` 仍是全部条数。

**Step 2: 跑测试确认失败**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_record_edits_endpoint.py -q`
Expected: FAIL（端点不存在）。

**Step 3: 写 schema**

```python
# pcs-backend/app/schemas/record_edits.py
"""编辑审计读端点的响应（TODO-066 · P9B-2）。

## 为什么需要它

SPEC §6.21 P9A-LCK-006 要求 409 弹窗提供「查看差异」，而差异内容在**编辑审计**
里（`audit_logs` 的 `RECORD_EDITED`）。但唯一的读端点 `GET /audit-logs`
**限 SYSTEM_ADMIN** ⇒ 普通 DESIGNER 拿到冲突弹窗却**点不开差异**。

⚠️ **`audit_logs` 表没有 `project_id`** ⇒ 授权只能靠
「`resource_type` + `resource_id` → 反查记录 → 记录的项目」。

## `changed_fields` 是**字段名列表**，不是值

一次大改版几十 KB，审计里只记字段名（ADR-0048 §⑦）。本端点**原样透传**，
**不**去回查旧值 —— 回查旧值需要快照表，而那是另一个设计（TODO）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class RecordEditItem(BaseModel):
    """一次编辑。"""

    audit_id: uuid.UUID
    changed_fields: list[str] = Field(
        default_factory=list, description="被改的字段名列表（不是值）"
    )
    overwrote_stale_baseline: bool = Field(
        default=False,
        description="这次编辑是否覆盖了无法校验的基线（ADR-0048 §⑦ 的额外审计行）",
    )
    user_id: uuid.UUID | None = Field(default=None, description="操作人；系统动作为空")
    occurred_at: datetime


class RecordEditsResponse(BaseModel):
    """一条记录的编辑历史。"""

    record_type: str = Field(description="RECORD_TYPE_REGISTRY 的键")
    record_id: uuid.UUID
    items: list[RecordEditItem]
    total: int
```

**Step 4: 写端点**

```python
# pcs-backend/app/api/v1/record_edits.py
"""记录编辑审计读端点（TODO-066 · P9B-2）。

⚠️ **授权靠记录，不靠审计行**：`audit_logs` 无 `project_id` ⇒ 先取记录
（`resolve_record_model` + `_load_record` 的项目守卫），再用
`resource_type = module` + `resource_id = str(record_id)` 查审计。
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.enums import AuditAction
from app.models.system import AuditLog
from app.schemas.record_edits import RecordEditItem, RecordEditsResponse
from app.api.v1.records_actions import _load_record

router = APIRouter(tags=["records"])

# 与批注同口径：能读记录的人就能看它的编辑历史。
_READ_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN")


@router.get(
    "/records/{module}/{record_id}/edits",
    response_model=RecordEditsResponse,
    summary="列记录的编辑审计（按项目守卫）",
)
async def list_record_edits(
    module: str,
    record_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> RecordEditsResponse:
    """列一条记录的编辑历史，最新在前。

    ⚠️ **只认 `action = RECORD_EDITED`**（ADR-0048 §⑦ 强制）—— 不得用
    「该记录最近一条审计」泛匹配去凑。
    """
    require_roles(actor, *_READ_ROLES)
    # need_mixin=False：编辑历史对**任何有归属项目**的记录都开放
    # （没有 sign_status 的表也能查它改过什么）。
    record = await _load_record(
        db, module=module, record_id=record_id, actor=actor, need_mixin=False
    )
    conditions = [
        AuditLog.action == AuditAction.RECORD_EDITED.value,
        AuditLog.resource_type == module,
        AuditLog.resource_id == str(record_id),
    ]
    total = await db.scalar(select(func.count()).select_from(AuditLog).where(*conditions))
    rows = (
        await db.execute(
            select(AuditLog)
            .where(*conditions)
            .order_by(AuditLog.occurred_at.desc(), AuditLog.audit_id.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    items: list[RecordEditItem] = []
    for row in rows:
        detail = row.detail if isinstance(row.detail, dict) else {}
        fields = detail.get("changed_fields")
        items.append(
            RecordEditItem(
                audit_id=row.audit_id,
                changed_fields=[str(f) for f in fields] if isinstance(fields, list) else [],
                overwrote_stale_baseline=bool(detail.get("overwrote_stale_baseline", False)),
                user_id=row.user_id,
                occurred_at=row.occurred_at,
            )
        )
    return RecordEditsResponse(
        record_type=module, record_id=record_id, items=items, total=int(total or 0)
    )
```

⚠️ `AuditLog` 的列名以 `app/models/system.py` 为准（`audit_id` / `user_id` /
`action` / `resource_type` / `resource_id` / `detail` / `occurred_at`）——
**执行时先读那个 model 确认**，不要照抄字段名。

**Step 5: 挂路由**

在 `pcs-backend/app/api/v1/__init__.py` 加
`from app.api.v1.record_edits import router as record_edits_router` 与
`api_router.include_router(record_edits_router)`。

**Step 6: 跑测试确认通过**

Run: `cd pcs-backend && uv run pytest tests/api/v1/test_record_edits_endpoint.py -q`
Expected: PASS（7 条断言全绿）。

**Step 7: 契约重生成 + 守门**

```bash
cd pcs-backend && uv run python scripts/export_openapi.py
bash pcs-backend/scripts/gate_08_openapi_contract.sh
```
Expected: 全过；契约新增 `RecordEditsResponse` / `RecordEditItem`。

**Step 8: 提交**

```bash
cd pcs-backend && git add app/schemas/record_edits.py app/api/v1/record_edits.py \
  app/api/v1/__init__.py tests/api/v1/test_record_edits_endpoint.py \
  ../pcs-frontend/openapi.snapshot.json ../pcs-frontend/src/types/api.d.ts
git commit -m "feat(P9B-2): TODO-066 按项目守卫的编辑审计读端点"
```

---

## Task T2：前端 api 层（4 个客户端）

**Files:**
- Create: `src/api/meta.ts`、`src/api/recordActions.ts`、`src/api/deliverables.ts`、
  `src/api/admin.ts`
- Test: `tests/api/record_actions_api.test.ts`、`tests/api/deliverables_api.test.ts`、
  `tests/api/admin_api.test.ts`

**Interfaces:**
- Consumes: `api` 实例（`src/api/client.ts`，baseURL `/api/v1` + Bearer 拦截器）；
  `EditableRecordType`（`src/api/records.ts`）。
- Produces:
  - `metaApi.stateMachine(): Promise<StateMachineResponse>`、
    `metaApi.permissions(): Promise<PermissionItem[]>`
  - `recordActionsApi.{obsolete, requestReversal, reversalDecision, submitApproval,
    approvalStep, abandonChange}` + `commentsApi.{list, create}`
  - `deliverablesApi.progress(deliverableId)` + `deliverablesApi.actions(deliverableId)`
  - `adminApi.{listUsers, disableUser, syncAdUsers}`

**Step 1: 写失败测试**（沿用 `tests/api/records_api.test.ts` 的 MSW `setupServer`
+ 闭包捕获写法）

必含断言：
- **每个动作的请求体逐字断言**（`reason` / `decision` / `approval_role` /
  `approval_depth` **不被改名**）⇒ 这是 P9B-1 的 RF-13 同形坑（字段名漂移
  TS 不报错 ⇒ 后端 422/403）。
- `submitApproval` 传 `{approval_role, approval_depth}`（**snake_case**）。
- `approvalStep` 传 `{decision, reason}`。
- `reversalDecision` 传 `{decision, reason}`。
- `obsolete` / `requestReversal` / `abandonChange` 传 `{reason}`。
- 批注 `create` 传 `{body}`；`list` 传 `limit` / `offset`。
- `deliverablesApi.progress` 打 `GET /deliverables/{id}/progress`（**不是**
  `workflow-progress/SIGN/...`）。
- `adminApi.disableUser` 用 **PUT**（不是 POST），路径 `/admin/users/{id}/disable`。

**Step 2: 跑测试确认失败**

Run: `cd pcs-frontend && npx vitest run tests/api/record_actions_api.test.ts tests/api/deliverables_api.test.ts tests/api/admin_api.test.ts`
Expected: FAIL（模块不存在）。

**Step 3: 写 `src/api/meta.ts`**

```ts
/**
 * Meta API 客户端（状态机 + 权限矩阵）—— P9B-2。
 *
 * ## 为什么操作栏的数据源是 meta 而不是前端表
 *
 * SPEC §6.3 给了一张「状态 → 按钮」的冻结表，但**前端硬编码它 = 第二份真相源**：
 * 后端加一个状态迁移（`app/services/state_machine.py` 的 `ALLOWED_TRANSITIONS`），
 * 前端的按钮表不会跟着变 ⇒ 用户看到一个**注定 409** 的按钮。
 *
 * ⇒ 按钮渲染由 `GET /meta/state-machine` 驱动（后端从 `ALLOWED_TRANSITIONS` 生成），
 * 角色门禁用同一条迁移的 `allowed_roles`（SPEC §5.5.1：**前端不得自行推导能力**）。
 *
 * ⚠️ 契约里的 schema 名是 **`StateTransition-Output`** —— 后端
 * `meta.py` 的 `StateTransition` 与 `models/enums.py` 的同名枚举撞名，
 * FastAPI 给前者加了 `-Output` 后缀。
 */
import { api } from './client';
import type { components } from '../types/api';

export type StateMachineResponse = components['schemas']['StateMachineResponse'];
export type StateTransition = components['schemas']['StateTransition-Output'];
export type PermissionItem = components['schemas']['PermissionItem'];

export const metaApi = {
  stateMachine: (): Promise<StateMachineResponse> =>
    api.get<StateMachineResponse>('/meta/state-machine').then((r) => r.data),
  permissions: (): Promise<PermissionItem[]> =>
    api.get<PermissionItem[]>('/meta/permissions').then((r) => r.data),
};
```

**Step 4: 写 `src/api/recordActions.ts`**

```ts
/**
 * 记录级写面客户端（9 态动作 + 批注）—— P9B-2 · SPEC §6.3 / §7.19.1。
 *
 * ⚠️ **`{module}` 是 `RECORD_TYPE_REGISTRY` 的键**（`CostEstResult` /
 * `cooling_tower_result` …），**不是表名** —— 后端 `resolve_record_model`
 * 查的就是那个注册表，传错 ⇒ 422 `RECORD_MODULE_UNKNOWN`。
 * ⇒ 复用 `src/api/records.ts` 的 `EditableRecordType`，**不另起词表**。
 *
 * ⚠️ **请求体字段名逐字取后端 schema**（`approval_role` / `approval_depth` /
 * `decision` / `reason`）—— 中间层改名 ⇒ TS 不报错 ⇒ 后端 422（RF-13 同形坑）。
 */
import { api } from './client';
import type { components } from '../types/api';
import type { EditableRecordType } from './records';

export type RecordActionResponse = components['schemas']['RecordActionResponse'];
export type SubmitApprovalResponse = components['schemas']['SubmitApprovalResponse'];
export type ApprovalStepResponse = components['schemas']['ApprovalStepResponse'];
export type CommentResponse = components['schemas']['CommentResponse'];
export type CommentListResponse = components['schemas']['CommentListResponse'];

/** 送审时要指定的待批角色（7 值词表，后端 `ApprovalRole`）。 */
export type ApprovalRole =
  | 'DESIGNER' | 'CHECKER' | 'REVIEWER' | 'APPROVER'
  | 'SYSTEM_ADMIN' | 'PROCESS_CONTROLLER' | 'DATA_ADMIN';

export const recordActionsApi = {
  obsolete: (module: EditableRecordType, recordId: string, reason: string) =>
    api.post<RecordActionResponse>(`/records/${module}/${recordId}/obsolete`, { reason })
      .then((r) => r.data),

  requestReversal: (module: EditableRecordType, recordId: string, reason: string) =>
    api.post<RecordActionResponse>(`/records/${module}/${recordId}/request-reversal`, { reason })
      .then((r) => r.data),

  reversalDecision: (
    module: EditableRecordType,
    recordId: string,
    decision: 'APPROVE' | 'REJECT',
    reason: string,
  ) =>
    api.post<RecordActionResponse>(`/records/${module}/${recordId}/reversal-decision`, {
      decision, reason,
    }).then((r) => r.data),

  submitApproval: (
    module: EditableRecordType,
    recordId: string,
    approvalRole: ApprovalRole,
    approvalDepth: number,
  ) =>
    api.post<SubmitApprovalResponse>(`/records/${module}/${recordId}/submit-approval`, {
      approval_role: approvalRole,
      approval_depth: approvalDepth,
    }).then((r) => r.data),

  approvalStep: (
    module: EditableRecordType,
    recordId: string,
    decision: 'PASS' | 'REJECT',
    reason: string,
  ) =>
    api.post<ApprovalStepResponse>(`/records/${module}/${recordId}/approval-step`, {
      decision, reason,
    }).then((r) => r.data),

  abandonChange: (module: EditableRecordType, recordId: string, reason: string) =>
    api.post<RecordActionResponse>(`/records/${module}/${recordId}/abandon-change`, { reason })
      .then((r) => r.data),
};

export const commentsApi = {
  list: (module: EditableRecordType, recordId: string, params?: { limit?: number; offset?: number }) =>
    api.get<CommentListResponse>(`/records/${module}/${recordId}/comments`, { params })
      .then((r) => r.data),
  create: (module: EditableRecordType, recordId: string, body: string) =>
    api.post<CommentResponse>(`/records/${module}/${recordId}/comments`, { body })
      .then((r) => r.data),
};
```

**Step 5: 写 `src/api/deliverables.ts`**

```ts
/**
 * 交付物读面客户端 —— P9B-2。
 *
 * ⚠️ `progress` 打的是**聚合端点** `GET /deliverables/{id}/progress`
 * （TODO-065），**不是** `GET /workflow-progress/SIGN/{version_id}` ——
 * 三类工作流的 `workflow_id` 语义各不相同（SIGN = 版本 id，
 * CUSTOMER_APPROVAL_PROXY = **交付物 id**），关联规则归后端（R-2）。
 */
import { api } from './client';
import type { components } from '../types/api';

export type DeliverableProgressResponse =
  components['schemas']['DeliverableProgressResponse'];
export type WorkflowProgressSection = components['schemas']['WorkflowProgressSection'];
export type DeliverableActionsListResponse =
  components['schemas']['DeliverableActionsListResponse'];

export const deliverablesApi = {
  progress: (deliverableId: string): Promise<DeliverableProgressResponse> =>
    api.get<DeliverableProgressResponse>(`/deliverables/${deliverableId}/progress`)
      .then((r) => r.data),

  actions: (
    deliverableId: string,
    params?: { limit?: number; offset?: number },
  ): Promise<DeliverableActionsListResponse> =>
    api.get<DeliverableActionsListResponse>(`/deliverables/${deliverableId}/actions`, { params })
      .then((r) => r.data),
};
```

**Step 6: 写 `src/api/admin.ts`**

```ts
/**
 * ADMIN 用户管理客户端 —— P9B-2 · SPEC §7.20 / P9A-ADM-001/002。
 *
 * ⚠️ 三个端点**全部限 SYSTEM_ADMIN**（`admin_users.py:32` 写死的
 * `_ADMIN_ROLES`）⇒ 前端按角色隐藏入口，但**鉴权在后端**（前端隐藏是体验，
 * 后端 403 是边界）。
 */
import { api } from './client';
import type { components } from '../types/api';

export type AdminUser = components['schemas']['AdminUserOut'];
export type UserDisabled = components['schemas']['UserDisabledOut'];
export type AdSyncResult = components['schemas']['AdSyncResultOut'];

export const adminApi = {
  listUsers: (): Promise<AdminUser[]> =>
    api.get<AdminUser[]>('/admin/users').then((r) => r.data),

  disableUser: (userId: string): Promise<UserDisabled> =>
    api.put<UserDisabled>(`/admin/users/${userId}/disable`).then((r) => r.data),

  syncAdUsers: (): Promise<AdSyncResult> =>
    api.post<AdSyncResult>('/admin/users/sync').then((r) => r.data),
};
```

**Step 7: 跑测试确认通过**

Run: `cd pcs-frontend && npx vitest run tests/api/record_actions_api.test.ts tests/api/deliverables_api.test.ts tests/api/admin_api.test.ts`
Expected: PASS。

**Step 8: 提交**

```bash
cd pcs-frontend && git add src/api/meta.ts src/api/recordActions.ts src/api/deliverables.ts src/api/admin.ts \
  tests/api/record_actions_api.test.ts tests/api/deliverables_api.test.ts tests/api/admin_api.test.ts
git commit -m "feat(P9B-2): 记录动作 / 交付物进度 / meta / ADMIN 的 api 客户端"
```

---

## Task T3：记录操作栏 `RecordActions`（§6.3 · meta 驱动）

**Files:**
- Create: `src/components/common/RecordActions.tsx`
- Modify: `src/pages/results/resultModules.ts`（描述符加 `hasSignStatus`）
- Test: `tests/components/common/RecordActions.test.tsx`

**Interfaces:**
- Consumes: `metaApi`（T2）、`recordActionsApi`（T2）、`useAuth`（`role`）、
  `EditableRecordType`。
- Produces:
  ```ts
  interface RecordActionsProps {
    module: EditableRecordType;
    recordId: string;
    signStatus: string | null;   // null = 该模块无 9 态列 ⇒ 不渲染
    onDone: () => void;          // 动作成功后由宿主页刷新
  }
  ```
  **T4 的抽屉消费它。**

**Step 1: 写失败测试**

必含断言（对应 RF-1~RF-4）：
1. `signStatus = null` ⇒ **不渲染任何按钮**（且**不发** `/records/…` 请求）。
2. `DRAFT` ⇒ 有「提交批准」「弃用」；**没有**「通过 / 退回」。
3. `IN_APPROVAL` ⇒ 有「通过」「退回」；**没有**「提交批准」。
4. **角色不够 ⇒ 按钮禁用 + Tooltip 写明原因**（如 `role = 'DESIGNER'` 时
   `IN_APPROVAL` 的「通过」禁用）⇒ RF-1。
5. **送审角色选择器排除当前用户自己的角色** ⇒ RF-2。
6. **理由为空 ⇒ 弃用按钮禁用** ⇒ RF-3。
7. **动作请求体逐字断言**（`{reason}` / `{decision, reason}` /
   `{approval_role, approval_depth}`）。
8. 403 / 409 / 422 ⇒ **显示错误码 + 原文**，**不静默**（RF-5 的「失败明说」）。
9. 无后端端点的动作（变更申请 / 创建交付物 / 关闭凭证）⇒ **禁用 + Tooltip
   「后端未提供该操作」**（R-6）。

**Step 2: 跑测试确认失败**

Run: `cd pcs-frontend && npx vitest run tests/components/common/RecordActions.test.tsx`
Expected: FAIL（组件不存在）。

**Step 3: 描述符加 `hasSignStatus`**

在 `src/pages/results/resultModules.ts` 的每个描述符上加：

```ts
/**
 * 本模块**有没有 9 态列**（`sign_status`）。
 *
 * ⚠️ `cost_est_results` **没有** `sign_status`（后端模型注释：1:1 跟随设备、
 * 状态跟设备）⇒ 它的记录**不参与 9 态工作流** ⇒
 * `POST /records/{module}/{id}/<action>` 会 422 `RECORD_MODULE_UNSUPPORTED`。
 *
 * ⇒ 前端**不发注定失败的请求**：无状态列 ⇒ 不渲染操作栏（RF-4）。
 */
hasSignStatus: boolean;
```

（`cost_est` 的描述符填 `false`，其余 5 个填 `true`。）

**Step 4: 写组件**

```tsx
/**
 * RecordActions —— 记录操作按钮组（P9B-2 · SPEC §6.3）。
 *
 * ## 按钮从哪来
 *
 * ⚠️ **不是**前端硬编码的「状态 → 按钮」表 —— 而是
 * `GET /meta/state-machine` 的 `allowed[状态]`（后端从 `ALLOWED_TRANSITIONS`
 * 生成）+ 每条迁移的 `allowed_roles`（SPEC §5.5.1：前端不得自行推导能力）。
 *
 * ⇒ 后端加一个迁移，前端自动跟上；前端**不会**出现「注定 409」的按钮。
 *
 * ## 禁用优先于报错（SPEC §5.1「门禁前置」）
 *
 * - 角色不在 `allowed_roles` ⇒ 禁用 + Tooltip 写明「当前角色不可执行此操作」
 * - 前置条件（`preconditions`）非空 ⇒ 禁用 + Tooltip 列出前置条件
 * - 理由必填的动作（弃用 / 发起撤销）理由为空 ⇒ 禁用 + Tooltip 说明
 *
 * ## 没有后端端点的动作
 *
 * SPEC §6.3 里的「变更申请 / 创建交付物 / 关闭凭证」**没有端点**
 * （`INITIATE_CHANGE` / `APPLY_CHANGE` 无 API）⇒ 渲染成**禁用**按钮 +
 * Tooltip「后端未提供该操作」，**不静默隐藏、也不发假请求**（R-6）。
 */
```

组件主体（骨架）：

```tsx
export function RecordActions({
  module, recordId, signStatus, onDone,
}: RecordActionsProps): JSX.Element | null {
  const role = useAuth((s) => s.role);
  const [sm, setSm] = useState<StateMachineResponse | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  // 理由弹窗 / 送审弹窗的 state …

  useEffect(() => {
    let cancelled = false;
    void metaApi.stateMachine()
      .then((r) => { if (!cancelled) setSm(r); })
      .catch(() => { if (!cancelled) setError('无法读取状态机定义'); });
    return () => { cancelled = true; };
  }, []);

  if (!signStatus) return null;                       // RF-4：无 9 态列 ⇒ 不渲染
  if (!sm) return <Skeleton active />;

  const actions = sm.allowed[signStatus] ?? [];
  // …按 action 映射到按钮与请求 …
}
```

⚠️ **动作 → 端点的映射表**（前端唯一的映射，**不是** ACL）：

| `action`（状态机事件） | 按钮文案 | 端点 | 请求体 | 理由 |
|---|---|---|---|---|
| `SUBMIT_FOR_CHECK` | 提交批准 | `submit-approval` | `{approval_role, approval_depth}` | 弹窗选待批角色（排除自己） |
| `PASS_CHECK` | 通过 | `approval-step` | `{decision:'PASS', reason}` | 理由可选 |
| `REJECT_CHECK` | 退回 | `approval-step` | `{decision:'REJECT', reason}` | 理由**必填**（前端拦） |
| `OBSOLETE` | 弃用 | `obsolete` | `{reason}` | 理由**必填** |
| `REQUEST_REVERSAL` | 发起撤销 | `request-reversal` | `{reason}` | 理由**必填** |
| `APPROVE_REVERSAL` | 撤销批准 | `reversal-decision` | `{decision:'APPROVE', reason}` | 理由可选 |
| `REJECT_REVERSAL` | 撤销驳回 | `reversal-decision` | `{decision:'REJECT', reason}` | 理由必填 |
| `ABANDON_CHANGE` | 放弃变更 | `abandon-change` | `{reason}` | 理由可选 |

⚠️ **「退回」的理由必填是前端的加严**：后端 `ApprovalStepRequest.reason` 允许空
⇒ 退回时用户不写理由 ⇒ 事后「为什么退回」无从追溯 ⇒ **前端拦**（后端仍兜底）。

**Step 5: 跑测试确认通过**

Run: `cd pcs-frontend && npx vitest run tests/components/common/RecordActions.test.tsx`
Expected: PASS（9 条断言全绿）。

**Step 6: typecheck + lint**

Run: `cd pcs-frontend && npm run typecheck && npm run lint`
Expected: exit 0（⚠️ `npm run lint` 自带 `--max-warnings 0`，**别用裸
`npx eslint src/` 替代**）。

**Step 7: 提交**

```bash
cd pcs-frontend && git add src/components/common/RecordActions.tsx src/pages/results/resultModules.ts \
  tests/components/common/RecordActions.test.tsx
git commit -m "feat(P9B-2): 记录操作栏（meta 状态机驱动 + 门禁前置）"
```

---

## Task T4：记录详情抽屉 + 批注面板 + 记录状态时间线

**Files:**
- Create: `src/components/common/CommentPanel.tsx`、
  `src/components/common/RecordTimeline.tsx`、
  `src/pages/results/RecordDetailDrawer.tsx`
- Modify: `src/pages/results/ResultListPage.tsx`（每行加「详情」入口）
- Test: `tests/components/common/CommentPanel.test.tsx`、
  `tests/components/common/RecordTimeline.test.tsx`、
  `tests/pages/results/record_detail.test.tsx`

**Interfaces:**
- Consumes: `RecordActions`（T3）、`commentsApi`（T2）、`deliverablesApi` 不涉及、
  后端 TODO-066 的端点（**T2 之后需在 `src/api/recordActions.ts` 补一个
  `recordEditsApi.list`** —— 见 Step 3a）。
- Produces: `RecordDetailDrawer` 组件（T3 的宿主页）。

**Step 3a: 补 `recordEditsApi`**

在 `src/api/recordActions.ts` 追加：

```ts
/** 记录编辑审计（TODO-066 · 按项目守卫的读端点）。 */
export type RecordEditsResponse = components['schemas']['RecordEditsResponse'];

export const recordEditsApi = {
  list: (
    module: EditableRecordType,
    recordId: string,
    params?: { limit?: number; offset?: number },
  ): Promise<RecordEditsResponse> =>
    api.get<RecordEditsResponse>(`/records/${module}/${recordId}/edits`, { params })
      .then((r) => r.data),
};
```

**Step 1: 写失败测试**

`CommentPanel`（RF-7 / RF-8 / RF-12）：
1. 空白（`'   '`）⇒ 发送按钮**禁用**。
2. 发送成功后列表**追加**新批注且输入框清空。
3. `total` 为 2、`limit` 为 1 ⇒ 渲染**分页**（不是「加载更多」）。
4. 403 ⇒ 显示「无权查看」**而不是**空列表（RF-12）。

`RecordTimeline`（RF-5）：
5. 只渲染 `RECORD_EDITED` 来源的条目（后端已过滤 ⇒ 前端**不得**自行泛匹配）。
6. `changed_fields` 为空数组 ⇒ 显示「（未记录字段）」而不是空白。
7. 空态文案是「尚无编辑记录」⇒ **不得**写成「尚无动作记录」（R-10）。

`RecordDetailDrawer`（RF-13）：
8. **换记录**（同一抽屉，recordId 变）⇒ 抽屉内容**整体重建**，不残留上一条
   （断言抽屉的 `data-testid` 上带的记录 id 已更新 + 旧记录的行不再出现）。

**Step 2: 跑测试确认失败**

Run: `cd pcs-frontend && npx vitest run tests/components/common/CommentPanel.test.tsx tests/components/common/RecordTimeline.test.tsx tests/pages/results/record_detail.test.tsx`
Expected: FAIL（组件不存在）。

**Step 3: 写三个组件**

`CommentPanel`：

```tsx
/**
 * 批注面板（P9B-2 · SPEC §7.19.1「批注面板：右侧抽屉」）。
 *
 * ⚠️ **空白不是内容**：后端 `CommentCreateRequest` 拒纯空白
 * （`min_length=1` 拦不住 `"   "`）⇒ 前端 `trim()` 后为空 ⇒ 发送禁用。
 *
 * ⚠️ **分页按 `total`**：后端排序带 `comment_id` tiebreaker（`created_at` 是
 * `server_default=func.now()`，SQLite 下只有秒级粒度）⇒ 「加载更多直到空」
 * 会漏条或重复 ⇒ 按 `total` 算页数。
 *
 * ⚠️ **批注不写 `workflow_progress`**（ADR-0047 §①）：「有人留言」不是流程活动。
 */
```

`RecordTimeline`：

```tsx
/**
 * 记录状态时间线（P9B-2 · SPEC §7.19.1「状态时间线」）。
 *
 * ⚠️ **数据源是编辑审计**（`RECORD_EDITED`），**不是** `workflow_progress`
 * —— 后端注释明写：actions 回答「谁做了什么」，观测层回答「流程到哪一步了」，
 * 混用会把「查过一眼」也算成活动（RF-5 / R-10）。
 */
```

`RecordDetailDrawer`：

```tsx
/**
 * 记录详情抽屉（P9B-2 · SPEC §7.19.1）。
 *
 * 结构：顶部（状态徽章 + 哈希）→ 操作栏（`<RecordActions>`）→ 批注 → 状态时间线。
 *
 * ⚠️ **`key` 必须带 `recordType + recordId`** —— P9B-1 的 bug-2043
 * （跨模块切换残留上一模块的行）同形：换记录不重建 ⇒ 残留上一条的内容（RF-13）。
 */
```

**Step 4: 结果列表页接「详情」入口**

在 `src/pages/results/ResultListPage.tsx` 的操作列加一个「详情」按钮，
打开 `RecordDetailDrawer`：

```tsx
<RecordDetailDrawer
  key={`${module.recordType}:${rowId}`}
  module={module.recordType}
  recordId={rowId}
  record={row}
/>
```

**Step 5: 跑测试确认通过**

Run: `cd pcs-frontend && npx vitest run tests/components/common/CommentPanel.test.tsx tests/components/common/RecordTimeline.test.tsx tests/pages/results/record_detail.test.tsx`
Expected: PASS（8 条断言全绿）。

**Step 6: typecheck + lint + 提交**

```bash
cd pcs-frontend && npm run typecheck && npm run lint
git add src/components/common/CommentPanel.tsx src/components/common/RecordTimeline.tsx \
  src/pages/results/RecordDetailDrawer.tsx src/pages/results/ResultListPage.tsx \
  src/api/recordActions.ts tests/
git commit -m "feat(P9B-2): 记录详情抽屉 + 批注面板 + 记录状态时间线"
```

---

## Task T5：交付物进度页接聚合端点 + 动作时间线

**Files:**
- Modify: `src/pages/deliverables/DeliverableProgressPage.tsx`
- Test: `tests/pages/deliverables/deliverable_progress.test.tsx`（改）

**Interfaces:**
- Consumes: `deliverablesApi.progress` / `deliverablesApi.actions`（T2）、
  `WorkflowProgressPanel`（P9B-1）。
- Produces: 无新导出（改宿主页）。

**Step 1: 改测试为 RED**

必含断言：
1. 展开一行 ⇒ 请求打的是 **`GET /deliverables/{id}/progress`**（**不是**
   `GET /workflow-progress/SIGN/{version_id}`）。
2. 三段（SIGN / CHANGE_NOTICE / CUSTOMER_APPROVAL_PROXY）**都渲染**。
3. `available=false` 的段 ⇒ 显示 `reason` **原文**（不是空列表）⇒ RF-6。
4. `available=true` 但 `total=0` 的段 ⇒ 显示「尚无步骤记录」（与「不可用」**不同**
   的两种空态）。
5. 动作时间线区渲染 `actions.items`，`detail_json` **是 JSON 文本** ⇒ 前端
   `JSON.parse` 且**畸形时不崩**。

**Step 2: 跑测试确认失败**

Run: `cd pcs-frontend && npx vitest run tests/pages/deliverables/deliverable_progress.test.tsx`
Expected: FAIL（仍打旧的 `workflow-progress/SIGN` 端点）。

**Step 3: 改页面**

- 用 `deliverablesApi.progress(deliverableId)` 取聚合数据；
- 三段各渲染一个 `WorkflowProgressPanel`（`workflowType` 取段的 `workflow_type`）；
- 段 `available=false` ⇒ 渲染**原因**（不是面板）；
- 加「动作时间线」区（`deliverablesApi.actions`），空态「尚无动作记录」
  （**与**记录状态时间线的「尚无编辑记录」**不同**，R-10）。

**Step 4: 跑测试确认通过 + 门禁**

Run: `cd pcs-frontend && npx vitest run tests/pages/deliverables/deliverable_progress.test.tsx && npm run typecheck && npm run lint`
Expected: PASS + exit 0。

**Step 5: 提交**

```bash
cd pcs-frontend && git add src/pages/deliverables/DeliverableProgressPage.tsx \
  tests/pages/deliverables/deliverable_progress.test.tsx
git commit -m "feat(P9B-2): 交付物进度页接聚合进度端点 + 动作时间线"
```

---

## Task T6：ADMIN —— 用户管理页 + 审计日志（查询 + 导出）

**Files:**
- Create: `src/pages/admin/UserAdminPage.tsx`
- Modify: `src/pages/audit/AuditLogPage.tsx`（筛选 + 导出 + 标题）、
  `src/layouts/MainLayout.tsx`（菜单组）、`src/App.tsx`（路由）、
  `src/pages/routeWrappers.tsx`（`UserAdminRoute`）
- Test: `tests/pages/admin/user_admin.test.tsx`、
  `tests/pages/audit/AuditLogPage.test.tsx`（改）
- Modify: `e2e/audit_log.spec.ts`（菜单名 / 标题）

**Interfaces:**
- Consumes: `adminApi`（T2）、`auditApi`（既有）。
- Produces: 路由 `/admin/users`；菜单组「管理」。

**Step 1: 写失败测试（用户管理页）**

必含断言（RF-9 / RF-10 / RF-12）：
1. 列表渲染 `display_name` / `roles` / `status` / `token_version`。
2. 点「停用」⇒ 调 `PUT /admin/users/{id}/disable` ⇒ **重新拉列表**
   （断言 `GET /admin/users` 被调了 **2 次**：首次 + 停用后）⇒ RF-9。
3. AD 同步返回 `{ok:false, error:'目录连不上'}` ⇒ 显示 **error 原文**，
   **不得**显示「同步成功」⇒ RF-10。
4. AD 同步返回 `{ok:true, skipped_empty:true}` ⇒ 显示「枚举到 0 个用户，未做任何写入」。
5. 非 SYSTEM_ADMIN ⇒ 入口**不出现**（菜单项隐藏，SPEC §5.1「菜单项隐藏」）。

**Step 2: 跑测试确认失败**

Run: `cd pcs-frontend && npx vitest run tests/pages/admin/user_admin.test.tsx`
Expected: FAIL（页面不存在）。

**Step 3: 写用户管理页**

```tsx
/**
 * ADMIN 用户管理页（P9B-2 · SPEC §7.20「用户管理（AD 同步）」/ P9A-ADM-001/002）。
 *
 * ⚠️ **停用后必须重新拉列表** —— 乐观更新单行会让「token_version」显示旧值，
 * 而用户正是靠它确认「已签发的 refresh 全部失效」（ADR-0046 §⑤）。
 *
 * ⚠️ **AD 同步的失败方向**：`ok=false` = **什么都没做**（目录连不上），
 * `skipped_empty=true` = 枚举到 0 个用户 ⇒ 两种都不是「同步成功」。
 */
```

**Step 4: 审计日志页（筛选 + 导出）**

在 `src/pages/audit/AuditLogPage.tsx` 的 `audit-logs` tab 加：

- **筛选表单**：`action` / `resource_type` / `resource_id` / `user_id` /
  `occurred_after` / `occurred_before` ⇒ 直接映射 `auditApi.listAuditLogs` 的
  **已有**参数名（`src/api/audit.ts` 的 `ListAuditLogsParams`）⇒ **不改 api 层**。
- **导出 CSV**：按**同一筛选条件**循环拉页（每页 200，上限 **5000 行**），
  生成 CSV 并下载；超限时**显式提示截断**（RF-11）。
  ⚠️ CSV 字段**要转义**（字段里可能有逗号 / 引号 / 换行）⇒ 自己写 `csvCell()`。
- **标题**：「Audit Query (F-P2-009 Sprint 3)」⇒ 改「**审计日志**」。

**Step 5: 菜单与路由**

`src/layouts/MainLayout.tsx`：
- 现在的组「审计」（`{ key: '/audit/logs', label: 'Audit Query (F-P2-009)' }`）
  ⇒ 改成组「**管理**」，含两项：
  `{ key: '/admin/users', label: '用户管理' }`、
  `{ key: '/audit/logs', label: '审计日志' }`。
- ⚠️ **「用户管理」项按角色显示**：`role !== 'SYSTEM_ADMIN'` ⇒ 不渲染该项
  （SPEC §5.1「菜单项隐藏」）。

`src/App.tsx`：加 `{ path: 'admin/users', element: <UserAdminRoute /> }`。
`src/pages/routeWrappers.tsx`：加 `UserAdminRoute`（照现有 `AuditLogRoute` 的写法）。

**Step 6: 改 e2e**

`e2e/audit_log.spec.ts`：
- `gotoAuditViaMenu` 的菜单项名 `'Audit Query (F-P2-009)'` ⇒ `'审计日志'`；
- 标题断言 `/Audit Query/` ⇒ `/审计日志/`。

**Step 7: 跑测试 + 门禁**

Run: `cd pcs-frontend && npx vitest run tests/pages/admin/user_admin.test.tsx tests/pages/audit/AuditLogPage.test.tsx tests/layouts/MainLayout.test.tsx && npm run typecheck && npm run lint`
Expected: PASS + exit 0。

**Step 8: 提交**

```bash
cd pcs-frontend && git add src/pages/admin/UserAdminPage.tsx src/pages/audit/AuditLogPage.tsx \
  src/layouts/MainLayout.tsx src/App.tsx src/pages/routeWrappers.tsx \
  tests/pages/admin/user_admin.test.tsx tests/pages/audit/AuditLogPage.test.tsx e2e/audit_log.spec.ts
git commit -m "feat(P9B-2): ADMIN 用户管理页 + 审计日志筛选与导出"
```

---

## Task T7：QA gate + 收口

**Files:**
- Modify: `src/mocks/handlers.ts` + `src/mocks/seed/signFlow.ts`（新端点的 mock）
- Modify: `tests/mocks/handlers.test.ts`（**棘轮清单** + ajv 校验）
- Create: `e2e/record_actions.spec.ts`（一条）

**Step 1: 补 mock + 棘轮**

新增 mock（**契约形状 + 生成类型标注**）：
- `GET /api/v1/meta/state-machine`（**注意**：P9B-1 已 mock 5 个 meta 端点 ⇒
  这是第 6 个；`meta/state-machine` 在 `openapi.snapshot.json` 的 paths 里
  ⇒ **属于「契约端点」** ⇒ 棘轮清单要同步加一行 + 加 ajv 校验）。
- `GET /api/v1/deliverables/{id}/progress`
- `GET /api/v1/records/{module}/{id}/edits`
- `GET /api/v1/records/{module}/{id}/comments` + `POST` 同路径
- `POST /api/v1/records/{module}/{id}/<action>`（8 个写端点）
- `GET /api/v1/admin/users` + `PUT .../disable` + `POST .../sync`

⚠️ `tests/mocks/handlers.test.ts` 的棘轮清单（`devOnly ∩ 契约`）**新增即红是预期**
⇒ 照着红更新清单 + 补 ajv 校验（**不是**把断言删了）。

**Step 2: E2E 一条**

`e2e/record_actions.spec.ts`：登录 → 结果页 → 打开记录详情 → 点「提交批准」→
选待批角色（**不含自己的角色**）→ 提交 → 断言请求体含 `approval_role` +
`approval_depth` → 断言按钮组按状态变化。

⚠️ antd 的 Button 对**两个汉字**的标签会插空格（"提 交"）⇒ Playwright 的
`getByRole('button', {name: '提交批准'})` **匹配不到** ⇒ 必须用正则
`/提\s*交\s*批\s*准/`（P9B-1 实测踩过）。

**Step 3: 浏览器回归（gstack browse）**

工具：`$B = ~/.claude/skills/gstack/browse/dist/browse`（Linux 下需 `CI=1`）。

清单：
1. login 200 → dashboard 渲染
2. 结果页 → 「详情」→ 抽屉打开 + 操作栏按状态渲染 + 批注区可输入
3. 送审弹窗的**角色下拉不含自己的角色**
4. 交付物进度页展开一行 ⇒ 网络面板看到 **`/deliverables/{id}/progress`**
   （**不是** `workflow-progress/SIGN/...`）⇒ 三段都在
5. 不可用段显示 `reason` 原文
6. ADMIN 用户管理页（用 SYSTEM_ADMIN 登录）⇒ 列表 + 停用 + 同步
7. 审计日志页 ⇒ 筛选 + 导出（下载的 CSV 行数 = 筛选结果行数）
8. 控制台无 antd / React / TS error
9. 核心 mock 端点无 404

**Step 4: 门禁全绿**

```bash
cd pcs-frontend && npm run typecheck && npm run lint && npm run test
cd pcs-backend && uv run pytest -q
bash pcs-backend/scripts/gate_08_openapi_contract.sh
```
Expected: 全绿；**前端 ≥ 809 passed**（P9B-1 收口基线），
**后端 ≥ 5168 passed / 77 skipped**（P9B-1 收口基线）。

**Step 5: 报告落盘**

`.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-p9b-2.md`
⚠️ `.gstack/` 已 gitignore ⇒ 报告**只落本地**；关键结论同步进 `TODOS.md`。

**Step 6: 收口**

- `TODOS.md`：登记 §6.3 无端点的三个按钮（变更申请 / 创建交付物 / 关闭凭证）
  + 修订 **TODO-065** 的 `workflow_id` 表（R-2）+ 关闭 TODO-065 / TODO-066。
- `.wolf/buglog.json`：本批修的 bug 逐条登记（`fix_commit` 必填）。
- `.wolf/STATUS.md`：用 `/handoff` 重生成。

**Step 7: 提交**

```bash
git add -A && git commit -m "chore(P9B-2): QA gate + 收口"
```

---

## 验收（全 lane）

- [ ] `GET /deliverables/{id}/progress` 返回**三段**，每段带 `available` + `reason`，
      `CUSTOMER_APPROVAL_PROXY` 段的 `workflow_id == deliverable_id`。
- [ ] `GET /records/{module}/{id}/edits` 按**项目**守卫（越权 404），
      只返回 `RECORD_EDITED`，`changed_fields` 是字段名列表。
- [ ] 操作栏由 `meta/state-machine` 驱动；角色不够 ⇒ 禁用 + 原因；
      送审角色选择器**排除自己**；理由必填处禁用。
- [ ] `cost_est`（无 `sign_status`）**无操作栏**，但**可批注**。
- [ ] 批注：空白禁用；按 `total` 分页；403 显示「无权查看」。
- [ ] 记录状态时间线用**编辑审计**；交付物动作时间线用 `/deliverables/{id}/actions`；
      两者**不混**、空态文案**不同**。
- [ ] 交付物进度页打的是**聚合端点**；不可用段显示**原因**。
- [ ] ADMIN：停用后**重拉列表**；AD 同步的失败方向**不显示成成功**；
      审计导出覆盖**筛选后的全部行**（超限显式提示）。
- [ ] 前端 typecheck + lint + 单测全绿（≥ 809）；后端 pytest 全绿（≥ 5168）；
      OpenAPI 契约前后端一致。

---

## 尚未解决的问题（开工前需裁决或登记）

1. **§6.3 的三个按钮没有后端端点**（变更申请 / 创建交付物 / 关闭凭证）
   ⇒ 本批渲染成禁用 + 说明（R-6），并登记 `TODOS.md`。
   ⚠️ 「变更申请」的下游是 `ChangeNoticeService.create_change_notice`
   （**NotImplementedError**）⇒ 即使补端点也要先解 TODO-057。
2. **交付物级签署写面（issue / sign-step / 代录）不可用**
   ⇒ `signature_matrices` 恒 0 行且无创建方（R-1）⇒ 本批不做。
   ⚠️ 若用户坚持本批就上签署 UI，需要先做 `SignatureMatrixService`（TODO-057）。
3. **变更单的关联列 `parent_deliverable_id` 全仓从未被写**
   ⇒ 聚合端点的 `CHANGE_NOTICE` 段恒不可用（R-3）。
   ⇒ TODO-065 的「一个交付物有多个变更单时取哪个」口径已定（取最新），
   但**数据源仍缺**。
4. **SPEC §5.1 的 `<Can permission="...">` 组件不存在**，且后端**不发射**
   `x-permission`（全仓 0 处）⇒ 本批用 `meta/permissions` 的
   `frontend_behavior` 代替（R-5）⇒ **须登记 SPEC 修订**。
5. **SPEC §6.3 的按钮表与 `meta/state-machine` 可能不一致**
   ⇒ 本批以 meta 为准（R-4）⇒ **须登记 SPEC 修订**（逐条比对后写进
   `docs/PCS-UI-SPEC.md` §12.4 修订记录）。
6. **ADMIN「角色分配」没有后端端点**（`/admin/users` 只有 list / disable / sync；
   角色只能靠 AD 同步的组映射）⇒ 本批不做 ⇒ 登记 `TODOS.md`。
7. **ADMIN「AI 开关 / Prompt 模板 / 系统参数」** ⇒ 属 P9B-3 或更后。
8. **审计导出的行数上限 5000** ⇒ 超限截断（R-9 / RF-11）；
   若运维要全量导出，需后端导出端点（另议）。
9. **本计划尚未过 `/plan-eng-review`** ⇒ 建议开工前过一轮
   （重点：T3 的 meta 驱动是否会与 §6.3 的冻结表冲突；T5 的聚合端点是否
   值得为一个恒空的 CHANGE_NOTICE 段而新建）。

---

## GSTACK REVIEW REPORT

（待 `/plan-eng-review` 后填写。）
