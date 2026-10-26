/**
 * 变更单闭环 API 客户端的**请求契约**（TODO-083 · P9A-DLV-011 T4 的前端）。
 *
 * ## 这组测试抓的是三件事
 *
 * 1. **三个端点的路径**（`initiate-change` / `apply-change` / `change-notice`）
 *    —— 写错时 TS **不报错**（路径是 string）⇒ 只能靠断言 URL 抓。
 * 2. **请求体是 `reason` 而不是别的**（`ObsoleteRequest` 复用 ⇒ 只有
 *    `reason` 一个字段）⇒ 多传字段后端会拒。
 * 3. **建变更单的 body 是 `change_type` / `reason` / `triggered_by`**（snake_case）
 *    ⇒ 漂成 camelCase ⇒ 后端 422。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { changeNoticesApi } from '../../src/api/changeNotices';
import { useAuth } from '../../src/store/auth';

const RECORD_TYPE = 'CostEstResult';
const RECORD_ID = '11111111-2222-3333-4444-555555555555';

let lastUrl = '';
let lastMethod = '';
let lastBody: unknown = null;

const server = setupServer(
  http.post('/api/v1/records/:record_type/:record_id/initiate-change', async ({ request, params }) => {
    lastUrl = request.url;
    lastMethod = 'POST';
    lastBody = await request.json();
    return HttpResponse.json({
      record_type: String(params['record_type']),
      record_id: String(params['record_id']),
      from_status: 'CHECKED',
      to_status: 'CHANGE_PENDING',
    });
  }),
  http.post('/api/v1/records/:record_type/:record_id/apply-change', async ({ request, params }) => {
    lastUrl = request.url;
    lastMethod = 'POST';
    lastBody = await request.json();
    return HttpResponse.json({
      record_type: String(params['record_type']),
      record_id: String(params['record_id']),
      from_status: 'CHANGE_PENDING',
      to_status: 'CHANGED',
    });
  }),
  http.post('/api/v1/records/:record_type/:record_id/change-notice', async ({ request, params }) => {
    lastUrl = request.url;
    lastMethod = 'POST';
    lastBody = await request.json();
    return HttpResponse.json({
      deliverable_id: 'd-1',
      version_id: 'v-1',
      workflow_id: 'd-1',
      matrix_id: 'm-1',
      project_id: 'p-1',
      doc_no: 'CN-0001',
      title: '变更单',
      sign_status: 'PENDING',
      detail: {
        detail_id: 'cnd-1',
        change_type: 'DATA_CORRECTION',
        reason: '管径修正',
        triggered_by: 'MANUAL',
        source_record_type: String(params['record_type']),
      },
    });
  }),
);

describe('changeNoticesApi —— 请求契约', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastUrl = '';
    lastMethod = '';
    lastBody = null;
    useAuth.getState().setSession({
      access_token: 'test-token',
      refresh_token: 'r',
      username: 'u',
      role: 'DESIGNER',
      user_id: 'u',
    });
  });

  it('initiate 打 /records/{type}/{id}/initiate-change，body 只有 reason', async () => {
    const res = await changeNoticesApi.initiate(RECORD_TYPE, RECORD_ID, '要改管径');
    expect(lastMethod).toBe('POST');
    expect(lastUrl).toContain(`/api/v1/records/${RECORD_TYPE}/${RECORD_ID}/initiate-change`);
    expect(lastBody).toEqual({ reason: '要改管径' });
    expect(res.to_status).toBe('CHANGE_PENDING');
  });

  it('apply 打 /records/{type}/{id}/apply-change', async () => {
    const res = await changeNoticesApi.apply(RECORD_TYPE, RECORD_ID, '改完了');
    expect(lastUrl).toContain(`/api/v1/records/${RECORD_TYPE}/${RECORD_ID}/apply-change`);
    expect(lastBody).toEqual({ reason: '改完了' });
    expect(res.to_status).toBe('CHANGED');
  });

  it('create 打 /records/{type}/{id}/change-notice，body 是 change_type/reason/triggered_by', async () => {
    const res = await changeNoticesApi.create(RECORD_TYPE, RECORD_ID, {
      change_type: 'DATA_CORRECTION',
      reason: '管径修正',
      triggered_by: 'MANUAL',
    });
    expect(lastUrl).toContain(`/api/v1/records/${RECORD_TYPE}/${RECORD_ID}/change-notice`);
    expect(lastBody).toEqual({
      change_type: 'DATA_CORRECTION',
      reason: '管径修正',
      triggered_by: 'MANUAL',
    });
    expect(res.doc_no).toBe('CN-0001');
  });
});
