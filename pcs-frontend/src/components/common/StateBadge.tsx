/**
 * StateBadge — 9 态工程状态徽章组件（P45-1-1 / Task 6）。
 *
 * 替换 v0.1 StatusTag.tsx；保持 props.status 字段名向后兼容。
 * 颜色/icon/label 与 SPEC §6.1 + tokens.css --state-* + meta API V1.1
 * 一致（开发期间 fallback 写死；meta API 拉取留 P5）。
 *
 * 关键能力：
 * - 颜色取 `var(--state-<kebab-status>)` + 背景 `var(--state-badge-bg-<STATUS>)`
 * - icon 占位字符（v0.1；v0.2 接 @ant-design/icons 按 meta.icon）
 * - 模块激活子集：SIM/PIPE/PUMP/PIPE_NET/FLASH = 4 态（DRAFT/IN_APPROVAL/
 *   CHECKED/CHECK_REJECTED）；CONFIG/DELIVERABLE = 9 态全集；非激活态半透明
 * - showStep + IN_APPROVAL 时显示 "Step N/3"
 */
import type { CSSProperties, ReactNode } from 'react';

import type { RecordSignStatus } from '../../types/records';

export type StateBadgeModule =
  | 'SIM' | 'PIPE' | 'PUMP' | 'PIPE_NET' | 'FLASH'
  | 'VESSEL' | 'SEP_EQUIP' | 'PSV' | 'HEAT'
  | 'CONFIG' | 'DELIVERABLE';

export type StateBadgeSize = 'sm' | 'md';

export interface StateBadgeProps {
  status: RecordSignStatus;
  module?: StateBadgeModule;
  size?: StateBadgeSize;
  showIcon?: boolean;
  showStep?: boolean;
  step?: number;
  /** v0.2 留口子（多级审批缩进）；v0.1 不渲染。 */
  depth?: number;
}

interface StatusMeta {
  token: string;       // 对应 tokens.css --state-<kebab>
  iconPlaceholder: string;  // v0.1 占位字符（v0.2 接 @ant-design/icons）
  label: string;
}

const STATUS_META: Record<RecordSignStatus, StatusMeta> = {
  DRAFT:            { token: 'state-draft',           iconPlaceholder: '✎', label: '草稿' },
  IN_APPROVAL:      { token: 'state-in-approval',     iconPlaceholder: '◷', label: '审批中' },
  CHECKED:          { token: 'state-checked',         iconPlaceholder: '✓', label: '已核验' },
  CHECK_REJECTED:   { token: 'state-check-rejected',  iconPlaceholder: '✕', label: '核验驳回' },
  STALE:            { token: 'state-stale',           iconPlaceholder: '⚠', label: '失效' },
  CHANGE_PENDING:   { token: 'state-change-pending',  iconPlaceholder: '↻', label: '变更待批' },
  CHANGED:          { token: 'state-changed',         iconPlaceholder: '⇄', label: '已变更' },
  REVERSAL_PENDING: { token: 'state-reversal-pending', iconPlaceholder: '⟲', label: '撤销待批' },
  OBSOLETE:         { token: 'state-obsolete',        iconPlaceholder: '⊘', label: '已弃用' },
};

const FOUR_STATE_SUBSET: ReadonlySet<RecordSignStatus> = new Set([
  'DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED',
]);

const MODULE_ACTIVATED: Record<StateBadgeModule, ReadonlySet<RecordSignStatus>> = {
  SIM: FOUR_STATE_SUBSET,
  PIPE: FOUR_STATE_SUBSET,
  PUMP: FOUR_STATE_SUBSET,
  PIPE_NET: FOUR_STATE_SUBSET,
  FLASH: FOUR_STATE_SUBSET,
  VESSEL: FOUR_STATE_SUBSET,
  SEP_EQUIP: FOUR_STATE_SUBSET,
  PSV: FOUR_STATE_SUBSET,
  HEAT: FOUR_STATE_SUBSET,
  CONFIG: new Set<RecordSignStatus>([
    'DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED', 'STALE',
    'CHANGE_PENDING', 'CHANGED', 'REVERSAL_PENDING', 'OBSOLETE',
  ]),
  DELIVERABLE: new Set<RecordSignStatus>([
    'DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED', 'STALE',
    'CHANGE_PENDING', 'CHANGED', 'REVERSAL_PENDING', 'OBSOLETE',
  ]),
};

const TOTAL_STEPS_DEFAULT = 3;

/** 把 DRAFT / IN_APPROVAL 等转成 tokens.css 里的 kebab-case。 */
function toKebab(status: string | null | undefined): string {
  if (!status) return 'unknown';
  return status.toLowerCase().replace(/_/g, '-');
}

export function StateBadge({
  status,
  module = 'CONFIG',
  size = 'md',
  showIcon = false,
  showStep = false,
  step,
  depth,
}: StateBadgeProps): JSX.Element {
  // depth 为 v0.2 缩进口子；v0.1 不消费但显式标记避免 unused warning
  void depth;

  const meta = STATUS_META[status as RecordSignStatus] ?? STATUS_META.DRAFT;
  const safeStatus = (status ?? 'DRAFT') as RecordSignStatus;
  const isActive = MODULE_ACTIVATED[module].has(safeStatus);
  const kebab = toKebab(status);

  const style: CSSProperties = {
    color: `var(--${meta.token})`,
    background: `var(--state-badge-bg-${safeStatus}, transparent)`,
    border: `1px solid var(--${meta.token})`,
    fontSize: size === 'sm' ? 11 : 12,
    lineHeight: size === 'sm' ? '18px' : '20px',
    padding: size === 'sm' ? '0 6px' : '2px 8px',
    borderRadius: 4,
    display: 'inline-flex',
    alignItems: 'center',
    gap: 4,
    opacity: isActive ? 1 : 0.4,
    fontFamily: 'inherit',
  };

  let iconNode: ReactNode = null;
  if (showIcon) {
    iconNode = (
      <span aria-hidden="true" data-testid="state-badge-icon">
        {meta.iconPlaceholder}
      </span>
    );
  }

  let stepSuffix = '';
  if (showStep && safeStatus === 'IN_APPROVAL') {
    const current = step ?? 1;
    stepSuffix = ` · Step ${current}/${TOTAL_STEPS_DEFAULT}`;
  }

  return (
    <span
      data-testid="state-badge"
      data-status={safeStatus}
      data-module={module}
      data-active={String(isActive)}
      data-kebab={kebab}
      style={style}
    >
      {iconNode}
      <span data-testid="state-badge-label">
        {meta.label}
        {stepSuffix}
      </span>
    </span>
  );
}

export default StateBadge;