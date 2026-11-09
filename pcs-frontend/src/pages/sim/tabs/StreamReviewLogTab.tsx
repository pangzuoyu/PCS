/**
 * 物流详情 —— 「校核记录」Tab（SPEC §7.7.2 · P9B-3 · T8 · TODO-112 改）。
 *
 * 数据源：`GET /streams/{id}/review-log`（**项目守卫**端点）
 * ⇒ 设计师能读到**自己物流**的校核经过。
 *
 * ⚠️ **过滤在后端** —— 端点只返回 `SUBMIT_FOR_CHECK` / `PASS_CHECK` /
 * `REJECT_CHECK` 三条（最小暴露原则）⇒ 前端**不得**再过滤一遍
 * （两处过滤 = 两个口径 = 迟早漂移）⇒ 本文件里**没有** `REVIEW_TRANSITIONS`。
 *
 * ⚠️ **为什么不再用 `GET /audit-logs`**：那个端点限 SYSTEM_ADMIN
 * （`audit_logs` 表**没有** `project_id` ⇒ 无法按项目守卫）⇒
 * 非管理员看到的是「无权查看」。
 */
import { useEffect, useState } from 'react';
import { Alert, Card, Table, Typography } from 'antd';

import { streamApi, type ReviewLogItem } from '../../../api/stream';
import { describePcsError } from '../../../api/errors';

/** 转移名 → 中文（其余原样显示，不猜）。 */
const TRANSITION_LABEL: Record<string, string> = {
  SUBMIT_FOR_CHECK: '提交校对',
  PASS_CHECK: '校对通过',
  REJECT_CHECK: '校对驳回',
};

export function StreamReviewLogTab({ streamId }: { streamId: string }): JSX.Element {
  const [rows, setRows] = useState<ReviewLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErrorMsg(null);
    streamApi
      .fetchReviewLog(streamId)
      .then((res) => {
        if (!cancelled) setRows(res ?? []);
      })
      .catch((err: unknown) => {
        if (!cancelled) setErrorMsg(describePcsError(err, '加载校核记录失败'));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [streamId]);

  return (
    <div data-testid="stream-tab-review-log">
      {errorMsg && (
        <Alert type="error" showIcon message={errorMsg} data-testid="stream-review-log-error" />
      )}
      <Card title="校核记录" size="small">
        {rows.length === 0 ? (
          <Typography.Text type="secondary">
            {loading ? '加载中…' : '（无校核记录）'}
          </Typography.Text>
        ) : (
          <Table
            size="small"
            rowKey={(row: ReviewLogItem) => `${row.transition}-${row.occurred_at}`}
            loading={loading}
            dataSource={rows}
            pagination={false}
            columns={[
              {
                title: '动作',
                dataIndex: 'transition',
                width: 120,
                render: (v: string) => TRANSITION_LABEL[v] ?? v,
              },
              {
                title: '操作人',
                dataIndex: 'operator',
                width: 200,
                render: (v: string | null) => v ?? '—',
              },
              { title: '时间', dataIndex: 'occurred_at', width: 190 },
              {
                title: '说明',
                dataIndex: 'detail',
                width: 200,
                render: (v: string | null) => v ?? '—',
              },
            ]}
          />
        )}
      </Card>
    </div>
  );
}

export default StreamReviewLogTab;
