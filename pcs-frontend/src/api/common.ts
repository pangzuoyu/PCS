/**COMMON 计算 API 客户端（P6-5 前端补课 / 3 计算页）。

按 UI SPEC §7.8 + 后端 OpenAPI（app/api/v1/common.py）：
- POST /api/v1/common/heating-value/calculate
  （HeatingValueCalcRequest → HeatingValueCalcResponse；C-06 气体热值）

错误通过 PcsError envelope 抛出（api client 统一处理 401）：
- HEATING_VALUE_INPUT_ERROR 422（空 compositions / mol_frac 非法）
- COMPOUND_NOT_FOUND 404（CAS 未命中 compound_heating_values 且
  Mendeleev fallback 不适用）
*/
import { api } from './client';
import type {
  HeatingValueCalcRequest,
  HeatingValueCalcResponse,
} from '../types/common';

export const commonCalcApi = {
  /**POST /api/v1/common/heating-value/calculate（C-06 气体热值）。*/
  calculateHeatingValue: (
    req: HeatingValueCalcRequest,
  ): Promise<HeatingValueCalcResponse> =>
    api
      .post<HeatingValueCalcResponse>('/common/heating-value/calculate', req)
      .then((r) => r.data),
};
