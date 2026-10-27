/**
 * 记录状态时间线（P9B-2 · T5 · SPEC §7.19.1「状态时间线」）。
 *
 * ⚠️ **数据源是编辑审计**（`RECORD_EDITED`），**不是** `workflow_progress`
 * —— 后端注释明写：actions 回答「谁做了什么」，观测层回答「流程到哪一步了」，
 * 混用会把「查过一眼」也算成活动（RF-5 / R-10）。
 *
 * ⚠️ **空态文案是「尚无编辑记录」**，**不得**写成「尚无动作记录」——
 * 交付物动作时间线用的是**另一个**数据源（`/deliverables/{id}/actions`）
 * ⇒ 两个空态必须可分辨，否则用户以为看到的是流程进度。
 */
import { useEffect, useState } from 'react';
import { Empty, Timeline, Typography } from 'antd';

import { recordEditsApi, type RecordEditItem } from '../../api/audit';
import { extractPcsError } from '../../api/errors';
import type { EditableRecordType } from '../../api/records';

export interface RecordTimelineProps {
  module: EditableRecordType;
  recordId: string;
}

export function RecordTimeline({ module, recordId }: RecordTimelineProps): JSX.Element {
  const [items, setItems] = useState<RecordEditItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    void recordEditsApi
      .list(module, recordId)
      .then((res) => {
        if (!cancelled) setItems(res.items);
      })
      .catch((err) => {
        if (cancelled) return;
        const envelope = extractPcsError(err);
        setItems([]);
        setError(envelope?.message ? `加载编辑历史失败：${envelope.message}` : '暂时无法加载编辑历史');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [module, recordId]);

  return (
    <div data-testid="record-timeline">
      <Typography.Text strong>状态时间线</Typography.Text>
      {error && (
        <Typography.Text type="danger" data-testid="record-timeline-error">
          {error}
        </Typography.Text>
      )}
      {!error && items.length === 0 && !loading && (
        // ⚠️ **空态文案**：编辑记录 ≠ 动作记录（R-10）
        <Empty data-testid="record-timeline-empty" description="尚无编辑记录" />
      )}
      <Timeline
        items={items.map((item) => ({
          key: item.audit_id,
          children: (
            <div data-testid={`record-timeline-item-${item.audit_id}`}>
              <Typography.Text>
                {item.changed_fields && item.changed_fields.length > 0
                  ? item.changed_fields.join('、')
                  : '（未记录字段）'}
              </Typography.Text>
              <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                {item.user_id ?? '未知'} · {item.occurred_at}
              </Typography.Text>
            </div>
          ),
        }))}
      />
    </div>
  );
}
