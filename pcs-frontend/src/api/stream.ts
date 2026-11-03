/**
 * SIM 物流 API 客户端（P9B-3 · T6/T7/T8 扩展）。
 *
 * ⚠️ **两个列表方法并存，各有各的形状**（别合并）：
 *
 * | 方法 | 返回 | 谁在用 |
 * |---|---|---|
 * | `listByProject` | **手写轻量子集**（`StreamListItem`，5 字段） | Vessel / SepEquip / Heat / Cv 四个计算页（OPEN-4-1/2/6） |
 * | `list` | **契约派生**（`StreamResponse` 完整 + 四项筛选） | 物流列表页（T6） |
 *
 * ⚠️ **`listByProject` 的名字与形状都保持不变** —— 计划要求把它的返回类型换成
 * 契约派生，但**实测会打破 4 个消费者**：它们把结果映射成
 * `{stream_id, tag_number}`（`tag_number` **不在契约里**，物流没有位号）⇒
 * 换成契约派生后那 4 处 `s.tag_number` 全部编译不过 ⇒ 本批**另开** `list`
 * 走契约派生，`listByProject` 一行不动（代价：那份手写轻量子集继续是技术债，
 * 已登记 TODO-109）。
 *
 * ⚠️ 类型**契约派生** —— 手写副本缺几十个必填字段 ⇒ 后端加字段前端静默丢。
 */
import { api } from './client';
import type { components } from '../types/api';
import type { Stream } from '../types/stream';

export type { Stream };

/** 批量提交校对的响应（**契约派生** · P9B-3b）。 */
export type StreamBatchSubmitResponse = components['schemas']['StreamBatchSubmitResponse'];
/** 批量里成功的一条（契约派生）。 */
export type StreamBatchSucceeded = components['schemas']['BatchSucceededItem'];
/** 批量里失败的一条（契约派生）。 */
export type StreamBatchFailed = components['schemas']['BatchFailedItem'];

/** 契约的 `StreamSource`（4 值 · 录入通道）。 */
export type StreamSource = components['schemas']['StreamSource'];
/** 契约的 `StreamCaseType`（4 值 · 设计工况）。 */
export type StreamCaseType = components['schemas']['StreamCaseType'];
/** 契约的 `StreamSignStatus`（9 态）。 */
export type StreamSignStatus = components['schemas']['StreamSignStatus'];

/**
 * 列表筛选（SPEC §7.7.1：工况 / 相态 / 状态 / 来源，**后端按 AND 组合**）。
 *
 * ⚠️ 四个字段名与后端 Query 参数**逐字一致**（`case_type` / `phase` /
 * `sign_status` / `source`）—— 改名会让筛选「看着生效其实没筛」。
 */
export interface StreamListFilters {
  case_type?: StreamCaseType;
  phase?: components['schemas']['StreamPhase'];
  sign_status?: StreamSignStatus;
  source?: StreamSource;
}

/**
 * 轻量子集（**手写**）—— 四个计算页的老消费者在用。
 *
 * ⚠️ `tag_number` **不在契约里**（物流是流量不是设备，没有位号）⇒ 这份形状
 * 已经是历史债；新代码请用 `list()`。
 */
export interface StreamListItem {
  stream_id: string;
  tag_number: string;
  stream_name: string;
  phase?: string;
  subphase?: string;
}

/** 契约的 `ValidateStreamResponse`（校验三色）。 */
export type ValidateStreamResponse = components['schemas']['ValidateStreamResponse'];

/**
 * 写入载荷 —— **契约派生**（字段名取自 `StreamResponse`）。
 *
 * ⚠️ 契约里 `CreateStreamRequest.payload` 是**裸 object**
 * （`additionalProperties: true`，**没有结构**）⇒ 没有具名 schema 可引用 ⇒
 * 这里从**响应** schema 取字段名（`StreamBase` 与 `StreamResponse` 同名同义）。
 * ⚠️ 这是裸载荷闸门里的**已知缺口**（登记为 TODO-110）⇒ 后端把 payload
 * 收紧成具名 schema 后，这里换成 `components['schemas'][...]` 即可。
 */
export type StreamCreatePayload = Pick<
  Stream,
  | 'stream_name'
  | 'description'
  | 'case_type'
  | 'data_mode'
  | 'phase'
  | 'temp'
  | 'press'
  | 'mass_flow'
  | 'molar_flow'
  | 'composition_json'
>;

/**
 * 状态点载荷 —— ⚠️ **手写**（契约里 state-points 的 body 同样是裸 object）。
 *
 * 字段与后端 `StreamStatePointBase` 逐字一致；必填项：
 * `state_label` / `case_type` / `temp` / `press` / `phase` / `mass_flow` /
 * `composition_json` / `source_type`。
 */
export interface StatePointPayload {
  state_label: string;
  case_type: 'NORMAL' | 'MIN' | 'MAX' | 'ALTERNATE';
  temp: number;
  press: number;
  phase: components['schemas']['StreamPhase'];
  mass_flow: number;
  composition_json: Record<string, unknown>;
  vapor_fraction?: number | null;
  source_type: components['schemas']['StreamSourceType'];
}

/**
 * 物性（`GET /streams/{id}/properties`）—— ⚠️ 契约里响应是**裸 dict**
 * （`additionalProperties: true`，**无结构**）⇒ 本地类型（见 TODO-111）。
 */
export interface StreamProperties {
  [key: string]: unknown;
}

/**
 * 状态点（`GET /streams/{id}/state-points`）—— ⚠️ 裸 object 数组（TODO-111）。
 *
 * ⚠️ 值类型一律**可选**：后端可能返回缺字段的行 ⇒ 渲染层必须防御性读。
 */
export interface StreamStatePoint {
  state_label?: string;
  case_type?: string;
  temp?: number | null;
  press?: number | null;
  phase?: string | null;
  mass_flow?: number | null;
  vapor_fraction?: number | null;
  [key: string]: unknown;
}

/** 血缘条目（`GET /lineage/{record_type}/{record_id}/graph` 的一项）。 */
export interface LineageEntry {
  lineage_id?: string;
  record_type?: string;
  record_id?: string;
  parent_lineage_id?: string | null;
  source?: string | null;
  source_ref_type?: string | null;
  source_ref_id?: string | null;
  actor_user_id?: string | null;
  change_summary?: string | null;
  occurred_at?: string | null;
}

/** 血缘图 —— ⚠️ 契约里是**裸 dict**（TODO-111）。 */
export interface LineageGraph {
  root?: LineageEntry;
  upstream?: LineageEntry[];
  downstream?: LineageEntry[];
}

export const streamApi = {
  /** 物流列表（契约派生 + 四项筛选）—— 物流列表页用。 */
  list: (projectId: string, filters: StreamListFilters = {}): Promise<Stream[]> =>
    api
      .get<Stream[]>(`/projects/${projectId}/streams`, { params: filters })
      .then((r) => r.data),

  /** GET /api/v1/projects/{project_id}/streams（**轻量子集** · 老消费者专用）。 */
  listByProject: (projectId: string): Promise<StreamListItem[]> =>
    api
      .get<StreamListItem[]>(`/projects/${projectId}/streams`)
      .then((r) => r.data),

  /**
   * 单条**提交校对**（DRAFT → IN_APPROVAL）。
   *
   * ⚠️ 与工具栏那条「批量提交校对」（⏳ P9B-3b）**不是同一件事**。
   * ⚠️ 组成合计不在 100±0.5% ⇒ 后端 422 `SIM_STREAM_COMPOSITION_OUT_OF_RANGE`
   * ⇒ **状态不变**（前端据此提示，不改徽章）。
   */
  submitForReview: (streamId: string): Promise<unknown> =>
    api.post(`/streams/${streamId}/submit`).then((r) => r.data),

  /**
   * 批量**提交校对**（`POST /streams/batch-submit` · 207 Multi-Status）。
   *
   * ⚠️ **207 是 2xx ⇒ axios 不抛异常** ⇒ 部分失败**不会**进 catch ⇒
   * 调用方**必须自己看** `failed` 数组（`failed.length > 0` ⇒ 有条没成）。
   * ⚠️ 与行操作那条「校对」（`submitForReview`，单条）**不是同一件事**。
   */
  batchSubmitForReview: (
    streamIds: string[],
    dryRun = false,
  ): Promise<StreamBatchSubmitResponse> =>
    api
      .post<StreamBatchSubmitResponse>('/streams/batch-submit', {
        stream_ids: streamIds,
        dry_run: dryRun,
      })
      .then((r) => r.data),
  /** 发起变更（CHECKED → CHANGE_PENDING，ADR-0002）。 */
  initiateChange: (streamId: string, reason?: string): Promise<unknown> =>
    api
      .post(`/streams/${streamId}/initiate-change`, { reason: reason ?? null })
      .then((r) => r.data),

  /**
   * 校验（POST /projects/{id}/streams/validate）—— **写入前**的门禁。
   *
   * ⚠️ 返回的 `blocks` / `warnings` / `infos` 是**裸 object 数组**（契约无结构）
   * ⇒ 前端**防御性**读 `code` / `message`。
   */
  validate: (
    projectId: string,
    payload: StreamCreatePayload,
  ): Promise<ValidateStreamResponse> =>
    api
      .post<ValidateStreamResponse>(`/projects/${projectId}/streams/validate`, { payload })
      .then((r) => r.data),

  /** 写入 DRAFT（POST /projects/{id}/streams）。 */
  create: (projectId: string, payload: StreamCreatePayload): Promise<Stream> =>
    api.post<Stream>(`/projects/${projectId}/streams`, { payload }).then((r) => r.data),

  /** 状态点（POST /streams/{id}/state-points）。 */
  createStatePoint: (streamId: string, payload: StatePointPayload): Promise<unknown> =>
    api.post(`/streams/${streamId}/state-points`, payload).then((r) => r.data),

  /** 物性（GET /streams/{id}/properties）。 */
  properties: (streamId: string): Promise<StreamProperties> =>
    api.get<StreamProperties>(`/streams/${streamId}/properties`).then((r) => r.data),

  /** 状态点（GET /streams/{id}/state-points）。 */
  statePoints: (streamId: string): Promise<StreamStatePoint[]> =>
    api.get<StreamStatePoint[]>(`/streams/${streamId}/state-points`).then((r) => r.data),

  /** 血缘图（GET /lineage/{record_type}/{record_id}/graph）。 */
  lineageGraph: (recordType: string, recordId: string): Promise<LineageGraph> =>
    api.get<LineageGraph>(`/lineage/${recordType}/${recordId}/graph`).then((r) => r.data),

  /**
   * 物性估算（POST /streams/{id}/properties/estimate）。
   *
   * ⚠️ **失败不阻塞**提交校对（用户裁决 2：估算���增强，不是门禁）⇒ 调用方
   * 自行决定「提示后继续」。
   */
  estimateProperties: (streamId: string, casList: string[]): Promise<unknown> =>
    api
      .post(`/streams/${streamId}/properties/estimate`, { cas_list: casList })
      .then((r) => r.data),
};
