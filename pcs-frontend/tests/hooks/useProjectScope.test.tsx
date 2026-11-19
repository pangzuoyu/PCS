/**
 * `useProjectScope` 测试（P10-C · T2 · TODO-159）。
 *
 * ## 为什么有这个 hook
 *
 * 前端此前到处拿**占位** project id（`PLACEHOLDER_PROJECT_ID`）去调端点
 * ⇒ ⇒ 那**不是真项目** ⇒ ⇒ 真后端下必然 404。
 * ⇒ ⇒ 真 id 从**服务端**解析：`GET /workspaces` 的每一行都带 `project_id`。
 *
 * ## 本文件钉的三条规则
 *
 * 1. **SYSTEM_ADMIN**：`GET /workspaces`（不传 owner_id）⇒ 200 ⇒ 直接用。
 * 2. **普通用户**：上一步 **403** ⇒ ⇒ 退到 `?owner_id={我自己}`。
 * 3. **其它错误**（401 / 网络 / 500）⇒ ⇒ **原样报错**（不被误吞成「没项目」）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

import { useProjectScope } from '../../src/hooks/useProjectScope';
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

beforeEach(() => {
  get.mockReset();
  useAuth.getState().clearSession();
  useAuth.getState().setSession({
    access_token: 'token-alice',
    refresh_token: 'refresh-alice',
    username: 'alice',
    role: 'DESIGNER',
    user_id: '00000000-0000-0000-0000-0000000a11ce',
  });
});

describe('useProjectScope — SYSTEM_ADMIN', () => {
  it('GET /workspaces 返回带 project_id 的工作区 ⇒ 解析出真项目 id', async () => {
    get.mockResolvedValue(
      ok([
        { workspace_id: 'ws-personal', workspace_type: 'PERSONAL', project_id: null },
        { workspace_id: 'ws-formal', workspace_type: 'FORMAL', project_id: 'proj-real' },
      ]),
    );
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBe('proj-real');
    expect(result.current.workspaceId).toBe('ws-formal');
    expect(result.current.error).toBeNull();
    // ⚠️ **不许退到 owner_id**（admin 一次就够）
    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith('/workspaces');
  });
});

describe('useProjectScope — 普通用户', () => {
  it('GET /workspaces 403 ⇒ 退到 ?owner_id={我自己}', async () => {
    get
      .mockRejectedValueOnce(fail(403))
      .mockResolvedValueOnce(
        ok([{ workspace_id: 'ws-mine', workspace_type: 'FORMAL', project_id: 'proj-mine' }]),
      );
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBe('proj-mine');
    expect(get).toHaveBeenCalledTimes(2);
    expect(get).toHaveBeenLastCalledWith('/workspaces', {
      params: { owner_id: '00000000-0000-0000-0000-0000000a11ce' },
    });
  });

  it('⚠️ **非 403 的错误不被吞**（401 / 500 ⇒ 原样报错）', async () => {
    get.mockRejectedValue(fail(500));
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBeNull();
    expect(result.current.error).toBeTruthy();
    // ⚠️ **只请求一次** ⇒ ⇒ 500 没有被误当成「要退到 owner_id」
    expect(get).toHaveBeenCalledTimes(1);
  });
});

describe('useProjectScope — 没有可用项目', () => {
  it('工作区都**没挂项目** ⇒ 给出说明（而不是空 projectId 悄悄发请求）', async () => {
    get.mockResolvedValue(
      ok([{ workspace_id: 'ws-personal', workspace_type: 'PERSONAL', project_id: null }]),
    );
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBeNull();
    expect(result.current.error).toContain('项目作用域');
  });
});


describe('useProjectScope — 多个项目时按 env hint 选（2026-11-19 · T2/T3 实测）', () => {
  it('⚠️ **优先取 `VITE_PROJECT_ID` 指的那个项目**（不是「列表里的第一个」）', async () => {
    // ⚠️ 真后端通道的种子库里**有两个**项目 ⇒ ⇒ 「第一个」是**不确定**的
    // ⇒ ⇒ 真后端通道里会解析到**别的项目**（页面查的不是它 ⇒ 假绿）。
    vi.stubEnv('VITE_PROJECT_ID', 'proj-hinted');
    get.mockResolvedValue(
      ok([
        { workspace_id: 'ws-a', workspace_type: 'FORMAL', project_id: 'proj-other' },
        { workspace_id: 'ws-b', workspace_type: 'FORMAL', project_id: 'proj-hinted' },
      ]),
    );
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBe('proj-hinted');
    vi.unstubAllEnvs();
  });

  it('hint 指向的项目**不在**列表里 ⇒ ⇒ 退回「第一个有项目的」', async () => {
    vi.stubEnv('VITE_PROJECT_ID', 'proj-not-mine');
    get.mockResolvedValue(
      ok([{ workspace_id: 'ws-a', workspace_type: 'FORMAL', project_id: 'proj-other' }]),
    );
    const { result } = renderHook(() => useProjectScope());
    await waitFor(() => expect(result.current.loading).toBe(false));
    expect(result.current.projectId).toBe('proj-other');
    vi.unstubAllEnvs();
  });
});
