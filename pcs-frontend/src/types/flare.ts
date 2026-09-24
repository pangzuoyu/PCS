/**
 * FLARE_SYS 模块类型（P6-2 frontend / Task 27）。
 *
 * SPEC §3.2.3（V1.3 P6-2 闭环后追加）+ 后端 OpenAPI：
 * - 5 calc（header_sizing / kod_sizing / stack_design / flare_tip + 早期合集）：
 *   - POST /api/v1/flare/header-sizing → HeaderSizingResponse 200（commit 8d82649 / 85c00da）
 *   - POST /api/v1/flare/kod-sizing → KodSizingResponse 200（commit 85c00da）
 *   - POST /api/v1/flare/stack-design → StackDesignResponse 200（commit ad7c436，
 *     合并 stack_height + radiation_check；前端按子结果区分渲染）
 *   - POST /api/v1/flare/tip → FlareTipResponse 200（commit ae089cf）
 * - CRUD /api/v1/flare/results（commit ae089cf）：
 *   - POST → FlareResultResponse 201
 *   - GET → FlareResultListResponse 200
 *   - GET /{record_id} → FlareResultResponse 200
 *   - PATCH /{record_id} → FlareResultResponse 200
 *   - DELETE /{record_id} → 204
 *
 * 设计要点：
 * - 业务字段与后端 Pydantic schema 1:1（snake_case 字段名）
 * - stack_design 端点合并输出 stack_height + radiation_check 两个子结果（前端展示分层）
 * - kod_sizing 端点合并输出 kod + water_seal 两个子结果
 * - FlareResultResponse `pass_` 字段：Pydantic 字段名 `pass_`（Python 保留字避让），
 *   序列化别名 `pass`（JSON wire 形态）。前端从 HTTP body 解析时 key 为 `pass`，
 *   使用 `Record<string, unknown>` 透传或 API 客户端层做映射。
 * - ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
 * - 错误码：FLARE_INPUT_ERROR 422 / FLARE_NOT_FOUND 404 /
 *         FLARE_PERSIST_SIGN_STATUS_LOCKED 422 / FLARE_PROJECT_MISMATCH 422
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

/** FLARE_SYS 计算类型（FlareSystemResult.calc_type 取值）：RELIEF_SUMMARY / HEADER_SIZING / KOD_SIZING / STACK_HEIGHT / RADIATION / FLARE_TIP（C-07 String(32) 锁定）。 */
export type FlareResultCalcType =
  | 'RELIEF_SUMMARY'
  | 'HEADER_SIZING'
  | 'KOD_SIZING'
  | 'STACK_HEIGHT'
  | 'RADIATION'
  | 'FLARE_TIP';

/** Pasquill-Gifford 大气稳定度等级（A–F；默认 D 中性，驱动 dispersion_factor）。 */
export type StabilityClass = 'A' | 'B' | 'C' | 'D' | 'E' | 'F';

// ---------------------------------------------------------------------------
// POST /api/v1/flare/header-sizing（API 521 §5.15.4）
// ---------------------------------------------------------------------------

/** POST /flare/header-sizing 请求：项目 ID + 标准 + 总泄放质量流量 + 管内平均温压 + 气体分子量/比热比 + 目标 Mach 数（默认 0.5 保守）。 */
export interface HeaderSizingRequest {
  project_id: string;                              // UUID（与 Task 19 aggregate_flare_load 隔离键一致）
  standard_profile_code?: string;                  // 默认 'API_521'
  relief_mass_flow_kgs: number;                    // 总泄放质量流量 kg/s（>0）
  avg_temperature_k: number;                       // 管内平均温度 K（>0）
  avg_pressure_pa: number;                         // 管内平均压力 Pa（>0）
  mw_kg_kmol: number;                              // 气体分子量 kg/kmol（>0）
  specific_heat_ratio: number;                     // 比热比 k = cp/cv（>1.0）
  target_mach?: number;                            // 目标 Mach 数（默认 0.5，范围 [0.05, 1.0]）
}

/** POST /flare/header-sizing 响应：总管直径/截面积/实际 Mach + 质量流速/气流速度 + 等温声速 + 气体密度 + 公式溯源 + project_id/standard 回显。 */
export interface HeaderSizingResponse {
  diameter_m: number;                              // 总管直径 m
  area_m2: number;                                 // 总管截面积 m²
  actual_mach: number;                             // 实际 Mach 数（应等于 target_mach）
  mass_flux_kgs_m2: number;                        // 质量流速 G kg/(s·m²)
  velocity_m_s: number;                            // 气流速度 m/s
  sound_speed_m_s: number;                         // 等温声速 m/s
  gas_density_kg_m3: number;                       // 管内气体密度 kg/m³（等温理想气体）
  formula_ref: string;                             // 公式溯源标记（API_521_§5.15.4）
  project_id: string;                              // 回显请求 project_id
  standard_profile_code: string;                   // 回显请求 standard_profile_code
}

// ---------------------------------------------------------------------------
// POST /api/v1/flare/kod-sizing（API 521 §5.15.3 Souders-Brown + §5.15.5 Water Seal）
// ---------------------------------------------------------------------------

/** POST /flare/kod-sizing 请求：项目 ID + 标准 + KOD 输入（蒸气/液滴流量密度 + Souders-Brown 系数）+ Water Seal 输入（总管/seal pot 压力 + 水密度 + 重力 + 安全系数 + 浪涌压力）。 */
export interface KodSizingRequest {
  project_id: string;                              // UUID（与 Task 19/20 隔离键一致）
  standard_profile_code?: string;                  // 默认 'API_521'
  // KOD 输入
  vapor_mass_flow_kgs: number;                     // 闪蒸气质量流量 kg/s（来自 Task 19，>0）
  vapor_density_kg_m3: number;                     // 蒸气密度 kg/m³（工况下，>0）
  liquid_density_kg_m3: number;                    // 液滴密度 kg/m³（>0）
  k_sb_m_s?: number;                               // Souders-Brown 系数 m/s（默认 0.3 保守，范围 (0, 2.0]）
  // Water Seal 输入
  header_pressure_pa: number;                      // 总管在 water seal 处压力 Pa（来自 Task 20，>0）
  seal_pot_pressure_pa: number;                    // seal pot 下游压力 Pa（大气压常 101325，>=0）
  water_density_kg_m3?: number;                    // 水封液密度 kg/m³（默认 1000 纯水，>0）
  gravity_m_s2?: number;                           // 重力加速度 m/s²（默认 9.81，>0）
  safety_factor?: number;                          // 设计安全系数（API 521 推荐 1.25–2.0，默认 1.5，>=1.0）
  surge_pressure_pa?: number;                      // 浪涌工况额外压力 Pa（默认 0，>=0）
}

/** KOD 子结果（API 521 §5.15.3 Souders-Brown）：KOD 直径/面积 + 允许/实际蒸气速度 + 极限比（恒等 1.0）+ 公式溯源。 */
export interface KodInfo {
  diameter_m: number;                              // KOD 直径 m
  area_m2: number;                                 // KOD 流通截面积 m²
  u_perm_m_s: number;                              // 允许蒸气速度 m/s
  u_actual_m_s: number;                            // 实际蒸气速度 m/s（数学恒等 u_perm）
  limit_ratio: number;                             // Souders-Brown 极限比 u_actual / u_perm（应 == 1.0）
  formula_ref: string;                             // 公式溯源标记（API_521_§5.15.3）
}

/** Water Seal 子结果（API 521 §5.15.5）：最小/设计液封高度 + 有效压差 + 公式溯源。 */
export interface WaterSealInfo {
  h_seal_m: number;                                // 最小液封高度 m
  h_design_m: number;                              // 设计液封高度 m（含 safety_factor）
  delta_pressure_pa: number;                       // 有效压差 Pa
  formula_ref: string;                             // 公式溯源标记（API_521_§5.15.5）
}

/** POST /flare/kod-sizing 响应：KOD 子结果 + Water Seal 子结果 + project_id/standard 回显 + 综合公式溯源（API_521_§5.15.3+§5.15.5）。 */
export interface KodSizingResponse {
  kod: KodInfo;
  water_seal: WaterSealInfo;
  project_id: string;                              // 回显请求 project_id
  standard_profile_code: string;                   // 回显请求 standard_profile_code
  formula_ref: string;                             // 综合公式溯源标记 "API_521_§5.15.3+§5.15.5"
}

// ---------------------------------------------------------------------------
// POST /api/v1/flare/stack-design（API 521 §7.4.2.2 + §7.4.2.3 + BEDD）
// ---------------------------------------------------------------------------

/** POST /flare/stack-design 请求：项目 ID + 标准 + Stack Height 输入（总热释放速率 MW + 稳定度等级 + 工程最小高度 + 风速）+ Radiation Check 输入（辐射热释放 + 受体距离 + 火焰长度/倾斜角 + BEDD 限值）。 */
export interface StackDesignRequest {
  project_id: string;                              // UUID（与 Task 19/20/21 隔离键一致）
  standard_profile_code?: string;                  // 默认 'API_521'
  // Stack Height 输入
  total_heat_release_mw: number;                   // 总热释放速率 MW（来自 Task 19，>0）
  stability_class?: StabilityClass;                // Pasquill-Gifford 大气稳定度（A–F，默认 D 中性）
  h_min_engineering_m?: number;                    // 工程最小高度 m（默认 10，范围 [5, 200]）
  wind_speed_m_s?: number;                         // 设计风速 m/s（默认 5，范围 [0, 50]）
  // Radiation Check 输入
  q_radiated_mw: number;                           // 火焰辐射热释放 MW（Q_total × fraction_rad，>0）
  receptor_distance_m: number;                     // 受体距火炬底水平距离 m（property line，>0）
  flame_height_m?: number | null;                  // 火焰长度 m（None 则自动 0.5×H_stack，>=0）
  tilt_angle_deg?: number;                         // 火焰倾斜角 度（默认 0 无风，范围 [0, 90]）
  bedd_limit_kw_m2?: number;                       // BEDD 限值 kW/m²（property line 4.73 / personnel 6.31 / emergency 12.6，默认 4.73）
}

/** Stack Height 子结果（API 521 §7.4.2.2）：推荐火炬高度 + 有效高度（含 dispersion_factor）+ 浮升抬升 + Pasquill-Gifford 修正因子 + 公式溯源。 */
export interface StackHeightInfo {
  h_stack_m: number;                               // 推荐火炬高度 m（max(h_min, h_eff)）
  h_effective_m: number;                           // 有效高度 m（含 dispersion_factor）
  buoyancy_rise_m: number;                         // 浮升抬升 ΔH_buoy m（1.5 × √Q_total）
  dispersion_factor: number;                       // Pasquill-Gifford 修正因子（依 stability_class）
  formula_ref: string;                             // 公式溯源标记（API_521_§7.4.2.2）
}

/** Radiation Check 子结果（API 521 §7.4.2.3 + BEDD）：受体处辐射强度 W/m² 与 kW/m² + BEDD 合规布尔 + BEDD 限值 + 火焰中心高度 + 斜距 R + 公式溯源。 */
export interface RadiationCheckInfo {
  q_at_receptor_w_m2: number;                      // 受体处辐射强度 W/m²
  q_at_receptor_kw_m2: number;                     // 受体处辐射强度 kW/m²（常用）
  bedd_compliant: boolean;                         // 是否满足 BEDD 限值（True = q ≤ bedd_limit）
  bedd_limit_kw_m2: number;                        // BEDD 限值 kW/m²（输入阈值）
  flame_center_height_m: number;                   // 火焰中心高度 m
  slant_distance_m: number;                        // 受体处斜距 R m
  formula_ref: string;                             // 公式溯源标记（API_521_§7.4.2.3+BEDD）
}

/** POST /flare/stack-design 响应：Stack Height 子结果 + Radiation Check 子结果 + project_id/standard 回显 + 综合公式溯源（API_521_§7.4.2.2+§7.4.2.3）。 */
export interface StackDesignResponse {
  stack_height: StackHeightInfo;
  radiation: RadiationCheckInfo;
  project_id: string;                              // 回显请求 project_id
  standard_profile_code: string;                   // 回显请求 standard_profile_code
  formula_ref: string;                             // 综合公式溯源标记 "API_521_§7.4.2.2+§7.4.2.3"
}

// ---------------------------------------------------------------------------
// POST /api/v1/flare/tip（API 521 §5.15.6）
// ---------------------------------------------------------------------------

/** POST /flare/tip 请求：项目 ID + 标准 + 总管直径（来自 Task 20）+ 气体分子量/比热比 + 尖端温压 + 目标 Mach 数（默认 0.2 尖端亚音速）。 */
export interface FlareTipRequest {
  project_id: string;                              // UUID（与 Task 19/20/21/22 隔离键一致）
  standard_profile_code?: string;                  // 默认 'API_521'
  header_diameter_m: number;                       // 火炬总管直径 m（来自 Task 20 header_sizing，>0）
  mw_kg_kmol: number;                              // 气体分子量 kg/kmol（>0）
  tip_temperature_k: number;                       // 尖端温度 K（工况下，>0）
  tip_pressure_pa: number;                         // 尖端压力 Pa（火炬入口压力，>0）
  specific_heat_ratio: number;                     // 比热比 k = cp/cv（>1.0）
  target_mach?: number;                            // 目标 Mach 数（默认 0.2 尖端亚音速，范围 [0.05, 1.0]）
}

/** POST /flare/tip 响应：尖端直径/面积/速度 + 实际 Mach + 等温声速 + 气体密度 + 质量流速 + 公式溯源（API_521_§5.15.6）+ project_id/standard 回显。 */
export interface FlareTipResponse {
  tip_diameter_m: number;                          // 尖端直径 m（与 header 同径；单点 tip 假设）
  tip_area_m2: number;                             // 尖端流通面积 m²
  tip_velocity_m_s: number;                        // 尖端目标速度 m/s（= M_target × a）
  actual_mach: number;                             // 实际 Mach 数（恒等于 target_mach）
  sound_speed_m_s: number;                         // 等温声速 m/s
  gas_density_kg_m3: number;                       // 管内气体密度 kg/m³
  mass_flux_kgs_m2: number;                        // 质量流速 G kg/(s·m²)
  formula_ref: string;                             // 公式溯源标记（API_521_§5.15.6）
  project_id: string;                              // 回显请求 project_id
  standard_profile_code: string;                   // 回显请求 standard_profile_code
}

// ---------------------------------------------------------------------------
// CRUD /api/v1/flare/results
// ---------------------------------------------------------------------------

/** POST /flare/results 请求体：溯源 + 隔离（mixin 必填）+ calc_type + sign_status + 18 业务字段（按 FlareSystemResult ORM 列名平铺；service ``**payload`` 喂给 ORM）。 */
export interface FlareResultCreateRequest {
  // 溯源 + 隔离（mixin 必填）
  project_id: string;                              // UUID（FK → projects）
  workspace_id: string;                            // UUID（业务隔离）
  tag_number: string;                              // 位号（TaggedRecordMixin NOT NULL）
  standard_profile_code?: string;                  // 默认 'API_521'
  calc_type: FlareResultCalcType;                  // 计算类型（C-07 String(32)）
  sign_status?: RecordSignStatus;                  // 默认 'DRAFT'
  // 18 业务字段
  total_relief_load_kg_h?: number | null;           // 总泄放质量流量 kg/h
  header_diameter_mm?: number | null;              // 总管直径 mm（来自 Task 20）
  header_mach?: number | null;                     // 总管实际 Mach 数（应等于 target_mach）
  header_pressure_drop_kpa?: number | null;        // 总管压降 kPa
  kod_diameter_mm?: number | null;                 // KOD 直径 mm（来自 Task 21）
  water_seal_height_mm?: number | null;            // 水封高度 mm（来自 Task 21）
  stack_height_m?: number | null;                  // 火炬高度 m（来自 Task 22）
  stack_diameter_m?: number | null;                // 火炬直径 m
  radiation_at_grade_kw_m2?: number | null;        // 地面辐射 kW/m²（来自 Task 22）
  radiation_limit_kw_m2?: number | null;           // BEDD 限值 kW/m²（来自 Task 22）
  pass_?: boolean | null;                          // 辐射校验 PASS/FAIL（SPEC §3.2.3；wire JSON key 为 "pass"）
  flare_tip_diameter_mm?: number | null;           // 尖端直径 mm（来自 tip 计算）
  steam_for_smokeless_kg_h?: number | null;        // 无烟蒸汽消耗 kg/h
  radiation_check_json?: Record<string, unknown> | null;  // 辐射校验完整产物（PCS-DICT-005 §3.1）
  input_json?: Record<string, unknown> | null;     // 入参（业务子结构）
  output_json?: Record<string, unknown> | null;    // 出参（业务子结构）
}

/** PATCH /flare/results/{record_id} 请求体：业务字段子集（不可改 sign_status / tag_number / 溯源 / standard / calc_type）。 */
export interface FlareResultUpdateRequest {
  calc_type?: FlareResultCalcType;                 // 计算类型
  total_relief_load_kg_h?: number | null;           // 总泄放质量流量 kg/h
  header_diameter_mm?: number | null;              // 总管直径 mm
  header_mach?: number | null;                     // 总管 Mach 数
  header_pressure_drop_kpa?: number | null;        // 总管压降 kPa
  kod_diameter_mm?: number | null;                 // KOD 直径 mm
  water_seal_height_mm?: number | null;            // 水封高度 mm
  stack_height_m?: number | null;                  // 火炬高度 m
  stack_diameter_m?: number | null;                // 火炬直径 m
  radiation_at_grade_kw_m2?: number | null;        // 地面辐射 kW/m²
  radiation_limit_kw_m2?: number | null;           // BEDD 限值 kW/m²
  pass_?: boolean | null;                          // 辐射校验 PASS/FAIL（wire JSON key 为 "pass"）
  flare_tip_diameter_mm?: number | null;           // 尖端直径 mm
  steam_for_smokeless_kg_h?: number | null;        // 无烟蒸汽消耗 kg/h
  radiation_check_json?: Record<string, unknown> | null;  // 辐射校验完整产物
  input_json?: Record<string, unknown> | null;     // 入参
  output_json?: Record<string, unknown> | null;    // 出参
}

/** FlareSystemResult 单条响应（GET /flare/results/{id} 与 POST 201 body）：溯源 + 18 业务字段 + 时间戳。ORM PK `flare_id` 重命名为 schema `id`。 */
export interface FlareResultResponse {
  id: string;                                      // UUID（FlareSystemResult.flare_id；ORM PK 重命名）
  project_id: string;                              // UUID
  workspace_id: string;                            // UUID
  tag_number: string;
  standard_profile_code: string;
  calc_type: FlareResultCalcType;
  sign_status: RecordSignStatus;                   // 签审状态 9 态
  record_hash: string | null;                      // 16 hex（ADR-0028 §决策 4 reflection）
  // 18 业务字段
  total_relief_load_kg_h: number | null;
  header_diameter_mm: number | null;
  header_mach: number | null;
  header_pressure_drop_kpa: number | null;
  kod_diameter_mm: number | null;
  water_seal_height_mm: number | null;
  stack_height_m: number | null;
  stack_diameter_m: number | null;
  radiation_at_grade_kw_m2: number | null;
  radiation_limit_kw_m2: number | null;
  pass_: boolean | null;                           // 辐射校验 PASS/FAIL（wire JSON key 为 "pass"）
  flare_tip_diameter_mm: number | null;
  steam_for_smokeless_kg_h: number | null;
  radiation_check_json: Record<string, unknown> | null;
  input_json: Record<string, unknown> | null;
  output_json: Record<string, unknown> | null;
  created_at: string;                              // ISO datetime
  updated_at: string | null;                       // ISO datetime
}

/** GET /flare/results 响应：FlareResultResponse 列表 + 命中条数（受 sign_status_filter 影响）+ 分页回显。 */
export interface FlareResultListResponse {
  items: FlareResultResponse[];
  total: number;                                   // 命中条数（默认 DRAFT/CHECKED filter）
  limit: number;                                   // 分页上限
  offset: number;                                  // 分页偏移
}
