/**
 * Audit Query API 客户端 (F-P2-009 Sprint 3 / Issue 7).
 *
 * 按后端 OpenAPI:
 * - GET /api/v1/audit-logs              (SYSTEM_ADMIN only)
 * - GET /api/v1/equipment-deletion-audit (DESIGNER+ + project_id filter)
 * - GET /api/v1/config-audit            (DESIGNER+ 公司级全局)
 *
 * Source-verify (2026-10-03):
 * - audit_logs.resource_type 实际值: "config_energy_conversion_factors"
 *   (与 ConfigEnergyConversionFactor.__tablename__ 一致)
 * - audit_logs.resource_id 类型 String(100), ConfigEnergyConversionFactor.id
 *   BIGINT, 需 str() 转换 (前端发 asset_id int, 后端转 str)
 */
import { api } from './client';

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