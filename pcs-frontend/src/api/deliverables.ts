/**
 * 交付物读面客户端 —— P9B-2 · SPEC §6.24 / §7.19。
 *
 * ⚠️ `progress` 打的是**聚合端点** `GET /deliverables/{id}/progress`
 * （TODO-065），**不是** `GET /workflow-progress/SIGN/{version_id}` ——
 * 两类工作流的 `workflow_id` 语义各不相同（SIGN = 版本 id，
 * CUSTOMER_APPROVAL_PROXY = **交付物 id**），关联规则归后端（R-2 / R-13）。
 */
import { api } from './client';
import type { components } from '../types/api';

export type DeliverableProgressResponse =
  components['schemas']['DeliverableProgressResponse'];
export type WorkflowProgressSection = components['schemas']['WorkflowProgressSection'];
export type DeliverableActionsListResponse =
  components['schemas']['DeliverableActionsListResponse'];

export const deliverablesApi = {
  progress: (deliverableId: string): Promise<DeliverableProgressResponse> =>
    api
      .get<DeliverableProgressResponse>(`/deliverables/${deliverableId}/progress`)
      .then((r) => r.data),

  actions: (
    deliverableId: string,
    params?: { limit?: number; offset?: number },
  ): Promise<DeliverableActionsListResponse> =>
    api
      .get<DeliverableActionsListResponse>(`/deliverables/${deliverableId}/actions`, {
        params,
      })
      .then((r) => r.data),
};
