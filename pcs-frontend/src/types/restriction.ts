/**
 * PCS 限制装置计算模块类型（SPEC §3.2.2）。
 *
 * 字段对齐后端 OpenAPI snapshot（api.d.ts RestrictionCalculateRequest/Response）。
 * 本文件作为手写 wrapper：re-export + 中文 JSDoc + 类型别名，便于组件代码引用。
 * 不直接修改 api.d.ts（OpenAPI 自动生成，下一次 api:gen 会覆盖）。
 */

import type { components } from './api';

/** 限制装置计算请求（SPEC §3.2.2.1~4）。16 字段 Pydantic 严格模式（extra='forbid'）。 */
export type RestrictionCalculateRequest = components['schemas']['RestrictionCalculateRequest'];

/** 限制装置计算响应。13 字段含 restriction_result_id + outlet_stream_id + record_hash。 */
export type RestrictionCalculateResponse = components['schemas']['RestrictionCalculateResponse'];

/** 限制装置类型枚举（ISO 5167 各类 + 多级降压）。 */
export type RestrictionDeviceType = 'ORIFICE' | 'VENTURI' | 'NOZZLE' | 'MULTI_STAGE';

/** 流体相态枚举。 */
export type RestrictionFluidPhase = 'LIQUID' | 'GAS';

/** 设计阶段枚举。 */
export type RestrictionDesignStage = 'BASIC' | 'DETAIL';

/** standard_profile_code 默认值常量（与后端 RestrictionEngine 对齐；SPEC §3.2.2 默认 ISO-5167）。 */
export const DEFAULT_STANDARD_PROFILE_CODE = 'ISO-5167' as const;

/** 限制装置计算结果关键字段（13 键 SPEC §3.2.2.6 子集）。 */
export interface RestrictionCalculationOutput {
  /** 排放系数（discharge coefficient；无量纲；ORIFICE/VENTURI/NOZZLE 各自 ISO 公式）。 */
  C_discharge: number;
  /** 直径比 β = d/D（无量纲）。 */
  beta_ratio: number;
  /** 可膨胀性系数 ε（无量纲；ISO 5167 简化公式；仅 GAS）。 */
  epsilon?: number;
  /** 压差（Pa）。 */
  delta_P_pa: number;
  /** 是否阻塞流（choked flow；dP 接近理论极限）。 */
  choked: boolean;
  /** 是否闪蒸（flashing；仅液体；P1 < 50 kPa 启发式）。 */
  flashing: boolean;
  /** 降压级数（仅 MULTI_STAGE；ORIFICE/VENTURI/NOZZLE = 1）。 */
  stages?: number;
  /** 执行标准 profile code（默认 ISO-5167）。 */
  standard_profile_code: string;
}
