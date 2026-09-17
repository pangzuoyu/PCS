/**
 * VESSEL 模块类型（P5-1-4 / Task 5）。
 *
 * SPEC §7.11.3：
 * - 设计阶段 BASIC / DETAIL
 * - 容器类型 VERTICAL / HORIZONTAL / WITH_DEMISTER
 * - 输入：物流 + 容器类型 + 工艺参数（密度/流量/停留时间）+ K 因子（CONFIG + 手动覆盖）
 * - 输出：V_max / D_min / 持液量 / check_result / confidence / orientation_warning
 * - 与 vessel_results ORM 落库对齐（P5-1-4 input_json / output_json 双轨）
 */

export type VesselType = 'VERTICAL' | 'HORIZONTAL' | 'WITH_DEMISTER';

export type VesselCheckResult = 'PASS' | 'WARNING' | 'FAIL';

export type VesselConfidence = 'HIGH' | 'MEDIUM' | 'LOW';

export interface VesselInput {
  source_stream_id: string;
  vessel_type: VesselType;
  rho_L_kg_m3: number;
  rho_V_kg_m3: number;
  liquid_flow_m3_s: number;
  vapor_flow_m3_s: number;
  residence_time_min: number;
  K_factor_ms: number;
}

export interface VesselResult {
  V_max_ms: number;
  D_min_m: number;
  liquid_volume_m3: number;
  vessel_type: VesselType;
  K_factor_ms: number;
  residence_time_min: number;
  check_result: VesselCheckResult;
  confidence: VesselConfidence;
  orientation_warning?: string;
}

export interface VesselCalculateResponse {
  calc_id: string;
  calc_type: 'VESSEL';
  record_hash: string;
  stream_id: string;
  lineage_ids: string[];
  result: VesselResult;
  outlet_stream_id: string;
  outlet_stream_name: string;
}