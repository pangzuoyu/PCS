/**
 * COST_EST 前端 TypeScript 类型（P6-3 frontend / Task 37）。
 *
 * SPEC §3.2.8 + 后端 OpenAPI（Task 36 commit 5e14a3f）：
 * - 3 calc：POST /cost-est/{six-tenths-rule|cepci-adjustment|cost-correlation}/calculate
 * - CRUD /api/v1/cost-est/results：
 *   - POST → CostEstCreateRequest 201
 *   - GET → CostEstListResponse 200
 *   - GET /{result_id} → CostEstResultResponse 200
 *   - PATCH /{result_id} → CostEstUpdateRequest 200
 *   - DELETE /{result_id} → CostEstDeleteResponse 200
 *
 * 设计要点：
 * - 业务字段与后端 Pydantic schema 1:1（snake_case 字段名）
 * - CostEstBase 公共基础（estimated_cost + currency + cost_index_year 必填；
 *   base_cost / base_year / cepci_index_base / cepci_index_target / scaling_exponent /
 *   equipment_type / scale_parameter / correlation_source 可选）
 * - 3 calc 字段差异：
 *   - SixTenthsRuleCalcRequest: equipment_id + reference_cost + reference_cepci + target_cepci + scaling_exponent + estimated_cost
 *   - CepciAdjustmentCalcRequest: equipment_id + reference_cost + reference_cepci + target_cepci + estimated_cost
 *   - CostCorrelationCalcRequest: equipment_id + equipment_type + scale_parameter + correlation_source + estimated_cost
 * - CostEst 无 sign_status 列 → 不做"锁定态"门禁（区别于 filtration/open_channel）；
 *   所有状态可 PATCH（CostEstUpdateRequest 含全字段 optional）
 * - 物理删除（无 OBSOLETE 态）：CostEstResult 1:1 跟随 equipment；删除后 equipment 可重建 cost_est
 * - CostEstResultResponse 不含 sign_status / record_hash / updated_at（设计：无 sign_status、无 record_hash 反射）
 * - 设备类型枚举：TOWER / VESSEL / HEAT_EXCHANGER / PUMP / COMPRESSOR / PIPING
 * - Task 35 已落地 CostCorrelationLibrary CONFIG 表；本类型层仅透传，不涉及业务计算
 * - ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
 * - 错误码：COST_EST_INPUT_ERROR 422 / COST_EST_NOT_FOUND 404 /
 *         COST_EST_PROJECT_MISMATCH 422
 *
 * @migrate-when: P6-3 regen + openapi-typescript 自动替换
 * @target: src/types/api.d.ts
 * @reason: 后端 OpenAPI 已定义 endpoint，但 api.d.ts regen 暂未触发；
 *         P6-3 frontend type 闭环需要手写类型过渡，待 V1.4 regen 替换。
 */

// ---------------------------------------------------------------------------
// 枚举 / 字面量
// ---------------------------------------------------------------------------

/** COST_EST 设备类型枚举（CostCorrelation 计算维度）：TOWER 塔 / VESSEL 容器 / HEAT_EXCHANGER 换热器 / PUMP 泵 / COMPRESSOR 压缩机 / PIPING 管道。 */
export type EquipmentType = 'TOWER' | 'VESSEL' | 'HEAT_EXCHANGER' | 'PUMP' | 'COMPRESSOR' | 'PIPING';

/** COST_EST 公共基础：estimated_cost + currency + cost_index_year 必填；其余 optional。 */
export interface CostEstBase {
  /** 估算投资 C₂（基准货币，>=0）。 */
  estimated_cost: number;
  /** 货币代码（maxLength=10，默认 USD）。 */
  currency: string;
  /** 目标年（1900~2200，默认 2019）。 */
  cost_index_year: number;
  /** 基准年成本 C₁（可空，>=0）。 */
  base_cost?: number | null;
  /** 基准年（1900~2200，可空）。 */
  base_year?: number | null;
  /** 基准 CEPCI（可空，>0）。 */
  cepci_index_base?: number | null;
  /** 目标 CEPCI（可空，>0）。 */
  cepci_index_target?: number | null;
  /** 关联式来源代码（maxLength=64，可空，如 'CC-TOWER-v1'）。 */
  correlation_source?: string | null;
  /** 60 法则 scaling 指数 n（0~1.5，可空）。 */
  scaling_exponent?: number | null;
}

// ---------------------------------------------------------------------------
// POST /api/v1/cost-est/six-tenths-rule/calculate
// ---------------------------------------------------------------------------

/** POST /cost-est/six-tenths-rule/calculate 请求：六十法则（C₂ = C₁ × (S₂/S₁)^n）+ CEPCI 调整。必填 5 字段。 */
export interface SixTenthsRuleCalcRequest {
  /** 设备 UUID（FK → equipment_list）。 */
  equipment_id: string;
  /** 基准投资 C₁（>=0）。 */
  reference_cost: number;
  /** 基准 CEPCI CEPCI₁（>0）。 */
  reference_cepci: number;
  /** 目标 CEPCI CEPCI₂（>0）。 */
  target_cepci: number;
  /** scaling 指数 n（0~1.5，默认 0.6）。 */
  scaling_exponent: number;
  /** 估算投资 C₂（>=0）。 */
  estimated_cost: number;
  /** 货币代码（maxLength=10，默认 USD）。 */
  currency?: string;
  /** 目标年（1900~2200，默认 2019）。 */
  cost_index_year?: number;
  /** 基准年成本 C₁（可空，>=0）。 */
  base_cost?: number | null;
  /** 基准年（1900~2200，可空）。 */
  base_year?: number | null;
}

/** POST /cost-est/six-tenths-rule/calculate 响应：CostEstBase 镜像 + result_id + equipment_id + created_at（201）。 */
export interface SixTenthsRuleCalcResponse extends CostEstBase {
  /** 计算结果 ID（cost_est_id；PK）。 */
  result_id: string;
  /** 设备 UUID。 */
  equipment_id: string;
  /** 创建时间（ISO 8601）。 */
  created_at: string;
}

// ---------------------------------------------------------------------------
// POST /api/v1/cost-est/cepci-adjustment/calculate
// ---------------------------------------------------------------------------

/** POST /cost-est/cepci-adjustment/calculate 请求：纯 CEPCI 时间/通胀调整（C₂ = C₁ × CEPCI₂/CEPCI₁）。必填 5 字段（无 scaling_exponent）。 */
export interface CepciAdjustmentCalcRequest {
  /** 设备 UUID。 */
  equipment_id: string;
  /** 基准投资 C₁（>=0）。 */
  reference_cost: number;
  /** 基准 CEPCI CEPCI₁（>0）。 */
  reference_cepci: number;
  /** 目标 CEPCI CEPCI₂（>0）。 */
  target_cepci: number;
  /** 估算投资 C₂（>=0）。 */
  estimated_cost: number;
  /** 货币代码（maxLength=10，默认 USD）。 */
  currency?: string;
  /** 目标年（1900~2200，默认 2019）。 */
  cost_index_year?: number;
  /** 基准年成本 C₁（可空，>=0）。 */
  base_cost?: number | null;
  /** 基准年（1900~2200，可空）。 */
  base_year?: number | null;
}

/** POST /cost-est/cepci-adjustment/calculate 响应：CostEstBase 镜像（无必填 scaling_exponent）+ result_id + equipment_id + created_at（201）。 */
export interface CepciAdjustmentCalcResponse extends CostEstBase {
  /** 计算结果 ID（cost_est_id；PK）。 */
  result_id: string;
  /** 设备 UUID。 */
  equipment_id: string;
  /** 创建时间（ISO 8601）。 */
  created_at: string;
}

// ---------------------------------------------------------------------------
// POST /api/v1/cost-est/cost-correlation/calculate
// ---------------------------------------------------------------------------

/** POST /cost-est/cost-correlation/calculate 请求：关联式计算（C = a × S^b；a/b 来自 CostCorrelationLibrary CONFIG 表）。必填 5 字段。 */
export interface CostCorrelationCalcRequest {
  /** 设备 UUID。 */
  equipment_id: string;
  /** 设备类型（TOWER/VESSEL/HEAT_EXCHANGER/PUMP/COMPRESSOR/PIPING）。 */
  equipment_type: EquipmentType;
  /** 规模参数 S（>0，如换热面积 m² / 塔径 m / 功率 kW）。 */
  scale_parameter: number;
  /** 关联式来源代码（maxLength=64，如 'CC-TOWER-v1'）。 */
  correlation_source: string;
  /** 估算投资 C₂（>=0）。 */
  estimated_cost: number;
  /** 货币代码（maxLength=10，默认 USD）。 */
  currency?: string;
  /** 目标年（1900~2200，默认 2019）。 */
  cost_index_year?: number;
  /** 基准年成本 C₁（可空，>=0）。 */
  base_cost?: number | null;
  /** 基准年（1900~2200，可空）。 */
  base_year?: number | null;
}

/** POST /cost-est/cost-correlation/calculate 响应：estimated_cost + currency + cost_index_year + base_cost + base_year + correlation_source + result_id + equipment_id + created_at（201）。 */
export interface CostCorrelationCalcResponse {
  /** 估算投资 C₂。 */
  estimated_cost: number;
  /** 货币代码。 */
  currency: string;
  /** 目标年。 */
  cost_index_year: number;
  /** 基准年成本 C₁（可空）。 */
  base_cost: number | null;
  /** 基准年（可空）。 */
  base_year: number | null;
  /** 关联式来源代码（可空）。 */
  correlation_source: string | null;
  /** 计算结果 ID。 */
  result_id: string;
  /** 设备 UUID。 */
  equipment_id: string;
  /** 创建时间（ISO 8601）。 */
  created_at: string;
}

// ---------------------------------------------------------------------------
// CRUD /api/v1/cost-est/results
// ---------------------------------------------------------------------------

/** POST /cost-est/results 请求体：必填 equipment_id + estimated_cost；其余 7 字段 optional。 */
export interface CostEstCreateRequest {
  /** 设备 UUID（FK → equipment_list）。 */
  equipment_id: string;
  /** 估算投资 C₂（>=0）。 */
  estimated_cost: number;
  /** 货币代码（maxLength=10，默认 USD）。 */
  currency?: string;
  /** 目标年（1900~2200，默认 2019）。 */
  cost_index_year?: number;
  /** 基准年成本 C₁（可空，>=0）。 */
  base_cost?: number | null;
  /** 基准年（1900~2200，可空）。 */
  base_year?: number | null;
  /** 基准 CEPCI（可空，>0）。 */
  cepci_index_base?: number | null;
  /** 目标 CEPCI（可空，>0）。 */
  cepci_index_target?: number | null;
  /** 关联式来源代码（maxLength=64，可空）。 */
  correlation_source?: string | null;
  /** 60 法则 scaling 指数 n（0~1.5，可空）。 */
  scaling_exponent?: number | null;
}

/** PATCH /cost-est/results/{result_id} 请求体：partial update；所有 9 字段 optional（PATCH 部分更新）；无 sign_status 锁定态门禁。 */
export interface CostEstUpdateRequest {
  estimated_cost?: number | null;
  currency?: string | null;
  cost_index_year?: number | null;
  base_cost?: number | null;
  base_year?: number | null;
  cepci_index_base?: number | null;
  cepci_index_target?: number | null;
  correlation_source?: string | null;
  scaling_exponent?: number | null;
}

/** COST_EST 单条响应（GET /cost-est/results/{result_id}）：完整业务字段；无 sign_status / record_hash / updated_at。ORM PK `cost_est_id` 重命名为 schema `result_id`。 */
export interface CostEstResultResponse {
  /** 结果 ID（cost_est_id；PK 重命名）。 */
  result_id: string;
  /** 设备 UUID（FK → equipment_list）。 */
  equipment_id: string;
  /** 估算投资 C₂。 */
  estimated_cost: number;
  /** 货币代码。 */
  currency: string;
  /** 目标年。 */
  cost_index_year: number;
  /** 基准年成本 C₁（可空）。 */
  base_cost: number | null;
  /** 基准年（可空）。 */
  base_year: number | null;
  /** 基准 CEPCI（可空）。 */
  cepci_index_base: number | null;
  /** 目标 CEPCI（可空）。 */
  cepci_index_target: number | null;
  /** 关联式来源代码（可空）。 */
  correlation_source: string | null;
  /** scaling 指数 n（可空）。 */
  scaling_exponent: number | null;
  /** 创建时间（ISO 8601）。 */
  created_at: string;
}

/** GET /cost-est/results 响应：CostEstResultResponse 列表 + 命中条数 + 分页回显。 */
export interface CostEstListResponse {
  /** CostEstResult 列表。 */
  items: CostEstResultResponse[];
  /** 命中条数。 */
  total: number;
  /** 分页偏移。 */
  skip: number;
  /** 分页上限。 */
  limit: number;
}

/** DELETE /cost-est/results/{result_id} 响应：物理删除（无 OBSOLETE 态）；含 result_id + equipment_id + deleted_at。 */
export interface CostEstDeleteResponse {
  /** 结果 ID（cost_est_id；PK）。 */
  result_id: string;
  /** 设备 UUID。 */
  equipment_id: string;
  /** 删除时间戳（ISO 8601）。 */
  deleted_at: string;
}
