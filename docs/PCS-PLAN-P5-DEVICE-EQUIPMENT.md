# P5 设备计算模块（第二批）实施计划 V1.5

> **执行方式**：superpowers TDD（每 task：RED → GREEN → commit）；subagent-driven-development 派新 agent。
> **基线 spec**：
> - `spec/工艺专用综合计算软件需求规格说明书 Web版 P5.md`（V1.3，2026-09-03）
> - `spec/工艺专用综合计算软件需求规格说明书 Web版开发计划.md`（V1.3，2026-09-06）§P5 周期 12–16 周
> - `spec/SUP-P5-PSV-001 PSV 多标准.md`（V1.0，2026-09-15，已批准，E-01）— PSV 计算标准 API/GB 项目级配置
> **P4 依赖**：FLASH / PIPE / PUMP / PIPE_NET 已闭环（pcs_test 1603 passed / ruff 0）
> **TODOS 关联**：026 / 028 / 034 / 035 / 036 / 037 + SUP-PSV-001 TODO-PSV-STD-001（PSV 多标准）
> **关联 spec**：SUP-008 V1.1 / SUP-009 V1.0 / SUP-010 V1.1 / SUP-007 / SUP-P5-PSV-001 / ADR-0022 / ADR-0027（P5-0-2 落地）/ ADR-0028（PSV 多标准引擎，Task 24 起草 Proposed，与 SUP 同步评审）/ ADR-0029（ChEDL 版本锁定，Task 25 起草，D-08 新建）
> **P5 阶段验收（开发计划 §关键里程碑）**：各设备计算与手算/商业软件偏差在 SPEC 要求范围内（≤1/1/2/2/5/10%）
> **P5 后续衔接（开发计划 §依赖图）**：PSV → P6 FLARE_SYS（泄放量汇总接口预留 + 按标准口径汇总 SUP-P5-PSV-001 §5.4） + HEAT → P7 UTIL（热负荷汇总接口预留）
> **BACKLOG 来源**：P4 验收报告 §六（Hooper 2-K / Beggs-Brill / P4-2-6 等不进 P5，P5+）

**Goal**：交付 VESSEL / SEP_EQUIP / PSV / HEAT 四模块 + 数据模型扩展（P5-OPEN-005/006 + TODO-026/028/036）+ PSV 多标准引擎（SUP-P5-PSV-001 + ADR-0028）+ ChEDL 版本锁定（ADR-0029），覆盖工艺室分离设备 + 安全阀 + 换热器三大类设备计算。

**Architecture**：底层 **ChEDL 验证模块**（`fluids.separator.v_Souders_Brown` / `K_separator_Watkins` / `K_separator_demister_York` / `fluids.particle_size.v_sphere` Stokes 三区迭代 / `fluids.safety_valve.API520_round_size` 仅复用圆整）+ **业务逻辑层自研**（API 521 火灾热输入 / API 2000 呼吸阀 / HTRI 解析器 / EQUIP_LIB 复用推荐 / PSV 多工况聚合 / 反应失控 / 热膨胀）+ P4 出口物流 helper（ADR-0022）；结果入 P0 已建表 + P5-OPEN-005 扩展；多泄放工况叠加 + 两相流 FLASH 联动；记录走 record_hash + DataLineage（公式版本入 lineage，P4-TASK0 D4/D5 已备；裁决 #8 ChEDL 分层架构）。

**Tech**：FastAPI + SQLAlchemy 2.0 async + PG16 + fluids(vendored, ADR-0029 锁定版本) + numpy.float64 + scipy

## 全局约束

- **数据门禁**：9 态（批 1 SUP-007 已落地）+ record_hash 无 version 字段 + 弃用操作（位号终身锁定）
- **公式版本**：每次计算写 `formula_version` 入 DataLineage（spec §2.5 + P4-TASK0 D4）；formula_ref 结构化字段 `{standard, version, clause}`（F-09，与 standard_refs_json 一致）
- **浮点**：numpy.float64（spec §2.5）
- **多泄放叠加**：PSV 多工况 → 取最大（spec §3.2.3）
- **两相流**：FLASH 联动（spec §3.2.3 + P5-OPEN-005 两相表扩展；GB 路径 DIERS 暂缺，Task 16 标记 P5+）
- **空冷器 ACHE**：HEAT 字段 + ache_params JSONB（spec §3.2.4 + SUP-009 §3.1）
- **HEAT 出口物流**：HEAT_EXCHANGE 独立物流链（ADR-0022，spec V1.2）
- **精度护栏**：沿用 P4 链式 worst-wins confidence（VESSEL/SEP_EQUIP/PSV 多步链需继承）
- **K 因子 SI 单位制**（D-01）：立式 0.04–0.10 / 卧式 0.07–0.15 / 带除沫器取上限；CONFIG 种子以 SI 存储，spec §3.2.1 同步修订
- **PSV 标准强制配置**（D-02）：项目未配置 → 422 `PSV_STANDARD_NOT_CONFIGURED`，禁止隐式回退；新建项目向导引导 PSV 标准配置（前端实现，后端仅提供配置端点）
- **GB/T 150.1 版本策略**（D-03）：项目级锁定，新项目默认 2024，历史项目迁移保持原版本（2011）+ `migrated_default=true` 标记
- **GB/T 12241 孔口表降级**（D-04）：P5 输出所需流道直径不强制圆整；formula_ref 标注 `orifice_table_status: "incomplete_fallback"`；完整录入转 P5+
- **ruff 0 errors**；**起始基线 ≥1603 passed**（P4 末态）；**P5 验收 ≥1670 passed**（基线 + 47 P5 核心 + 15 SUP 门禁 + 5 ChEDL 版本锁定，F-04 + E-02 + D-08）
- **ChEDL 版本锁定**（D-08）：Task 25 (P5-0-6) + ADR-0029；fluids / chemicals / ht 冻结至 requirements.txt；P5-0 批内完成，P5-1 启动前生效
- **DETAIL/BASIC 双阶段设计**：design_stage 下沉自 P4-OPEN-009（VESSEL/PSV/COLUMN 加列，spec §4.3 OPEN-005）

## 任务清单（25 task；Task 24/25 为 P5-0-5/P5-0-6 前置执行）

### 批 P5-0 — 数据模型层（6 task：Task 1~4 主 + Task 24/25 前置，全部批内执行）

#### Task 1: P5-0-1 P5-OPEN-005 模型扩展（relief_results + column_sizing + mixer_results + 4 蒸汽表 + design_stage）

**Files**:
- Create: `alembic/versions/p5_open_005_model_extension.py`
- Modify: `app/models/calc.py`（新增 4 表 ORM + 现有表加 design_stage 列）
- Test: `tests/models/test_p5_model_extension.py`

**接口**:
- Produces: `relief_results` / `column_sizing_results` / `mixer_results` / `steam_drum_results` / `two_phase_pipe_sizing_results` / `blowdown_drum_results` / `thermosiphon_circulation_results` 7 表 ORM；`vessel_results.design_stage` / `psv_results.design_stage` / `column_sizing_results.design_stage` 三列（BASIC/DETAIL）
- **RECORD_TYPE_REGISTRY 即时注册**（裁决 #11 时机修正）：P5-0-1 完成后立即在 `app/services/calc_lineage.py` 注册 7 表 + 现有 5 表 = **12 类**；新增测试断言 registry 完整性（防止 Task 4 主键 rename 后落库验证空跑）

**Steps**:
1. RED: 写 7 表 ORM 存在性 + design_stage 列存在性 + alembic 迁移 head 跑通测试 + **RECORD_TYPE_REGISTRY 12 类注册断言**
2. GREEN: 按 SUP-008 V1.1 §2.2-§2.6 + §8.4 + SUP-010 V1.1 §3.1 建表；design_stage 加列（BASIC/DETAIL 枚举）；calc_lineage.RECORD_TYPE_REGISTRY 同步追加
3. 测试：DICT V3.7/V3.9 字段对齐；alembic upgrade head OK；列存在性；registry 完整性
4. commit: `feat(p5-0-1): model extension (7 tables + design_stage + registry 12 类)`

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
1. RED: 写 Souders-Brown 公式手算对照（K=0.1 m/s, ρ_L=850 kg/m³, ρ_V=1.2 kg/m³ → V_max=0.1×√((850-1.2)/1.2)=0.1×√707.33=**2.66 m/s**）+ D_min 公式 + 停留时间 3~5 分钟 + 与 ChEDL `fluids.separator.v_Souders_Brown(K, rhol, rhog)` 交叉验证
2. GREEN: **ChEDL 分层架构**（裁决 #8）—— 直接调 `fluids.separator.v_Souders_Brown` / `K_separator_Watkins` / `K_separator_demister_York` / `K_Souders_Brown_theoretical`，不重写核心公式；自研仅做 K 因子 CONFIG 读取 + 容器类型分支（立式/卧式/带除沫器）+ D_min / 停留时间
3. 测试：6 例（4 容器类型 × 卧式/立式）+ K 因子边界 0.04/0.10/0.15 + **单位约定**（K 取 SI m/s，与 ChEDL 一致）+ 与手算 + ChEDL 交叉验证偏差 ≤1%
4. commit: `feat(p5-1-1): vessel Souders-Brown sizing (ChEDL 底层)`

**注**：spec §3.2.1 K 因子取值"立式 0.03~0.15 / 卧式 0.15~0.35"——其中 0.35 是英制 GPSA ft/s 单位下的值（0.35 ft/s ≈ 0.107 m/s），按 SI 应为 0.04–0.10（立式）/ 0.07–0.15（卧式）。**待 spec 修订裁决 SI vs 英制**；本 task 实施按 SI（m/s）+ GPSA SI 换算取值，spec 修订裁决后调整 CONFIG 种子数据。

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
1. RED: 写 Lapple 公式（ΔP_c = C_f × ρ/2 × V_in²，C_f = 16·a·b / D_e²）手算（d=0.5m, a=0.2m, b=0.1m, V_in=15m/s, ρ=1.2 → C_f=64·0.02/0.5²=5.12 → ΔP=5.12×0.6×225=691 Pa）+ Barth 压降模型（出口管旋流速度头 + 壁面摩擦 + 出口管损失）+ 偏差基准数据集（GPSA Engineering Data Book §Cyclone Separators 算例 + 文献 Stairmand 高效旋风分离器标准数据）
2. GREEN: 默认 Lapple（P5-OPEN-002 已确认）；Swift/Barth 作为可选 method 参数；自研三方法实现（**fpi 模块成熟度低，活跃更新停滞 8 年，不依赖**——ChEDL 不建议复用）
3. 测试：3 方法各 2 例（标准/高效旋风）+ **分阈值偏差基准**（Lapple ≤15% GPSA 算例 / Swift ≤10% / Barth ≤8% ——简化方法偏差预期高于 Barth）
4. commit: `feat(p5-2-1): cyclone (Lapple/Swift/Barth + GPSA 基准)`

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
- Produces: `calc_gravity_separator(inp: GravitySeparatorInput) -> GravitySeparatorResult`（chamber_length_m / chamber_width_m / settling_velocity_ms / method_region: Literal["Stokes","Intermediate","Newton"] / re_particle）

**Steps**:
1. RED: 写 Stokes 沉降手算（d=100μm, ρ_p=1100 kg/m³, μ=1.8e-5 Pa·s → v_t=g·(ρ_p-ρ_f)·d²/(18μ)=9.81×100×(100e-6)²/(18×1.8e-5)≈0.0074 m/s，Re_p=ρ·v·d/μ=1.2×0.0074×100e-6/1.8e-5≈0.05 → Stokes 区）+ 与 ChEDL `fluids.particle_size.v_sphere(d, rho_p, rho_f, mu)` 交叉验证（含三区判定）
2. GREEN: **ChEDL 优先**（裁决 #8）—— 调 `fluids.particle_size.v_sphere`，**ChEDL 内置 Stokes/Intermediate/Newton 三区迭代收敛**（无需自研迭代逻辑；plan 原始"单向判定"疏漏消除）；叶片/纤维用经验法（spec §3.2.2）
3. 测试：3 区域各 1 例 + v_sphere 跨区域边界（Re≈1, Re≈1000）+ Stokes ≤1% 偏差 + 粒径分布拟合 ≤5% 偏差
4. commit: `feat(p5-2-3): gravity separator (Stokes via ChEDL v_sphere) + vane/fiber`

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
- Produces: `calc_fire_case(inp: FireCaseInput, standard: FireCaseStandard) -> FireCaseResult`（wetted_area_m2 / heat_input_w / relief_mass_flow_kgs / relief_volume_flow_m3s / h_fg_j_per_kg / c_factor / F_factor / **formula_ref: FireCaseFormulaRef = {standard: str, version: str, clause: str}** —— 结构化字段，F-09，与 standard_refs_json 一致）
- **standard 由 `StandardResolver.resolve(project_id, discipline="PSV")` 注入**（SUP-P5-PSV-001 §4.1）；不允许请求参数直接传 standard_profile_code（请求可覆盖但需权限校验 — 由 Task 18 处理）

**Steps**:
1. RED: 写 API 521 完整单位换算链（**英制链**，F-02 修正 A^0.82 中间值 + D-03 GB 2011/2024 双版本）——
   - 立式容器润湿面积 A_w = π·D·H（**94.248 m²**，非 85；卧式含液位修正按封头曲面+圆柱部分）
   - **API 521 7th Ed. Table 5 C 值分档**（用户审查 #1 关键修正）：
     - adequate drainage + firefighting：**C = 21,000 BTU/(hr·ft²)**
     - inadequate drainage + firefighting：**C = 34,500 BTU/(hr·ft²)**
     - plan V1.1 误用 43,200（混淆 SI 转换系数）—— 阻塞级错误，修正为 21,000
   - **算例复核（F-02）**：D=3m, H=10m → A_w = π×3×10 = 94.248 m² × 10.7639 = 1,014.5 ft² → ln(1014.5) × 0.82 = 6.9221 × 0.82 = 5.6761 → e^5.6761 = **291.9** → Q(BTU/hr) = 21,000 × 291.9 ≈ **6,129,900 BTU/hr** → Q(W) = 6,129,900 × 0.2931 ≈ **1.797 MW**（V1.1/V1.3 误算 283.7 → 1.75 MW 低估 2.8% / 5.0 kg/s 偏低 2.6%）→ W = 1.797M / 350,000 = **5.13 kg/s**
   - **h_fg 标注**（用户审查风险 #2）：350 kJ/kg 仅作**测试用例输入值**（非 API 521 推荐值；API 521 保守下限 115 kJ/kg，典型烃类 200-400 kJ/kg）；生产代码 h_fg 应从 FLASH 物流热力学数据获取（CHEDL `chemicals.Hfus` / 饱和蒸气 + 饱和液体焓差）或用户输入；测试断言必须显式声明 `h_fg_input_kj_per_kg=350`
2. GREEN: 自研公式（fluids/chemicals 无对应模块）—— **API/GB 计算逻辑完全隔离，各自独立函数和测试基准，不在函数内部用 `if standard == "GB"` 分支**（SUP-P5-PSV-001 §4.1 核心原则）：
   - **API 521 7th Ed. 分支**（`calc_fire_case_api521(inp)`）：润湿面积按容器类型分支（立式 πDH / 卧式封头曲面+圆柱+液位修正）+ C 值 adequate drainage / inadequate drainage 分档（**21000 / 34500**）+ F 环境因子 + h_fg 用户输入；formula_ref = {standard: "API_521", version: "7th", clause: "Table 5"}
   - **GB/T 150.1 双版本分支**（D-03）：`calc_fire_case_gb150_v2011(inp)` / `calc_fire_case_gb150_v2024(inp)`；standard.version 锁定后路由到对应子分支；2024 子分支为默认（新建项目）；润湿面积按 GB 几何规则（与 API 的 πDH 不同）+ GB 修正系数 + GB 附录B 泄放公式结构；formula_ref = {standard: "GB_T_150.1", version: <2011|2024>, clause: "附录B"}
   - **入口分发**：`calc_fire_case(inp, standard)` 根据 standard.profile_code + standard.version 路由到对应分支；standard 由 Task 24 (P5-0-5) StandardResolver 注入
3. 测试：4 例（API 立式/卧式 × adequate drainage/inadequate drainage）+ 4 例（GB 2024 立式/卧式 × adequate/inadequate）+ 2 例（GB 2011 同一容器 — 验证版本差异隔离）+ **完整单位链断言**（API 英制链 A_w(ft²) → Q(BTU/hr) → Q(W) — 中间值 1,014.5 / 291.9 / 6,129,900 / 1.797MW / 5.13kg/s 五段独立断言）+ **GB 标准算例 / 工艺室手算 ≤5% 偏差**（GB 阈值由工艺室确认）+ formula_ref 字段结构化断言（FireCaseFormulaRef = {standard, version, clause} 三字段）+ h_fg 输入字段断言
4. commit: `feat(p5-3-1): PSV fire case (API 521 7th + GB/T 150.1 2011/2024 双版本双路径)`

#### Task 14: P5-3-2 阀门关闭 + 反应失控 + 热膨胀

**Files**:
- Create: `app/services/psv/other_cases_service.py`
- Create: `tests/services/psv/test_other_cases.py`

**接口**:
- Produces: `calc_closed_valve_case(inp, standard: ClosedValveStandard) -> ReliefResult` + `calc_reaction_runaway(inp) -> ReliefResult` + `calc_thermal_expansion(inp, standard: ThermalExpansionStandard) -> ReliefResult`
- standard 由 P5-0-5 StandardResolver 注入；GB 路径为 `calc_closed_valve_case_hg20570(inp)`（SUP-P5-PSV-001 §4.3：HG/T 20570.2-1995 框架 + 工程经验补充）

**Steps**:
1. RED: 写 3 工况公式手算 + **公式来源标注**（plan 原始疏漏消除 + SUP-P5-PSV-001 双路径）——
   - `closed_valve`：API 521 §4.3 阀门误关流量截断（最大泵流量 + 流体膨胀系数 β）；公式 W = Q_pump × ρ × β
   - `closed_valve_GB`：HG/T 20570.2-1995 §2.3 控制阀故障（**原标准未提供完整公式，formula_ref 必须标注 `supplement: 基于工程经验补充`，F-08 修正原 typo**）
   - `reaction_runaway`：API 521 §4.4 + DIERS 两相流泄放动力学（**API/GB 共用** —— 反应失控公式不受标准体系差异影响）
   - `thermal_expansion`：API 521 §4.5 液体热膨胀（阻塞管段工况）；W = V × ρ × β × ΔT / t
2. GREEN: **API/GB 计算逻辑完全隔离**（SUP-P5-PSV-001 §4.1）—— `calc_closed_valve_case_api521(inp)` vs `calc_closed_valve_case_hg20570(inp)` 独立函数 + 公用入口分发；公用 `ReliefResult` dataclass（mass_flow + volume_flow + scenario enum + **formula_ref 字段 + standard_refs 子字段**）；公式版本入 DataLineage
3. 测试：3 工况 × 2 标准 = 6 例（API closed_valve / GB closed_valve 公式来源标注 / API reaction / GB reaction / API thermal / GB thermal）+ formula_ref 断言 + **GB closed_valve formula_ref.supplement 字段断言** + 与 API 521 / DIERS 手算 ≤5% 偏差
4. commit: `feat(p5-3-2): PSV other cases (API/GB 双路径 + 公式溯源)`

#### Task 15: P5-3-3 多工况叠加 + 最大泄放量

**Files**:
- Create: `app/services/psv/relief_aggregator_service.py`
- Create: `tests/services/psv/test_relief_aggregator.py`

**接口**:
- Produces: `aggregate_relief_cases(cases: list[ReliefResult]) -> ReliefAggregateResult`（max_mass_flow_kgs / max_volume_flow_m3s / max_scenario / per_scenario_json）

**Steps**:
1. RED: 写多工况叠加测试（3 工况 → max mass flow 取最大；max volume flow 取最大；max_scenario 字段标记）
2. GREEN: 聚合函数 + spec §2.5 "多泄放工况叠加 ≤5s" 性能测试 + **ReliefAggregateResult 直接作为 Task 16 ReliefAreaInput.mass_flow 输入**（plan 原始"任务顺序独立"问题消除 —— Task 16 测试中追加端到端"聚合 → 面积"用例）
3. 测试：4 工况叠加 + 空集异常 + **端到端"Task 15 聚合 → Task 16 面积"集成测试**（fixture 共享）
4. commit: `feat(p5-3-3): PSV multi-case aggregator (端到端驱动 Task 16)`

**衔接说明**：Task 15 完成后，Task 16 实现时应直接消费 `ReliefAggregateResult.max_mass_flow_kgs` 而非构造孤立测试数据；端到端集成测试断言 `area_m2 > 0` 且 `formula_ref` 标记 `omega_method=two_point`。

#### Task 16: P5-3-4 PSV 泄放面积（气体/液体/两相流）

**Files**:
- Create: `app/services/psv/relief_area_service.py`
- Create: `tests/services/psv/test_relief_area.py`

**接口**:
- Produces: `calc_relief_area(inp: ReliefAreaInput, standard: ReliefAreaStandard) -> ReliefAreaResult`（area_m2 / medium: Literal["GAS","VAPOR","LIQUID","TWO_PHASE"] / formula_ref / omega_method: Optional[Literal["single_point","two_point","direct_integration"]] / standard_refs）
- standard 由 P5-0-5 StandardResolver 注入；API 路径 `calc_relief_area_api520(inp)` / GB 路径 `calc_relief_area_gb12241(inp)`

**Steps**:
1. RED: 写 3 介质公式手算 + **ω 法版本明确 + GB/T 12241-2021 双路径**（plan 原始疏漏消除 + SUP-P5-PSV-001 §4.4）——
   - **API 520 路径**：气体 A = W / (C·Kd·P1·Kb) × √(T·Z/M)（§5.5.3）/ 液体 A = W / (ρ·√(ΔP/(k·ρ)))（§5.6.2）/ 两相流 ω 法默认 two_point（API 520 附录D 滞止 + 0.9·P_stagnation）
   - **GB/T 12241-2021 路径**（SUP-P5-PSV-001 §4.4）：§7.4 排量系数确定 + §7.5 额定排量系数 + §8 安全阀尺寸确定；额定排量 = 理论排量 × 额定排量系数 或 实测排量 × 减低系数(0.9)；亚临界流动需乘 Kb（GB 表4）；**两相流方法 GB 路径 P5 阶段暂缺**（D-06 决议：转 P5+，P5-OPEN-00W 关闭），Task 16 GB 两相流介质**复用 API 结果**并 formula_ref 标注 `two_phase_inherited_from: "API_520"`；ReliefAreaStandard 接口预留 DIERS 积分法扩展位
   - `omega_method: Literal["single_point","two_point","direct_integration"]` 仅 API 路径生效
2. GREEN: 介质分支 + 两相流 FLASH 联动（调 P4 flash_service 算 Z/M）+ C/Kd/Kb 默认值表（API 路径）+ GB 排量系数表（GB 路径）+ omega_method 参数透传；**API/GB 计算逻辑完全隔离**（SUP-P5-PSV-001 §4.1）；**ChEDL 复用评估**：可调 `fluids.safety_valve.API520_round_size`（API 526 圆整复用 Task 17），但两相流方法仍自研以锁定 ω 法版本；**问题6 落库口径**：GB 两相流介质复用 API 结果时 `relief_results.standard_profile_code = "GB"`（项目配置优先，不写 "API"）+ `relief_results.formula_ref_json.two_phase_inherited_from = "API_520"`（标注计算来源）；P6 FLARE_SYS 按项目标准汇总时不遗漏该记录
3. 测试：3 介质 × 2 标准 = 6 例 + **omega_method 切换测试**（API 单点 vs 两点 vs 直接积分）+ 两相流 ≤5% 偏差（vs HYSYS）+ formula_ref 断言（含 omega_method / GB clause）/ GB 标准算例 ≤5% 偏差（阈值由工艺室确认）
4. commit: `feat(p5-3-4): PSV relief area (API 520 + GB/T 12241 双路径 + omega_method)`

#### Task 17: P5-3-5 API 526 选型 + API 2000 呼吸阀

**Files**:
- Create: `app/services/psv/orifice_service.py`（API 526 孔口圆整）
- Create: `app/services/psv/breathing_valve_service.py`（API 2000 呼吸阀）
- Create: `tests/services/psv/test_orifice.py`
- Create: `tests/services/psv/test_breathing_valve.py`

**接口**:
- Produces: `select_orifice(area_m2, standard: OrificeStandard) -> OrificeResult`（API 526 标准孔口 D~T / GB/T 12241 标准孔口，圆整向上）+ `calc_breathing_valve(inp) -> BreathingValveResult`（thermal_inout_m3_s / working_inout_m3_s / total_m3_s）
- standard 由 P5-0-5 StandardResolver 注入；API 路径 `select_orifice_api526(area_m2)` / GB 路径 `select_orifice_gb12241(area_m2)`

**Steps**:
1. RED: 写 API 526 孔口表（D=0.110in² ... T=26.0in²）+ GB/T 12241-2021 §8 标准孔口表 + API 2000 第7版呼吸量（待 P5-OPEN-003 确认，默认第7版）
2. GREEN: **API/GB 计算逻辑完全隔离**（SUP-P5-PSV-001 §4.1 + §4.5）—— `select_orifice_api526` 圆整到 D~T 孔口；`select_orifice_gb12241` 按 GB/T 12241 §8 圆整；**GB 孔口表 P5 降级路径**（D-04 裁决：P5 输出所需流道直径不强制圆整；P5-OPEN-00Z 关闭）：`select_orifice_gb12241(inp)` → 计算 `required_diameter_mm` + formula_ref = {standard: "GB_T_12241", version: "2021", clause: "§8", **orifice_table_status: "incomplete_fallback"**, note: "输出所需流道直径，未圆整到标准孔口系列"}；完整 GB 孔口表录入转 P5+；呼吸量（API 2000 热呼吸 + 操作呼吸）
3. 测试：API 526 圆整向上 + **GB/T 12241 降级路径**（required_diameter_mm + orifice_table_status 断言）+ 呼吸量 ≤2% 偏差 + formula_ref 结构化断言（OrificeFormulaRef = {standard, version, clause, orifice_table_status, note}）
4. commit: `feat(p5-3-5): PSV orifice (API 526 + GB/T 12241 双路径) + breathing (API 2000)`

#### Task 18: P5-3-6 PSV API + 落库 + outlet_stream

**Files**:
- Create: `app/services/psv/psv_persist.py`
- Create: `app/api/v1/psv.py`
- Create: `tests/services/psv/test_psv_persist.py`
- Create: `tests/api/v1/test_psv.py`
- Create: `alembic/versions/p5_psv_standard_not_null.py`（F-07：Task 24 加列 + 默认值，Task 18 强制 NOT NULL + 存量回填）

**接口**:
- Produces: `POST /api/v1/psv/calculate-relief` / `calculate-area` / `select-orifice` + `POST /api/v1/projects/{project_id}/standards/psv`（SUP-P5-PSV-001 §5.1 项目标准配置）
- 落库: `psv_results` + `relief_results`（P5-OPEN-005 新表）+ outlet_stream(source_type=PSV) + **标准字段三列 NOT NULL**（`standard_profile_code` / `standard_refs_json` / `formula_ref_json` —— **F-07**：Task 24 加列+默认值；Task 18 migration `p5_psv_standard_not_null.py` 强制 NOT NULL + 存量回填 `'API' / {} / {}`）
- **预留接口**（P6 FLARE_SYS 消费）：`GET /api/v1/psv/relief-summary?project_id=` 按 **项目标准** 汇总（SUP-P5-PSV-001 §5.4）—— 避免 P6 FLARE_SYS 拿到混合口径数据；响应中含 `standard_profile_code` 供 P6 识别数据口径

**Steps**:
1. RED: 4 端点 + persist + 标准字段落库 + 门禁规则（G1~G6，SUP-P5-PSV-001 §6）测试 + **存量回填 + NOT NULL 迁移测试**（F-07）
2. GREEN: 
   - `POST /projects/{project_id}/standards/psv` 项目标准配置（CUSTOM 时 approval_json 必填；仅项目标准负责人/管理员可配，403 否则）
   - 3 计算端点：调用 `StandardResolver.resolve(project_id, discipline="PSV")` 获取 standard → 注入 Task 13/14/16/17 函数；项目未配置 → 422 `PSV_STANDARD_NOT_CONFIGURED`；请求覆盖项目默认但无权限 → 403 `PSV_STANDARD_OVERRIDE_FORBIDDEN`（G1/G2 门禁）
   - finalize_calc_record 双表 + 写入标准三列 + create_outlet_stream 扩展 "PSV"
   - **F-03**：`relief_summary` 按项目标准取每组最大 mass_flow 对应工况（**改用窗口函数**，避免 MAX(scenario) 字母序错误）：
     ```sql
     SELECT DISTINCT ON (project_id, standard_profile_code)
         project_id, standard_profile_code,
         mass_flow AS max_mass_flow,
         volume_flow AS max_volume_flow,
         scenario AS max_scenario
     FROM relief_results
     WHERE project_id = :pid
     ORDER BY project_id, standard_profile_code, mass_flow DESC
     ```
   - record_hash 计算含 standard 字段（G4 同一输入跨标准 → 不同 record_hash → 两条独立记录）
   - **F-07**：migration `p5_psv_standard_not_null.py` —— UPDATE 存量记录 standard_profile_code='API' / standard_refs_json='{}' / formula_ref_json='{}' → ALTER COLUMN ... SET NOT NULL
3. 测试：4 端点 + 标准字段落库 roundtrip + **G1-G6 门禁 6 例**（未配置 422 / 无权限覆盖 403 / CUSTOM 无审批 422 / 跨标准 record_hash 不同 / 标准变更旧记录待复核 / 历史迁移 migrated_default=true）+ 双表 roundtrip + 多工况叠加 ≤5s + **relief_summary max_scenario 正确性测试**（F-03：FIRE 5kg/s vs CLOSED_VALVE 8kg/s vs THERMAL 3kg/s → max_scenario="CLOSED_VALVE" 而非字母序 "THERMAL_EXPANSION"）+ NOT NULL 迁移后无空记录
4. commit: `feat(p5-3-6): PSV API + persist + standard 落库 + FLARE_SYS 按标准预留 + relief_summary 窗口函数`

### 批 P5-4 — HEAT 换热器（5 task）

#### Task 19: P5-4-1 HTRI 自研解析器

**Files**:
- Create: `app/services/heat/htri_parser.py`
- Create: `tests/services/heat/test_htri_parser.py`
- Create: `tests/services/heat/fixtures/htri_sample.txt`（自造测试样本）

**接口**:
- Produces: `parse_htri(path) -> HtriParsedData`（Q_w / U_w_m2k / area_m2 / shell_dia_m / tube_length_m / tube_count / baffle_spacing_m / ...）+ `detect_version(path) -> str` + `HTRI_VERSION_SUPPORTED: list[str]` 白名单 + `HtriVersionUnsupportedError` 异常

**Steps**:
1. RED: 写解析手算样本（Q=1MW, U=500 W/m²K, A=10m²）+ 解析失败异常 + **版本探测测试**（公司常用 v1 / v2 / 不支持版本 v99）
2. GREEN: 自研解析（基于 HTRI 文本/CSV 输出格式）+ `detect_version(path)` 探测函数（按文件头魔数 / 文件名约定 / 首行关键字判别）+ `HTRI_VERSION_SUPPORTED` 白名单（待 P5-OPEN-001 确认；默认 ["Xist_v6","Xchanger_Suite_v8"]）+ 不在白名单 → `HtriVersionUnsupportedError(versions_supported)` 含升级指引 URL；plan 原始"版本兼容风险被低估"疏漏消除
3. 测试：3 例（基本/管壳/空冷）+ **版本探测 5 例**（白名单 v1/v2 + 不支持 v99/0/空文件）+ 解析失败异常 + ≤10s 性能
4. commit: `feat(p5-4-1): HTRI parser + version detection`

**OPEN**：P5-OPEN-001（HTRI 版本兼容范围）默认按公司常用版本实施，扩展性预留 `version: str` 字段
**架构评估（用户审查建议 3）**：ht 包（Zukauskas/Bell/ESDU 公开方法）与 HTRI（Licensor 专有）双轨并行 —— 折中方案保留 HTRI 解析器（与工艺室现有工作流一致）+ 评估 ht 直接计算作为独立交叉验证路径（P5+ 实施，本 task 仅预留接口）

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
- Produces: `estimate_weight(inp: WeightEstimateInput) -> WeightEstimateResult`（**shell_cylinder_weight_kg** + **shell_total_weight_kg** / tube_weight_kg / baffle_weight_kg / nozzles_weight_kg / channels_weight_kg / total_weight_kg / formula_ref / tema_type: Literal["BEM","AEM","..."]）

**Steps**:
1. RED: 写 U 型管手算 + **公式来源标注 + 壳体分量拆分**（plan V1.1 字段不清，用户审查 #2 修正）——
   - 公式参考 **TEMA Standards 9th Ed. §5 机械设计 + 工程经验公式**（Hall/Smolik 换热器设计手册 + Perry's Chemical Engineers' Handbook §11 换热器）
   - **圆筒段裸重**（薄壁圆筒展开面积 × 壁厚 × 密度）：D_shell=1m, L=5m, t_shell=0.012m → shell_cylinder=7850×0.012×π×1×5≈**1,480 kg**
   - **壳体总重**（含封头+法兰+接管+补强+支座）：≈1,480 + 300（封头×2）+ 300（法兰）+ 75（接管补强）+ 225（鞍座）≈**2,380 kg**（与 V1.0 hardcoded 2,400 量级一致，圆筒段非总重）
   - 偏差基准：商业软件 HTRI / Aspen EDR 报告值；或文献算例（Peters & Timmerhaus Plant Design §换热器重量）
2. GREEN: 自研公式（fluids/chemicals 无对应模块）—— **shell 拆分为 cylinder + heads + flanges + nozzles + saddles 五段累加**；tube / baffle / channels 三段；formula_ref 字段记录 TEMA 版本 + 公式出处
3. 测试：2 例（BEM 固定管板 / AEM U 型管）+ 与 HTRI / Aspen EDR 报告偏差 ≤10%（仅 total_weight）+ **shell_cylinder vs shell_total 独立断言**（cylinder 1,480 ± 1% 总差 / total 2,380 ± 10% vs 商业软件）+ formula_ref 字段断言
4. commit: `feat(p5-4-4): weight estimate (TEMA 9th + 五段壳体拆分)`

#### Task 23: P5-4-5 HEAT API + 落库 + outlet_stream（HEAT_EXCHANGE）

**Files**:
- Create: `app/services/heat/heat_persist.py`
- Create: `app/api/v1/heat.py`
- Create: `tests/services/heat/test_heat_persist.py`
- Create: `tests/api/v1/test_heat.py`

**接口**:
- Produces: `POST /api/v1/heat/import-htri` / `GET /heat/{heat_id}` / `POST /heat/{heat_id}/weight-estimate`
- 落库: `heat_results` 单行 + outlet_stream(source_type=HEAT, change_type=HEAT_EXCHANGE)
- **预留接口**（P7 UTIL 消费）：heat_results 表 `duty_w`（热负荷）+ `total_weight_kg` 字段供 P7 UTIL 综合能耗 / 设备汇总查询

**Steps**:
1. RED: 3 端点 + 48 字段 roundtrip + outlet_stream HEAT_EXCHANGE 测试
2. GREEN: finalize_calc_record + create_outlet_stream 扩展 "HEAT" + HEAT_EXCHANGE change_type；物流号更换（spec V1.2 §3.2.4）
3. 测试：3 端点 + HEAT_EXCHANGE 出口物流独立编号 + ACL + 三步守卫 + heat_results.duty_w/total_weight_kg 字段可读
4. commit: `feat(p5-4-5): HEAT API + persist + outlet_stream + UTIL 预留`

### 批 P5-0 前置任务（Task 24/25 — P5-0-5/P5-0-6，与主 P5-0 批同步执行）

> **执行顺序**：F-01 方案 A 决策 + **D-08 时序细化**（问题3 明确）。Task 24/25 编为末尾但**前置执行**——P5-1 启动前必须完成。
> - **Task 25（P5-0-6 ChEDL 版本锁定）**：在 **P5-0 批最开始执行，先于 Task 1**（独立无依赖，仅修改 pyproject.toml + uv.lock + ADR；P5-1 启动前 ChEDL 已锁定，避免风险窗口过大）
> - **Task 24（P5-0-5 PSV 标准配置模型）**：在 **Task 1（P5-0-1 模型扩展）完成后立即执行**（不必等 Task 2~4；三列依赖 Task 1 落地）；与 Task 2~4 并行

#### Task 24: P5-0-5 PSV 标准配置模型（SUP-P5-PSV-001 §3，前置执行）

> **执行顺序调整（问题3 明确）**：Task 24 在 Task 1（P5-0-1 模型扩展）完成后**立即执行**，不必等 Task 2~4；三列依赖 Task 1 落地

**Files**:
- Create: `alembic/versions/p5_psv_standard_profiles.py`（**仅加列 + 默认值**，F-07：NOT NULL 强制由 Task 18 完成）
- Modify: `app/models/psv.py`（新建 `ProjectCalculationStandardProfile` ORM + `PsvStandardProfileCode` 枚举）
- Modify: `app/models/calc.py`（psv_results / relief_results 加 `standard_profile_code` 默认 'API' / `standard_refs_json` 默认 `'{}'` / `formula_ref_json` 默认 `'{}'` 三列；可空，Task 18 强制 NOT NULL）
- Modify: `app/services/calc_lineage.py`（RECORD_TYPE_REGISTRY 同步登记 `ProjectCalculationStandardProfile`，F-06：**Task 24 完成后总注册数 = 13 类**）
- Create: `app/services/psv/standard_resolver.py`（项目级标准解析层）
- Create: `app/services/psv/formula_ref_types.py`（**问题4 集中定义 TypedDict**：FireCaseFormulaRef / ClosedValveFormulaRef / ReliefAreaFormulaRef / OrificeFormulaRef 等所有 formula_ref 结构化字段统一在此 module；Task 13/14/16/17 引用）
- Create: `tests/models/test_psv_standard_profile.py`
- Create: `tests/services/psv/test_standard_resolver.py`
- Create: `docs/adr/0028-psv-multi-standard-engine.md`（**D-05：状态 = Proposed（评审中）**——SUP-P5-PSV-001 V1.0 已批准（E-01），但 ADR 作为架构落地文档需独立评审）

**接口**:
- Produces: `project_calculation_standard_profiles` 表（含 `profile_code: Literal["API","GB","CUSTOM"]` + `standard_refs_json` + `approval_json` + **`approved_by`（CUSTOM 时非空）** + **`is_default`** + TimestampMixin 四列 `created_by` / `created_at` / `updated_at` / **`effective_from`**）；`psv_results` / `relief_results` 三列（可空，Task 18 强制）；`StandardResolver.resolve(project_id, discipline="PSV") -> PsvStandardProfile`；ADR-0028（Proposed）
- **表字段对齐 SUP-P5-PSV-001 §3.1**（问题2 补全）：`id` / `project_id` / `discipline` / `profile_code` / `standard_refs_json` / **`approval_json`（CUSTOM 时必填）** / **`approved_by`（CUSTOM profile 审批人，与 created_by 区分）** / `is_default` / `effective_from` / `created_by` / `created_at` / `updated_at`；`approved_by` 在 `profile_code='CUSTOM'` 时 NOT NULL，其他情况可空
- **formula_ref TypedDict 集中定义**（问题4）：
  ```python
  # app/services/psv/formula_ref_types.py
  from typing import TypedDict, Optional, Literal

  class FireCaseFormulaRef(TypedDict):
      standard: str           # 如 "API_521" / "GB_T_150.1"
      version: str            # 如 "7th" / "2011" / "2024"
      clause: str             # 如 "Table 5" / "附录B"
      # GB 火灾扩展字段（D-03）：
      drained: Optional[Literal["adequate", "inadequate"]]

  class ClosedValveFormulaRef(TypedDict):
      standard: str
      version: str
      clause: str
      supplement: Optional[str]  # HG/T 20570.2-1995 标注"基于工程经验补充"

  class ReliefAreaFormulaRef(TypedDict):
      standard: str
      version: str
      clause: str
      omega_method: Optional[Literal["single_point", "two_point", "direct_integration"]]
      two_phase_inherited_from: Optional[str]  # D-06：GB 路径两相流标 "API_520"

  class OrificeFormulaRef(TypedDict):
      standard: str           # 如 "API_526" / "GB_T_12241"
      version: str
      clause: str             # 如 "§8"
      orifice_table_status: Optional[Literal["complete", "incomplete_fallback"]]  # D-04
      note: Optional[str]
  ```
- 标准 profile 映射（SUP-P5-PSV-001 §2 + **D-03 GB/T 150.1 版本策略**）：
  - **API profile**：fire_case=API_521_7th / closed_valve=API_521_7th / relief_area=API_520_10th / orifice=API_526_2017 / two_phase.omega_method=two_point
  - **GB profile**（**D-03**：新项目默认 version="2024"；历史项目迁移可保持 version="2011" + migrated_default=true 标记）：fire_case={standard: "GB_T_150.1", version: <"2011"|"2024">, clause: "附录B"} / closed_valve={standard: "HG_T_20570.2", version: "1995", clause: "§2.3"} / relief_area={standard: "GB_T_12241", version: "2021", clause: "§7.4"} / orifice={standard: "GB_T_12241", version: "2021", clause: "§8", orifice_table_status: "incomplete_fallback"}（**D-04 降级**）/ pilot_operated={standard: "GB_T_28778", version: "2023", enabled: false}（**D-07**：转 P5+）
  - **CUSTOM profile**：混合配置 + approval_json 必填（approved_by + reason + approved_at，**D-02**：仅项目标准负责人/管理员可创建）

**Steps**:
1. RED: 写项目未配置 → 422 `PSV_STANDARD_NOT_CONFIGURED` 测试 + API/GB/CUSTOM 三 profile 配置 + 读取测试 + psv_results/relief_results 三列存在性测试 + CUSTOM 无 approval → 422 `PSV_CUSTOM_PROFILE_APPROVAL_REQUIRED` 测试 + **RECORD_TYPE_REGISTRY 13 类注册断言**（F-06）+ **GB profile version=2024/2011 双版本切换测试**（D-03）+ **D-02 项目未配置无隐式回退**测试 + **`approved_by` 字段存在性 + CUSTOM 时 NOT NULL 测试**
2. GREEN:
   - 新表 `project_calculation_standard_profiles`（含 UNIQUE(project_id, discipline, effective_from) + is_default 唯一性 + TimestampMixin `created_by` / `created_at` / `updated_at` + `approved_by` BIGINT REFERENCES users(id)，**profile_code='CUSTOM' 时 approved_by NOT NULL**，其他可空）
   - psv_results / relief_results 三列加列（默认 'API' / '{}' / '{}'，**可空**，**F-07**：NOT NULL 由 Task 18 完成）
   - `StandardResolver` 服务层：**D-02 禁止隐式回退** —— 项目未配置 → raise `PsvStandardNotConfiguredError(422)`；项目配置 CUSTOM 无 approval 或无 approved_by → raise `PsvCustomProfileApprovalRequiredError(422)`；项目配置 GB version 锁定 → 路由到对应子分支
   - `formula_ref_types.py`（问题4 集中定义 TypedDict）
   - ADR-0028 起草（**D-05 Proposed 状态**）：PSV 多标准引擎设计裁决（项目级显式配置 + 公式溯源 + 禁止隐式回退 + GB 2011/2024 双版本 + GB 孔口表降级 + DIERS/先导式转 P5+）
3. 测试：≥11 例（未配置 422 / API 配置 / GB 2024 配置 / GB 2011 配置 / GB 2024→2011 切换 / CUSTOM 无 approval 422 / **CUSTOM 无 approved_by 422** / 同一 (project_id, discipline) 时间唯一 / record_hash 含 standard 字段独立 / **registry 13 类完整性** F-06 / **D-02 无隐式回退**断言）
4. commit: `feat(p5-0-5): PSV standard profile (SUP-P5-PSV-001 §3 + ADR-0028 Proposed + approved_by + TypedDict)`

**门禁**（SUP-P5-PSV-001 §6）：G1 项目未配置 → 422（D-02 强化：禁止隐式回退） / G3 CUSTOM 缺审批（approval_json + approved_by）→ 422 / G6 历史迁移 → migrated_default=true 标记
**依赖**：Task 1（P5-0-1 模型扩展）必须先完成（三列才能加）；Task 25（ChEDL 版本锁定）作为 P5-0 批前置基线

#### Task 25: P5-0-6 ChEDL 版本锁定 ADR-0029（D-08，前置执行）

**Files**:
- Create: `docs/adr/0029-chedl-version-lock.md`
- Modify: `pcs-backend/pyproject.toml`（fluids / chemicals / ht 锁定到精确版本 `==X.Y.Z`）
- Modify: `pcs-backend/uv.lock`（uv lock 重新生成，对应版本快照）
- Create: `tests/architecture/test_chedl_version.py`（pip freeze 快照断言 + import 时版本断言）
- Create: `tests/fixtures/chedl_version_snapshot.txt`（CI baseline）

**接口**:
- Produces: `requirements.txt` + `uv.lock` 锁定 ChEDL 精确版本；ADR-0029（Accepted，记录版本选择依据 + 锁定策略 + 升级流程）；测试断言 `fluids.__version__ == X.Y.Z` 等

**Steps**:
1. RED: 写 ChEDL 版本断言测试（`import fluids; assert fluids.__version__ == "X.Y.Z"` + `chemicals` + `ht` 三库）+ `pip freeze` 输出与 baseline `chedl_version_snapshot.txt` 字节级一致测试
2. GREEN:
   - 选择 ChEDL 版本：fluids / chemicals / ht 选当前稳定版（P5-0 启动时 P4 已闭环的版本号）—— 锁定策略：精确版本 `==X.Y.Z`，**禁止 `>=` / `~=`**（杜绝 floating）
   - ADR-0029 内容：版本选择依据（功能覆盖 + 已知 bug 修复）+ 锁定策略（精确版本）+ 升级流程（独立 PR + 回归测试全量 + ADR 更新）
   - `uv.lock` 重新生成（`uv lock`）+ CI baseline fixture 落地
3. 测试：≥5 例（fluids / chemicals / ht 三库版本断言 + pip freeze 快照断言 + uv.lock 文件存在性 + 升级流程文档链接断言）
4. commit: `feat(p5-0-6): ChEDL version lock (ADR-0029 + requirements.txt ==)`

**生效时机**：P5-0 批内完成（P5-1 启动前生效）；P5-1 之后**禁止修改** ChEDL 版本（升级需独立 PR）

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
| SUP-P5-PSV-001 §2 项目级 PSV 标准配置模型 | P5-0-5（新增） |
| SUP-P5-PSV-001 §3.1 project_calculation_standard_profiles 表 + §3.2 psv_results/relief_results 加列 | P5-0-5 + P5-0-1（数据模型层） |
| SUP-P5-PSV-001 §3.3 formula_ref 条款级 | P5-0-1 + P5-3-1/3-2/3-4/3-5（lineage D4 已备） |
| SUP-P5-PSV-001 §4.1 standard_resolver 层 | P5-0-5（独立 module）+ P5-3-1~3-5（接口参数注入） |
| SUP-P5-PSV-001 §4.2 API 521 / GB/T 150.1-2024 附录B 双路径 | P5-3-1（火灾工况 API/GB 双函数） |
| SUP-P5-PSV-001 §4.3 HG/T 20570.2-1995 + 工程经验补充 | P5-3-2（control valve 故障 GB 路径） |
| SUP-P5-PSV-001 §4.4 API 520 / GB/T 12241-2021 双路径 | P5-3-4（relief_area API/GB） |
| SUP-P5-PSV-001 §4.5 API 526 / GB/T 12241-2021 双路径 | P5-3-5（orifice API/GB） |
| SUP-P5-PSV-001 §5.1 项目标准配置 API | P5-3-6（新增 `POST /projects/{project_id}/standards/psv`） |
| SUP-P5-PSV-001 §5.2~§5.3 计算请求 + 响应落库 | P5-3-1/3-2/3-4/3-5（standard_profile_code 注入）+ P5-3-6 |
| SUP-P5-PSV-001 §5.4 relief_summary 按项目标准汇总 | P5-3-6（接口调整 + 供 P6 FLARE_SYS） |
| SUP-P5-PSV-001 §6 G1~G6 门禁 | P5-3-6（422/403 校验 + record_hash 含 standard + pending_review + migrated_default） |
| SUP-P5-PSV-001 §7 API/GB 独立 golden + 阈值 ≤2%/≤5% | P5-3-1/3-2/3-4/3-5 测试用例 |
| SUP-P5-PSV-001 §8.5 新增 ≥15 例门禁/标准切换测试 | 验收基线 ≥1665 → ≥1670（含 D-08 ChEDL +5） |
| SUP-P5-PSV-001 §9 OPEN-00X/Y/Z/W/V | 见 "裁决记录 D-02/D-03/D-04/D-06/D-07" + "Backlog" |
| SUP-P5-PSV-001 §10 Backlog（DIERS / 先导式 / 孔口表 / CUSTOM 审批 / 跨标准对比 / P6 FLARE_SYS 汇总） | P5+ / P6+ 见 Backlog |
| ADR-0029 ChEDL 版本锁定（D-08） | Task 25 (P5-0-6) |

**覆盖完整性**：spec §2~§4 + SUP-P5-PSV-001 §1~§10 全部覆盖（**25 task** 含 Task 24 P5-0-5 前置 + Task 25 P5-0-6 ChEDL 版本锁定；F-01 方案 A）。

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

**SUP-P5-PSV-001 V1.0 整合新增风险 / OPEN**（D-02/D-03/D-04/D-06/D-07 已关闭，全部见裁决记录）：
- **PSV 多标准引擎（SUP-P5-PSV-001 §1-§10）**：新增 Task 24 (P5-0-5) 前置任务 + Task 25 (P5-0-6) ChEDL 版本锁定（D-08）；psv_results / relief_results 三列扩展（Task 24 加列+默认值，Task 18 强制 NOT NULL — F-07）；API/GB 路径物理隔离；6 道门禁（G1-G6）
- **OPEN-00X PSV 计算标准默认**（SUP §9）：**D-02 关闭** —— 强制项目级显式配置，禁止隐式回退；新建项目向导引导（前端，后端仅提供配置端点）
- **OPEN-00Y GB/T 150.1 版本**（SUP §9）：**D-03 关闭** —— 项目级可选，新项目默认 2024；历史项目迁移 version="2011" + migrated_default=true 标记
- **OPEN-00Z GB/T 12241 孔口表**（SUP §9）：**D-04 关闭** —— P5 降级为按计算面积输出所需流道直径（formula_ref 标注 orifice_table_status=incomplete_fallback）；完整录入转 P5+
- **OPEN-00W GB 路径两相流方法 DIERS**（SUP §9）：**D-06 关闭** —— 转 P5+；Task 16 GB 两相流介质复用 API 结果并 formula_ref 标注 two_phase_inherited_from="API_520"
- **OPEN-00V 先导式阀 GB/T 28778**（SUP §9）：**D-07 关闭** —— 转 P5+；profile.pilot_operated.enabled=false 配置项预留
- **CUSTOM profile 审批工作流**（SUP §10）：当前仅 approval_json 三字段（approved_by / reason / approved_at），完整审批流（提交 → 复核 → 签发）P5+ 评估
- **跨标准结果对比报告**（SUP §10）：同一容器 API vs GB 偏差分析；P5+ 评估
- **P6 FLARE_SYS 按标准口径汇总接口**（SUP §10）：依赖 Task 18 relief_summary 按项目标准汇总（F-03 窗口函数修正）+ P6 火炬总管汇总时识别口径，避免混合数据
- **门禁测试基线**：G1~G6 + 独立 golden 阈值 + 公式溯源 + record_hash 含 standard → 新增 ≥15 例（验收基线 ≥1665 → **≥1670** 含 D-08 +5）
- **formula_ref 结构化（F-09）**：所有 formula_ref 字段统一为 `{standard, version, clause, ...}` 结构化对象（替代原 Literal）；与 standard_refs_json 结构一致便于 lineage 对比

## 裁决记录

- 批 P5-0 必须先闭环（P5-1~P5-4 依赖 ORM 列 + 9 态 + DICT V3.3 rename）
- outlet_stream Literal 在 P5-1-4 一次性扩展为 ["FLASH","PIPE","PUMP","PIPE_NET","VESSEL","SEP_EQUIP","PSV","HEAT"]
- **RECORD_TYPE_REGISTRY 时机修正**（用户审查问题 #2）：在 **P5-0-1 完成后立即注册** vessel_results / sep_equip_results / psv_results / relief_results / column_sizing_results / mixer_results / 4 张蒸汽表（7 表 + 现有 5 表 = 12 类）；P5-0-2 完成后追加 heat_results（双轨）。**Task 4 (P5-0-4) 测试可正常使用 finalize_calc_record 落库验证**
- 5 个 P5 服务互不依赖（VESSEL → FLASH 物流 → ρ_L/ρ_V；PSV → FLASH 物流 → Z/M；HEAT → EQUIP_LIB；SEP_EQUIP → 颗粒 Stokes 独立）
- 性能预算 ≤2/2/2/5/10/1s 与精度 ≤1/1/2/2/5/10% 由各批性能 + golden 测试覆盖
- 任务粒度与 P4 主体一致（一批一 commit 模式 → P5 同样）
- **ChEDL 分层架构（裁决 #8，源自用户审查建议）**：底层计算引擎优先调用已验证 ChEDL 模块；业务逻辑层自研
  - 直接调用清单：`fluids.separator.v_Souders_Brown` / `K_separator_Watkins` / `K_separator_demister_York`（Task 5/10）/ `fluids.particle_size.v_sphere`（Task 11 三区迭代内置）/ `fluids.safety_valve.API520_round_size`（Task 17 API 526 圆整，仅复用圆整 + 不复用两相流方法因 ω 法版本未锁定）
  - 评估/不调用：`ht` 模块（与 HTRI 双轨评估，P5+ 实施）/ `fluids.safety_valve` 两相流方法（ω 法版本未锁定，自研）/ `fpi` 旋风分离器（活跃更新停滞 8 年，自研）
  - 自研清单：API 521 火灾热输入 / API 2000 呼吸阀 / HTRI 解析器 / EQUIP_LIB 复用推荐 / PSV 多工况聚合 / 反应失控 / 热膨胀
- **golden value 严格度（裁决 #9，源自用户审查错误 1+2）**：所有手算验收值必须给出**完整单位换算链**（D/H/A/Q/W/h_fg 各自独立断言），禁用未注明单位的 hardcoded 数字；与 ChEDL 交叉验证作为独立基线
- **公式溯源字段（裁决 #10，源自用户审查疏漏 4 + 5）**：`ReliefResult.formula_ref` / `CycloneResult.formula_ref` / `WeightEstimateResult.formula_ref` 等字段记录公式版本 + 标准出处（API 520 / 521 / 526 / TEMA / DIERS 等）；版本入 DataLineage（P4-TASK0 D4 已备）
- **PSV 多工况端到端（裁决 #11，源自用户审查问题 #1）**：Task 15 聚合结果直接驱动 Task 16 ReliefAreaInput.mass_flow；端到端测试断言 `area_m2 > 0` + `omega_method=two_point`
- **API 521 英制链锁定 + C 值修正 + A^0.82 中间值复核（裁决 #12，源自用户审查错误 #1，阻塞级 + F-02）**：统一使用英制链（A 以 ft²、Q 以 BTU/hr、C 以 BTU/(hr·ft²)）；C 值分档 adequate drainage+firefighting = **21,000**（V1.1 误用 43,200 高估 2.1 倍）/ inadequate drainage+firefighting = **34,500**；**F-02 算例复核**：D=3m H=10m → A_w=94.248 m² × 10.7639 = 1,014.5 ft² → ln(1014.5)×0.82 = 6.9221×0.82 = 5.6761 → e^5.6761 = **291.9**（V1.3 误算 283.7 低估 2.8%）→ Q = 21,000×291.9 = **6,129,900 BTU/hr** → Q = **1.797 MW**（V1.3 误算 1.75 MW 低估 2.6%）→ W = 1.797M / 350,000 = **5.13 kg/s**（V1.3 误算 5.0 kg/s）；**五段独立断言**（A=94.248m² / A=1,014.5ft² / A^0.82=291.9 / Q=6,129,900 BTU/hr / W=5.13kg/s）；实施前必读 API 521 7th Ed. Table 5 确认
- **h_fg 输入语义（裁决 #13，源自用户审查风险 #2）**：测试用例输入值 350 kJ/kg **非 API 521 推荐值**（API 521 保守下限 115 kJ/kg）；生产代码 h_fg 应从 FLASH 物流热力学数据（CHEDL `chemicals` 饱和蒸气/液体焓差）或用户输入获取；测试断言必须显式声明 `h_fg_input_kj_per_kg=350` 标注为"用例输入"
- **壳体重量分量拆分（裁决 #14，源自用户审查 #2）**：`WeightEstimateResult.shell_cylinder_weight_kg`（圆筒段裸重，薄壁圆筒展开面积 × 壁厚 × 密度） vs `shell_total_weight_kg`（含封头+法兰+接管+补强+支座五段累加）独立字段；V1.0 hardcoded 2,400 kg 实为 shell_total；V1.1 hardcoded 1,480 kg 实为 shell_cylinder；两者不可混用
- **spec §3.2.1 K 因子取值修订（裁决 #16 / D-01 EFFECTIVE，详见上）**：已采纳 SI 单位制（m/s），spec §3.2.1 修订为立式 0.04–0.10 / 卧式 0.07–0.15 / 带除沫器取上限；spec 修订单独立项（不等 P5 执行）；CONFIG 种子以 SI 存储
- **PSV 多标准引擎（裁决 #15，源自 SUP-P5-PSV-001 V1.0 待评审）**：
  - **项目级显式配置**：`PsvStandardProfileCode = Literal["API","GB","CUSTOM"]`；项目未配置 → 422 `PSV_STANDARD_NOT_CONFIGURED`，**禁止隐式回退 API**（SUP-P5-PSV-001 §6 G1）
  - **API/GB 计算逻辑完全隔离**（§4.1 核心原则）：各自独立函数 + 独立测试基准；不在函数内部用 `if standard == "GB"` 分支
  - **GB profile 必含字段**（SUP-P5-PSV-001 §2.1）：`fire_case={standard: "GB_T_150.1", version: "2024", clause: "附录B"}` / `closed_valve={standard: "HG_T_20570.2", version: "1995", clause: "§2.3"}` / `relief_area={standard: "GB_T_12241", version: "2021", clause: "§7.4"}` / `orifice={standard: "GB_T_12241", version: "2021", clause: "§8", orifice_table_status: "incomplete_fallback"}` / `pilot_operated={standard: "GB_T_28778", version: "2023", enabled: false}`
  - **CUSTOM profile 必填审批**：approval_json 含 approved_by + reason + approved_at；缺 → 422 `PSV_CUSTOM_PROFILE_APPROVAL_REQUIRED`（G3）
  - **公式溯源 + record_hash**：`psv_results` / `relief_results` 三列 NOT NULL（`standard_profile_code` / `standard_refs_json` / `formula_ref_json`）；record_hash 计算必须含 standard 字段；同一输入跨标准 → 不同 record_hash → 两条独立记录（G4）
  - **覆盖权限**：请求覆盖项目默认但无权限 → 403 `PSV_STANDARD_OVERRIDE_FORBIDDEN`（G2）
  - **变更/迁移**：标准配置变更 → 旧记录标记 `pending_review` 不自动重算（G5）；历史项目迁移 → `migrated_default=true` 标记 + 复核要求（G6）
  - **relief_summary 按项目标准汇总**（§5.4）：避免 P6 FLARE_SYS 拿到混合口径数据
  - **HG/T 20570.2-1995 控制阀故障补充公式**：原标准未提供完整公式，formula_ref 必须标注 `supplement: 基于工程经验补充`（§4.3；F-08 同步修正原 typo）
  - **P5-OPEN-00X/Y/Z/W/V 已关闭**（SUP-P5-PSV-001 §9）—— 详见裁决 #17（D-02 PSV 强制配置）/ #18（D-03 GB/T 150.1 版本策略）/ #19（D-04 GB/T 12241 孔口表降级）/ #20（D-06 GB DIERS 转 P5+）/ #21（D-07 先导式阀转 P5+）；**D-05 ADR-0028 状态 = Proposed（评审中）—— SUP-P5-PSV-001 V1.0 已批准（E-01 / 裁决 #23），但 ADR 作为架构落地文档需独立评审（架构 ADR 与需求 spec 是不同层级）**；Task 24 起草 Proposed，评审通过后转 Accepted
- **K 因子 SI 单位制（裁决 #16，D-01 EFFECTIVE）**：spec §3.2.1 K 因子取值修订为 SI（m/s）—— 立式 0.04–0.10 / 卧式 0.07–0.15 / 带除沫器取上限；CONFIG 种子以 SI 存储；spec 修订单独立项（不等 P5 执行）；Task 5 (P5-1-1) K 因子边界测试改为 0.04/0.10/0.15（立式）/ 0.07/0.11/0.15（卧式）
- **PSV 标准强制配置（裁决 #17，D-02 EFFECTIVE）**：不设隐式默认，强制项目级显式配置；项目首次调用 PSV 计算端点未配置 → 422 `PSV_STANDARD_NOT_CONFIGURED`（响应体含配置引导链接）；新建项目向导引导 PSV 标准配置（前端实现，后端仅提供配置端点）；Task 24 (P5-0-5) StandardResolver 不实现"无配置回退 API"分支
- **GB/T 150.1 版本策略（裁决 #18，D-03 EFFECTIVE）**：项目级可选，profile 配置锁定；新建项目默认 version="2024"；历史项目迁移保持原版本（2011）+ `migrated_default=true` 标记；Task 13 (P5-3-1) GB 分支拆为两个子分支 `calc_fire_case_gb150_v2011(inp)` / `calc_fire_case_gb150_v2024(inp)`，standard.version 锁定后路由
- **GB/T 12241 孔口表降级（裁决 #19，D-04 EFFECTIVE）**：P5 阶段 `select_orifice_gb12241(inp)` 降级为"按计算面积输出所需流道直径"，不强制圆整到标准孔口系列；formula_ref 结构化标注 `orifice_table_status: "incomplete_fallback"` + `note`；P5-OPEN-00Z 关闭，完整录入转 P5+
- **GB 路径 DIERS 转 P5+（裁决 #20，D-06 EFFECTIVE）**：Task 16 (P5-3-4) GB 路径两相流方法 P5 阶段暂缺；GB 两相流介质计算时**复用 API 结果**并 formula_ref 标注 `two_phase_inherited_from: "API_520"`；ReliefAreaStandard 接口预留 DIERS 积分法扩展位；P5-OPEN-00W 关闭
- **先导式阀 GB/T 28778 转 P5+（裁决 #21，D-07 EFFECTIVE）**：Task 24 GB profile 保留 `pilot_operated: {standard: "GB_T_28778", version: "2023", enabled: false}` 配置项，不实现计算模块；P5-OPEN-00V 关闭
- **ChEDL 版本锁定（裁决 #22，D-08 EFFECTIVE）**：P5-0 批内新增 **Task 25 (P5-0-6) ChEDL 版本锁定 ADR-0029**；fluids / chemicals / ht 冻结至 pyproject.toml 精确版本 `==X.Y.Z`（**禁止 `>=` / `~=`**）；uv.lock 重新生成；测试断言 `import fluids; assert fluids.__version__ == "X.Y.Z"`；P5-0 批内完成，P5-1 启动前生效；升级需独立 PR + 全量回归 + ADR 更新
- **SUP-P5-PSV-001 基线批准（裁决 #23，E-01 EFFECTIVE）**：SUP-P5-PSV-001 V1.0 状态从"待评审"改为"已批准"（E-01），P5 基线生效；Task 24 (P5-0-5) 可执行
- **验收基线 1670（裁决 #24，E-02 EFFECTIVE）**：pcs_test 全量 ≥1670 passed（基线 1603 + 47 P5 核心 + 15 SUP 门禁/标准切换 + 5 ChEDL 版本锁定 — D-08）；起始基线 ≥1603（P4 末态）/ P5 验收 ≥1670（F-04 + E-02 + D-08）

**强制修正同步项**（F-01~F-09，随 D-02/D-03/D-04/D-06/D-07/D-08 + E-01/E-02 同步生效）：
- **F-01 Task 编号**：方案 A — P5-0-5 编为 **Task 24**（前置执行，与原 P5-1-1~P5-4-5 编号解耦）；新增 **Task 25 (P5-0-6)**；任务总数 24 → **25**；P5-1~P5-4 编号不变（Task 5~23），避免大量 +1 重排
- **F-02 A^0.82 数值**：见裁决 #12 五段独立断言
- **F-03 relief_summary SQL**：MAX(scenario) 字母序错误 → 改用 `DISTINCT ON (project_id, standard_profile_code) ... ORDER BY mass_flow DESC` 窗口函数；Task 18 GREEN 步骤 + 测试同步更新
- **F-04 测试基线**：全局约束 "≥1588" → "起始 ≥1603 / 验收 ≥1670"（明确区分起始基线与验收目标）
- **F-05 Architecture 段**：已同步 ChEDL 分层架构（底层 ChEDL 验证模块 + 业务逻辑层自研）
- **F-06 RECORD_TYPE_REGISTRY**：Task 1 (P5-0-1) 完成后 12 类断言；**Task 24 (P5-0-5) 完成后 13 类断言**（新增 ProjectCalculationStandardProfile）；Task 24 测试清单增加 13 类完整性断言
- **F-07 NOT NULL 迁移时序**：Task 24 migration 仅加列 + 默认值（可空）；**Task 18 新增 `p5_psv_standard_not_null.py`** 强制 NOT NULL + 存量回填 `'API' / {} / {}`；两 migration 分离
- **F-08 Task 14 typo**：formla_ref → formula_ref（已修正）
- **F-09 formula_ref 结构化**：原 `Literal["API_521_7th","GB_T_150.1_2024_附录B"]` → 结构化字段 `{standard, version, clause, ...}`（FireCaseFormulaRef / OrificeFormulaRef 等）；与 standard_refs_json 结构一致便于 lineage 对比

## Backlog（按优先级）

**P5 启动前必关闭**（用户审查关注项升级）：
- ~~ChEDL 版本锁定 ADR~~（**已转 Task 25 (P5-0-6) + ADR-0029，D-08 关闭**，P5-0 批内完成）

**P5+ 后续**：
- HTRI_VERSION_SUPPORTED 实测确认（待 P5-OPEN-001 + 公司常用版本样例）
- GPSA 算例版本核对（旋风分阈值 15%/10%/8% 验证基准来源）
- Hooper 2-K / Darby 3-K 低 Re K 值修正（P4 转入）
- `fluids.two_phase` Beggs-Brill 交叉校核
- `fluids.fittings` K_from_f 交叉校核
- P4-2-6 热损失 + 混合黏度
- CIA 引擎（hash_changed / changed_fields / STALE→CHANGE_PENDING）
- 控制阀 / PSV（V1.4 §1.2 不在 P5，P6+）
- P6（CV/RESTRICTION/FLARE_SYS/COOL_TOWER/PSYCHRO/OPEN_CHANNEL）规划另起

**SUP-P5-PSV-001 V1.0 Backlog**（P5+ / P6+）：
- **ADR-0028 Task 24 已起草**（**D-05 Proposed 状态**，与 SUP-P5-PSV-001 V1.0 同步评审）：标准 profile 配置 + StandardResolver 层 + 双路径隔离原则 + 6 道门禁 + record_hash 含 standard 字段 + GB 2011/2024 双版本 + GB 孔口表降级 + DIERS/先导式转 P5+
- **ADR-0029 Task 25 已起草**（**D-08**：ChEDL 版本锁定，Accepted）：fluids / chemicals / ht 精确版本 + 升级流程
- GB 路径两相流 DIERS 积分法实现（**D-06 转 P5+**，P5-OPEN-00W 关闭）
- GB/T 28778-2023 先导式安全阀计算模块（**D-07 转 P5+**，P5-OPEN-00V 关闭）
- GB/T 12241 标准孔口表完整录入（**D-04 转 P5+**，P5-OPEN-00Z 关闭；当前 P5 降级为按计算面积输出所需流道直径）
- CUSTOM profile 审批工作流（提交 → 复核 → 签发完整链路；当前仅 approval_json 三字段）
- 跨标准结果对比报告（同一容器 API vs GB 偏差分析）
- P6 FLARE_SYS 按标准口径汇总接口（依赖 P5-3-6 relief_summary 按项目标准汇总 + F-03 窗口函数修正）

**P5 OPEN 项决议状态**（D-02/D-03/D-04/D-06/D-07 已生效，全部关闭）：

| 编号 | 内容 | 裁决 | 决议 | 关闭 |
|---|---|---|---|---|
| P5-OPEN-00X | 工艺室 PSV 默认标准（API vs GB/HG） | D-02 | 强制项目级显式配置，禁止隐式回退 | ✅ |
| P5-OPEN-00Y | GB/T 150.1 版本（2011 vs 2024） | D-03 | 项目级可选，新项目默认 2024 | ✅ |
| P5-OPEN-00Z | GB/T 12241 孔口表完整录入 | D-04 | P5 降级，完整录入转 P5+ | ✅ |
| P5-OPEN-00W | GB 路径两相流方法（DIERS） | D-06 | 转 P5+ | ✅ |
| P5-OPEN-00V | 先导式阀（GB/T 28778）纳入 | D-07 | 转 P5+ | ✅ |

## 验收

P5 闭环判定：
1. **25 task 全部 CLOSED**（含 R1 fix 如有；F-01 方案 A：Task 1~23 主批 + Task 24/25 前置执行）
2. **pcs_test 全量 ≥1670 passed**（E-02 + D-08）
   - **基线 1603 passed**（P4 末态）+ **47 P5 核心**（**问题5 构成**：Task 5 VESSEL 10 + Task 9~12 SEP_EQUIP 12 + Task 13~18 PSV 20 + Task 19~23 HEAT 5 = 47；实施后按实际测试清单核算，误差 ±3 例）
   - **15 SUP 门禁/标准切换**（SUP-P5-PSV-001 §8.5：项目未配置 422 / API 配置 / GB 配置 / 无权限覆盖 403 / 跨标准 record_hash 不同 等 15 例）
   - **5 ChEDL 版本锁定**（Task 25：fluids / chemicals / ht 三库版本断言 + pip freeze 快照 + uv.lock 存在性 5 例）
3. ruff 0 errors
4. spec §3.2.1~§3.2.4 全部功能 + §3.3.1 性能 + §3.3.2 精度 验收通过
5. **P5-OPEN-001/002/003/004/00X/Y/Z/W/V 全部给出决议**（**问题7 扩展**）：
   - P5-OPEN-001（HTRI 版本兼容）：**默认按公司常用版本实施**（Xist_v6 / Xchanger_Suite_v8 白名单），version 字段预留；扩展性解决
   - P5-OPEN-002（Lapple 默认）：**Task 9 默认 method=Lapple 已实施**；Swift/Barth 作为可选 method 参数 → 关闭
   - P5-OPEN-003（API 2000 v7）：**默认第7版**；如验证集发现偏差回退第6版 → 关闭
   - P5-OPEN-004（焓值来自 Licensor）：**Task 21 焓值表契约已落地** → 关闭
   - P5-OPEN-00X（PSV 默认标准）：**D-02 关闭** —— 强制项目级显式配置，禁止隐式回退
   - P5-OPEN-00Y（GB/T 150.1 版本）：**D-03 关闭** —— 项目级可选，新项目默认 2024
   - P5-OPEN-00Z（GB/T 12241 孔口表）：**D-04 关闭** —— P5 降级，完整录入转 P5+
   - P5-OPEN-00W（GB 路径 DIERS）：**D-06 关闭** —— 转 P5+
   - P5-OPEN-00V（先导式阀 GB/T 28778）：**D-07 关闭** —— 转 P5+
6. ADR-0028 + ADR-0029 起草评审（**D-05**：ADR-0028 与 SUP-P5-PSV-001 V1.0 独立评审，SUP 已批准 E-01；ADR-0029 独立评审）
7. spec §3.2.1 K 因子 SI 修订已提交（**D-01**）
8. P5 验收报告（PCS-P5-CLOSE-REPORT.md）落盘