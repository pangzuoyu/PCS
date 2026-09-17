/**
 * VESSEL 模块类型（P5-1-4 / Task 5）。
 *
 * SPEC §7.11.3 + 与后端 OpenAPI schema 对齐（app/api/v1/vessel.py）：
 * - CalculateRequest.source_stream_id + sizing{SizingInputSchema} + hydraulics{HydraulicsInputSchema}
 * - 设计阶段 BASIC / DETAIL
 * - 容器类型 VERTICAL / HORIZONTAL / WITH_DEMISTER
 * - sizing 输出：V_max / D_min / 持液量 / check_result / confidence
 * - hydraulics 输出：Q_orifice / Q_overflow / t_drainage_min / orientation_warning
 * - 与 vessel_results ORM 落库对齐（P5-1-4 input_json / output_json 双轨）
 *
 * V1.0 SPEC 详细字段未纳入；与 plan PCS-PLAN-P5-DEVICE-EQUIPMENT.md 一致；
 * SPEC 修订待 P5-1-4 闭环后追加 §7.11.3 详细字段章节。
 */

export type VesselType = 'VERTICAL' | 'HORIZONTAL' | 'WITH_DEMISTER';

export type VesselOrientation = 'vertical' | 'horizontal';

export type VesselCheckResult = 'PASS' | 'WARNING' | 'FAIL';

export type VesselConfidence = 'HIGH' | 'MEDIUM' | 'LOW';

export interface VesselSizing {
  vessel_type: VesselType;
  rho_L_kg_m3: number;
  rho_V_kg_m3: number;
  liquid_flow_m3_s: number;
  vapor_flow_m3_s: number;
  /** 0 = 按 vessel_type 默认区间中值 */
  residence_time_min: number;
  /** SI 物理范围 0.01 ~ 1.0 m/s */
  K_factor_ms: number;
}

export interface VesselHydraulics {
  D_m: number;
  L_m: number;
  h0_m: number;
  d_orifice_m: number;
  Cd_orifice: number;
  Q_in_liquid_m3_s: number;
  d_overflow_m: number;
  h_overflow_m: number;
  Cd_overflow: number;
  /** 触发 orientation_warning 的关键字段 */
  orientation: VesselOrientation;
  thermal_breathing_factor: number;
}

export interface VesselCalculateRequest {
  source_stream_id: string;
  sizing: VesselSizing;
  hydraulics: VesselHydraulics;
}

export interface VesselCalculateResponse {
  calc_id: string;
  calc_type: 'VESSEL';
  record_hash: string;
  stream_id: string;
  lineage_ids: string[];
  result: Record<string, unknown>;
  outlet_stream_id: string;
  outlet_stream_name: string;
}