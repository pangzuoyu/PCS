/**
 * 记录级写面客户端的**请求契约**（P9B-2 · T3 · SPEC §6.3 / §7.19.1）。
 *
 * ## 这组测试抓的是「字段名漂移」
 *
 * `decision` 改名成 `approve` / `reason` 改名成 `comment` ⇒ **TypeScript 不报错**
 * ⇒ 后端 422 ⇒ 症状是「按钮点了没反应」。⇒ 只能靠**断言请求体**抓。
 *
 * ⚠️ **R-17（契约破坏性变更）**：`submitApproval` **不再**传
 * `approval_role` / `approval_depth`（批准链由后端从项目 `RECORD` 矩阵推导）
 * ⇒ 这条断言专门盯住「前端又把角色传回去了」。
 *
 * 断言方式：MSW node server 拦真实请求，把 body 捕获进闭包变量。
 * ⚠️ **不要 mock api 模块**：那会把这组测试变成「测 mock 的行为」。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { commentsApi, recordActionsApi } from '../../src/api/recordActions';
import type { components } from '../../src/types/api';

const RECORD_ID = '11111111-2222-3333-4444-555555555555';
const MODULE = 'cooling_tower_result';

let lastBody: unknown = null;
let lastUrl = '';
let lastMethod = '';

const MOCK_ACTION = {
  record_type: MODULE,
  record_id: RECORD_ID,
  from_status: 'DRAFT',
  to_status: 'OBSOLETE',
} satisfies components['schemas']['RecordActionResponse'];

const MOCK_SUBMIT = {
  record_type: MODULE,
  record_id: RECORD_ID,
  from_status: 'DRAFT',
  to_status: 'IN_APPROVAL',
  approval_step: 1,
  approval_depth: 3,
  approval_role: 'CHECKER',
} satisfies components['schemas']['SubmitApprovalResponse'];

const MOCK_STEP = {
  record_type: MODULE,
  record_id: RECORD_ID,
  from_status: 'IN_APPROVAL',
  to_status: 'IN_APPROVAL',
  approval_step: 2,
  approval_depth: 3,
} satisfies components['schemas']['ApprovalStepResponse'];

const MOCK_COMMENT = {
  comment_id: 'c-1',
  record_type: MODULE,
  record_id: RECORD_ID,
  body: '这里的数据要再核对一遍',
  author_id: 'u-1',
  created_at: '2026-10-20T10:00:00Z',
} satisfies components['schemas']['CommentResponse'];

const server = setupServer(
  http.post('/api/v1/records/:module/:recordId/:action', async ({ request, params }) => {
    lastBody = await request.json();
    lastUrl = request.url;
    lastMethod = request.method;
    if (params['action'] === 'submit-approval') return HttpResponse.json(MOCK_SUBMIT);
    if (params['action'] === 'approval-step') return HttpResponse.json(MOCK_STEP);
    return HttpResponse.json(MOCK_ACTION);
  }),
  http.get('/api/v1/records/:module/:recordId/comments', ({ request }) => {
    lastUrl = request.url;
    lastMethod = request.method;
    return HttpResponse.json({ items: [MOCK_COMMENT], total: 1 });
  }),
  http.post('/api/v1/records/:module/:recordId/comments', async ({ request }) => {
    lastBody = await request.json();
    lastUrl = request.url;
    lastMethod = request.method;
    return HttpResponse.json(MOCK_COMMENT);
  }),
);

describe('recordActionsApi —— 请求体逐字断言', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    lastUrl = '';
    lastMethod = '';
  });

  it('obsolete ⇒ {reason}', async () => {
    await recordActionsApi.obsolete(MODULE, RECORD_ID, '数据过期');
    expect(lastMethod).toBe('POST');
    expect(lastUrl).toContain(`/records/${MODULE}/${RECORD_ID}/obsolete`);
    expect(lastBody).toEqual({ reason: '数据过期' });
  });

  it('requestReversal ⇒ {reason}', async () => {
    await recordActionsApi.requestReversal(MODULE, RECORD_ID, '撤销申请');
    expect(lastUrl).toContain('/request-reversal');
    expect(lastBody).toEqual({ reason: '撤销申请' });
  });

  it('reversalDecision ⇒ {decision, reason}', async () => {
    await recordActionsApi.reversalDecision(MODULE, RECORD_ID, 'APPROVE', '同意撤销');
    expect(lastUrl).toContain('/reversal-decision');
    expect(lastBody).toEqual({ decision: 'APPROVE', reason: '同意撤销' });
  });

  it('abandonChange ⇒ {reason}', async () => {
    await recordActionsApi.abandonChange(MODULE, RECORD_ID, '上游撤销了变更');
    expect(lastUrl).toContain('/abandon-change');
    expect(lastBody).toEqual({ reason: '上游撤销了变更' });
  });

  it('approvalStep ⇒ {decision, reason}', async () => {
    await recordActionsApi.approvalStep(MODULE, RECORD_ID, 'REJECT', '数据有问题');
    expect(lastUrl).toContain('/approval-step');
    expect(lastBody).toEqual({ decision: 'REJECT', reason: '数据有问题' });
  });

  it('⚠️ R-17：submitApproval **只传** {reason?} —— 不得再传 approval_role / approval_depth', async () => {
    await recordActionsApi.submitApproval(MODULE, RECORD_ID, '初版请审');
    expect(lastUrl).toContain('/submit-approval');
    expect(lastBody).toEqual({ reason: '初版请审' });
    // ⚠️ 显式断「没有这两个键」—— `toEqual` 已断，但这条把**意图**写进用例
    expect(Object.keys(lastBody as object)).not.toContain('approval_role');
    expect(Object.keys(lastBody as object)).not.toContain('approval_depth');
  });

  it('submitApproval 不传 reason ⇒ 请求体是 {}（不是 {reason: undefined} 之外的东西）', async () => {
    await recordActionsApi.submitApproval(MODULE, RECORD_ID);
    expect(lastBody).toEqual({ reason: undefined });
    expect(Object.keys(lastBody as object)).not.toContain('approval_role');
  });
});

describe('commentsApi —— 批注', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastBody = null;
    lastUrl = '';
    lastMethod = '';
  });

  it('create ⇒ {body}', async () => {
    await commentsApi.create(MODULE, RECORD_ID, '这里的数据要再核对一遍');
    expect(lastMethod).toBe('POST');
    expect(lastUrl).toContain(`/records/${MODULE}/${RECORD_ID}/comments`);
    expect(lastBody).toEqual({ body: '这里的数据要再核对一遍' });
  });

  it('list ⇒ 传 limit / offset', async () => {
    await commentsApi.list(MODULE, RECORD_ID, { limit: 20, offset: 40 });
    expect(lastMethod).toBe('GET');
    expect(lastUrl).toContain('limit=20');
    expect(lastUrl).toContain('offset=40');
  });
});
