/**
 * PSYCHRO 模块类型（P6-2 frontend / Task 27）。
 *
 * SPEC §3.2.5（V1.3 P6-2 闭环后追加）+ 后端 OpenAPI（commit 9218ff4）：
 * - 6 calc：
 *   - POST /api/v1/psychro/humidity-ratio → HumidityRatioResponse 200
 *     （ASHRAE RP-1845 / CoolProp；湿度比 W kg/kg dry air）
 *   - POST /api/v1/psychro/dew-point → DewPointResponse 200
 *     （露点温度 °C；chedl_wrapper 返回 K，本响应减 273.15）
 *   - POST /api/v1/psychro/wet-bulb → WetBulbResponse 200
 *     （湿球温度 °C；等焓饱和温度近似）
 *   - POST /api/v1/psychro/enthalpy → EnthalpyResponse 200
 *     （比焓 kJ/kg dry air；chedl_wrapper 返回 J/kg，本响应 ÷1000）
 *   - POST /api/v1/psychro/specific-volume → SpecificVolumeResponse 200
 *     （比容 m³/kg dry air）
 *   - POST /api/v1/psychro/cooling-coil → CoolingCoilResponse 200
 *     （ASHRAE Handbook Fundamentals 2021 §1.2 显热/潜热拆分）
 * - CRUD /api/v1/psychro/results：
 *   - POST → PsychroResultResponse 201
 *   - GET → PsychroResultListResponse 200
 *   - GET /{record_id} → PsychroResultResponse 200
 *   - PATCH /{record_id} → PsychroResultResponse 200
 *   - DELETE /{record_id} → 204
 *
 * 设计要点：
 * - 业务字段与后端 Pydantic schema 1:1（snake_case 字段名）
 * - 6 calc 公共请求基础字段：t_c / rh / p_pa（5 项 calc 共用单状态点）
 *   + cooling-coil 双状态点（t1_c/rh1 + t2_c/rh2）+ 风量 q_air_m3_s
 * - 公式溯源统一 `ASHRAE_RP-1845_CoolProp` / `ASHRAE_HF2021_§1.2`
 * - coolprop_version 溯源：service 层从 CoolProp.get_global_param_string("version")
 *   自动填入；payload 缺时兜底 "unknown"；record_hash 反射自动包含
 * - 12 业务字段（PsychroResult ORM 排除 PK + mixin）：
 *   coolprop_version + 7 result 字段（humidity_ratio_kg_kg / dew_point_c /
 *   wet_bulb_c / enthalpy_kj_kg / specific_volume_m3_kg / sensible_heat_kw /
 *   latent_heat_kw）+ input_json / output_json
 * - 6 calc_type × 各自 result 字段的 optional 标记：前端仅展示 calc_type
 *   对应字段；schema 不互斥但 UI 渲染逻辑互斥
 * - ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
 * - 错误码：PSYCHRO_INPUT_ERROR 422 / PSYCHRO_NOT_FOUND 404 /
 *         PSYCHRO_PERSIST_SIGN_STATUS_LOCKED 422 / PSYCHRO_PROJECT_MISMATCH 422
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

/** PSYCHRO 计算类型（PsychroResult.calc_type 取值）：HUMIDITY_RATIO / DEW_POINT / WET_BULB / ENTHALPY / SPECIFIC_VOLUME / COOLING_COIL（C-07 String(32) 锁定）。 */
export type PsychroCalcType =
  | 'HUMIDITY_RATIO'
  | 'DEW_POINT'
  | 'WET_BULB'
  | 'ENTHALPY'
  | 'SPECIFIC_VOLUME'
  | 'COOLING_COIL';

// ---------------------------------------------------------------------------
// POST /api/v1/psychro/humidity-ratio
// ---------------------------------------------------------------------------

/** POST /psychro/humidity-ratio 请求：干球温度 °C + 相对湿度 0~1 + 大气压力 Pa（默认 101325 海平面）。 */
export interface HumidityRatioRequest {
  t_c: number;                                     // 干球温度 °C（>-273.15；华氏参考 0~50°C）
  rh: number;                                      // 相对湿度（无量纲，0~1）
  p_pa?: number;                                   // 大气压力 Pa（默认海平面 101325，>0）
}

/** POST /psychro/humidity-ratio 响应：湿度比 kg/kg dry air + 公式溯源（ASHRAE_RP-1845_CoolProp）。 */
export interface HumidityRatioResponse {
  humidity_ratio_kg_kg: number;                    // 湿度比 W（kg 水 / kg 干空气）
  formula_ref: string;                             // 公式溯源标记（ASHRAE_RP-1845_CoolProp）
}

// ---------------------------------------------------------------------------
// POST /api/v1/psychro/dew-point
// ---------------------------------------------------------------------------

/** POST /psychro/dew-point 请求：干球温度 °C + 相对湿度 0~1 + 大气压力 Pa（默认 101325）。 */
export interface DewPointRequest {
  t_c: number;                                     // 干球温度 °C（>-273.15）
  rh: number;                                      // 相对湿度 0~1
  p_pa?: number;                                   // 大气压力 Pa（默认 101325，>0）
}

/** POST /psychro/dew-point 响应：露点温度 °C（chedl_wrapper 返回 K，本响应减 273.15）+ 公式溯源。 */
export interface DewPointResponse {
  dew_point_c: number;                             // 露点温度 °C
  formula_ref: string;                             // 公式溯源标记（ASHRAE_RP-1845_CoolProp）
}

// ---------------------------------------------------------------------------
// POST /api/v1/psychro/wet-bulb
// ---------------------------------------------------------------------------

/** POST /psychro/wet-bulb 请求：干球温度 °C + 相对湿度 0~1 + 大气压力 Pa（默认 101325）。 */
export interface WetBulbRequest {
  t_c: number;                                     // 干球温度 °C（>-273.15）
  rh: number;                                      // 相对湿度 0~1
  p_pa?: number;                                   // 大气压力 Pa（默认 101325，>0）
}

/** POST /psychro/wet-bulb 响应：湿球温度 °C（等焓饱和温度近似）+ 公式溯源。 */
export interface WetBulbResponse {
  wet_bulb_c: number;                              // 湿球温度 °C
  formula_ref: string;                             // 公式溯源标记（ASHRAE_RP-1845_CoolProp）
}

// ---------------------------------------------------------------------------
// POST /api/v1/psychro/enthalpy
// ---------------------------------------------------------------------------

/** POST /psychro/enthalpy 请求：干球温度 °C + 相对湿度 0~1 + 大气压力 Pa（默认 101325）。 */
export interface EnthalpyRequest {
  t_c: number;                                     // 干球温度 °C（>-273.15）
  rh: number;                                      // 相对湿度 0~1
  p_pa?: number;                                   // 大气压力 Pa（默认 101325，>0）
}

/** POST /psychro/enthalpy 响应：比焓 kJ/kg dry air（chedl_wrapper 返回 J/kg，本响应 ÷1000）+ 公式溯源。 */
export interface EnthalpyResponse {
  enthalpy_kj_kg: number;                          // 比焓 kJ/kg dry air
  formula_ref: string;                             // 公式溯源标记（ASHRAE_RP-1845_CoolProp）
}

// ---------------------------------------------------------------------------
// POST /api/v1/psychro/specific-volume
// ---------------------------------------------------------------------------

/** POST /psychro/specific-volume 请求：干球温度 °C + 相对湿度 0~1 + 大气压力 Pa（默认 101325）。 */
export interface SpecificVolumeRequest {
  t_c: number;                                     // 干球温度 °C（>-273.15）
  rh: number;                                      // 相对湿度 0~1
  p_pa?: number;                                   // 大气压力 Pa（默认 101325，>0）
}

/** POST /psychro/specific-volume 响应：比容 m³/kg dry air + 公式溯源。 */
export interface SpecificVolumeResponse {
  specific_volume_m3_kg: number;                   // 比容 m³/kg dry air
  formula_ref: string;                             // 公式溯源标记（ASHRAE_RP-1845_CoolProp）
}

// ---------------------------------------------------------------------------
// POST /api/v1/psychro/cooling-coil（ASHRAE Handbook Fundamentals 2021 §1.2）
// ---------------------------------------------------------------------------

/** POST /psychro/cooling-coil 请求：进/出口干球温度 + 进/出口相对湿度 + 大气压力 Pa + 体积风量 m³/s（双状态点拆分显热/潜热）。 */
export interface CoolingCoilRequest {
  t1_c: number;                                    // 入口干球温度 °C（>-273.15）
  rh1: number;                                     // 入口相对湿度 0~1
  t2_c: number;                                    // 出口干球温度 °C（>-273.15）
  rh2: number;                                     // 出口相对湿度 0~1
  p_pa?: number;                                   // 大气压力 Pa（默认 101325，>0）
  q_air_m3_s: number;                              // 体积风量 m³/s（>0）
}

/** POST /psychro/cooling-coil 响应：显热 kW（m_dot × Q_sensible / 1000）+ 潜热 kW（m_dot × Q_latent / 1000）+ 公式溯源（ASHRAE_HF2021_§1.2）。 */
export interface CoolingCoilResponse {
  sensible_heat_kw: number;                        // 显热 kW
  latent_heat_kw: number;                          // 潜热 kW
  formula_ref: string;                             // 公式溯源标记（ASHRAE_HF2021_§1.2）
}

// ---------------------------------------------------------------------------
// CRUD /api/v1/psychro/results
// ---------------------------------------------------------------------------

/** POST /psychro/results 请求体：溯源 + 隔离（mixin 必填）+ calc_type + sign_status + 12 业务字段（按 PsychroResult ORM 列名平铺；service ``**payload`` 喂给 ORM）。 */
export interface PsychroResultCreateRequest {
  // 溯源 + 隔离（mixin 必填）
  project_id: string;                              // UUID（FK → projects）
  workspace_id: string;                            // UUID（业务隔离）
  tag_number: string;                              // 位号（TaggedRecordMixin NOT NULL）
  standard_profile_code?: string;                  // 默认 'ASHRAE_FUND_2021'
  calc_type: PsychroCalcType;                      // 计算类型（C-07 String(32)）
  sign_status?: RecordSignStatus;                  // 默认 'DRAFT'
  // 12 业务字段
  coolprop_version?: string | null;                // CoolProp 版本（如 '6.6.0'）；payload 缺时 service 自动从 get_coolprop_version() 写入（SPEC §3.2.5 溯源）
  humidity_ratio_kg_kg?: number | null;             // 湿度比 kg/kg dry air
  dew_point_c?: number | null;                     // 露点温度 °C
  wet_bulb_c?: number | null;                      // 湿球温度 °C
  enthalpy_kj_kg?: number | null;                  // 比焓 kJ/kg dry air
  specific_volume_m3_kg?: number | null;           // 比容 m³/kg dry air
  sensible_heat_kw?: number | null;                // 显热 kW（cooling_coil 专用）
  latent_heat_kw?: number | null;                  // 潜热 kW（cooling_coil 专用）
  input_json?: Record<string, unknown> | null;     // 入参（业务子结构）
  output_json?: Record<string, unknown> | null;    // 出参（业务子结构）
}

/** PATCH /psychro/results/{record_id} 请求体：业务字段子集（不可改 sign_status / tag_number / 溯源 / standard / calc_type / coolprop_version）。 */
export interface PsychroResultUpdateRequest {
  humidity_ratio_kg_kg?: number | null;             // 湿度比 kg/kg dry air
  dew_point_c?: number | null;                     // 露点温度 °C
  wet_bulb_c?: number | null;                      // 湿球温度 °C
  enthalpy_kj_kg?: number | null;                  // 比焓 kJ/kg dry air
  specific_volume_m3_kg?: number | null;           // 比容 m³/kg dry air
  sensible_heat_kw?: number | null;                // 显热 kW（cooling_coil 专用）
  latent_heat_kw?: number | null;                  // 潜热 kW（cooling_coil 专用）
  input_json?: Record<string, unknown> | null;     // 入参（业务子结构）
  output_json?: Record<string, unknown> | null;    // 出参（业务子结构）
}

/** PsychroResult 单条响应（GET /psychro/results/{id} 与 POST 201 body）：溯源 + 12 业务字段 + 时间戳。ORM PK `psychro_id` 重命名为 schema `id`。 */
export interface PsychroResultResponse {
  id: string;                                      // UUID（PsychroResult.psychro_id；ORM PK 重命名）
  project_id: string;                              // UUID
  workspace_id: string;                            // UUID
  tag_number: string;
  standard_profile_code: string;
  calc_type: PsychroCalcType;
  coolprop_version: string | null;                 // CoolProp 版本（如 '6.6.0'）；溯源 — service 层从 CoolProp.get_global_param_string("version") 自动填入；缺省 / 失败时兜底 "unknown"
  sign_status: RecordSignStatus;                   // 签审状态 9 态
  record_hash: string | null;                      // 16 hex（ADR-0028 §决策 4 reflection）
  // 10 业务字段
  humidity_ratio_kg_kg: number | null;
  dew_point_c: number | null;
  wet_bulb_c: number | null;
  enthalpy_kj_kg: number | null;
  specific_volume_m3_kg: number | null;
  sensible_heat_kw: number | null;
  latent_heat_kw: number | null;
  input_json: Record<string, unknown> | null;
  output_json: Record<string, unknown> | null;
  created_at: string;                              // ISO datetime
  updated_at: string | null;                       // ISO datetime
}

/** GET /psychro/results 响应：PsychroResultResponse 列表 + 命中条数（受 sign_status_filter 影响）+ 分页回显。 */
export interface PsychroResultListResponse {
  items: PsychroResultResponse[];
  total: number;                                   // 命中条数（默认 DRAFT/CHECKED filter）
  limit: number;                                   // 分页上限
  offset: number;                                  // 分页偏移
}
