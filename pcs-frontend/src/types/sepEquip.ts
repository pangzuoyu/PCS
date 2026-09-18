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

/** 旋风分离器切割粒径计算法：LAPPLE（经典）/ SWIFT（修正）/ BARTH（工业级）。 */
export type CycloneMethod = 'LAPPLE' | 'SWIFT' | 'BARTH';
/** 除雾器填料类型：标准 STANDARD / 高效 HIGH_EFFICIENCY。 */
export type PadType = 'STANDARD' | 'HIGH_EFFICIENCY';
/** 重力分离器内部型式：板式 PLAIN / 百叶 VANE / 纤维 FIBER。 */
export type SeparatorType = 'PLAIN' | 'VANE' | 'FIBER';
/** 重力分离沉降区域：斯托克斯 STOKES / 中间区 INTERMEDIATE / 牛顿 NEWTON（按 Re 数划分）。 */
export type Region = 'STOKES' | 'INTERMEDIATE' | 'NEWTON';

/** 旋风分离器参数：筒径/排气管径 + 进出口宽高 + 入口气速 + 气/粒密度 + 动力粘度 + 有效圈数 + 计算法（LAPPLE/SWIFT/BARTH）。 */
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

/** 除雾器参数：填料类型 + 气体流量 + 筒径 + 气体密度/粘度 + 液体负荷。 */
export interface MistEliminatorParams {
  pad_type: PadType;
  Q_gas_m3_s: number;
  D_cylinder_m: number;
  rho_gas_kg_m3: number;
  mu_gas_pa_s: number;
  liquid_load_kg_m3: number;
}

/** 重力分离器参数：粒径 + 粒/流体密度 + 流体粘度 + 高度设定 + 水平流速。 */
export interface GravitySeparatorParams {
  d_particle_m: number;
  rho_particle_kg_m3: number;
  rho_fluid_kg_m3: number;
  mu_fluid_pa_s: number;
  height_setting_m: number;
  horizontal_velocity_ms: number;
}

/** POST /sep-equip/calculate 请求：源流 + 设备类型 + 对应类型参数（按 device_type 区分 params）。 */
export interface SepEquipCalculateRequest {
  source_stream_id: string;
  device_type: SepEquipDeviceType;
  params:
    | CycloneParams
    | MistEliminatorParams
    | GravitySeparatorParams;
}

/** POST /sep-equip/calculate 响应：calc_id + 设备类型 + record_hash + 源流 ID + lineage + result + 出口流 ID/名。 */
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