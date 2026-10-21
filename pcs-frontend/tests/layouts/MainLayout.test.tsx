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
import { useDegradation } from '../../src/store/degradation';

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
  // ⚠️ `/health` 的 `realtime` —— 顶栏实时状态横幅的数据源（SPEC §6.23）。
  // **默认可变** ⇒ 各用例可改；`realtime=degraded` 时顶栏必须出现横幅。
  http.get('/api/v1/health', () =>
    HttpResponse.json({
      status: 'ok',
      database: 'up',
      realtime: healthState.realtime,
      realtime_reason: healthState.realtime_reason,
    }),
  ),
);

/** `/health` 的 realtime 状态（可变 ⇒ 各用例自己设）。 */
let healthState: { realtime: string; realtime_reason: string | null } = {
  realtime: 'ok',
  realtime_reason: null,
};

describe('MainLayout — 通知接线（TODO-065）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
  afterAll(() => server.close());
  beforeEach(() => {
    vi.clearAllMocks();
    useDegradation.setState({ message: null });
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


/**
 * 降级横幅（SPEC §6.21 P9A-LCK-004 · RF-6）。
 *
 * ⚠️ **横幅不阻断任何操作** —— 放行的是**体验**，拦住并发的是 DB 层的
 * `record_hash` 比对 ⇒ 降级时编辑**照常**可用。
 *
 * ⚠️ **文案取后端 message 原文** —— 「；本次编辑无冲突检测」这半句由后端按
 * **该表的保存路径是否已接上冲突检测**决定（ADR-0048 §⑤）
 * ⇒ 前端**不得**自行拼接、不得降级成一句全局提示。
 */
describe('MainLayout — 降级横幅（RF-6）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
  afterAll(() => server.close());
  beforeEach(() => {
    useDegradation.setState({ message: null });
  });

  it('degraded ⇒ 顶栏出现横幅，且文案**原样**取后端 message', async () => {
    // ⚠️ **走 `setMessage`**（生产代码用的正是它）—— 直接 `setState` 会
    // 把「setMessage 是空函数」那个 bug 彻底掩盖（浏览器 QA 实测踩过）。
    useDegradation.getState().setMessage(
      '锁服务不可用，保存时可能冲突；本次编辑无冲突检测',
    );
    render(
      <MemoryRouter>
        <MainLayout />
      </MemoryRouter>,
    );

    await waitFor(() => expect(screen.getByTestId('degradation-banner')).toBeTruthy());
    expect(screen.getByTestId('degradation-banner').textContent).toContain(
      '本次编辑无冲突检测',
    );
    // ⚠️ **不阻断**：壳照常渲染（通知铃铛仍在）
    expect(screen.getByTestId('notif-badge')).toBeTruthy();
  });

  it('无降级 ⇒ **不渲染**横幅（不是渲染一句自造全局提示）', async () => {
    render(
      <MemoryRouter>
        <MainLayout />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId('notif-badge')).toBeTruthy());
    expect(screen.queryByTestId('degradation-banner')).toBeNull();
  });
});

/**
 * 实时状态横幅（SPEC §6.23 · 最终评审 Important ④）。
 *
 * ## 为什么这条测试存在
 *
 * `RealtimeStatusBanner` 组件**写好了、有测试**，却**没有任何宿主**渲染它
 * ⇒ §6.23 实际上**没交付**（组件只活在测试里 —— 本仓最怕的「假绿」形状）。
 *
 * ⇒ 顶栏（`MainLayout`）必须读 `/health` 的 `realtime` / `realtime_reason`
 * 并在 degraded 时渲染横幅。
 */
describe('MainLayout —— 实时状态横幅（SPEC §6.23）', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'bypass' }));
  afterAll(() => server.close());
  beforeEach(() => {
    healthState = { realtime: 'ok', realtime_reason: null };
  });

  it('realtime=degraded ⇒ 顶栏出现横幅，且说「仍可收到通知」（不得说「已关闭」）', async () => {
    healthState = { realtime: 'degraded', realtime_reason: 'redis_unavailable' };
    render(
      <MemoryRouter>
        <MainLayout />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId('realtime-status-banner')).toBeTruthy());
    const text = screen.getByTestId('realtime-status-banner').textContent ?? '';
    expect(text).toContain('仍可收到通知');
    expect(text).not.toContain('已关闭');
    // ⚠️ `realtime_reason` 走**枚举映射** ⇒ 不得把原始英文码当文案
    expect(text).not.toContain('redis_unavailable');
  });

  it('realtime=ok ⇒ **不渲染**横幅', async () => {
    render(
      <MemoryRouter>
        <MainLayout />
      </MemoryRouter>,
    );
    await waitFor(() => expect(screen.getByTestId('notif-badge')).toBeTruthy());
    expect(screen.queryByTestId('realtime-status-banner')).toBeNull();
  });
});
