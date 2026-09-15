# P5 设备计算模块（第二批）实施计划 V1.0

> **执行方式**：superpowers TDD（每 task：RED → GREEN → commit）；subagent-driven-development 派新 agent。
> **基线 spec**：`spec/工艺专用综合计算软件需求规格说明书 Web版 P5.md`（V1.3，2026-09-03）
> **P4 依赖**：FLASH / PIPE / PUMP / PIPE_NET 已闭环（pcs_test 1603 passed / ruff 0）
> **TODOS 关联**：026 / 028 / 034 / 035 / 036 / 037
> **关联 spec**：SUP-008 V1.1 / SUP-009 V1.0 / SUP-010 V1.1 / SUP-007 / ADR-0022 / ADR-0027（待建）
> **BACKLOG 来源**：P4 验收报告 §六（Hooper 2-K / ChEDL 版本锁定 / Beggs-Brill / P4-2-6 等不进 P5，P5+）

**Goal**：交付 VESSEL / SEP_EQUIP / PSV / HEAT 四模块 + 数据模型扩展（P5-OPEN-005/006 + TODO-026/028/036），覆盖工艺室分离设备 + 安全阀 + 换热器三大类设备计算。

**Architecture**：自研算法（Souders-Brown / Lapple / Stokes / API 520/521/526 / API 2000） + 复用 P4 出口物流 helper（ADR-0022） + HTRI 自研解析器；结果入 P0 已建表 + P5-OPEN-005 扩展；多泄放工况叠加 + 两相流 FLASH 联动；记录走 record_hash + DataLineage（公式版本入 lineage，P4-TASK0 D4/D5 已备）。

**Tech**：FastAPI + SQLAlchemy 2.0 async + PG16 + fluids(vendored) + numpy.float64 + scipy

## 全局约束

- **数据门禁**：9 态（批 1 SUP-007 已落地）+ record_hash 无 version 字段 + 弃用操作（位号终身锁定）
- **公式版本**：每次计算写 `formula_version` 入 DataLineage（spec §2.5 + P4-TASK0 D4）
- **浮点**：numpy.float64（spec §2.5）
- **多泄放叠加**：PSV 多工况 → 取最大（spec §3.2.3）
- **两相流**：FLASH 联动（spec §3.2.3 + P5-OPEN-005 两相表扩展）
- **空冷器 ACHE**：HEAT 字段 + ache_params JSONB（spec §3.2.4 + SUP-009 §3.1）
- **HEAT 出口物流**：HEAT_EXCHANGE 独立物流链（ADR-0022，spec V1.2）
- **精度护栏**：沿用 P4 链式 worst-wins confidence（VESSEL/SEP_EQUIP/PSV 多步链需继承）
- **ruff 0 errors**；**测试基线 ≥1588 passed**（P4 末态 1603，扣除可能的跨批变更）
- **DETAIL/BASIC 双阶段设计**：design_stage 下沉自 P4-OPEN-009（VESSEL/PSV/COLUMN 加列，spec §4.3 OPEN-005）

## 任务清单（23 task）

### 批 P5-0 — 数据模型层（4 task，前置）

#### Task 1: P5-0-1 P5-OPEN-005 模型扩展（relief_results + column_sizing + mixer_results + 4 蒸汽表 + design_stage）

**Files**:
- Create: `alembic/versions/p5_open_005_model_extension.py`
- Modify: `app/models/calc.py`（新增 4 表 ORM + 现有表加 design_stage 列）
- Test: `tests/models/test_p5_model_extension.py`

**接口**:
- Produces: `relief_results` / `column_sizing_results` / `mixer_results` / `steam_drum_results` / `two_phase_pipe_sizing_results` / `blowdown_drum_results` / `thermosiphon_circulation_results` 7 表 ORM；`vessel_results.design_stage` / `psv_results.design_stage` / `column_sizing_results.design_stage` 三列（BASIC/DETAIL）

**Steps**:
1. RED: 写 7 表 ORM 存在性 + design_stage 列存在性 + alembic 迁移 head 跑通测试
2. GREEN: 按 SUP-008 V1.1 §2.2-§2.6 + §8.4 + SUP-010 V1.1 §3.1 建表；design_stage 加列（BASIC/DETAIL 枚举）
3. 测试：DICT V3.7/V3.9 字段对齐；alembic upgrade head OK；列存在性
4. commit: `feat(p5-0-1): model extension (7 tables + design_stage)`

#### Task 2: P5-0-2 P5-OPEN-006 HEAT 旧字段清洗 + ADR-0027

**Files**:
- Create: `docs/adr/0027-heat-results-dual-track.md`
- Modify: `app/models/calc.py`（heat_results 9 旧字段保留 + 39 新字段扩展）
- Test: `tests/models/test_heat_results_dual_track.py`

**接口**:
- Produces: `heat_results` 表 48 列（9 旧 + 39 新，向后兼容）；ADR-0027 落地

**Steps**:
1. RED: 写 dual-track 兼容性测试（旧字段保留 + 新字段可用 + DICT V3.7 字段对齐）
2. GREEN: SUP-009 §3.1 字段落地；ADR-0027 写双轨设计裁决（旧字段审计 + 新字段扩展）
3. 测试：字段完整性 + 旧数据兼容
4. commit: `feat(p5-0-2): heat_results dual-track + ADR-0027`

#### Task 3: P5-0-3 TODO-036 StreamSignStatus 9 态扩展

**Files**:
- Create: `alembic/versions/p5_sign_status_9states.py`
- Modify: `app/models/enums.py`（sign_status 枚举值扩展）
- Test: `tests/models/test_sign_status_9states.py`

**接口**:
- Produces: `streamsignstatus` PG enum 4→9 态（DRAFT/IN_APPROVAL/CHECKED/CHECK_REJECTED/STALE/CHANGE_PENDING/CHANGED/REVERSAL_PENDING/OBSOLETE）

**Steps**:
1. RED: 写 9 态枚举值存在性测试（迁移前 FAIL，迁移后 PASS）
2. GREEN: 备份 enum definition → `ALTER TYPE ... ADD VALUE 'STALE' ...` 等 5 新值；ORM 枚举同步
3. 测试：旧 4 态写入兼容 + 9 态全列读回
5. commit: `feat(p5-0-3): StreamSignStatus 9-state extension`

**约束**：`ALTER TYPE ... ADD VALUE` 不可逆 → migration 必须独立 + 备份（spec §P5-OPEN-010）

#### Task 4: P5-0-4 TODO-026 + TODO-028 字段平铺 + 主键 rename

**Files**:
- Create: `alembic/versions/p5_pk_rename_and_flatten.py`
- Modify: `app/models/calc.py`（vessel_results/heat_results/cv_results/pipe_network_results/restriction_results/flare_system_results/cooling_tower_results/sep_equip_results/filtration_results/open_channel_results 10 表主键 rename + vessel_results/sep_equip_results/heat_results 等 P5 模块平铺字段）
- Test: `tests/models/test_p5_pk_flatten.py`

**接口**:
- Produces: 10 表主键 rename（vessel_id→vessel_calc_id / heat_exchanger_id→heat_calc_id 等 DICT V3.3 §4.1）；P5 模块字段平铺或 `*_json` 子结构

**Steps**:
1. RED: 主键 rename 后 ORM 字段名匹配测试 + P5 模块平铺字段或 data_sheet_json 写入读出测试
2. GREEN: rename 主键 + SUP-001~014 字段平铺；旧 FK 同步 rename
3. 测试：rename 全覆盖 + 平铺字段与 DICT V3.3 对齐
4. commit: `feat(p5-0-4): PK rename + flatten per DICT V3.3`

### 批 P5-1 — VESSEL 容器计算（4 task）

#### Task 5: P5-1-1 vessel_service 核心（Souders-Brown + D_min + 停留时间）

**Files**:
- Create: `app/services/vessel/vessel_service.py`
- Create: `tests/services/vessel/test_vessel_sizing.py`
- Create: `tests/services/vessel/fixtures/golden_vessel_souders_brown.json`

**接口**:
- Consumes: `CONFIG.K_factor_vertical_separator`（P2 配）+ `rho_L` / `rho_V`（FLASH 物流）
- Produces: `calc_vessel_sizing(inp: VesselSizingInput) -> VesselSizingResult`（vessel_type / D_min_m / liquid_volume_m3 / V_max_ms / K_factor）

**Steps**:
1. RED: 写 Souders-Brown 公式手算对照（K=0.1, ρ_L=850, ρ_V=1.2 → V_max=2.64 m/s）+ D_min 公式 + 停留时间 3~5 分钟
2. GREEN: 自实现算法（不依赖 fluids.tanks 核心公式）+ K 因子从 CONFIG 读 + 容器类型分支（立式/卧式/带除沫器）
3. 测试：6 例（4 容器类型 × 卧式/立式）+ K 因子边界 0.03/0.15/0.35 + 验收 ≤1% 偏差
4. commit: `feat(p5-1-1): vessel Souders-Brown sizing`

#### Task 6: P5-1-2 vessel 流体力学校核（fluids.tanks 排空/溢流/液位-容积/放空）

**Files**:
- Modify: `app/services/vessel/vessel_service.py`（加 hydraulics 子函数）
- Create: `tests/services/vessel/test_vessel_hydraulics.py`

**接口**:
- Produces: `calc_vessel_hydraulics(inp: VesselHydraulicsInput) -> VesselHydraulicsResult`（empty_time_s / overflow_ok / level_volume_curve_json / vent_capacity_m3_s）

**Steps**:
1. RED: 写排空时间手算 + 卧式罐液位-容积曲线几何公式
2. GREEN: 调 `fluids.tanks.time_to_empty` / `tank_level_to_volume`；溢流口校核（Q_in vs 溢流能力）；放空能力（呼吸量 PVRV 参考）
3. 测试：4 例（排空/溢流/液位-容积/放空）+ 验收 ≤5% 偏差
4. commit: `feat(p5-1-2): vessel hydraulics (fluids.tanks)`

#### Task 7: P5-1-3 vessel 复用推荐（EQUIP_LIB 匹配）

**Files**:
- Modify: `app/services/vessel/vessel_service.py`（加 recommend）
- Create: `app/services/vessel/recommend_service.py`（按 EQUIP_LIB 相似度匹配）
- Create: `tests/services/vessel/test_vessel_recommend.py`

**接口**:
- Produces: `recommend_vessels(vessel_calc_id) -> list[VesselRecommendEntry]`（equipment_no / K_factor / D_min / similarity_pct）

**Steps**:
1. RED: 写 EQUIP_LIB 匹配测试（接口尺寸 + 容器类型 + 工作压力量级）
2. GREEN: 按 EQUIP_LIB.service 接口匹配；相似度排序；上限 10 条
3. 测试：3 例（精确匹配 / 相似 / 不匹配空集）
4. commit: `feat(p5-1-3): vessel EQUIP_LIB recommend`

#### Task 8: P5-1-4 vessel API + 落库 + outlet_stream

**Files**:
- Create: `app/services/vessel/vessel_persist.py`
- Create: `app/api/v1/vessel.py`
- Create: `tests/services/vessel/test_vessel_persist.py`
- Create: `tests/api/v1/test_vessel.py`

**接口**:
- Produces: `POST /api/v1/vessel/calculate` + `GET /api/v1/vessel/{vessel_id}/recommend`
- 落库: `vessel_results` 单行（input_json/output_json + record_hash + lineage）+ outlet_stream(source_type=VESSEL)

**Steps**:
1. RED: 写 API + persist roundtrip + outlet_stream 写出测试
2. GREEN: finalize_calc_record 收口 + create_outlet_stream(source_type="VESSEL") 扩展（P4 outlet_stream Literal 加 "VESSEL"）
3. 测试：端点 + 三步守卫 + ACL + 13 字段 roundtrip
4. commit: `feat(p5-1-4): vessel API + persist + outlet_stream`

### 批 P5-2 — SEP_EQUIP 气固/气液分离设备（4 task）

#### Task 9: P5-2-1 旋风分离器（Lapple/Swift/Barth 三方法）

**Files**:
- Create: `app/services/sep_equip/cyclone_service.py`
- Create: `tests/services/sep_equip/test_cyclone.py`
- Create: `tests/services/sep_equip/fixtures/golden_cyclone_lapple.json`

**接口**:
- Produces: `calc_cyclone(inp: CycloneInput) -> CycloneResult`（D_cylinder_m / inlet_width_m / inlet_height_m / pressure_drop_pa / efficiency_pct / method: Literal["Lapple","Swift","Barth"]）

**Steps**:
1. RED: 写 Lapple 手算（d=0.5m, v_in=15m/s, ρ=1.2 → ΔP=750 Pa）+ Barth 效率公式
2. GREEN: 默认 Lapple（P5-OPEN-002 已确认）；Swift/Barth 作为可选 method 参数
3. 测试：3 方法各 1 例 + 验收 ≤10% 压降偏差
4. commit: `feat(p5-2-1): cyclone (Lapple/Swift/Barth)`

#### Task 10: P5-2-2 丝网除沫器（York + Souders-Brown）

**Files**:
- Create: `app/services/sep_equip/mist_eliminator_service.py`
- Create: `tests/services/sep_equip/test_mist_eliminator.py`

**接口**:
- Produces: `calc_mist_eliminator(inp: MistEliminatorInput) -> MistEliminatorResult`（pad_area_m2 / thickness_mm / pressure_drop_pa）

**Steps**:
1. RED: 写 York 法手算 + Souders-Brown K 取值（带除沫器取更高 K）
2. GREEN: York 公式 + 压降校核
3. 测试：2 例（标准/带除沫器 K）
4. commit: `feat(p5-2-2): mist eliminator (York)`

#### Task 11: P5-2-3 重力沉降器（Stokes）+ 叶片/纤维

**Files**:
- Create: `app/services/sep_equip/gravity_separator_service.py`
- Create: `tests/services/sep_equip/test_gravity_separator.py`

**接口**:
- Produces: `calc_gravity_separator(inp: GravitySeparatorInput) -> GravitySeparatorResult`（chamber_length_m / chamber_width_m / settling_velocity_ms）

**Steps**:
1. RED: 写 Stokes 沉降手算（d=100μm, ρ_p=1100, μ=1.8e-5 → v_t=0.0074 m/s）+ 终端速度三区判定（Re<1 Stokes / Re=1-1000 Intermediate / Re>1000 Newton）
2. GREEN: 调 `fluids.particle_size.v_sphere`；叶片/纤维用经验法（spec §3.2.2）
3. 测试：Stokes ≤1% 偏差 + 三区判定 + 粒径分布拟合 ≤5% 偏差
4. commit: `feat(p5-2-3): gravity separator (Stokes) + vane/fiber`

#### Task 12: P5-2-4 sep_equip API + 落库

**Files**:
- Create: `app/services/sep_equip/sep_equip_persist.py`
- Create: `app/api/v1/sep_equip.py`
- Create: `tests/services/sep_equip/test_sep_equip_persist.py`
- Create: `tests/api/v1/test_sep_equip.py`

**接口**:
- Produces: `POST /api/v1/sep-equip/calculate`（设备类型 Literal["CYCLONE","MIST_ELIMINATOR","GRAVITY","VANE","FIBER"]）
- 落库: `sep_equip_results` 单行 + outlet_stream(source_type=SEP_EQUIP)

**Steps**:
1. RED: 端点 + 5 类型分发 + persist roundtrip
2. GREEN: finalize_calc_record + create_outlet_stream 扩展 "SEP_EQUIP"
3. 测试：5 类型各 1 例 + 13 字段 roundtrip + ACL + 三步守卫
4. commit: `feat(p5-2-4): sep_equip API + persist + outlet_stream`

### 批 P5-3 — PSV 安全阀（6 task）

#### Task 13: P5-3-1 PSV 火灾工况（API 521）

**Files**:
- Create: `app/services/psv/fire_case_service.py`
- Create: `tests/services/psv/test_fire_case.py`

**接口**:
- Produces: `calc_fire_case(inp: FireCaseInput) -> FireCaseResult`（wetted_area_m2 / heat_input_w / relief_mass_flow_kgs / relief_volume_flow_m3s）

**Steps**:
1. RED: 写 API 521 火灾工况手算（立式容器 d=3m h=10m → A_w=85m² → Q=850000W → W=12.5 kg/s）
2. GREEN: 润湿面积计算（绝热 vs 非绝热分支）+ 热输入量（环境因子 env_factor）
3. 测试：2 例（绝热/非绝热）+ ≤2% 偏差
4. commit: `feat(p5-3-1): PSV fire case (API 521)`

#### Task 14: P5-3-2 阀门关闭 + 反应失控 + 热膨胀

**Files**:
- Create: `app/services/psv/other_cases_service.py`
- Create: `tests/services/psv/test_other_cases.py`

**接口**:
- Produces: `calc_closed_valve_case(inp) -> ReliefResult` + `calc_reaction_runaway(inp) -> ReliefResult` + `calc_thermal_expansion(inp) -> ReliefResult`

**Steps**:
1. RED: 写 3 工况公式手算（closed_valve 流体膨胀 / reaction 泄放动力学 / thermal 液体膨胀系数）
2. GREEN: 各工况独立函数；公用 `ReliefResult` dataclass（mass_flow + volume_flow + scenario enum）
3. 测试：3 工况各 1 例
4. commit: `feat(p5-3-2): PSV other cases (closed/reaction/thermal)`

#### Task 15: P5-3-3 多工况叠加 + 最大泄放量

**Files**:
- Create: `app/services/psv/relief_aggregator_service.py`
- Create: `tests/services/psv/test_relief_aggregator.py`

**接口**:
- Produces: `aggregate_relief_cases(cases: list[ReliefResult]) -> ReliefAggregateResult`（max_mass_flow_kgs / max_scenario / per_scenario_json）

**Steps**:
1. RED: 写多工况叠加测试（3 工况 → max mass flow 取最大）
2. GREEN: 聚合函数 + spec §2.5 "多泄放工况叠加 ≤5s" 性能测试
3. 测试：4 工况叠加 + 空集异常
4. commit: `feat(p5-3-3): PSV multi-case aggregator`

#### Task 16: P5-3-4 PSV 泄放面积（气体/液体/两相流）

**Files**:
- Create: `app/services/psv/relief_area_service.py`
- Create: `tests/services/psv/test_relief_area.py`

**接口**:
- Produces: `calc_relief_area(inp: ReliefAreaInput) -> ReliefAreaResult`（area_m2 / medium: Literal["GAS","VAPOR","LIQUID","TWO_PHASE"] / formula_ref）

**Steps**:
1. RED: 写 3 介质公式手算（气体：A=W/(C×Kd×P1×Kb)×√(TZ/M) / 液体 API 520 / 两相 API 520 8th Ed. 附录 D）
2. GREEN: 介质分支 + 两相流 FLASH 联动（调 P4 flash_service 算 Z/M）；C/Kd/Kb 默认值表
3. 测试：3 介质各 1 例 + 两相流 ≤5% 偏差（vs HYSYS）
4. commit: `feat(p5-3-4): PSV relief area (gas/liquid/two-phase)`

#### Task 17: P5-3-5 API 526 选型 + API 2000 呼吸阀

**Files**:
- Create: `app/services/psv/orifice_service.py`（API 526 孔口圆整）
- Create: `app/services/psv/breathing_valve_service.py`（API 2000 呼吸阀）
- Create: `tests/services/psv/test_orifice.py`
- Create: `tests/services/psv/test_breathing_valve.py`

**接口**:
- Produces: `select_orifice(area_m2) -> OrificeResult`（API 526 标准孔口 D~T，圆整向上）+ `calc_breathing_valve(inp) -> BreathingValveResult`（thermal_inout_m3_s / working_inout_m3_s / total_m3_s）

**Steps**:
1. RED: 写 API 526 孔口表（D=0.110in² ... T=26.0in²）+ API 2000 第7版呼吸量（待 P5-OPEN-003 确认，默认第7版）
2. GREEN: 圆整函数 + 呼吸量（热呼吸 ΔT 引起 + 操作呼吸 进出料引起）
3. 测试：圆整向上 + 呼吸量 ≤2% 偏差
4. commit: `feat(p5-3-5): PSV orifice (API 526) + breathing (API 2000)`

#### Task 18: P5-3-6 PSV API + 落库 + outlet_stream

**Files**:
- Create: `app/services/psv/psv_persist.py`
- Create: `app/api/v1/psv.py`
- Create: `tests/services/psv/test_psv_persist.py`
- Create: `tests/api/v1/test_psv.py`

**接口**:
- Produces: `POST /api/v1/psv/calculate-relief` / `calculate-area` / `select-orifice`
- 落库: `psv_results` + `relief_results`（P5-OPEN-005 新表）+ outlet_stream(source_type=PSV)

**Steps**:
1. RED: 3 端点 + persist + 两表落库测试
2. GREEN: finalize_calc_record 双表 + create_outlet_stream 扩展 "PSV"
3. 测试：3 端点 + 双表 roundtrip + 多工况叠加 ≤5s 性能
4. commit: `feat(p5-3-6): PSV API + persist + outlet_stream`

### 批 P5-4 — HEAT 换热器（5 task）

#### Task 19: P5-4-1 HTRI 自研解析器

**Files**:
- Create: `app/services/heat/htri_parser.py`
- Create: `tests/services/heat/test_htri_parser.py`
- Create: `tests/services/heat/fixtures/htri_sample.txt`（自造测试样本）

**接口**:
- Produces: `parse_htri(path) -> HtriParsedData`（Q_w / U_w_m2k / area_m2 / shell_dia_m / tube_length_m / tube_count / baffle_spacing_m / ...）

**Steps**:
1. RED: 写解析手算样本（Q=1MW, U=500, A=10m²）+ 解析失败异常
2. GREEN: 自研解析（基于 HTRI 文本/CSV 输出格式；P5-OPEN-001 待确认兼容范围，按 P4-PUMP 模式先支持一个版本）
3. 测试：3 例（基本/管壳/空冷）+ 解析失败异常 + ≤10s 性能
4. commit: `feat(p5-4-1): HTRI parser`

**OPEN**：P5-OPEN-001（HTRI 版本兼容范围）默认按公司常用版本实施，扩展性预留 `version: str` 字段

#### Task 20: P5-4-2 heat_results 39 字段扩展

**Files**:
- Modify: `app/models/calc.py`（P5-0-2 已加列，本 task 落库实现）
- Create: `app/services/heat/heat_data_service.py`
- Create: `tests/services/heat/test_heat_data.py`

**接口**:
- Produces: `HeatResultsService` 写入 48 列（9 旧 + 39 新）+ 总参/壳程管程/传热/结构/管束/壳体/重量 7 大类平铺

**Steps**:
1. RED: 写 39 字段 roundtrip 测试（DICT V3.7 §3.1 对齐）
2. GREEN: 平铺字段写入 + SUP-009 §3.1 字段名映射
3. 测试：39 字段全覆盖 + 旧字段保留兼容
4. commit: `feat(p5-4-2): heat_results 39-field extension`

#### Task 21: P5-4-3 ACHE 空冷器（ache_params JSONB + 焓值表）

**Files**:
- Modify: `app/services/heat/heat_data_service.py`（加 ACHE 分支）
- Create: `tests/services/heat/test_ache.py`

**接口**:
- Produces: `save_ache_params(heat_id, params: AcheParams)` + 焓值表（多温度点物性）

**Steps**:
1. RED: 写 ACHE 字段 JSONB 写入读出 + 焓值表结构（P5-OPEN-004 已确认焓值表来自 Licensor）
2. GREEN: `ache_params` JSONB 列写入（fan_count/fan_power/bundle_area/air_inlet_temp/altitude/fin/tube_nozzle/air_side_resistance_dist）+ `enthalpy_table_json` 多温度点
3. 测试：ACHE 字段完整性 + 焓值表 ≥10 温度点
4. commit: `feat(p5-4-3): ACHE (ache_params + enthalpy table)`

#### Task 22: P5-4-4 重量估算（U型管/固定管板）

**Files**:
- Create: `app/services/heat/weight_estimate_service.py`
- Create: `tests/services/heat/test_weight_estimate.py`

**接口**:
- Produces: `estimate_weight(inp: WeightEstimateInput) -> WeightEstimateResult`（shell_weight_kg / tube_weight_kg / baffle_weight_kg / total_weight_kg / tema_type: Literal["BEM","AEM","..."]）

**Steps**:
1. RED: 写 U 型管手算（D_shell=1m, L=5m, n_tubes=200 → shell=2400kg, tube=1800kg, baffle=200kg）
2. GREEN: 公式基于壳径/管长/管数；TEMA 类型分支
3. 测试：2 例（BEM/AEM）+ ≤10% 偏差
4. commit: `feat(p5-4-4): weight estimate (U-tube/BEM)`

#### Task 23: P5-4-5 HEAT API + 落库 + outlet_stream（HEAT_EXCHANGE）

**Files**:
- Create: `app/services/heat/heat_persist.py`
- Create: `app/api/v1/heat.py`
- Create: `tests/services/heat/test_heat_persist.py`
- Create: `tests/api/v1/test_heat.py`

**接口**:
- Produces: `POST /api/v1/heat/import-htri` / `GET /heat/{heat_id}` / `POST /heat/{heat_id}/weight-estimate`
- 落库: `heat_results` 单行 + outlet_stream(source_type=HEAT, change_type=HEAT_EXCHANGE)

**Steps**:
1. RED: 3 端点 + 48 字段 roundtrip + outlet_stream HEAT_EXCHANGE 测试
2. GREEN: finalize_calc_record + create_outlet_stream 扩展 "HEAT" + HEAT_EXCHANGE change_type；物流号更换（spec V1.2 §3.2.4）
3. 测试：3 端点 + HEAT_EXCHANGE 出口物流独立编号 + ACL + 三步守卫
4. commit: `feat(p5-4-5): HEAT API + persist + outlet_stream`

## Self-Review

### 1. Spec 覆盖度

| Spec 段 | 覆盖 task |
|---|---|
| §2.2 VESSEL/SEP_EQUIP/PSV/HEAT 模块定位 | P5-1 / P5-2 / P5-3 / P5-4 全部 |
| §2.5 DataLineage 公式版本 | 全部 task 走 finalize_calc_record（P4-TASK0 D4/D5 已备） |
| §2.5 numpy.float64 | 全部 service 自实现 |
| §2.5 PSV 多泄放叠加 | P5-3-3 独立 task |
| §2.5 HEAT 管壳/空冷 | P5-4-2 + P5-4-3 |
| §2.5 EQUIP_LIB 复用 | P5-1-3 |
| §3.1.2 8 REST 端点 | P5-1-4（2）/ P5-2-4（1）/ P5-3-6（3）/ P5-4-5（2，实际含 weight-estimate 共 3）= 9 端点（weight-estimate 单独） |
| §3.2.1 VESSEL 4 计算类型 | P5-1-1 + P5-1-2 |
| §3.2.1 验收 ≤1% / ≤5% | P5-1-1/P5-1-2 测试 |
| §3.2.2 SEP_EQUIP 5 设备类型 | P5-2-1/2-2/2-3 |
| §3.2.2 验收 ≤1% / ≤5% / ≤10% | P5-2 测试 |
| §3.2.3 PSV 泄放工况 + 两相流 | P5-3-1/3-2/3-4 |
| §3.2.3 验收 ≤2% / ≤5% | P5-3 测试 |
| §3.2.3 API 526 + API 2000 | P5-3-5 |
| §3.2.4 HEAT HTRI + 39 字段 + ACHE + 重量 + 出口物流 | P5-4-1/4-2/4-3/4-4/4-5 |
| §3.2.4 验收 ≤10% 重量 | P5-4-4 |
| §3.3.1 性能预算 ≤2/2/2/5/10/1s | 各批性能测试 |
| §3.3.2 精度预算 1/1/2/2/5/10% | 各批 golden 测试 |
| §3.4 5 数据表（含 P5-OPEN-005 扩展 7 表） | P5-0-1 + P5-0-2 |
| §4.3 P5-OPEN-005 数据扩展 | P5-0-1 |
| §4.3 P5-OPEN-006 HEAT 旧字段清洗 | P5-0-2 |
| §4.3 P5-OPEN-001 HTRI 版本 | P5-4-1 留 version 字段 |
| §4.3 P5-OPEN-002 Lapple 默认 | P5-2-1 默认 Lapple |
| §4.3 P5-OPEN-003 API 2000 v7 | P5-3-5 默认 v7 |
| §4.3 P5-OPEN-004 焓值来自 Licensor | P5-4-3 焓值表契约 |

**覆盖完整性**：spec §2~§4 全部覆盖。

### 2. Placeholder 扫描

- 无 "TBD" / "TODO"（除引用 TODOS.md）
- 无 "implement later"
- 无 "Similar to Task N"
- 每 task 含 Files + 接口 + Steps + 测试要点

### 3. 类型一致性

- `outlet_stream.source_type` Literal 在 P4-3-3 已扩 ["FLASH","PIPE","PUMP","PIPE_NET"]；P5 需扩 ["VESSEL","SEP_EQUIP","PSV","HEAT"]（P5-1-4 / P5-2-4 / P5-3-6 / P5-4-5 同步扩展；建议先在 P5-1-4 一次性扩展，后续 task 复用）
- `finalize_calc_record` P4-TASK0 已扩展 5 类 → P5 需登记新表（vessel_results/sep_equip_results/psv_results/relief_results/heat_results 等；RECORD_TYPE_REGISTRY 在 P5-0-1/0-2 完成后追加）
- `calc_entry.check_calc_inputs` 三步守卫 P4-0-3 已备 → P5 API 复用

### 4. 风险与 OPEN

- **OPEN-001 HTRI 版本兼容**：默认 v1 解析，扩展性预留 `htri_version` 字段；后续按 sample 扩展
- **OPEN-003 API 2000 v7**：默认 v7，验证集如发现偏差回退 v6
- **ALTER TYPE 9 态**：P5-0-3 必须独立 migration + 备份（不可逆）
- **HTRI 解析器自研**：基于文本/CSV 自研，P5-OPEN-001 待确认范围；风险中等
- **EQUIP_LIB 复用推荐**：依赖 EQUIP_LIB service 已落地（P2/P3）
- **两相流 FLASH 联动**：P5-3-4 调 P4 flash_service（已闭环），无新增依赖

## 裁决记录

- 批 P5-0 必须先闭环（P5-1~P5-4 依赖 ORM 列 + 9 态 + DICT V3.3 rename）
- outlet_stream Literal 在 P5-1-4 一次性扩展为 ["FLASH","PIPE","PUMP","PIPE_NET","VESSEL","SEP_EQUIP","PSV","HEAT"]
- RECORD_TYPE_REGISTRY 在 P5-0-2 完成后追加 7 类（含 vessel/sep_equip/psv/relief/heat + 设计阶段 design_stage）
- 5 个 P5 服务互不依赖（VESSEL → FLASH 物流 → ρ_L/ρ_V；PSV → FLASH 物流 → Z/M；HEAT → EQUIP_LIB；SEP_EQUIP → 颗粒 Stokes 独立）
- 性能预算 ≤2/2/2/5/10/1s 与精度 ≤1/1/2/2/5/10% 由各批性能 + golden 测试覆盖
- 任务粒度与 P4 主体一致（一批一 commit 模式 → P5 同样）

## Backlog（P5+ 后续）

- Hooper 2-K / Darby 3-K 低 Re K 值修正（P4 转入）
- ChEDL 版本锁定 ADR
- `fluids.two_phase` Beggs-Brill 交叉校核
- `fluids.fittings` K_from_f 交叉校核
- P4-2-6 热损失 + 混合黏度
- CIA 引擎（hash_changed / changed_fields / STALE→CHANGE_PENDING）
- 控制阀 / PSV（V1.3 §1.2 不在 P5，P6+）
- P6（CV/RESTRICTION/FLARE_SYS/COOL_TOWER/PSYCHRO/OPEN_CHANNEL）规划另起

## 验收

P5 闭环判定：
1. 23 task 全部 CLOSED（含 R1 fix 如有）
2. pcs_test 全量 ≥1650 passed（基线 1603 + 47+ 新测试）
3. ruff 0 errors
4. spec §3.2.1~§3.2.4 全部功能 + §3.3.1 性能 + §3.3.2 精度 验收通过
5. P5-OPEN-001/003 实测数据已附（HTRI v1 解析正确 + API 2000 v7 偏差 ≤2%）
6. P5 验收报告（PCS-P5-CLOSE-REPORT.md）落盘