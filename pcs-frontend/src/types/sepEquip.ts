/**
 * SEP_EQUIP 模块类型（P5-2-4 / Task 12）。
 *
 * SPEC §7.11.4：
 * - 5 设备类型：Cyclone / MistEliminator / Gravity / Vane / Fiber
 * - 每种设备对应独立字段（dispatcher 构造对应 dataclass）
 * - 与 sep_equip_results ORM 落库对齐
 */

export type SepEquipDeviceType =
  | 'CYCLONE'
  | 'MIST_ELIMINATOR'
  | 'GRAVITY'
  | 'VANE'
  | 'FIBER';

export type CycloneMethod = 'LAPPLE' | 'SWIFT' | 'BARTH';
export type PadType = 'STANDARD' | 'HIGH_EFFICIENCY';
export type SeparatorType = 'PLAIN' | 'VANE' | 'FIBER';
export type Region = 'STOKES' | 'INTERMEDIATE' | 'NEWTON';

export interface CycloneParams {
  D_cylinder_m: number;
  D_exhaust_m: number;
  a_inlet_m: number;
  b_inlet_m: number;
  V_in_ms: number;
  rho_kg_m3: number;
  mu_pa_s: number;
  rho_particle_kg_m3: number;
  N_effective_turns: number;
  method: CycloneMethod;
}

export interface MistEliminatorParams {
  pad_type: PadType;
  Q_gas_m3_s: number;
  D_cylinder_m: number;
  rho_gas_kg_m3: number;
  mu_gas_pa_s: number;
  liquid_load_kg_m3: number;
}

export interface GravitySeparatorParams {
  d_particle_m: number;
  rho_particle_kg_m3: number;
  rho_fluid_kg_m3: number;
  mu_fluid_pa_s: number;
  height_setting_m: number;
  horizontal_velocity_ms: number;
}

export interface SepEquipCalculateRequest {
  source_stream_id: string;
  device_type: SepEquipDeviceType;
  params:
    | CycloneParams
    | MistEliminatorParams
    | GravitySeparatorParams;
}

export interface SepEquipCalculateResponse {
  calc_id: string;
  calc_type: SepEquipDeviceType;
  record_hash: string;
  stream_id: string;
  lineage_ids: string[];
  result: Record<string, unknown>;
  outlet_stream_id: string;
  outlet_stream_name: string;
}