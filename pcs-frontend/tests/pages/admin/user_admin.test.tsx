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
/** 403 ⇒ 模拟「无权查看」；200 ⇒ 正常。 */
let listStatus = 200;
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
    if (listStatus === 403) {
      return HttpResponse.json(
        {
          code: 'HTTP_403',
          message: "需要角色 ['SYSTEM_ADMIN']",
          detail: null,
          trace_id: 't-403',
        },
        { status: 403 },
      );
    }
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
    listStatus = 200;
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

  it('⚠️ 列表显示 email / department / last_login_at（后端已返回，前端没展示）', async () => {
    // ⚠️ `AdminUserOut` **本来就带** email / department / last_login_at
    //    ⇒ 运营看不到邮箱 = 找不到「这个人是谁」⇒ 列表形同虚设。
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeTruthy());
    expect(screen.getByText('zhangsan@example.com')).toBeTruthy();
    expect(screen.getByText('工艺')).toBeTruthy();
    expect(screen.getByText('2026-10-20 09:00 UTC')).toBeTruthy();
  });

  it('⚠️ 403（无权）⇒ 错误提示**不可关闭** + **不渲染空表**', async () => {
    // ⚠️ 此前错误 Alert **可关闭** ⇒ 关掉就退化成「用户（0）」的**空表**
    //    ⇒ 管理员读成「系统里一个用户都没有」⇒ 真相是「你没权限」（RF-12）。
    listStatus = 403;
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByTestId('admin-error')).toBeTruthy());
    expect(screen.getByTestId('admin-error').textContent).toContain('无权');
    expect(document.querySelector('.ant-alert-close-icon')).toBeNull();
    expect(document.querySelector('.ant-table')).toBeNull();
  });

  it('⚠️ 停用**要二次确认**（未确认 ⇒ **不调 PUT**）', async () => {
    // ⚠️ 停用会**递增 token_version** ⇒ 在手 refresh 全部失效 ⇒ 误点即误伤。
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeTruthy());

    fireEvent.click(screen.getByTestId('admin-disable-u-1'));

    await waitFor(() => expect(screen.getByTestId('admin-disable-confirm')).toBeTruthy());
    // ⚠️ 确认框里要点名**谁**被停用 + 说清后果
    const modalText = screen.getByTestId('admin-disable-confirm').textContent ?? '';
    expect(modalText).toContain('zhangsan');
    expect(modalText).toContain('refresh');
    // ⚠️ **未确认 ⇒ 一个 PUT 都不发**
    expect(disableCalls).toBe(0);
    expect(listCalls).toBe(1);
  });

  it('⚠️ 点「停用」⇒ 二次确认 ⇒ 调 PUT ⇒ **重新拉列表**（RF-9）', async () => {
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeTruthy());
    expect(listCalls).toBe(1);

    fireEvent.click(screen.getByTestId('admin-disable-u-1'));
    await waitFor(() => expect(screen.getByTestId('admin-disable-confirm-ok')).toBeTruthy());
    fireEvent.click(screen.getByTestId('admin-disable-confirm-ok'));

    await waitFor(() => expect(listCalls).toBe(2));
    expect(disableCalls).toBe(1);
    // ⚠️ 重新拉到的**新** token_version 必须显示出来（不是旧值 3）
    await waitFor(() => expect(screen.getByText('4')).toBeTruthy());
  });

  it('⚠️ 二次确认**取消** ⇒ 不调 PUT', async () => {
    render(<UserAdminPage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeTruthy());

    fireEvent.click(screen.getByTestId('admin-disable-u-1'));
    await waitFor(() => expect(screen.getByTestId('admin-disable-confirm-cancel')).toBeTruthy());
    fireEvent.click(screen.getByTestId('admin-disable-confirm-cancel'));

    await waitFor(() => expect(screen.queryByTestId('admin-disable-confirm')).toBeNull());
    expect(disableCalls).toBe(0);
    expect(listCalls).toBe(1);
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

  it('⚠️ AD 同步 `skipped_empty=true` ⇒ **不是绿色成功条**（什么都没写入）', async () => {
    // ⚠️ 绿色 success 条 = 「成功」⇒ 用户以为同步过了 ⇒ 真相是「**一个都没写**」。
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
    const cls = screen.getByTestId('admin-notice').className;
    expect(cls).toContain('ant-alert-warning');
    expect(cls).not.toContain('ant-alert-success');
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
