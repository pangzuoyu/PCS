/**
 * COMMON 模块类型（P45-3-3 / Task 30）。
 *
 * SPEC §7.8：
 * - ComponentProperty：组分物性（组分库）
 * - AllowableStress：许用应力（材料 + 温度 + 标准）
 * - ToxicityClass：毒性 / 爆炸极限（hazard_class 三档）
 *
 * TODO(api-migration): AllowableStressResult 已在 api.d.ts 存在
 * （§AllowableStressResult）。ComponentProperty / ToxicityClass 后端
 * 端点未在 P5-1 前冻结，V1 沿用前端 mock props shape。P5-1 完成后
 * 由 api.d.ts 替换。
 *
 * 见 docs/superpowers/plans/2026-09-16-p45-frontend-sprint-batch3.md
 * §"P5 契约冻结点"
 */

export interface ComponentProperty {
  component_id: string;
  name: string;
  formula: string;
  cas_number?: string;
  mw: number;                  // 分子量
  tc_k: number;                // 临界温度
  pc_mpa: number;              // 临界压力
  omega: number;               // 偏心因子
}

/** 许用应力表（材料 × 温度 × 标准）：指定材料在指定温度下的许用应力 MPa（ASME/GB/DIN 等）。 */
export interface AllowableStress {
  material: string;
  temperature_c: number;
  allowable_stress_mpa: number;
  standard: string;            // ASME / GB / DIN
}

/** 危险等级：LOW 低 / MEDIUM 中 / HIGH 高（用于介质/工艺综合分级）。 */
export type HazardClass = 'LOW' | 'MEDIUM' | 'HIGH';

/** 介质毒性分级：组分 ID + 名称 + 半致死量 LD50 + 允许暴露限 PEL + 爆炸极限（LEL/UEL）+ 危险等级。 */
export interface ToxicityClass {
  component_id: string;
  name: string;
  ld50_mg_kg?: number;
  pel_ppm?: number;            // 允许暴露限值
  explosive_limit_json?: { lel: number; uel: number };
  hazard_class: HazardClass;
}
// ---------------------------------------------------------------------------
// 气体热值（C-06 / P6-4 T1；POST /common/heating-value/calculate）
// ---------------------------------------------------------------------------

import type { components } from './api';

/** 气体热值计算请求：compositions [{cas, mol_frac}]（不要求和 1，service 归一化）+ excess_air_pct。 */
export type HeatingValueCalcRequest = components['schemas']['HeatingValueCalcRequest'];

/** 气体热值计算响应：HHV/LHV 双单位 + 化学计量空气 + 烟气组成/MW + formula_ref 溯源。 */
export type HeatingValueCalcResponse = components['schemas']['HeatingValueCalcResponse'];
