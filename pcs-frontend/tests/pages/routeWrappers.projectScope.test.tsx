/**
 * 「项目作用域」路由层测试（P10-C · T2 · TODO-159）。
 *
 * ## 为什么要有这个文件
 *
 * 三个页面此前调**不存在**的端点，且用的是**占位** project id
 * （`00000000-0000-0000-0000-000000000001`）⇒ ⇒ 真后端下 **404**。
 *
 * ⇒ ⇒ 现在：
 * - `/pipe/line-list` ⇒ ⇒ **先解析真项目 id** ⇒ ⇒ 再按项目取一览表；
 * - `/pms` · `/bedd` ⇒ ⇒ **不发请求**（后端确实没有那两个实体）⇒ ⇒ 占位页。
 *
 * ## 本文件钉的规则
 *
 * 1. **绝不用占位 id 发请求**（⇒ ⇒ 断言 URL 里**不含**那个常量）。
 * 2. `/pipe/line-list` 的请求 URL = `/api/v1/projects/{真 id}/pipe-line-list`。
 * 3. `/pms` · `/bedd` ⇒ ⇒ **零请求**。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';

import { PipeLineListRoute, PmsRoute, BeddRoute } from '../../src/pages/routeWrappers';
import { PLACEHOLDER_PROJECT_ID } from '../../src/constants/env';
import { api } from '../../src/api/client';

vi.mock('../../src/api/client', () => ({
  api: { get: vi.fn() },
  handleSessionOver: vi.fn(),
}));

const get = vi.mocked(api.get);

/** `useFetch` 用的全局 `fetch` 桩（记录调用过的 URL）。 */
let fetched: string[] = [];

function stubFetch(): void {
  fetched = [];
  vi.stubGlobal(
    'fetch',
    vi.fn((url: string) => {
      fetched.push(url);
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => [],
      });
    }),
  );
}

beforeEach(() => {
  get.mockReset();
  get.mockResolvedValue({
    data: [
      { workspace_id: 'ws-formal', workspace_type: 'FORMAL', project_id: 'proj-real' },
    ],
  } as never);
  stubFetch();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('PipeLineListRoute — 用**真** project id (P10-C · T2)', () => {
  it('解析出项目作用域 ⇒ 请求 `/api/v1/projects/{真 id}/pipe-line-list`', async () => {
    render(<PipeLineListRoute />);
    await waitFor(() => expect(fetched.length).toBeGreaterThan(0));
    expect(fetched).toContain('/api/v1/projects/proj-real/pipe-line-list');
  });

  it('⚠️ **绝不用占位 project id 发请求**', async () => {
    render(<PipeLineListRoute />);
    await waitFor(() => expect(fetched.length).toBeGreaterThan(0));
    for (const url of fetched) {
      expect(url).not.toContain(PLACEHOLDER_PROJECT_ID);
    }
  });

  it('没有项目作用域 ⇒ 显示说明，**且不发请求**', async () => {
    get.mockResolvedValue({ data: [] } as never);
    render(<PipeLineListRoute />);
    await waitFor(() =>
      expect(screen.getByTestId('pipe-line-list-scope-error')).toBeTruthy(),
    );
    expect(fetched).toEqual([]);
  });
});

describe('PmsRoute / BeddRoute — **零请求**的占位页 (P10-C · T2)', () => {
  it('/pms ⇒ 不发任何请求，且页面写明「数据源尚未接入」', async () => {
    render(<PmsRoute />);
    expect(screen.getByTestId('pms-page')).toBeTruthy();
    expect(screen.getByTestId('pms-not-wired')).toBeTruthy();
    expect(fetched).toEqual([]);
    expect(get).not.toHaveBeenCalled();
  });

  it('/bedd ⇒ 不发任何请求，且页面写明「数据源尚未接入」', async () => {
    render(<BeddRoute />);
    expect(screen.getByTestId('bedd-page')).toBeTruthy();
    expect(screen.getByTestId('bedd-not-wired')).toBeTruthy();
    expect(fetched).toEqual([]);
    expect(get).not.toHaveBeenCalled();
  });
});
