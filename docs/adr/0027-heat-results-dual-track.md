---
status: accepted
date: 2026-09-17
revised: 2026-09-18
version: V1.0
proposed_by: P5 架构评审委员会（Task 2 起草组）
related: [SUP-009 V1.0, P5-PLAN-P5-DEVICE-EQUIPMENT.md, P5-OPEN-006, ADR-0028 V1.1, DICT-ALL-003 V3.3, P0 规格说明书]
accepted_by: P5-4 实施落定（commit p5_4_heat_duty_split 迁移）
---

# P5-4 实施状态：duty 双轨字段已就位（决策 5 跟踪项闭环）

**2026-09-18 修订**：

- 决策 5 跟踪项"P5-4 实施时按需拆分 duty_legacy/duty_calc"已通过 `p5_4_heat_duty_split` alembic 迁移落地：
  1. `heat_results.duty_legacy` Float nullable — P4 上游 duty
  2. `heat_results.duty_calc` Float nullable — P5 计算 duty
  3. 存量回填：`duty_calc = duty WHERE duty IS NOT NULL`（默认按溯源未知归 P5 计算归属）
  4. ORM `HeatResult` 加 `duty_legacy` + `duty_calc` 两字段，`duty` 列保留向后兼容
- **未修改 service 层写入路径**：`HeatCalcInput.duty` 与 `_store(inp)` 调用未变更。
  双轨字段的实际写入策略（HTRI conversion 走 duty_calc vs 直接用户输入走 duty_legacy）
  由 P5-4 HEAT 工艺工程师后续批决定。
- **`duty` 列保留**：向后兼容 P5-OPEN-006 §"9 旧标量"承诺；后续批如全量切换至 duty_calc/duty_legacy 双轨，
  需另起迁移下掉旧列。

---

# HEAT 双轨设计：9 标量旧字段保留 + 40 新字段同表扩展

HEAT 模块（P5-4 batch）需支持 HTRI 空冷器（ACHE）+ TEMA 管壳式换热器两类工艺计算，输出字段数 30+。SPEC-P5 V1.3 P5-OPEN-006（2026-09-03 联合项目组批准）声明原 heat_results 表 9 标量旧字段向后兼容，Task 2（P5-0-2）新增 39 字段。SUP-009 V1.0 §3.1 是字段层权威定义。

若不显式区分"旧 9 标量"与"新 40 字段"，将出现 P5-4 实现时新旧字段命名冲突、HTRI 导出数据无法映射到新结构、record_hash 因含旧字段产生数据漂移、P6 HEAT_EXCHANGE 物流链读取数据字段不确定等问题。

本 ADR 记录 HEAT 双轨设计的 6 项架构裁决。

决定：**旧 9 标量 + 现状 5 JSONB + 新 40 字段 三层共存于 heat_results 表**。

---

## 决策 1：双轨（旧 9 标量 + 新 40 字段）三层结构

| 层级 | 内容 | 来源 | 退役计划 |
|---|---|---|---|
| **旧轨**（P5-OPEN-006 §保留） | 9 标量：equipment_no / equipment_name / duty / effective_area / hot_inlet_pressure / hot_outlet_pressure / cold_inlet_pressure / cold_outlet_pressure / u_overall | SPEC-P5 V1.3 P5-OPEN-006 | 不退役（向后兼容承诺） |
| **现状 JSONB**（P3 通用 + P4 实施）| 5 JSONB：air_side_json / design_conditions_json / enthalpy_table_json / input_json / output_json | 早期 HEAT 临时实现 | P5-4 服务层按需补 SPEC-P5 V1.2 §4.1 设计的 9 JSONB 容器 |
| **新轨**（P5-0-2 Task 2 扩展） | 39 标量 + 3 JSONB（shell_params / tube_params / ache_params）| SUP-009 V1.0 §3.1 | 不退役（业务物理属性） |

**总业务列 = 9 旧 + 5 现状 + 42 新 = 56 列**（加 26 lifecycle/mixin = 82 列）

> **勘误**：P5-PLAN Task 2 §"接口"原文"48 列（9 旧 + 39 新）" 表述偏差：
> 1. "39 新" 实际是 **39 标量 + 3 JSONB = 42 新字段**（SUP-009 §3.1.2 `duty` 与 9 旧 `duty` 合并为 1 列，共享语义）
> 2. SUP-009 §3.3 笔误"39 字段（2 个 JSONB 复合结构）"应改为"39 字段（3 个 JSONB 复合结构：shell_params / tube_params / ache_params）"
> 3. "9 旧" 定义为 9 标量旧字段（SPEC 权威），不是 P5-PLAN 文本"现状 5 JSONB"
>
> 修订纳入 P5-0 批末文档同步清单（Q1 锚点）。

---

## 决策 2：REGISTRY 9 → 10

**理由**：HeatResult 自 P4 起已存在 ORM（`app/models/calc.py:456`），但 P4 时遗漏登记 RECORD_TYPE_REGISTRY。本批次发现 git log 无任何 heat_results / HeatResult 在 `app/services/calc_lineage.py` 的历史（git log -S 无结果），确认情形 A：P4 实施遗漏。

**修正动作**：Task 2 同步 HeatResult 入 REGISTRY，9 → 10。

**Q4 约束 3 修订**：原"P5-0-1b 后 REGISTRY = 13"修订为"= 14"（+ HeatResult）。此修订不破坏 Q4 顺序约束，仅修正基数（13 → 14）。

**验收断言**：`len(RECORD_TYPE_REGISTRY) == 10`（P5-0-2 后）。

---

## 决策 3：PK rename 已 Task 4a closure（不在 Task 2 scope）

**现状**：heat_results PK = `heat_exchanger_id`（DICT-ALL-003 V3.3 + P0 规格说明书权威）

**DICT 版本事实**：
- DICT V3.3 §4.1：不直接定义 heat_results PK（仅含 type_code / snapshot_id）
- **DICT V3.4 文件不存在**（V3.3 → V3.5 跳过 V3.4；spec/PCS-DICT-ALL-003 V3.3.md / V3.5.md 已确认）
- P0 规格说明书（`spec/工艺专用综合计算软件需求规格说明书 Web版 P0.md:227`）：`heat_results PK = heat_exchanger_id` ← **权威定义**

**Task 4a closure（commit 34ab33e, 2026-09-16）**：10 表统一方向 = **移除 `_calc` 后缀**（统一为 `*_id`）：
- `heat_calc_id → heat_exchanger_id` ✅（DICT V3.3 + P0 对齐）
- `vessel_calc_id → vessel_id` / `cv_calc_id → cv_id` 等 10 表一致

**Task 2 裁定**：**不动 PK**。理由：
1. Task 2 scope = HEAT 双轨字段扩展；PK 命名 = Task 4a 已 closure
2. heat_results PK 已是 `heat_exchanger_id`（commit 34ab33e 已落地）
3. ADR-0027 决策 3 旧版"V3.4 方向 = heat_calc_id"为**未核实引用**，已修订

**P5-PLAN §"Task 4 推进"勘误**：原文"heat_calc_id → heat_exchanger_id" 与 Task 4a commit **方向一致**（非"反向"），P5-0 批末修订删除反向标记。

---

## 决策 4：现状 5 JSONB 保留（非旧字段）

**理由**：
- 5 JSONB 是 P3 通用约定（input_json / output_json）+ P4 HEAT 早期临时实现（air_side_json / design_conditions_json / enthalpy_table_json）
- 与 P5-OPEN-006 §"9 旧标量"语义不对应，不属"旧轨"范畴
- 与 SUP-009 §3.1 §3.2 "新 40 字段"语义不对应，不属"新轨"范畴
- 保留 = 不删除、不重构、不审计退役

**SPEC V1.2 §4.1 9 JSONB（general/performance/heat_transfer/construction/tube_bundle/shell_internals/weights/material/connections）与现状 5 JSONB 语义不对应**：
- SPEC 9 JSONB = 设备物理属性（设计目标，P5+ 未来模型）
- 现状 5 JSONB = 输入输出快照（P4 临时实现）

**P5+ backlog**：若 P5-4 HEAT 服务层实施时需要 SPEC 9 JSONB，P5-4 内按需补全（届时有明确业务场景与数据源）。Task 2 不预先补，避免空壳字段。

---

## 决策 5：42 新字段 = 39 标量新 + 3 JSONB（SUP-009 §3.1 权威，duty 与 9 旧共享）

按 SUP-009 V1.0 §3.1（与 P5-OPEN-005 §P5-OPEN-006 引用一致）：

**40 标量**（FLOAT / INT / VARCHAR，按 §3.1.1-3.1.6 分组）：

| 组 | 字段数 | 字段 |
|---|---|---|
| 基础标识（§3.1.1） | 7 | exchanger_type, orientation, units_series, units_parallel, shells_per_unit, total_area_gross, total_area_eff |
| 通用热工性能（§3.1.2） | 9 | duty, lmtd, mtd_corrected, emtd, overdesign_percent, u_service, u_calculated, u_clean, heat_exchange_area |
| 通用几何（§3.1.4） | 9 | tube_count, tube_od, tube_id, tube_wall_thickness, tube_length, tube_pitch, tube_layout, tube_material, tube_passes |
| 壳程几何（§3.1.5） | 10 | shell_id, shell_design_pressure, shell_design_temp, baffle_type, baffle_cut_percent, baffle_spacing, baffle_inlet_spacing, seal_strip_count, passlane_seal_rod_count, impingement_plate |
| 热阻分布（§3.1.6） | 5 | thermal_resistance_shell, thermal_resistance_tube, thermal_resistance_fouling, thermal_resistance_metal, thermal_resistance_bond |
| **小计** | **40** | — |

**`duty` 共享 9 旧**：SUP-009 §3.1.2 `duty` 字段与 P5-OPEN-006 9 旧 `duty` 同名同义（FLOAT kW），合并为 1 列（用 9 旧名 `duty`）。新标量 40 - 1（共享）= **39 新标量** + 3 JSONB = **42 新字段**。

> **P5-4 跟踪项（已闭环 2026-09-18）**：SUP-009 `duty`（P5 计算结果）与 9 旧 `duty`（P4 上游值）业务语义有差异。P5-0 简化裁定"共享 1 列"，P5-4 实施时按需拆分为 `duty_legacy`（9 旧）/ `duty_calc`（新）双字段 — 2026-09-18 已通过 `p5_4_heat_duty_split` 迁移落地，详本 ADR 顶部修订段。

**3 JSONB**：
- `shell_params`（§3.1.3）：壳程工艺物性（fluid_name / mass_flow / temp_in/out / density_in/out / viscosity_in/out / cp_in/out / k_in/out / pressure_in / pressure_drop_calc / pressure_drop_allow / velocity / film_coef / fouling_res / design_pressure / design_temp / passes / flow_direction）
- `tube_params`（§3.1.3）：管程工艺物性（同 shell_params 结构）
- `ache_params`（§3.1.7）：空冷器专属（fans / airside / fin / nozzle / airside_resistance_distribution 五大子结构）

---

## 决策 6：record_hash 排除旧 9 标量（防数据漂移）

**问题**：旧 9 标量 + 现状 5 JSONB + 新 40 字段同表，compute_record_hash（`app/services/calc_lineage.py`）会哈希全部列。

**风险**：旧 9 标量在 P4 数据中可能有未对齐历史值（如 equipment_no 为 NULL 但 effective_area 已有值），新写入时 hash 因 NULL 变化漂移。

**裁定**：
1. record_hash 暂**包含全部业务列**（与 P5-OPEN-005 一致）
2. **P5-4 业务实现时**评估是否对旧 9 标量应用 `_round_sig` 后再哈希
3. **不进 P5-0 scope**：避免 P5-0 批范围膨胀

> 此条目记为 ADR-0027 后续跟踪项（"P5-4 hash 漂移评估"），由 P5-4 启动时复查。

---

## 决策影响段（与 ADR-0028 V1.1 交叉引用）

- **ADR-0028 V1.1 影响段**："P5-0-2 完成后追加 heat_results" 表述作废（用户 2026-09-16 裁决 Q4）。修订为"P5-0-2 同时扩字段 + 补 HeatResult 到 REGISTRY，9 → 10"
- **DICT-ALL-003 V3.7 §3.1**：HEAT 字段映射同步（37 + 3 + 9 = 49 业务字段对齐 DICT）
- **DICT-ALL-003 V3.4 §4.1**：PK rename 方向（heat_exchanger_id → heat_calc_id）纳入 Task 4a 后续 sprint

---

## 版本历史

| 版本 | 日期 | 修改内容 |
|---|---|---|
| V1.0 | 2026-09-17 | 初始版本：Task 2 P5-0-2 实施依据（6 项裁决） |
| V1.0-rev | 2026-09-18 | 决策 5 跟踪项闭环：duty 双轨字段已就位（p5_4_heat_duty_split 迁移），status → accepted |
