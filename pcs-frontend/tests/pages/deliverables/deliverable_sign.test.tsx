/**
 * 交付物级签署**写面**（P9B-2 · T8 · SPEC §7.19）。
 *
 * ## 守五件事
 *
 * 1. ⚠️ **「签发」的禁用优先于报错** —— 已有版本时按钮**禁用**（不是点了吃
 *    409）。⚠️ 但**退回后（DRAFT）例外**：此时必须**能**再签发，否则变更单
 *    被驳回一次就**永久卡死**（后端 `issue` 的幂等判据就是「有没有未退回的
 *    版本」⇒ DRAFT 时允许重签）。
 * 2. ⚠️ **「签署」显示矩阵的下一步**（步骤号 + 角色）；当前角色**不在**该步的
 *    `sign_role` ⇒ 按钮禁用 + **写明原因**（不是让用户猜）。
 * 3. ⚠️ **退回必须填理由**（前端拦）—— 退回是签署流程里唯一能纠错的路径。
 * 4. ⚠️ **签署成功 ⇒ 重新拉该行的进度**（不乐观更新）⇒ 步骤推进看得见。
 * 5. ⚠️ **代录失败 ⇒ 显示后端 `error` 原文**，不得显示成功。
 *
 * ## 为什么用 MSW mock **服务端**
 *
 * 被测的是「我们怎么消费后端的响应与错误」，不是「mock 的行为」⇒ mock
 * 服务端（返回**契约形状**）。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { DeliverableProgressPage } from '../../../src/pages/deliverables/DeliverableProgressPage';
import { useAuth } from '../../../src/store/auth';
import type { components } from '../../../src/types/api';

type Deliverable = components['schemas']['DeliverableResponse'];

const DRAFT_NO_VERSION = {
  deliverable_id: 'd-draft',
  project_id: 'p-1',
  deliverable_type: 'CALCULATION_BOOK',
  scope_type: 'PROJECT_ALL',
  doc_no: 'CB-001',
  doc_no_mode: 'MANUAL',
  title: '泵计算书',
  current_rev: '0',
  version_purpose: 'DRAFT',
  sign_status: 'DRAFT',
  current_version_id: null,
  matrix_id: 'm-1',
} satisfies Deliverable;

const PENDING_WITH_VERSION = {
  ...DRAFT_NO_VERSION,
  deliverable_id: 'd-pending',
  doc_no: 'CB-002',
  title: '换热器计算书',
  current_rev: '1',
  version_purpose: 'ISSUED_FOR_CONSTRUCTION',
  sign_status: 'PENDING',
  current_version_id: 'v-2',
} satisfies Deliverable;

/** 已退回（DRAFT）但**已有版本** ⇒ 允许再签发（否则变更单永久卡死）。 */
const DRAFT_WITH_VERSION = {
  ...PENDING_WITH_VERSION,
  deliverable_id: 'd-returned',
  doc_no: 'CB-003',
  sign_status: 'DRAFT',
} satisfies Deliverable;

/** 版本冻结的签署步骤（`signature_summary_json.steps`）。 */
const FROZEN_STEPS = [
  { step_order: 1, sign_role: 'DESIGNER', required: true, can_self_check: true, can_skip: false },
  { step_order: 2, sign_role: 'REVIEWER', required: true, can_self_check: true, can_skip: false },
];

/** 第 1 步已签完 ⇒ 下一步是第 2 步（REVIEWER）。 */
const SIGN_PROGRESS = {
  deliverable_id: 'd-pending',
  sections: [
    {
      workflow_type: 'SIGN',
      workflow_id: 'v-2',
      available: true,
      reason: null,
      total: 2,
      pending: 0,
      in_progress: 1,
      completed: 1,
      skipped: 0,
      failed: 0,
      items: [
        {
          progress_id: 'p-1',
          step_order: 1,
          step_role: 'DESIGNER',
          step_status: 'COMPLETED',
          started_at: '2026-10-20T10:00:00Z',
          completed_at: '2026-10-20T10:05:00Z',
          assignee: 'u-1',
          result_hash: null,
        },
      ],
    },
  ],
} satisfies components['schemas']['DeliverableProgressResponse'];

let listCalls = 0;
let progressCalls = 0;
let snapshotCalls = 0;
let issueCalls = 0;
let signCalls = 0;
let proxyCalls = 0;
let lastSignBody: Record<string, unknown> | null = null;
let lastIssueBody: Record<string, unknown> | null = null;
/** 代录端点是否失败（失败 ⇒ 弹窗要显示后端原文）。 */
let proxyFails = false;
/** 代录端点是否返 **401**（二次认证失败 ⇒ **不是**会话过期！）。 */
let proxyUnauthorized = false;
/** 版本快照端点是否失败（失败 ⇒ 「读不到步骤」，**不是**「没有步骤」）。 */
let snapshotFails = false;

const server = setupServer(
  http.get('/api/v1/deliverables', () => {
    listCalls += 1;
    return HttpResponse.json({
      items: [DRAFT_NO_VERSION, PENDING_WITH_VERSION, DRAFT_WITH_VERSION],
      total: 3,
      limit: 20,
      offset: 0,
    });
  }),
  http.get('/api/v1/deliverables/:id/progress', () => {
    progressCalls += 1;
    return HttpResponse.json(SIGN_PROGRESS);
  }),
  http.get('/api/v1/deliverables/:id/actions', () =>
    HttpResponse.json({ deliverable_id: 'd-pending', items: [], total: 0 }),
  ),
  http.get('/api/v1/deliverables/:id/versions/:rev/snapshot', () => {
    snapshotCalls += 1;
    if (snapshotFails) {
      return HttpResponse.json(
        { code: 'HTTP_500', message: '读不到签署步骤' },
        { status: 500 },
      );
    }
    return HttpResponse.json({
      deliverable_id: 'd-pending',
      rev: '1',
      version_purpose: 'ISSUED_FOR_CONSTRUCTION',
      description: '第 1 版',
      doc_no: 'CB-002',
      sign_status: 'PENDING',
      record_snapshot_json: {},
      signature_summary_json: { steps: FROZEN_STEPS, signatures: [] },
      bindings: [],
    });
  }),
  http.post('/api/v1/deliverables/:id/issue', async ({ request }) => {
    issueCalls += 1;
    lastIssueBody = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      deliverable_id: 'd-draft',
      version_id: 'v-9',
      rev: '1',
      doc_no: 'CB-001',
      version_purpose: 'ISSUED_FOR_CONSTRUCTION',
      sign_status: 'PENDING',
      issued_at: '2026-10-20T10:00:00Z',
    });
  }),
  http.post('/api/v1/deliverables/:id/sign-step', async ({ request }) => {
    signCalls += 1;
    lastSignBody = (await request.json()) as Record<string, unknown>;
    return HttpResponse.json({
      deliverable_id: 'd-pending',
      version_id: 'v-2',
      step_index: 2,
      step_role: 'REVIEWER',
      decision: lastSignBody?.decision ?? 'SIGN',
      state: 'COMPLETED',
      deliverable_sign_status: 'PENDING',
      signed_at: '2026-10-20T10:10:00Z',
    });
  }),
  http.post('/api/v1/deliverables/:id/customer-approval/proxy', async ({ request }) => {
    proxyCalls += 1;
    await request.json();
    if (proxyUnauthorized) {
      // ⚠️ **二次认证失败**（AD 密码打错）⇒ 401，但**会话没过期**
      return HttpResponse.json(
        { code: 'SECONDARY_AUTH_FAILED', message: '用户名或密码错误' },
        { status: 401 },
      );
    }
    if (proxyFails) {
      return HttpResponse.json(
        { code: 'CREDENTIAL_FILE_NOT_FOUND', message: '代录失败：凭证文件不存在' },
        { status: 422 },
      );
    }
    return HttpResponse.json({
      deliverable_id: 'd-pending',
      version_id: 'v-2',
      attachment_id: 'att-1',
      customer_approver_name: '客户方 张三',
      approval_date: '2026-10-20',
      approval_method: 'EMAIL',
      is_proxy: true,
      proxied_at: '2026-10-20T10:00:00Z',
    });
  }),
);

describe('交付物级签署写面（T8）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    listCalls = 0;
    progressCalls = 0;
    snapshotCalls = 0;
    issueCalls = 0;
    signCalls = 0;
    proxyCalls = 0;
    lastSignBody = null;
    lastIssueBody = null;
    proxyFails = false;
    proxyUnauthorized = false;
    snapshotFails = false;
    useAuth.setState({ role: 'DESIGNER', accessToken: 'test-token' });
  });

  async function renderPage() {
    render(<DeliverableProgressPage />);
    await waitFor(() => expect(screen.getByText('泵计算书')).toBeTruthy());
  }

  it('⚠️ 「签发」：**无版本 ⇒ 可用**；已有版本且 PENDING ⇒ **禁用**', async () => {
    await renderPage();

    const noVersion = screen.getByTestId('deliverable-issue-d-draft');
    const issued = screen.getByTestId('deliverable-issue-d-pending');
    expect(noVersion.hasAttribute('disabled')).toBe(false);
    expect(issued.hasAttribute('disabled')).toBe(true);
  });

  it('⚠️ 「签发」：**退回后（DRAFT + 已有版本）⇒ 仍可用**（否则变更单永久卡死）', async () => {
    await renderPage();

    const returned = screen.getByTestId('deliverable-issue-d-returned');
    expect(returned.hasAttribute('disabled')).toBe(false);
  });

  it('⚠️ 「签发」成功 ⇒ 提交**版本目的**（逐字）并**重新拉列表**', async () => {
    await renderPage();

    fireEvent.click(screen.getByTestId('deliverable-issue-d-draft'));
    await waitFor(() => expect(screen.getByTestId('issue-submit')).toBeTruthy());
    fireEvent.click(screen.getByTestId('issue-submit'));

    await waitFor(() => expect(issueCalls).toBe(1));
    expect(lastIssueBody?.version_purpose).toBe('ISSUED_FOR_CONSTRUCTION');
    // ⚠️ 不乐观更新 ⇒ 重新拉列表
    await waitFor(() => expect(listCalls).toBeGreaterThan(1));
  });

  it('⚠️ 「签署」⇒ 弹窗显示**下一步**（步骤号 + 角色）；角色不符 ⇒ 按钮禁用 + 写明原因', async () => {
    await renderPage();

    fireEvent.click(screen.getByTestId('deliverable-sign-d-pending'));
    await waitFor(() => expect(screen.getByTestId('sign-next-step')).toBeTruthy());

    // ⚠️ 下一步 = 第 2 步（REVIEWER）—— 第 1 步已签完
    expect(screen.getByTestId('sign-next-step').textContent).toContain('第 2 步');
    expect(screen.getByTestId('sign-next-step').textContent).toContain('REVIEWER');
    // ⚠️ 步骤取**版本冻结快照**（不是活矩阵 ⇒ 与后端同源，bug-2063）
    expect(snapshotCalls).toBeGreaterThan(0);
    // ⚠️ 当前角色 DESIGNER ≠ REVIEWER ⇒ 禁用 + 说明
    expect(screen.getByTestId('sign-submit').hasAttribute('disabled')).toBe(true);
    expect(screen.getByTestId('sign-role-hint').textContent).toContain('REVIEWER');
  });

  it('⚠️ 「退回」⇒ **理由必填**（前端拦 ⇒ 不发请求）', async () => {
    useAuth.setState({ role: 'REVIEWER', accessToken: 'test-token' });
    await renderPage();

    fireEvent.click(screen.getByTestId('deliverable-sign-d-pending'));
    await waitFor(() => expect(screen.getByTestId('sign-return')).toBeTruthy());
    fireEvent.click(screen.getByTestId('sign-return'));
    await waitFor(() => expect(screen.getByTestId('sign-return-submit')).toBeTruthy());

    fireEvent.click(screen.getByTestId('sign-return-submit'));

    // ⚠️ 理由为空 ⇒ **不发请求**
    await waitFor(() => expect(screen.getByTestId('sign-reason-required')).toBeTruthy());
    expect(signCalls).toBe(0);
  });

  it('⚠️ 「退回」填了理由 ⇒ 请求体带 `reason` + `decision=RETURN`', async () => {
    useAuth.setState({ role: 'REVIEWER', accessToken: 'test-token' });
    await renderPage();

    fireEvent.click(screen.getByTestId('deliverable-sign-d-pending'));
    await waitFor(() => expect(screen.getByTestId('sign-return')).toBeTruthy());
    fireEvent.click(screen.getByTestId('sign-return'));
    await waitFor(() => expect(screen.getByTestId('sign-return-reason')).toBeTruthy());
    fireEvent.change(screen.getByTestId('sign-return-reason'), {
      target: { value: 'P&ID 缺 E-101' },
    });
    fireEvent.click(screen.getByTestId('sign-return-submit'));

    await waitFor(() => expect(signCalls).toBe(1));
    expect(lastSignBody?.decision).toBe('RETURN');
    expect(lastSignBody?.reason).toBe('P&ID 缺 E-101');
    expect(lastSignBody?.version_id).toBe('v-2');
    expect(lastSignBody?.step_index).toBe(2);
  });

  it('⚠️ 签署成功 ⇒ **重新拉该行的进度**（不乐观更新）', async () => {
    useAuth.setState({ role: 'REVIEWER', accessToken: 'test-token' });
    await renderPage();

    fireEvent.click(screen.getByTestId('deliverable-sign-d-pending'));
    await waitFor(() => expect(screen.getByTestId('sign-submit')).toBeTruthy());
    const before = progressCalls;
    fireEvent.click(screen.getByTestId('sign-submit'));

    await waitFor(() => expect(signCalls).toBe(1));
    // ⚠️ 进度被重新拉（不是本地改状态）
    await waitFor(() => expect(progressCalls).toBeGreaterThan(before));
  });

  it('⚠️ 读不到签署步骤 ⇒ 显示「**读不到**」（**不是**「没有待签的步骤」）', async () => {
    snapshotFails = true;
    await renderPage();

    fireEvent.click(screen.getByTestId('deliverable-sign-d-pending'));
    await waitFor(() => expect(screen.getByTestId('sign-context-error')).toBeTruthy());
    // ⚠️ 不得说「没有待签的步骤」—— 那会让用户以为**签完了**
    expect(screen.queryByTestId('sign-no-step')).toBeNull();
  });

  it('⚠️ 代录 **401**（二次认证失败）⇒ 显示原文 + **不登出**（会话没过期！）', async () => {
    // ⚠️ axios 拦截器此前对**任何** 401 都 clearSession + 跳登录 ⇒ AD 密码打错
    //    ⇒ 用户被踢回登录页、填好的凭证全丢、且**看不到**「用户名或密码错误」。
    proxyUnauthorized = true;
    await renderPage();

    fireEvent.click(screen.getByTestId('deliverable-proxy-d-pending'));
    await waitFor(() => expect(screen.getByTestId('proxy-submit')).toBeTruthy());
    fireEvent.change(screen.getByTestId('proxy-file-path'), {
      target: { value: 'approvals/customer.pdf' },
    });
    fireEvent.change(screen.getByTestId('proxy-file-name'), {
      target: { value: 'customer.pdf' },
    });
    fireEvent.change(screen.getByTestId('proxy-approver-name'), {
      target: { value: '客户方 张三' },
    });
    fireEvent.change(screen.getByTestId('proxy-approval-date'), {
      target: { value: '2026-10-20' },
    });
    fireEvent.change(screen.getByTestId('proxy-secondary-username'), {
      target: { value: 'zhangsan' },
    });
    fireEvent.change(screen.getByTestId('proxy-secondary-password'), {
      target: { value: 'wrong' },
    });
    fireEvent.click(screen.getByTestId('proxy-submit'));

    await waitFor(() => expect(proxyCalls).toBe(1));
    await waitFor(() => expect(screen.getByTestId('sign-dialog-error')).toBeTruthy());
    expect(screen.getByTestId('sign-dialog-error').textContent).toContain('用户名或密码错误');
    // ⚠️ **会话还在**（不是登录过期 ⇒ 不该清 session）
    expect(useAuth.getState().accessToken).toBe('test-token');
  });

  it('⚠️ 「代录」⇒ 失败时显示后端 `message` **原文**（不得显示成功）', async () => {
    proxyFails = true;
    await renderPage();

    fireEvent.click(screen.getByTestId('deliverable-proxy-d-pending'));
    await waitFor(() => expect(screen.getByTestId('proxy-submit')).toBeTruthy());
    fireEvent.change(screen.getByTestId('proxy-file-path'), {
      target: { value: 'approvals/customer.pdf' },
    });
    fireEvent.change(screen.getByTestId('proxy-file-name'), {
      target: { value: 'customer.pdf' },
    });
    fireEvent.change(screen.getByTestId('proxy-approver-name'), {
      target: { value: '客户方 张三' },
    });
    fireEvent.change(screen.getByTestId('proxy-approval-date'), {
      target: { value: '2026-10-20' },
    });
    fireEvent.change(screen.getByTestId('proxy-secondary-username'), {
      target: { value: 'zhangsan' },
    });
    fireEvent.change(screen.getByTestId('proxy-secondary-password'), {
      target: { value: 's3cret' },
    });
    fireEvent.click(screen.getByTestId('proxy-submit'));

    await waitFor(() => expect(proxyCalls).toBe(1));
    await waitFor(() => expect(screen.getByTestId('sign-dialog-error')).toBeTruthy());
    expect(screen.getByTestId('sign-dialog-error').textContent).toContain(
      '代录失败：凭证文件不存在',
    );
  });
});
