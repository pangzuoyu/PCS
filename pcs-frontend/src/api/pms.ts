/**
 * PMS / BEDD API 客户端（P10-H · T2 · TODO-195）。
 *
 * ## 形状以契约为准
 *
 * `PmsItemResponse` / `PmsItemListResponse` / `BeddDocument` / `BeddResponse`
 * 全部来自 `src/types/api.d.ts`（OpenAPI 生成）⇒ ⇒ **不手写副本**
 * ⇒ ⇒ 前端手写类型漂移的那一类缺陷（bug-180）从根上没了。
 *
 * ## 签署不在这里
 *
 * 送审 / 审批 / 作废走**通用记录工作流**
 * （`/records/PmsItem/{id}/submit-approval` …）⇒ ⇒ 用
 * `recordActionsApi` ⇒ ⇒ 本模块只管「建 / 改 / 列」。
 */
import { api } from './client';
import type { components } from '../types/api';

/** PMS 条目（契约 `PmsItemResponse`）。 */
export type PmsItem = components['schemas']['PmsItemResponse'];
/** PMS 列表响应（契约 `PmsItemListResponse`）。 */
export type PmsItemListResponse = components['schemas']['PmsItemListResponse'];
/** 新建 PMS 条目的请求体（契约 `PmsItemCreate`）。 */
export type PmsItemCreate = components['schemas']['PmsItemCreate'];
/** 修改 PMS 条目的请求体（契约 `PmsItemUpdate`）。 */
export type PmsItemUpdate = components['schemas']['PmsItemUpdate'];
/** BEDD 文档（契约 `BeddDocument`）。 */
export type BeddDocument = components['schemas']['BeddDocument'];
/** BEDD 读取响应（契约 `BeddResponse`）。 */
export type BeddResponse = components['schemas']['BeddResponse'];

export const pmsApi = {
  /** `GET /projects/{project_id}/pms`（列表）。 */
  list: (projectId: string): Promise<PmsItemListResponse> =>
    api.get<PmsItemListResponse>(`/projects/${projectId}/pms`).then((r) => r.data),

  /** `POST /projects/{project_id}/pms`（新建 ⇒ ⇒ DRAFT）。 */
  create: (projectId: string, body: PmsItemCreate): Promise<PmsItem> =>
    api.post<PmsItem>(`/projects/${projectId}/pms`, body).then((r) => r.data),

  /** `PATCH /projects/{project_id}/pms/{item_id}`（**仅 DRAFT**）。 */
  update: (projectId: string, itemId: string, body: PmsItemUpdate): Promise<PmsItem> =>
    api
      .patch<PmsItem>(`/projects/${projectId}/pms/${itemId}`, body)
      .then((r) => r.data),
};

export const beddApi = {
  /** `GET /projects/{project_id}/bedd`（**没写过 ⇒ 空文档**，不是 404）。 */
  get: (projectId: string): Promise<BeddResponse> =>
    api.get<BeddResponse>(`/projects/${projectId}/bedd`).then((r) => r.data),

  /** `PUT /projects/{project_id}/bedd`（**整份替换**）。 */
  put: (projectId: string, document: BeddDocument): Promise<BeddResponse> =>
    api.put<BeddResponse>(`/projects/${projectId}/bedd`, document).then((r) => r.data),
};
