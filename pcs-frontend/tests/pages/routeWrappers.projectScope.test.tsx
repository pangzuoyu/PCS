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
import { useProjectScopeStore } from '../../src/store/projectScope';

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

/**
 * 「我能看的项目」清单（**授权** ∪ **工作区**）—— P10-H · T1 之后
 * 项目作用域来自 `GET /user-projects/me` ∪ `GET /workspaces`。
 */
let grants: unknown[] = [];
let workspaces: unknown[] = [];

beforeEach(() => {
  get.mockReset();
  // ⚠️ **store 是模块级的**（P10-H · T1）⇒ ⇒ 用例之间必须清干净
  //    ⇒ 否则上一个用例加载出来的项目作用域会**漏进**下一个用例。
  useProjectScopeStore.getState().reset();
  grants = [
    {
      id: 'grant-1',
      user_id: '00000000-0000-0000-0000-0000000a11ce',
      project_id: 'proj-real',
      role_in_project: 'PROJECT_LEAD',
      granted_by: null,
      granted_at: null,
      revoked_at: null,
      revoked_by: null,
    },
  ];
  workspaces = [
    { workspace_id: 'ws-formal', workspace_type: 'FORMAL', project_id: 'proj-real' },
  ];
  get.mockImplementation((url: string) => {
    if (url === '/user-projects/me') return Promise.resolve({ data: grants } as never);
    if (url === '/workspaces') return Promise.resolve({ data: workspaces } as never);
    if (url === '/meta/ui-schema/bedd') {
      return Promise.resolve({ data: { schema_version: '1.0.0', resource: 'bedd', fields: [] } } as never);
    }
    if (url === '/projects/proj-real/pms') {
      return Promise.resolve({ data: { items: [], total: 0, limit: 100, offset: 0 } } as never);
    }
    if (url === '/projects/proj-real/bedd') {
      return Promise.resolve({ data: { project_id: 'proj-real', document: {}, updated_at: null } } as never);
    }
    // `GET /projects/{id}` ⇒ ⇒ 项目名
    const id = url.replace('/projects/', '');
    return Promise.resolve({
      data: {
        project_id: id,
        project_no: 'PRJ-1',
        project_name: '真项目',
        project_type: 'PETROCHEMICAL',
        product_category: 'OTHER',
        electricity_value_type: 'EQUIVALENT',
      },
    } as never);
  });
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
    grants = [];
    workspaces = [];
    render(<PipeLineListRoute />);
    await waitFor(() =>
      expect(screen.getByTestId('pipe-line-list-scope-error')).toBeTruthy(),
    );
    expect(fetched).toEqual([]);
  });
});

describe('PmsRoute / BeddRoute — 接**真端点**（P10-H · T2 · TODO-195）', () => {
  it('/pms ⇒ 按**当前项目**取数（不再是占位页）', async () => {
    render(<PmsRoute />);
    await waitFor(() => expect(get).toHaveBeenCalledWith('/projects/proj-real/pms'));
    expect(screen.getByTestId('pms-page')).toBeTruthy();
    // ⚠️ **不再有「数据源尚未接入」** ⇒ ⇒ 那是占位期的说法
    expect(screen.queryByTestId('pms-not-wired')).toBeNull();
  });

  it('/bedd ⇒ 取文档 + uiSchema（分组 Tab）', async () => {
    render(<BeddRoute />);
    await waitFor(() => expect(get).toHaveBeenCalledWith('/projects/proj-real/bedd'));
    expect(get).toHaveBeenCalledWith('/meta/ui-schema/bedd');
    expect(screen.getByTestId('bedd-page')).toBeTruthy();
    expect(screen.queryByTestId('bedd-not-wired')).toBeNull();
  });
});
