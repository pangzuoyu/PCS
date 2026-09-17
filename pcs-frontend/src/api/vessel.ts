/**VESSEL 容器计算 API 客户端（P5 frontend 全栈收口 / OPEN-4-1）。

按 SPEC §7.11.3 + 后端 OpenAPI（app/api/v1/vessel.py）：
- POST /api/v1/vessel/calculate（VesselCalculateRequest → VesselCalculateResponse）

错误通过 PcsError envelope 抛出：
- STREAM_NOT_CHECKED 403 — 源流未签出（仅 CHECKED 可算）
- HEAT_INPUT_ERROR 422 / VESSEL_NOT_FOUND 404 等

前端 message.error 显示 message 字段；StreamListItem 流列表由 streamApi 提供
（OPEN-6 已在 HeatComputePage 接入，VESSEL 复用 streamApi.listByProject）。
*/
import { api } from './client';
import type {
  VesselCalculateRequest,
  VesselCalculateResponse,
} from '../types/vessel';

export const vesselApi = {
  /**POST /api/v1/vessel/calculate。*/
  calculate: (req: VesselCalculateRequest): Promise<VesselCalculateResponse> =>
    api.post<VesselCalculateResponse>('/vessel/calculate', req).then((r) => r.data),
};
