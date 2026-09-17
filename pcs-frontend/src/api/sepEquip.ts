/**SEP_EQUIP 分离设备计算 API 客户端（P5 frontend 全栈收口 / OPEN-4-2）。

按 SPEC §7.11.4 + 后端 OpenAPI（app/api/v1/sep_equip.py）：
- POST /api/v1/sep-equip/calculate（CalculateRequest → CalculateResponse）

5 设备类型共享 1 端点，params 按 device_type 分派（CycloneParams / MistEliminatorParams
/ GravitySeparatorParams + VANE/FIBER 沿用 Gravity）。

错误通过 PcsError envelope 抛出：
- STREAM_NOT_CHECKED 403 — 源流未签出（仅 CHECKED 可算）
- SEP_EQUIP_INPUT_ERROR 422 / SEP_EQUIP_NOT_FOUND 404 等

前端 message.error 显示 message 字段；StreamListItem 流列表由 streamApi 提供。
*/
import { api } from './client';
import type {
  CycloneParams,
  GravitySeparatorParams,
  MistEliminatorParams,
  SepEquipDeviceType,
} from '../types/sepEquip';

/**SepEquipCalculateRequest 联合：source_stream_id + device_type + params。
 * params 形态由 device_type 决定（仿 VesselCalculateRequest 的双层结构）。*/
export interface SepEquipCalculateRequest {
  source_stream_id: string;
  device_type: SepEquipDeviceType;
  params: CycloneParams | MistEliminatorParams | GravitySeparatorParams;
}

/**后端 CalculateResponse 1:1 对齐。*/
export interface SepEquipCalculateResponse {
  calc_id: string;
  calc_type: string;
  record_hash: string;
  stream_id: string;
  lineage_ids: string[];
  result: Record<string, unknown>;
  outlet_stream_id: string;
  outlet_stream_name: string;
}

export const sepEquipApi = {
  /**POST /api/v1/sep-equip/calculate。*/
  calculate: (req: SepEquipCalculateRequest): Promise<SepEquipCalculateResponse> =>
    api.post<SepEquipCalculateResponse>('/sep-equip/calculate', req).then((r) => r.data),
};