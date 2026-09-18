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

/** 容器安装方位：立式 vertical / 卧式 horizontal（影响持液量/水力学默认区间）。 */
export type VesselOrientation = 'vertical' | 'horizontal';

/** 容器校核结果：通过 PASS / 警告 WARNING / 不通过 FAIL（驱动 Card 状态色 + Result Alert）。 */
export type VesselCheckResult = 'PASS' | 'WARNING' | 'FAIL';

/** 容器选型置信度：高 HIGH / 中 MEDIUM / 低 LOW（输入缺失字段或区间外推时降级）。 */
export type VesselConfidence = 'HIGH' | 'MEDIUM' | 'LOW';

/** 容器选型入参：容器类型 + 气液密度 + 双流量 + 停留时间（0 = 默认中值）+ K 因子（0.01~1.0 m/s）。 */
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

/** 容器水力学入参：筒径/长/初液位 + 孔径/Cd + 进液流量 + 溢流孔径/高度/Cd + 方位 + 热呼吸因子。 */
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

/** POST /vessel/calculate 请求：源流 ID + 选型入参 + 水力学入参（sizing/hydraulics 分别承载）。 */
export interface VesselCalculateRequest {
  source_stream_id: string;
  sizing: VesselSizing;
  hydraulics: VesselHydraulics;
}

/** POST /vessel/calculate 响应：calc_id + 类型 + record_hash + 源流 ID + lineage + 结果 dict + 出口流 ID/名。 */
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