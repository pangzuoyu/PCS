/**
 * 系统状态页的守卫（P10-C · T1b · SPEC §7.22）。
 *
 * ## 本文件断什么
 *
 * 1. 五个组件**都渲染出来**（DB / Redis / 队列 / LDAP + 总体）
 * 2. 队列深度与 worker 存活**看得见**
 * 3. ⚠️ **不显示敏感值**（后端只给「通不通 / 有多深 / 什么时候心跳」）
 * 4. 读取失败 ⇒ ⇒ **要有提示**（不能白屏 ⇒ ⇒ ⇒ 静默失败最难查）
 */
import { describe, expect, it, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';
import StatusPage from '../../../src/pages/system/StatusPage';

const server = setupServer();

const OK_STATUS = {
  status: 'ok',
  checked_at: 1732425600,
  database: { status: 'ok', detail: null, latency_ms: 2.1 },
  redis: { status: 'ok', detail: null, latency_ms: 0.8 },
  queue: {
    status: 'ok',
    depth: 3,
    worker_last_heartbeat: 'Nov-24 15:39:00 j_complete=12 j_failed=0',
    worker_alive: true,
  },
  ldap: { status: 'ok', detail: '已配置（ldap://localhost:389）', latency_ms: null },
};

describe('StatusPage', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    server.use(
      http.get('/api/v1/status', () => HttpResponse.json(OK_STATUS)),
    );
  });

  it('renders all five components', async () => {
    render(<StatusPage />);
    await waitFor(() => expect(screen.getByText('总体状态')).toBeTruthy());
    expect(screen.getByText('数据库')).toBeTruthy();
    expect(screen.getByText('Redis')).toBeTruthy();
    expect(screen.getByText('LDAP')).toBeTruthy();
    // ⚠️ 「任务队列」出现**两次**（表格行 + 卡片标题）⇒ ⇒ 用 getAll
    expect(screen.getAllByText('任务队列').length).toBeGreaterThan(0);
  });

  it('shows the queue depth and worker liveness', async () => {
    render(<StatusPage />);
    await waitFor(() => expect(screen.getByText('待处理任务数')).toBeTruthy());
    expect(screen.getByText('3')).toBeTruthy();
    expect(screen.getByText('Worker 存活')).toBeTruthy();
  });

  it('does not render secrets', async () => {
    const { container } = render(<StatusPage />);
    await waitFor(() => expect(screen.getByText('总体状态')).toBeTruthy());
    const text = container.textContent ?? '';
    expect(text).not.toContain('postgres://');
    expect(text).not.toContain('redis://');
    expect(text).not.toContain('password');
  });

  it('shows an error message when the read fails', async () => {
    server.use(
      http.get('/api/v1/status', () =>
        HttpResponse.json({ code: 'INTERNAL_ERROR' }, { status: 500 }),
      ),
    );
    render(<StatusPage />);
    await waitFor(() => expect(screen.getByText('状态读取失败')).toBeTruthy());
  });
});
