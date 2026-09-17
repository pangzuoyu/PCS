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

export type PsvStandardProfileCode = 'API' | 'GB' | 'CUSTOM';

export type ReliefScenario =
  | 'FIRE'
  | 'CLOSED_VALVE'
  | 'REACTION_RUNAWAY'
  | 'THERMAL_EXPANSION';

export type DesignStage = 'BASIC' | 'DETAIL';

export type ReliefPhase = 'GAS' | 'LIQUID' | 'TWO_PHASE';

export type OrificeSize =
  | 'D' | 'E' | 'F' | 'G' | 'H' | 'J' | 'K' | 'L'
  | 'M' | 'N' | 'P' | 'Q' | 'R' | 'T';

// SUP-P5-PSV-002 V1.14 §3.2：阀体型式 / 阀体材料 / 波纹管材料 / 孔口系列 / 背压类型 / 介质 / 先导温度等级 / 爆破膜位置 / 法兰等级 / Kb 来源 / 阀体品牌
export type PsvValveType =
  | 'SPRING_LOADED'      // 弹簧载荷式（默认）
  | 'BALANCED_BELLOWS'   // 平衡波纹管式
  | 'PILOT_OPERATED'     // 先导式（P5 拦截 G7）
  | 'RUPTURE_DISC';      // 爆破膜式（P5 拦截 G8）

export type PsvBodyMaterial =
  | 'CARBON_STEEL'       // 碳钢
  | 'SS304'
  | 'SS316'
  | 'SS316L'
  | 'ALLOY';             // 合金钢

export type PsvBellowsMaterial =
  | 'HASTELLOY_C276'
  | 'SS316L'
  | 'INCONEL_625'
  | 'INCONEL_718'
  | 'ALLOY_400'
  | 'ALLOY_C22';

export type PsvBackPressureType = 'BUILT_UP' | 'SUPERIMPOSED';

export type PsvMedium = 'GAS' | 'VAPOR' | 'LIQUID' | 'TWO_PHASE';

export type PsvPilotTempClass = 'GENERAL' | 'HIGH_TEMP' | 'CRYOGENIC';

export type PsvRuptureDiscPosition = 'UPSTREAM' | 'DOWNSTREAM' | 'NONE';

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
export type PsvValveBrand = string;

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

export interface FireScenarioParams extends ScenarioParamsBase {
  kind: 'FIRE';
  D_m: number;
  H_m: number;
  liquid_level_fraction: number;
  environment_factor_F: number;
  h_fg_j_per_kg: number;
}

export interface ClosedValveScenarioParams extends ScenarioParamsBase {
  kind: 'CLOSED_VALVE';
  V_pipe_m3: number;
  rho_L_kg_m3: number;
  t_isolation_s: number;
}

export interface ReactionRunawayScenarioParams extends ScenarioParamsBase {
  kind: 'REACTION_RUNAWAY';
  Q_rxn_w: number;
  fraction_to_valve: number;
}

export interface ThermalExpansionScenarioParams extends ScenarioParamsBase {
  kind: 'THERMAL_EXPANSION';
  V_L_m3: number;
  rho_L_kg_m3: number;
  beta_per_k: number;
  delta_T_k: number;
  t_heat_s: number;
}

export type ScenarioParams =
  | FireScenarioParams
  | ClosedValveScenarioParams
  | ReactionRunawayScenarioParams
  | ThermalExpansionScenarioParams;

// ---------------------------------------------------------------------------
// sizing_params（GAS / LIQUID / TWO_PHASE 三相态）
// ---------------------------------------------------------------------------

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
}

// ---------------------------------------------------------------------------
// POST /api/v1/psv/calculate 输出
// ---------------------------------------------------------------------------

export interface PsvAggregateResult {
  dominant_scenario: ReliefScenario;
  case_count: number;
  per_scenario_json: Record<string, unknown>;
}

export interface PsvReliefAreaResult {
  area_required_m2: number;
  medium: ReliefPhase;
  formula_ref: FormulaRef;
  omega_method?: 'ω';
  orifice_table_status?: 'incomplete_fallback';
}

export interface PsvOrificeResult {
  selected_size: OrificeSize;
  actual_area_m2: number;
  inlet_size: string;
  outlet_size: string;
}

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

export interface UpsertPsvStandardProfileRequest {
  profile_code: PsvStandardProfileCode;
  standard_refs_json: Record<string, FormulaRef>;
  approval_json?: Record<string, unknown>;
  approved_by?: string;
}