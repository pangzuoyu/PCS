/**
 * COOL_TOWER 模块类型（P6-2 frontend / Task 27）。
 *
 * SPEC §3.2.4（V1.3 P6-2 闭环后追加）+ 后端 OpenAPI：
 * - 3 calc（commit ddc402b / 31fbe21）：
 *   - POST /api/v1/cool-tower/water-balance → WaterBalanceResponse 200
 *     （§3.2.4.4 蒸发/风吹/排污/补充水 4 项）
 *   - POST /api/v1/cool-tower/fan-power → FanPowerResponse 200
 *     （§3.2.4.6 CTI 1492 风机功率）
 *   - POST /api/v1/cool-tower/heat-load-aggregator → HeatLoadAggregatorResponse 200
 *     （§3.2.4.5 跨 HeatResult 汇总 h_aggregate_kw）
 * - CRUD /api/v1/cool-tower/results（commit 31fbe21）：
 *   - POST → CoolingTowerResultResponse 201
 *   - GET → CoolingTowerResultListResponse 200
 *   - GET /{record_id} → CoolingTowerResultResponse 200
 *   - PATCH /{record_id} → CoolingTowerResultResponse 200
 *   - DELETE /{record_id} → 204
 *
 * 设计要点：
 * - 业务字段与后端 Pydantic schema 1:1（snake_case 字段名）
 * - 10 业务字段（CoolingTowerResult ORM 排除 PK + mixin）：
 *   tower_type / duty_kw / water_flow_m3h / makeup_water_m3h / fan_power_kw /
 *   merkel_integral / data_sheet_json / input_json / output_json + 计算型 tag_number
 * - heat-load-aggregator 依赖 HeatResult 行：项目内 SHELL_TUBE / PLATE 类别求和，
 *   默认排除 AIR_COOL
 * - 公式溯源标记统一 `API_521_§3.2.4.X`
 * - ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
 * - 错误码：COOL_TOWER_INPUT_ERROR 422 / COOL_TOWER_NOT_FOUND 404 /
 *         COOL_TOWER_PERSIST_SIGN_STATUS_LOCKED 422 / COOL_TOWER_PROJECT_MISMATCH 422
 *
 * @migrate-when: P6-3 regen + openapi-typescript 自动替换
 * @target: src/types/api.d.ts
 * @reason: 后端 OpenAPI 已定义 endpoint，但 api.d.ts regen 暂未触发；
 *         P6-2 frontend type 闭环需要手写类型过渡，待 V1.4 regen 替换。
 */

import type { RecordSignStatus } from './records';

// ---------------------------------------------------------------------------
// 枚举 / 字面量
// ---------------------------------------------------------------------------

/** 冷却塔塔型：逆流机械抽风 COUNTERFLOW_MECH / 横流机械抽风 CROSSFLOW_MECH / 自然通风 NATURAL_DRAFT（驱动 Merkel/Curve 路径选择）。 */
export type CoolingTowerType =
  | 'COUNTERFLOW_MECH'
  | 'CROSSFLOW_MECH'
  | 'NATURAL_DRAFT';

/** COOL_TOWER 计算类型（CoolingTowerResult.calc_type 取值）：MERKEL / WATER_BALANCE / FAN_POWER / HEAT_AGGREGATE（C-07 String(32) 锁定）。 */
export type CoolTowerCalcType =
  | 'MERKEL'
  | 'WATER_BALANCE'
  | 'FAN_POWER'
  | 'HEAT_AGGREGATE';

/** HEAT 汇总时 exchanger_category 白名单过滤项（驱动 HeatResult 行筛选；默认排除 AIR_COOL）。 */
export type HeatExchangerCategoryFilter =
  | 'SHELL_TUBE'
  | 'PLATE'
  | 'AIR_COOL';

// ---------------------------------------------------------------------------
// POST /api/v1/cool-tower/water-balance（§3.2.4.4）
// ---------------------------------------------------------------------------

/** POST /cool-tower/water-balance 请求：循环水量 + 温差 + 浓缩倍数 + 风吹损失系数 + 蒸发潜热（默认 2400）+ 水比热（默认 4.187）。 */
export interface WaterBalanceRequest {
  q_w_m3_s: number;                                // 循环水量 m³/s（>0）
  delta_t_c: number;                               // 温差 °C（>=0；与 Kelvin 等价差值）
  cycle_ratio?: number;                            // 浓缩倍数 C_cycle（典型 3~5，默认 4，>1）
  drift_fraction?: number;                         // 风吹损失系数（∈ [0, 0.1]；典型 0.001~0.002）
  h_vap_kj_kg?: number;                            // 蒸发潜热 kJ/kg（默认 2400，>0）
  c_water_kj_kg_k?: number;                        // 水比热 kJ/kg·K（默认 4.187，>0）
}

/** POST /cool-tower/water-balance 响应：蒸发/风吹/排污损失 + 总补充水 + 公式溯源（API_521_§3.2.4.4）。 */
export interface WaterBalanceResponse {
  evaporation_m3_s: number;                        // 蒸发损失 E m³/s
  drift_m3_s: number;                              // 风吹损失 D m³/s
  blowdown_m3_s: number;                           // 排污损失 B m³/s（工程下限 clamp 0）
  makeup_m3_s: number;                             // 总补充水 M m³/s
  formula_ref: string;                             // 公式溯源标记（API_521_§3.2.4.4）
}

// ---------------------------------------------------------------------------
// POST /api/v1/cool-tower/fan-power（§3.2.4.6 CTI 1492）
// ---------------------------------------------------------------------------

/** POST /cool-tower/fan-power 请求：风机风量 + 全压 + 风机效率（轴流式 typ. 0.7，离心式 typ. 0.65）+ 电机效率（typ. 0.85~0.95）。 */
export interface FanPowerRequest {
  q_air_m3_s: number;                              // 风机风量 m³/s（>0）
  delta_p_total_pa: number;                        // 全压 Pa（>0）
  fan_efficiency: number;                          // 风机效率（0 < η_fan < 1）
  motor_efficiency: number;                        // 电机效率（0 < η_motor < 1）
}

/** POST /cool-tower/fan-power 响应：风机功率 kW + 公式溯源（API_521_§3.2.4.6）。 */
export interface FanPowerResponse {
  p_fan_kw: number;                                // 风机功率 kW
  formula_ref: string;                             // 公式溯源标记（API_521_§3.2.4.6）
}

// ---------------------------------------------------------------------------
// POST /api/v1/cool-tower/heat-load-aggregator（§3.2.4.5）
// ---------------------------------------------------------------------------

/** POST /cool-tower/heat-load-aggregator 请求：项目 ID + exchanger_category 过滤项（默认 SHELL_TUBE/PLATE）+ sign_status 白名单（默认 DRAFT/CHECKED）。 */
export interface HeatLoadAggregatorRequest {
  project_id: string;                              // UUID（isolation key）
  exchanger_categories_filter?: HeatExchangerCategoryFilter[] | null;  // 默认 ['SHELL_TUBE', 'PLATE']；排除 'AIR_COOL'
  sign_status_filter?: RecordSignStatus[] | null;  // sign_status 白名单（默认 ['DRAFT', 'CHECKED']）
}

/** POST /cool-tower/heat-load-aggregator 响应：总 kW + 命中 HeatResult 行数 + 按 exchanger_category 细分 + 公式溯源（API_521_§3.2.4.5）。 */
export interface HeatLoadAggregatorResponse {
  h_aggregate_kw: number;                          // 总 kW（各 exchanger_category 求和）
  heat_record_count: number;                       // 命中 HeatResult 行数
  per_exchanger_category: Record<string, number>;  // 按 exchanger_category 细分
  formula_ref: string;                             // 公式溯源标记（API_521_§3.2.4.5）
}

// ---------------------------------------------------------------------------
// CRUD /api/v1/cool-tower/results
// ---------------------------------------------------------------------------

/** POST /cool-tower/results 请求体：溯源 + 隔离（mixin 必填）+ calc_type + sign_status + 10 业务字段（按 CoolingTowerResult ORM 列名平铺；service ``**payload`` 喂给 ORM）。 */
export interface CoolingTowerResultCreateRequest {
  // 溯源 + 隔离（mixin 必填）
  project_id: string;                              // UUID（FK → projects）
  workspace_id: string;                            // UUID（业务隔离）
  tag_number: string;                              // 位号（TaggedRecordMixin NOT NULL）
  standard_profile_code?: string;                  // 默认 'CTI_ATC_105'
  calc_type: CoolTowerCalcType;                    // 计算类型（C-07 String(32)）
  sign_status?: RecordSignStatus;                  // 默认 'DRAFT'
  // 10 业务字段
  tower_type?: CoolingTowerType | null;            // 塔型（COUNTERFLOW_MECH / CROSSFLOW_MECH / NATURAL_DRAFT）
  duty_kw?: number | null;                         // 热负荷 kW（来自 Task 25 heat_aggregator）
  water_flow_m3h?: number | null;                  // 循环水量 m³/h（来自 Task 24）
  makeup_water_m3h?: number | null;                // 补充水量 m³/h（来自 Task 24 water_balance）
  fan_power_kw?: number | null;                    // 风机功率 kW（来自 Task 25 fan_power）
  merkel_integral?: number | null;                 // Merkel 积分值 KaV/L（来自 Task 24 merkel）
  data_sheet_json?: Record<string, unknown> | null;  // PCS-DICT-007 SUP-012 §3 14 子结构 data sheet
  input_json?: Record<string, unknown> | null;     // 入参（业务子结构）
  output_json?: Record<string, unknown> | null;    // 出参（业务子结构）
}

/** PATCH /cool-tower/results/{record_id} 请求体：业务字段子集（不可改 sign_status / tag_number / 溯源 / standard / calc_type）。 */
export interface CoolingTowerResultUpdateRequest {
  tower_type?: CoolingTowerType | null;            // 塔型
  duty_kw?: number | null;                         // 热负荷 kW
  water_flow_m3h?: number | null;                  // 循环水量 m³/h
  makeup_water_m3h?: number | null;                // 补充水量 m³/h
  fan_power_kw?: number | null;                    // 风机功率 kW
  merkel_integral?: number | null;                 // Merkel 积分值 KaV/L
  data_sheet_json?: Record<string, unknown> | null;  // PCS-DICT-007 SUP-012 §3 14 子结构 data sheet
  input_json?: Record<string, unknown> | null;     // 入参
  output_json?: Record<string, unknown> | null;    // 出参
}

/** CoolingTowerResult 单条响应（GET /cool-tower/results/{id} 与 POST 201 body）：溯源 + 10 业务字段 + 时间戳。ORM PK `cooling_tower_id` 重命名为 schema `id`。 */
export interface CoolingTowerResultResponse {
  id: string;                                      // UUID（CoolingTowerResult.cooling_tower_id；ORM PK 重命名）
  project_id: string;                              // UUID
  workspace_id: string;                            // UUID
  tag_number: string;
  standard_profile_code: string;
  calc_type: CoolTowerCalcType;
  sign_status: RecordSignStatus;                   // 签审状态 9 态
  record_hash: string | null;                      // 16 hex（ADR-0028 §决策 4 reflection）
  // 10 业务字段
  tower_type: CoolingTowerType | null;
  duty_kw: number | null;
  water_flow_m3h: number | null;
  makeup_water_m3h: number | null;
  fan_power_kw: number | null;
  merkel_integral: number | null;
  data_sheet_json: Record<string, unknown> | null;
  input_json: Record<string, unknown> | null;
  output_json: Record<string, unknown> | null;
  created_at: string;                              // ISO datetime
  updated_at: string | null;                       // ISO datetime
}

/** GET /cool-tower/results 响应：CoolingTowerResultResponse 列表 + 命中条数（受 sign_status_filter 影响）+ 分页回显。 */
export interface CoolingTowerResultListResponse {
  items: CoolingTowerResultResponse[];
  total: number;                                   // 命中条数（默认 DRAFT/CHECKED filter）
  limit: number;                                   // 分页上限
  offset: number;                                  // 分页偏移
}
