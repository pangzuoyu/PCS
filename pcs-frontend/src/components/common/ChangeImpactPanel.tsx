/**
 * ChangeImpactPanel — 变更影响分析面板（P45-1-8 / Task 13）。
 *
 * SPEC §6.7 + plan P45-1-8：
 * - 顶部 ⚠ 提示 + 变更源描述 + 变更人/时间
 * - 受影响记录列表：橙色左边框 + 警告图标 + tag/result
 * - 单行 [确认重算] + 多选 + 底部 [批量确认重算] / [全部暂不处理]
 *
 * Props（SPEC 锁定）：
 *   changeSource: { description, changed_by, changed_at }
 *   affectedRecords: AffectedRecord[]
 *   onConfirmRecalc?: (recordIds: string[]) => void
 *   onDefer?: () => void
 */
import { useMemo, useState } from 'react';
import { Alert, Button, Card, Checkbox, List, Space, Typography } from 'antd';
import { WarningOutlined } from '@ant-design/icons';

export interface ChangeSource {
  /** 变更源描述（如「物流 S-101 · 流量 50 → 60 m³/h」） */
  description: string;
  /** 变更人 */
  changed_by: string;
  /** 变更时间（ISO 字符串或可格式化日期） */
  changed_at: string;
}

export interface AffectedRecord {
  record_id: string;
  /** 记录类型（PIPE / PUMP / UTIL …），决定前缀图标 */
  record_type: string;
  /** 装置/记录位号 */
  tag_number: string;
  /** 影响的计算结果（如「压降结果」「扬程结果」「电耗汇总」） */
  result_label: string;
}

interface Props {
  changeSource: ChangeSource;
  affectedRecords: AffectedRecord[];
  onConfirmRecalc?: (recordIds: string[]) => void;
  onDefer?: () => void;
}

/** 类型 → 颜色 / 前缀（spec 灰色统一，仅左边框与图标传达警告） */
const TYPE_COLOR: Record<string, string> = {
  PIPE: 'var(--state-stale, #D29922)',
  PUMP: 'var(--state-stale, #D29922)',
  UTIL: 'var(--state-stale, #D29922)',
  SIM: 'var(--state-stale, #D29922)',
};

export function ChangeImpactPanel({
  changeSource,
  affectedRecords,
  onConfirmRecalc,
  onDefer,
}: Props): JSX.Element {
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const allSelected = useMemo(
    () =>
      affectedRecords.length > 0 &&
      affectedRecords.every((r) => selected.has(r.record_id)),
    [selected, affectedRecords],
  );

  function toggle(recordId: string): void {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(recordId)) next.delete(recordId);
      else next.add(recordId);
      return next;
    });
  }

  function toggleAll(): void {
    setSelected(() => {
      if (allSelected) return new Set();
      return new Set(affectedRecords.map((r) => r.record_id));
    });
  }

  function handleBatchConfirm(): void {
    const ids = allSelected
      ? affectedRecords.map((r) => r.record_id)
      : Array.from(selected);
    if (ids.length > 0) onConfirmRecalc?.(ids);
  }

  function handleDefer(): void {
    onDefer?.();
  }

  return (
    <Card
      data-testid="change-impact-panel"
      title={
        <Space>
          <WarningOutlined style={{ color: 'var(--state-stale, #D29922)' }} />
          <Typography.Text strong>上游数据已变更</Typography.Text>
        </Space>
      }
      style={{ marginTop: 16 }}
    >
      <Alert
        type="warning"
        showIcon
        data-testid="change-impact-source"
        message={
          <Space direction="vertical" size={2}>
            <span data-testid="change-source-description">
              变更源：{changeSource.description}
            </span>
            <Typography.Text type="secondary" data-testid="change-source-meta">
              变更人：{changeSource.changed_by} ·{' '}
              {changeSource.changed_at}
            </Typography.Text>
          </Space>
        }
        style={{ marginBottom: 16 }}
      />

      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          marginBottom: 8,
        }}
      >
        <Typography.Text strong data-testid="affected-count">
          受影响记录（{affectedRecords.length}）
        </Typography.Text>
        {affectedRecords.length > 0 && (
          <Checkbox
            data-testid="select-all"
            checked={allSelected}
            onChange={toggleAll}
          >
            全选
          </Checkbox>
        )}
      </div>

      <List
        data-testid="affected-list"
        size="small"
        dataSource={affectedRecords}
        renderItem={(r) => {
          const color = TYPE_COLOR[r.record_type] ?? 'var(--state-stale, #D29922)';
          return (
            <List.Item
              data-testid="affected-item"
              data-record-id={r.record_id}
              data-record-type={r.record_type}
              style={{
                borderLeft: `4px solid ${color}`,
                paddingLeft: 12,
              }}
            >
              <Space style={{ flex: 1 }}>
                <Checkbox
                  data-testid="affected-checkbox"
                  checked={selected.has(r.record_id)}
                  onChange={() => toggle(r.record_id)}
                />
                <span
                  data-testid="affected-type"
                  style={{ fontFamily: 'var(--font-mono, monospace)' }}
                >
                  ● {r.record_type}
                </span>
                <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>
                  {r.tag_number}
                </span>
                <span style={{ color: 'var(--text-secondary, #656D76)' }}>
                  {r.result_label}
                </span>
              </Space>
              <Button
                type="link"
                data-testid="confirm-single"
                data-record-id={r.record_id}
                onClick={() => onConfirmRecalc?.([r.record_id])}
              >
                确认重算
              </Button>
            </List.Item>
          );
        }}
      />

      <Space style={{ marginTop: 16 }}>
        <Button
          type="primary"
          data-testid="batch-confirm"
          disabled={selected.size === 0 && !allSelected}
          onClick={handleBatchConfirm}
        >
          批量确认重算（{allSelected ? affectedRecords.length : selected.size}）
        </Button>
        <Button data-testid="defer-all" onClick={handleDefer}>
          全部暂不处理
        </Button>
      </Space>
    </Card>
  );
}

export default ChangeImpactPanel;