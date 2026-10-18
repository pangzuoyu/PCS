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
 * - **模块强调子集**：SIM/PIPE/PUMP/PIPE_NET/FLASH = 4 态（DRAFT/IN_APPROVAL/
 *   CHECKED/CHECK_REJECTED）满透明度，其余 5 态半透明；CONFIG/DELIVERABLE
 *   = 9 态全集；**这管的是「要不要突出显示」，不是「哪些状态合法」**（见下）
 * - showStep + IN_APPROVAL 时显示 "Step N/3"
 *
 * ## 强调 ≠ 词表（2026-10-19 的元教训，配套 bug-180）
 *
 * `MODULE_ACTIVATED` **只**决定 `opacity`，从不做有效性检查 ——
 * 所以物流记录进 `STALE`（后端 `StreamSignStatus` 九态之一，
 * `stream_service.py:258` 的锁定检查逐个点名了它）是**合法**的，
 * 只是渲染成半透明。
 *
 * ⚠️ 因此**不能**把它提升成编译期词表：那会把一个「渲染强调」
 * 误升成「合法性约束」，于是合法的 `STALE` 被 `tsc` 拒绝 ——
 * 比现状更糟的回归。
 *
 * 真正的**词表**只有一个地方：`StatusVocabularies`，由 props 的
 * 判别联合强制。当前只有 `PIPE_CLASS` 与签署词表不同 ——
 * 管子等级走自己的发布态（DRAFT/ACTIVE/OBSOLETE），不走签署。
 *
 * ## 未知状态必须**显形**，不得静默映射
 *
 * 旧实现 `STATUS_META[status] ?? STATUS_META.DRAFT`：
 * 一个**已生效**的管子等级落进去会显示「草稿」。用户不会报 bug
 * （他不知道本该显示什么），他会基于错误信息做决策 ——
 * 「这个等级还没生效，不能用于设计」。
 * **数据语义被静默改写**，与 `definitionBody.ts` 给缺 `source`
 * 的条件伪造 `'EQUIP_LIST'` 同族。
 *
 * 判别联合拦得住**字面量**（开发者写错 module/status 组合），
 * 拦不住**后端返回的裸 string**（契约 `status` 没写 Literal）——
 * 运行时这一层由下面的 `UNKNOWN_*` 分支兜住。
 */
import type { CSSProperties, ReactNode } from 'react';

import type { RecordSignStatus } from '../../types/records';

export type StateBadgeSize = 'sm' | 'md';

/** 管子等级的生命周期：走发布态，**不走签署**（bug-180）。 */
export const PIPE_CLASS_STATUSES = ['DRAFT', 'ACTIVE', 'OBSOLETE'] as const;
export type PipeClassStatus = typeof PIPE_CLASS_STATUSES[number];

export type SignModule =
  | 'SIM' | 'PIPE' | 'PUMP' | 'PIPE_NET' | 'FLASH'
  | 'VESSEL' | 'SEP_EQUIP' | 'PSV' | 'HEAT'
  | 'CONFIG' | 'DELIVERABLE';

export type StateBadgeModule = SignModule | 'PIPE_CLASS';

/**
 * props 用**判别联合**而不是「module + 一个宽 status」。
 *
 * 宽 status（`RecordSignStatus` 一把梭）的后果：
 * `module="PIPE_CLASS" status="CHECKED"` 与 `module="PIPE" status="ACTIVE"`
 * 都能过 `tsc`，类型系统对「module/status 组合」零保护。
 * 判别联合让这两种组合**编译期就报错**。
 */
type StateBadgeBase = {
  size?: StateBadgeSize;
  showIcon?: boolean;
  showStep?: boolean;
  step?: number;
  /** v0.2 留口子（多级审批缩进）；v0.1 不渲染。 */
  depth?: number;
};

export type StateBadgeProps = StateBadgeBase & (
  | { module: 'PIPE_CLASS'; status: PipeClassStatus }
  /** 省略 `module` 时按 CONFIG（9 态全集）处理，见组件内 defaultProps。 */
  | { module?: SignModule; status: RecordSignStatus }
);

interface StatusMeta {
  token: string;       // 对应 tokens.css --state-<kebab>
  iconPlaceholder: string;  // v0.1 占位字符（v0.2 接 @ant-design/icons）
  label: string;
}

type AnyKnownStatus = RecordSignStatus | PipeClassStatus;

const STATUS_META: Record<AnyKnownStatus, StatusMeta> = {
  DRAFT:            { token: 'state-draft',           iconPlaceholder: '✎', label: '草稿' },
  IN_APPROVAL:      { token: 'state-in-approval',     iconPlaceholder: '◷', label: '审批中' },
  CHECKED:          { token: 'state-checked',         iconPlaceholder: '✓', label: '已核验' },
  CHECK_REJECTED:   { token: 'state-check-rejected',  iconPlaceholder: '✕', label: '核验驳回' },
  STALE:            { token: 'state-stale',           iconPlaceholder: '⚠', label: '失效' },
  CHANGE_PENDING:   { token: 'state-change-pending',  iconPlaceholder: '↻', label: '变更待批' },
  CHANGED:          { token: 'state-changed',         iconPlaceholder: '⇄', label: '已变更' },
  REVERSAL_PENDING: { token: 'state-reversal-pending', iconPlaceholder: '⟲', label: '撤销待批' },
  OBSOLETE:         { token: 'state-obsolete',        iconPlaceholder: '⊘', label: '已弃用' },
  // 管子等级的 ACTIVE（bug-180）。复用已核验的绿色 token ——
  // 语义不同（「已发布可被项目引用」≠「计算已校核」）但**观感**相同：
  // 都是「这一项现在可用」。文案必须分开：写「已核验」是语义撒谎。
  ACTIVE:           { token: 'state-checked',         iconPlaceholder: '✓', label: '已生效' },
};

const FOUR_STATE_SUBSET: ReadonlySet<RecordSignStatus> = new Set([
  'DRAFT', 'IN_APPROVAL', 'CHECKED', 'CHECK_REJECTED',
]);

/**
 * **强调**表：只决定 opacity（1 vs 0.4），**不做有效性检查**。
 * 「窄」在这里是视觉选择，不是合法性约束 —— 见文件头。
 */
const MODULE_ACTIVATED: Record<StateBadgeModule, ReadonlySet<AnyKnownStatus>> = {
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
  // 管子等级三态都算「当前有效」，没有半透明态。
  PIPE_CLASS: new Set<PipeClassStatus>([...PIPE_CLASS_STATUSES]),
};

const TOTAL_STEPS_DEFAULT = 3;

/** 把 DRAFT / IN_APPROVAL 等转成 tokens.css 里的 kebab-case。 */
function toKebab(status: string | null | undefined): string {
  if (!status) return 'unknown';
  return status.toLowerCase().replace(/_/g, '-');
}

/** 未知状态的呈现：一眼看得出「系统不认识」，而不是假装是草稿。 */
const UNKNOWN_TOKEN = 'state-stale';

/**
 * 未知状态分支（bug-180）。
 *
 * 开发期**抛错**而不是渲染：让问题在第一次出现时就炸，
 * 而不是等用户拿错误信息做决策。
 * 生产期渲染显式的「未知状态: X」—— 至少用户知道是系统不认识，
 * 而不是数据本身处于某个状态。
 *
 * ⚠️ 绝不回落到 `STATUS_META.DRAFT`。那会把 ACTIVE 说成草稿
 * （语义改写，且用户无从察觉）。
 */
function unknownBadge(status: string, size: StateBadgeSize): JSX.Element {
  if (import.meta.env.DEV) {
    throw new Error(
      `StateBadge: 未知状态 ${JSON.stringify(status)}`
      + `（已知：${Object.keys(STATUS_META).join(', ')}）`,
    );
  }
  const style: CSSProperties = {
    color: `var(--${UNKNOWN_TOKEN})`,
    background: 'transparent',
    border: `1px dashed var(--${UNKNOWN_TOKEN})`,
    fontSize: size === 'sm' ? 11 : 12,
    lineHeight: size === 'sm' ? '18px' : '20px',
    padding: size === 'sm' ? '0 6px' : '2px 8px',
    borderRadius: 4,
    display: 'inline-flex',
    alignItems: 'center',
    fontFamily: 'inherit',
  };
  return (
    <span
      data-testid="state-badge"
      data-status={status}
      data-known="false"
      data-kebab={toKebab(status)}
      style={style}
    >
      <span data-testid="state-badge-label">未知状态: {status}</span>
    </span>
  );
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

  // ⚠️ **先查未知分支，再谈样式**。旧的 `?? STATUS_META.DRAFT` 把
  // 不认识的状态说成草稿 —— 已 ACTIVE 的管子等级会显示「草稿」。
  const meta = STATUS_META[status as AnyKnownStatus];
  if (!meta) return unknownBadge(String(status), size);

  const safeStatus = status as AnyKnownStatus;
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
      data-known="true"
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