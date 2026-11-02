/**
 * 物流详情 —— 「校核记录」Tab（SPEC §7.7.2 · P9B-3 · T8）。
 *
 * 数据源：`GET /audit-logs?resource_type=streams&resource_id=<id>&action=RECORD_TRANSITION`
 * ⇒ 该物流的**全部**状态转移 ⇒ 前端再按 `detail_json.transition` 过滤出
 * **校对相关**的三条（SUBMIT_FOR_CHECK / PASS_CHECK / REJECT_CHECK）。
 *
 * ⚠️ **过滤靠 `detail_json.transition`，不是新造审计动作** —— 审计行的 action
 *    是 `RECORD_TRANSITION`（与记录侧**同构**）⇒ 别的 transition（提交审批、
 *    标记陈旧……）**不显示**在这个 Tab 里。
 * ⚠️ `detail_json` 在契约里是**任意 object** ⇒ 防御性读（可能整个字段缺失）。
 * ⚠️ **本 Tab 的后端过滤**是已知技术债（TODO-104）：一个物流的全部状态转移都
 *    拉回来在前端筛（当前平均 5~10 条，可接受）。
 * ⚠️ **`GET /audit-logs` 限 SYSTEM_ADMIN**（audit_logs 表**没有** project_id
 *    ⇒ 无法按项目守卫）⇒ 非管理员看到的是「无权查看」（TODO-112）。
 */
import { useEffect, useState } from 'react';
import { Alert, Card, Table, Typography } from 'antd';

import { auditApi, type AuditLogItem } from '../../../api/audit';
import { describePcsError } from '../../../api/errors';

/** 校对相关的状态转移（其余 transition 不显示）。 */
const REVIEW_TRANSITIONS = ['SUBMIT_FOR_CHECK', 'PASS_CHECK', 'REJECT_CHECK'];

/** 转移名 → 中文（其余原样显示，不猜）。 */
const TRANSITION_LABEL: Record<string, string> = {
  SUBMIT_FOR_CHECK: '提交校对',
  PASS_CHECK: '校对通过',
  REJECT_CHECK: '校对驳回',
};

/** 取 `detail_json.transition`（防御性：字段可能缺失 / 不是字符串）。 */
function transitionOf(row: AuditLogItem): string {
  const detail = row.detail_json;
  if (!detail || typeof detail !== 'object') return '';
  const value = detail.transition;
  return typeof value === 'string' ? value : '';
}

export function StreamReviewLogTab({ streamId }: { streamId: string }): JSX.Element {
  const [rows, setRows] = useState<AuditLogItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErrorMsg(null);
    auditApi
      .listAuditLogs({
        resource_type: 'streams',
        resource_id: streamId,
        action: 'RECORD_TRANSITION',
      })
      .then((res) => {
        if (!cancelled) setRows(res.items ?? []);
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

  // ⚠️ 过滤在前端（后端过滤是已知技术债 · TODO-104）
  const reviewRows = rows.filter((r) => REVIEW_TRANSITIONS.includes(transitionOf(r)));

  return (
    <div data-testid="stream-tab-review-log">
      {errorMsg && (
        <Alert type="error" showIcon message={errorMsg} data-testid="stream-review-log-error" />
      )}
      <Card title="校核记录" size="small">
        {reviewRows.length === 0 ? (
          <Typography.Text type="secondary">
            {loading ? '加载中…' : '（无校核记录）'}
          </Typography.Text>
        ) : (
          <Table
            size="small"
            rowKey="audit_id"
            loading={loading}
            dataSource={reviewRows}
            pagination={false}
            columns={[
              {
                title: '动作',
                dataIndex: 'action',
                width: 120,
                render: (_: unknown, row: AuditLogItem) =>
                  TRANSITION_LABEL[transitionOf(row)] ?? transitionOf(row),
              },
              { title: '操作人', dataIndex: 'user_id', width: 200, render: (v: string) => v ?? '—' },
              { title: '时间', dataIndex: 'occurred_at', width: 190 },
            ]}
          />
        )}
      </Card>
    </div>
  );
}

export default StreamReviewLogTab;
