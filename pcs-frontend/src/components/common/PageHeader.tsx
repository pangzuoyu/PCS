/**
 * PageHeader — 统一页面头部（P45-3-0 / Task 27）。
 *
 * SPEC §6.1 + plan P45-3-0：
 * - 统一 P3/P4 模块详情页头部
 * - slot：title / status 徽章 / version hash / actions / extra（步骤条等）
 *
 * Props：
 *   title: string
 *   status?: RecordSignStatus
 *   module?: StateBadgeModule
 *   version?: { hash: string; label?: string }
 *   actions: ReactNode
 *   extra?: ReactNode
 */
import type { ReactNode } from 'react';
import { Space, Typography } from 'antd';

import { HashBadge } from './HashBadge';
import { StateBadge, type StateBadgeModule } from './StateBadge';
import type { RecordSignStatus } from '../../types/records';

interface VersionSlot {
  hash: string;
  label?: string;
}

interface Props {
  title: string;
  status?: RecordSignStatus;
  module?: StateBadgeModule;
  version?: VersionSlot;
  actions: ReactNode;
  extra?: ReactNode;
}

export function PageHeader({
  title,
  status,
  module = 'CONFIG',
  version,
  actions,
  extra,
}: Props): JSX.Element {
  return (
    <div
      data-testid="page-header"
      style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'space-between',
        padding: '8px 0 16px',
        borderBottom: '1px solid var(--color-border, #E5E7EB)',
        marginBottom: 16,
      }}
    >
      <Space size={12} align="center">
        <Typography.Title level={3} style={{ margin: 0 }} data-testid="page-header-title">
          {title}
        </Typography.Title>
        {status && (
          <span
            data-testid="page-header-status"
            data-status={status}
            data-module={module}
            style={{ display: 'inline-flex' }}
          >
            <StateBadge status={status} module={module} />
          </span>
        )}
        {version && (
          <span data-testid="page-header-version" style={{ display: 'inline-flex' }}>
            <HashBadge hash={version.hash} label={version.label} copyable={false} />
          </span>
        )}
      </Space>

      <Space size={12} align="center">
        {extra}
        <Space size={4} data-testid="page-header-actions">
          {actions}
        </Space>
      </Space>
    </div>
  );
}

export default PageHeader;