/**
 * PCS 调节阀 Cv 计算模块类型（SPEC §3.2.1）。
 *
 * 字段对齐后端 OpenAPI snapshot（api.d.ts CvCalculateRequest/Response）。
 * 本文件作为手写 wrapper：re-export + 中文 JSDoc + 类型别名，便于组件代码引用。
 * 不直接修改 api.d.ts（OpenAPI 自动生成，下一次 api:gen 会覆盖）。
 */

import type { components } from './api';

/** 调节阀 Cv 计算请求（SPEC §3.2.1.1~1.4）。22 字段 Pydantic 严格模式（extra='forbid'）。 */
export type CvCalculateRequest = components['schemas']['CvCalculateRequest'];

/** 调节阀 Cv 计算响应。13 字段含 cv_result_id + outlet_stream_id + record_hash。 */
export type CvCalculateResponse = components['schemas']['CvCalculateResponse'];

/** 流体相态枚举（替代裸 string literal union）。 */
export type CvFluidPhase = 'LIQUID' | 'GAS' | 'TWO_PHASE';

/** 设计阶段枚举。 */
export type CvDesignStage = 'BASIC' | 'DETAIL';

/** standard_profile_code 默认值常量（与后端 CvEngine 对齐；ADR-0028）。 */
export const DEFAULT_STANDARD_PROFILE_CODE = 'API-60534' as const;

/** 调节阀计算结果关键字段（21 键 SPEC §3.2.1.6 子集）。 */
export interface CvCalculationOutput {
  /** 计算 Cv 值（无量纲；液体：Q·√(SG/ΔP)；气体：含 Y 修正）。 */
  Cv_calculated: number;
  /** 选取 Cv 值（向上圆整到标准系列；可选）。 */
  Cv_selected?: number;
  /** 是否阻塞流（choked flow）。 */
  choked: boolean;
  /** 是否气蚀（cavitation；仅液体）。 */
  cavitation: boolean;
  /** 是否闪蒸（flashing；仅液体）。 */
  flashing: boolean;
  /** 噪音 SIL（dB；IEC 60534-8-3 简化法；可选）。 */
  noise_sil_db?: number;
}
