/**
 * Audit API 客户端测试 (F-P2-009 Sprint 3 / Issue 7).
 *
 * 覆盖:
 * - auditApi.listAuditLogs 路径 + 参数透传
 * - auditApi.listEquipmentDeletionAudit 路径
 * - auditApi.listConfigAudit 路径 + asset_id int 参数
 */
import { describe, it, expect, vi } from 'vitest';

vi.mock('../../src/api/client', async () => {
  const actual = await vi.importActual<typeof import('../../src/api/client')>(
    '../../src/api/client',
  );
  return {
    ...actual,
    api: {
      post: vi.fn().mockResolvedValue({ data: { stub: true } }),
      get: vi.fn().mockResolvedValue({ data: { stub: true } }),
    },
  };
});

import { api } from '../../src/api/client';
import { auditApi } from '../../src/api/audit';

describe('auditApi.listAuditLogs', () => {
  it('calls GET /audit-logs with params', () => {
    void auditApi.listAuditLogs({ resource_type: 'config_asset', limit: 10 });
    expect(api.get).toHaveBeenCalledWith('/audit-logs', {
      params: { resource_type: 'config_asset', limit: 10 },
    });
  });
});

describe('auditApi.listEquipmentDeletionAudit', () => {
  it('calls GET /equipment-deletion-audit with project_id', () => {
    void auditApi.listEquipmentDeletionAudit({
      project_id: 'p-123', limit: 50,
    });
    expect(api.get).toHaveBeenCalledWith('/equipment-deletion-audit', {
      params: { project_id: 'p-123', limit: 50 },
    });
  });
});

describe('auditApi.listConfigAudit', () => {
  it('calls GET /config-audit with asset_id', () => {
    void auditApi.listConfigAudit({ asset_id: 42 });
    expect(api.get).toHaveBeenCalledWith('/config-audit', {
      params: { asset_id: 42 },
    });
  });

  it('calls GET /config-audit without params', () => {
    void auditApi.listConfigAudit({});
    expect(api.get).toHaveBeenCalledWith('/config-audit', { params: {} });
  });
});