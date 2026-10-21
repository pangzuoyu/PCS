/**
 * WorkflowProgressPanel 的守卫（P9B-1 Task T5 · SPEC §6.24）。
 *
 * ## 为什么这几条不能省
 *
 * - **五态不得归并成三态**：`PENDING` 与 `SKIPPED` 都是「没完成」，但一个是
 *   「还没开始」、一个是「被跳过」⇒ 合并后用户无法区分「还没排到我」和
 *   「这一步被跳过」。
 * - **不得显示百分比**：`total` 是**节点数**不是工作量 ⇒ 百分比是编造的。
 * - **空态措辞**：`items` 为空 ⇒ 「该工作流暂无步骤记录」，**不是**「0 步已完成」。
 * - **CHANGE_NOTICE 恒为空**（后端写入点不可达，P9A-DLV-007）⇒ 不得显示成
 *   「流程异常」。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { WorkflowProgressPanel } from '../../../src/components/common/WorkflowProgressPanel';
import { WORKFLOW_TABS } from '../../../src/components/common/workflowTabs';

type ProgressResponse = {
  workflow_type: string;
  workflow_id: string;
  project_id: string;
  total: number;
  pending: number;
  in_progress: number;
  completed: number;
  skipped: number;
  failed: number;
  items: Array<{
    progress_id: string;
    step_order: number;
    step_role: string;
    step_status: string;
    started_at?: string | null;
    completed_at?: string | null;
    assignee?: string | null;
    result_hash?: string | null;
  }>;
};

const ITEMS: ProgressResponse['items'] = [
  {
    progress_id: 'p2',
    step_order: 2,
    step_role: 'CHECKER',
    step_status: 'COMPLETED',
    started_at: '2026-10-20T10:00:00Z',
    completed_at: '2026-10-20T10:30:00Z',
    assignee: 'bob',
    result_hash: 'a3f9c21d8b7e6f50',
  },
  {
    progress_id: 'p1',
    step_order: 1,
    step_role: 'DESIGNER',
    step_status: 'PENDING',
    started_at: null,
    completed_at: null,
    assignee: null,
    result_hash: null,
  },
  {
    progress_id: 'p3',
    step_order: 3,
    step_role: 'REVIEWER',
    step_status: 'SKIPPED',
    started_at: null,
    completed_at: null,
    assignee: null,
    result_hash: null,
  },
  {
    progress_id: 'p4',
    step_order: 4,
    step_role: 'APPROVER',
    step_status: 'IN_PROGRESS',
    started_at: '2026-10-20T11:00:00Z',
    completed_at: null,
    assignee: 'carol',
    result_hash: null,
  },
  {
    progress_id: 'p5',
    step_order: 5,
    step_role: 'SYSTEM_ADMIN',
    step_status: 'FAILED',
    started_at: '2026-10-20T12:00:00Z',
    completed_at: null,
    assignee: 'dan',
    result_hash: null,
  },
];

const server = setupServer(
  http.get('/api/v1/workflow-progress/:type/:id', ({ params }) =>
    HttpResponse.json({
      workflow_type: String(params.type),
      workflow_id: String(params.id),
      project_id: '00000000-0000-0000-0000-000000000001',
      total: ITEMS.length,
      pending: 1,
      in_progress: 1,
      completed: 1,
      skipped: 1,
      failed: 1,
      items: ITEMS,
    } satisfies ProgressResponse),
  ),
);

describe('WorkflowProgressPanel — 观测进度（SPEC §6.24）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    // 每个用例独立渲染，避免上一个的 DOM 残留
    document.body.innerHTML = '';
  });

  it('五态分色，**PENDING 与 SKIPPED 不合并**', async () => {
    render(<WorkflowProgressPanel workflowType="SIGN" workflowId="v-1" />);
    await waitFor(() => expect(screen.getByTestId('workflow-progress-panel')).toBeTruthy());

    const pending = screen.getByTestId('progress-node-p1');
    const skipped = screen.getByTestId('progress-node-p3');
    expect(pending.getAttribute('data-step-status')).toBe('PENDING');
    expect(skipped.getAttribute('data-step-status')).toBe('SKIPPED');
    // ⚠️ 两态的**呈现**必须可区分（颜色 class 不同）
    expect(pending.getAttribute('data-status-color')).not.toBe(
      skipped.getAttribute('data-status-color'),
    );
  });

  it('⚠️ **不显示百分比**（total 是节点数不是工作量）', async () => {
    render(<WorkflowProgressPanel workflowType="SIGN" workflowId="v-1" />);
    await waitFor(() => expect(screen.getByTestId('workflow-progress-panel')).toBeTruthy());
    expect(screen.getByTestId('workflow-progress-panel').textContent).not.toContain('%');
  });

  it('顶部五计数取响应同名字段', async () => {
    render(<WorkflowProgressPanel workflowType="SIGN" workflowId="v-1" />);
    await waitFor(() => expect(screen.getByTestId('workflow-progress-counts')).toBeTruthy());
    const counts = screen.getByTestId('workflow-progress-counts').textContent ?? '';
    expect(counts).toContain('待办');
    expect(counts).toContain('进行中');
    expect(counts).toContain('完成');
    expect(counts).toContain('跳过');
    expect(counts).toContain('失败');
  });

  it('节点按 step_order **升序**', async () => {
    render(<WorkflowProgressPanel workflowType="SIGN" workflowId="v-1" />);
    // ⚠️ 等**节点**出现（不是等面板出现）—— 节点是 fetch 落地后才渲染的
    await waitFor(() =>
      expect(document.querySelectorAll('[data-step-order]').length).toBe(ITEMS.length),
    );
    const orders = Array.from(
      document.querySelectorAll('[data-step-order]'),
    ).map((el) => Number(el.getAttribute('data-step-order')));
    expect(orders).toEqual([1, 2, 3, 4, 5]);
  });

  it('result_hash 用 HashBadge', async () => {
    render(<WorkflowProgressPanel workflowType="SIGN" workflowId="v-1" />);
    await waitFor(() => expect(screen.getByTestId('progress-node-p2')).toBeTruthy());
    expect(screen.getByTestId('progress-node-p2').textContent).toContain('a3f9');
  });

  it('WORKFLOW_TABS **只渲染 enabled 的 tab**（本批只有 SIGN）', () => {
    render(<WorkflowProgressPanel workflowType="SIGN" workflowId="v-1" />);
    const enabled = WORKFLOW_TABS.filter((t) => t.enabled).map((t) => t.type);
    expect(enabled).toEqual(['SIGN']);
    // ⚠️ 后端枚举**没有** `DOC_PROXY`（「代录」= `CUSTOMER_APPROVAL_PROXY`）
    expect(WORKFLOW_TABS.map((t) => t.type)).not.toContain('DOC_PROXY');
    expect(WORKFLOW_TABS.map((t) => t.type)).toContain('CUSTOMER_APPROVAL_PROXY');
  });
});


describe('WorkflowProgressPanel — 空态与不可达类型', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());

  it('items 为空 ⇒ 空态「该工作流暂无步骤记录」，**不是**「0 步已完成」', async () => {
    server.use(
      http.get('/api/v1/workflow-progress/:type/:id', () =>
        HttpResponse.json({
          workflow_type: 'CHANGE_NOTICE',
          workflow_id: 'd-1',
          project_id: 'p-1',
          total: 0,
          pending: 0,
          in_progress: 0,
          completed: 0,
          skipped: 0,
          failed: 0,
          items: [],
        } satisfies ProgressResponse),
      ),
    );
    render(<WorkflowProgressPanel workflowType="CHANGE_NOTICE" workflowId="d-1" />);
    // ⚠️ 等**加载完成**后的空态（加载中也是同一个容器，文案不同）
    await waitFor(() =>
      expect(screen.getByTestId('workflow-progress-empty').textContent ?? '').toContain(
        '暂无步骤记录',
      ),
    );
    const text = screen.getByTestId('workflow-progress-empty').textContent ?? '';
    expect(text).toContain('暂无步骤记录');
    expect(text).not.toContain('0 步已完成');
    // ⚠️ CHANGE_NOTICE 的写入点不可达（P9A-DLV-007）⇒ **不得**显示成「流程异常」
    expect(text).not.toContain('异常');
  });
});
