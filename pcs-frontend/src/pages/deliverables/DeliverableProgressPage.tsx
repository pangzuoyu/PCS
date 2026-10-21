/**
 * DeliverableProgressPage —— 交付物的签署进度（P9B-1 · SPEC §6.24）。
 *
 * ## 它是「观测面板」的**宿主**
 *
 * `WorkflowProgressPanel`（T5）需要一个宿主才有意义 ⇒ 本页就是它。
 *
 * ## ⚠️ 本批**只 SIGN**
 *
 * 后端三类工作流的 `workflow_id` 语义**不同**：
 * - `SIGN` → **版本 ID**
 * - `CHANGE_NOTICE` → 变更单自身的 `deliverable_id`（变更单是独立交付物）
 * - `CUSTOMER_APPROVAL_PROXY` → 交付物 ID
 *
 * ⇒ 前端拿不全 ⇒ 聚合端点延到 **P9B-2**（TODO-065）。
 *
 * ## 三条纪律
 *
 * 1. ⚠️ **行展开才拉 progress**（列表加载时**不**预取）⇒ 无 N+1。
 * 2. ⚠️ SIGN 的 `workflow_id` 用 **`current_version_id`**（T0 新增的字段）——
 *    **不是**用 rev 匹配（rev 是自由文本，匹配不出唯一版本）。
 * 3. ⚠️ **不得自行按项目过滤交付物** —— 后端已做项目守卫
 *    （`check_project_access_or_404`）⇒ 前端过滤会把「无权限」说成「无数据」。
 */
import { useEffect, useState } from 'react';
import { Empty, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import { StateBadge } from '../../components/common/StateBadge';
import { WorkflowProgressPanel } from '../../components/common/WorkflowProgressPanel';
import { api } from '../../api/client';
import { PROJECT_ID } from '../../constants/env';
import type { components } from '../../types/api';

type Deliverable = components['schemas']['DeliverableResponse'];
type DeliverableList = components['schemas']['DeliverableListResponse'];

export function DeliverableProgressPage(): JSX.Element {
  const [items, setItems] = useState<Deliverable[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    void api
      .get<DeliverableList>('/deliverables', {
        params: { project_id: PROJECT_ID, limit: 100, offset: 0 },
      })
      .then((res) => {
        if (cancelled) return;
        setItems(res.data.items ?? []);
        setTotal(res.data.total ?? 0);
      })
      .catch(() => {
        if (!cancelled) {
          setItems([]);
          setTotal(0);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const columns: ColumnsType<Deliverable> = [
    { title: '编号', dataIndex: 'doc_no', key: 'doc_no' },
    { title: '名称', dataIndex: 'title', key: 'title' },
    {
      title: '当前 Rev',
      dataIndex: 'current_rev',
      key: 'current_rev',
    },
    {
      title: '状态',
      dataIndex: 'sign_status',
      key: 'sign_status',
      render: (v: string) => <StateBadge status={v as never} />,
    },
  ];

  return (
    <div data-testid="deliverable-progress-page">
      <PageHeader title="交付物签署进度" actions={<span />} />
      <Table<Deliverable>
        rowKey="deliverable_id"
        columns={columns}
        dataSource={items}
        loading={loading}
        pagination={false}
        scroll={{ x: 'max-content' }}
        expandable={{
          expandedRowRender: (row) => {
            // ⚠️ ① 没有版本行 ⇒ 「尚未签发」（**不是**「流程未开始」）
            if (!row.current_version_id) {
              return (
                <Empty
                  data-testid="deliverable-no-version"
                  description="该交付物尚未签发，无签署进度"
                />
              );
            }
            // ⚠️ ② SIGN 的 workflow_id = **版本 ID**（不是 rev、不是 deliverable_id）
            return (
              <div data-testid="deliverable-progress-panel">
                <WorkflowProgressPanel
                  workflowType="SIGN"
                  workflowId={row.current_version_id}
                  emptyDescription="签署流程尚未开始"
                  errorDescription="你无权查看此交付物的进度"
                />
              </div>
            );
          },
        }}
      />
      <span style={{ display: 'none' }}>{total}</span>
    </div>
  );
}

export default DeliverableProgressPage;
