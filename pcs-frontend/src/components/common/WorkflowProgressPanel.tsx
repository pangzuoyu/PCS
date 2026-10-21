/**
 * WorkflowProgressPanel —— 一条工作流的步骤进度（P9B-1 · SPEC §6.24）。
 *
 * 依据 P9A-OBS-001~004（ADR-0047 观测层）。
 *
 * ## 数据源
 *
 * `GET /api/v1/workflow-progress/{workflow_type}/{workflow_id}`
 * - `{workflow_type}` ∈ `SIGN` / `CHANGE_NOTICE` / `CUSTOMER_APPROVAL_PROXY`
 * - `{workflow_id}` **多态**：`SIGN` → **版本 ID**；其余 → **交付物 ID**
 *   ⇒ 前端**不得**假设它一定是交付物 ID（传错 ⇒ 404）。
 *
 * ## 四条纪律
 *
 * 1. **五态不得归并成三态**：`PENDING`（还没开始）与 `SKIPPED`（被跳过）
 *    都是「没完成」，但合并后用户无法区分「还没排到我」和「这一步被跳过」。
 * 2. **不得显示百分比**：`total` 是**节点数**不是工作量 ⇒ 百分比是编造的。
 * 3. **空态措辞**：`items` 为空 ⇒ 「该工作流暂无步骤记录」，
 *    **不是**「0 步已完成」。
 * 4. **CHANGE_NOTICE 的写入点当前不可达**（P9A-DLV-007）⇒ 该类型面板恒为空
 *    ⇒ **不得**把空面板显示成「流程异常」。
 */
import { useEffect, useState } from 'react';
import { Empty, Space, Tabs, Tag, Typography } from 'antd';

import { HashBadge } from './HashBadge';
import { api } from '../../api/client';
import type { components } from '../../types/api';
// ⚠️ 词表独立成文件（eslint `react-refresh/only-export-components` 不允许
// 组件文件导出非组件；仓库既有先例 `src/pages/report/definitionBody.ts`）。
import { WORKFLOW_TABS, type WorkflowType } from './workflowTabs';

type ProgressResponse = components['schemas']['WorkflowProgressResponse'];
type ProgressItem = components['schemas']['WorkflowProgressItemResponse'];

/** 五态配色（SPEC §6.24）。 */
const STEP_STATUS_STYLE: Record<
  string,
  { color: string; dashed?: boolean; pulse?: boolean }
> = {
  PENDING: { color: 'var(--text-secondary, #656D76)' },
  IN_PROGRESS: { color: 'var(--state-in-approval, #2F6FEB)', pulse: true },
  COMPLETED: { color: 'var(--state-checked, #2DA44E)' },
  // ⚠️ SKIPPED 与 PENDING **都是灰**，但一个更浅 + **虚线** ⇒ 可区分
  SKIPPED: { color: 'var(--text-disabled, #BFBFBF)', dashed: true },
  FAILED: { color: 'var(--state-check-rejected, #CF222E)' },
};

interface Props {
  workflowType: WorkflowType;
  workflowId: string;
}

export function WorkflowProgressPanel({ workflowType, workflowId }: Props): JSX.Element {
  const [data, setData] = useState<ProgressResponse | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void api
      .get<ProgressResponse>(
        `/workflow-progress/${workflowType}/${encodeURIComponent(workflowId)}`,
      )
      .then((res) => {
        if (!cancelled) setData(res.data);
      })
      .catch(() => {
        // ⚠️ 拿不到就明说（空态），**不得**静默当成「无步骤」
        if (!cancelled) setData(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [workflowType, workflowId]);

  const items: ProgressItem[] = [...(data?.items ?? [])].sort(
    (a, b) => a.step_order - b.step_order,
  );

  return (
    <div data-testid="workflow-progress-panel">
      <Tabs
        size="small"
        activeKey={workflowType}
        // ⚠️ **只渲染 enabled 的 tab**（本批只有 SIGN）
        items={WORKFLOW_TABS.filter((t) => t.enabled).map((t) => ({
          key: t.type,
          label: t.label,
        }))}
      />

      {data && (
        <Space
          size={16}
          wrap
          data-testid="workflow-progress-counts"
          style={{ marginBottom: 12 }}
        >
          <span>待办 {data.pending}</span>
          <span>进行中 {data.in_progress}</span>
          <span>完成 {data.completed}</span>
          <span>跳过 {data.skipped}</span>
          <span>失败 {data.failed}</span>
        </Space>
      )}

      {items.length === 0 ? (
        <Empty
          data-testid="workflow-progress-empty"
          description={
            loading ? '加载中…' : '该工作流暂无步骤记录'
          }
        />
      ) : (
        <Space direction="vertical" size={4} style={{ width: '100%' }}>
          {items.map((item) => {
            const style = STEP_STATUS_STYLE[item.step_status] ?? {
              color: 'var(--text-secondary, #656D76)',
            };
            return (
              <div
                key={item.progress_id}
                data-testid={`progress-node-${item.progress_id}`}
                data-step-order={item.step_order}
                data-step-status={item.step_status}
                data-status-color={style.color}
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: 8,
                  padding: '4px 8px',
                  borderLeft: `3px ${style.dashed ? 'dashed' : 'solid'} ${style.color}`,
                  opacity: style.pulse ? 0.9 : 1,
                }}
              >
                <span>#{item.step_order}</span>
                <Tag style={{ color: style.color, borderColor: style.color }}>
                  {item.step_status}
                </Tag>
                <span>{item.step_role}</span>
                {item.assignee && <span>· {item.assignee}</span>}
                {item.started_at && (
                  <Typography.Text type="secondary">
                    · 起 {item.started_at}
                  </Typography.Text>
                )}
                {item.completed_at && (
                  <Typography.Text type="secondary">
                    · 止 {item.completed_at}
                  </Typography.Text>
                )}
                {item.result_hash && <HashBadge hash={item.result_hash} />}
              </div>
            );
          })}
        </Space>
      )}
    </div>
  );
}

export default WorkflowProgressPanel;
