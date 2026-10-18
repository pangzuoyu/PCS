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
 *   module?: SignModule
 *   version?: { hash: string; label?: string }
 *   actions: ReactNode
 *   extra?: ReactNode
 */
import type { ReactNode } from 'react';
import { Space, Typography } from 'antd';

import { HashBadge } from './HashBadge';
import { StateBadge, type SignModule } from './StateBadge';
import type { RecordSignStatus } from '../../types/records';

interface VersionSlot {
  hash: string;
  label?: string;
}

interface Props {
  title: string;
  status?: RecordSignStatus;
  /**
   * 标题栏是**签署**徽章位，所以只收签署模块。
   *
   * ⚠️ 刻意不是 `StateBadgeModule`（那含 `PIPE_CLASS`）：
   * `module="PIPE_CLASS"` + `status: RecordSignStatus` 是个非法组合，
   * 放宽后 `tsc` 就拦不住了（bug-180 的教训）。管子等级页
   * 在自己的表格列里用 StateBadge，不过 PageHeader。
   */
  module?: SignModule;
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