/**
 * 交付物读面客户端的**端点形状**（P9B-2 · T3）。
 *
 * ## 这组测试抓的是「打错端点」
 *
 * `progress` 若打 `GET /workflow-progress/SIGN/{version_id}` ⇒ 前端得自己拼
 * 「哪类工作流用哪个 id」⇒ 后端加一类工作流，前端就查的是**空的**那一段
 * （关联规则是**后端的业务规则**，不是前端的拼装活）。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { deliverablesApi } from '../../src/api/deliverables';
import type { components } from '../../src/types/api';

const DELIVERABLE_ID = 'aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee';

let lastUrl = '';
let lastMethod = '';
let signCalls = 0;
/** 最近一次写请求的**请求体**（逐字断言 ⇒ 字段名/取值不许变形）。 */
let lastBody: unknown = null;

const MOCK_PROGRESS = {
  deliverable_id: DELIVERABLE_ID,
  sections: [
    {
      workflow_type: 'SIGN',
      workflow_id: 'v-2',
      available: true,
      reason: null,
      total: 2,
      pending: 1,
      in_progress: 1,
      completed: 0,
      skipped: 0,
      failed: 0,
      items: [],
    },
    {
      workflow_type: 'CUSTOMER_APPROVAL_PROXY',
      workflow_id: DELIVERABLE_ID,
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
  ],
} satisfies components['schemas']['DeliverableProgressResponse'];

const MOCK_ACTIONS = {
  deliverable_id: DELIVERABLE_ID,
  items: [
    {
      action: 'DELIVERABLE_ISSUED',
      resource_type: 'deliverable',
      resource_id: DELIVERABLE_ID,
      actor_user_id: 'u-1',
      detail_json: '{"version_purpose":"ISSUED_FOR_CONSTRUCTION"}',
      created_at: '2026-10-20T10:00:00Z',
    },
  ],
  total: 1,
} satisfies components['schemas']['DeliverableActionsListResponse'];

const server = setupServer(
  http.get('/api/v1/deliverables/:id/progress', ({ request }) => {
    lastUrl = request.url;
    lastMethod = request.method;
    return HttpResponse.json(MOCK_PROGRESS);
  }),
  http.get('/api/v1/deliverables/:id/actions', ({ request }) => {
    lastUrl = request.url;
    lastMethod = request.method;
    return HttpResponse.json(MOCK_ACTIONS);
  }),
  http.post('/api/v1/deliverables/:id/issue', async ({ request }) => {
    lastUrl = request.url;
    lastMethod = request.method;
    lastBody = await request.json();
    return HttpResponse.json({
      deliverable_id: DELIVERABLE_ID,
      version_id: 'v-1',
      rev: '1',
      doc_no: 'CB-001',
      version_purpose: 'ISSUED_FOR_CONSTRUCTION',
      sign_status: 'PENDING',
      issued_at: '2026-10-20T10:00:00Z',
    });
  }),
  http.post('/api/v1/deliverables/:id/sign-step', async ({ request }) => {
    lastUrl = request.url;
    lastMethod = request.method;
    lastBody = await request.json();
    return HttpResponse.json({
      deliverable_id: DELIVERABLE_ID,
      version_id: 'v-1',
      step_index: 1,
      step_role: 'DESIGNER',
      decision: 'SIGN',
      state: 'COMPLETED',
      deliverable_sign_status: 'PENDING',
      signed_at: '2026-10-20T10:00:00Z',
    });
  }),
  http.post('/api/v1/deliverables/:id/customer-approval/proxy', async ({ request }) => {
    lastUrl = request.url;
    lastMethod = request.method;
    lastBody = await request.json();
    return HttpResponse.json({
      deliverable_id: DELIVERABLE_ID,
      version_id: 'v-1',
      attachment_id: 'att-1',
      customer_approver_name: '客户方 张三',
      approval_date: '2026-10-20',
      approval_method: 'EMAIL',
      is_proxy: true,
      proxied_at: '2026-10-20T10:00:00Z',
    });
  }),
  // ⚠️ 单条工作流端点 —— **不得**被聚合端点替代后仍被调用
  http.get('/api/v1/workflow-progress/:type/:id', () => {
    signCalls += 1;
    return HttpResponse.json({ items: [], total: 0 });
  }),
);

describe('deliverablesApi —— 端点形状', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastUrl = '';
    lastMethod = '';
    signCalls = 0;
  });

  it('progress ⇒ GET /deliverables/{id}/progress（**不是** workflow-progress/SIGN/...）', async () => {
    const res = await deliverablesApi.progress(DELIVERABLE_ID);
    expect(lastMethod).toBe('GET');
    expect(lastUrl).toContain(`/deliverables/${DELIVERABLE_ID}/progress`);
    expect(signCalls).toBe(0);
    expect(res.sections).toHaveLength(2);
  });

  it('actions ⇒ GET /deliverables/{id}/actions + 传 limit / offset', async () => {
    const res = await deliverablesApi.actions(DELIVERABLE_ID, { limit: 10, offset: 5 });
    expect(lastMethod).toBe('GET');
    expect(lastUrl).toContain(`/deliverables/${DELIVERABLE_ID}/actions`);
    expect(lastUrl).toContain('limit=10');
    expect(lastUrl).toContain('offset=5');
    expect(res.total).toBe(1);
  });
});

/**
 * 交付物**写面**客户端的端点形状（P9B-2 · T8）。
 *
 * ⚠️ **字段名逐字**（`version_purpose` / `step_index` / `decision` /
 * `file_path` …）—— 改成 camelCase ⇒ FastAPI **静默忽略**（Pydantic 默认
 * 丢弃多余字段）⇒ 前端以为传了、后端没收到 ⇒ 签发出来的是空版本。
 */
describe('deliverablesApi —— 写面端点形状（T8）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastUrl = '';
    lastMethod = '';
    lastBody = null;
  });

  it('issue ⇒ POST /deliverables/{id}/issue + 请求体逐字', async () => {
    const res = await deliverablesApi.issue(DELIVERABLE_ID, {
      version_purpose: 'ISSUED_FOR_CONSTRUCTION',
      description: '第 1 版',
    });

    expect(lastMethod).toBe('POST');
    expect(lastUrl).toContain(`/deliverables/${DELIVERABLE_ID}/issue`);
    expect(lastBody).toEqual({
      version_purpose: 'ISSUED_FOR_CONSTRUCTION',
      description: '第 1 版',
    });
    expect(res.version_id).toBe('v-1');
  });

  it('signStep ⇒ POST /deliverables/{id}/sign-step + 请求体逐字（含 step_index）', async () => {
    const res = await deliverablesApi.signStep(DELIVERABLE_ID, {
      version_id: 'v-1',
      step_index: 2,
      decision: 'RETURN',
      reason: 'P&ID 缺 E-101',
    });

    expect(lastMethod).toBe('POST');
    expect(lastUrl).toContain(`/deliverables/${DELIVERABLE_ID}/sign-step`);
    expect(lastBody).toEqual({
      version_id: 'v-1',
      step_index: 2,
      decision: 'RETURN',
      reason: 'P&ID 缺 E-101',
    });
    expect(res.state).toBe('COMPLETED');
  });

  it('customerApprovalProxy ⇒ POST /deliverables/{id}/customer-approval/proxy + 请求体逐字', async () => {
    const body = {
      version_id: 'v-1',
      file_path: 'approvals/2026/customer.pdf',
      file_name: 'customer.pdf',
      file_type: 'PDF' as const,
      approver_name: '客户方 张三',
      approval_date: '2026-10-20',
      approval_method: 'EMAIL' as const,
      secondary_username: 'zhangsan',
      secondary_password: 's3cret',
    };

    const res = await deliverablesApi.customerApprovalProxy(DELIVERABLE_ID, body);

    expect(lastMethod).toBe('POST');
    expect(lastUrl).toContain(`/deliverables/${DELIVERABLE_ID}/customer-approval/proxy`);
    expect(lastBody).toEqual(body);
    expect(res.is_proxy).toBe(true);
  });
});
