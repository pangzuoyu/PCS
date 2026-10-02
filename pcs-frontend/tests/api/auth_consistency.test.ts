/**
 * Auth consistency 端到端测试 (P7-7+ actor 上下文).
 *
 * 验证 mock-login → /auth/me → setSession 全链路, 前后端 user_id 必须一致:
 * - mock-login response 含 user_id
 * - /auth/me 返回相同 user_id (dev-mode MOCK_USER_IDS)
 * - Bearer token + Authorization header 始终正确发送
 */

import { describe, it, expect, beforeAll, afterEach, afterAll } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { authApi } from '../../src/api/client';
import { useAuth } from '../../src/store/auth';

const MOCK_USER_IDS: Record<string, string> = {
  alice: '00000000-0000-0000-0000-0000000a11ce',
  bob: '00000000-0000-0000-0000-0000000b0b01',
};

const mockTokens = {
  alice: { access_token: 'mock-token-alice', refresh_token: 'mock-refresh-alice' },
  bob: { access_token: 'mock-token-bob', refresh_token: 'mock-refresh-bob' },
};

let lastMeAuth: string | null = null;
let lastMockLoginAuth: string | null = null;

const handlers = [
  http.post('/api/v1/auth/mock-login', async ({ request }) => {
    lastMockLoginAuth = request.headers.get('Authorization');
    const body = (await request.json()) as { username?: string };
    const username = body.username ?? 'alice';
    return HttpResponse.json({
      access_token: mockTokens[username as keyof typeof mockTokens]?.access_token,
      refresh_token: mockTokens[username as keyof typeof mockTokens]?.refresh_token,
      token_type: 'bearer',
      role: 'DESIGNER',
      username,
      user_id: MOCK_USER_IDS[username],
    });
  }),
  http.get('/api/v1/auth/me', ({ request }) => {
    lastMeAuth = request.headers.get('Authorization');
    return HttpResponse.json({
      username: 'alice',
      role: 'DESIGNER',
      user_id: MOCK_USER_IDS.alice,
    });
  }),
];

const server = setupServer(...handlers);

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});
afterEach(() => {
  server.resetHandlers();
  useAuth.getState().clearSession();
  lastMeAuth = null;
  lastMockLoginAuth = null;
});
afterAll(() => {
  server.close();
});

describe('Auth flow actor context consistency (P7-7+ 全栈覆盖)', () => {
  it('mock-login 返回 user_id + role + username', async () => {
    const tokens = await authApi.mockLogin('alice');
    expect(tokens.username).toBe('alice');
    expect(tokens.role).toBe('DESIGNER');
    expect(tokens.access_token).toBe('mock-token-alice');
    // MockLoginResponse 应该含 user_id (P7-7+ actor 上下文)
    expect((tokens as unknown as { user_id?: string }).user_id).toBe(
      MOCK_USER_IDS.alice,
    );
  });

  it('/auth/me 返回权威 user_id (JWT 派生, 与后端一致)', async () => {
    const me = await authApi.me();
    expect(me.username).toBe('alice');
    expect(me.role).toBe('DESIGNER');
    expect(me.user_id).toBe(MOCK_USER_IDS.alice);
  });

  it('所有 auth 调用携带 Bearer token (Authorization header 正确发送)', async () => {
    useAuth.getState().setSession({
      access_token: 'mock-token-alice',
      refresh_token: 'mock-refresh-alice',
      username: 'alice',
      role: 'DESIGNER',
      user_id: MOCK_USER_IDS.alice,
    });

    await authApi.me();
    // axios 请求拦截器自动注入 Bearer token
    expect(lastMeAuth).toBe(`Bearer mock-token-alice`);
  });

  it('LoginPage setSession 后, useAuth.userId 与 backend actor.user_id 一致 (UUID 字节级匹配)', async () => {
    // 1. mockLogin 拿 token
    const tokens = await authApi.mockLogin('alice');
    // 2. /auth/me 拿权威 user_id
    const me = await authApi.me();
    // 3. setSession 写入 zustand
    useAuth.getState().setSession({
      ...tokens,
      user_id: me.user_id,
    });

    const state = useAuth.getState();
    // 4. 前后端 user_id 一致 (P7-7+ 关键不变量, 否则 endpoint guard 404)
    expect(state.userId).toBe(MOCK_USER_IDS.alice);
    expect(state.userId).toBe(me.user_id);
    expect(state.username).toBe('alice');
    expect(state.role).toBe('DESIGNER');
    expect(state.accessToken).toBe('mock-token-alice');
  });

  it('clearSession 后 useAuth.userId 清空, 后续请求应不带 Bearer token', async () => {
    useAuth.getState().setSession({
      access_token: 'mock-token-alice',
      refresh_token: 'mock-refresh-alice',
      username: 'alice',
      role: 'DESIGNER',
      user_id: MOCK_USER_IDS.alice,
    });
    expect(useAuth.getState().userId).toBe(MOCK_USER_IDS.alice);

    useAuth.getState().clearSession();
    expect(useAuth.getState().userId).toBeNull();
    expect(useAuth.getState().accessToken).toBeNull();

    // 后续请求不带 Authorization header (axios interceptor 跳过)
    await authApi.me();
    expect(lastMeAuth).toBeNull();
  });
});