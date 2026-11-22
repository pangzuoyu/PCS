/**
 * `useProjectScope` 测试（P10-H · T1 · TODO-194）。
 *
 * ## 本文件钉的规则
 *
 * 1. **候选来源是「授权 ∪ 工作区」** ⇒ ⇒ 不是「列表里的第一个」。
 * 2. **项目名**来自 `GET /projects/{id}`（授权列表**没有名字**）。
 * 3. **选中的项目保持**（换页不丢）⇒ ⇒ 状态在 store 里，不在 hook 里。
 * 4. **没有候选 ⇒ 给出说明**（不静默地空 projectId）。
 * 5. **非 403 的错误不被吞**（401 / 500 ⇒ 原样报错）。
 * 6. **幂等**：多个组件同时挂载 ⇒ ⇒ 只发**一轮**请求。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor, act } from '@testing-library/react';

import { useProjectScope } from '../../src/hooks/useProjectScope';
import { useProjectScopeStore } from '../../src/store/projectScope';
import { api } from '../../src/api/client';
import { useAuth } from '../../src/store/auth';

vi.mock('../../src/api/client', () => ({
  api: { get: vi.fn() },
  handleSessionOver: vi.fn(),
}));

const get = vi.mocked(api.get);

/** 造一个 axios 风格的响应。 */
function ok(data: unknown) {
  return { data } as never;
}

/** 造一个 axios 风格的错误（带 HTTP 状态码）。 */
function fail(status: number) {
  return { response: { status } } as never;
}

/** 授权列表（`UserProjectResponse` 的**契约形状**）。 */
function grants(rows: Array<[string, string]>) {
  return rows.map(([projectId, role], i) => ({
    id: `grant-${i}`,
    user_id: '00000000-0000-0000-0000-0000000a11ce',
    project_id: projectId,
    role_in_project: role,
    granted_by: null,
    granted_at: '2026-08-01T09:00:00Z',
    revoked_at: null,
    revoked_by: null,
  }));
}

/**
 * 铺一套响应：**授权**（`/user-projects/me`）+ **工作区**（`/workspaces`）
 * + **项目名**（`/projects/{id}`）。
 */
function serve(granted: Array<[string, string]>, names: Record<string, string>): void {
  get.mockImplementation((url: string) => {
    if (url === '/user-projects/me') return Promise.resolve(ok(grants(granted)));
    if (url === '/workspaces') return Promise.resolve(ok([]));
    const id = url.replace('/projects/', '');
    if (names[id]) {
      return Promise.resolve(
        ok({
          project_id: id,
          project_no: 'PRJ-1',
          project_name: names[id],
          project_type: 'PETROCHEMICAL',
          product_category: 'ETHYLENE',
          electricity_value_type: 'EQUIVALENT_VALUE',
        }),
      );
    }
    return Promise.reject(fail(404));
  });
}

beforeEach(() => {
  get.mockReset();
  useProjectScopeStore.getState().reset();
  useAuth.getState().clearSession();
  useAuth.getState().setSession({
    access_token: 'token-alice',
    refresh_token: 'refresh-alice',
    username: 'alice',
    role: 'DESIGNER',
    user_id: '00000000-0000-0000-0000-0000000a11ce',
  });
});

describe('useProjectScope — 候选清单', () => {
  it('授权列表 ⇒ 解析出**全部**候选 + 项目名（不是只取「第一个」）', async () => {
    serve(
      [
        ['proj-a', 'PROJECT_LEAD'],
        ['proj-b', 'DESIGNER'],
      ],
      { 'proj-a': '乙烯项目', 'proj-b': '炼油项目' },
    );
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projects.map((p) => p.projectId)).toEqual(['proj-a', 'proj-b']);
    expect(result.current.projects.map((p) => p.name)).toEqual(['乙烯项目', '炼油项目']);
    expect(result.current.error).toBeNull();
    // ⚠️ 默认选中**第一个**（还没有用户选择时）
    expect(result.current.projectId).toBe('proj-a');
  });

  it('⚠️ **工作区挂的项目**也在候选里（我自己的项目 · 授权行后加的）', async () => {
    get.mockImplementation((url, config) => {
      if (url === '/user-projects/me') return Promise.resolve(ok(grants([])));
      if (url === '/workspaces') {
        // ⚠️ 普通用户 ⇒ 必须带 `owner_id`
        const params = config?.params as { owner_id?: string } | undefined;
        expect(params?.owner_id).toBe('00000000-0000-0000-0000-0000000a11ce');
        return Promise.resolve(
          ok([{ workspace_id: 'ws-1', workspace_type: 'FORMAL', project_id: 'proj-own' }]),
        );
      }
      return Promise.resolve(
        ok({
          project_id: 'proj-own',
          project_no: 'PRJ-2',
          project_name: '自有项目',
          project_type: 'REFINERY',
          product_category: 'REFINING',
          electricity_value_type: 'EQUIVALENT_VALUE',
        }),
      );
    });
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projects.map((p) => p.projectId)).toEqual(['proj-own']);
    expect(result.current.projectId).toBe('proj-own');
  });

  it('⚠️ **admin 走工作区全量**（不带 owner_id）⇒ ⇒ 没有授权行也能选项目', async () => {
    useAuth.getState().clearSession();
    useAuth.getState().setSession({
      access_token: 'token-admin',
      refresh_token: 'refresh-admin',
      username: 'admin',
      role: 'SYSTEM_ADMIN',
      user_id: '00000000-0000-0000-0000-0000000a11ce',
    });
    get.mockImplementation((url, config) => {
      if (url === '/user-projects/me') return Promise.resolve(ok(grants([])));
      if (url === '/workspaces') {
        const params = config?.params as { owner_id?: string } | undefined;
        expect(params?.owner_id).toBeUndefined();
        return Promise.resolve(
          ok([{ workspace_id: 'ws-1', workspace_type: 'FORMAL', project_id: 'proj-admin' }]),
        );
      }
      return Promise.resolve(
        ok({
          project_id: 'proj-admin',
          project_no: 'PRJ-3',
          project_name: '管理员项目',
          project_type: 'PETROCHEMICAL',
          product_category: 'OTHER',
          electricity_value_type: 'EQUIVALENT',
        }),
      );
    });
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBe('proj-admin');
  });
});

describe('useProjectScope — 选中项', () => {
  it('用户选的项目**保持**（换页 / 重渲染都不丢）', async () => {
    serve(
      [
        ['proj-a', 'PROJECT_LEAD'],
        ['proj-b', 'DESIGNER'],
      ],
      { 'proj-a': '乙烯项目', 'proj-b': '炼油项目' },
    );
    const { result, rerender } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    act(() => result.current.selectProject('proj-b'));
    expect(result.current.projectId).toBe('proj-b');
    rerender();
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBe('proj-b');
  });

  it('env hint 只作**首次默认值**（用户选过之后 ⇒ 以用户的选择为准）', async () => {
    vi.stubEnv('VITE_PROJECT_ID', 'proj-b');
    serve(
      [
        ['proj-a', 'PROJECT_LEAD'],
        ['proj-b', 'DESIGNER'],
      ],
      { 'proj-a': '乙烯项目', 'proj-b': '炼油项目' },
    );
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBe('proj-b');
    act(() => result.current.selectProject('proj-a'));
    expect(result.current.projectId).toBe('proj-a');
    vi.unstubAllEnvs();
  });
});

describe('useProjectScope — 异常', () => {
  it('没有候选 ⇒ 给出说明（而不是空 projectId 悄悄发请求）', async () => {
    serve([], {});
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBeNull();
    expect(result.current.error).toContain('项目作用域');
  });

  it('⚠️ **非 403 的错误不被吞**（500 ⇒ 原样报错）', async () => {
    get.mockRejectedValue(fail(500));
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBeNull();
    expect(result.current.error).toBeTruthy();
  });
});

describe('useProjectScope — 并发', () => {
  it('⚠️ **幂等**：两个组件同时挂 ⇒ ⇒ 只发**一轮** `/user-projects/me`', async () => {
    serve([['proj-a', 'PROJECT_LEAD']], { 'proj-a': '乙烯项目' });
    renderHook(() => useProjectScope());
    renderHook(() => useProjectScope());
    await waitFor(() =>
      expect(
        get.mock.calls.filter((c) => c[0] === '/user-projects/me').length,
      ).toBe(1),
    );
  });
});
