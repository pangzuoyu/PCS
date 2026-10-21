# P9B-1 实施计划：结果记录页 + 编辑锁前端（SPEC §6.21 / §6.7.1 / §6.22~§6.24）

> **For agentic workers:** REQUIRED SUB-SKILL: `superpowers:executing-plans`
> （或 `superpowers:subagent-driven-development`）。
> ledger: `.superpowers/sdd/PCS-PLAN-P9B-1-结果记录页与编辑锁/progress.md`
> **本计划已过 `/plan-eng-review`（2026-10-21）** —— 裁决逐条落在正文里，
> 末尾有 `## GSTACK REVIEW REPORT`。

**Goal:** 兑现 SPEC §6.21（编辑锁 P9A-LCK-001~006）、§6.7.1（CIA 确认
P9A-CIA-001/002）、§6.22~§6.24（待办 / 实时状态 / 观测进度）的**前端**，
并让 6 类可编辑结果表真正可编辑（带锁、带基线、409 可处理）。

**Architecture:** 「**一个通用结果页 + 6 个类型化模块描述符**」，不是 6 份页面。
差异只有四处（record_type / 路径 / 主键名 / 字段清单），其余（列表 / 编辑抽屉 /
取锁 / 心跳 / 基线 / 保存 / 409 弹窗）全部共用。字段清单用 **`keyof ResponseType`
约束** ⇒ 字段改名 = **编译期错误**。基线判定抽成 **`useEditBaseline` hook**，
所有编辑入口共用。

**Tech Stack:** React 18 + TypeScript 5.5 + antd 5 + axios + zustand + vitest +
MSW（node 与 browser 两用）+ Playwright（e2e/ 已装）。

**Spec:**
- `docs/PCS-UI-SPEC.md` **V2.1** —— §6.21 / §6.7.1 / §6.20 / §6.22 / §6.23 / §6.24 / §3.2 / §5.2
- `spec/PCS-REQ-2026-002-SPEC-P9 …` **V2.1** §7.2（P9B 验收）、§4.2（前端纪律）
- `docs/adr/0048-edit-lock-storage.md`（两层锁）、`0047`（观测层）、`0049`（通知/待办）

---

## Global Constraints

1. **类型全部来自生成的 `src/types/api.d.ts`**（`components['schemas'][...]`），
   **不手写**（TODO-064 已删 18 个漂移手写类型）。⚠️ `src/types/*.ts` 还有 57 个
   同名手写类型（TODO-064），**本批不碰**（除非要 import）。
2. **mock 必须与真端点同形**：契约端点的 mock 响应体**用生成的类型标注**
   （`satisfies components['schemas'][...]`），**不得手写自由 dict**
   ⇒ 这正是 bug-2040 的根源（mock 与真端点不同源 ⇒ 漂移被藏住 ⇒ 只有生产构建才炸）。
   ⚠️ 本仓**没有** orval / openapi-msw（`package.json` 只有 `openapi-typescript`）
   ⇒ **不引入新依赖**，用类型标注 + `satisfies` 兜住。
   ⚠️ `tests/mocks/handlers.test.ts` 的**棘轮清单**（`devOnly ∩ 契约`）必须同步更新
   —— 新增即红是**预期**（照着红更新清单 + 加 ajv 校验）。
3. **`record_type` 用 `RECORD_TYPE_REGISTRY` 的键**：`CostEstResult` / `FiltrationResult` /
   `OpenChannelResult` / `cooling_tower_result` / `flare_system_result` / `psychro_result`
   —— **不是表名**（3 个是 snake_case）。⚠️ `/locks` **校验**，传错 ⇒ 404。
   ⚠️ **全仓只有这一套**（TODO-060 已归一）。数据层**不得**保留分类词字段。
4. **PATCH 必须带并发基线**，且基线**分三档**（见 T2 的 `useEditBaseline`）。
   ⚠️ **所有从后端拿到的字段，回传时一律原样透传响应里的字符串** ——
   **不得过 `new Date()` 或任何日期解析**（JS `Date` 只到毫秒，PG `TIMESTAMPTZ`
   是微秒 ⇒ 过一次 `Date` 就**每次假 409**）。
   ⚠️ 展示用的格式化走**独立函数**，**格式化值不得用于回传**。
   ⚠️ `expected_hash` 原样回传（后端格式：`sha256().hexdigest()[:16]` ⇒
   **小写 hex 16 字符、无前缀**；不大写、不加 `0x`、不 trim 后改大小写）。
5. **不得自动重试**任何 409（锁续期、保存冲突）—— 重试仍是 409，且把「失效」掩盖成
   「网络抖动」。
6. **失败方向**：拿不到就明说（`unknown` basis、空态、403），**不得**静默降级成
   「无冲突」。
7. **release 是 best-effort**：失败**一律忽略**（409 / 403 / 404 / 500 / 网络错误），
   **不弹窗、不阻断关闭流程**；锁靠 30min TTL 回收。
8. 提交约定：conventional commits，**无 attribution 行**。长 commit message 写文件后
   `git commit -F <file>`（`!` `（）` 会被 shell 吃掉）。
9. ⚠️ **不要建 worktree**（本仓历史事故，见 `.wolf/STATUS.md`）。

## Review Focus

以下失败模式是 SPEC 蕴含、但**任何任务的测试若不专门写就不会覆盖**的。
每条都指派给了拥有该代码的任务。

| # | 失败模式 | 期望行为 | 归属 |
|---|---|---|---|
| RF-1 | **保存成功后不刷新基线** —— 编辑会重算 `record_hash`，基线不刷新 ⇒ 下一次保存**必 409**（假冲突） | 保存成功后用响应里的新 `record_hash` 覆盖基线 | T3 |
| RF-2 | **`expected_hash` 漏传** ⇒ 409 `basis=no_baseline`，症状是「保存总是失败」且**不指向漏传** | 请求体必须断言带基线；弹窗按 `no_baseline` 给「刷新后重试」出口 | T1 / T2 |
| RF-3 | **他人持锁** ⇒ 误写成「无权限」 | 只**禁用保存**，浏览 / 复制 / 查看哈希**不阻断**；禁用原因写「谁在改」 | T2 |
| RF-4 | **锁失效（renew 409）** ⇒ 自动重试 | **不重试**，表单转只读，提示「编辑锁已失效，请重新进入编辑」 | T2 |
| RF-5 | **`changed_by` / `changed_at` 为 null** ⇒ 用 `updated_at` 冒充 | 弹窗文案显示「未知」；**不得**拿 `updated_at` 顶替 | T2 |
| RF-6 | Redis 降级（`degraded=true`）⇒ 横幅**阻断**编辑 | 横幅**不阻断**（放行的是体验，拦住并发的是 DB 层）；文案取后端 `message` 原文 | T4 |
| RF-7 | `sign_status` 锁定态（CHECKED / IN_APPROVAL …）⇒ 仍显示可编辑 | 编辑按钮**禁用**（前端不等后端 422 才报错） | T3 |
| **RF-8** | **基线只发一档** —— `record_hash` 为空（从未 finalize）的行 ⇒ 后端退到 `expected_updated_at`；两档皆无 ⇒ **永远 409** | 三档判定（`useEditBaseline`），判定在**打开抽屉时**完成，保存只透传 | T2 |
| **RF-9** | **时间戳过 `new Date()`** —— 微秒被截成毫秒 ⇒ 每次假 409 | 基线里的时间戳**原样透传**响应字符串 | T1 / T2 / T3 |
| **RF-10** | **抽屉关闭白占锁 30min** ⇒ 同事看到「张三 正在编辑」而张三 已走 | 抽屉关闭即 release；未保存修改先弹确认；页面卸载用 `sendBeacon` | T3 |
| **RF-11** | **`record_type` 传分类词**（"PIPE"）⇒ `/locks` / `/change-impact` 404 | 数据层只放注册表键；展示分类走「键 → UI 表示」映射表 + fallback | T4 |
| **RF-12** | **禁用原因不分类** ⇒ 用户以为是自己没权限 | Tooltip 区分「状态不可编辑」与「无基线（联系管理员）」两类 | T2 / T3 |
| **RF-13** | **基线字段名在中间层漂移**（`expected_hash` → `expectedHash`）⇒ ⚠️ **TypeScript 不报错**（实测 2026-10-21 编译通过）⇒ 请求体缺基线 ⇒ **每次保存 409 `no_baseline`** | 中间层与请求体**同一套 snake_case 字段名**；**测试断言请求体**（不是 hook 返回值） | T1 / T2 / T3 |

---

## P9B 全景与本批边界

P9 SPEC §4.3/§4.4 的 P9B 共 8 个工作项（7.5–10 人周）。**本计划做并发控制 +
变更影响确认 + 结果页 + 观测/待办面板 + 交付物进度页**（它们互为一套：都吃
P9A-4 D0~D3 的契约）。

| P9B 工作项 | 本批 | 去向 |
|---|---|---|
| 并发控制前端（§6.21 + P9A-LCK-001~006） | ✅ **T2/T3/T4** | — |
| 变更影响分析前端（§6.7.1 确认动作） | ✅ **T4**（组件扩展 + 接线） | 高亮 / 对比另批 |
| 6 类结果记录页 | ✅ **T3** | — |
| workflow_progress / 待办 / 实时状态（§6.22~§6.24） | ✅ **T5** + 宿主页 **T6** | — |
| 签署流程前端（操作栏 / 批注 / 状态时间线） | ❌ | P9B-2（后端 `/records/{module}/{id}/comments` 等已就绪） |
| ADMIN 用户管理前端（`/admin/users` 3 端点已交付） | ❌ | P9B-2 |
| ADMIN 审计日志前端 | ❌ | P9B-2（`AuditLogPage` 已有雏形） |
| ADMIN 系统参数前端 | ❌ | P9B-3 |
| 物流手动创建向导 + 校对 UI | ❌ | P9B-3 |

⚠️ **T5 的面板本批有宿主**（T6 交付物进度页，只 SIGN），**不是死代码**。

---

## 事实基础（2026-10-21 实测，非推断）

**后端契约**（OpenAPI 冻结在 `p9_007`）：

| 模块 | 列表路径 | 主键 | record_type | PATCH 请求体 | 响应 |
|---|---|---|---|---|---|
| cool_tower | `/cool-tower/results` | `id` | `cooling_tower_result` | `CoolTowerResultUpdateRequest` | `CoolTowerResultResponse` |
| filtration | `/filtration/results` | `result_id` | `FiltrationResult` | `FiltrationUpdateRequest` | `FiltrationResultResponse` |
| flare | `/flare/results` | `id` | `flare_system_result` | `FlareResultUpdateRequest` | `FlareResultResponse` |
| open_channel | `/open-channel/results` | `result_id` | `OpenChannelResult` | `OpenChannelUpdateRequest` | `OpenChannelResultResponse` |
| psychro | `/psychro/results` | `id` | `psychro_result` | `PsychroResultUpdateRequest` | `PsychroResultResponse` |
| cost_est | `/cost-est/results` | `result_id` | `CostEstResult` | `CostEstUpdateRequest` | `CostEstResultResponse` |

- 6 个 `*UpdateRequest` **都有** `expected_hash` + `expected_updated_at` ⇒ **同构**，
  可用**统一签名**（无「不带基线」的 PATCH）。
- 6 个响应**都有** `record_hash`（16 hex 小写）；**只有 `cost_est` 没有 `updated_at`**。
- 列表：`GET ?project_id=`（**必填**）+ 分页。返回信封有**两种**：
  `{items,total,limit,offset}`（cool-tower / flare / psychro）与
  `{items,total,skip,limit}`（filtration / open-channel / cost-est）⇒
  **只读 `items` + `total`**，分页字段名差异不消费。
- **可编辑状态只有 `DRAFT` / `CHANGE_PENDING`**（后端 `*_PERSIST_SIGN_STATUS_LOCKED`），
  其余 7 态后端拒改。
- 409 响应体 = 仓库统一信封 `{code, message, detail, trace_id}`，冲突对象在
  `detail.conflict`，`basis` ∈ `record_hash` / `updated_at` / `no_baseline`。
- `/locks/{rt}/{id}/acquire|renew|release`：
  - **acquire**：`200 + success` / `409`（他人持锁，响应体仍是 `LockResponse`，带 `holder`）
    / `200 + degraded=true`（Redis 挂了）。
  - ⚠️ **acquire 的 Lua「已经是我的也算成功」**（`_ACQUIRE_LUA`：`current == ARGV[1] ⇒
    expire; return 1`）⇒ 误点关闭再打开**不会卡住**；后端注释明写这是为
    「页面刷新 / 路由回退再 acquire」而设。
  - **锁身份 = user**（key `lock:edit:{rt}:{id}`，value 是 hash 存 `user_id`）
    ⇒ 同一用户多标签共享一把锁；标签 1 release 会删掉标签 2 也在用的锁。
  - **release**：非持有者 ⇒ **409**（实测 `locks.py:254`，**不是** 403）。
  - ⚠️ `/locks` **校验** `record_type` ⇒ 传表名 **404**。

**基线阶梯（后端 `check_conflict` 的实际语义）**：

```
当前 record_hash 非空   ⇒ 比 hash：不等 ⇒ 409 (basis=record_hash)
当前 record_hash 为空   ⇒ 比 updated_at：不等 ⇒ 409 (basis=updated_at)
                        → 无 updated_at / 客户端没给基线 ⇒ 409 (basis=no_baseline)
```

- 全库 **21 张表**有 `record_hash` + `updated_at`；
  **5 张**有 `record_hash` **无** `updated_at`（与本批相关的是 **`cost_est_results`**）。
- 6 张可编辑结果表里 **5 张**有 `updated_at`（cool-tower / filtration / flare /
  open-channel / psychro），**只有 `cost_est_results` 没有** ⇒
  它的行若 hash 为空 ⇒ **两档皆无 ⇒ 永远 409**。
- dev 库 6 张结果表**总 0 行** ⇒ 「两档皆无」当前**无真实数据** ⇒ 前端第三档是
  **防御性代码**（但必须有：cost_est 一旦出现空 hash 行就会命中）。
- `record_hash` 格式：`sha256(...).hexdigest()[:16]` ⇒ **小写 hex 16 字符、无前缀**。

**交付物（宿主页用）**：

- `GET /deliverables?project_id=` → `{items, total}`；**已有** `limit`(≤500) + `offset`。
  ⚠️ **已有项目守卫**（`check_project_access_or_404`，`deliverables.py:116`）
  ⇒ `project_id` 是**筛选条件**，但**授权在后端**，前端不必也不得自行过滤。
- `DeliverableResponse` 有 `current_rev`（**非空 str**，自由文本 "A/B/0/1/AS-BUILT/X"，
  **无值域约束**），**没有** `version_id` ⇒ 本批后端加 `current_version_id`。
- `GET /deliverables/{id}/versions` → 数组（`version_id` + `rev`）。
- `WorkflowType`（后端枚举，**三值**）：`SIGN` / `CHANGE_NOTICE` /
  `CUSTOMER_APPROVAL_PROXY` ⇒ ⚠️ **没有 `DOC_PROXY`**（「代录」= `CUSTOMER_APPROVAL_PROXY`）。
- ⚠️ **三类工作流的 `workflow_id` 语义不同**（本批只做 SIGN）：
  `SIGN` / `CUSTOMER_APPROVAL_PROXY` → **版本 ID**；
  `CHANGE_NOTICE` → **变更单自身的 deliverable_id**（变更单是独立交付物，
  `deliverable_type=CHANGE_NOTICE`）⇒ 前端拿不到 ⇒ 聚合端点延到 P9B-2（**TODO-065**）。

**前端现状**：

- 已有：`src/api/locks.ts`（`editLockApi` + `EDITABLE_RECORD_TYPES` +
  `isEditableRecordType` + **待删的 `editRecordApi`**）、`src/api/changeImpact.ts`、
  `src/api/errors.ts`（`extractConflict` / `conflictKind`）、
  `src/api/notifications.ts`、`src/api/todos.ts`（2026-10-21 新增）。
- **6 个结果页一个都没有**：无路由、无 Page、无列表调用；`src/` 里 **0 个 PATCH 调用**。
- `ChangeImpactPanel` 现有 `record_type` 是**分类词**（`PIPE` / `PUMP` / `UTIL`）
  ⇒ **第 7 套词表**；后端 `/change-impact` 对未登记词 **404**
  （`change_impact.py:134`）⇒ T4 必须改成注册表键。
- 可复用：`useAuth`（`userId` 由后端 `/auth/me` 给，**不得**前端派生）、
  `api` 实例、`PageHeader` / `HashBadge` / `StateBadge` / `NumericCell` / `ModuleLayout`。
- 既有范式：请求契约测试用 MSW `setupServer` + 闭包捕获（`tests/api/edit_lock_api.test.ts`）。
- ⚠️ `tsconfig.json` 把 `tests/` 纳入类型检查 ⇒ 测试 fixture 也必须类型正确。

---

## 文件结构

**新建**（12 个）：

| 文件 | 职责 |
|---|---|
| `src/api/records.ts` | 记录域单一来源：`EditableRecordType` + `EDITABLE_RECORD_TYPES` + `PatchBaseline` + `RESULT_BASES` + `recordsApi`（list/get/patch） |
| `src/hooks/useEditBaseline.ts` | **三档基线判定**（hash / updated_at / 两档皆无）⇒ `{disabled, reason, expected_hash?, expected_updated_at?}`（⚠️ 与 `PatchBaseline` **同一套 snake_case 字段名** ⇒ 展开即兼容，见 RF-13） |
| `src/hooks/useEditLock.ts` | 取锁 → 60s 心跳 → 失效转只读；release（best-effort） |
| `src/components/common/EditLockIndicator.tsx` | 锁状态（他人持锁 / 失效） |
| `src/components/common/EditConflictModal.tsx` | 409 弹窗，按 `basis` 三值 + `unknown` 兜底分流 |
| `src/pages/results/resultModules.ts` | 6 个模块的**类型化描述符**（唯一字段清单来源） |
| `src/pages/results/ResultListPage.tsx` | 通用列表页（描述符驱动） |
| `src/pages/results/ResultEditDrawer.tsx` | 通用编辑抽屉（锁 + 基线 + 表单 + 保存 + 409） |
| `src/components/common/WorkflowProgressPanel.tsx` | §6.24 观测进度面板（tab 可配置） |
| `src/components/common/TodoPanel.tsx` | §6.22 待办面板 |
| `src/components/common/RealtimeStatusBanner.tsx` | §6.23 实时状态（降级） |
| `src/store/degradation.ts` | zustand：降级横幅的全局状态 |

**修改**（7 个）：

| 文件 | 改什么 |
|---|---|
| `src/api/locks.ts` | **删** `editRecordApi` + `PatchBaseline`；`EDITABLE_RECORD_TYPES` / `EditableRecordType` **移到 `records.ts`**（本文件从 `records.ts` import ⇒ 单向 `locks → records`，**无循环**）；头注释改为「锁操作客户端」 |
| `src/api/audit.ts` | 加 `listRecordEdits`（`changed_fields` 来自编辑审计；⚠️ 端点限 SYSTEM_ADMIN ⇒ 见 T2 的 403 降级） |
| `src/components/common/ChangeImpactPanel.tsx` | ① `record_type` 改**注册表键**；② 新增「注册表键 → UI 表示」映射表（**value 不得是分类词**）+ fallback；③ 扩展 props：系统判定 `confirm` + 人工判定 `manual-adjust` |
| `src/components/common/NotificationCenter.tsx` | 待办 tab 换成 `<TodoPanel>` |
| `src/layouts/MainLayout.tsx` | 顶栏降级横幅 + 6 条结果页菜单 + 交付物进度页菜单 |
| `src/App.tsx` | 6 条结果页路由 + 1 条交付物进度页路由 |
| `src/mocks/handlers.ts` | 6 模块的 list/detail/patch mock（**契约形状 + 生成类型标注**）+ `/deliverables*` + 三条场景 handler（他人持锁 / 三种 409 / 降级） |

**后端**（1 个文件 + 契约）：`pcs-backend/app/schemas/deliverable.py` 加
`current_version_id`；`pcs-backend/app/services/deliverable_service.py` 用
`selectinload` 取当前版本（**禁 N+1**）；`pcs-backend/app/api/v1/deliverables.py`
序列化时带上。⇒ 契约重生成（G-08 门禁）。

---

## Task T0：后端 —— `DeliverableResponse.current_version_id`

**Files:**
- Modify: `pcs-backend/app/schemas/deliverable.py`、`app/services/deliverable_service.py`、
  `app/api/v1/deliverables.py`
- Test: `pcs-backend/tests/api/v1/test_deliverables_current_version.py`（新）

**Interfaces:**
- Produces: `DeliverableResponse.current_version_id: uuid.UUID | None`

- [ ] **Step 1：写失败测试**

  ```python
  async def test_current_version_id_points_at_current_rev(db_session, ...):
      """current_version_id 必须是 current_rev 对应的那个 version 的 id。

      这是「防止未来有人改了 current_rev 的算法但忘了 current_version_id」的唯一防线。
      """
      d = await get_deliverable(db_session, deliverable_id=...)
      assert d.current_version_id is not None
      v = await get_version(db_session, version_id=d.current_version_id)
      assert v.rev == d.current_rev

  async def test_current_version_id_is_none_when_no_version(db_session, ...):
      """没有版本行的交付物 ⇒ current_version_id 为 None。

      ⚠️ 判据是「**没有版本行**」，不是「current_rev 为 null」——
      current_rev 是**非空 str**（ORM `Mapped[str]` + schema 必填），永不为 null。
      """
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**（字段不存在）

- [ ] **Step 3：实现**
  - schema：`current_version_id: uuid.UUID | None = None`
  - service：`select(Deliverable).options(selectinload(Deliverable.versions))`
    ⇒ **禁止**在序列化时逐行查版本（**N+1**）
  - 取当前版本 = `rev == current_rev` 的那条；匹配不到 ⇒ `None`

- [ ] **Step 4：跑测试确认通过** ⇒ **PASS**

- [ ] **Step 5：N+1 验收（约束 2）**
  100 个交付物时 SQL 查询数 **≤ 3**（交付物 + versions + 计数）⇒ 用 SQL 日志或
  `EXPLAIN ANALYZE` 确认。**不达标就回 Step 3 改 join / selectinload。**

- [ ] **Step 6：契约重生成 + 全量门禁**
  ```bash
  bash pcs-backend/scripts/gate_08_openapi_contract.sh
  cd pcs-backend && uv run pytest -q
  ```
  ⚠️ **前端类型从 `./api` 生成，不得手写** ⇒ 验收：
  ```bash
  grep -rn "current_version_id" pcs-frontend/src/types/ --include='*.ts' | grep -v 'api\.d\.ts'
  ```
  ⇒ 必须 **0 命中**（`api.d.ts` 是生成物，它**必然**有该字段 ⇒ 断言时必须排除它）。

- [ ] **Step 7：提交** `git commit -m "feat(P9A): DeliverableResponse 补 current_version_id（selectinload，禁 N+1）"`

---

## Task T1：记录 api 层（6 模块 list / get / patch）+ 归并 `editRecordApi`

**Files:**
- Create: `pcs-frontend/src/api/records.ts`
- Modify: `pcs-frontend/src/api/locks.ts`（**删** `editRecordApi` + `PatchBaseline` +
  `EDITABLE_RECORD_TYPES` / `EditableRecordType` 移出）、`src/api/audit.ts`
- Test: `pcs-frontend/tests/api/records_api.test.ts`（新）、
  `tests/api/edit_lock_api.test.ts`（**基线测试迁出** ⇒ 改 import）

**Interfaces:**
- Consumes: `components['schemas'][...]`
- Produces:
  ```ts
  // src/api/records.ts —— 记录域的**单一来源**
  export const EDITABLE_RECORD_TYPES = [
    'CostEstResult', 'FiltrationResult', 'OpenChannelResult',
    'cooling_tower_result', 'flare_system_result', 'psychro_result',
  ] as const;
  export type EditableRecordType = (typeof EDITABLE_RECORD_TYPES)[number];

  /** 并发基线（SPEC §6.21 P9A-LCK-006）。
   *  ⚠️ **字段名必须是 snake_case**（与后端请求体逐字一致）——
   *  中间层（`EditBaseline`）也用**同一套名字** ⇒ 展开即兼容，无需转换。
   *  ⚠️ 可选性（两个都可选）**类型层表达不了**「至少一档」⇒ 由**运行时**保证
   *  （`useEditBaseline` 的 `disabled === false` ⇒ 至少一档有值，见 T2）。 */
  export interface PatchBaseline {
    expected_hash?: string;          // ⚠️ 一档
    expected_updated_at?: string;    // ⚠️ 二档（原样透传，**不过 Date**）
  }

  export const RESULT_BASES: Record<EditableRecordType, string> = {
    CostEstResult: '/cost-est/results',
    FiltrationResult: '/filtration/results',
    OpenChannelResult: '/open-channel/results',
    cooling_tower_result: '/cool-tower/results',
    flare_system_result: '/flare/results',
    psychro_result: '/psychro/results',
  };

  export const recordsApi = {
    /** ⚠️ 返回类型只约束**信封的公共部分** `{items, total}` ——
     *  6 个模块的分页字段名**不同**（`limit/offset` vs `skip/limit`）
     *  ⇒ **不消费分页字段**，偏移自己算。 */
    list: <T>(base: string, params: { project_id: string; limit?: number; offset?: number }) =>
      api.get<{ items: T[]; total: number } & Record<string, unknown>>(
        base, { params },
      ).then((r) => r.data),
    get: <TRes>(base: string, id: string) =>
      api.get<TRes>(`${base}/${id}`).then((r) => r.data),
    /** ⚠️ 6 个模块**同构**（OpenAPI 实测：6 个 *UpdateRequest 都带基线字段）
     *  ⇒ 统一签名。基线字段由调用方按三档判定填入。 */
    patch: <TRes, TBody extends object>(
      base: string, id: string, body: TBody & PatchBaseline,
    ) => api.patch<TRes>(`${base}/${id}`, body).then((r) => r.data),
  };
  ```
  ⚠️ **基线字段名在中间层漂移 ⇒ TypeScript 不报错 ⇒ 运行时每次保存 409**
  （实测 2026-10-21：`{...changed, ...baseline}` 里的 `expectedHash` **编译通过**，
  但请求体没有 `expected_hash` ⇒ 后端 `expected_hash is None` ⇒ 409 `no_baseline`）
  ⇒ 这就是 **RF-13**，守卫见 T2/T3 的「穿过展开」的断言。

- [ ] **Step 1：写失败测试** `tests/api/records_api.test.ts`（MSW `setupServer`）

  ```ts
  it('PATCH 必须带 expected_hash —— 漏了后端一律 409，而症状是「保存总是失败」', async () => {
    await recordsApi.patch('/cost-est/results', 'r1', {
      expected_hash: 'a3f9c21d8b7e6f50', estimated_cost: 35,
    });
    expect((lastBody as { expected_hash: string }).expected_hash).toBe('a3f9c21d8b7e6f50');
  });

  it('基线的 expected_updated_at **原样透传**（不落 new Date()）—— 微秒被截成毫秒 ⇒ 每次假 409', async () => {
    const raw = '2026-10-20T10:22:31.123456+08:00';
    await recordsApi.patch('/cost-est/results', 'r1', { expected_updated_at: raw });
    expect((lastBody as { expected_updated_at: string }).expected_updated_at).toBe(raw);
    // ⚠️ 断言**逐字相等**（不是 toEqual(new Date(raw).toISOString())）
  });

  it('列表必须带 project_id（类型层必填 + URL 上可见）', async () => {
    await recordsApi.list('/cost-est/results', { project_id: 'p1' });
    expect(lastListUrl).toContain('project_id=p1');
  });

  it('PATCH 成功返回**更新后的记录**（含新的 record_hash）⇒ 基线靠它刷新（RF-1）', async () => {
    // mock 返回 record_hash='ffffffffffffffff'
    const res = await recordsApi.patch('/cost-est/results', 'r1', { expected_hash: 'a3f9c21d8b7e6f50' });
    expect((res as { record_hash: string }).record_hash).toBe('ffffffffffffffff');
  });
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**：`recordsApi` 不存在

- [ ] **Step 3：实现 `src/api/records.ts`**（上面 Interfaces 的代码）

- [ ] **Step 4：`src/api/locks.ts` 归并（DRY 裁决）**
  - **删** `editRecordApi` + `PatchBaseline`
  - **移出** `EDITABLE_RECORD_TYPES` + `EditableRecordTypeName` ⇒ 改名为
    `EditableRecordType`，移到 `records.ts`
  - `locks.ts` 改为 `import { EDITABLE_RECORD_TYPES, type EditableRecordType } from './records'`
    ⇒ 依赖方向 **locks → records**（单向，**无循环**）
  - 头注释改为「编辑锁操作客户端（acquire / renew / release）」+ 指向 `records.ts`

- [ ] **Step 5：`src/api/audit.ts` 加编辑审计查询**
  ```ts
  /** 编辑审计（SPEC §6.21 P9A-LCK-006「查看差异」的来源）。
   *  ⚠️ `/audit-logs` **限 SYSTEM_ADMIN** ⇒ 非管理员 403 ⇒ T2 的弹窗必须优雅降级。 */
  export function listRecordEdits(params: { resource_type: string; resource_id: string; limit?: number }) {
    return api.get<AuditLogListResponse>('/audit-logs', { params }).then((r) => r.data);
  }
  ```

- [ ] **Step 6：迁移测试**
  - `tests/api/edit_lock_api.test.ts` 里那两处 `editRecordApi.patchCostEst`
    （:116 / :127）测的是「**PATCH 必须带 expected_hash**」⇒ **基线逻辑**，
    **不是锁** ⇒ **移到 `tests/api/records_api.test.ts`**
  - 锁测试只留 acquire / renew / release 的用例

- [ ] **Step 7：跑测试确认通过** ⇒ **PASS**（≥4 例）+ `tests/api/edit_lock_api.test.ts` 仍绿

- [ ] **Step 8：提交** `git commit -m "refactor(P9B): PATCH 统一到 recordsApi —— 删 editRecordApi，词表与基线类型归记录域"`

---

## Task T2：基线 hook + 编辑锁 hook + 锁指示器 + 409 弹窗

**Files:**
- Create: `src/hooks/useEditBaseline.ts`、`src/hooks/useEditLock.ts`、
  `src/components/common/EditLockIndicator.tsx`、`src/components/common/EditConflictModal.tsx`
- Test: `tests/hooks/useEditBaseline.test.ts`、`tests/hooks/useEditLock.test.tsx`、
  `tests/components/common/EditLockIndicator.test.tsx`、
  `tests/components/common/EditConflictModal.test.tsx`

**Interfaces:**
- Consumes: `recordsApi` + `EditableRecordType`（T1）、`editLockApi`（`src/api/locks.ts`）、
  `extractConflict` / `conflictKind`（`src/api/errors.ts`）、`listRecordEdits`（T1）
- Produces:
  ```ts
  // src/hooks/useEditBaseline.ts —— **三档基线判定的唯一实现**
  export type EditBaselineReason =
    | 'ok'                 // 有可用基线
    | 'no-permission'      // 当前状态不可编辑（sign_status 锁定态）
    | 'no-baseline';       // 两档皆无 ⇒ 无法安全编辑

  /** ⚠️ **继承 `PatchBaseline` ⇒ 字段名逐字相同（snake_case）** ——
   *  展开即类型兼容，不需要转换函数。
   *  ⚠️ 若这里改用 camelCase（`expectedHash`），**TypeScript 不会报错**
   *  （实测 2026-10-21 编译通过）⇒ 请求体缺 `expected_hash`
   *  ⇒ **每次保存 409 no_baseline** ⇒ 见 RF-13。 */
  export interface EditBaseline extends PatchBaseline {
    disabled: boolean;
    reason: EditBaselineReason;
  }

  /** 可编辑的签署态 —— **本批 `canEdit` 的唯一判据**（见补充 1）。
   *  ⚠️ 后端只允许 `DRAFT` / `CHANGE_PENDING` 可 PATCH（`*_PERSIST_SIGN_STATUS_LOCKED`）。 */
  export const EDITABLE_SIGN_STATUSES = ['DRAFT', 'CHANGE_PENDING'] as const;
  export function isEditableSignStatus(signStatus: string): boolean {
    return (EDITABLE_SIGN_STATUSES as readonly string[]).includes(signStatus);
  }

  export function useEditBaseline(record: {
    record_hash?: string | null;
    updated_at?: string | null;
    /** ⚠️ **必填** = `isEditableSignStatus(record.sign_status)`。
     *  忘了传 = **编译错误**（不是运行时默认 true ⇒ 漏判 sign_status）。 */
    canEdit: boolean;
  }): EditBaseline;

  // src/hooks/useEditLock.ts
  export type EditLockState =
    | { status: 'idle' }
    | { status: 'held'; ttlSeconds: number }
    | { status: 'blocked'; holder: LockHolderResponse }
    | { status: 'expired' }
    | { status: 'degraded'; message: string | null };

  export function useEditLock(args: {
    recordType: EditableRecordType;
    recordId: string;
    enabled: boolean;
    onDegraded?: (message: string | null) => void;
  }): {
    state: EditLockState;
    readOnly: boolean;
    release: () => Promise<void>;
  };
  ```

- [ ] **Step 1：写失败测试 —— `useEditBaseline`（三档）**

  ```ts
  it('hash 非空 ⇒ expected_hash', () => {
    const b = useEditBaseline({ record_hash: 'a3f9c21d8b7e6f50', canEdit: true });
    expect(b.expected_hash).toBe('a3f9c21d8b7e6f50');
    expect(b.disabled).toBe(false);
  });

  it('hash 空 + 有 updated_at ⇒ 退到第二档（expected_updated_at）', () => {
    const raw = '2026-10-20T10:22:31.123456+08:00';
    const b = useEditBaseline({ record_hash: '', updated_at: raw, canEdit: true });
    expect(b.expected_updated_at).toBe(raw);   // ⚠️ 逐字（RF-9）
    expect(b.expected_hash).toBeUndefined();
    expect(b.disabled).toBe(false);
  });

  it('两档皆无 ⇒ disabled + reason=no-baseline（**不是** no-permission）', () => {
    const b = useEditBaseline({ record_hash: '', updated_at: null, canEdit: true });
    expect(b.disabled).toBe(true);
    expect(b.reason).toBe('no-baseline');
  });

  it('canEdit=false ⇒ disabled + reason=no-permission（与 no-baseline **可区分**）', () => {
    const b = useEditBaseline({ record_hash: 'a3f9c21d8b7e6f50', canEdit: false });
    expect(b.reason).toBe('no-permission');
  });

  it('**disabled=false ⇒ 至少一档基线存在**（运行时保证，类型层表达不了）', () => {
    const b = useEditBaseline({ record_hash: 'a3f9c21d8b7e6f50', canEdit: true });
    expect(b.disabled).toBe(false);
    expect(b.expected_hash || b.expected_updated_at).toBeTruthy();
  });

  it('**RF-13：基线字段名穿过展开后仍是 expected_hash**（TS 不拦 ⇒ 必测）', async () => {
    // ⚠️ 这条是 P1 的守卫：`{...changed, ...baseline}` 里的字段名若漂成
    // `expectedHash`，**TypeScript 编译通过**（实测 2026-10-21）⇒
    // 请求体缺 `expected_hash` ⇒ **每次保存 409 no_baseline**。
    // ⇒ 断言**请求体**（不是 hook 的返回值）。
    const b = useEditBaseline({ record_hash: 'a3f9c21d8b7e6f50', canEdit: true });
    await recordsApi.patch('/cost-est/results', 'r1', { ...{ estimated_cost: 35 }, ...b });
    expect((lastBody as Record<string, unknown>).expected_hash).toBe('a3f9c21d8b7e6f50');
    expect((lastBody as Record<string, unknown>).expectedHash).toBeUndefined();
  });
  ```

  ⚠️ **`canEdit` 的来源（本批唯一的判据）**：
  `canEdit = isEditableSignStatus(record.sign_status)`
  （`DRAFT` / `CHANGE_PENDING` 可编辑，其余 7 态不可编辑）。
  - ⚠️ **不检查项目权限** —— 后端 `check_project_access_or_404` 已做，
    前端重复检查会与后端口径不一致。
  - ⚠️ **不检查签署职责** —— ADR-0050 的范围，本批不做。
  - ⚠️ **`canEdit` 是必填参数**（不是可选 + 默认值）⇒ 调用方忘了传
    `isEditableSignStatus(...)` 就是**编译错误**，而不是运行时默默放行
    （可选 + 默认 `true` ⇒ 漏判 sign_status ⇒ RF-7 静默失效）。

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**

- [ ] **Step 3：实现 `useEditBaseline`**

  ```ts
  export function useEditBaseline({ record_hash, updated_at, canEdit }: Args): EditBaseline {
    if (!canEdit) return { disabled: true, reason: 'no-permission' };
    const hash = (record_hash ?? '').trim();
    if (hash) return { disabled: false, reason: 'ok', expected_hash: hash };
    const ts = updated_at ?? null;
    if (ts) return { disabled: false, reason: 'ok', expected_updated_at: ts };   // ⚠️ 原样
    return { disabled: true, reason: 'no-baseline' };
  }
  ```
  ⚠️ **判定在打开抽屉时完成**（调用方在抽屉打开时算一次并缓存）；
  **保存路径只透传，不再判断** ⇒ 用户填完一堆数据才被告知不能保存是最糟 UX。

- [ ] **Step 4：写失败测试 —— `useEditLock`（fake timers）**

  ```ts
  it('取锁成功后每 60s 续期一次', ...);
  it('续期 409 ⇒ 转只读，且**不重试**（RF-4）', async () => {
    vi.spyOn(editLockApi, 'renew').mockResolvedValue(LOCK_409);
    ... expect(editLockApi.renew).toHaveBeenCalledTimes(1);   // ← 没有第二次
  });
  it('取锁 409（他人持锁）⇒ blocked + readOnly，holder 取后端原文（RF-3）', ...);
  it('degraded=true ⇒ **可编辑**（体验层失效，不是保护层）（RF-6）', ...);
  it('acquire 网络失败 ⇒ degraded（不崩、不阻塞编辑）', ...);      // ← GAP
  it('enabled=false ⇒ **不取锁**（不请求 acquire）', ...);          // ← GAP
  ```

- [ ] **Step 5：实现 `useEditLock`**

  ```ts
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    void editLockApi.acquire(recordType, recordId).then((res) => {
      if (cancelled) return;
      if (res.degraded) { setState({ status: 'degraded', message: res.message ?? null }); onDegraded?.(res.message ?? null); return; }
      if (!res.success && res.holder) { setState({ status: 'blocked', holder: res.holder }); return; }
      setState({ status: 'held', ttlSeconds: res.ttl_seconds });
    }).catch(() => { if (!cancelled) setState({ status: 'degraded', message: null }); });

    const timer = setInterval(() => {
      void editLockApi.renew(recordType, recordId).then((res) => {
        if (cancelled) return;
        if (!res.success) { setState({ status: 'expired' }); return; }   // ⚠️ 不重试
        if (res.degraded) { setState({ status: 'degraded', message: res.message ?? null }); onDegraded?.(res.message ?? null); }
      }).catch(() => { if (!cancelled) setState({ status: 'expired' }); });
    }, 60_000);                                                   // ⚠️ 60s
    return () => { cancelled = true; clearInterval(timer); };
  }, [recordType, recordId, enabled]);
  ```
  ⚠️ **不自动 release**（30min TTL 回收；页面关闭不要求显式释放，SPEC §6.21
  P9A-LCK-002）⇒ **但** T3 的抽屉关闭路径**显式**调 release（RF-10）。
  `release` 实现：**所有错误一律忽略**（409 / 403 / 404 / 500 / 网络），
  **不弹窗、不阻断关闭流程**。

- [ ] **Step 6：实现 `EditLockIndicator`**
  - `blocked` ⇒ **「{holder.username || holder.user_id} 正在编辑（{相对时间}）」**
    ⚠️ **禁用原因写「谁在改」，不写「无权限」**（RF-3）；holder 取后端原文，不猜不缓存。
  - `expired` ⇒ 「编辑锁已失效，请重新进入编辑」
  - `held` / `degraded` ⇒ 不渲染（降级横幅在顶栏，T4）

- [ ] **Step 7：实现 `EditConflictModal`（按 `basis` 分流）**

  | basis | 文案 | 出口 |
  |---|---|---|
  | `record_hash` | 「{changed_by} 于 {changed_at} 修改了这条记录」 | [查看差异] / [放弃我的修改并刷新] |
  | `updated_at` | 同上（只知道行被改过） | 同上 |
  | `no_baseline` | 「**该记录缺少并发校验基线，无法安全保存**」⚠️ **不得**说「已被他人修改」 | [刷新后重试] / [联系管理员] |
  | `unknown`（`conflictKind` 兜底） | 「说不清是否冲突」 | [刷新后重试] |

  ⚠️ **RF-5**：`changed_by` / `changed_at` 为 null ⇒ 显示「未知」，**不得**用 `updated_at` 冒充。
  ⚠️ **不得自动重试**（不轮询、不重发）。
  ⚠️ [查看差异] ⇒ 调 `listRecordEdits`；**403 时**（非 SYSTEM_ADMIN）显示
  「无权查看差异（需系统管理员）」并**保留** [放弃我的修改并刷新] 出口（**TODO-066**）。
  ⚠️ 后端对「两档皆无」**仍返 409 `no_baseline`** ⇒ 前端禁用只是 UX 优化，
  **不得**据此放宽后端。

- [ ] **Step 8：跑测试确认通过** ⇒ **PASS**（基线 4 + 锁 6 + 指示器 3 + 弹窗 5）

- [ ] **Step 9：提交** `git commit -m "feat(P9B): 三档基线 hook + 编辑锁 hook + 锁指示器 + 409 弹窗"`

---

## Task T3：通用结果页 + 6 个模块描述符 + 6 条路由 + 编辑抽屉

**Files:**
- Create: `src/pages/results/resultModules.ts`、`ResultListPage.tsx`、`ResultEditDrawer.tsx`
- Modify: `src/App.tsx`、`src/layouts/MainLayout.tsx`、`src/mocks/handlers.ts`
- Test: `tests/pages/results/result_page.test.tsx`、`tests/mocks/handlers.test.ts`

**Interfaces:**
- Consumes: `recordsApi` / `RESULT_BASES`（T1）、`useEditBaseline` / `useEditLock` /
  `EditLockIndicator` / `EditConflictModal`（T2）
- Produces:
  ```ts
  // src/pages/results/resultModules.ts
  export interface CommonResultRow {
    project_id: string; workspace_id: string; tag_number: string | null;
    sign_status: string; record_hash: string; created_at: string;
    updated_at?: string | null;
  }
  export interface ResultFieldDef { key: string; label: string; unit?: string; precision?: number; }
  export interface ResultModuleDef<TRes extends CommonResultRow> {
    recordType: EditableRecordType;
    base: string;                        // = RESULT_BASES[recordType]
    pk: 'id' | 'result_id';              // ⚠️ 各不相同（实测）
    route: string; title: string;
    columns: ResultFieldDef[];
    /** ⚠️ **只放标量业务字段**：`*_json` 与后端计算字段（`pass`）**不进表单**。 */
    editableFields: readonly (keyof TRes & string)[];
  }
  export const RESULT_MODULES: readonly ResultModule[];   // 6 个
  export type ResultModule = (typeof RESULT_MODULES)[number];
  ```

- [ ] **Step 1：写失败测试** `tests/pages/results/result_page.test.tsx`

  ```ts
  it('列表渲染：位号 + record_hash + 状态徽章', ...);

  it('打开编辑 ⇒ 请求体带 expected_hash（取自记录的 record_hash）', async () => {
    ... expect(lastPostedBody.expected_hash).toBe('a3f9c21d8b7e6f50');   // RF-2
  });

  it('保存成功 ⇒ 基线刷新为**响应里的新 record_hash**（RF-1）', async () => {
    ... fireEvent.click(save); await waitFor(...);
    fireEvent.click(save);                       // 再存一次
    await waitFor(() => expect(lastPostedBody.expected_hash).toBe('ffffffffffffffff'));
  });

  it('409 ⇒ 弹窗按 basis 分流（三种 basis 三套文案 + 出口）', async () => {
    // record_hash / updated_at ⇒ 「修改了这条记录」；no_baseline ⇒ 「缺少并发校验基线」
  });

  it('no_baseline 的 409 **不得**显示「已被他人修改」（两者原因不同）', ...);

  it('sign_status=CHECKED ⇒ 编辑按钮禁用（RF-7）', ...);

  it('他人持锁 ⇒ 只禁用保存，浏览 / 复制 / 查看哈希仍可用（RF-3）', ...);

  it('两档皆无 ⇒ 编辑按钮禁用 + Tooltip 说「联系管理员」；状态锁定 ⇒ 说「当前状态 X 不可编辑」（两类原因**可区分**，RF-12）', ...);

  it('抽屉关闭 ⇒ 调 release（RF-10）', async () => {
    ... fireEvent.click(closeBtn); await waitFor(() => expect(releaseCalled).toBe(true));
  });

  it('**有未保存修改**时关闭 ⇒ 弹确认；取消 ⇒ 抽屉保持打开', async () => { ... });

  it('release 失败 ⇒ **不弹窗**、不阻断关闭（best-effort）', async () => { ... });

  it('页面卸载 ⇒ 用 navigator.sendBeacon 发 release（不是普通 fetch）', async () => {
    // 触发 pagehide ⇒ 断言 sendBeacon 被调用
  });
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**

- [ ] **Step 3：实现 `resultModules.ts`** —— 6 个模块的 `editableFields`
  （**逐字取自各模块 `*UpdateRequest` 的标量字段**，排除 `expected_hash` /
  `expected_updated_at` / `*_json` / 计算字段 `pass`）：

  | 模块 | `pk` | `editableFields` |
  |---|---|---|
  | CostEstResult | `result_id` | `estimated_cost` `currency` `cost_index_year` `base_cost` `base_year` `cepci_index_base` `cepci_index_target` `correlation_source` `scaling_exponent` |
  | FiltrationResult | `result_id` | `filter_type` `media_type` `area` `cycle_time` `pressure_drop` `cake_resistance_alpha` `specific_resistance_r0` `permeability_k` `porosity_eps` `filter_velocity` |
  | FlareSystemResult | `id` | `calc_type` `total_relief_load_kg_h` `header_diameter_mm` `header_mach` `header_pressure_drop_kpa` `kod_diameter_mm` `water_seal_height_mm` `stack_height_m` `stack_diameter_m` `radiation_at_grade_kw_m2` `radiation_limit_kw_m2` `flare_tip_diameter_mm` `steam_for_smokeless_kg_h` |
  | OpenChannelResult | `result_id` | `channel_type` `flow_rate` `depth` `velocity` `slope` `critical_depth` `froude_number` `manning_n` `hydraulic_radius` `jump_type` `conjugate_depth` `energy_loss` |
  | PsychroResult | `id` | `humidity_ratio_kg_kg` `dew_point_c` `wet_bulb_c` `enthalpy_kj_kg` `specific_volume_m3_kg` `sensible_heat_kw` `latent_heat_kw` `saturation_w_kg_kg` `saturation_w_mg_sm3` `saturation_w_lb_per_mmscf` `saturation_T_c` |
  | CoolingTowerResult | `id` | `tower_type` `duty_kw` `water_flow_m3h` `makeup_water_m3h` `fan_power_kw` `merkel_integral` |

  ⚠️ **每个模块单独一个 const、各带自己的响应类型** ⇒ `editableFields` 里
  拼错字段 = **编译期错误**。
  ⚠️ `columns` / `editableFields` **只在这里写一次**；页面不硬编码字段。

- [ ] **Step 4：实现 `ResultListPage.tsx`（描述符驱动）**
  - `recordsApi.list(base, { project_id: PROJECT_ID, limit, offset })`
    （`PROJECT_ID` 取 `src/constants/env.ts`）
  - antd `Table`：`columns` 由描述符生成；`record_hash` 列用 `HashBadge`；
    `sign_status` 列用 `StateBadge`；数值列用 `NumericCell`
  - 分页：antd Table 的 `pagination` ⇒ 走 `limit`/`offset`（后端已支持，
    ⚠️ **两种信封的偏移字段名不同** ⇒ 只用 `items` + `total`，偏移自己算）
  - **每行的 [编辑] 按钮**（RF-7，补充 3）：
    ```tsx
    const editable = isEditableSignStatus(row.sign_status);   // ⚠️ 唯一判据
    <Button disabled={!editable} title={editable ? undefined : `当前状态 ${row.sign_status} 不可编辑`}>
      编辑
    </Button>
    ```
    ⚠️ **在渲染按钮时就禁用**，**不是**打开抽屉后才检查 ⇒ 点禁用按钮
    不该有任何反应（否则用户已经进了编辑态才发现不能改）。
  - **`onSaved` 的处理**（RF-1，补充 2）：
    ```tsx
    const onSaved = (updated: { record_hash: string }) => {
      setRecords((prev) => prev.map((r) =>
        String(r[module.pk]) === String(id) ? { ...r, record_hash: updated.record_hash } : r,
      ));
    };
    ```
    ⚠️ **就地更新本地 state**，**不得重新拉整个列表**（那是浪费请求，
    也会让滚动位置与分页跳变）。
    ⚠️ 不更新 ⇒ 第二次保存仍带旧 hash ⇒ **必 409**（RF-1 静默失效）。

- [ ] **Step 5：实现 `ResultEditDrawer.tsx`**
  ```tsx
  interface Props {
    open: boolean;
    module: ResultModule;
    record: CommonResultRow & Record<string, unknown>;
    onClose: () => void;
    onSaved: (updated: { record_hash: string }) => void;   // ⚠️ 父级用它刷新基线
  }
  ```
  流程：
  1. **打开时**：`const baseline = useEditBaseline({
       record_hash, updated_at,
       canEdit: isEditableSignStatus(record.sign_status),   // ⚠️ 唯一判据（补充 1）
     })` ⇒ 三档判定在此完成（RF-8）
  2. `const lock = useEditLock({ recordType, recordId, enabled: open, onDegraded })`
  3. 顶部 `<EditLockIndicator state={lock.state} />`
  4. `baseline.disabled` ⇒ **禁用保存** + Tooltip：
     - `no-permission` ⇒ 「当前状态 {sign_status} 不可编辑」
       （⚠️ 这是**状态**门禁，不是权限门禁；别写成「无权限」）
     - `no-baseline` ⇒ 「该记录缺少并发校验基线，无法安全编辑，请联系管理员」
     （**两类原因文案可区分**，RF-12）
  5. 表单：字段由 `module.editableFields` 渲染
  6. 保存：**显式**构造请求体（**不要**直接展开整个 `baseline`）：
     ```ts
     const body = {
       ...changed,
       expected_hash: baseline.expected_hash,
       expected_updated_at: baseline.expected_updated_at,   // ⚠️ undefined 会被 JSON.stringify 省略
     };
     await recordsApi.patch(base, id, body);
     ```
     ⇒ ⚠️ **只带判定出来的那一档**，**原样透传**（RF-9）
     ⇒ ⚠️ **不要**用 `{...changed, ...baseline}` 展开整个对象：会把
     `disabled` / `reason` 也塞进请求体（后端 `extra="ignore"` 会静默丢弃，
     但那依赖后端策略；显式构造是**不依赖**策略的做法）。
     ⇒ ⚠️ **RF-13**：字段名必须是 `expected_hash`（snake_case）。
     **TypeScript 不拦这个**（实测 2026-10-21 编译通过）⇒ 靠 T2/T3 的
     「断言请求体」的测试兜底。
  7. 成功 ⇒ `onSaved({ record_hash: res.record_hash })`（**RF-1**）+ `message.success`
  8. 409 ⇒ `extractConflict(err)` ⇒ 打开 `EditConflictModal`（⚠️ **不自动重试**）
  9. `lock.readOnly` ⇒ 禁用「保存」（**只禁保存**，不禁浏览）
  10. **关闭时**（RF-10）：
      - 有未保存修改 ⇒ 弹确认「你有未保存的修改，确认关闭将放弃修改并释放编辑锁」
        ⇒ 取消 ⇒ **保持抽屉打开**
      - ⇒ `await lock.release()`（**best-effort**：所有错误忽略，不弹窗）
      - 页面卸载路径 ⇒
        ```ts
        navigator.sendBeacon(
          `/api/v1/locks/${recordType}/${recordId}/release`,
          new Blob([JSON.stringify({ user_id: currentUserId })], { type: 'application/json' }),
        );
        ```
        ⚠️ body 用 **Blob + `application/json`**（不用普通 fetch —— `beforeunload`
        里的 fetch 可能被浏览器取消）；⚠️ **不得**在 `beforeunload` 里用普通 fetch。

- [ ] **Step 6：接 6 条路由 + 菜单**
  ```tsx
  { path: 'results/cool-tower', element: <ResultListRoute module="cooling_tower_result" /> },
  { path: 'results/filtration', element: <ResultListRoute module="FiltrationResult" /> },
  { path: 'results/flare', element: <ResultListRoute module="flare_system_result" /> },
  { path: 'results/open-channel', element: <ResultListRoute module="OpenChannelResult" /> },
  { path: 'results/psychro', element: <ResultListRoute module="psychro_result" /> },
  { path: 'results/cost-est', element: <ResultListRoute module="CostEstResult" /> },
  ```
  菜单加一组「结果记录」（6 项）。

- [ ] **Step 7：mock（契约形状 + 生成类型标注）**
  `src/mocks/handlers.ts` 加 6 个 `GET /{base}` + 6 个 `PATCH /{base}/:id`
  （PATCH 回**新的** `record_hash`）。⚠️ 响应体用
  `satisfies components['schemas'][...]` 标注（**不得手写自由 dict**）。
  ⚠️ `tests/mocks/handlers.test.ts` 的**棘轮清单**（`devOnly ∩ 契约`）必须同步更新
  —— 新增即红是**预期**（照着红更新清单 + 加 ajv 校验）。

- [ ] **Step 8：跑测试确认通过** ⇒ **PASS**（≥12 例）+ `tests/mocks/handlers.test.ts` 绿

- [ ] **Step 9：提交** `git commit -m "feat(P9B): 通用结果页 + 类型化模块描述符 + 编辑抽屉（三档基线 / release 时机）"`

---

## Task T4：降级横幅 + ChangeImpactPanel 的「确认」动作

**Files:**
- Create: `src/store/degradation.ts`
- Modify: `src/layouts/MainLayout.tsx`、`src/components/common/ChangeImpactPanel.tsx`、
  `src/pages/sim/StreamDetailPage.tsx`
- Test: `tests/components/common/ChangeImpactPanel.test.tsx`、`tests/layouts/MainLayout.test.tsx`

**Interfaces:**
- Consumes: `changeImpactApi.confirm` / `.manualAdjust`、`useEditLock` 的 `onDegraded`（T2）
- Produces:
  ```ts
  // src/store/degradation.ts（zustand）
  export const useDegradation = create<{
    message: string | null;
    setMessage: (m: string | null) => void;
  }>(() => ({ message: null, setMessage: () => {} }));
  ```
  ```ts
  // ChangeImpactPanel 新增 props（**旧的 onConfirmRecalc 保留不动**）
  interface Props {
    changeSource: ChangeSource; affectedRecords: AffectedRecord[];
    onConfirmRecalc?: (recordIds: string[]) => void;   // ⚠️ 指向**另一个端点** confirm-recalc
    onConfirmSystem?: (recordType: string, recordId: string) => Promise<void>;
    onManualAdjust?: (recordType: string, recordId: string,
                      decision: 'NO_CHANGE' | 'CHANGED', reason: string) => Promise<void>;
  }
  ```

- [ ] **Step 1：写失败测试**

  ```ts
  it('degraded ⇒ 顶栏出现橙色横幅，且**不阻断**编辑（RF-6）', ...);
  it('横幅文案取后端 message 原文（前端不拼接）', ...);
  it('系统判定：按钮文案随响应 decision 分流（NO_CHANGE ⇒「确认：结果未变」；CHANGED ⇒「确认：结果已变」+ 须重新签署）', ...);
  it('人工判定：reason 为空 ⇒ **不发请求**（后端 422）', ...);
  it('人工判定与系统判定是**两个**端点，不合并', ...);
  it('**record_type 用注册表键** ⇒ 未知键显示默认图标 + **原始键文本**（不崩、不空白、不是「默认分类」）', ...);
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**

- [ ] **Step 3：实现降级横幅**
  - `src/store/degradation.ts`（zustand，全局）
  - `useEditLock` 的 `onDegraded` ⇒ `setMessage(res.message)`
  - `MainLayout` 顶部：`<Alert type="warning" data-testid="degradation-banner" message={degradation.message} />`
    ⚠️ 文案**原样渲染**后端 `message`；⚠️ **不阻断**任何操作；
    ⚠️ `message` 为 null ⇒ 不渲染横幅（**不是**渲染一句自造全局提示）

- [ ] **Step 4：`ChangeImpactPanel` —— `record_type` 改注册表键（RF-11）**

  ⚠️ **完整改动清单（已 grep 核实，2026-10-21）**：

  | 处 | 文件:行 | 改什么 | 性质 |
  |---|---|---|---|
  | 1 | `ChangeImpactPanel.tsx:31` | `record_type: string` ⇒ `record_type: EditableRecordType \| string`（**数据层只放注册表键**） | 机械 |
  | 2 | `ChangeImpactPanel.tsx:47-50` | `TYPE_COLOR`（PIPE/PUMP/UTIL/SIM 四个键，**值全是同一个颜色**）⇒ 换成「**注册表键 → UI 表示**」映射表 | 新增 |
  | 3 | `ChangeImpactPanel.tsx:151` | `TYPE_COLOR[r.record_type] ?? 默认色` ⇒ 新映射 + fallback | 机械 |
  | 4 | `ChangeImpactPanel.tsx:156` | `data-record-type={r.record_type}` ⇒ 透传不变（已是键） | 无 |
  | 5 | `ChangeImpactPanel.tsx:172` | `● {r.record_type}` ⇒ 显示名（`PipingResult` ⇒ 「管道」） | 机械 |
  | 6 | `src/mocks/seed/streams.ts:169-171` | 3 条 seed 的 `'PIPE'` / `'PUMP'` ⇒ `'PipingResult'` / `'PumpResult'` | 机械 |
  | 7 | `tests/components/common/ChangeImpactPanel.test.tsx:25-27, 62` | 3 个 fixture + 1 条断言 ⇒ 改注册表键 | 机械 |

  ⚠️ **映射表的语义（RF-11）**：
  - **只包含本批涉及的 6 个注册表键**（`CostEstResult` / `FiltrationResult` /
    `OpenChannelResult` / `cooling_tower_result` / `flare_system_result` /
    `psychro_result`）—— 其余 15 个注册表键**走 fallback**。
    理由：本批只做这 6 个结果页；其余键的 UI 表示在**它们自己的批次**做
    （一次填 21 个 = 本批不需要的工作量，且那 15 个键的显示名没人核对过）。
  - key = **注册表键**（`PipingResult` / `PumpResult` / …）
  - value = **UI 表示**（图标 / 颜色 / 显示名）—— **value 不得是分类词**
    （⛔ `{ PipingResult: 'PIPE' }` 就是**第 8 套词表**，与 TODO-060 的方向相反）
  - **fallback（必须）**：键不在表里 ⇒ **默认图标 + 原始注册表键文本**，
    **不报错、不空白、不回退到某个「默认分类」**
    （后端注册表新增类型时，前端映射表不可能实时同步 ⇒ 失败模式应是
    「显示不完美」，不是「面板崩溃」）
  - ⚠️ **组件内**没有 `record_type === 'PIPE'` 这类业务逻辑判断（已 grep 核实：
    只有颜色查表 / 属性透传 / 显示文本）⇒ **全是机械替换**，没有逻辑改写。
  - ⚠️ `TYPE_COLOR` 现有四个键**值同色** ⇒ 它本来就不做分类 ⇒ 新映射的
    **颜色统一**（SPEC §6.7：「spec 灰色统一，仅左边框与图标传达警告」），
    **区分靠图标 + 显示名**。

- [ ] **Step 5：扩展 `ChangeImpactPanel` 的两个新动作**
  - [确认重算] / [批量确认重算] ⇒ 指向 `confirm-recalc`（**另一个端点**，不动）
  - [系统判定] ⇒ `POST /change-impact/{rt}/{id}/confirm`
    ⇒ 响应 `decision` 决定文案：
    `NO_CHANGE` ⇒「确认：结果未变（免凭证）」；`CHANGED` ⇒「确认：结果已变（须重新签署）」
  - [人工判定] ⇒ `POST /change-impact/{rt}/{id}/manual-adjust`
    ⇒ body `{decision, reason}`；⚠️ **`reason` 必填**（空 ⇒ 422）⇒ 前端先校验
  - ⚠️ **不得自动重试**（会无限循环覆盖）

- [ ] **Step 6：跑测试确认通过** ⇒ **PASS**

- [ ] **Step 7：提交** `git commit -m "feat(P9B): 锁降级横幅 + ChangeImpactPanel 的注册表键归一与两个判定动作"`

---

## Task T5：观测进度 / 待办 / 实时状态面板（§6.22~§6.24）

**Files:**
- Create: `src/components/common/WorkflowProgressPanel.tsx`、`TodoPanel.tsx`、
  `RealtimeStatusBanner.tsx`
- Modify: `src/components/common/NotificationCenter.tsx`（待办 tab 换成 `TodoPanel`）
- Test: `tests/components/common/{WorkflowProgressPanel,TodoPanel,RealtimeStatusBanner}.test.tsx`

**Interfaces:**
- Consumes: `GET /workflow-progress/{workflow_type}/{workflow_id}`、
  `GET /todos`（`src/api/todos.ts` 已有）、`GET /health` 的 `realtime` / `realtime_reason`
- Produces:
  ```ts
  // src/components/common/WorkflowProgressPanel.tsx
  /** 工作流类型 tab —— **可配置**，不写死「只 SIGN」。 */
  export interface WorkflowTab { type: WorkflowType; label: string; enabled: boolean; }
  /** ⚠️ type 必须是**后端枚举三值**：`SIGN` / `CHANGE_NOTICE` / `CUSTOMER_APPROVAL_PROXY`
   *  （⚠️ **没有 `DOC_PROXY`** —— 「代录」的后端键是 `CUSTOMER_APPROVAL_PROXY`） */
  export const WORKFLOW_TABS: readonly WorkflowTab[] = [
    { type: 'SIGN', label: '签署', enabled: true },
    { type: 'CHANGE_NOTICE', label: '变更单', enabled: false },          // P9B-2
    { type: 'CUSTOMER_APPROVAL_PROXY', label: '代录', enabled: false },  // P9B-2
  ];
  interface Props { workflowType: WorkflowType; workflowId: string; }

  // TodoPanel
  interface Props { items: TodoItem[]; compact?: boolean; onOpen?: (t: TodoItem) => void; }
  // RealtimeStatusBanner
  interface Props { realtime: 'ok' | 'degraded'; reason: string | null; }
  ```

- [ ] **Step 1：写失败测试**

  ```ts
  it('五态分色，PENDING 与 SKIPPED **不合并**', ...);
  it('不显示百分比（total 是节点数不是工作量）', ...);        // 断言 DOM 里没有 '%'
  it('items 为空 ⇒ 空态「该工作流暂无步骤记录」，不是「0 步已完成」', ...);
  it('CHANGE_NOTICE 面板为空 ⇒ 不显示成「流程异常」', ...);
  it('TodoPanel：空态不得断言「你没有待办」', ...);           // 可能是「无签署职责」
  it('RealtimeStatusBanner：degraded ⇒ 文案含「仍可收到通知」且**不阻断**', ...);
  it('WORKFLOW_TABS 只渲染 enabled 的 tab（本批只有 SIGN）', ...);
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**

- [ ] **Step 3：实现三个组件**（逐条对着 SPEC §6.22 / §6.23 / §6.24）
  - `WorkflowProgressPanel`：拉 `GET /workflow-progress/{type}/{id}`；顶部五计数；
    节点条按 `step_order` 升序；五态配色（PENDING 灰 / IN_PROGRESS 蓝脉冲 /
    COMPLETED 绿 / SKIPPED 灰虚线 / FAILED 红）；`result_hash` 用 `HashBadge`
  - `TodoPanel`：列（交付物 / 版本 / 步骤 / 签署职责 / 标题 / 操作）；
    `compact` 时只渲染标题 + 职责（抽屉用）
  - `RealtimeStatusBanner`：读 `/health` 的 `realtime` / `realtime_reason`；
    ⚠️ `realtime` **不得**用于 liveness/readiness；⚠️ 降级文案说「及时性降级，
    通知**仍可达**」；⚠️ `realtime_reason` 走**枚举**映射，不自造

- [ ] **Step 4：`NotificationCenter` 的待办 tab 换成 `TodoPanel`**
  （SPEC §6.20 的分组来源：待办 ← `GET /todos`，**不是**通知）

- [ ] **Step 5：跑测试确认通过** ⇒ **PASS**

- [ ] **Step 6：提交** `git commit -m "feat(P9B): 观测进度 / 待办 / 实时状态面板（SPEC §6.22~§6.24）"`

---

## Task T6：宿主页 —— 交付物进度页（只 SIGN）

**Files:**
- Create: `src/pages/deliverables/DeliverableProgressPage.tsx`
- Modify: `src/App.tsx`、`src/layouts/MainLayout.tsx`、`src/mocks/handlers.ts`
- Test: `tests/pages/deliverables/deliverable_progress.test.tsx`

**Interfaces:**
- Consumes: `GET /deliverables?project_id=`（**已带项目守卫 + limit/offset**）、
  `GET /deliverables/{id}/versions`、`DeliverableResponse.current_version_id`（T0）、
  `WorkflowProgressPanel`（T5）
- Produces: 路由 `/deliverables/progress`

- [ ] **Step 1：写失败测试**

  ```ts
  it('列表渲染：doc_no + title + sign_status', ...);
  it('行**展开**才拉 progress（列表加载时**不**预取 ⇒ 无 N+1）', async () => {
    ... 断言列表加载后 versions/progress 请求次数为 0；展开后为 1
  });
  it('SIGN 的 workflow_id 用 current_version_id（**不**用 rev 匹配）', ...);
  it('空状态区分三种', async () => {
    // ① 无版本 ⇒ 「该交付物尚未签发，无签署进度」
    // ② 有版本但无 progress 行 ⇒ 「签署流程尚未开始」
    // ③ 无权限 ⇒ 「你无权查看此交付物的进度」
  });
  it('只有 SIGN tab 被渲染（DOC_PROXY/CHANGE_NOTICE disabled ⇒ P9B-2 开）', ...);
  ```

- [ ] **Step 2：跑测试确认失败** ⇒ **FAIL**

- [ ] **Step 3：实现**
  - 列表：`GET /deliverables?project_id=PROJECT_ID&limit&offset`
    ⇒ ⚠️ **后端已做项目鉴权**（`check_project_access_or_404`）⇒ 前端**不得**
    自行按项目过滤（那会把「无权限」说成「无数据」）
  - 行展开 ⇒ 取 `current_version_id` ⇒ `<WorkflowProgressPanel workflowType="SIGN"
    workflowId={current_version_id} />`
  - ⚠️ `current_version_id` 为 null ⇒ 走空状态 ①
  - 分页：antd Table `pagination`（后端已支持 limit/offset）

- [ ] **Step 4：mock**：`/deliverables` + `/deliverables/{id}/versions` +
  `/workflow-progress/SIGN/{id}`（契约形状 + 生成类型标注）

- [ ] **Step 5：跑测试确认通过** ⇒ **PASS**

- [ ] **Step 6：提交** `git commit -m "feat(P9B): 交付物进度页（SIGN，宿主观测面板）"`

---

## Task T7：QA gate + 收口

**Files:**
- Report: `.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-p9b-1.md`（已 gitignore）
- Modify: `TODOS.md`、`.wolf/{STATUS,cerebrum,buglog}`

- [ ] **Step 1：静态门禁**
  ```bash
  cd pcs-frontend
  npm run typecheck        # exit 0
  npm run lint             # exit 0（自带 --max-warnings 0）
  npm run test             # ≥ 本批 baseline（725）
  cd ../pcs-backend && uv run pytest -q      # ≥ 5157
  ```

- [ ] **Step 2：MSW 三场景（浏览器回归，覆盖用户可见路径）**

  ⚠️ 三条 handler 的 response **必须从生成类型构造**（`satisfies
  components['schemas'][...]`），**不得手写自由 dict** ⇒ 这正是 bug-2040 的
  正确修法。

  | 场景 | handler 返回 | 类型来源 |
  |---|---|---|
  | 他人持锁 | `POST /locks/{rt}/{id}/acquire` → 409 + 持有者 | `LockResponse` |
  | 三种 409 | `PATCH /{base}/{id}` → 409 + `detail.conflict.basis` 三值 | `ConflictEnvelope` |
  | 降级 | `GET /health` → `{realtime:'degraded', realtime_reason:'redis_unavailable'}` | `components['schemas'][...]` |

  浏览器回归清单：
  - login 200 → dashboard 渲染
  - **7 条新路由可达**（6 结果页 + 交付物进度页），每条列表有数据
  - 点「编辑」⇒ 抽屉打开 + **请求体带 `expected_hash`**（network 面板核对）
  - **他人持锁**场景 ⇒ 锁指示器显示「XX 正在编辑」+ 保存按钮禁用 + **哈希仍可读可复制**
  - **三种 409** 场景 ⇒ 三套文案 + 对应出口
  - **降级**场景 ⇒ 顶栏横幅出现 + **编辑不被阻断**
  - 交付物进度页：行展开才发请求；空状态三态
  - 控制台无 antd / React / TS error；核心 mock 端点无 404
  - ⚠️ **本批改了 MSW 契约形状 ⇒ 必须再跑一次**（bug-2040 实测：mock 不同源
    ⇒ 浏览器 QA 看不见漂移）

- [ ] **Step 3：Playwright E2E（**只一条**：409 分流）**
  `pcs-frontend/e2e/` 已有 Playwright 配置。脚本：
  ```
  登录 → 打开结果页 → 打开记录编辑 → 修改并保存
  → 模拟 409（他人先保存）
  → 断言 409 弹窗出现
  → 点「查看差异」→ 断言展示当前版本（或 403 降级文案）
  → 点「放弃并刷新」→ 断言锁指示器消失、编辑按钮可用
  ```
  ⚠️ **只做这一条** —— E2E 的价值是跨组件集成，一条够；三条 = 三个 flaky 源。

- [ ] **Step 4：报告落盘**（`.gstack/qa-reports/`）

- [ ] **Step 5：收口**
  - `TODOS.md`：P9B-2 / P9B-3 的工作项登记（本批已登记 **TODO-065** 聚合端点、
    **TODO-066** 编辑审计端点）
  - `.wolf/STATUS.md`（`/handoff`）、`.wolf/cerebrum.md`、`.wolf/buglog.json`
  - SPEC 若与实现有偏差 ⇒ **登记修订**（不静默偏离）

- [ ] **Step 6：提交** `git commit -m "docs(P9B): P9B-1 收口 —— QA 报告 + TODOS + wolf 状态"`

---

## 验收（全 lane）

- `npm run typecheck` exit 0 · `npm run lint` exit 0 · `npm run test` ≥ baseline 全绿
- 后端 `pytest -q` ≥ 5157 passed / 0 failed
- **6 个 PATCH 在前端确实被调用，且每次都带基线**（断言请求体，不靠症状）
- **409 弹窗不得自动重试**（测试断言调用次数 == 1）
- **保存成功后基线刷新**（RF-1，否则第二次保存必假 409）
- **基线里的时间戳原样透传**（RF-9，测试断言逐字相等）
- 7 条新路由可达 + 浏览器回归 10 项全过 + **MSW 三场景**验过
- Playwright E2E 一条（409 分流）绿
- `tests/` 纳入类型检查 ⇒ fixture 也必须类型正确

---

## 尚未解决的问题

1. **「查看差异」只对 SYSTEM_ADMIN 可用** —— 编辑审计只能从 `/audit-logs` 读，
   后端**限 SYSTEM_ADMIN** ⇒ 普通 DESIGNER 拿到 409 弹窗却**看不到差异**。
   ⇒ 本批：前端优雅降级（403 ⇒ 「无权查看差异（需系统管理员）」）。
   ⇒ **TODO-066**（按项目守卫的编辑审计读端点，归属 P9B-2）。
2. **聚合端点缺失** —— `GET /workflow-progress/{type}/{id}` 是单条查询；
   三类工作流的 `workflow_id` 语义不同（CHANGE_NOTICE 是变更单自身的
   deliverable_id）⇒ 前端凑不齐。⇒ 本批只做 SIGN（用 `current_version_id`）。
   ⇒ **TODO-065**（`GET /deliverables/{id}/progress`，归属 P9B-2，触发条件已写明）。
3. **6 个模块的字段清单仍是手写的**（但在 `resultModules.ts` 一处，且**类型约束**
   到 `keyof ResponseType`）⇒ 改名 = 编译期错误。⚠️ 若后端给这些表出 **uiSchema**，
   应改走 `SchemaForm`（SPEC 的既有方向）—— 本批不做。
4. **`expected_updated_at` 第二档基线只在「hash 为空」时用** —— 正常路径是 hash
   一档；第二档是**兜底**，不是常态。
5. **`project_id` 来自 `src/constants/env.ts` 的 `PROJECT_ID` 常量**（单项目假设）
   ⇒ 多项目切换属 P9B-2（`WorkspaceSwitcher` 已存在但未接结果页）。
6. **P9 SPEC §4.2 的「7 个 mock type 文件改 import 自 ./api」不成立**（该节自己
   已注明：28/31 个导出 interface 在 OpenAPI 里无对应 schema）⇒ 本批**不执行**
   那条，只遵守「类型从 `components['schemas']` 来」。
7. **没有 WebSocket 客户端** —— 后端 `WS /api/v1/ws/notifications` 已就绪，但本批
   只读 `/health` 的 `realtime` 并**降级切轮询**；真 WS 订阅属 P9B-2。

## GSTACK REVIEW REPORT

| Review | Trigger | Why | Runs | Status | Findings |
|--------|---------|-----|------|--------|----------|
| CEO Review | `/plan-ceo-review` | Scope & strategy | 0 | — | 未跑（本批是实现计划，premise 由 UI-SPEC V2.1 / P9 SPEC V2.1 冻结） |
| Codex Review | `codex review` | Independent 2nd opinion | 0 | — | 未跑（outside voice 跳过，见下） |
| Eng Review | `/plan-eng-review` | Architecture & tests (required) | 1 | **issues_found → 已全部落进计划** | 12 个 issue（含 3 个 P1），0 critical gap 未闭环 |
| Design Review | `/plan-design-review` | UI/UX gaps | 0 | — | 未跑（本批是数据/并发接线为主，无视觉体系变更） |
| DX Review | `/plan-devex-review` | Developer experience gaps | 0 | — | 未跑 |

**裁决（14 条，全部落进正文）**

| # | 议题 | 裁决 | 落点 |
|---|---|---|---|
| D1 | gstack 写作风格 | 保留新版默认 | — |
| D2 | 是否先跑 `/office-hours` | 跳过（仓库已有 plan + 3 份 SPEC/ADR 文档 = 前提已备） | — |
| D3 | 技能路由写进 CLAUDE.md | 不加（本仓 CLAUDE.md 已是项目专属规则） | — |
| D4 | 范围：T5 无宿主 | **保留 T5 + 另建宿主页面** | T5 / T6 |
| A1 | `record_type` 词表（第 7 套） | **改成注册表键**；映射表 = 「键 → UI 表示」，value 不得是分类词；必须带 fallback（默认图标 + 原始键文本）；组件内**无**业务逻辑判断（grep 已证）⇒ 全是机械替换 | T4 Step 4（7 行改动清单） |
| A2 | 基线不止一档 | **三档基线**，抽成 `useEditBaseline` hook（所有编辑入口共用）；判定在**打开抽屉时**，保存只透传；禁用原因区分「无权限」/「无基线→联系管理员」；后端仍拒 no_baseline | T2 / RF-8 / RF-12 |
| A4 | 宿主页面 | 交付物进度页，**本批只 SIGN**；tab **可配置**（后端三值，**无 `DOC_PROXY`**）；空状态三态；懒加载在展开时 | T5 / T6 |
| D5 | 本批后端改多少 | **只加 `current_version_id`**（nullable，`selectinload` 禁 N+1，测试断言 `v.rev == d.current_rev`）；聚合端点延 P9B-2 | T0 / TODO-065 |
| A5 | 锁释放时机 | 抽屉关闭即 release；未保存修改先弹确认；页面卸载用 `sendBeacon`；release 失败**全部忽略** | T3 / RF-10 |
| DRY | 两个 PATCH 客户端 | **删 `editRecordApi`**；`EDITABLE_RECORD_TYPES` / `EditableRecordType` / `PatchBaseline` 一起移到 `records.ts`（依赖单向 locks → records，无循环）；基线测试**迁到** `records.test.ts` | T1 |
| 测试 | 覆盖深度 | 单元覆盖 11 个 GAP（后端阶梯已由 D2 覆盖）+ **MSW 三场景**（他人持锁 / 三种 409 / 降级）；**Playwright 只做一条**（409 分流） | T7 |
| TODOS | 登记哪些 | **只登记 2 条新发现**：TODO-065（聚合端点）/ TODO-066（编辑审计端点）；其余 4 项留在「P9B 全景」表 | TODOS.md |

**评审过程中核实的事实修正（已写进计划）**

| 修正 | 原表述 | 核实结果 |
|---|---|---|
| 后端 release 错误码 | 403 | **409**（`locks.py:254`）⇒ 前端「全部忽略」的处理与之无关，不阻塞 |
| 「有 hash+updated_at 的表」 | 5 张 | **21 张**；6 张可编辑结果表里 5 张有，**只有 `cost_est_results` 没有** |
| `current_rev` 可为 null | 判据「current_rev 为 null ⟺ current_version_id 为 null」 | `current_rev` 是**非空 str**，永不为 null ⇒ 判据改成「**没有版本行**」 |
| D5 约束 4 的验收命令 | `grep -rn "current_version_id" src/types/` | 会命中**生成物** `api.d.ts` ⇒ 假红 ⇒ 验收必须排除生成物 |
| `WORKFLOW_TABS` 的 type | `"DOC_PROXY"` | 后端枚举**没有** `DOC_PROXY`（代录 = `CUSTOMER_APPROVAL_PROXY`） |
| 「3 处机械替换」 | 3 处 | **7 处**（含 seed 与测试 fixture），已列成表；组件内**无**逻辑判断 ⇒ 全是机械替换 |
| 约束④ 权限过滤 | 担心 `project_id` 未鉴权 | **不成立** —— `deliverables.py:116` 已有 `check_project_access_or_404` |
| 约束② 分页 | 担心无分页 | **已有** `limit`(≤500) + `offset` |

**失败模式（全部有测试 + 错误处理 + 用户可见提示）**：见 RF-1~RF-12。
**Critical gap：0**（11 个测试缺口已全部进计划；4 条失败模式原本既无测试也无
错误处理且静默 —— 基线只发一档、时间戳过 `Date`、release 白占锁、record_type
传分类词 —— 已由 RF-8/9/10/11 覆盖）。

**NOT in scope**：P9B-2（签署流程前端 / ADMIN 前端 / 聚合端点 / 编辑审计端点）·
P9B-3（系统参数 / 物流向导）· P9A-DLV-007（`create_change_notice`）·
ADR-0050 P1~P6（用户裁决暂缓）· 生产构建路径的浏览器验证（vitest + MSW node
已覆盖同一形状）。

**What already exists（复用，不重建）**：`src/api/locks.ts`（`editLockApi`）·
`src/api/errors.ts`（`extractConflict` / `conflictKind`）· `src/api/changeImpact.ts` ·
`src/api/notifications.ts` + `todos.ts` · `useAuth` · `api` 实例 ·
`PageHeader` / `HashBadge` / `StateBadge` / `NumericCell` / `ModuleLayout` ·
`tests/mocks/handlers.test.ts` 的 ajv 校验 + 棘轮清单模式。
**不复用**：`SchemaForm`（它吃后端 `UiSchemaResponse`，结果表**没有** uiSchema）。

**并行化**：**Sequential implementation, no parallelization opportunity.**
T0（后端）→ T1（api 层）→ T2（hook + 组件）→ T3（页面）→ T4（横幅 + CIA）→
T5（面板）→ T6（宿主页）→ T7（QA）。T2~T6 都依赖 T1 的类型与 T2 的组件；
T3/T4/T5/T6 都改 `MainLayout.tsx` / `App.tsx` / `handlers.ts` ⇒ 同目录冲突。

**Outside voice**：跳过（用户未要求；codex 未装）。

### 决策委员会复审（2026-10-21 · 8 条裁决全部落进正文）

| # | 级别 | 裁决 | 落点 |
|---|---|---|---|
| **P1 必修 1** | P1 | `EditBaseline` 字段名统一为 **`expected_hash` / `expected_updated_at`** ⇒ `EditBaseline extends PatchBaseline` | T1 / T2 / T3 + **RF-13** |
| 补充 1 | P2 | `canEdit` 的来源 = **`sign_status ∈ {DRAFT, CHANGE_PENDING}`**（不查项目权限、不查签署职责）⇒ `canEdit` 改为**必填参数** | T2 / T3 |
| 补充 2 | P2 | 父组件用 `onSaved` 的 `record_hash` **就地更新本地 state**，**不重拉列表** | T3 Step 4 |
| 补充 3 | P2 | `sign_status` 检查在**渲染 [编辑] 按钮时**，不是打开抽屉后 | T3 Step 4 |
| 补充 4 | P2 | 映射表**只含本批 6 个注册表键**，其余 15 个走 fallback | T4 Step 4 |
| 补充 5 | P2 | `PatchBaseline` 的「至少一档」由**运行时**保证（类型层表达不了）⇒ 测试断言 `disabled=false ⇒ 至少一档存在` | T2 Step 1 |
| 补充 6 | P2 | `recordsApi.list` 返回类型约束为 `{ items: T[]; total: number }`（分页字段名两种，**不消费**） | T1 |
| 补充 7 | P3 | `sendBeacon` 的 body 用 **Blob + `application/json`** | T3 Step 5 |

⚠️ **委员会 P1 的机制判定被实测修正（2026-10-21）**：
委员会判定「`{...changed, ...baseline}` **一定编译失败**」⇒ 实测
`npx tsc --noEmit --strict` **通过（exit 0）**。

⇒ 真实后果**不是**「编译卡住实施者」，而是**更坏的**：
**编译绿 ⇒ 运行时每次保存必 409 `no_baseline`**（请求体里是 `expectedHash`，
后端找 `expected_hash` ⇒ 基线缺失 ⇒ `check_conflict` 走 `expected_hash is None`）。
⇒ 这正是本仓最怕的形状（类型系统不拦 ⇒ 假绿 ⇒ 运行时才炸），
且它会**绕过** T1 的既有守卫（那条测的是**直接调用** `recordsApi.patch` 传对了 key，
不是走 `EditBaseline` 展开的那条路径）。

⇒ 因此修法**不变**（字段名统一），但**必须补一条穿过展开的守卫**
（断言**请求体**含 `expected_hash`、不含 `expectedHash`）⇒ 已作为 **RF-13**
进 Review Focus 表 + T2 Step 1 的测试。

⚠️ 顺带核实：后端 `*UpdateRequest` 是 `extra="ignore"` ⇒ 多余字段
（如展开整个 `baseline` 带出的 `disabled` / `reason`）会被**静默丢弃**、不会 422
⇒ 但那是**依赖后端策略**的做法 ⇒ T3 改为**显式构造请求体**（只带两个基线 key）。
