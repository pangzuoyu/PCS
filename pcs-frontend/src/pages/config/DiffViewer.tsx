/**
 * DiffViewer — 通用版本对比组件（P45-2-8 / Task 26）。
 *
 * SPEC §6.17：
 * - 并排左右视图（prev vs curr）
 * - 字段级 diff（JSON：changed/added/removed/unchanged）
 * - 字符串值变化时字符级 diff（行内红绿）
 * - prev/curr 标签 + 时间戳
 *
 * Props（SPEC 锁定）：
 *   prev: DiffVersion
 *   curr: DiffVersion
 *   fieldOrder?: string[]   // 字段显示顺序（默认按 key 升序）
 */
import { useMemo } from 'react';
import { Col, Row, Space, Tag, Typography } from 'antd';

/** 一个版本（§6.17）。 */
export interface DiffVersion {
  label: string;
  timestamp: string;
  /** 任意 JSON-serializable 结构（字段值若是字符串 → 字符级 diff）。 */
  data: Record<string, unknown>;
}

interface Props {
  prev: DiffVersion;
  curr: DiffVersion;
  fieldOrder?: string[];
}

type RowStatus = 'changed' | 'added' | 'removed' | 'unchanged';

interface FieldRow {
  key: string;
  status: RowStatus;
  prevValue: unknown;
  currValue: unknown;
}

const STATUS_TAG: Record<RowStatus, { color: string; label: string }> = {
  changed: { color: 'orange', label: '变更' },
  added: { color: 'green', label: '新增' },
  removed: { color: 'red', label: '删除' },
  unchanged: { color: 'default', label: '未变' },
};

function buildRows(prev: DiffVersion['data'], curr: DiffVersion['data'], order?: string[]): FieldRow[] {
  const keys = order ?? Array.from(new Set([...Object.keys(prev), ...Object.keys(curr)])).sort();
  return keys.map((k) => {
    const hasPrev = k in prev;
    const hasCurr = k in curr;
    if (hasPrev && !hasCurr) return { key: k, status: 'removed' as const, prevValue: prev[k], currValue: undefined };
    if (!hasPrev && hasCurr) return { key: k, status: 'added' as const, prevValue: undefined, currValue: curr[k] };
    if (JSON.stringify(prev[k]) !== JSON.stringify(curr[k])) {
      return { key: k, status: 'changed' as const, prevValue: prev[k], currValue: curr[k] };
    }
    return { key: k, status: 'unchanged' as const, prevValue: prev[k], currValue: curr[k] };
  });
}

/** 极简字符级 LCS diff（只对比字符串值变化时使用）。 */
function charDiff(prev: string, curr: string): Array<{ type: 'same' | 'removed' | 'added'; text: string }> {
  const a = prev;
  const b = curr;
  const m = a.length;
  const n = b.length;
  const dp: number[][] = Array.from({ length: m + 1 }, () => new Array(n + 1).fill(0));
  for (let i = m - 1; i >= 0; i--) {
    for (let j = n - 1; j >= 0; j--) {
      dp[i][j] = a[i] === b[j] ? dp[i + 1][j + 1] + 1 : Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }
  const ops: Array<{ type: 'same' | 'removed' | 'added'; text: string }> = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      ops.push({ type: 'same', text: a[i] });
      i++;
      j++;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push({ type: 'removed', text: a[i] });
      i++;
    } else {
      ops.push({ type: 'added', text: b[j] });
      j++;
    }
  }
  while (i < m) ops.push({ type: 'removed', text: a[i++] });
  while (j < n) ops.push({ type: 'added', text: b[j++] });

  // 合并相邻同 type
  const merged: typeof ops = [];
  for (const op of ops) {
    const last = merged[merged.length - 1];
    if (last && last.type === op.type) last.text += op.text;
    else merged.push({ ...op });
  }
  return merged;
}

function ValueDisplay({ value, status }: { value: unknown; status: RowStatus }): JSX.Element {
  if (status === 'removed') {
    return <Typography.Text type="secondary">（已删除）</Typography.Text>;
  }
  if (value === undefined || value === null) {
    return <Typography.Text type="secondary">—</Typography.Text>;
  }
  if (typeof value === 'string') {
    return (
      <Typography.Text style={{ fontFamily: 'var(--font-mono, monospace)' }}>
        {value}
      </Typography.Text>
    );
  }
  return (
    <Typography.Text style={{ fontFamily: 'var(--font-mono, monospace)' }}>
      {JSON.stringify(value)}
    </Typography.Text>
  );
}

function StringCharDiff({ prev, curr }: { prev: string; curr: string }): JSX.Element {
  const ops = charDiff(prev, curr);
  return (
    <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>
      {ops.map((op, i) => {
        if (op.type === 'same') return <span key={i}>{op.text}</span>;
        if (op.type === 'removed') {
          return (
            <span
              key={i}
              data-testid="diff-char-removed"
              style={{
                background: 'var(--surface-bg-error, #FFE3E3)',
                color: 'var(--state-check-rejected, #C62828)',
                textDecoration: 'line-through',
                padding: '0 2px',
              }}
            >
              {op.text}
            </span>
          );
        }
        return (
          <span
            key={i}
            data-testid="diff-char-added"
            style={{
              background: 'var(--surface-bg-success, #E6F4EA)',
              color: 'var(--state-checked, #2E7D32)',
              padding: '0 2px',
            }}
          >
            {op.text}
          </span>
        );
      })}
    </span>
  );
}

export function DiffViewer({ prev, curr, fieldOrder }: Props): JSX.Element {
  const rows = useMemo(() => buildRows(prev.data, curr.data, fieldOrder), [prev, curr, fieldOrder]);

  function renderValue(value: unknown, status: RowStatus, compareValue?: unknown): JSX.Element {
    if (status === 'changed' && typeof value === 'string' && typeof compareValue === 'string') {
      return <StringCharDiff prev={value} curr={compareValue} />;
    }
    return <ValueDisplay value={value} status={status} />;
  }

  return (
    <div data-testid="diff-viewer">
      <Typography.Title level={4}>版本对比</Typography.Title>
      <Row gutter={16}>
        <Col span={12} data-testid="diff-left">
          <Space style={{ marginBottom: 8 }}>
            <Tag color="blue">{prev.label}</Tag>
            <Typography.Text type="secondary">{prev.timestamp}</Typography.Text>
          </Space>
          <div
            style={{
              border: '1px solid var(--color-border, #E5E7EB)',
              borderRadius: 4,
              padding: 8,
              fontFamily: 'var(--font-mono, monospace)',
              background: 'var(--surface-bg-info, #F0F4F8)',
              minHeight: 200,
            }}
          >
            <pre style={{ margin: 0 }}>{JSON.stringify(prev.data, null, 2)}</pre>
          </div>
        </Col>

        <Col span={12} data-testid="diff-right">
          <Space style={{ marginBottom: 8 }}>
            <Tag color="green">{curr.label}</Tag>
            <Typography.Text type="secondary">{curr.timestamp}</Typography.Text>
          </Space>
          <div
            style={{
              border: '1px solid var(--color-border, #E5E7EB)',
              borderRadius: 4,
              padding: 8,
              fontFamily: 'var(--font-mono, monospace)',
              background: 'var(--surface-bg-info, #F0F4F8)',
              minHeight: 200,
            }}
          >
            <pre style={{ margin: 0 }}>{JSON.stringify(curr.data, null, 2)}</pre>
          </div>
        </Col>
      </Row>

      <div style={{ marginTop: 16 }}>
        <Typography.Title level={5}>字段差异</Typography.Title>
        <Space direction="vertical" style={{ width: '100%' }} size={4}>
          {rows.map((row) => (
            <div
              key={row.key}
              data-testid="diff-row"
              data-status={row.status}
              data-field={row.key}
              style={{
                borderLeft: `3px solid var(--state-${row.status === 'changed' ? 'in-approval' : row.status === 'added' ? 'checked' : row.status === 'removed' ? 'check-rejected' : 'draft'}, #999)`,
                background:
 row.status === 'changed'
                  ? 'var(--surface-bg-warning, #FFF7E6)'
                  : row.status === 'added'
                  ? 'var(--surface-bg-success, #E6F4EA)'
                  : row.status === 'removed'
                  ? 'var(--surface-bg-error, #FFE3E3)'
                  : 'transparent',
                padding: '6px 10px',
                borderRadius: 4,
              }}
            >
              <Space>
                <Tag color={STATUS_TAG[row.status].color}>{STATUS_TAG[row.status].label}</Tag>
                <Typography.Text strong>{row.key}</Typography.Text>
              </Space>
              <div style={{ marginTop: 4 }}>
                <Typography.Text type="secondary">prev：</Typography.Text>
                {renderValue(row.prevValue, row.status, row.currValue)}
              </div>
              <div style={{ marginTop: 4 }}>
                <Typography.Text type="secondary">curr：</Typography.Text>
                <ValueDisplay value={row.currValue} status={row.status === 'removed' ? 'changed' : row.status} />
              </div>
            </div>
          ))}
        </Space>
      </div>
    </div>
  );
}

export default DiffViewer;