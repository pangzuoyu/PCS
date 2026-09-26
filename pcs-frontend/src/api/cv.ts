/**CV 控制阀计算 API 客户端（P6-5 前端补课 / 3 计算页）。

按 UI SPEC §7.12 + 后端 OpenAPI（app/api/v1/cv.py）：
- POST /api/v1/cv/calculate
  （CvCalculateRequest → CvCalculateResponse；IEC 60534 Cv + P6-4 Masonelian fl）

错误通过 PcsError envelope 抛出（api client 统一处理 401）：
- CV_INPUT_ERROR 422（phase 分支字段缺失 / 越界）
- CV_VALVE_LIBRARY_MISS 404（valve_type+manufacturer 组合未命中）
*/
import { api } from './client';
import type {
  CvCalculateRequest,
  CvCalculateResponse,
} from '../types/cv';

export const cvApi = {
  /**POST /api/v1/cv/calculate（IEC 60534 Cv + Masonelian fl）。*/
  calculate: (req: CvCalculateRequest): Promise<CvCalculateResponse> =>
    api.post<CvCalculateResponse>('/cv/calculate', req).then((r) => r.data),
};
