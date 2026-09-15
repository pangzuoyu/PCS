/**
 * NumericCell — 数值单元格统一渲染（P45-1-4 / Task 9）。
 *
 * SPEC §6.12：
 * - 默认 6 位有效数字；货币 2 位小数（precisionType='decimal'）
 * - 单位小一号（11px），次要色，不换行，间距 4px
 * - null → —
 * - assumed → 橙色三角 + 橙色文字
 * - stale   → 橙色文字
 * - conflict→ 红色文字
 * - 等宽字体默认 on（金融/工程表格对齐需求）
 *
 * Status → tokens.css：
 * - normal   → var(--text-primary)
 * - assumed  → var(--state-change-pending)
 * - stale    → var(--state-stale)
 * - conflict → var(--state-check-rejected)
 */
import type { CSSProperties } from 'react';

export type NumericCellStatus = 'normal' | 'assumed' | 'stale' | 'conflict';
export type NumericCellPrecisionType = 'significant' | 'decimal';
export type NumericCellAlign = 'left' | 'right' | 'center';

export interface NumericCellProps {
  value: number | null;
  unit?: string;
  precision?: number;
  precisionType?: NumericCellPrecisionType;
  align?: NumericCellAlign;
  status?: NumericCellStatus;
  monospace?: boolean;
}

const STATUS_COLOR: Record<NumericCellStatus, string> = {
  normal: 'var(--text-primary)',
  assumed: 'var(--state-change-pending)',
  stale: 'var(--state-stale)',
  conflict: 'var(--state-check-rejected)',
};

function formatNumber(value: number, precision: number, type: NumericCellPrecisionType): string {
  if (type === 'decimal') return value.toFixed(precision);
  return value.toPrecision(precision);
}

export function NumericCell({
  value,
  unit,
  precision = 6,
  precisionType = 'significant',
  align = 'right',
  status = 'normal',
  monospace = true,
}: NumericCellProps): JSX.Element {
  const display = value === null || value === undefined || Number.isNaN(value)
    ? '—'
    : formatNumber(value, precision, precisionType);

  const isAssumed = status === 'assumed';
  const valueColor = status === 'assumed' ? STATUS_COLOR.normal : STATUS_COLOR[status];
  const markerColor = STATUS_COLOR.assumed;

  const valueStyle: CSSProperties = {
    fontFamily: monospace ? 'var(--font-mono, ui-monospace, Menlo, Consolas, monospace)' : 'inherit',
    color: valueColor,
    textAlign: align,
  };

  const unitStyle: CSSProperties = {
    fontSize: 11,
    color: 'var(--text-tertiary, #5A6773)',
    marginLeft: 4,
    whiteSpace: 'nowrap',
    fontFamily: 'inherit',
  };

  return (
    <span
      data-testid="numeric-cell"
      data-status={status}
      data-precision-type={precisionType}
      data-align={align}
      data-monospace={String(monospace)}
      data-null={String(value === null || value === undefined || Number.isNaN(value))}
      style={{ display: 'inline-flex', alignItems: 'baseline' }}
    >
      {isAssumed && (
        <span
          data-testid="numeric-cell-marker"
          aria-label="assumed"
          style={{ marginRight: 4, color: markerColor }}
        >
          ⚠
        </span>
      )}
      <span data-testid="numeric-cell-value" style={valueStyle}>
        {display}
      </span>
      {unit && (
        <span data-testid="numeric-cell-unit" style={unitStyle}>
          {unit}
        </span>
      )}
    </span>
  );
}

export default NumericCell;