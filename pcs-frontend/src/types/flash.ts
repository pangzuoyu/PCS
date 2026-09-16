/**
 * FLASH 模块类型（P45-3-4 / Task 31）。
 *
 * SPEC §7.11.1：
 * - 热力学方法 4 种
 * - 计算类型 5 种（PT / PH / PS / BUBBLE_POINT / DEW_POINT）
 * - 输入：物流 + 方法 + 计算类型 + 条件（T/P 或 H/S）
 * - 输出：汽化分率 + 双组成 + 焓熵 + K 值
 *
 * TODO(api-migration): FlashResult 注释存在于 api.d.ts（§FlashResult.flash_id）
 * 但完整 FlashInput / FlashResult schema 须 P5-1 calculate 入口交付时冻结；
 * 当前 V1 极简版沿用前端 mock props shape。
 *
 * 见 docs/superpowers/plans/2026-09-16-p45-frontend-sprint-batch3.md
 * §"P5 契约冻结点"
 */

export type ThermoMethod = 'PR' | 'SRK' | 'NRTL' | 'IAPWS_IF97';

export type FlashCalcType = 'PT' | 'PH' | 'PS' | 'BUBBLE_POINT' | 'DEW_POINT';

export interface FlashInput {
  stream_id: string;
  thermo_method: ThermoMethod;
  calc_type: FlashCalcType;
  t_k?: number;
  p_mpa?: number;
  h_kj_kg?: number;
  s_kj_kg_k?: number;
}

export interface FlashResult {
  vapor_fraction: number;
  liquid_composition: Record<string, number>;
  vapor_composition: Record<string, number>;
  h_kj_kg: number;
  s_kj_kg_k: number;
  k_values: Record<string, number>;
  converged: boolean;
}