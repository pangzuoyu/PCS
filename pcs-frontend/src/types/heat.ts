/**
 * HEAT 模块类型（P5-4 frontend / Task 1）。
 *
 * SPEC §7.11.6（V1.3 P5-4 闭环后追加）+ 后端 OpenAPI（commit 96165e1）：
 * - POST /api/v1/heat/import-htri（multipart/form-data）→ ImportHtriResponse 201
 * - GET /api/v1/heat/{heat_id} → HeatResultResponse 200
 * - POST /api/v1/heat/{heat_id}/weight-estimate → WeightEstimateResponse 200
 *
 * 设计要点：
 * - 设计阶段单层（无 BASIC/DETAIL 分级；HeatResult ORM 无 design_stage 字段）
 * - 出口流 source_type=HEAT_CALCULATED + change_type=HEAT_EXCHANGE
 * - 9 段重量 segments（5 段壳体 + tube/baffle/channels + shell_total）
 * - input_json / output_json 双轨（output_json 含 total_weight_kg / weight_segments，P7 UTIL 消费）
 * - ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与 psv / vessel 一致）
 * - 错误码：HEAT_INPUT_ERROR 422 / HEAT_NOT_FOUND 404 / HEAT_PROJECT_MISMATCH 422 /
 *         SIM_STREAM_NOT_FOUND 404
 *
 * @migrate-when: P5 全栈收口 + openapi-typescript regen 后
 * @target: src/types/api.d.ts
 * @reason: 后端 OpenAPI commit 96165e1 已定义 endpoint，但 api.d.ts 未 regen；
 *         P5-4 frontend 闭环需要类型对齐，临时手写类型待 V1.4 阶段 regen 替换。
 */

// ---------------------------------------------------------------------------
// 枚举 / 字面量
// ---------------------------------------------------------------------------

export type ExchangerCategory = 'SHELL_TUBE' | 'AIR_COOL' | 'PLATE';

export type TemaType =
  | 'BEM'
  | 'AEM'
  | 'AEL'
  | 'NEN'
  | 'BEM_FIXED'
  | 'AEM_U_TUBE';

export type Material = 'carbon_steel' | 'SS304' | 'SS316' | 'SS316L';

// ---------------------------------------------------------------------------
// POST /api/v1/heat/import-htri 输入（multipart/form-data）
// ---------------------------------------------------------------------------
// Form 字段：file (UploadFile .txt, required) + project_id + workspace_id +
//           equipment_no + tag_number + exchanger_category + equipment_name?
//           + source_stream_id?

// ---------------------------------------------------------------------------
// POST /api/v1/heat/import-htri 输出（201）
// ---------------------------------------------------------------------------

export interface ImportHtriResponse {
  calc_id: string;                              // UUID（HeatResult.heat_exchanger_id）
  calc_type: 'HEAT';
  record_hash: string;                          // 16 hex（ADR-0031）
  project_id: string;                           // UUID
  equipment_no: string;
  equipment_name: string | null;               // OPEN-7：补足免 get() roundtrip
  tag_number: string;                          // HeatResult 业务 tag
  exchanger_category: ExchangerCategory;
  duty_w: number | null;                        // 热负荷 W（HTRI 解析后填入；P7 UTIL 消费）
  output_json: Record<string, unknown>;         // OPEN-7：HTRI output 摘录（总重等）
  outlet_stream_id: string | null;              // source_stream_id 提供时存在
  outlet_stream_name: string | null;            // HEAT_EXCHANGE 后缀（outlet_stream.py:138）
}

// ---------------------------------------------------------------------------
// GET /api/v1/heat/{heat_id} 输出（200）
// ---------------------------------------------------------------------------

export interface HeatResultResponse {
  calc_id: string;                              // UUID
  calc_type: 'HEAT';
  project_id: string;                           // UUID
  workspace_id: string;                         // UUID
  tag_number: string;
  equipment_no: string | null;
  equipment_name: string | null;
  exchanger_category: ExchangerCategory;
  duty: number | null;                          // 热负荷 W（P7 UTIL 消费）
  record_hash: string | null;                   // 16 hex
  input_json: Record<string, unknown>;          // 原始 HTRI 字段（input_json 双轨）
  output_json: Record<string, unknown>;         // 含 total_weight_kg / weight_segments（P7 UTIL 消费）
}

// ---------------------------------------------------------------------------
// POST /api/v1/heat/{heat_id}/weight-estimate 输入
// ---------------------------------------------------------------------------
// WeightEstimateRequest（19 字段 TEMA 9th 几何参数）

export interface WeightEstimateRequest {
  tema_type: TemaType;
  shell_id_m: number;
  shell_length_m: number;
  shell_thickness_m: number;
  // 默认值见 api/v1/heat.py L107-125
  material?: Material;                          // 默认 'carbon_steel'
  head_count?: number;                          // 默认 2
  head_straight_m?: number;                     // 默认 0.025
  flange_count?: number;                        // 默认 2
  flange_class?: string;                        // 默认 '300#'（ASME B16.5）
  flange_size_dn?: number;                      // 默认 600
  nozzle_count?: number;                        // 默认 4
  nozzle_size_dn?: number;                      // 默认 100
  saddle_count?: number;                        // 默认 2
  saddle_size_dn?: number;                      // 默认 600
  tube_count?: number;                          // 默认 0
  tube_od_m?: number;
  tube_thickness_m?: number;
  tube_length_m?: number;
  baffle_count?: number;                        // 默认 0
  baffle_diameter_m?: number;
  baffle_thickness_m?: number;
}

// ---------------------------------------------------------------------------
// POST /api/v1/heat/{heat_id}/weight-estimate 输出（200）
// ---------------------------------------------------------------------------

export interface WeightSegmentResponse {
  weight_kg: number;
  formula_ref: string;                          // standard + version + clause
}

export interface WeightEstimateResponse {
  calc_id: string;                              // UUID
  total_weight_kg: number;                      // TEMA 9th 5 段 + tube/baffle/channels
  shell_total_kg: number;                       // 壳体 5 段累加
  segments: {
    shell_cylinder: WeightSegmentResponse;
    shell_heads: WeightSegmentResponse;
    shell_flanges: WeightSegmentResponse;
    shell_nozzles: WeightSegmentResponse;
    shell_saddles: WeightSegmentResponse;
    shell_total: WeightSegmentResponse;
    tube: WeightSegmentResponse;
    baffle: WeightSegmentResponse;
    channels: WeightSegmentResponse;
  };
  formula_ref: Record<string, string>;          // 顶层（含 TEMA 版本 + 各段标准 + clause）
  record_hash: string;                          // 刷新后（output_json 变更）
}