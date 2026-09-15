/**
 * AssumedDataMarker — 假设数据标识（P45-1-5 / Task 10）。
 *
 * SPEC §6.11 + plan P45-1-5：
 * - 字段旁橙色三角 △（var(--state-change-pending)）
 * - Tooltip 三段拼接：reason / source / value（任一缺省跳过空行）
 * - 签署确认：签署弹窗顶部显示假设数据清单，必须勾选「已知悉并接受上述假设数据」
 *   （弹窗逻辑在签署流程，本组件只渲染单字段标识）
 *
 * assumed=false → null（不渲染占位）
 */
import { Tooltip } from 'antd';

export interface AssumedDataMarkerProps {
  assumed: boolean;
  reason?: string;
  source?: string;
  value?: string;
}

function buildTooltipText(reason?: string, source?: string, value?: string): string {
  const lines: string[] = [];
  if (reason) lines.push(reason);
  if (value) lines.push(`数值 = ${value}`);
  if (source) lines.push(`来源：${source}`);
  return lines.join('\n');
}

export function AssumedDataMarker({
  assumed,
  reason,
  source,
  value,
}: AssumedDataMarkerProps): JSX.Element | null {
  if (!assumed) return null;

  const tooltipText = buildTooltipText(reason, source, value);

  return (
    <Tooltip title={tooltipText} placement="top">
      <span
        data-testid="assumed-data-marker"
        data-reason={reason ?? ''}
        data-source={source ?? ''}
        data-value={value ?? ''}
        aria-label="假设数据"
        style={{
          display: 'inline-flex',
          alignItems: 'center',
          color: 'var(--state-change-pending)',
          cursor: 'help',
          marginLeft: 4,
          fontSize: 12,
        }}
      >
        △
      </span>
    </Tooltip>
  );
}

export default AssumedDataMarker;