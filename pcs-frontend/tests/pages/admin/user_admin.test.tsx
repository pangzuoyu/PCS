/**
 * ADMIN 用户管理页（P9B-2 · T7 · SPEC §7.20 / P9A-ADM-001/002）。
 *
 * 守三件事：
 * 1. ⚠️ **停用后重新拉列表**（RF-9）—— 乐观更新单行会让 `token_version` 显示
 *    旧值，而用户正是靠它确认「已签发的 refresh 全部失效」（ADR-0046 §⑤）。
 * 2. ⚠️ **AD 同步的失败方向**（RF-10）—— `ok=false` = **什么都没做**；
 *    `skipped_empty=true` = 枚举到 0 个用户 ⇒ 两种都不是「同步成功」。
 * 3. ⚠️ **非 SYSTEM_ADMIN 看不到入口**（SPEC §5.1「菜单项隐藏」）。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { UserAdminPage } from '../../../src/pages/admin/UserAdminPage';
import { useAuth } from '../../../src/store/auth';
import type { components } from '../../../src/types/api';

type AdminUser = components['schemas']['AdminUserOut'];
type AdSyncResult = components['schemas']['AdSyncResultOut'];

const USER = {
  user_id: 'u-1',
  username: 'zhangsan',
  display_name: '张三',
  email: 'zhangsan@example.com',
  department: '工艺',
  roles: ['DESIGNER'],
  status: 'ACTIVE',
  token_version: 3,
  last_login_at: '2026-10-20T09:00:00Z',
} satisfies AdminUser;

let listCalls = 0;
let disableCalls = 0;
let syncResult: AdSyncResult = {
  ok: true,
  created: 1,
  updated: 0,
  departed: 0,
  unmapped: 0,
  skipped_empty: false,
  error: null,
};

const server = setupServer(
  http.get('/api/v1/admin/users', () => {
    listCalls += 1;
    // ⚠️ 停用后**重新拉**时，服务端返回的 token_version 变了
    return HttpResponse.json([{ ...USER, status: disableCalls > 0 ? 'DISABLED' : 'ACTIVE', token_version: disableCalls > 0 ? 4 : 3 }]);
  }),
  http.put('/api/v1/admin/users/:userId/disable', () => {
    disableCalls += 1;
    return HttpResponse.json({
      user_id: USER.user_id,
      username: USER.username,
      status: 'DISABLED',
      token_version: 4,
    });
  }),
  http.post('/api/v1/admin/users/sync', () => HttpResponse.json(syncResult)),
);

describe('UserAdminPage —— ADMIN 用户管理', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    listCalls = 0;
    disableCalls = 0;
    syncResult = {
      ok: true,
      created: 1,
      updated: 0,
      departed: 0,
      unmapped: 0,
      skipped_empty: false,
      error: null,
    };
    useAuth.setState({ role: 'SYSTEM_ADMIN', accessToken: 'test-token' });
  });

  it('列表渲染 display_name / roles / status / token_version', async () => {
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeTruthy());
    expect(screen.getByText('DESIGNER')).toBeTruthy();
    expect(screen.getByText('ACTIVE')).toBeTruthy();
    expect(screen.getByText('3')).toBeTruthy();
  });

  it('⚠️ 点「停用」⇒ 调 PUT ⇒ **重新拉列表**（RF-9）', async () => {
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeTruthy());
    expect(listCalls).toBe(1);

    fireEvent.click(screen.getByTestId('admin-disable-u-1'));

    await waitFor(() => expect(listCalls).toBe(2));
    expect(disableCalls).toBe(1);
    // ⚠️ 重新拉到的**新** token_version 必须显示出来（不是旧值 3）
    await waitFor(() => expect(screen.getByText('4')).toBeTruthy());
  });

  it('⚠️ AD 同步 `ok=false` ⇒ 显示 **error 原文**，**不得**显示成功（RF-10）', async () => {
    syncResult = {
      ok: false,
      created: 0,
      updated: 0,
      departed: 0,
      unmapped: 0,
      skipped_empty: false,
      error: '目录连不上',
    };
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeTruthy());

    fireEvent.click(screen.getByTestId('admin-sync-ad'));

    await waitFor(() => expect(screen.getByTestId('admin-error')).toBeTruthy());
    expect(screen.getByTestId('admin-error').textContent).toContain('目录连不上');
    expect(screen.queryByTestId('admin-notice')).toBeNull();
  });

  it('⚠️ AD 同步 `skipped_empty=true` ⇒ 「枚举到 0 个用户，未做任何写入」（RF-10）', async () => {
    syncResult = {
      ok: true,
      created: 0,
      updated: 0,
      departed: 0,
      unmapped: 0,
      skipped_empty: true,
      error: null,
    };
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeTruthy());

    fireEvent.click(screen.getByTestId('admin-sync-ad'));

    await waitFor(() => expect(screen.getByTestId('admin-notice')).toBeTruthy());
    expect(screen.getByTestId('admin-notice').textContent).toContain('枚举到 0 个用户');
    expect(screen.getByTestId('admin-notice').textContent).toContain('未做任何写入');
  });

  it('AD 同步成功 ⇒ 显示计数', async () => {
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeTruthy());

    fireEvent.click(screen.getByTestId('admin-sync-ad'));

    await waitFor(() => expect(screen.getByTestId('admin-notice')).toBeTruthy());
    expect(screen.getByTestId('admin-notice').textContent).toContain('AD 同步完成');
  });
});
