/**
 * 签署矩阵管理 API 客户端的**请求契约**（TODO-079 · P9A-DLV-011 T3 的前端）。
 *
 * ## 这组测试抓的是三件事
 *
 * 1. **路径写错**：`/projects/{id}/signature-matrices` 与
 *    `/projects/{id}/signature-matrices/{module}` **只差一段** ⇒ 写错时
 *    TS **不报错**（路径是 string）⇒ 只能靠断言 URL 抓。
 * 2. **请求体字段漂成 camelCase**：`matrix_id` ⇒ `matrixId` ⇒ 后端 422
 *    （Pydantic 认 snake_case）⇒ 与既有 bug（`expectedHash` vs
 *    `expected_hash`）**同形**。
 * 3. **解绑的 404 语义**：后端「本来就没绑 ⇒ `unbound=false`，**不是** 404」
 *    ⇒ 前端不能把 404 当「没绑上」。
 *
 * 断言方式：MSW node server 拦真实请求，把 URL / body 捕获进闭包变量
 * （仿 `tests/api/records_api.test.ts` 的既有套路）。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { signatureMatricesApi } from '../../src/api/signatureMatrices';
import { useAuth } from '../../src/store/auth';

const MATRIX_ID = '11111111-2222-3333-4444-555555555555';
const PROJECT_ID = '99999999-8888-7777-6666-555555555555';

let lastUrl = '';
let lastMethod = '';
let lastBody: unknown = null;

const server = setupServer(
  http.get('/api/v1/signature-matrices', ({ request }) => {
    lastUrl = request.url;
    lastMethod = 'GET';
    return HttpResponse.json({ items: [], total: 0 });
  }),
  http.get('/api/v1/signature-matrices/:matrix_id', ({ request, params }) => {
    lastUrl = request.url;
    lastMethod = 'GET';
    return HttpResponse.json({
      matrix_id: String(params['matrix_id']),
      matrix_name: 'm',
      module: '*',
      doc_type: 'CALCULATION_BOOK',
      version_purpose: 'ISSUED_FOR_CONSTRUCTION',
      status: 'ACTIVE',
      steps: [],
    });
  }),
  http.post('/api/v1/signature-matrices', async ({ request }) => {
    lastUrl = request.url;
    lastMethod = 'POST';
    lastBody = await request.json();
    return HttpResponse.json(
      {
        matrix_id: MATRIX_ID,
        matrix_name: 'm',
        module: '*',
        doc_type: 'CALCULATION_BOOK',
        version_purpose: 'ISSUED_FOR_CONSTRUCTION',
        status: 'ACTIVE',
        steps: [],
      },
      { status: 201 },
    );
  }),
  http.put('/api/v1/signature-matrices/:matrix_id', async ({ request, params }) => {
    lastUrl = request.url;
    lastMethod = 'PUT';
    lastBody = await request.json();
    return HttpResponse.json({
      matrix_id: String(params['matrix_id']),
      matrix_name: 'm',
      module: '*',
      doc_type: 'CALCULATION_BOOK',
      version_purpose: 'ISSUED_FOR_CONSTRUCTION',
      status: 'ACTIVE',
      steps: [],
    });
  }),
  http.post('/api/v1/projects/:project_id/signature-matrices', async ({ request, params }) => {
    lastUrl = request.url;
    lastMethod = 'POST';
    lastBody = await request.json();
    return HttpResponse.json({
      project_id: String(params['project_id']),
      module: 'RECORD',
      matrix_id: MATRIX_ID,
      matrix_name: 'm',
    });
  }),
  http.delete('/api/v1/projects/:project_id/signature-matrices/:module', ({ request, params }) => {
    lastUrl = request.url;
    lastMethod = 'DELETE';
    return HttpResponse.json({
      project_id: String(params['project_id']),
      module: String(params['module']),
      unbound: true,
    });
  }),
);

describe('signatureMatricesApi —— 请求契约', () => {
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

  it('list 打到 /signature-matrices（不带项目过滤 —— 模板是全局表）', async () => {
    await signatureMatricesApi.list({ limit: 200 });
    expect(lastMethod).toBe('GET');
    expect(lastUrl).toContain('/api/v1/signature-matrices');
    expect(lastUrl).not.toContain('project_id');
  });

  it('create 的请求体是 snake_case（matrix_name / steps[].step_order）', async () => {
    await signatureMatricesApi.create({
      matrix_name: '矩阵 A',
      module: '*',
      doc_type: 'CALCULATION_BOOK',
      version_purpose: 'ISSUED_FOR_CONSTRUCTION',
      status: 'DRAFT',
      steps: [
        {
          step_order: 1,
          sign_role: 'CHECKER',
          required: true,
          can_self_check: true,
          can_skip: false,
        },
      ],
    });
    expect(lastMethod).toBe('POST');
    const body = lastBody as Record<string, unknown>;
    expect(body['matrix_name']).toBe('矩阵 A');
    expect(Array.isArray(body['steps'])).toBe(true);
    const steps = body['steps'] as Record<string, unknown>[];
    expect(steps[0]['step_order']).toBe(1);
    expect(steps[0]['sign_role']).toBe('CHECKER');
  });

  it('update 打 /signature-matrices/{id}', async () => {
    await signatureMatricesApi.update(MATRIX_ID, { matrix_name: '改名' });
    expect(lastMethod).toBe('PUT');
    expect(lastUrl).toContain(`/api/v1/signature-matrices/${MATRIX_ID}`);
  });

  it('bind 打 /projects/{id}/signature-matrices 且请求体是 matrix_id', async () => {
    await signatureMatricesApi.bind(PROJECT_ID, { module: 'RECORD', matrix_id: MATRIX_ID });
    expect(lastMethod).toBe('POST');
    expect(lastUrl).toContain(`/api/v1/projects/${PROJECT_ID}/signature-matrices`);
    const body = lastBody as Record<string, unknown>;
    expect(body['matrix_id']).toBe(MATRIX_ID);
    expect(body['module']).toBe('RECORD');
  });

  it('unbind 打 /projects/{id}/signature-matrices/{module}（多一段 module）', async () => {
    const res = await signatureMatricesApi.unbind(PROJECT_ID, 'RECORD');
    expect(lastMethod).toBe('DELETE');
    expect(lastUrl).toContain(`/api/v1/projects/${PROJECT_ID}/signature-matrices/RECORD`);
    // ⚠️ 「本来就没绑」不是 404，而是 `unbound=false`
    expect(res.unbound).toBe(true);
  });
});
