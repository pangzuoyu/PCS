/**
 * 6 类可编辑结果记录的 seed（P9B-1 · SPEC §6.21）。
 *
 * ⚠️ **响应体一律用生成的 OpenAPI 类型标注**（`satisfies`）——
 * 手写自由 dict 就是 bug-2040 的根源（mock 与真端点不同源 ⇒ 漂移被藏住
 * ⇒ 只有生产构建才炸）。
 *
 * ## 三个「场景记录」（浏览器 QA 用）
 *
 * mock 的行为由**记录 id** 驱动（不是随机、不是 query 参数）⇒ QA 只要
 * 打开对应那一行就能复现：
 *
 * | id | 场景 |
 * |---|---|
 * | `scenario-locked` | **他人持锁** ⇒ acquire 返 409 + 持锁人 |
 * | `scenario-degraded` | **Redis 降级** ⇒ acquire 返 `degraded=true` |
 * | `scenario-conflict-hash` | 保存 409 `basis=record_hash` |
 * | `scenario-conflict-updated-at` | 保存 409 `basis=updated_at` |
 * | `scenario-conflict-no-baseline` | 保存 409 `basis=no_baseline` |
 */
import type { components } from '../../types/api';

type CoolTower = components['schemas']['CoolTowerResultResponse'];
type Filtration = components['schemas']['FiltrationResultResponse'];
type Flare = components['schemas']['FlareResultResponse'];
type OpenChannel = components['schemas']['OpenChannelResultResponse'];
type Psychro = components['schemas']['PsychroResultResponse'];
type CostEst = components['schemas']['CostEstResultResponse'];

const PROJECT_ID = '00000000-0000-0000-0000-000000000001';
const WORKSPACE_ID = '00000000-0000-0000-0000-000000000002';
const CREATED_AT = '2026-10-20T10:22:31Z';
/** ⚠️ 微秒精度的时间戳（后端 `TIMESTAMPTZ` 是微秒）⇒ 前端**不得**过 `new Date()`。 */
const UPDATED_AT = '2026-10-20T10:22:31.123456+08:00';

export const SCENARIO = {
  locked: 'scenario-locked',
  degraded: 'scenario-degraded',
  conflictHash: 'scenario-conflict-hash',
  conflictUpdatedAt: 'scenario-conflict-updated-at',
  conflictNoBaseline: 'scenario-conflict-no-baseline',
} as const;

export const seedCoolTowerResults: CoolTower[] = [
  {
    id: '11111111-1111-1111-1111-111111111111',
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'CT-001',
    standard_profile_code: 'GB-500',
    calc_type: 'EVAPORATIVE',
    sign_status: 'DRAFT',
    record_hash: 'a3f9c21d8b7e6f50',
    tower_type: 'COUNTERFLOW',
    duty_kw: 100,
    water_flow_m3h: 50,
    makeup_water_m3h: 1,
    fan_power_kw: 5,
    merkel_integral: 0.5,
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
  {
    id: '22222222-2222-2222-2222-222222222222',
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'CT-002',
    standard_profile_code: 'GB-500',
    calc_type: 'EVAPORATIVE',
    sign_status: 'CHECKED',
    record_hash: 'b4e0d3e2c8a7f601',
    tower_type: 'DRAFT',
    duty_kw: 200,
    water_flow_m3h: 90,
    makeup_water_m3h: 2,
    fan_power_kw: 9,
    merkel_integral: 0.62,
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
  // 三个「场景记录」⇒ 浏览器 QA 可复现他人持锁 / 降级 / 三种 409。
  {
    id: SCENARIO.locked,
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'CT-LOCKED',
    standard_profile_code: 'GB-500',
    calc_type: 'EVAPORATIVE',
    sign_status: 'DRAFT',
    record_hash: 'c5f1e4f3d9b80612',
    tower_type: 'INDUCTION',
    duty_kw: 300,
    water_flow_m3h: 120,
    makeup_water_m3h: 3,
    fan_power_kw: 14,
    merkel_integral: 0.71,
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
  {
    id: SCENARIO.degraded,
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'CT-DEGRADED',
    standard_profile_code: 'GB-500',
    calc_type: 'EVAPORATIVE',
    sign_status: 'DRAFT',
    record_hash: 'd6025a4eac917023',
    tower_type: 'INDUCTION',
    duty_kw: 400,
    water_flow_m3h: 150,
    makeup_water_m3h: 4,
    fan_power_kw: 19,
    merkel_integral: 0.8,
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
  {
    id: SCENARIO.conflictHash,
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'CT-CONFLICT-HASH',
    standard_profile_code: 'GB-500',
    calc_type: 'EVAPORATIVE',
    sign_status: 'DRAFT',
    record_hash: 'e7136b5fbd028134',
    tower_type: 'COUNTERFLOW',
    duty_kw: 500,
    water_flow_m3h: 180,
    makeup_water_m3h: 5,
    fan_power_kw: 24,
    merkel_integral: 0.9,
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
  {
    id: SCENARIO.conflictUpdatedAt,
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'CT-CONFLICT-UPDATED-AT',
    standard_profile_code: 'GB-500',
    calc_type: 'EVAPORATIVE',
    sign_status: 'DRAFT',
    record_hash: 'f8247c60ce139245',
    tower_type: 'COUNTERFLOW',
    duty_kw: 600,
    water_flow_m3h: 210,
    makeup_water_m3h: 6,
    fan_power_kw: 29,
    merkel_integral: 1.0,
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
  {
    id: SCENARIO.conflictNoBaseline,
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'CT-CONFLICT-NO-BASELINE',
    standard_profile_code: 'GB-500',
    calc_type: 'EVAPORATIVE',
    sign_status: 'DRAFT',
    record_hash: '09358d71df24a356',
    tower_type: 'COUNTERFLOW',
    duty_kw: 700,
    water_flow_m3h: 240,
    makeup_water_m3h: 7,
    fan_power_kw: 34,
    merkel_integral: 1.1,
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
];

export const seedFiltrationResults: Filtration[] = [
  {
    result_id: '33333333-3333-3333-3333-333333333333',
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'F-001',
    filter_type: 'BAG',
    media_type: 'POLYESTER',
    area: 12,
    cycle_time: 24,
    pressure_drop: 180,
    cake_resistance_alpha: 1.2e9,
    specific_resistance_r0: 4.5e10,
    permeability_k: 1.1e-12,
    porosity_eps: 0.45,
    filter_velocity: 0.02,
    sign_status: 'DRAFT',
    record_hash: '1a369e82e035b467',
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
];

export const seedFlareResults: Flare[] = [
  {
    id: '44444444-4444-4444-4444-444444444444',
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'FL-001',
    standard_profile_code: 'GB-500',
    calc_type: 'HEAT',
    sign_status: 'DRAFT',
    record_hash: '2b47af93f146c578',
    total_relief_load_kg_h: 1500,
    header_diameter_mm: 300,
    header_mach: 0.08,
    header_pressure_drop_kpa: 12,
    kod_diameter_mm: 150,
    water_seal_height_mm: 300,
    stack_height_m: 25,
    stack_diameter_m: 1.2,
    radiation_at_grade_kw_m2: 7.8,
    radiation_limit_kw_m2: 10,
    flare_tip_diameter_mm: 600,
    steam_for_smokeless_kg_h: 120,
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
];

export const seedOpenChannelResults: OpenChannel[] = [
  {
    result_id: '55555555-5555-5555-5555-555555555555',
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'CH-001',
    channel_type: 'RECTANGULAR',
    cross_section_json: { width: 2, depth: 1 },
    flow_rate: 3.2,
    depth: 0.6,
    velocity: 1.4,
    slope: 0.001,
    critical_depth: 0.42,
    froude_number: 0.58,
    manning_n: 0.015,
    hydraulic_radius: 0.46,
    jump_type: 'NONE',
    conjugate_depth: 0.98,
    energy_loss: 0.12,
    sign_status: 'DRAFT',
    record_hash: '3c58b0a40257d689',
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
];

export const seedPsychroResults: Psychro[] = [
  {
    id: '66666666-6666-6666-6666-666666666666',
    project_id: PROJECT_ID,
    workspace_id: WORKSPACE_ID,
    tag_number: 'PS-001',
    standard_profile_code: 'GB-500',
    calc_type: 'PSYCHROMETRIC',
    sign_status: 'DRAFT',
    record_hash: '4d69c1b51368e79a',
    humidity_ratio_kg_kg: 0.008,
    dew_point_c: 6.2,
    wet_bulb_c: 18.5,
    enthalpy_kj_kg: 48.3,
    specific_volume_m3_kg: 0.86,
    sensible_heat_kw: 12.5,
    latent_heat_kw: 8.1,
    saturation_w_kg_kg: 0.012,
    saturation_w_mg_sm3: 9.4,
    saturation_w_lb_per_mmscf: 0.79,
    saturation_T_c: 19.1,
    created_at: CREATED_AT,
    updated_at: UPDATED_AT,
  },
];

export const seedCostEstResults: CostEst[] = [
  {
    result_id: '77777777-7777-7777-7777-777777777777',
    equipment_id: '88888888-8888-8888-8888-888888888888',
    project_id: PROJECT_ID,
    estimated_cost: 350000,
    currency: 'CNY',
    cost_index_year: 2024,
    base_cost: 300000,
    base_year: 2020,
    cepci_index_base: 580,
    cepci_index_target: 780,
    correlation_source: 'Gottlieb1989',
    scaling_exponent: 0.6,
    record_hash: '5e7ad2c62479f8ab',
    created_at: CREATED_AT,
  },
];
