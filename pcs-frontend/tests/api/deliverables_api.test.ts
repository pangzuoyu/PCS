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
