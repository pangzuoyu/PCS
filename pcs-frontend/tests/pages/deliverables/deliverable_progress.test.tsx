/**
 * 交付物进度页的守卫（P9B-1 Task T6 · SPEC §6.24 · **P9B-2 改为聚合端点**）。
 *
 * ## P9B-2 之后这页打的是**聚合端点**（TODO-065）
 *
 * `GET /deliverables/{id}/progress` ⇒ 一次返回**两类**工作流的进度：
 * `SIGN`（workflow_id = 版本 id）与 `CUSTOMER_APPROVAL_PROXY`（= 交付物 id）。
 *
 * ⚠️ **没有 `CHANGE_NOTICE` 段**（R-13）：变更单**本身就是交付物** ⇒ 它自己
 * 一行、自有 SIGN 进度；靠 `parent_deliverable_id` 反查**永远查不到** ⇒
 * 留着一个**永远为假**的段比没有更坏。
 *
 * ## 四条不能省的
 *
 * 1. ⚠️ **行展开才拉**（列表加载时**不**预取）⇒ 无 N+1。
 * 2. ⚠️ **面板受控**（R-15）⇒ 展开一行**不**发分段请求
 *    （`workflow-progress/...` **零调用**）⇒ 聚合端点的收益不被抵消。
 * 3. ⚠️ **两种空态可分辨**：`available=false`（显示**原因**）≠
 *    `available=true` 但 `total=0`（显示「尚无步骤记录」）。
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
    current_version_id: null, // ⚠️ 无版本 ⇒ SIGN 段不可用
    version_purpose: 'ISSUED_FOR_CONSTRUCTION',
    sign_status: 'DRAFT',
    matrix_id: null,
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
    customer_approval_date: null,
    customer_approver_name: null,
    created_at: '2026-10-20T10:00:00Z',
  },
];

let aggregateCalls = 0;
let actionCalls = 0;
/** 动作时间线的**总条数**（> items.length ⇒ 被截断）。 */
let actionsTotal = 1;
/** 单条工作流端点的调用数 —— 受控模式下必须**恒为 0**（R-15）。 */
let singleProgressCalls = 0;
/** 聚合端点返回的段（测试按需改写）。 */
let sections: unknown[] = [];

const DEFAULT_SECTIONS = [
  {
    workflow_type: 'SIGN',
    workflow_id: 'v-2',
    available: true,
    reason: null,
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
  },
  {
    workflow_type: 'CUSTOMER_APPROVAL_PROXY',
    workflow_id: VERSIONED_ID,
    available: false,
    reason: '尚未签发版本，无签署流程',
    total: 0,
    pending: 0,
    in_progress: 0,
    completed: 0,
    skipped: 0,
    failed: 0,
    items: [],
  },
];

/** 列表端点的失败态（403 ⇒ 「无权查看」**不是**空表）。 */
let listStatus = 200;
/** 进度**按交付物 id**分别返回（多行展开那条用例专用）。 */
let usePerIdSections = false;

/** 每行的**不同**进度（用来断言「每行显示自己的」）。 */
const SECTIONS_BY_ID: Record<string, unknown[]> = {
  [DRAFT_ID]: [
    {
      workflow_type: 'SIGN',
      workflow_id: 'v-draft',
      available: true,
      reason: null,
      total: 1,
      pending: 0,
      in_progress: 1,
      completed: 0,
      skipped: 0,
      failed: 0,
      items: [
        {
          progress_id: 'p-draft',
          step_order: 1,
          step_role: 'DRAFT_ROW_ROLE',
          step_status: 'IN_PROGRESS',
          started_at: '2026-10-20T10:00:00Z',
          completed_at: null,
          assignee: 'alice',
          result_hash: null,
        },
      ],
    },
  ],
  [VERSIONED_ID]: [
    {
      workflow_type: 'SIGN',
      workflow_id: 'v-2',
      available: true,
      reason: null,
      total: 1,
      pending: 0,
      in_progress: 1,
      completed: 0,
      skipped: 0,
      failed: 0,
      items: [
        {
          progress_id: 'p-versioned',
          step_order: 1,
          step_role: 'VERSIONED_ROW_ROLE',
          step_status: 'IN_PROGRESS',
          started_at: '2026-10-20T10:00:00Z',
          completed_at: null,
          assignee: 'bob',
          result_hash: null,
        },
      ],
    },
  ],
};

const server = setupServer(
  http.get('/api/v1/deliverables', () => {
    if (listStatus !== 200) {
      return HttpResponse.json(
        { code: 'HTTP_403', message: '无权查看该项目的交付物' },
        { status: listStatus },
      );
    }
    return HttpResponse.json({ items: DELIVERABLES, total: DELIVERABLES.length });
  }),
  // ⚠️ **聚合端点**（P9B-2 · TODO-065）
  http.get('/api/v1/deliverables/:id/progress', ({ params }) => {
    aggregateCalls += 1;
    const id = String(params.id);
    // ⚠️ **每行给不同内容**（否则断言「每行显示自己的进度」测不出来）
    //    ⇒ 只在「多行展开」那条用例里开（其余用例共用 `sections`）。
    const own = usePerIdSections ? SECTIONS_BY_ID[id] : undefined;
    return HttpResponse.json({
      deliverable_id: id,
      sections: own ?? sections,
    });
  }),
  http.get('/api/v1/deliverables/:id/actions', ({ params }) => {
    actionCalls += 1;
    const items = [
      {
        action: 'DELIVERABLE_ISSUED',
        resource_type: 'deliverable',
        resource_id: String(params.id),
        actor_user_id: 'u-1',
        detail_json: '{"version_purpose":"ISSUED_FOR_CONSTRUCTION"}',
        created_at: '2026-10-20T10:00:00Z',
      },
    ];
    return HttpResponse.json({
      deliverable_id: String(params.id),
      items,
      // ⚠️ `total` 与 `items.length` 不一致 ⇒ 被**截断**（后端默认 limit=200）
      total: actionsTotal,
    });
  }),
  // ⚠️ 单条工作流端点 —— 受控模式下**不得**被调用（R-15）
  http.get('/api/v1/workflow-progress/:type/:id', () => {
    singleProgressCalls += 1;
    return HttpResponse.json({ items: [], total: 0 });
  }),
);

describe('DeliverableProgressPage —— 交付物进度（SPEC §6.24）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    aggregateCalls = 0;
    actionCalls = 0;
    singleProgressCalls = 0;
    sections = DEFAULT_SECTIONS;
    actionsTotal = 1;
    listStatus = 200;
    usePerIdSections = false;
  });

  it('列表渲染：doc_no + title + sign_status', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-001')).toBeTruthy());
    expect(screen.getByText('泵计算书')).toBeTruthy();
    expect(screen.getByText('CB-002')).toBeTruthy();
  });

  it('⚠️ **不展开** ⇒ 0 个请求（列表加载时**不**预取 ⇒ 无 N+1）', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-001')).toBeTruthy());
    expect(aggregateCalls).toBe(0);
    expect(actionCalls).toBe(0);
  });

  it('⚠️ 展开一行 ⇒ 打的是 **GET /deliverables/{id}/progress**（不是 workflow-progress/SIGN/...）', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(aggregateCalls).toBe(1));
    expect(screen.getByTestId('deliverable-progress-panel')).toBeTruthy();
  });

  it('⚠️ 展开**两行** ⇒ 每行显示**自己的**进度（不是最后展开那行的）', async () => {
    // ⚠️ 此前是**单个** `expandedId` + `expandedRowRender` 忽略 `record`
    //    ⇒ A 行和 B 行**同时**渲染同一份 state ⇒ A 行下面显示的是 **B 的进度**
    //    （doc_no 都对不上）⇒ 收起 B 后 A 行还展开着却显示「尚无进度信息」。
    usePerIdSections = true;
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    const icons = document.querySelectorAll('.ant-table-row-expand-icon');
    fireEvent.click(icons[0]);
    await waitFor(() => expect(screen.getByText('DRAFT_ROW_ROLE')).toBeTruthy());
    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByText('VERSIONED_ROW_ROLE')).toBeTruthy());

    // ⚠️ 两行**同时**展开 ⇒ **两个面板各显示各的**（此前两个面板渲染的是同一份
    //    state ⇒ 第一个面板里出现的是**第二行**的角色）。
    const panels = document.querySelectorAll('[data-testid=deliverable-progress-panel]');
    expect(panels.length).toBe(2);
    expect(panels[0].textContent).toContain('DRAFT_ROW_ROLE');
    expect(panels[0].textContent).not.toContain('VERSIONED_ROW_ROLE');
    expect(panels[1].textContent).toContain('VERSIONED_ROW_ROLE');

    // 收起 B ⇒ A 行**仍然**显示自己的进度
    // ⚠️ **重新取**展开图标（antd 展开后会重渲染表格 ⇒ 旧的 NodeList 可能失效）
    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByText('DRAFT_ROW_ROLE')).toBeTruthy());
    // ⚠️ antd 收起后**保留**该行的 DOM（隐藏）⇒ 断言「不可见」而不是「不存在」
    expect(screen.getByText('VERSIONED_ROW_ROLE')).not.toBeVisible();
  });

  it('⚠️ 列表 **403** ⇒ 显示「无权查看」（**不是**空表）', async () => {
    listStatus = 403;
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByTestId('deliverable-list-error')).toBeTruthy());
    expect(screen.getByTestId('deliverable-list-error').textContent).toContain('无权查看');
    // ⚠️ 不得渲染成「暂无数据」的空表
    expect(screen.queryByText('暂无数据')).toBeNull();
  });

  it('⚠️ 评审 #11：列表失败后**页内可恢复**（重试 ⇒ 表格回来，不用整页刷新）', async () => {
    listStatus = 403;
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByTestId('deliverable-list-error')).toBeTruthy());
    expect(screen.queryByText('CB-002')).toBeNull();

    // 后端恢复（或权限拿到）⇒ 点「重试」⇒ 同一挂载内表格回来
    listStatus = 200;
    fireEvent.click(screen.getByTestId('deliverable-list-retry'));
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());
    expect(screen.queryByTestId('deliverable-list-error')).toBeNull();
  });

  it('⚠️ R-15：展开一行 ⇒ **分段请求零调用**（面板受控 ⇒ 不自己拉）', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(aggregateCalls).toBe(1));
    await new Promise((r) => setTimeout(r, 50));
    // ⚠️ **必须**是 0 —— 否则聚合端点的收益被完全抵消，且两套数据源可能不一致
    expect(singleProgressCalls).toBe(0);
  });

  it('⚠️ **两段都渲染**（SIGN / CUSTOMER_APPROVAL_PROXY），且**没有** CHANGE_NOTICE 段（R-13）', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByTestId('deliverable-progress-panel')).toBeTruthy());

    expect(screen.getByTestId('deliverable-section-SIGN')).toBeTruthy();
    expect(screen.getByTestId('deliverable-section-CUSTOMER_APPROVAL_PROXY')).toBeTruthy();
    expect(screen.queryByTestId('deliverable-section-CHANGE_NOTICE')).toBeNull();
  });

  it('⚠️ `available=false` 的段 ⇒ 显示 **reason 原文**（不是空列表）（RF-6）', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByTestId('deliverable-progress-panel')).toBeTruthy());

    const block = screen.getByTestId('deliverable-section-CUSTOMER_APPROVAL_PROXY');
    expect(block.textContent).toContain('尚未签发版本，无签署流程');
  });

  it('⚠️ `available=true` 但 `total=0` ⇒ 「尚无步骤记录」（与「不可用」**不同**）', async () => {
    sections = [
      {
        workflow_type: 'SIGN',
        workflow_id: 'v-2',
        available: true,
        reason: null,
        total: 0,
        pending: 0,
        in_progress: 0,
        completed: 0,
        skipped: 0,
        failed: 0,
        items: [],
      },
    ];
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByTestId('workflow-progress-empty')).toBeTruthy());
    expect(screen.getByTestId('workflow-progress-empty').textContent).toContain('尚无步骤记录');
  });

  it('⚠️ 动作时间线渲染 actions.items；`detail_json` 是 JSON **文本** ⇒ 解析且畸形时不崩', async () => {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByTestId('deliverable-actions')).toBeTruthy());
    await waitFor(() => expect(screen.getAllByTestId('deliverable-action-item').length).toBe(1));
    expect(screen.getByTestId('deliverable-action-item').textContent).toContain(
      'DELIVERABLE_ISSUED',
    );
    expect(screen.getByTestId('deliverable-action-item').textContent).toContain(
      'version_purpose',
    );
  });

  it('⚠️ 动作时间线**被截断** ⇒ 明说「只显示前 N 条（共 M 条）」', async () => {
    // ⚠️ 后端默认 limit=200 ⇒ 超过 200 条时**静默截断** ⇒ 用户以为「就这些」。
    actionsTotal = 250;
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());
    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByTestId('deliverable-actions')).toBeTruthy());
    await waitFor(() =>
      expect(screen.getByTestId('deliverable-actions-truncated')).toBeTruthy(),
    );
    const hint = screen.getByTestId('deliverable-actions-truncated').textContent ?? '';
    expect(hint).toContain('250');
  });

  it('⚠️ 动作时间线空态是「尚无动作记录」（**不是**「尚无编辑记录」—— R-10）', async () => {
    server.use(
      http.get('/api/v1/deliverables/:id/actions', () =>
        HttpResponse.json({ deliverable_id: VERSIONED_ID, items: [], total: 0 }),
      ),
    );
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-002')).toBeTruthy());

    fireEvent.click(document.querySelectorAll('.ant-table-row-expand-icon')[1]);
    await waitFor(() => expect(screen.getByTestId('deliverable-actions-empty')).toBeTruthy());
    expect(screen.getByTestId('deliverable-actions-empty').textContent).toContain('动作记录');
  });

  it('⚠️ 列表**分页**（不得静默截断到前 100 条）', async () => {
    const seen: Array<{ limit: string | null; offset: string | null }> = [];
    server.use(
      http.get('/api/v1/deliverables', ({ request }) => {
        const url = new URL(request.url);
        seen.push({
          limit: url.searchParams.get('limit'),
          offset: url.searchParams.get('offset'),
        });
        return HttpResponse.json({ items: DELIVERABLES, total: 250 });
      }),
    );
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('CB-001')).toBeTruthy());
    // ⚠️ 必须有分页控件（否则 >100 条的交付物被静默截断）
    expect(document.querySelector('.ant-pagination')).toBeTruthy();
    // ⚠️ 请求必须带 limit / offset（可翻页）
    expect(seen[0]?.limit).toBeTruthy();
    expect(seen[0]?.offset).toBe('0');
  });
});
