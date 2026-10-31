/**
 * ADMIN 建项目页（P9B-2 · 延后的 minor · Batch F）。
 *
 * ⚠️ **为什么要有这个页面**：T-1 只交付了**后端**的 `POST /projects` ⇒ 前端
 *    没有建项目的入口 ⇒ 项目建不出来 ⇒ 签署流程走不通（只能靠 mock 验证）。
 *
 * 守三件事：
 * 1. ⚠️ **8 个必填字段全都要有**（后端 `ProjectCreate`）—— 漏一个 ⇒ 422；
 * 2. ⚠️ **工作区必须选一个已存在的**（FK ⇒ 后端不建孤儿项目）；
 * 3. ⚠️ **建完要说「已绑矩阵」**（后端同事务绑 ⇒ 当场就能送审）—— 不说 ⇒
 *    用户以为还要去矩阵页手动绑一次。
 */
import { describe, it, expect, beforeAll, afterAll, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { http, HttpResponse } from 'msw';
import { setupServer } from 'msw/node';

import { ProjectAdminPage } from '../../../src/pages/admin/ProjectAdminPage';
import { useAuth } from '../../../src/store/auth';

const WORKSPACES = [
  {
    workspace_id: 'ws-formal-001',
    workspace_type: 'FORMAL',
    name: '30 万吨乙烯项目',
    project_id: null,
    owner_id: null,
    created_at: '2026-08-01T09:00:00Z',
    last_active_at: '2026-09-16T03:00:00Z',
    retention_days: null,
    status: 'ACTIVE',
  },
  {
    // 评审 #4：PERSONAL 工作区建的项目永远送不了审（后端 403）⇒ 不许出现在选项里
    workspace_id: 'ws-personal-001',
    workspace_type: 'PERSONAL',
    name: '张三的草稿区',
    project_id: null,
    owner_id: null,
    created_at: '2026-08-01T09:00:00Z',
    last_active_at: '2026-09-16T03:00:00Z',
    retention_days: 90,
    status: 'ACTIVE',
  },
];

let createCalls = 0;
let lastBody: Record<string, unknown> | null = null;
/** 建项目的失败（测试按需改写）。 */
let createStatus = 201;

const server = setupServer(
  http.get('/api/v1/workspaces', () => HttpResponse.json(WORKSPACES)),
  http.post('/api/v1/projects', async ({ request }) => {
    createCalls += 1;
    lastBody = (await request.json()) as Record<string, unknown>;
    if (createStatus === 422) {
      return HttpResponse.json(
        { code: 'VALIDATION_ERROR', message: 'project_no 已存在' },
        { status: 422 },
      );
    }
    return HttpResponse.json(
      {
        project_id: 'p-new-1',
        project_no: String(lastBody['project_no']),
        project_name: String(lastBody['project_name']),
        project_type: String(lastBody['project_type']),
        product_category: String(lastBody['product_category']),
        electricity_value_type: 'AC_380V',
      },
      { status: 201 },
    );
  }),
);

describe('ProjectAdminPage —— 建项目', () => {
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterAll(() => server.close());
  beforeEach(() => {
    createCalls = 0;
    lastBody = null;
    createStatus = 201;
    useAuth.setState({ role: 'SYSTEM_ADMIN', accessToken: 'test-token' });
  });

  /** 填完 8 个必填字段 + 选工作区。 */
  async function fillForm(): Promise<void> {
    await waitFor(() => expect(screen.getByTestId('project-no')).toBeTruthy());
    fireEvent.change(screen.getByTestId('project-no'), { target: { value: 'P-2026-01' } });
    fireEvent.change(screen.getByTestId('project-name'), { target: { value: '新项目' } });
    fireEvent.change(screen.getByTestId('project-owner-company'), {
      target: { value: '某某化工' },
    });
    fireEvent.change(screen.getByTestId('project-location'), { target: { value: '宁波' } });
    fireEvent.change(screen.getByTestId('project-type'), { target: { value: 'ENGINEERING' } });
    fireEvent.change(screen.getByTestId('project-design-phase'), { target: { value: 'FEED' } });
    fireEvent.change(screen.getByTestId('project-unit-system'), { target: { value: 'SI' } });
    // ⚠️ 选工作区（antd Select ⇒ 展开下拉再点选项）
    const select = screen.getByTestId('project-workspace');
    fireEvent.mouseDown(select.querySelector('.ant-select-selector') as HTMLElement);
    await waitFor(() => expect(document.querySelector('.ant-select-dropdown')).toBeTruthy());
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    const opt = within(dropdown).getByText(/30 万吨乙烯项目/).closest('.ant-select-item');
    fireEvent.click(opt as HTMLElement);
  }

  it('⚠️ 评审 #4：工作区下拉**只列 FORMAL**（PERSONAL 建的项目永远送不了审）', async () => {
    render(<ProjectAdminPage />);
    const select = await waitFor(() => screen.getByTestId('project-workspace'));
    fireEvent.mouseDown(select.querySelector('.ant-select-selector') as HTMLElement);
    const dropdown = await waitFor(() =>
      document.querySelector('.ant-select-dropdown'),
    );
    await waitFor(() =>
      expect(within(dropdown as HTMLElement).getByText(/30 万吨乙烯项目/)).toBeTruthy(),
    );
    // PERSONAL 不许出现
    expect(
      within(dropdown as HTMLElement).queryByText(/张三的草稿区/),
    ).toBeNull();
  });

  it('⚠️ 建项目 ⇒ POST 带**全部必填字段** + 工作区', async () => {
    render(<ProjectAdminPage />);
    await fillForm();

    fireEvent.click(screen.getByTestId('project-submit'));

    await waitFor(() => expect(createCalls).toBe(1));
    expect(lastBody).toMatchObject({
      project_no: 'P-2026-01',
      project_name: '新项目',
      owner_company: '某某化工',
      location: '宁波',
      project_type: 'ENGINEERING',
      design_phase: 'FEED',
      unit_system: 'SI',
      workspace_id: 'ws-formal-001',
    });
  });

  it('⚠️ 建成功 ⇒ 说「已自动绑定签署矩阵，可以提交批准了」', async () => {
    render(<ProjectAdminPage />);
    await fillForm();

    fireEvent.click(screen.getByTestId('project-submit'));

    await waitFor(() => expect(screen.getByTestId('project-notice')).toBeTruthy());
    const notice = screen.getByTestId('project-notice').textContent ?? '';
    expect(notice).toContain('P-2026-01');
    // ⚠️ 后端同事务绑矩阵 ⇒ 页面必须**说清楚**「不用再去矩阵页手动绑」
    expect(notice).toContain('签署矩阵');
    expect(notice).toContain('提交批准');
  });

  it('⚠️ 失败（422）⇒ 显示后端原文，**不得**显示成功', async () => {
    createStatus = 422;
    render(<ProjectAdminPage />);
    await fillForm();

    fireEvent.click(screen.getByTestId('project-submit'));

    await waitFor(() => expect(screen.getByTestId('project-error')).toBeTruthy());
    expect(screen.getByTestId('project-error').textContent).toContain('project_no 已存在');
    expect(screen.queryByTestId('project-notice')).toBeNull();
  });

  it('⚠️ 漏填必填 ⇒ **不发请求**（前端先拦）', async () => {
    render(<ProjectAdminPage />);
    await waitFor(() => expect(screen.getByTestId('project-no')).toBeTruthy());

    fireEvent.click(screen.getByTestId('project-submit'));

    await waitFor(() => expect(screen.getByText('项目编号必填')).toBeTruthy());
    expect(createCalls).toBe(0);
  });
});
