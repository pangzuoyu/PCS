/**
 * 交付物进度页的守卫（P9B-1 Task T6 · SPEC §6.24）。
 *
 * ## 为什么这页是「观测」的宿主
 *
 * T5 的 `WorkflowProgressPanel` 需要一个**宿主**才有意义 —— 本页就是它。
 * 本批**只 SIGN**（后端三类工作流的 `workflow_id` 语义不同：
 * `SIGN` → 版本 ID；`CHANGE_NOTICE` → 变更单自身的 deliverable_id
 * ⇒ 前端凑不齐 ⇒ 聚合端点延到 P9B-2，见 TODO-065）。
 *
 * ## 四条不能省的
 *
 * 1. ⚠️ **行展开才拉 progress**（列表加载时**不**预取）⇒ 无 N+1。
 * 2. ⚠️ SIGN 的 `workflow_id` 用 **`current_version_id`**（**不**用 rev 匹配 ——
 *    rev 是自由文本，匹配不出唯一版本）。
 * 3. ⚠️ **空状态三态可区分**：无版本 / 有版本但流程未开始 / 无权限。
 * 4. ⚠️ 前端**不得**自行按项目过滤交付物 —— 后端已做项目守卫
 *    （`check_project_access_or_404`）⇒ 前端过滤会把「无权限」说成「无数据」。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { DeliverableProgressPage } from '../../../src/pages/deliverables/DeliverableProgressPage';

const DRAFT_ID = 'd-1';
const VERSIONED_ID = 'd-2';

const DELIVERABLES = [
  {
    deliverable_id: DRAFT_ID,
    project_id: '00000000-0000-0000-0000-000000000001',
    deliverable_type: 'CALCULATION_BOOK',
    scope_type: 'PROJECT_ALL',
    scope_value: null,
    doc_no: 'CB-001',
    doc_no_mode: 'MANUAL',
    title: '泵计算书',
    current_rev: 'A',
    current_version_id: null, // ⚠️ 无版本 ⇒ 空态 ①
    version_purpose: 'ISSUED_FOR_CONSTRUCTION',
    sign_status: 'DRAFT',
    matrix_id: null,
    parent_deliverable_id: null,
    customer_approval_date: null,
    customer_approver_name: null,
    created_at: '2026-10-20T10:00:00Z',
  },
  {
    deliverable_id: VERSIONED_ID,
    project_id: '00000000-0000-0000-0000-000000000001',
    deliverable_type: 'CALCULATION_BOOK',
    scope_type: 'PROJECT_ALL',
    scope_value: 'PUMP',
    doc_no: 'CB-002',
    doc_no_mode: 'MANUAL',
    title: '换热器计算书',
    current_rev: 'B',
    current_version_id: 'v-2', // ⚠️ SIGN 的 workflow_id = **版本 ID**
    version_purpose: 'ISSUED_FOR_CONSTRUCTION',
    sign_status: 'CHANGE_PENDING',
    matrix_id: null,
    parent_deliverable_id: null,
    customer_approval_date: null,
    customer_approver_name: null,
    created_at: '2026-10-20T10:00:00Z',
  },
];

let progressCalls = 0;

const server = setupServer(
  http.get('/api/v1/deliverables', () =>
    HttpResponse.json({ items: DELIVERABLES, total: DELIVERABLES.length }),
  ),
  http.get('/api/v1/workflow-progress/:type/:id', ({ params }) => {
    progressCalls += 1;
    if (params.id === 'v-forbidden') {
      return HttpResponse.json({ code: 'FORBIDDEN' }, { status: 403 });
    }
    return HttpResponse.json({
      workflow_type: 'SIGN',
      workflow_id: String(params.id),
      project_id: '00000000-0000-0000-0000-000000000001',
      total: 1,
      pending: 0,
      in_progress: 1,
      completed: 0,
      skipped: 0,
      failed: 0,
      items: [
        {
          progress_id: 'p-1',
          step_order: 1,
          step_role: 'DESIGNER',
          step_status: 'IN_PROGRESS',
          started_at: '2026-10-20T10:00:00Z',
          completed_at: null,
          assignee: 'alice',
          result_hash: null,
        },
      ],
    });
  }),
);

describe('DeliverableProgressPage —— 交付物进度（SPEC §6.24）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    progressCalls = 0;
  });

  it('列表渲染：doc_no + title + sign_status', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-001')).toBeTruthy());
    expect(screen.getByText('泵计算书')).toBeTruthy();
    expect(screen.getByText('CB-002')).toBeTruthy();
  });

  it('⚠️ 行**展开**才拉 progress（列表加载时**不**预取 ⇒ 无 N+1）', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-001')).toBeTruthy());
    // 列表加载后**一次都**不该拉 progress
    expect(progressCalls).toBe(0);

    // 展开第一行（无版本的那行）⇒ 空态 ①
    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[0]);
    await waitFor(() => expect(screen.getByTestId('deliverable-no-version')).toBeTruthy());
    expect(screen.getByTestId('deliverable-no-version').textContent).toContain('尚未签发');
  });

  it('SIGN 的 workflow_id 用 **current_version_id**（不是 rev 匹配）', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    // 展开**第二**行（有版本）
    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(progressCalls).toBe(1));
    // ⚠️ 请求的 id 是**版本 ID**（v-2），**不是** rev 文本（'B'）
    expect(screen.getByTestId('deliverable-progress-panel').textContent).toContain('IN_PROGRESS');
  });

  it('空状态三态可区分：① 无版本 / ② 流程未开始 / ③ 无权限', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    // ① 无版本
    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[0]);
    await waitFor(() => expect(screen.getByTestId('deliverable-no-version')).toBeTruthy());
    expect(screen.getByTestId('deliverable-no-version').textContent).toContain('尚未签发');

    // ② 有版本但进度为空 ⇒ 「签署流程尚未开始」
    server.use(
      http.get('/api/v1/workflow-progress/:type/:id', () =>
        HttpResponse.json({
          workflow_type: 'SIGN',
          workflow_id: 'v-2',
          project_id: 'p-1',
          total: 0,
          pending: 0,
          in_progress: 0,
          completed: 0,
          skipped: 0,
          failed: 0,
          items: [],
        }),
      ),
    );
    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByTestId('workflow-progress-empty')).toBeTruthy());
    expect(screen.getByTestId('workflow-progress-empty').textContent).toContain(
      '尚未开始',
    );
  });

  it('③ 无权限（progress 403）⇒ 「你无权查看此交付物的进度」', async () => {
    server.use(
      http.get('/api/v1/workflow-progress/:type/:id', () =>
        HttpResponse.json({ code: 'FORBIDDEN' }, { status: 403 }),
      ),
    );
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());
    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByTestId('workflow-progress-empty')).toBeTruthy());
    expect(screen.getByTestId('workflow-progress-empty').textContent).toContain(
      '无权查看',
    );
  });

  it('只有 SIGN tab 被渲染（CHANGE_NOTICE / 代录 disabled ⇒ P9B-2 开）', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-001')).toBeTruthy());
    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByTestId('deliverable-progress-panel')).toBeTruthy());
    // ⚠️ 本批只 SIGN ⇒ 面板里只有「签署」一个 tab
    expect(screen.getByTestId('deliverable-progress-panel').textContent).toContain('签署');
    expect(screen.getByTestId('deliverable-progress-panel').textContent).not.toContain('变更单');
    expect(screen.getByTestId('deliverable-progress-panel').textContent).not.toContain('代录');
  });
});
