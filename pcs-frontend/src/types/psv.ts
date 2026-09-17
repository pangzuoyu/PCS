/**
 * PSV 模块类型（P5-3-6 / Task 18）。
 *
 * SPEC §7.11.5：
 * - PSV 标准 API / GB / CUSTOM（项目配置）
 * - 4 端点：relief / area / orifice / standards
 * - 标准字段三列：standard_profile_code / standard_refs_json / formula_ref_json
 * - 多工况叠加（FIRE / CLOSED_VALVE / REACTION_RUNAWAY / THERMAL_EXPANSION）
 */

export type PsvStandardProfileCode = 'API' | 'GB' | 'CUSTOM';

export type ReliefScenario =
  | 'FIRE'
  | 'CLOSED_VALVE'
  | 'REACTION_RUNAWAY'
  | 'THERMAL_EXPANSION';

export type ValveType = 'SPRING_LOADED' | 'PILOT_OPERATED' | 'BALANCED_BELLOW';

export interface FireCaseInput {
  source_stream_id: string;
  vessel_type: 'VERTICAL' | 'HORIZONTAL';
  D_m: number;
  H_m: number;
  liquid_level_fraction: number;
  environment_factor_F: number;
  h_fg_input_kj_per_kg: number;
}

export interface FireCaseResult {
  wetted_area_m2: number;
  heat_input_w: number;
  relief_mass_flow_kgs: number;
  relief_volume_flow_m3s: number;
  h_fg_j_per_kg: number;
  c_factor: number;
  F_factor: number;
  formula_ref: {
    standard: string;
    version: string;
    clause: string;
  };
}

export interface ClosedValveInput {
  source_stream_id: string;
  pump_flow_m3_s: number;
  rho_kg_m3: number;
  beta: number;
}

export interface ThermalExpansionInput {
  source_stream_id: string;
  V_m3: number;
  rho_kg_m3: number;
  beta: number;
  dT_K: number;
  t_s: number;
}

export interface ReliefResult {
  scenario: ReliefScenario;
  mass_flow_kgs: number;
  volume_flow_m3s: number;
  formula_ref: Record<string, string>;
}

export interface ReliefAggregateResult {
  max_mass_flow_kgs: number;
  max_volume_flow_m3s: number;
  max_scenario: ReliefScenario;
  per_scenario_json: ReliefResult[];
}

export interface ReliefAreaInput {
  source_equipment_id: string;
  mass_flow_kgs: number;
  medium: 'GAS' | 'VAPOR' | 'LIQUID' | 'TWO_PHASE';
  pressure_pa: number;
  temperature_k: number;
  Z: number;
  M_kg_kmol: number;
  rho_kg_m3?: number;
  dP_pa?: number;
  k?: number;
  omega_method?: 'single_point' | 'two_point' | 'direct_integration';
}

export interface ReliefAreaResult {
  area_m2: number;
  medium: ReliefAreaInput['medium'];
  formula_ref: Record<string, string>;
  omega_method?: ReliefAreaInput['omega_method'];
}

export interface OrificeResult {
  selected_orifice: string;
  orifice_area_m2: number;
  required_diameter_mm?: number;
  formula_ref: Record<string, string>;
}

export interface PsvStandardRef {
  standard_code: string;
  version: string;
  clause?: string;
}

export interface PsvStandardProfile {
  profile_code: PsvStandardProfileCode;
  standard_refs_json: Record<string, PsvStandardRef>;
  approval_json?: Record<string, unknown>;
  approved_by?: string;
  is_default: boolean;
}

export interface PsvCalculateReliefRequest {
  source_stream_id: string;
  scenarios: Array<{
    scenario: ReliefScenario;
    params: FireCaseInput | ClosedValveInput | ThermalExpansionInput;
  }>;
  valve_type?: ValveType;
  override_standard?: PsvStandardProfileCode;
}

export interface PsvCalculateReliefResponse {
  calc_id: string;
  aggregate: ReliefAggregateResult;
  record_hash: string;
  standard_profile_code: PsvStandardProfileCode;
}