/**
 * 仪表盘的**守卫条件**（评审 #24 · P10-F · F2-T2）。
 *
 * ## 为什么有这个测试
 *
 * `DashboardPage` 原先的守卫条件是「**选了工作区**」⇒ ⇒ 而**个人 / 临时工作区
 * 按设计就没有项目**（`project_id` 恒为 `null`）⇒ ⇒ 原实现拿
 * `ws.project_id ?? <占位 id>` 兜底 ⇒ ⇒ **把占位 id 当真项目用** ⇒ ⇒
 * 两条 404（`/checklist/projects/<占位>` + `/completeness`）+ 控制台 error。
 *
 * ⚠️ 真后端通道今天**选不中**它（种子工作区的 `owner_id` 也是 NULL ⇒ 切换器
 * 按 `owner_id` 过滤 ⇒ 选不中）⇒ ⇒ 但**生产里是真缺陷**（mock 种子的
 * PERSONAL / TEMPORARY 工作区 `project_id` **就是 null**）⇒ ⇒ 修。
 *
 * ## 断言纪律
 *
 * - 断**后果**（面板渲不渲染 / 请求发没发 / 发的 `projectId` 是**哪个值**）
 *   不断「调用了哪个函数」。
 * - **两个方向都要断** —— 只断「不渲染」的话，「永远不渲染面板」也能过。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';

import DashboardPage from '../../src/pages/DashboardPage';
import { checklistApi, workspaceApi } from '../../src/api/sprint1';
import { useAuth } from '../../src/store/auth';
import type { Workspace } from '../../src/types/workspace';

/** 一个**真项目 id**（刻意与占位常量 `00000000-…-0001` 不同 ⇒ 才断得出「占位被当真值用」）。 */
const REAL_PROJECT_ID = '11111111-1111-1111-1111-111111111111';

const WS_NO_PROJECT: Workspace = {
  workspace_id: 'ws-no-project',
  workspace_type: 'PERSONAL',
  name: '无项目工作区',
  project_id: null,
  owner_id: '00000000-0000-0000-0000-0000000a11ce',
  created_at: '2026-01-01T00:00:00Z',
  last_active_at: null,
  retention_days: null,
  status: 'ACTIVE',
};

const WS_WITH_PROJECT: Workspace = {
  ...WS_NO_PROJECT,
  workspace_id: 'ws-with-project',
  workspace_type: 'FORMAL',
  name: '有项目工作区',
  project_id: REAL_PROJECT_ID,
};

function login(): void {
  useAuth.getState().setSession({
    access_token: 'token-alice',
    refresh_token: 'refresh-alice',
    username: 'alice',
    role: 'DESIGNER',
    user_id: '00000000-0000-0000-0000-0000000a11ce',
  });
}

/** 选中切换器里的某个工作区（antd Select 的选项在 portal 里）。 */
async function selectWorkspace(user: ReturnType<typeof userEvent.setup>, name: string) {
  await user.click(screen.getByRole('combobox'));
  const option = await screen.findByText(new RegExp(name));
  await user.click(option);
}

// ⚠️ **不用** `vi.restoreAllMocks()` ⇒ 它会把 `tests/setup.ts` 里给
// `window.matchMedia` 装的桩一起还原成「返回 undefined」⇒ ⇒ antd 的
// `responsiveObserver` 立刻抛 `Cannot destructure property 'matches'`。
// ⇒ ⇒ 本文件自己的 spy 在各用例内**显式** `mockRestore()`。
let spies: { mockRestore: () => void }[] = [];

beforeEach(() => {
  login();
  spies = [
    vi.spyOn(workspaceApi, 'list').mockResolvedValue([WS_NO_PROJECT, WS_WITH_PROJECT]),
    vi.spyOn(checklistApi, 'list').mockResolvedValue([]),
    vi.spyOn(checklistApi, 'completeness').mockResolvedValue({
      project_id: REAL_PROJECT_ID,
      total: 0,
      required_total: 0,
      required_verified: 0,
      required_assumed: 0,
      required_blocked: 0,
      completeness_pct: 0,
    } as never),
  ];
});

afterEach(() => {
  spies.forEach((s) => s.mockRestore());
  useAuth.getState().clearSession();
});

describe('仪表盘的守卫条件（评审 #24）', () => {
  it('选中的工作区**没有** project_id ⇒ 不渲染清单面板（不产生 404）', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await selectWorkspace(user, '无项目工作区');

    // ① 面板**不存在**
    expect(screen.queryByTestId('input-checklist-panel')).not.toBeInTheDocument();
    // ② **一个请求都没发**（面板没挂载 ⇒ 没有 404）
    await waitFor(() => expect(checklistApi.list).not.toHaveBeenCalled());
    expect(checklistApi.completeness).not.toHaveBeenCalled();
  });

  it('选中的工作区**有** project_id ⇒ 面板渲染且请求带**真项目 id**', async () => {
    const user = userEvent.setup();
    render(<DashboardPage />);

    await selectWorkspace(user, '有项目工作区');

    expect(await screen.findByTestId('input-checklist-panel')).toBeInTheDocument();
    await waitFor(() => expect(checklistApi.list).toHaveBeenCalledWith(REAL_PROJECT_ID));
    expect(checklistApi.completeness).toHaveBeenCalledWith(REAL_PROJECT_ID);
    // ⚠️ **占位常量被当真值用**是这个缺陷的病根 ⇒ ⇒ 断「不是占位」
    expect(checklistApi.list).not.toHaveBeenCalledWith(
      '00000000-0000-0000-0000-000000000001',
    );
  });

  it('**没选**工作区 ⇒ 不渲染清单面板（保持既有的「选择工作区后查看清单」）', async () => {
    render(<DashboardPage />);

    expect(screen.queryByTestId('input-checklist-panel')).not.toBeInTheDocument();
    expect(screen.getByText('选择工作区后查看清单')).toBeInTheDocument();
  });
});
