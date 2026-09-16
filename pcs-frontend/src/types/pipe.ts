/**
 * PIPE 模块类型（P45-3-5 / Task 32）。
 *
 * SPEC §7.11.2：
 * - 设计阶段 BASIC / DETAIL
 * - 输入：物流 + 管道号 + 长度 + 起终点 + 管件 + 设计条件 + 等级 + 绝热 + 粗糙度 + 许用压降
 * - 输出：管径 / 壁厚 / 压降 / 流速 / 流型 / 两相流子结果
 * - 一览表行（41 列，design_stage 切换）
 *
 * TODO(api-migration): 当前为 V1 极简版前端 mock props shape；PipeCalculate
 * 端点（P5-1）冻结后由 src/types/api.d.ts 替换。
 */

export type PipeDesignStage = 'BASIC' | 'DETAIL';

export interface PipeFitting {
  type: string;
  quantity: number;
  size: string;
}

export interface PipeInput {
  stream_id: string;
  pipe_no: string;
  length_m: number;
  start_point: string;
  end_point: string;
  pid_ref?: string;
  fittings: PipeFitting[];
  design_pressure_mpa: number;
  design_temperature_c: number;
  corrosion_allowance_mm: number;
  pipe_class_id: string;
  insulation_code?: string;
  insulation_thickness_mm?: number;
  heat_trace?: boolean;
  roughness_mm: number;
  allowable_dp_kpa: number;
}

export type TwoPhasePattern =
  | 'STRATIFIED' | 'WAVE' | 'ANNULAR' | 'SLUG' | 'MIST' | 'NONE';

export interface TwoPhaseResult {
  pattern: Exclude<TwoPhasePattern, 'NONE'>;
  liquid_holdup: number;
}

export interface PipeResult {
  diameter_mm: number;
  wall_thickness_mm: number;
  dp_kpa: number;
  velocity_m_s: number;
  flow_pattern: TwoPhasePattern;
  two_phase?: TwoPhaseResult;
}

/** 管道一览表行（V1 极简：BASIC 15 列 / DETAIL 扩展至 25 列）。 */
export interface PipeLineListRow {
  seq: number;
  pipe_no: string;
  size: string;
  material: string;
  fluid_code: string;
  fluid_name: string;
  phase: string;
  fluid_class: string;
  toxicity: string;
  pipe_class: string;
  /** BASIC 截止 */
  design_pressure_mpa: number;
  design_temperature_c: number;
  /** DETAIL 扩展 */
  length_m?: number;
  dp_kpa?: number;
  velocity_m_s?: number;
  pipe_class_detail?: string;
  insulation_code?: string;
  start_point?: string;
  end_point?: string;
  pid_ref?: string;
  sign_status?: string;
  updated_by?: string;
  updated_at?: string;
}