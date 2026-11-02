/**
 * 系统参数页（§7.20.1 · P9B-3 · T5）。
 *
 * ⚠️ **一次保存 = 一个 PUT**（硬约束 1）—— 测试要钉住「保存只发一个请求」，
 * 否则前端改成逐键 PATCH 时测试不会红，而那正是委员会禁止的形状。
 *
 * ⚠️ **值是 JSONB**（SPEC §7.20.1）⇒ 输入框给 **JSON 文本** ⇒ 保存前
 * `JSON.parse` ⇒ 解析失败**就地报错、不发请求**（解析失败不是后端的错）。
 *
 * ⚠️ **失败方向**：PUT 失败 ⇒ 显示错误且**不**显示「已保存」——
 * 「已保存」出现在失败时，管理员会以为改动生效了（实际一个键都没改）。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { SystemSettingsPage } from '../../../src/pages/admin/SystemSettingsPage';
import { useAuth } from '../../../src/store/auth';
import type { components } from '../../../src/types/api';

type SystemSettingOut = components['schemas']['SystemSettingOut'];

const SETTINGS: SystemSettingOut[] = [
  {
    setting_key: 'session.timeout_minutes',
    setting_value_json: 30,
    description: '会话超时（分钟）',
    updated_at: '2026-11-03T01:00:00Z',
  },
  {
    setting_key: 'edit_lock.ttl_minutes',
    setting_value_json: 15,
    description: '编辑锁有效期（分钟）',
    updated_at: '2026-11-03T01:00:00Z',
  },
  {
    setting_key: 'record.self_check_allowed',
    setting_value_json: true,
    description: '是否允许设计兼任校核',
    updated_at: '2026-11-03T01:00:00Z',
  },
  {
    setting_key: 'stream.batch_submit_limit',
    setting_value_json: 100,
    description: '物流批量提交上限（P9B-3b 用）',
    updated_at: '2026-11-03T01:00:00Z',
  },
];

/** PUT 的调用次数（钉住「一次保存 = 一个请求」）。 */
let putCalls = 0;
/** 最近一次 PUT 的 body。 */
let lastPutBody: unknown = null;
/** PUT 是否失败（500）。 */
let putStatus = 200;

const server = setupServer(
  http.get('/api/v1/system-settings', () => HttpResponse.json(SETTINGS)),
  http.put('/api/v1/system-settings', async ({ request }) => {
    putCalls += 1;
    lastPutBody = await request.json();
    if (putStatus === 500) {
      return HttpResponse.json(
        {
          code: 'INTERNAL_ERROR',
          message: '保存失败',
          detail: null,
          trace_id: 't-500',
        },
        { status: 500 },
      );
    }
    return HttpResponse.json({ updated: [] });
  }),
);

describe('SystemSettingsPage —— 系统参数页', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    putCalls = 0;
    lastPutBody = null;
    putStatus = 200;
    useAuth.setState({ role: 'SYSTEM_ADMIN', accessToken: 'test-token' });
  });

  it('渲染参数行（键 + 值取自 mock）', async () => {
    render(<SystemSettingsPage />);
    await waitFor(() => expect(screen.getByText('session.timeout_minutes')).toBeTruthy());

    expect(screen.getByText('edit_lock.ttl_minutes')).toBeTruthy();
    expect(screen.getByText('会话超时（分钟）')).toBeTruthy();
    // ⚠️ 值是 JSONB ⇒ 输入框给 JSON 文本
    expect((screen.getByTestId('setting-input-session.timeout_minutes') as HTMLInputElement).value).toBe('30');
    expect((screen.getByTestId('setting-input-record.self_check_allowed') as HTMLInputElement).value).toBe('true');
  });

  it('⚠️ 改两个参数点保存 ⇒ **只发一个** PUT，body.settings 含两个键', async () => {
    render(<SystemSettingsPage />);
    await waitFor(() => expect(screen.getByText('session.timeout_minutes')).toBeTruthy());

    fireEvent.change(screen.getByTestId('setting-input-session.timeout_minutes'), {
      target: { value: '45' },
    });
    fireEvent.change(screen.getByTestId('setting-input-record.self_check_allowed'), {
      target: { value: 'false' },
    });
    fireEvent.click(screen.getByTestId('system-settings-save'));

    await waitFor(() => expect(putCalls).toBe(1));
    expect(putCalls).toBe(1);
    expect(lastPutBody).toEqual({
      settings: {
        'session.timeout_minutes': 45,
        'record.self_check_allowed': false,
      },
    });
  });

  it('PUT 失败（500）⇒ 显示错误且**不**显示「已保存」', async () => {
    putStatus = 500;
    render(<SystemSettingsPage />);
    await waitFor(() => expect(screen.getByText('session.timeout_minutes')).toBeTruthy());

    fireEvent.change(screen.getByTestId('setting-input-session.timeout_minutes'), {
      target: { value: '45' },
    });
    fireEvent.click(screen.getByTestId('system-settings-save'));

    await waitFor(() => expect(screen.getByTestId('system-settings-error')).toBeTruthy());
    expect(screen.getByTestId('system-settings-error').textContent).toContain('INTERNAL_ERROR');
    expect(screen.queryByTestId('system-settings-notice')).toBeNull();
    expect(document.body.textContent).not.toContain('已保存');
  });

  it('⚠️ JSON 解析失败 ⇒ 就地报错 + **不发请求**', async () => {
    render(<SystemSettingsPage />);
    await waitFor(() => expect(screen.getByText('session.timeout_minutes')).toBeTruthy());

    fireEvent.change(screen.getByTestId('setting-input-session.timeout_minutes'), {
      target: { value: '{不是 JSON' },
    });
    fireEvent.click(screen.getByTestId('system-settings-save'));

    await waitFor(() =>
      expect(screen.getByTestId('setting-error-session.timeout_minutes')).toBeTruthy(),
    );
    expect(putCalls).toBe(0);
  });
});
