/**
 * P5-3 PSV 计算 + 项目标准配置 API 客户端（V1.2 SPEC §7.11.5）。
 *
 * 按 SPEC V1.2 + 后端 OpenAPI（commit 93627a7）：
 * - POST /api/v1/psv/calculate → PsvCalculateResponse
 * - GET /api/v1/projects/{pid}/psv/standard-profile → PsvStandardProfile | null
 * - POST /api/v1/projects/{pid}/psv/standard-profile → PsvStandardProfile（创建/激活）
 *
 * 错误通过 PcsError envelope 抛出（code/message/detail/trace_id）；
 * 401 由 client.ts response interceptor 兜底跳登录，其他 code 由业务层 try/catch。
 */

import { api } from './client';
import type {
  PsvCalculateRequest,
  PsvCalculateResponse,
  PsvStandardProfile,
  UpsertPsvStandardProfileRequest,
} from '../types/psv';

export const psvApi = {
  calculate: (req: PsvCalculateRequest) =>
    api
      .post<PsvCalculateResponse>('/psv/calculate', req)
      .then((r) => r.data),

  getStandardProfile: (projectId: string) =>
    api
      .get<PsvStandardProfile | null>(
        `/projects/${projectId}/psv/standard-profile`,
      )
      .then((r) => r.data),

  upsertStandardProfile: (
    projectId: string,
    req: UpsertPsvStandardProfileRequest,
  ) =>
    api
      .post<PsvStandardProfile>(
        `/projects/${projectId}/psv/standard-profile`,
        req,
      )
      .then((r) => r.data),
};