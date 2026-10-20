/**
 * MainLayout 的通知接线测试（TODO-065 · P9A Z 收口实测发现）。
 *
 * ## 为什么有这条
 *
 * P9A 交付了真的 `GET /api/v1/notifications`，响应形状是
 * `{items: NotificationItemResponse[], unread_count: number}`（契约）。
 * 而 `MainLayout` 一直按**自己造的数组**消费它：
 *
 * ```ts
 * .then((j: Notification[]) => setNotifications(j))
 * ```
 *
 * `j` 是 `as Notification[]` 的**类型断言**，运行时**不做任何检查** ⇒
 * 真后端返回的对象被塞进 `useState<Notification[]>` ⇒
 * 下一行 `notifications.filter(...)` 抛 `TypeError` ⇒ **整个壳崩**
 * （MainLayout 是所有已登录页面的父级）。
 *
 * ⚠️ **dev 与浏览器 QA 全程看不见它** —— `main.tsx` 在 `import.meta.env.DEV`
 * 下恒挂 MSW，而 MSW 的 `/api/v1/notifications` handler 返回的是
 * `seedNotifications`（**前端自造形状的数组**）⇒ mock 把漂移**藏住了**。
 * ⇒ 生产构建（MSW 被 tree-shake 移除）才暴露。
 *
 * 本测试用 MSW node server 返**契约形状** ⇒ 就是生产的形状。
 *
 * ⚠️ **不 mock api 模块**：那会把这组测试变成「测 mock 的行为」。
 * 这里 mock 的是**服务端**，被测的是**我们怎么消费它的响应**。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import MainLayout from '../../src/layouts/MainLayout';

/** 契约形状（`components['schemas']['NotificationListResponse']`）。 */
const CONTRACT_RESPONSE = {
  items: [
    {
      notification_id: '11111111-1111-1111-1111-111111111111',
      kind: 'SIGN_COMPLETED',
      title: 'Rev C 已签署',
      body: '校核 alice 已签署',
      detail: null,
      created_at: '2026-10-20T10:00:00+08:00',
      read_at: null,
    },
  ],
  unread_count: 1,
};

const server = setupServer(
  http.get('/api/v1/notifications', () => HttpResponse.json(CONTRACT_RESPONSE)),
  http.get('/api/v1/todos', () => HttpResponse.json({ items: [], total: 0 })),
);

describe('MainLayout — 通知接线（TODO-065）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
  afterAll(() => server.close());
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('后端返回契约形状时不得崩（红点取 unread_count，未读取 read_at）', async () => {
    // 崩的话这里就抛（React render error ⇒ 测试失败）。
    render(
      <MemoryRouter>
        <MainLayout />
      </MemoryRouter>,
    );

    // 契约形状下：未读数 = 1（来自 unread_count，不是前端数 items）。
    await waitFor(() => {
      expect(screen.getByTestId('notif-badge').textContent).toContain('1');
    });
  });
});
