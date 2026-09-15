# 后端 ↔ PCS-UI-SPEC 契约对账报告

- **日期**：2026-09-16
- **触发**：P4.5 前端补课 Sprint (P45) 启动；用户裁决要求编码前对齐 10 项契约
- **基线**：P45-0-4 commit `11c1589` → P45-0-4.5 commit `df8383a`（V1.1）
- **规范基准**：`docs/PCS-UI-SPEC.md` V1.0 + `pcs-backend/docs/openapi.json`（Task 4.5 冻结 114 paths）

## 对账清单

| # | 契约项 | 状态 | 落点 / 缺口 |
|---|---|---|---|
| 1 | OpenAPI 3.1（按模块拆分）| ✅ | `pcs-backend/docs/openapi.json`（377K, 114 paths / 98 schemas）；20+ routers（workspaces / records / streams / pipe / sim / meta 等）按模块拆分 |
| 2 | Pydantic JSON Schema + uiSchema | ⚠️ 50% | JSON Schema 派生已含；**uiSchema 缺** — Task 18.5 (P45-2-3) 4h 后端交付，在 Task 19 SchemaForm 开始前完成 |
| 3 | 枚举字典 JSON（value/label/color/icon/order）| ✅ | `GET /api/v1/meta/enums` 返 **19 组**：RecordSignStatus/StreamSignStatus 9 态全集 + DeliverableSignStatus/WorkspaceType/EquipmentStatus(N/E/D/M/F)/CalcStatus/ActualDataStatus/SnapshotStatus + P2 ConfigStatus/ConfigTransition + SUP-008 PipeType/CheckResult/PumpOperation/DesignStage/FlowPattern/TwoPhaseCheck + StreamDataMode(CHEMICAL/PETROLEUM/SOLID) + StreamCaseType(物流 4 值)/StatePointCaseType(状态点 4 值) |
| 4 | 状态机迁移表（含权限/前置/副作用）| ✅ | `GET /api/v1/meta/state-machine` 返 21 条 transitions，每条含 from/action/to/allowed_roles/preconditions/side_effects；从 `app/services/state_machine.ALLOWED_TRANSITIONS + TRANSITION_ROLES + SNAPSHOT_TRIGGERS + TRANSITION_AUDIT_ACTION` 派生（单一来源） |
| 5 | 权限矩阵 CSV | ✅ | `GET /api/v1/meta/permissions` + `GET /meta/permissions.csv`；AST 扫 `app/api/v1/*.py` 所有 `require_roles(user, "X", ...)` 调用点 + state_machine `TRANSITION_ROLES`；含 7 实际使用角色 (DESIGNER/CHECKER/REVIEWER/APPROVER/SYSADMIN/SYSTEM_ADMIN/PROCESS_CONTROLLER/VIEWER) |
| 6 | 统一错误码表 | ✅ | `GET /api/v1/meta/error-codes` 返 **94 条**（AST 扫全仓 PcsError 实例 + 3 auth）；含 STREAM_UNRELIABLE_BLOCKED / PIPE_CLASS_BAD_TRANSITION / CHANGE_NOTICE_BAD_STATE / REVERSAL_BAD_STATE 等 |
| 7 | 请求/响应示例 | ✅ | OpenAPI 每端点含 request body / response example；FastAPI 自动生成 |
| 8 | Mock Server + Seed 数据 | ❌ 未交付 | **Task 5 (P45-0-5)** MSW + Seed + vitest shape 验证 — 与 V1.1 后端并行（不同人） |
| 9 | 文件上传/异步任务/通知规范 | ⚠️ 契约未冻结 | P0/P1 已规划后端实现（customer_approval_attachments.file_hash / ARQ 任务队列 / audit_logs + 通知中心），但前端契约未冻结。**用户裁决：入 P5，拆三层**：L1 multipart 上传契约 + 存储路径 + 病毒扫描占位（P5 起点）；L2 task_id + 轮询/SSE + 进度查询（P5 中期 HEAT 前）；L3 通知契约（站内信 + 审计联动 + 跳转路由）（P5 后期）|
| 10 | 前端契约冻结清单 | ✅ | Task 4.5 commit `df8383a` 冻结 openapi.json 114 paths；前端 `api:check` drift gate 守护（Task 3 已落）|

## 已交付（V1.1 commit df8383a 后）

- 19 组 enum 字典
- 13 事件 × 9 态 state-machine + from/action/to/allowed_roles/preconditions/side_effects
- 7 角色权限矩阵（含 SYSTEM_ADMIN/SYSADMIN 别名）
- 94 条错误码（AST 全仓派生）
- /meta/permissions.csv 导出端点
- 1625 backend 测试全过 / ruff 0 errors

## 阻塞 P5 推进的缺口（按风险序）

1. **Task 5 MSW + Seed** — 前端 13 组件离线开发依赖；2h
2. **Task 18.5 uiSchema** — Task 19 SchemaForm 关键输入；4h（依赖 V1.1 已满足）
3. **P5 起点 L1/L2/L3 契约** — 文件上传 / 异步任务 / 通知；详见 §P5 起点契约

## 用户裁决记录（2026-09-16）

| # | 项 | 裁决 |
|---|---|---|
| 1 | OpenAPI | ✅ 无需动作 |
| 2 | uiSchema | 立即做，4h；在 Task 5 后、Task 19 前 |
| 3 | 枚举字典 | ⚠️ → ✅ V1.1 已扫全 PCS-UI-SPEC §3.5 + 后端 enums.py + schemas/stream.py，补全 19 组 |
| 4 | 状态机迁移表 | ⚠️ → ✅ V1.1 补 allowed_roles/preconditions/side_effects |
| 5 | 权限矩阵 | ⚠️ → ✅ V1.1 grep 全仓 `require_roles` 装饰器，导出全集 |
| 6 | 错误码 | ⚠️ → ✅ V1.1 grep `PcsError(` 全仓，94 条导出 |
| 7 | 请求/响应示例 | ✅ 无需动作 |
| 8 | Mock Server | Task 5，2h；可并行于 V1.1 |
| 9 | 文件上传/异步/通知 | 入 P5，拆三层；契约 P5 起点冻结，实现分批 |
| 10 | 契约冻结清单 | ✅ 无需动作 |

## 执行顺序（用户裁决 4）

```
V1.1 元 API 补全（后端，df8383a 已完）✅
  ↓
Task 5 MSW + Seed（前端，2h）  ← 当前
  ↓
uiSchema（后端，4h，Task 18.5）  ← 下一步
  ↓
Task 6 组件库启动
```

## 批次调整

| 批 | 原 | 新 |
|---|---|---|
| 批 0 | Task 1–5 | Task 1–5 + Task 4.5（V1.1） |
| 批 1 | Task 6–18 | Task 6–18 + Task 18.5（uiSchema，可在批 1 末）|
| 批 2 | Task 19–26 | 不变 |
| 批 3 | 提纲 | 不变 |

执行方式（累积裁决）：
- 批 0：inline，Task 1→2→3→4→4.5→5 顺序
- 批 1：subagent-driven，Task 6–18 + 18.5
- 批 2：Task 19–20 inline，Task 21–26 subagent
- 批 3：另编

## P5 起点必须补充的契约（入 P5 计划）

P5 启动时，除现有 openapi.json 外，必须冻结：

### L1 — 文件上传契约（P5 起点）

```
POST /api/v1/attachments
  multipart/form-data: file (≤20MB) + resource_type + resource_id
  → 202 { attachment_id, file_hash, status: "scanning" }

GET /api/v1/attachments/{id}
  → 200 { attachment_id, file_hash, status, download_url, scanned_at }

GET /api/v1/attachments/{id}/download
  → 200 binary stream
```

### L2 — 异步任务契约（P5 中期 HEAT 前）

```
POST /api/v1/tasks
  { task_type, payload }
  → 202 { task_id, status: "queued" }

GET /api/v1/tasks/{id}
  → 200 { task_id, status, progress: {pct, current_step, total_steps}, result_url? }

GET /api/v1/tasks/{id}/result
  → 200 { ...计算结果... }

GET /api/v1/tasks/{id}/events  (SSE，可选)
  → text/event-stream
```

### L3 — 通知契约（P5 后期）

```
GET /api/v1/notifications?unread_only=true&limit=20&offset=0
  → 200 { items: [{ id, type, title, body, route, read_at }], total, unread_count }

POST /api/v1/notifications/{id}/read
  → 204

GET /api/v1/notifications/unread-count
  → 200 { unread_count: number }
```

type 取值：CALC_COMPLETED / STALE_DETECTED / SIGN_PENDING / SIGN_REJECTED / SIGN_APPROVED / CHANGE_REQUESTED / TASK_COMPLETED
route 格式：`/<resource>/<id>` 或 `{ modal: "SignApprovalModal", params: { ... } }`

P5 计划编写时，这三条作为起点交付物，与 HEAT/PUMP 等模块并行。