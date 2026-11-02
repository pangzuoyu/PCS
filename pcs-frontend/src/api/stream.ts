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

  /** 发起变更（CHECKED → CHANGE_PENDING，ADR-0002）。 */
  initiateChange: (streamId: string, reason?: string): Promise<unknown> =>
    api
      .post(`/streams/${streamId}/initiate-change`, { reason: reason ?? null })
      .then((r) => r.data),
};
