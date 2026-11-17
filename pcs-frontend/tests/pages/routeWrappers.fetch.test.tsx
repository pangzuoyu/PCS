/**
 * `useFetch` 的失败态 + **401 与 axios 通道共用一份真相源**（P10-F · 评审 #9）。
 *
 * ## 为什么有这个测试
 *
 * `routeWrappers.tsx::useFetch` 是前端**第二条 HTTP 通道**（第一条是 axios）。
 * 它原先的形状是「**失败与加载中同形**」：
 * - `!r.ok` ⇒ 返回 `null` ⇒ `if (!stream) return 加载中…` ⇒ **后端 500 与
 *   「还在加载」在屏幕上完全一样** ⇒ 用户永远等不到失败提示。
 * - `.catch(() => {})` ⇒ 网络异常被**静默吞掉** ⇒ 同上。
 * - **完全不处理 401** ⇒ access token 30 分钟过期后，这条通道**既不跳登录页、
 *   也不清会话**，页面停在「加载中…」⇒ 每个用户每个会话必遇。
 *
 * ## 这套断言的纪律（照 `docs/solutions/testing-issues/` 的同族结论）
 *
 * - 断**行为**（屏幕上出现什么），不断「调用了哪个函数」。
 * - 401 那条断的是「**只有一份真相源**」⇒ ⇒ 删掉 `useFetch` 里对
 *   `handleSessionOver` 的调用 ⇒ ⇒ 本文件**必须红**（变异敏感）。
 * - 断**真 store**（`useAuth.getState().accessToken` 变 null），不用 mock 的
 *   `clearSession` ⇒ ⇒ 断的是真实副作用，不是 mock 的调用次数。
 */
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, waitFor, act, fireEvent } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useNavigate } from 'react-router-dom';
import type { JSX } from 'react';

import {
  PipeClassListRoute,
  PropertySearchRoute,
  StreamDetailRoute,
} from '../../src/pages/routeWrappers';
import { AssetListPage } from '../../src/pages/config/AssetListPage';
import { useAuth } from '../../src/store/auth';
import type { Stream } from '../../src/types/stream';
import type { PipeClass } from '../../src/types/pipeClass';
import type { ConfigAsset } from '../../src/types/configAsset';

// ---------------------------------------------------------------------------
// 夹具
// ---------------------------------------------------------------------------

/** 塞一个已登录会话（两条通道都据此带 Bearer）。 */
function login(): void {
  useAuth.getState().setSession({
    access_token: 'token-alice',
    refresh_token: 'refresh-alice',
    username: 'alice',
    role: 'DESIGNER',
    user_id: '00000000-0000-0000-0000-0000000a11ce',
  });
}

/** 一个最小可用的 `Response` 替身（只需 `ok` / `status` / `json`）。 */
function response(body: unknown, init?: { ok?: boolean; status?: number }): unknown {
  return {
    ok: init?.ok ?? true,
    status: init?.status ?? 200,
    json: async () => body,
  };
}

/** 永远不 resolve，只在 `abort()` 时 reject（⇒ 用于超时/卸载路径）。 */
function stubHangingFetch(): void {
  vi.stubGlobal(
    'fetch',
    vi.fn((_url: string, init?: { signal?: AbortSignal }) =>
      new Promise((_resolve, reject) => {
        init?.signal?.addEventListener('abort', () => {
          const err = new Error('The operation was aborted.');
          err.name = 'AbortError';
          reject(err);
        });
      }),
    ),
  );
}

/** 桩掉 `window.location`（jsdom 的 location 不可局部改写）。 */
function stubLocation(pathname: string): { pathname: string; href: string } {
  const loc = { pathname, href: `http://localhost:5173${pathname}` };
  vi.stubGlobal('location', loc);
  return loc;
}

/** 在指定路由上渲染（`StreamDetailRoute` 读 `useParams` ⇒ 必须有 `<Route>`）。 */
function renderAt(path: string, pattern: string, element: JSX.Element) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={pattern} element={element} />
      </Routes>
    </MemoryRouter>,
  );
}

/** 一个能改路由的按钮（用来制造「同一个组件实例、path 变了」）。 */
function Nav({ to }: { to: string }): JSX.Element {
  const navigate = useNavigate();
  return <button onClick={() => navigate(to)}>go</button>;
}

const stream: Stream = {
  stream_id: 's-1',
  stream_name: '新鲜进料',
  phase: 'LIQUID',
  temp: 25,
  press: 0.5,
  mass_flow: 10000,
  molar_flow: 100,
  composition_json: { N2: 0.78, O2: 0.21 },
  reference_count: 0,
  sign_status: 'CHECKED',
  record_hash: 'a3f9b2e1c21ed7a8',
  case_type: 'NORMAL',
  data_mode: 'CHEMICAL',
  source_type: 'MANUAL_ENTRY',
  source: 'MANUAL',
  approval_depth: 2,
  created_at: '2026-09-15 14:00',
  updated_at: '2026-09-15 14:32',
};

const pipeClass: PipeClass = {
  class_id: 'pc-1',
  class_name: 'CS-STD',
  material_standard: 'GB/T 12459',
  corrosion_allowance: 3,
  design_pressure: 1.6,
  design_temperature: 120,
  dn_series_json: { min: 150, max: 150 },
  sch_series_json: { DN150: '40' },
  flange_class: '150#',
  source: 'COMPANY_STD',
  version: 'v1',
  status: 'PUBLISHED',
};

const asset: ConfigAsset = {
  asset_id: 'a-1',
  category: 'CATEGORY_2',
  name: '某公式',
  status: 'DRAFT',
  current_version: 'v1',
};

/** 第二条物流（用来断「换 id 之后显示的是新数据，不是上一条」）。 */
const stream2: Stream = { ...stream, stream_id: 's-2', stream_name: '另一条物流' };

afterEach(() => {
  vi.unstubAllGlobals();
  // ⚠️ **不用** `vi.restoreAllMocks()` ⇒ 它会把 `tests/setup.ts` 里给
  // `window.matchMedia` 装的桩一起还原成「返回 undefined」⇒ ⇒ antd 的
  // `responsiveObserver` 立刻抛 `Cannot destructure property 'matches'`。
  // 本文件自己的 spy 在各用例内显式 `mockRestore()`。
  useAuth.getState().clearSession();
});

// ---------------------------------------------------------------------------

describe('useFetch 的失败态（评审 #9）', () => {
  it('fetch 500 ⇒ 页面显示「加载失败」而不是「加载中…」', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(response({ message: 'boom' }, { ok: false, status: 500 })),
    );
    renderAt('/streams/s-1', '/streams/:id', <StreamDetailRoute />);

    expect(await screen.findByText(/加载失败/)).toBeInTheDocument();
    expect(screen.queryByText('加载中…')).not.toBeInTheDocument();
  });

  it('fetch 抛网络异常 ⇒ 同样进入失败态（不被吞掉）', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')));
    renderAt('/streams/s-1', '/streams/:id', <StreamDetailRoute />);

    expect(await screen.findByText(/加载失败：网络错误/)).toBeInTheDocument();
    expect(screen.queryByText('加载中…')).not.toBeInTheDocument();
  });

  it('fetch 401 ⇒ 与 axios 通道同一份真相源（清会话 + 跳 /login）', async () => {
    login();
    const loc = stubLocation('/streams/s-1');
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(response({ code: 'EXPIRED_TOKEN' }, { ok: false, status: 401 })),
    );
    renderAt('/streams/s-1', '/streams/:id', <StreamDetailRoute />);

    // ⚠️ 断**真 store**（不是 mock 的 clearSession 调用次数）
    await waitFor(() => expect(useAuth.getState().accessToken).toBeNull());
    expect(loc.href).toBe('/login');
  });
});

describe('useFetch 的四个边界（评审 D11）', () => {
  it('超时：15s 后进入失败态，文案是「请求超时」而不是「网络错误」', async () => {
    vi.useFakeTimers();
    try {
      stubHangingFetch();
      renderAt('/streams/s-1', '/streams/:id', <StreamDetailRoute />);

      expect(screen.getByText('加载中…')).toBeInTheDocument();

      // ⚠️ 断**边界**：14.999s 还没超时（⇒ 超时值就是 15s，不是 10s/30s）
      await act(async () => {
        await vi.advanceTimersByTimeAsync(14_999);
      });
      expect(screen.getByText('加载中…')).toBeInTheDocument();

      await act(async () => {
        await vi.advanceTimersByTimeAsync(1);
      });
      expect(screen.getByText(/加载失败：请求超时（15s）/)).toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });

  it('卸载清理：abort() 被调 + 定时器被清（防 timer 泄漏）', () => {
    const abortSpy = vi.spyOn(AbortController.prototype, 'abort');
    const clearSpy = vi.spyOn(globalThis, 'clearTimeout');
    stubHangingFetch();

    const { unmount } = renderAt('/streams/s-1', '/streams/:id', <StreamDetailRoute />);
    const clearsBefore = clearSpy.mock.calls.length;

    unmount();

    expect(abortSpy).toHaveBeenCalled();
    expect(clearSpy.mock.calls.length).toBeGreaterThan(clearsBefore);

    abortSpy.mockRestore();
    clearSpy.mockRestore();
  });

  it('请求头：AssetListPage 的请求带的是**会话 token**，不是写死的 DEV_BEARER', async () => {
    login();
    const fetchMock = vi.fn().mockResolvedValue(response([]));
    vi.stubGlobal('fetch', fetchMock);

    render(<AssetListPage assets={[asset]} />);
    fireEvent.click(screen.getByTestId('asset-action-version'));

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const init = fetchMock.mock.calls[0][1] as { headers: { Authorization: string } };
    expect(init.headers.Authorization).toBe('Bearer token-alice');
    // ⚠️ 写死的假 token 一旦回来，这条必须红
    expect(init.headers.Authorization).not.toContain('mock-jwt-token');
  });
});

describe('useFetch 改签名后的调用点回归（9 个调用点 · 代表 3 个）', () => {
  it('/pipe-classes ⇒ 取到的数据真的渲染进表格', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url === '/api/v1/pipe-classes' ? response([pipeClass]) : response(null, { ok: false, status: 404 }),
        ),
      ),
    );
    renderAt('/pipe-classes', '/pipe-classes', <PipeClassListRoute />);

    expect(await screen.findByTestId('pipe-class-list-page')).toBeInTheDocument();
    expect(screen.getByText('CS-STD')).toBeInTheDocument();
    expect(screen.getByText('GB/T 12459')).toBeInTheDocument();
  });

  it('/streams/{id} ⇒ 取到的物流真的渲染进详情页', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() => Promise.resolve(response(stream))),
    );
    renderAt('/streams/s-1', '/streams/:id', <StreamDetailRoute />);

    expect(await screen.findByTestId('stream-detail-page')).toBeInTheDocument();
    // ⚠️ 物流名在页头与详情表里各出现一次 ⇒ 断**详情表**这一处，不做全局计数
    expect(screen.getByTestId('stream-detail-descriptions').textContent).toContain('新鲜进料');
  });

  it('/common/materials/search ⇒ 取到的组分真的渲染进卡片', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        Promise.resolve(
          url === '/api/v1/common/materials/search'
            ? response([{ cas: '74-98-6', name: '苯', formula: 'C6H6', mw: 78.11, source: 'lib' }])
            : response(null, { ok: false, status: 404 }),
        ),
      ),
    );
    renderAt('/common/materials', '/common/materials', <PropertySearchRoute />);

    expect(await screen.findByTestId('property-search-page')).toBeInTheDocument();
    expect(screen.getByText('苯')).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// ⚠️ **path 变化 ⇒ 状态必须重置**（P10-F · 整支评审 C1）
// ---------------------------------------------------------------------------

describe('useFetch 在 path 变化时必须重置状态（评审 C1）', () => {
  it('上一条请求失败 ⇒ 换 id 后不再停在那条错误上（重新进入加载态 ⇒ 再显示新数据）', async () => {
    // ⚠️ 第二条请求**故意挂住** ⇒ ⇒ 「加载中…」这个中间态可以被确定性地断言
    //    （若立即 resolve ⇒ 断言与微任务赛跑 ⇒ 假绿）。
    let resolveSecond: (v: unknown) => void = () => {};
    const second = new Promise((resolve) => {
      resolveSecond = resolve;
    });
    vi.stubGlobal(
      'fetch',
      vi.fn((url: string) =>
        url.endsWith('/s-1')
          ? Promise.resolve(response({ message: 'boom' }, { ok: false, status: 500 }))
          : second,
      ),
    );

    render(
      <MemoryRouter initialEntries={['/streams/s-1']}>
        <Nav to="/streams/s-2" />
        <Routes>
          <Route path="/streams/:id" element={<StreamDetailRoute />} />
        </Routes>
      </MemoryRouter>,
    );

    // ① 第一条失败 ⇒ 失败态
    expect(await screen.findByText(/加载失败：HTTP 500/)).toBeInTheDocument();

    // ② ⚠️ **换 id**（React Router **复用同一个组件实例** ⇒ `useState` 不重置）
    //    ⇒ ⇒ 旧代码里 `error` 仍是 'HTTP 500'、`loading` 仍是 false
    //    ⇒ ⇒ 页面停在一个**假的**失败提示上，且新数据永远不显示。
    fireEvent.click(screen.getByText('go'));
    expect(screen.getByText('加载中…')).toBeInTheDocument();
    expect(screen.queryByText(/加载失败/)).not.toBeInTheDocument();

    // ③ 新数据真的渲染出来（不是上一条的）
    await act(async () => {
      resolveSecond(response(stream2));
    });
    expect(await screen.findByTestId('stream-detail-page')).toBeInTheDocument();
    expect(screen.getByTestId('stream-detail-descriptions').textContent).toContain(
      '另一条物流',
    );
  });

  it('卸载后迟到的 401 不清会话（不在已卸载的组件上做会话副作用）', async () => {
    login();
    stubLocation('/streams/s-1');
    let resolve401: (v: unknown) => void = () => {};
    const pending = new Promise((resolve) => {
      resolve401 = resolve;
    });
    vi.stubGlobal('fetch', vi.fn(() => pending));

    const { unmount } = renderAt('/streams/s-1', '/streams/:id', <StreamDetailRoute />);
    unmount();

    await act(async () => {
      resolve401(response({ code: 'EXPIRED_TOKEN' }, { ok: false, status: 401 }));
    });

    // ⚠️ 组件已经卸载 ⇒ ⇒ 不该再清会话（否则「用户刚离开页面」就被登出）
    expect(useAuth.getState().accessToken).not.toBeNull();
  });
});
