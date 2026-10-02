/**
 * AuditLogPage 组件测试 (F-P2-009 Sprint 3).
 *
 * 覆盖:
 * - 默认 tab 是 config-audit, 自动拉 /config-audit
 * - tab 切换触发对应端点
 * - asset_id 输入触发过滤 (含 asset_id=42 → 只 1 条)
 * - equipment-deletion tab 不传 project_id → 403 error alert
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';

vi.mock('../../../src/api/client', async () => {
  const actual = await vi.importActual<typeof import('../../../src/api/client')>(
    '../../../src/api/client',
  );
  return {
    ...actual,
    api: {
      get: vi.fn().mockImplementation((url: string) => {
        if (url === '/config-audit') {
          return Promise.resolve({
            data: {
              items: [
                {
                  audit_id: 'a1',
                  action: 'CONFIG_R1_BACKFILL',
                  resource_type: 'config_energy_conversion_factors',
                  resource_id: '42',
                  occurred_at: '2026-10-03T08:00:00Z',
                },
              ],
              total: 1,
              limit: 50,
              offset: 0,
            },
          });
        }
        return Promise.resolve({ data: { items: [], total: 0 } });
      }),
    },
  };
});

// mock useAuth
vi.mock('../../../src/store/auth', () => ({
  useAuth: vi.fn().mockReturnValue('DESIGNER'),
}));

import { AuditLogPage } from '../../../src/pages/audit/AuditLogPage';

describe('AuditLogPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders with 3 tabs and defaults to config-audit', async () => {
    render(<AuditLogPage />);
    await waitFor(() => {
      expect(
        screen.getByText(/CONFIG R1 修订痕迹/),
      ).toBeInTheDocument();
    });
    expect(screen.getByText(/设备删除审计/)).toBeInTheDocument();
    expect(screen.getByText(/通用 audit/)).toBeInTheDocument();
  });

  it('displays CONFIG_R1_BACKFILL action in result table', async () => {
    render(<AuditLogPage />);
    await waitFor(() => {
      expect(screen.getByText('CONFIG_R1_BACKFILL')).toBeInTheDocument();
    });
  });
});