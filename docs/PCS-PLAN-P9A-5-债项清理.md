# P9A-5 计划：`record_type` 词表归一（TODO-060）+ cost_est 项目隔离（TODO-061）

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans。
> ledger: `.superpowers/sdd/PCS-PLAN-P9A-5-债项清理/progress.md`

**Goal:** 关掉 P9A-4 收口时登记的两笔债，且**必须在 P9B 前端接线之前**做完 ——
前端若照现状写，会同时持两套 `record_type` 标识。

**绑定依据:** ADR-0048（编辑锁）· ADR-0050 §未决 2（`CostEstResult` 缺列，TODOS.md TODO-048 同族）

---

## Task A：`record_type` 归一到 `RECORD_TYPE_REGISTRY` 的键

### A0. 前提（2026-10-20 实测，推翻了 TODO-060 的两条原文）

| TODO-060 原文 | 实测 |
|---|---|
| 「三处三套词表」 | **五套**：注册表键（21，其中 **5 个 ≠ 类名**）/ 表名 / 类名（`data_lineage` `record_change_snapshots`）/ 前端 SIM 域 `PIPE`/`PUMP`/`UTIL` / `cia_engine.REGISTRY`（第 6 套，键与它自己写进 DB 的值对不上） |
| 「`__tablename__` ↔ `RECORD_TYPE_REGISTRY` **双向**可换」 | ❌ **假**。只有「键 → 表名」单向成立；「表名 → 键」21/21 全失败（复数 vs 单数），「类名 → 键」5 个失败 |

⇒ **「类名」不是一套词表** ⇒ 原定的「归一到类名」方向作废。

### A1. 裁决

- **单一来源 = `RECORD_TYPE_REGISTRY` 的键**（`app/services/calc_lineage.py:84`）。
  理由：它是**唯一**已被两个 URL 空间共用（`/change-impact` + `/records/{module}`）、
  且被 DB 列 `record_comments.record_type` 存着的那套。
- `/locks/{record_type}` 与 6 个 PATCH 的 guard **改用键** ⇒ 全仓一套。
- `TABLE_CAPABILITIES` 的键由**表名**改为**注册表键**；其 `model` 字段删除 ——
  模型从注册表取（消掉「表 → 模型」的第二份清单，正是本文件 docstring 自己
  反对的那件事）。
- `/locks` 三个端点**必须校验** `record_type ∈ TABLE_CAPABILITIES`，否则 404
  （与 `/change-impact` 未知类型的处理一致）。⚠️ 这是**破坏性契约变更** ⇒ SPEC 升 **V2.0**。
  无兼容期：前端零调用方（实测 `grep -rn '/locks' src/` 0 命中）。
- `cia_engine.REGISTRY`（第 6 套词表，且键与写入值对不上）**不在本 task**：
  改它要重路由 CIA 扫描 ⇒ 单独登记 TODO-062。

### A2. 步骤（TDD）

1. RED：`POST /locks/cost_est_results/{id}/acquire`（表名）⇒ 现在 200，期望 **404**。
2. RED：`POST /locks/CostEstResult/{id}/acquire`（键）⇒ 200，且降级横幅文案
   **不**误加「；本次编辑无冲突检测」。
3. 改 `TABLE_CAPABILITIES` 键 + 去 `model` 字段 + `capability_of` 走注册表。
4. 改 6 个 PATCH 调用点的 `record_type=` 字面量。
5. `/locks` 加校验（三端点；`renew` 不碰 DB 仍成立 —— 校验查的是内存表）。
6. 集合契约测试（AST）：6 个 PATCH 端点传入的字面量**必须**都在
   `TABLE_CAPABILITIES` 里；且其键 ⊆ `RECORD_TYPE_REGISTRY` 的键。
7. 更新既有 lock(12) + edit_guard(16) + edit_conflict(8) 测试里用表名的地方。
8. SPEC V2.0（§6.21 P9A-LCK-001/006、§6.7.1 的词表句、409 示例、修订记录行）；
   ADR-0048 §⑤§⑥ 同步。

### A3. 验收

- `uv run pytest tests/api/v1/test_edit_lock_api.py tests/services/test_edit_guard.py tests/api/v1/test_edit_conflict.py tests/architecture -q` 全绿
- 全量后端 ≥ 5102 + 新增例数
- `check_openapi_payload_coverage.py` exit 0（裸字段 71 未增）
- `openapi.snapshot.json` 的 `{record_type}` 参数应带 `enum`（新增）⇒ 前端能拿到词表

---

## Task B：`CostEstResult` 项目隔离（TODO-061）

### B1. 裁决

- **补 `cost_est_results.project_id`**（`Uuid` NOT NULL，FK → `projects.project_id`，带索引）。
  - 依据：ADR-0050 `:403`/`:477` + TODO-048「归属：P9A 补列时一并处理」三处一致。
  - 反查方案（`equipment_id → equipment_list.project_id` JOIN）被否：① 守卫 helper
    读 `record.project_id` ⇒ JOIN 要另写一条守卫路径；② `GET /results` 的
    **项目过滤**必须有列。
- **不补** `workspace_id` / `sign_status` / `updated_at`：`CostEstResult` 的设计
  是「与设备 1:1、状态跟随设备」（模型 docstring + `cost_est_persist_service.py:12`）。
  ⚠️ 因此 `has_updated_at=False` **保持不变** ⇒ `tests/alembic/test_p9_006...:90`
  那条断言不红。
- **漂移风险**（设备换项目 ⇒ 冗余列过期）：创建路径从 equipment **复制**
  `project_id`；加一条测试钉住「create 时 project_id 取自 equipment」。
  设备换项目的路径**当前不存在**（无任何端点 UPDATE `equipment_list.project_id`）。

### B2. 步骤（TDD）

1. RED：8 个端点逐一断言「无权用户 ⇒ 404/403 且**数据没变**」——
   ⚠️ 沿用 bug-2039 的教训：**光断言状态码不够**（旧顺序下响应也是 404）。
2. RED：`GET /cost-est/results` 不传参 ⇒ 现在**全库返回**，期望只返回调用方
   有权项目的行（跨项目读泄漏）。
3. 迁移 `p9_007`（`down_revision="p9_006"`）：加列 nullable → `UPDATE ... FROM
   equipment_list` 回填 → 改 NOT NULL + FK + 索引（幂等：`if_not_exists` / `if_exists`）。
4. ORM 加列；创建路径（4 个 POST）从 equipment 取 `project_id` 写入。
5. 8 个端点加守卫；PATCH 的顺序必须是 **鉴权 → `check_conflict` → 保存**。
6. `list` 加 `project_id` 过滤参数；「不传 = 全量」的旧语义**删除**。
7. 改既有测试 fixture：`test_cost_est_api.py` / `test_edit_conflict.py` /
   `test_cost_est_persist_service.py` 用的是**随机 project_id** ⇒ 必须建真
   project + 授权（或 SYSTEM_ADMIN），否则新增守卫让它们全红。
8. DRIFT 守门：`alembic current` vs `heads`，再**两库各跑一次** `alembic check`
   （退出码 **255**；DB 落后时它 exit 0 但**根本没跑**）。

### B3. 验收

- 新增守卫测试先 RED 后 GREEN
- 全量后端 ≥ Task A 基线
- 两库均 `p9_007`（head），`alembic check` 均 exit 0 且**真跑了**
- `record_hash` 不变式测试（`tests/services/test_record_hash_invariant.py`）照绿

---

## 尚未解决（本计划结束时）

- **`cia_engine.REGISTRY` 是第 6 套词表，且它的键与它写进 `data_lineage` 的值
  对不上**（`cia_engine.py:46-52` 键是 `config_asset` 单数，`:160` 写的是类名
  `ConfigAsset`）⇒ 登记 TODO-062，不在本计划内改（改它要重路由 CIA 扫描）。
- **`record_type` 的其余四套**（`data_lineage` / `record_change_snapshots` 存类名、
  `audit_logs.resource_type` 混存类名与注册表键、前端 SIM 域 `PIPE`/`PUMP`/`UTIL`）
  本计划只把**契约面**（URL 参数 + guard 入参）归一，**历史数据与 DB 列不动**
  ⇒ 存量行里两种写法并存，属预期。
- **`ADR-0050:200-207` 有事实错误**（称 `record_comments` 存类名，实为注册表键）
  ⇒ 本计划修订该处。
