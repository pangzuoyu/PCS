/**
 * 设备台账 API 客户端（EQUIP_LIST · SPEC §7.13 · P10-C · T3）。
 *
 * ## 为什么它是**单独一个**模块（而不是塞进 `records.ts`）
 *
 * 设备台账是**独立实体**（`equipment_list` 表）：它不是「某次计算的结果」，
 * 而是**被各模块同步过来的设备主数据**（PUMP / VESSEL / HEAT / PSV / CV /
 * MANUAL 六个来源）⇒ ⇒ 与「结果记录域」不是一回事 ⇒ ⇒ 单独一个客户端。
 *
 * ⚠️ **形状以契约为准**：`EquipListListResponse` = `{items, total, limit, offset}`
 * （`src/types/api.d.ts` 生成）⇒ ⇒ 不手写副本。
 */
import { api } from './client';
import type { components } from '../types/api';

/** 设备台账的一行（契约 `EquipListResponse`）。 */
export type EquipListItem = components['schemas']['EquipListResponse'];

/** 设备台账列表响应（契约 `EquipListListResponse`）。 */
export type EquipListListResponse = components['schemas']['EquipListListResponse'];

/** 列表查询参数（**全部可选** —— 后端据此过滤）。 */
export interface EquipListParams {
  project_id?: string;
  workspace_id?: string;
  source_module?: string;
  sign_status?: string;
  equipment_status?: string;
  limit?: number;
  offset?: number;
}

export const equipListApi = {
  /** GET /api/v1/equipment-list（分页 + 6 维过滤）。 */
  list: (params: EquipListParams = {}): Promise<EquipListListResponse> =>
    api.get<EquipListListResponse>('/equipment-list', { params }).then((r) => r.data),

  /** GET /api/v1/equipment-list/{equipment_id}（单条）。 */
  get: (equipmentId: string): Promise<EquipListItem> =>
    api.get<EquipListItem>(`/equipment-list/${equipmentId}`).then((r) => r.data),
};
