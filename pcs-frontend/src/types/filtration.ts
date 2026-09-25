/**
 * FILTRATION 前端 TypeScript 类型（P6-3 frontend / Task 37）。
 *
 * SPEC §3.2.7 + 后端 OpenAPI（Task 34 commit 312e1b3 / Task 36 commit 5e14a3f）：
 * - 3 calc：POST /filtration/{ruth-constant-pressure|ruth-constant-rate|ergun}/calculate
 * - CRUD /api/v1/filtration/results：
 *   - POST → FiltrationCreateRequest 201
 *   - GET → FiltrationListResponse 200
 *   - GET /{result_id} → FiltrationResultResponse 200
 *   - PATCH /{result_id} → FiltrationUpdateRequest 200
 *   - DELETE /{result_id} → FiltrationDeleteResponse 200
 *
 * 设计要点：
 * - 业务字段与后端 Pydantic schema 1:1（snake_case 字段名）
 * - FiltrationBase 公共基础（4 必填 + 5 optional：media_type/area/cycle_time/pressure_drop +
 *   cake_resistance_alpha/specific_resistance_r0/permeability_k/porosity_eps/filter_velocity）
 * - 3 calc request 与 CreateRequest 共享 FiltrationBase 主体；
 *   calc request 多 project_id + workspace_id + tag_number 3 字段（Mixin 必填）
 * - 3 calc response 在 calc request 基础上 + result_id + record_hash + sign_status + created_at
 * - filter_type 字段为 RUTH_CONST_PRESSURE/RUTH_CONST_RATE/ERGUN_DEEP_BED
 *   （ResultResponse 中回显，CreateRequest 中必填）
 * - FiltrationUpdateRequest 为 partial update（所有字段 optional；service 层白名单校验）
 * - 软删除：tag_number 后缀加 `__OBSOLETE_<ts>`；sign_status 改为 OBSOLETE
 * - ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
 * - 错误码：FILTRATION_INPUT_ERROR 422 / FILTRATION_NOT_FOUND 404 /
 *         FILTRATION_PERSIST_SIGN_STATUS_LOCKED 422 / FILTRATION_PROJECT_MISMATCH 422
 *
 * @migrate-when: P6-3 regen + openapi-typescript 自动替换
 * @target: src/types/api.d.ts
 * @reason: 后端 OpenAPI 已定义 endpoint，但 api.d.ts regen 暂未触发；
 *         P6-3 frontend type 闭环需要手写类型过渡，待 V1.4 regen 替换。
 */

import type { RecordSignStatus } from './records';

// ---------------------------------------------------------------------------
// 枚举 / 字面量
// ---------------------------------------------------------------------------

/** FILTRATION 计算类型：RUTH_CONST_PRESSURE / RUTH_CONST_RATE / ERGUN_DEEP_BED（与 OpenAPI 描述对齐）。 */
export type FilterType = 'RUTH_CONST_PRESSURE' | 'RUTH_CONST_RATE' | 'ERGUN_DEEP_BED';

/** FILTRATION 公共基础（4 必填 + 5 optional）。 */
export interface FiltrationBase {
  /** 介质代码（SAND/ANTHRACITE/CARBON/RUTH_FILTER_CLOTH/ERGUN_PACKING）。 */
  media_type: string;
  /** 过滤面积 A（m²）。 */
  area: number;
  /** 过滤周期（h）。 */
  cycle_time: number;
  /** 压降（Pa）。 */
  pressure_drop: number;
  /** 滤饼比阻 α（m/kg，可空）。 */
  cake_resistance_alpha?: number | null;
  /** 介质单位阻力 R₀（1/m，可空）。 */
  specific_resistance_r0?: number | null;
  /** 渗透率 k（m²，可空，>0）。 */
  permeability_k?: number | null;
  /** 床层空隙率 ε（无量纲，0~1，可空）。 */
  porosity_eps?: number | null;
  /** 过滤速率 v（m/s，可空）。 */
  filter_velocity?: number | null;
}

// ---------------------------------------------------------------------------
// POST /api/v1/filtration/ruth-constant-pressure/calculate
// ---------------------------------------------------------------------------

/** POST /filtration/ruth-constant-pressure/calculate 请求：Ruth 恒压过滤方程（t/V = (μαc/2A²ΔP)V + μRm/AΔP）。 */
export interface RuthConstantPressureCalcRequest extends FiltrationBase {
  /** 项目 ID（UUID；isolation key）。 */
  project_id: string;
  /** 工作区 ID（UUID）。 */
  workspace_id: string;
  /** 位号（per-project 唯一；TaggedRecordMixin NOT NULL）。 */
  tag_number: string;
}

/** POST /filtration/ruth-constant-pressure/calculate 响应：RuthConstantPressureCalcRequest + result_id + record_hash + sign_status + created_at。 */
export interface RuthConstantPressureCalcResponse extends RuthConstantPressureCalcRequest {
  /** 计算结果 ID（filter_id；ORM PK 重命名为 schema result_id）。 */
  result_id: string;
  /** record_hash（ADR-0028 §决策 4 reflection；16 hex）。 */
  record_hash: string | null;
  /** 签审状态 9 态。 */
  sign_status: RecordSignStatus;
  /** 创建时间（ISO 8601）。 */
  created_at: string;
}

// ---------------------------------------------------------------------------
// POST /api/v1/filtration/ruth-constant-rate/calculate
// ---------------------------------------------------------------------------

/** POST /filtration/ruth-constant-rate/calculate 请求：Ruth 恒速过滤方程（t/V = ...）。 */
export type RuthConstantRateCalcRequest = RuthConstantPressureCalcRequest;

/** POST /filtration/ruth-constant-rate/calculate 响应：恒速过滤计算产物。 */
export type RuthConstantRateCalcResponse = RuthConstantPressureCalcResponse;

// ---------------------------------------------------------------------------
// POST /api/v1/filtration/ergun/calculate
// ---------------------------------------------------------------------------

/** POST /filtration/ergun/calculate 请求：Ergun 方程（−ΔP/L = 150μ(1−ε)²/(dp²ε³) × ρv + 1.75(1−ε)/(dpε³) × ρv²）。 */
export type ErgunCalcRequest = RuthConstantPressureCalcRequest;

/** POST /filtration/ergun/calculate 响应：深床过滤计算产物。 */
export type ErgunCalcResponse = RuthConstantPressureCalcResponse;

// ---------------------------------------------------------------------------
// CRUD /api/v1/filtration/results
// ---------------------------------------------------------------------------

/** POST /filtration/results 请求体：FiltrationBase + 隔离 + 位号 + filter_type（必填）。 */
export interface FiltrationCreateRequest extends FiltrationBase {
  /** 项目 ID（UUID）。 */
  project_id: string;
  /** 工作区 ID（UUID）。 */
  workspace_id: string;
  /** 位号（per-project 唯一；maxLength=64, minLength=1）。 */
  tag_number: string;
  /** 过滤类型（RUTH_CONST_PRESSURE/RUTH_CONST_RATE/ERGUN_DEEP_BED；必填）。 */
  filter_type: FilterType;
}

/** PATCH /filtration/results/{result_id} 请求体：partial update；所有字段 optional（PATCH 部分更新）；service 层白名单校验。 */
export interface FiltrationUpdateRequest {
  filter_type?: string | null;
  media_type?: string | null;
  area?: number | null;
  cycle_time?: number | null;
  pressure_drop?: number | null;
  cake_resistance_alpha?: number | null;
  specific_resistance_r0?: number | null;
  permeability_k?: number | null;
  porosity_eps?: number | null;
  filter_velocity?: number | null;
}

/** FILTRATION 单条响应（GET /filtration/results/{result_id}）：溯源 + FiltrationBase + filter_type + 时间戳。ORM PK `filter_id` 重命名为 schema `result_id`。 */
export interface FiltrationResultResponse extends FiltrationBase {
  /** 项目 ID（UUID；isolation key）。 */
  project_id: string;
  /** 工作区 ID（UUID）。 */
  workspace_id: string;
  /** 位号（maxLength=64, minLength=1）。 */
  tag_number: string;
  /** 结果 ID（filter_id；ORM PK 重命名；前端统一用 result_id）。 */
  result_id: string;
  /** 过滤类型（回显；ResultResponse 必填）。 */
  filter_type: string;
  /** 签审状态 9 态。 */
  sign_status: RecordSignStatus;
  /** record_hash（16 hex）。 */
  record_hash: string | null;
  /** 创建时间（ISO 8601）。 */
  created_at: string;
  /** 更新时间（ISO 8601；可空）。 */
  updated_at: string | null;
}

/** GET /filtration/results 响应：FiltrationResultResponse 列表 + 命中条数 + 分页回显。 */
export interface FiltrationListResponse {
  /** FiltrationResult 列表。 */
  items: FiltrationResultResponse[];
  /** 命中条数（受 include_obsolete 影响）。 */
  total: number;
  /** 分页偏移。 */
  skip: number;
  /** 分页上限。 */
  limit: number;
}

/** DELETE /filtration/results/{result_id} 响应：result_id + tag_number（含 __OBSOLETE_<ts> 后缀）+ sign_status（OBSOLETE）+ deleted_at。 */
export interface FiltrationDeleteResponse {
  /** 结果 ID（filter_id；PK）。 */
  result_id: string;
  /** 位号（含 `__OBSOLETE_<ts>` 后缀）。 */
  tag_number: string;
  /** 签审状态（已改为 OBSOLETE）。 */
  sign_status: RecordSignStatus;
  /** 删除时间（updated_at）。 */
  deleted_at: string;
}
