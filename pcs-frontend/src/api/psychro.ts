/**PSYCHRO 计算 API 客户端（P6-5 前端补课 / 3 计算页）。

按 UI SPEC §7.12 + 后端 OpenAPI（app/api/v1/psychro.py）：
- POST /api/v1/psychro/saturation-water-content/calculate
  （SaturationWaterContentRequest → Response；C-17 显式水含量）

错误通过 PcsError envelope 抛出（api client 统一处理 401）：
- SATURATION_WATER_CONTENT_INPUT_ERROR 422（T/P 越界）
- PSYCHRO_CALC_ERROR 502（CoolProp 拒绝工况）
*/
import { api } from './client';
import type {
  SaturationWaterContentRequest,
  SaturationWaterContentResponse,
} from '../types/psychro';

export const psychroApi = {
  /**POST /psychro/saturation-water-content/calculate（C-17 饱和水含量）。*/
  calculateSaturationWaterContent: (
    req: SaturationWaterContentRequest,
  ): Promise<SaturationWaterContentResponse> =>
    api
      .post<SaturationWaterContentResponse>(
        '/psychro/saturation-water-content/calculate',
        req,
      )
      .then((r) => r.data),
};
