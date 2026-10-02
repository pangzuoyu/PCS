/**
 * P7 Sprint 2 UTIL API 客户端（P7-6B 冷却水 + R1 综合能耗）。
 *
 * 按后端 OpenAPI（commit 260f357 BLOCKER-3 集成后）：
 * - GET /api/v1/util/heat-exchange-items?project_id=&workspace_id=
 *   → list[UtilHeatExchangeResponse]（T3 蒸汽/冷凝水/P7-6B 冷却水 共用表）
 * - POST /api/v1/util/heat-exchange-items → UtilHeatExchangeResponse 201
 * - POST /api/v1/util/energy-summary/aggregate → UtilEnergySummaryResponse 201
 *
 * 设计要点：
 * - P7-6B 冷却水落地复用 R1 §7.2 medium_type 设计 (无新表): water records
 *   用 medium_type='CIRCULATING_WATER' 等 9 类 + pressure_level 留空
 * - steam records 用 medium_type='STEAM' + pressure_level='GE_7_0_MPA' 等 9 档
 * - 错误通过 PcsError envelope 抛出 (SIM_STREAM_NOT_FOUND 等)
 * - workspace_id 由调用方传入（meta/projects 取真实 workspace_id）
 */

import { api } from './client';
import type { components } from '../types/api';

type UtilHeatExchangeCreateRequest = components['schemas']['UtilHeatExchangeCreateRequest'];
type UtilHeatExchangeResponse = components['schemas']['UtilHeatExchangeResponse'];
type UtilEnergySummaryAggregateRequest =
  components['schemas']['UtilEnergySummaryAggregateRequest'];
type UtilEnergySummaryResponse = components['schemas']['UtilEnergySummaryResponse'];

// R1 §7.2 GB 30251-2024 附录 A 9 类水 (per Do-Not-Repeat: 不入新 utility_cooling_water 表,
// 复用 utility_heat_exchange.medium_type; 9 + STEAM 共 11 类)
export const WATER_TYPE_OPTIONS: Array<{
  value: string;
  label: string;
  toe_factor?: number;
}> = [
  { value: 'FRESH_WATER', label: '新鲜水', toe_factor: 0.15 },
  { value: 'CIRCULATING_WATER', label: '循环水', toe_factor: 0.06 },
  { value: 'SOFTENED_WATER', label: '软化水', toe_factor: 0.17 },
  { value: 'DEMINERALIZED_WATER', label: '除盐水', toe_factor: 0.21 },
  { value: 'LP_DEAERATED_WATER', label: '低压除氧水', toe_factor: 1.85 },
  { value: 'HP_DEAERATED_WATER', label: '高压除氧水', toe_factor: 2.71 },
  { value: 'TURBINE_CONDENSATE', label: '透平凝液', toe_factor: 0.11 },
  { value: '120C_CONDENSATE_TREATED', label: '120°C 凝液处理', toe_factor: 0.34 },
  { value: '120C_CONDENSATE_REUSABLE', label: '120°C 凝液回用', toe_factor: 10.14 },
];

export interface ListHeatExchangeParams {
  project_id: string;
  workspace_id: string;
  // 可选 medium_type 过滤 (P7-6B 冷却水只查 WATER; 蒸汽只查 STEAM)
  medium_type?: string;
}

export const utilApi = {
  /**列出 heat_exchange_items (T3 蒸汽/冷凝水/P7-6B 冷却水 共用表). */
  listHeatExchange: (params: ListHeatExchangeParams) =>
    api
      .get<UtilHeatExchangeResponse[]>('/util/heat-exchange-items', { params })
      .then((r) => r.data),

  /**创建 heat_exchange 行. R1 §7.1/§7.2: pressure_level (蒸汽 9 档) + medium_type (10 类). */
  createHeatExchange: (body: UtilHeatExchangeCreateRequest) =>
    api
      .post<UtilHeatExchangeResponse>('/util/heat-exchange-items', body)
      .then((r) => r.data),

  /**触发综合能耗汇总 (R1 §7 _compute_totals 分类聚合). */
  aggregateEnergySummary: (body: UtilEnergySummaryAggregateRequest) =>
    api
      .post<UtilEnergySummaryResponse>('/util/energy-summary/aggregate', body)
      .then((r) => r.data),
};