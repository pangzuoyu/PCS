# P9B-1 计划：结果记录页 + 编辑锁前端（SPEC §6.21 / §6.7.1）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans。
> ledger: `.superpowers/sdd/PCS-PLAN-P9B-1-结果记录页与编辑锁/progress.md`

**Goal:** 兑现 SPEC §6.21（P9A-LCK-001~006）与 §6.7.1（P9A-CIA-001/002）的前端。

**前置（硬依赖）：** `docs/PCS-PLAN-P9A-5-债项清理.md` Task A 必须先落地 ——
`record_type` 归一到 `RECORD_TYPE_REGISTRY` 的键，否则前端要同时持两套标识
（实测 `RECORD_TYPE_REGISTRY` 21 键里 5 个 ≠ 类名 ⇒ 「类名」不是词表）。

**范围的事实基础（2026-10-20 实测）：**

- 6 类结果记录（cool_tower / filtration / flare / open_channel / psychro / cost_est）
  在前端**连页面都没有**：无路由、无 Page、无 api 客户端、`src/` 里 **0 个 PATCH 调用**。
  ⇒ 本 lane 是「从零建」，不是「接线」。
- 已就绪可复用：`useAuth`（`src/store/auth.ts`，`userId` 由后端 `/auth/me` 给，
  **不得**前端派生）、`api` 实例（`src/api/client.ts`，baseURL `/api/v1`，
  拦截器**只处理 401**）、`PageHeader` / `HashBadge` / `StateBadge` /
  `ChangeImpactPanel` / `ModuleLayout`。
- 既有范式：请求契约测试用 MSW `setupServer` + `lastPostedBody` 闭包捕获
  （`tests/pages/util/cooling_water.test.tsx`）；组件测试直接 `render` +
  `data-testid`（`tests/components/common/ChangeImpactPanel.test.tsx`）。
- ⚠️ `tsconfig.json:14` 把 `tests/` 纳入类型检查 ⇒ 测试 fixture 也必须类型正确。
- ⚠️ 手写类型**已漂移**：6 个 `src/types/*.ts` 的 `*UpdateRequest` 缺
  `expected_hash` / `expected_updated_at`；`CostEstResultResponse` 手写版注释
  说无 `record_hash`，生成版有。

---

## Task F0：api 层与类型漂移

**产出**

| 文件 | 内容 |
|---|---|
| `src/api/locks.ts` | `acquire` / `renew` / `release`，类型取 `components['schemas']['LockResponse']` |
| `src/api/changeImpact.ts` | `confirm` / `manualAdjust`（⚠️ **两个端点不可合并**，见 §6.7.1） |
| `src/api/errors.ts` | `extractConflict(err): ConflictDetail \| null` —— 读 `err.response.data.detail.conflict` |
| `src/api/records.ts`（6 个模块） | 6 类的 list / get / patch（patch **必带** `expected_hash`） |

- **删掉** 6 个手写 `*UpdateRequest` interface（漂移源），统一用生成类型
  （`src/api/reportBuilder.ts` 头注释定的规矩：类型全从 `api.d.ts` 来，不手写）。
- `extractConflict` **不得**塞进 axios 响应拦截器直接弹窗：规格要求按 `basis`
  分流不同文案不同动作 ⇒ 分流属于组件状态。

**测试**（RED 先写）
- `tests/api/locks_api.test.ts`：MSW 捕获路径；`extractConflict` 对
  409 / 404 / 非对象错误的行为（含 `detail` 缺失时不抛）。
- `tests/api/records_patch_baseline.test.ts`：**PATCH 必须带 `expected_hash`**
  —— 断言 `lastPostedBody.expected_hash` 等于响应里的 `record_hash`。
  ⚠️ 这是 SPEC P9A-LCK-006 的核心断言，抓「漏传基线 ⇒ 409」的静默回归。

---

## Task F1：共享组件层（SPEC §6.21 / §6.7.1 的实体）

| 文件 | 规格条款 | 要点 |
|---|---|---|
| `src/hooks/useEditLock.ts` | P9A-LCK-001/002 | acquire → 60s `renew` 定时器 → **失效转只读**；⚠️ **不得自动重试**续期（重试仍是 409，且会把失效掩盖成网络抖动）；离开页面**不**要求 release（30min TTL 回收），正常离开可 release |
| `src/components/common/EditLockIndicator.tsx` | P9A-LCK-001/003 | 三态：可编辑 / **他人持锁（只禁用保存，不阻断浏览、复制、查看哈希）** / 降级。⚠️ 禁用原因写「谁在改」，**不写「无权限」**（并发提示 ≠ 权限问题）；holder 显示用后端原文，不猜不缓存 |
| `src/components/common/EditConflictModal.tsx` | P9A-LCK-005/006 | 按 `basis` **三值分流**（`record_hash` / `updated_at` / `no_baseline`），文案与动作见 SPEC 表；两个出口「查看差异」/「放弃我的修改并刷新」；⚠️ **不得自动重试**；⚠️ `changed_by`/`changed_at` 为 null 时**不得**用 `updated_at` 冒充 |
| `MainLayout.tsx` | P9A-LCK-004 + §3.2 | 降级横幅：文案**原样渲染**后端 `message`，前端**不得拼接、不得**降级成一句全局提示；横幅**不阻断**编辑 |
| `ChangeImpactPanel.tsx` | §6.7.1 | 扩展 props：系统判定（`confirm`，按钮文案随响应 `decision` 分流）+ 人工判定（`manual-adjust`，`reason` **必填**，空 ⇒ 422）；⚠️ 现有 `onConfirmRecalc` 指向的是**另一个端点** `confirm-recalc`（P1 的传播触发器），**不可合并** |
| `src/api/audit.ts` 扩展 | P9A-LCK-005 | 「查看差异」要的 `changed_fields` 在**编辑审计**里，不在 409 响应体里 |

⚠️ `basis` 在 409（3 值：`record_hash`/`updated_at`/`no_baseline`）与 CIA 响应
（4 值：多 `full_hash`、`manual`）里**不是同一个词表** ⇒ 两个类型分开，不复用。

**测试**：`tests/components/common/{EditLockIndicator,EditConflictModal}.test.tsx` +
`tests/hooks/useEditLock.test.tsx`（fake timers 验 60s；验**不**重试）。

---

## Task F2：6 个结果页

每页：列表（Table，可按项目/工作区）→ 详情（字段按生成 schema 的**响应**类型）→
编辑抽屉（**必带** `expected_hash`；挂 `EditLockIndicator`；409 接 `EditConflictModal`）。

| 模块 | 路由 | 后端基址 | 结果主键字段（⚠️ 各不相同） |
|---|---|---|---|
| cool_tower | `/results/cool-tower` | `/cool-tower/results` | `id` |
| filtration | `/results/filtration` | `/filtration/results` | `result_id` |
| flare | `/results/flare` | `/flare/results` | `result_id` |
| open_channel | `/results/open-channel` | `/open-channel/results` | `result_id` |
| psychro | `/results/psychro` | `/psychro/results` | `result_id` |
| cost_est | `/results/cost-est` | `/cost-est/results` | `result_id` |

⚠️ **`cost_est_results` 没有 `updated_at`**（`edit_guard.TABLE_CAPABILITIES`
里 `has_updated_at=False`）⇒ 该页**不能**依赖 `expected_updated_at`，只有
`record_hash` 一档基线。
⚠️ 6 条路径的 `record_type` 一律用**注册表键**（`CoolingTowerResult` /
`FiltrationResult` / `FlareSystemResult` / `OpenChannelResult` / `PsychroResult` /
`CostEstResult`），**不是**表名。

**测试**：`tests/pages/<module>/*.test.tsx` —— 每页至少 3 例：列表渲染 /
打开编辑带出 `expected_hash` / 409 弹窗按 basis 分流。

---

## Task F3：QA gate + 收口

按 `CLAUDE.md`「Per-Batch QA Gate」跑一次浏览器回归（vite :5173）：
`typecheck` clean · `lint` clean（`--max-warnings 0`，别用裸 `npx eslint`）·
`vitest run` ≥ 本批 baseline · login 200 + 6 个新路由可达 + 控制台无
antd/React/TS error · 核心 mock 端点无 404。报告落
`.gstack/qa-reports/qa-report-pcs-frontend-YYYY-MM-DD-p9b-1.md`（已 gitignore）。

收口：`TODOS.md`（TODO-060/061 标闭环）· `.wolf/{STATUS,cerebrum,buglog}` ·
SPEC 若与实现有偏差**登记修订**（不静默偏离）。

---

## 验收（全 lane）

- `npm run typecheck` exit 0 · `npm run lint` exit 0 · `npm test` 全绿且 ≥ baseline
- `tests/` 纳入类型检查 ⇒ fixture 也必须类型正确
- 6 个 PATCH 在前端**确实被调用**，且**每次都带** `expected_hash`
- 409 弹窗**不得**自动重试（测试里断言调用次数 == 1）

## 尚未解决

- **6 个页面的 UI 细节**（字段分组、列宽、空态文案）SPEC 未逐字段规定 ⇒ 按
  各模块生成 schema 的响应字段**动态渲染**，不硬编码字段清单（否则又一份要漂移的清单）。
- **`ChangeImpactPanel` 现由 mock 数据驱动**（`src/mocks/seed/streams.ts`），
  接真实 CIA 端点会牵动 SIM 域 ⇒ 本 lane 只**扩展 props 与回调**，不替它换数据源。
