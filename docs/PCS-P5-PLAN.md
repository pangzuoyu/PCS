# PCS P5 批计划锚点（2026-09-16 / 末次修订 2026-09-17）

**目的**：P5-0 批执行过程中产生的**待办裁决 / 跨任务约束 / 实施细节**，统一锚定在本文件。
**非用途**：不替代各 SUP / ADR / 计划文件；本文件是 P5-0 批内的"运行记事本"，批次末（V1.4 / V1.9 / ADR-0028 修订）应清空并归档。

**当前状态（2026-09-17）**：P5-0 批 **6/7 已闭环**：
- ✅ Task 1（P5-0-1 model extension）commit 40b0c69
- ✅ Task 3（P5-0-3 StreamSignStatus 9-state）commit 2741ed9
- ✅ Task 4a（P5-0-4a PK rename 10 表 + tag_number 统一）commit 34ab33e
- ✅ Task 24a（P5-0-5 PSV 多标准 + 9 类）commit fcf1108
- ✅ Task 2（P5-0-2 HEAT 双轨 + ADR-0027 V1.0 + 10 类）commit 37b6dc4
- ⏳ Task 24b（P5-0-5 canonical JSON 工具 + compute_record_hash 集成）—— **DEFERRED**（quality 强化，不阻塞 P5-1 启动；详 §约束 5）
- ✅ Task 25/26（本文件 = 文档批次末修订，Q1 锚点）

**Task 4a 已 closure**，故 §"P5-0 批剩余 3 task 路径"已执行完毕；§"Task 4 工作分解"已实施并 commit，详见 §实施细节备忘。

**批次末修订 TODO**：本文件本次修订已闭合 Q1 锚点；剩余 P5-1 启动前的 backfill = §约束 5 Task 24b 决策。

---

## 跨任务约束（用户 2026-09-16 裁决）

### 约束 1：column_sizing 字段统一（Q2 路径 A）

- **现状**：column_sizing 表用 `column_tag` 业务字段（P5-0-1a 落地）；其余 16 张计算表用 mixin `tag_number`
- **裁决**：**Task 4a 统一为 `tag_number`**（路径 A — 与 16 表一致，无特例）
- **执行结果**（commit 34ab33e）：column_tag 列 drop + tag_number NOT NULL 强化 + UNIQUE 迁移至 (project_id, tag_number)。✅ 闭环

### 约束 2：relief_results 跨 project FK 校验（Q3 路径 B）

- **现状**：relief_results.selected_psv_id → psv_results.psv_id 无跨 project 隔离
- **裁决**：**Task 18（P5-3-6 PSV API + persist）补全写入前跨 project 校验**
- **执行时机**：Task 18 persist 层加 service 层 assert；Task 24（PSV 标准配置）落地时在 relief_results.standard_profile_code 相关逻辑加注释："跨 project FK 校验待 Task 18 补全"
- **P5-0 批内不动**：与 Task 24 scope 正交，避免 scope 膨胀。✅ 闭环

### 约束 3：REGISTRY 类数中间顺序（Q4 修订）

| 时点 | REGISTRY 类数 | 内容 | 状态 |
|---|---|---|---|
| P4-TASK0 末态 | 5 | PipingResult / PumpResult / FlashResult / PipeNetworkResult / TwoPhaseResult | ✅ 闭环 |
| P5-0-1a 后 | 8 | + ReliefResult / ColumnSizingResult / MixerResult | ✅ 闭环（commit 40b0c69）|
| P5-0-5 后（Task 24a）| **9** | + ProjectCalculationStandardProfile | ✅ 闭环（commit fcf1108）|
| **P5-0-2 后（Task 2）**| **10** | **+ HeatResult（修正 P4 遗漏）**| ✅ **闭环（commit 37b6dc4）**|
| P5-0-1b 后（4 蒸汽表）| **14** | + SteamDrumResult / TwoPhasePipeSizingResult / BlowdownDrumResult / ThermosiphonCirculationResult | ⏳ 后续 sprint |
| P5-0-4a 后（Task 4a）| 10 不变 | Task 4a 仅字段重命名 + tag_number 统一；REGISTRY 不增 | ✅ 闭环 |

**顺序不可跳跃**。Task 24a checkpoint 断言 `len(RECORD_TYPE_REGISTRY) == 9`，Task 2 修订为 `== 10`（Q4 13 → 14 因 + HeatResult）。

### 约束 4：文档批次末修订清单（Q1 锚点 — 2026-09-17 闭环）

P5-0 批**末**修订：

| # | 修订项 | 状态 |
|---|---|---|
| 1 | ADR-0028 影响段：registry 12/13 → 8/9 | ✅ **核实无需修订** — ADR-0028 V1.1 全文不含 REGISTRY 数字陈述；原 Q1 锚点为 2026-09-16 预期，本批核实后无需动 ADR-0028 |
| 2 | V1.8/V1.9 计划：Task 1 拆分为 P5-0-1a + P5-0-1b | ⏳ PCS-PLAN V1.8/V1.9 升版留 P5-1 启动前 |
| 3 | P5-0 批任务清单：Task 1 工作量重评（实质完成 Task 1a = 1 主 commit 闭环；Task 1b = 后续 sprint）| ✅ 本文件 §"当前状态"已记录 |
| 4 | P5-PLAN Task 2 §"接口"原文"48 列（9 旧 + 39 新）"勘误 | ✅ 本文件 §"实施细节备忘 / Task 2"已修订为 **56 列（9 旧 + 5 现状 + 42 新）**|
| 5 | P5-PLAN §"Task 4 推进" 文本 DICT 方向核实 | ✅ commit 34ab33e 已 closure，方向 = **移除 `_calc` 后缀**（统一 `*_id`），与 DICT V3.3 + P0 规格说明书第 227 行一致 |
| 6 | ADR-0027 决策 1 表格"36 标量 + 3 JSONB"勘误（应为 39 标量 + 3 JSONB = 42 新）| ✅ ADR-0027 V1.0 proposed 已修订并 commit 37b6dc4 |
| 7 | ADR-0027 决策 3 引用"DICT V3.4 §4.1"虚构引用（V3.4 文件不存在）| ✅ ADR-0027 V1.0 proposed 已修订并 amend commit 37b6dc4 |

**P5-0 批末执行结果**：#3-7 已本批闭环；#1-2 留 ADR-0028 V1.2 升版 + PCS-PLAN V1.8/V1.9 升版（属 V1.x 计划升版，不属 P5-0 批内代码修订）。

### 约束 5：Task 24b DEFERRED 评估（2026-09-17 核实）

**Task 24b 范围**：canonical JSON 工具 + compute_record_hash 集成。

**核实结果**：
- `compute_record_hash`（`services/calc_lineage.py:89-115`）：6 位有效数字规范化 + sha256 截断 16 hex，**已实现**
- `finalize_calc_record`（`services/calc_lineage.py:118-157`）：record_hash + DataLineage 血缘 + D4/D5 扩展，**已实现**
- canonical JSON 工具：当前 `_json.dumps(..., sort_keys=True)` 已部分 canonical；**质量强化**（防 json.dumps 默认参数漂移），非阻塞路径

**P5-1 启动条件检查**：
- ✅ vessel_results 业务字段全是 JSON（不需补列，D-2 已 unlock）
- ✅ record_hash 链路就绪
- ✅ REGISTRY 10 类（HeatResult 已入，P5-1 vessel_results 入 REGISTRY 时顺位 ≥ 10）

**结论**：Task 24b **不阻塞 P5-1 启动**；留 P5+ 后续 sprint 作 hash 一致性强化。

---

## P5-0 批路径（用户 2026-09-16 推荐 — 已执行）

| Task | 工作量 | 依赖 | 下游批次 | commit | 状态 |
|---|---|---|---|---|---|
| **Task 4a**（PK rename 10 表 + tag_number 统一）| 大 | Task 1 ✅ | P5-1（VESSEL）| 34ab33e | ✅ |
| **Task 24a**（PSV 多标准配置 + REGISTRY +1 = 9）| 大 | Task 1 ✅ | P5-3（PSV）| fcf1108 | ✅ |
| **Task 2**（HEAT 双轨 56 列 + REGISTRY +1 = 10 + ADR-0027）| 中 | — | P5-4（HEAT）| 37b6dc4 | ✅ |

**执行结果**：Task 4a → Task 24a → Task 2 已按推荐顺序闭环。

---

## 实施细节备忘

### Task 4a 工作分解（已 closure，commit 34ab33e）

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §96-110 + DICT V3.3 + P0 规格说明书第 227 行：

1. **PK rename 10 表**：方向 = **移除 `_calc` 后缀**（统一 `*_id`）
   - vessel_results: vessel_calc_id → vessel_id
   - two_phase_results: two_phase_calc_id → two_phase_id
   - sep_equip_results: sep_calc_id → sep_equip_id
   - heat_results: heat_calc_id → heat_exchanger_id
   - cv_results: cv_calc_id → cv_id
   - restriction_results: orifice_calc_id → orifice_id
   - cooling_tower_results: ct_calc_id → cooling_tower_id
   - psychro_results: psychro_calc_id → psychro_id
   - open_channel_results: channel_calc_id → open_channel_id
   - filtration_results: filter_calc_id → filter_id
2. **tag_number 统一**（约束 1）：column_sizing drop column_tag + tag_number NOT NULL + UNIQUE 迁移至 (project_id, tag_number)
3. **alembic migration**：`p5_0_4a_pk_rename_and_tag_number.py`（down_revision = p5_open_005_model_extension）

### Task 24a 工作分解（已 closure，commit fcf1108）

按 SUP-P5-PSV-001 §3 + ADR-0028 V1.1 决策 11：
- psv_results / relief_results 加 7 列（standard_profile_code / standard_refs_json / formula_ref_json / pending_review / migrated_default / override_reason / override_approval_json）
- EXCLUDE USING gist 约束（btree_gist 扩展已就绪，commit 5060b76）
- ProjectCalculationStandardProfile 配置类（registry +1 = 9）
- TypedDict 强类型化（PSV 选型 + 泄放计算）

### Task 2 工作分解（已 closure，commit 37b6dc4）

按 SUP-009 V1.0 §3.1 + P5-OPEN-006 + ADR-0027 V1.0 决策 1/2/5：

- **双轨结构**（9 旧 + 5 现状 + 42 新 = **56 业务列**）：
  - 9 旧标量（SPEC-P5 V1.3 P5-OPEN-006 权威）：equipment_no / equipment_name / **duty** / effective_area / hot_inlet_pressure / hot_outlet_pressure / cold_inlet_pressure / cold_outlet_pressure / u_overall
  - 5 现状 JSONB：air_side_json / design_conditions_json / enthalpy_table_json / input_json / output_json
  - 39 新标量 + 3 新 JSONB：SUP-009 §3.1.1-3.1.6 分组（`duty` 与 9 旧共享 1 列）
- **新增列数**：9 旧 + 39 新标量（除 duty 共享）+ 3 新 JSONB = **51 列**
- **新轨总字段**：39 标量 + 3 JSONB = **42 新字段**
- **REGISTRY +1 = 10**（修正 P4 遗漏 HeatResult 入 REGISTRY）
- **ADR-0027 V1.0 proposed**（6 决策：双轨结构 / REGISTRY / PK rename 边界 / 5 JSONB 保留 / 新轨 42 字段 / record_hash 暂含全部业务列）

---

## P5 frontend 收口 checklist（2026-09-17 新增）

**目的**：P5 全部前端页面完成后（VESSEL / SEP_EQUIP / PSV + 标准 profile 等），统一收口**前端技术债**，避免 6 批次都登记但从未解决的悬案。

### 收口项 #1：硬编码常量统一抽象（OPEN-2 + OPEN-3）

- **OPEN-2：PROJECT_ID 硬编码**
  - 位置：`pcs-frontend/src/pages/routeWrappers.tsx:71` — `'00000000-0000-0000-0000-000000000001'`
  - 风险：未来 P5-6 / P5-7 多项目场景必须从 store/URL 派生，UUID 字面量无法支持

- **OPEN-3：DEV_BEARER 硬编码 3 处重复**
  - 位置 1：`pcs-frontend/src/pages/routeWrappers.tsx:74` — `DEV_BEARER = 'Bearer mock-jwt-token'`
  - 位置 2：`pcs-frontend/src/layouts/MainLayout.tsx:82` — 字面量 `'Bearer mock-jwt-token'`
  - 位置 3：`pcs-frontend/src/mocks/handlers.ts:14` — `MOCK_TOKEN`（来自 seed/meta.ts）
  - 风险：3 处值必须人工同步，未来替换 auth 方案时遗漏即 P0 bug

**处理方案**：P5 全部前端页面（P5-1 / P5-2 / P5-3）完成后，**统一抽 `src/constants/env.ts`**：

```ts
// src/constants/env.ts（建议）
export const PROJECT_ID = (import.meta.env.VITE_PROJECT_ID ?? '00000000-0000-0000-0000-000000000001');
export const DEV_BEARER = `Bearer ${import.meta.env.VITE_DEV_TOKEN ?? 'mock-jwt-token'}`;
```

- 3 处 import 替换为统一来源
- Vite env vars 通过 `.env.development` / `.env.production` 注入
- 收口 commit：`refactor(p5-close): constants/env.ts 统一 PROJECT_ID + DEV_BEARER`

**不在各批次分散处理的原因**：
1. P5-3（PSV 前端）/ P5-2（SEP_EQUIP 前端）/ P5-1（VESSEL 前端）各自批次都会引入新的 `routeWrappers.tsx` + `useFetch` 调用，分散处理会形成 3 次 commit + 3 次文件 diff
2. 收口涉及 vite env vars 注入（`.env.development` / `.env.production`），需要 P5 全栈 frontend baseline 一致后整体切换
3. 1 次集中处理 vs 6 次分散处理：减少跨批 merge 冲突 + 减少回归测试轮次

**触发条件**：P5-3 frontend 闭环（commit 93627a7 后端 + 本批次 frontend）后，由用户"继续"驱动收口 task。

**状态**：✅ 已收口（commit `1afa756`，2026-09-17）—— `src/constants/env.ts` 统一 PROJECT_ID + DEV_BEARER，`src/vite-env.d.ts` 扩展 ImportMetaEnv（VITE_PROJECT_ID / VITE_DEV_TOKEN 可选），`routeWrappers.tsx` / `MainLayout.tsx` / `AssetListPage.tsx` 4 处硬编码字面量清零；tsc + eslint + vitest 496/496 baseline 持平

### 收口项 #2（未来登记位）

后续 P5-1 / P5-2 frontend 闭环时如发现跨批技术债，统一登记于此段。

---

## 关联文档

- PCS-PLAN-P5-DEVICE-EQUIPMENT.md（V1.3 总计划）
- PCS-P5-START-CHECKLIST.md（启动门 12 项检查）
- **ADR-0027 V1.0 proposed**（HEAT 双轨设计，2026-09-17）
- ADR-0028 V1.1 accepted（PSV 多标准引擎）
- ADR-0030 V1.1 accepted（ChEDL 版本锁定）
- SUP-008 V1.1 + SUP-009 V1.0 + SUP-010 V1.1

**生成时机**：P5-0-1 完成后立即创建（2026-09-16）
**末次更新**：2026-09-17（Task 25/26 文档批次末修订 + P5 frontend 收口 checklist 登记 OPEN-2/3）
