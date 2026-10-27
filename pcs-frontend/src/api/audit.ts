/**
 * Audit Query API 客户端 (F-P2-009 Sprint 3 / Issue 7).
 *
 * 按后端 OpenAPI:
 * - GET /api/v1/audit-logs              (SYSTEM_ADMIN only)
 * - GET /api/v1/equipment-deletion-audit (DESIGNER+ + project_id filter)
 * - GET /api/v1/config-audit            (DESIGNER+ 公司级全局)
 * - GET /api/v1/records/{module}/{id}/edits (P9B-2 · TODO-066 · 按项目守卫)
 *
 * Source-verify (2026-10-03):
 * - audit_logs.resource_type 实际值: "config_energy_conversion_factors"
 *   (与 ConfigEnergyConversionFactor.__tablename__ 一致)
 * - audit_logs.resource_id 类型 String(100), ConfigEnergyConversionFactor.id
 *   BIGINT, 需 str() 转换 (前端发 asset_id int, 后端转 str)
 */
import { api } from './client';
import type { components } from '../types/api';

export interface ListAuditLogsParams {
  resource_type?: string;
  resource_id?: string;
  user_id?: string;
  action?: string;
  occurred_after?: string;
  occurred_before?: string;
  limit?: number;
  offset?: number;
}

export interface ListEquipmentDeletionAuditParams {
  project_id?: string;
  workspace_id?: string;
  equipment_id?: string;
  deleted_by?: string;
  occurred_after?: string;
  occurred_before?: string;
  limit?: number;
  offset?: number;
}

export interface ListConfigAuditParams {
  asset_id?: number;
  occurred_after?: string;
  occurred_before?: string;
  limit?: number;
  offset?: number;
}

export interface AuditLogItem {
  audit_id: string;
  user_id?: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  detail_json?: Record<string, unknown>;
  occurred_at: string;
}

export interface AuditLogListResponse {
  items: AuditLogItem[];
  total: number;
  limit: number;
  offset: number;
}

export interface EquipmentDeletionAuditItem {
  audit_id: string;
  equipment_id: string;
  project_id: string;
  workspace_id: string;
  equipment_tag: string;
  deleted_by: string;
  orphan_records: Record<string, unknown>;
  occurred_at: string;
  reason?: string;
}

export interface EquipmentDeletionAuditListResponse {
  items: EquipmentDeletionAuditItem[];
  total: number;
  limit: number;
  offset: number;
}

export const auditApi = {
  listAuditLogs(params: ListAuditLogsParams): Promise<AuditLogListResponse> {
    return api.get('/audit-logs', { params }).then((r) => r.data);
  },
  listEquipmentDeletionAudit(
    params: ListEquipmentDeletionAuditParams,
  ): Promise<EquipmentDeletionAuditListResponse> {
    return api.get('/equipment-deletion-audit', { params }).then((r) => r.data);
  },
  listConfigAudit(
    params: ListConfigAuditParams,
  ): Promise<AuditLogListResponse> {
    return api.get('/config-audit', { params }).then((r) => r.data);
  },
};

/**
 * 编辑审计（SPEC §6.21 P9A-LCK-006「查看差异」的来源）。
 *
 * ⚠️ **数据源换了**（P9B-2 · R-14）：原先打 `/audit-logs`（**限 SYSTEM_ADMIN**）
 * ⇒ 普通 DESIGNER 拿到 409 弹窗却**点不开差异** ⇒ 现打**按项目守卫**的
 * `GET /records/{module}/{record_id}/edits`（TODO-066）⇒ **普通用户点得开**。
 *
 * ⚠️ `changed_fields`（**字段名列表**，不是值）在**顶层**（不是 `detail_json` 里）——
 * 新端点已经把 `detail_json` 摊平了。
 *
 * ⚠️ **此处是审计类客户端的归一处** ⇒ 不要再出现第三份审计入口。
 */
export type RecordEditsResponse = components['schemas']['RecordEditsResponse'];
export type RecordEditItem = components['schemas']['RecordEditItem'];

export const recordEditsApi = {
  list(
    module: string,
    recordId: string,
    params?: { limit?: number; offset?: number },
  ): Promise<RecordEditsResponse> {
    return api
      .get<RecordEditsResponse>(`/records/${module}/${recordId}/edits`, { params })
      .then((r) => r.data);
  },
};