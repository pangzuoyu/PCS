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
  AllowableStress,
  ComponentProperty,
  HeatingValueCalcRequest,
  HeatingValueCalcResponse,
  ToxicityClass,
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

/**
 * COMMON 的**查询类**端点（P10-C · T1 · TODO-160）。
 *
 * ## ⚠️ 为什么这三个查询**必须带参数**（首屏 422 的根因）
 *
 * 契约（`pcs-backend/docs/openapi.json`）里三个端点的必填参数是：
 *
 * | 端点 | 必填参数 | 空查询的后果 |
 * |---|---|---|
 * | `GET /common/materials/search` | `keyword`（min_length=1） | **422** |
 * | `GET /common/allowable-stress` | `material` + `temp_c` | **422** |
 * | `GET /common/safety` | `cas` | **422** |
 *
 * ⇒ ⇒ 前端**首屏不能发空查询** ⇒ 页面改成**查询驱动**：用户填了条件才发请求。
 *
 * ## ⚠️ 返回**形状**也不对称（别按数组写）
 *
 * - `materials/search` ⇒ **数组**（但后端 `search_chemical` 最多命中 **1** 条）
 * - `allowable-stress` ⇒ **单个对象**（插值结果，不是表）
 * - `safety` ⇒ **单个对象**（`_SAFETY_DATA` 的一条）
 *
 * ⇒ ⇒ 前端页面按「命中若干条」渲染（`[obj]` 包装成 1 行的表 / 1 张卡片）。
 */
export const commonQueryApi = {
  /** GET /api/v1/common/materials/search（`keyword` 必填）。 */
  searchMaterials: (keyword: string): Promise<ComponentProperty[]> =>
    api
      .get<ComponentProperty[]>('/common/materials/search', {
        params: { keyword },
        timeout: 15_000,
      })
      .then((r) => r.data),

  /** GET /api/v1/common/allowable-stress（`material` + `temp_c` 必填）。 */
  allowableStress: (
    material: string,
    tempC: number,
  ): Promise<AllowableStress> =>
    api
      .get<AllowableStress>('/common/allowable-stress', {
        params: { material, temp_c: tempC },
        timeout: 15_000,
      })
      .then((r) => r.data),

  /** GET /api/v1/common/safety（`cas` 必填）。 */
  safety: (cas: string): Promise<ToxicityClass> =>
    api
      .get<ToxicityClass>('/common/safety', {
        params: { cas },
        timeout: 15_000,
      })
      .then((r) => r.data),
};
