/**
 * PSV 模块类型（P5-3 frontend / Task 1）。
 *
 * SPEC §7.11.5（V1.2 commit 7db5ea5）+ 后端 OpenAPI（commit 93627a7）：
 * - POST /api/v1/psv/calculate：单次 relief_scenario + scenario_params + sizing_params
 * - GET/POST /api/v1/projects/{pid}/psv/standard-profile
 * - 4 种 relief_scenario 路由：FIRE / CLOSED_VALVE / REACTION_RUNAWAY / THERMAL_EXPANSION
 * - design_stage BASIC ≤25 列 / DETAIL 完整
 * - 标准字段三件套：standard_profile_code / standard_refs_json / formula_ref_json
 * - 出口流 source_type = PSV_CALCULATED
 */

// ---------------------------------------------------------------------------
// 枚举 / 字面量
// ---------------------------------------------------------------------------

/** PSV 项目标准集代号：API（520/521 美标）/ GB（12241 国标）/ CUSTOM（用户自定义）。 */
export type PsvStandardProfileCode = 'API' | 'GB' | 'CUSTOM';

/** 泄放场景 4 类：火灾 FIRE / 出口阀关断 CLOSED_VALVE / 反应失控 REACTION_RUNAWAY / 热膨胀 THERMAL_EXPANSION（API 521 9th §3.4~3.7）。 */
export type ReliefScenario =
  | 'FIRE'
  | 'CLOSED_VALVE'
  | 'REACTION_RUNAWAY'
  | 'THERMAL_EXPANSION';

/** 设计阶段：基础设计 BASIC ≤25 列 / 详细设计 DETAIL 完整（驱动一览表列切换）。 */
export type DesignStage = 'BASIC' | 'DETAIL';

/** 泄放相态：气相 GAS / 液相 LIQUID / 两相 TWO_PHASE（决定 sizing_params 路径 + 公式 dispatch）。 */
export type ReliefPhase = 'GAS' | 'LIQUID' | 'TWO_PHASE';

/** API 520 孔口代号（D~T 共 14 档，按面积递增）。 */
export type OrificeSize =
  | 'D' | 'E' | 'F' | 'G' | 'H' | 'J' | 'K' | 'L'
  | 'M' | 'N' | 'P' | 'Q' | 'R' | 'T';

// SUP-P5-PSV-002 V1.14 §3.2：阀体型式 / 阀体材料 / 波纹管材料 / 孔口系列 / 背压类型 / 介质 / 先导温度等级 / 爆破膜位置 / 法兰等级 / Kb 来源 / 阀体品牌
/** PSV 阀体型式：弹簧载荷式 SPRING_LOADED（默认）/ 平衡波纹管式 BALANCED_BELLOWS / 先导式 PILOT_OPERATED（P5 拦截 G7）/ 爆破膜式 RUPTURE_DISC（P5 拦截 G8）。 */
export type PsvValveType =
  | 'SPRING_LOADED'      // 弹簧载荷式（默认）
  | 'BALANCED_BELLOWS'   // 平衡波纹管式
  | 'PILOT_OPERATED'     // 先导式（P5 拦截 G7）
  | 'RUPTURE_DISC';      // 爆破膜式（P5 拦截 G8）

/** PSV 阀体材料：碳钢 CARBON_STEEL / SS304 / SS316 / SS316L / 合金钢 ALLOY（5 档，§3.7 兼容矩阵 dispatch）。 */
export type PsvBodyMaterial =
  | 'CARBON_STEEL'       // 碳钢
  | 'SS304'
  | 'SS316'
  | 'SS316L'
  | 'ALLOY';             // 合金钢

/** PSV 波纹管材料（6 种 SUP-P5-PSV-002 V1.14 §3.8 兼容矩阵）。 */
export type PsvBellowsMaterial =
  | 'HASTELLOY_C276'
  | 'SS316L'
  | 'INCONEL_625'
  | 'INCONEL_718'
  | 'ALLOY_400'
  | 'ALLOY_C22';

/** PSV 背压类型：BUILT_UP 累积背压（>10% 需 Kb 修正）/ SUPERIMPOSED 叠加背压。 */
export type PsvBackPressureType = 'BUILT_UP' | 'SUPERIMPOSED';

/** PSV 适用介质：气相 GAS / 蒸汽 VAPOR / 液相 LIQUID / 两相 TWO_PHASE。 */
export type PsvMedium = 'GAS' | 'VAPOR' | 'LIQUID' | 'TWO_PHASE';

/** 先导式 PSV 温度等级：常规 / 高温 / 低温（OPEN-18 待补）。 */
export type PsvPilotTempClass = 'GENERAL' | 'HIGH_TEMP' | 'CRYOGENIC';

/** 爆破膜相对阀体位置：上游 / 下游 / 无（NONE = 不装爆破膜）。 */
export type PsvRuptureDiscPosition = 'UPSTREAM' | 'DOWNSTREAM' | 'NONE';

/** PSV 法兰等级（ASME B16.5 6 档）：150# / 300# / 600# / 900# / 1500# / 2500#。 */
export type PsvFlangeClass =
  | '150#'
  | '300#'
  | '600#'
  | '900#'
  | '1500#'
  | '2500#';

// §4.3 Kb 来源标识（'none' = 标准定义 1.0；'mixed:{mfr1}+{mfr2}[+{mfr3}]' = 多厂商混用）
// 与后端 PsvKbSource Literal（valve_selection_types.py:96-109）完全对齐：
// - 含 Farris / Crosby（V1.14 P2-1 扩品牌集）
// - 含 3 厂商混用（mixed:LESER+Consolidated+Anderson_Greenwood）
/** Kb 来源标识（与后端 valve_selection_types.py:96-109 完全对齐）：none = 标准定义 1.0；manufacturer:{mfr} = 单厂商曲线；mixed:{mfr1}+{mfr2}[+{mfr3}] = 多厂商混用；api520_fig30 / en4126 = 标准曲线兜底。 */
export type PsvKbSource =
  | 'none'
  | 'manufacturer:LESER'
  | 'manufacturer:Consolidated'
  | 'manufacturer:Anderson_Greenwood'
  | 'manufacturer:Farris'
  | 'manufacturer:Crosby'
  | 'mixed:LESER+Consolidated'
  | 'mixed:LESER+Anderson_Greenwood'
  | 'mixed:Consolidated+Anderson_Greenwood'
  | 'mixed:LESER+Consolidated+Anderson_Greenwood'
  | 'api520_fig30'
  | 'en4126';

// §4.1 V1.14 P2-1：valve_brand 自由字符串（不枚举）；已知品牌见 _KB_DATA
//    后端 Warning + 回退覆盖/保守优先策略
/** PSV 阀体品牌：自由字符串（不枚举；§4.1 V1.14 P2-1 扩展）；已知品牌在 _KB_DATA；后端 Warning + 回退覆盖/保守优先策略。 */
export type PsvValveBrand = string;

/** 公式引用三元组：标准代号（API 520/521/...）+ 版本号（9th/10th/...）+ 条款号（§3.4/§C.2.2/...）。 */
export interface FormulaRef {
  standard: string;
  version: string;
  clause: string;
}

// ---------------------------------------------------------------------------
// scenario_params 路由联合（4 种）
// ---------------------------------------------------------------------------

interface ScenarioParamsBase {
  kind: ReliefScenario;
}

/** 火灾场景参数：容器直径 D + 受热高度 H + 液位分率 + 环境因子 F + 汽化潜热 h_fg（API 521 9th §3.4 火灾 Wetted-Method）。 */
export interface FireScenarioParams extends ScenarioParamsBase {
  kind: 'FIRE';
  D_m: number;
  H_m: number;
  liquid_level_fraction: number;
  environment_factor_F: number;
  h_fg_j_per_kg: number;
}

/** 出口阀关断场景参数：管段容积 V_pipe + 液相密度 + 隔离时间。 */
export interface ClosedValveScenarioParams extends ScenarioParamsBase {
  kind: 'CLOSED_VALVE';
  V_pipe_m3: number;
  rho_L_kg_m3: number;
  t_isolation_s: number;
}

/** 反应失控场景参数：反应放热功率 Q_rxn + 阀门分率 fraction_to_valve。 */
export interface ReactionRunawayScenarioParams extends ScenarioParamsBase {
  kind: 'REACTION_RUNAWAY';
  Q_rxn_w: number;
  fraction_to_valve: number;
}

/** 热膨胀场景参数：液相容积 + 密度 + 体膨胀系数 beta + 温升 delta_T + 加热时间。 */
export interface ThermalExpansionScenarioParams extends ScenarioParamsBase {
  kind: 'THERMAL_EXPANSION';
  V_L_m3: number;
  rho_L_kg_m3: number;
  beta_per_k: number;
  delta_T_k: number;
  t_heat_s: number;
}

/** 4 场景参数并集（按 kind 字段区分）；后端 PSV calculate 按此 dispatch。 */
export type ScenarioParams =
  | FireScenarioParams
  | ClosedValveScenarioParams
  | ReactionRunawayScenarioParams
  | ThermalExpansionScenarioParams;

// ---------------------------------------------------------------------------
// sizing_params（GAS / LIQUID / TWO_PHASE 三相态）
// ---------------------------------------------------------------------------

/** PSV 选型入参：泄放质量流量 + 相态 + 背压 + 定压 + GAS/TWO_PHASE 路径（温度/分子量/Z/k）+ LIQUID 路径（液相密度）。 */
export interface SizingParams {
  relief_mass_flow_kgs: number;
  phase: ReliefPhase;
  P_back_pa: number;
  P_set_pa: number;
  // GAS / TWO_PHASE 路径
  T_k?: number;
  M_kg_per_mol?: number;
  Z?: number;
  k_cp_ratio?: number;
  // LIQUID 路径
  rho_L_kg_m3?: number;
}

// ---------------------------------------------------------------------------
// POST /api/v1/psv/calculate 输入
// ---------------------------------------------------------------------------

/** POST /psv/calculate 请求：源流 ID + 泄放场景 + scenario_params + sizing_params + 可选 design_stage + SUP-P5-PSV-002 V1.14 §4.1 阀体选型 18 字段 + H-P5-4d CDTP/G15 三字段（向后兼容 extra='ignore'）。 */
export interface PsvCalculateRequest {
  source_stream_id: string;
  relief_scenario: ReliefScenario;
  scenario_params: ScenarioParams;
  sizing_params: SizingParams;
  design_stage?: DesignStage;
  // SUP-P5-PSV-002 V1.14 §4.1 阀体选型 18 字段
  // 已有 3 字段（blowdown_fraction / inlet_size / outlet_size）+ 新增 15 字段
  // 后端 Pydantic v2 extra='ignore' 静默忽略缺失字段；老请求格式仍兼容（§7.2）
  blowdown_fraction?: number;
  inlet_size?: string | null;
  outlet_size?: string | null;
  valve_type?: PsvValveType;
  body_material?: PsvBodyMaterial;
  bellows_material?: PsvBellowsMaterial | null;
  medium?: PsvMedium;
  flange_class?: PsvFlangeClass;
  back_pressure_pct?: number | null;
  back_pressure_type?: PsvBackPressureType;
  overpressure_pct?: number;
  orifice_override?: OrificeSize | null;
  valve_brand?: PsvValveBrand | null;
  pilot_temperature_c?: number | null;
  pilot_temp_class?: PsvPilotTempClass;
  rupture_disc_position?: PsvRuptureDiscPosition;
  fire_protection?: boolean;
  service_note?: string | null;
  // H-P5-4d-2 / H-P5-4d-3 — HIGH fe — CDTP 修正 + G15 Q/R/T 高温低分子量校验
  superimposed_pressure_pa?: number | null;
  fluid_temperature_c?: number | null;
  molecular_weight?: number | null;
}

// ---------------------------------------------------------------------------
// POST /api/v1/psv/calculate 输出
// ---------------------------------------------------------------------------

/** PSV 多场景聚合结果：主导场景（流量最大）+ 场景数 + 各场景明细 JSON（前端聚合表渲染）。 */
export interface PsvAggregateResult {
  dominant_scenario: ReliefScenario;
  case_count: number;
  per_scenario_json: Record<string, unknown>;
}

/** PSV 泄放面积结果：所需面积 m² + 介质相态 + 公式引用 + 可选 ω 方法（C7-b Annex C.2.2）+ 可选孔口表兜底标记（orifice_table 不全时填 incomplete_fallback）。 */
export interface PsvReliefAreaResult {
  area_required_m2: number;
  medium: ReliefPhase;
  formula_ref: FormulaRef;
  omega_method?: 'ω';
  orifice_table_status?: 'incomplete_fallback';
}

/** PSV 选型孔口结果：选中尺寸 + 实际面积 + 进出口口径。 */
export interface PsvOrificeResult {
  selected_size: OrificeSize;
  actual_area_m2: number;
  inlet_size: string;
  outlet_size: string;
}

/** PSV 计算结果主体：泄放场景 + 聚合结果 + 泄放面积 + 选型孔口 + 定压等。 */
export interface PsvResultBody {
  relief_scenario: ReliefScenario;
  aggregate: PsvAggregateResult;
  relief_area: PsvReliefAreaResult;
  orifice: PsvOrificeResult;
  set_pressure_pa: number;
  blowdown_fraction: number;
  standard_profile_code: PsvStandardProfileCode;
  standard_refs_json: Record<string, FormulaRef>;
  formula_ref_json: {
    dominant_scenario: string;
    fire_case_or_other: FormulaRef;
    relief_area: FormulaRef;
    orifice: FormulaRef;
  };
  // SUP-P5-PSV-002 V1.14 §4.6 响应扩展
  // 后端落地 OPEN-10 后填充；前端先行渲染（缺字段时静默隐藏）
  valve_type?: PsvValveType;
  body_material?: PsvBodyMaterial;
  bellows_material?: PsvBellowsMaterial | null;
  inlet_size?: string | null;
  outlet_size?: string | null;
  flange_class?: PsvFlangeClass;
  back_pressure_pct?: number | null;
  back_pressure_type?: PsvBackPressureType;
  overpressure_pct?: number;
  kb_factor?: number | null;
  kb_source?: PsvKbSource | null;
  valve_brand?: PsvValveBrand | null;
  cdtp_applied?: boolean;
  rupture_disc_kc?: number | null;
  warnings?: string[];
}

/** POST /psv/calculate 响应：calc_id + calc_type + 完整 result body + 出口流 ID + record_hash + 签名状态。 */
export interface PsvCalculateResponse {
  calc_id: string;
  calc_type: 'PSV';
  record_hash: string;
  stream_id: string;
  lineage_ids: string[];
  outlet_stream_id: string | null;
  outlet_stream_name: string | null;
  result: PsvResultBody;
}

// ---------------------------------------------------------------------------
// 项目标准配置（GET/POST /projects/{pid}/psv/standard-profile）
// ---------------------------------------------------------------------------

/** GET /projects/{pid}/psv/standard-profile：项目级 PSV 标准集（profile_id + 项目 + 学科 PSV + 标准代号 + 子标准/版本/条款映射 + 审批 JSON + 默认/迁移默认双标志 + 生效起止 + 审批人 + 时间戳）。 */
export interface PsvStandardProfile {
  profile_id: string;
  project_id: string;
  discipline: 'PSV';
  profile_code: PsvStandardProfileCode;
  standard_refs_json: Record<string, FormulaRef>;
  approval_json: Record<string, unknown> | null;
  is_default: boolean;
  migrated_default: boolean;
  effective_from: string;
  effective_to: string | null;
  approved_by: string | null;
  created_at: string;
  updated_at: string;
}

/** POST /psv/standard-profile 请求：标准集代号 + 子标准/版本/条款映射 + 审批信息。 */
export interface UpsertPsvStandardProfileRequest {
  profile_code: PsvStandardProfileCode;
  standard_refs_json: Record<string, FormulaRef>;
  approval_json?: Record<string, unknown>;
  approved_by?: string;
}