/**
 * 401「会话结束码」白名单（P9B-4 评审 #1）。
 *
 * ## 为什么有这个测试
 *
 * T0-B 把账号状态判定移到 **actor 层**（后端每次请求查 `users.status`）⇒
 * 账号被停用后，**在手 access token 的下一次请求**就得到
 * `401` + body 带 `code="USER_DISABLED"`。
 *
 * 而前端的 axios 拦截器只在两种情况下清 session + 跳登录页：
 * ① 响应**没有** `code`（旧行为：不知道是什么 401 ⇒ 当会话过期处理）；
 * ② `code` 在 `SESSION_OVER_CODES` 白名单里。
 *
 * ⇒ `USER_DISABLED` 曾经**不在**白名单 ⇒ 停用用户带着在手 token 卡在任意业务页，
 * 之后每个请求都 401，页面只剩通用错误提示，**永远回不到登录页**，
 * 也永远不知道自己被停用了。
 *
 * ⚠️ SPEC §7.1（V2.12，**本批新增**）白纸黑字写着「前端按**普通 401** 处理
 * （跳登录页）」⇒ 实现与自家 SPEC 冲突 ⇒ 本测试把 SPEC 那句话钉成可执行断言。
 *
 * ⚠️ 同时守住**不该登出**的那一类：代录客户批准的**二次认证**失败
 * （`SECONDARY_AUTH_FAILED`）也是 401 ⇒ 一律登出会把用户填好的凭证全丢
 * ⇒ 只有**会话码**才清 session。
 */

import { describe, it, expect, beforeAll, afterEach, afterAll, vi } from 'vitest';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { api } from '../../src/api/client';
import { useAuth } from '../../src/store/auth';

/** 本次要返回的 401 body（`undefined` ⇒ 不带 code 字段）。 */
let nextBody: Record<string, string> | undefined;

const server = setupServer(
  http.get('/api/v1/probe-401', () =>
    nextBody
      ? HttpResponse.json(nextBody, { status: 401 })
      : HttpResponse.json({ message: 'no code here' }, { status: 401 }),
  ),
);

beforeAll(() => {
  server.listen({ onUnhandledRequest: 'error' });
});

afterEach(() => {
  server.resetHandlers();
  useAuth.getState().clearSession();
  vi.unstubAllGlobals();
  nextBody = undefined;
});

afterAll(() => {
  server.close();
});

/**
 * 桩掉 `window.location`（jsdom 的 location 是 unforgeable ⇒ 只能整体替换）。
 *
 * ⚠️ **`href` 必须是合法绝对 URL** —— axios 用 `window.location.href` 解析相对
 * URL（`baseURL = '/api/v1'`）⇒ 桩成 '/sim/streams' 会让请求在发出前就抛
 * `Invalid base URL`（实测踩过）⇒ 401 根本到不了拦截器。
 */
function stubLocation(pathname: string): { pathname: string; href: string } {
  const loc = {
    pathname,
    href: `http://localhost:5173${pathname}`,
  };
  vi.stubGlobal('location', loc);
  return loc;
}

/** 塞一个已登录会话（拦截器据此带 Bearer）。 */
function login(): void {
  useAuth.getState().setSession({
    access_token: 'token-alice',
    refresh_token: 'refresh-alice',
    username: 'alice',
    role: 'DESIGNER',
    user_id: '00000000-0000-0000-0000-0000000a11ce',
  });
}

/** 触发一次 401（吞掉 rejection，只看副作用）。 */
async function trigger401(): Promise<void> {
  await api.get('/probe-401').catch(() => undefined);
}

describe('401 会话结束码白名单（评审 #1）', () => {
  it('401 USER_DISABLED ⇒ 清 session + 跳登录页（停用立即生效）', async () => {
    login();
    expect(useAuth.getState().accessToken).toBe('token-alice');

    // ⚠️ 停在业务页（不是 /login）⇒ 拦截器应当跳转到 /login
    const loc = stubLocation('/sim/streams');

    nextBody = { code: 'USER_DISABLED', message: 'user account is disabled: alice' };
    await trigger401();

    // ⚠️ 会话必须被清掉（**这是**「停用立即生效」在前端的落点）
    expect(useAuth.getState().accessToken).toBeNull();
    expect(useAuth.getState().userId).toBeNull();
    // ⚠️ 且必须跳回登录页（SPEC §7.1 V2.12 的承诺）
    expect(loc.href).toBe('/login');
  });

  it('401 USER_DISABLED 即使当前已在 /login 也不重复跳转（仍清 session）', async () => {
    login();
    const loc = stubLocation('/login');

    nextBody = { code: 'USER_DISABLED' };
    await trigger401();

    expect(useAuth.getState().accessToken).toBeNull();
    // ⚠️ 已经在登录页 ⇒ 不该再跳（否则登录页会被反复重定向）
    //    ⇒ href 保持**初始值**，未被改写成 '/login'
    expect(loc.href).toBe('http://localhost:5173/login');
  });

  it('401 二次认证失败 SECONDARY_AUTH_FAILED ⇒ **不清 session**（既有行为不许回归）', async () => {
    login();
    const loc = stubLocation('/sim/streams');

    nextBody = { code: 'SECONDARY_AUTH_FAILED', message: '客户批准人密码错误' };
    await trigger401();

    // ⚠️ 这不是会话结束 ⇒ 用户填好的凭证不能被踢掉
    expect(useAuth.getState().accessToken).toBe('token-alice');
    expect(loc.href).toBe('http://localhost:5173/sim/streams');
  });

  it('401 没有 code ⇒ 清 session（旧行为：不知道是什么 401 ⇒ 当会话过期处理）', async () => {
    login();
    const loc = stubLocation('/sim/streams');

    await trigger401();

    expect(useAuth.getState().accessToken).toBeNull();
    expect(loc.href).toBe('/login');
  });

  it('401 REFRESH_REVOKED ⇒ 清 session（ADR-0046 §5 的 tv 闸，同形状缺口）', async () => {
    login();
    const loc = stubLocation('/sim/streams');

    nextBody = { code: 'REFRESH_REVOKED' };
    await trigger401();

    expect(useAuth.getState().accessToken).toBeNull();
    expect(loc.href).toBe('/login');
  });
});
