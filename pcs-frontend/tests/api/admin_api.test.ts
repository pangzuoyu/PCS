/**
 * ADMIN 客户端的**方法与路径**（P9B-2 · T3 · SPEC §7.20 / P9A-ADM-001/002）。
 *
 * ## 这组测试抓的是「方法错了」
 *
 * `disableUser` 用 **PUT**（不是 POST）⇒ 写成 POST ⇒ 后端 405 ⇒
 * 症状是「停用按钮点了没反应」，且**不指向**方法错。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { adminApi } from '../../src/api/admin';
import type { components } from '../../src/types/api';

const USER_ID = 'user-1';

let lastUrl = '';
let lastMethod = '';

const MOCK_USER = {
  user_id: USER_ID,
  username: 'zhangsan',
  display_name: '张三',
  email: 'zhangsan@example.com',
  department: '工艺',
  roles: ['DESIGNER'],
  status: 'ACTIVE',
  token_version: 3,
  last_login_at: '2026-10-20T09:00:00Z',
} satisfies components['schemas']['AdminUserOut'];

const MOCK_DISABLED = {
  user_id: USER_ID,
  username: 'zhangsan',
  status: 'DISABLED',
  token_version: 4,
} satisfies components['schemas']['UserDisabledOut'];

const MOCK_SYNC = {
  ok: true,
  created: 1,
  updated: 0,
  departed: 0,
  unmapped: 0,
  skipped_empty: false,
  error: null,
} satisfies components['schemas']['AdSyncResultOut'];

const server = setupServer(
  http.get('/api/v1/admin/users', ({ request }) => {
    lastUrl = request.url;
    lastMethod = request.method;
    return HttpResponse.json([MOCK_USER]);
  }),
  http.put('/api/v1/admin/users/:userId/disable', ({ request }) => {
    lastUrl = request.url;
    lastMethod = request.method;
    return HttpResponse.json(MOCK_DISABLED);
  }),
  http.post('/api/v1/admin/users/sync', ({ request }) => {
    lastUrl = request.url;
    lastMethod = request.method;
    return HttpResponse.json(MOCK_SYNC);
  }),
);

describe('adminApi —— 方法与路径', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    lastUrl = '';
    lastMethod = '';
  });

  it('listUsers ⇒ GET /admin/users', async () => {
    const users = await adminApi.listUsers();
    expect(lastMethod).toBe('GET');
    expect(lastUrl).toContain('/admin/users');
    expect(users).toHaveLength(1);
    expect(users[0].token_version).toBe(3);
  });

  it('⚠️ disableUser ⇒ **PUT** /admin/users/{id}/disable（不是 POST）', async () => {
    const res = await adminApi.disableUser(USER_ID);
    expect(lastMethod).toBe('PUT');
    expect(lastUrl).toContain(`/admin/users/${USER_ID}/disable`);
    expect(res.status).toBe('DISABLED');
    expect(res.token_version).toBe(4);
  });

  it('syncAdUsers ⇒ POST /admin/users/sync', async () => {
    const res = await adminApi.syncAdUsers();
    expect(lastMethod).toBe('POST');
    expect(lastUrl).toContain('/admin/users/sync');
    expect(res.ok).toBe(true);
  });
});
