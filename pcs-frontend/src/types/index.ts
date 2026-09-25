/**
 * TYPES 模块 barrel 导出（P6-3 frontend / Task 37）。
 *
 * 设计：仅追加本任务新增的 3 模块 barrel 出口（open-channel / filtration / cost-est）。
 *       既有模块（flare / cool_tower / psychro / common 等）保留直接 import 路径，
 *       不强行 re-export，避免 cv.ts / restriction.ts 等同常量名冲突扩散到 barrel。
 *
 * 推荐用法：
 *   import type { ManningCalcRequest } from '../types/open-channel';
 *   import type { FiltrationResultResponse } from '../types/filtration';
 *   import type { SixTenthsRuleCalcRequest } from '../types/cost-est';
 *
 * 或通过本 barrel：
 *   import type {
 *     ManningCalcRequest,
 *     FiltrationResultResponse,
 *     SixTenthsRuleCalcRequest,
 *   } from '../types';
 *
 * @migrate-when: openapi-typescript regen 替换 api.d.ts 后
 * @target: src/types/api.d.ts + src/types/<module>.ts
 */

// P6-3 / Task 37（本次提交追加 3 模块）
export * from './open-channel';
export * from './filtration';
export * from './cost-est';
