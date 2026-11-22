/**
 * `ProjectSelector` 测试（P10-H · T1 · TODO-194 · SPEC §3.2 TopBar「项目切换」）。
 *
 * ⚠️ antd Select 的 popup 渲染到 `document.body` ⇒ ⇒ 用
 * `mouseDown(.ant-select-selector)` 打开下拉，再点选项。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

vi.mock('../../../src/api/client', () => ({
  api: { get: vi.fn() },
  handleSessionOver: vi.fn(),
}));

import { ProjectSelector } from '../../../src/components/common/ProjectSelector';
import { useProjectScopeStore } from '../../../src/store/projectScope';
import { api } from '../../../src/api/client';
import { useAuth } from '../../../src/store/auth';

const get = vi.mocked(api.get);

function ok(data: unknown) {
  return { data } as never;
}

function serve(): void {
  get.mockImplementation((url: string) => {
    if (url === '/user-projects/me') {
      return Promise.resolve(
        ok([
          {
            id: 'grant-1',
            user_id: '00000000-0000-0000-0000-0000000a11ce',
            project_id: 'proj-a',
            role_in_project: 'PROJECT_LEAD',
            granted_by: null,
            granted_at: null,
            revoked_at: null,
            revoked_by: null,
          },
          {
            id: 'grant-2',
            user_id: '00000000-0000-0000-0000-0000000a11ce',
            project_id: 'proj-b',
            role_in_project: 'DESIGNER',
            granted_by: null,
            granted_at: null,
            revoked_at: null,
            revoked_by: null,
          },
        ]),
      );
    }
    if (url === '/workspaces') return Promise.resolve(ok([]));
    const id = url.replace('/projects/', '');
    const names: Record<string, string> = { 'proj-a': '乙烯项目', 'proj-b': '炼油项目' };
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
    return Promise.reject({ response: { status: 404 } } as never);
  });
}

async function openDropdown(): Promise<HTMLElement> {
  const select = document.querySelector('.ant-select-selector');
  if (select) fireEvent.mouseDown(select);
  await waitFor(() => {
    expect(document.querySelector('.ant-select-dropdown')).toBeTruthy();
  });
  return document.querySelector('.ant-select-dropdown') as HTMLElement;
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

describe('ProjectSelector — 渲染与切换', () => {
  it('下拉里列出**全部**候选项目（按名字）', async () => {
    serve();
    render(<ProjectSelector />);
    const dropdown = await openDropdown();
    expect(within(dropdown).getByText('乙烯项目')).toBeTruthy();
    expect(within(dropdown).getByText('炼油项目')).toBeTruthy();
  });

  it('选另一个项目 ⇒ ⇒ **全局作用域**跟着换（store 变）', async () => {
    serve();
    render(<ProjectSelector />);
    const dropdown = await openDropdown();
    const option = within(dropdown).getByText('炼油项目').closest('.ant-select-item');
    fireEvent.click(option!);
    await waitFor(() => expect(useProjectScopeStore.getState().currentProjectId).toBe('proj-b'));
  });

  it('显示我在该项目的角色（PROJECT_LEAD / DESIGNER）', async () => {
    serve();
    render(<ProjectSelector />);
    await waitFor(() => expect(screen.getByTestId('project-selector-role')).toBeTruthy());
    expect(screen.getByTestId('project-selector-role').textContent).toContain('PROJECT_LEAD');
  });
});

describe('ProjectSelector — 没有项目 / 出错', () => {
  it('没有候选 ⇒ 显示**原因**（**不静默**）', async () => {
    get.mockImplementation((url: string) => {
      if (url === '/user-projects/me') return Promise.resolve(ok([]));
      if (url === '/workspaces') return Promise.resolve(ok([]));
      return Promise.reject({ response: { status: 404 } } as never);
    });
    render(<ProjectSelector />);
    await waitFor(() => expect(screen.getByTestId('project-selector-error')).toBeTruthy());
    expect(screen.getByTestId('project-selector-error').textContent).toContain('项目作用域');
  });

  it('拉取失败 ⇒ 显示错误文案（不是空白）', async () => {
    get.mockRejectedValue({ response: { status: 500 } } as never);
    render(<ProjectSelector />);
    await waitFor(() => expect(screen.getByTestId('project-selector-error')).toBeTruthy());
  });
});
