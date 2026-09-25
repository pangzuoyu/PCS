/**
 * OPEN_CHANNEL 前端 TypeScript 类型（P6-3 frontend / Task 37）。
 *
 * SPEC §3.2.6 + 后端 OpenAPI（Task 32 commit ce675a6 / Task 36 commit 5e14a3f）：
 * - 4 calc：POST /open-channel/{manning|section|critical|jump}/calculate
 * - CRUD /api/v1/open-channel/results：
 *   - POST → OpenChannelCreateRequest 201
 *   - GET → OpenChannelListResponse 200
 *   - GET /{result_id} → OpenChannelResultResponse 200
 *   - PATCH /{result_id} → OpenChannelUpdateRequest 200
 *   - DELETE /{result_id} → OpenChannelDeleteResponse 200
 *
 * 设计要点：
 * - 业务字段与后端 Pydantic schema 1:1（snake_case 字段名）
 * - OpenChannelBase 公共基础（15 字段：channel_type + cross_section_json +
 *   flow_rate/depth/velocity/slope + 8 optional 业务字段）
 * - 4 calc request 与 CreateRequest 共享 OpenChannelBase 主体；
 *   calc request 多 project_id + workspace_id + tag_number 3 字段（Mixin 必填）
 * - 4 calc response 在 calc request 基础上 + result_id + sign_status + record_hash + created_at
 * - OpenChannelUpdateRequest 为 partial update（所有字段 optional；service 层白名单校验）
 * - channel_type 字面量 RECT/TRAP/CIRC 与 OpenAPI 描述一致
 * - 软删除：tag_number 后缀加 `__OBSOLETE_<ts>`；sign_status 改为 OBSOLETE
 * - ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
 * - 错误码：OPEN_CHANNEL_INPUT_ERROR 422 / OPEN_CHANNEL_NOT_FOUND 404 /
 *         OPEN_CHANNEL_PERSIST_SIGN_STATUS_LOCKED 422 / OPEN_CHANNEL_PROJECT_MISMATCH 422
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

/** OPEN_CHANNEL 断面类型：RECT 矩形 / TRAP 梯形 / CIRC 圆形（与 OpenAPI 描述对齐）。 */
export type ChannelType = 'RECT' | 'TRAP' | 'CIRC';

/** OPEN_CHANNEL 公共基础（15 字段 + 8 optional 业务字段）。 */
export interface OpenChannelBase {
  /** 断面类型（RECT / TRAP / CIRC）。 */
  channel_type: ChannelType;
  /** 断面几何 {bottom_width, side_slope, diameter}（additionalProperties: true 自由键）。 */
  cross_section_json: Record<string, number>;
  /** 流量 Q（m³/s）。 */
  flow_rate: number;
  /** 水深 h（m）。 */
  depth: number;
  /** 流速 v（m/s）。 */
  velocity: number;
  /** 坡度 S（m/m）。 */
  slope: number;
  /** 临界水深 h_c（m，可空）。 */
  critical_depth?: number | null;
  /** Froude 数 Fr（可空）。 */
  froude_number?: number | null;
  /** Manning 糙率 n（可空，>0）。 */
  manning_n?: number | null;
  /** 水力半径 R（m，可空）。 */
  hydraulic_radius?: number | null;
  /** 水跃类型 WAVY/WEAK/OSCILLATING/STEADY/STRONG（可空）。 */
  jump_type?: string | null;
  /** 水跃共轭水深（m，可空）。 */
  conjugate_depth?: number | null;
  /** 水跃能量损失 ΔE（m，可空）。 */
  energy_loss?: number | null;
}

// ---------------------------------------------------------------------------
// POST /api/v1/open-channel/manning/calculate
// ---------------------------------------------------------------------------

/** POST /open-channel/manning/calculate 请求：Manning 公式（Q = A/n × R^(2/3) × S^(1/2)）— OpenChannelBase + 隔离 + 位号。 */
export interface ManningCalcRequest extends OpenChannelBase {
  /** 项目 ID（UUID；isolation key）。 */
  project_id: string;
  /** 工作区 ID（UUID）。 */
  workspace_id: string;
  /** 位号（per-project 唯一；TaggedRecordMixin NOT NULL）。 */
  tag_number: string;
}

/** POST /open-channel/manning/calculate 响应：ManningCalcRequest + result_id + record_hash + sign_status + created_at。 */
export interface ManningCalcResponse extends ManningCalcRequest {
  /** 计算结果 ID（open_channel_id；ORM PK 重命名为 schema result_id）。 */
  result_id: string;
  /** record_hash（ADR-0028 §决策 4 reflection；16 hex）。 */
  record_hash: string | null;
  /** 签审状态 9 态。 */
  sign_status: RecordSignStatus;
  /** 创建时间（ISO 8601）。 */
  created_at: string;
}

// ---------------------------------------------------------------------------
// POST /api/v1/open-channel/section/calculate
// ---------------------------------------------------------------------------

/** POST /open-channel/section/calculate 请求：断面水力要素计算（v=Q/A, R=A/P）— 与 ManningCalcRequest 同 OpenChannelBase。 */
export type SectionCalcRequest = ManningCalcRequest;

/** POST /open-channel/section/calculate 响应：断面水力要素计算产物。 */
export type SectionCalcResponse = ManningCalcResponse;

// ---------------------------------------------------------------------------
// POST /api/v1/open-channel/critical/calculate
// ---------------------------------------------------------------------------

/** POST /open-channel/critical/calculate 请求：临界水深/Froude 数计算（Fr=1 时 h_c）。 */
export type CriticalCalcRequest = ManningCalcRequest;

/** POST /open-channel/critical/calculate 响应：临界水深 h_c + Froude 数。 */
export type CriticalCalcResponse = ManningCalcResponse;

// ---------------------------------------------------------------------------
// POST /api/v1/open-channel/jump/calculate
// ---------------------------------------------------------------------------

/** POST /open-channel/jump/calculate 请求：水跃共轭水深/能量损失计算（Bélanger 方程）。 */
export type JumpCalcRequest = ManningCalcRequest;

/** POST /open-channel/jump/calculate 响应：水跃计算产物（conjugate_depth + energy_loss + jump_type）。 */
export type JumpCalcResponse = ManningCalcResponse;

// ---------------------------------------------------------------------------
// CRUD /api/v1/open-channel/results
// ---------------------------------------------------------------------------

/** POST /open-channel/results 请求体：OpenChannelBase 字段子集 + 隔离 + 位号（所有 8 optional 业务字段可填）。 */
export interface OpenChannelCreateRequest extends OpenChannelBase {
  /** 项目 ID（UUID）。 */
  project_id: string;
  /** 工作区 ID（UUID）。 */
  workspace_id: string;
  /** 位号（per-project 唯一；maxLength=64, minLength=1）。 */
  tag_number: string;
}

/** PATCH /open-channel/results/{result_id} 请求体：partial update；所有字段 optional（PATCH 部分更新）；service 层白名单校验。 */
export interface OpenChannelUpdateRequest {
  channel_type?: string | null;
  cross_section_json?: Record<string, number> | null;
  flow_rate?: number | null;
  depth?: number | null;
  velocity?: number | null;
  slope?: number | null;
  critical_depth?: number | null;
  froude_number?: number | null;
  manning_n?: number | null;
  hydraulic_radius?: number | null;
  jump_type?: string | null;
  conjugate_depth?: number | null;
  energy_loss?: number | null;
}

/** OPEN_CHANNEL 单条响应（GET /open-channel/results/{result_id}）：溯源 + OpenChannelBase + 时间戳。ORM PK `open_channel_id` 重命名为 schema `result_id`。 */
export interface OpenChannelResultResponse extends OpenChannelBase {
  /** 项目 ID（UUID；isolation key）。 */
  project_id: string;
  /** 工作区 ID（UUID）。 */
  workspace_id: string;
  /** 位号（maxLength=64, minLength=1）。 */
  tag_number: string;
  /** 结果 ID（open_channel_id；ORM PK 重命名；前端统一用 result_id）。 */
  result_id: string;
  /** 签审状态 9 态。 */
  sign_status: RecordSignStatus;
  /** record_hash（16 hex）。 */
  record_hash: string | null;
  /** 创建时间（ISO 8601）。 */
  created_at: string;
  /** 更新时间（ISO 8601；可空）。 */
  updated_at: string | null;
}

/** GET /open-channel/results 响应：OpenChannelResultResponse 列表 + 命中条数 + 分页回显。 */
export interface OpenChannelListResponse {
  /** OpenChannelResult 列表。 */
  items: OpenChannelResultResponse[];
  /** 命中条数（受 include_obsolete 影响）。 */
  total: number;
  /** 分页偏移。 */
  skip: number;
  /** 分页上限。 */
  limit: number;
}

/** DELETE /open-channel/results/{result_id} 响应：result_id + tag_number（含 __OBSOLETE_<ts> 后缀）+ sign_status（OBSOLETE）+ deleted_at。 */
export interface OpenChannelDeleteResponse {
  /** 结果 ID（open_channel_id；PK）。 */
  result_id: string;
  /** 位号（含 `__OBSOLETE_<ts>` 后缀）。 */
  tag_number: string;
  /** 签审状态（已改为 OBSOLETE）。 */
  sign_status: RecordSignStatus;
  /** 删除时间（updated_at）。 */
  deleted_at: string;
}
