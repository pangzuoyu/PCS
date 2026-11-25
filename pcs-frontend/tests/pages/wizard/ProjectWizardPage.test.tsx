/**
 * ProjectWizardPage —— **4 步向导**（P10-K · W-6 / W-15 · SPEC §7.5）。
 *
 * ## ⚠️ **整文件重写**（W-15）
 *
 * 原文件的 14 条断言**全部绑死在占位页的 props 契约**上
 * （`initialSteps` / `initialProjectName` / `onStepDone` / `onFinish`）
 * ⇒ ⇒ ⇒ 而新向导**不收 props**（4 步是页面自己的状态）
 * ⇒ ⇒ ⇒ ⇒ 原断言**全部失效** ⇒ ⇒ ⇒ ⇒ 重写（不是改）。
 *
 * ## 这组钉住什么
 *
 * 1. **4 步的顺序**（建项目 → 项目人员 → 选模板 → 确认）；
 * 2. **第 1 步建的项目一律 `DRAFT`**（人裁 2026-11-25）⇒ ⇒ ⇒ 中途弃单
 *    **可被识别**；
 * 3. **模板必选**（不选不能继续）；
 * 4. **第 2/3 步失败 ⇒ ⇒ ⇒ 项目保留 + 明确告知 + 两个出口**
 *    ⇒ ⇒ ⇒ **没有任何删除调用**；
 * 5. **第 4 步激活 + 去 BEDD** ⇒ ⇒ ⇒ 切当前项目 + 跳 `/bedd`。
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { ConfigProvider } from 'antd';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const create = vi.fn();
const setStatus = vi.fn();
const grant = vi.fn();
const listTemplates = vi.fn();
const apply = vi.fn();
const refresh = vi.fn();
const listWorkspaces = vi.fn();
const selectProject = vi.fn();

// ⚠️ **必须 spread 原模块** ⇒ ⇒ ⇒ `ProjectCreateForm` 还要 `UNIT_SYSTEMS`
//   与 `PRODUCT_CATEGORIES`（词表常量）⇒ ⇒ ⇒ 只 mock 三个函数 ⇒ ⇒ ⇒
//   ⇒ ⇒ ⇒ 「No UNIT_SYSTEMS export is defined on the mock」⇒ ⇒ ⇒ 全红。
vi.mock('../../../src/api/projects', async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  projectsApi: {
    create: (...a: unknown[]) => create(...a),
    setStatus: (...a: unknown[]) => setStatus(...a),
    listWorkspaces: (...a: unknown[]) => listWorkspaces(...a),
  },
  userProjectsApi: {
    grant: (...a: unknown[]) => grant(...a),
  },
  projectTemplatesApi: {
    list: (...a: unknown[]) => listTemplates(...a),
    apply: (...a: unknown[]) => apply(...a),
  },
}));

vi.mock('../../../src/store/projectScope', () => ({
  useProjectScopeStore: {
    getState: () => ({ refresh, selectProject }),
  },
}));

import { ProjectWizardPage } from '../../../src/pages/wizard/ProjectWizardPage';

function renderPage() {
  return render(
    <ConfigProvider>
      <MemoryRouter initialEntries={['/wizard']}>
        <Routes>
          <Route path="/wizard" element={<ProjectWizardPage />} />
          <Route path="/bedd" element={<div data-testid="bedd-page">BEDD</div>} />
          <Route path="/pms" element={<div data-testid="pms-page">PMS</div>} />
        </Routes>
      </MemoryRouter>
    </ConfigProvider>,
  );
}

/** 填完第 1 步并提交（**不驱动 antd Select** ⇒ ⇒ 只填文本字段）。 */
async function submitStep1(): Promise<void> {
  fireEvent.change(screen.getByTestId('project-no'), { target: { value: 'P-001' } });
  fireEvent.change(screen.getByTestId('project-name'), { target: { value: '测试项目' } });
  fireEvent.change(screen.getByTestId('project-owner-company'), {
    target: { value: 'PCS' },
  });
  fireEvent.change(screen.getByTestId('project-location'), { target: { value: '惠州' } });
  fireEvent.change(screen.getByTestId('project-type'), { target: { value: 'CHEMICAL' } });
  fireEvent.change(screen.getByTestId('project-design-phase'), {
    target: { value: 'FEED' },
  });
  // ⚠️ **工作区是必填** ⇒ ⇒ ⇒ 不选 ⇒ ⇒ ⇒ 表单校验不过 ⇒ ⇒ ⇒ 提交不了
  fireEvent.mouseDown(
    screen.getByTestId('project-workspace').querySelector(
      '.ant-select-selector',
    ) as HTMLElement,
  );
  const ws = await screen.findByTitle('测试工作区（FORMAL）');
  fireEvent.click(ws);
  fireEvent.click(screen.getByTestId('project-submit'));
  await waitFor(() => expect(create).toHaveBeenCalled());
}

beforeEach(() => {
  create.mockReset(); setStatus.mockReset(); grant.mockReset();
  listTemplates.mockReset(); apply.mockReset(); listWorkspaces.mockReset();
  listWorkspaces.mockResolvedValue([
    {
      workspace_id: 'ws-1',
      workspace_type: 'FORMAL',
      name: '测试工作区',
      project_id: null,
      created_at: '2026-11-25T00:00:00Z',
    },
  ]);
  refresh.mockReset(); selectProject.mockReset();
  create.mockResolvedValue({ project_id: 'p-new', project_no: 'P-001' });
  setStatus.mockResolvedValue({});
  grant.mockResolvedValue({});
  apply.mockResolvedValue({ segments: {} });
  listTemplates.mockResolvedValue([
    {
      template_id: 't-1',
      name: '通用项目模板',
      industry: 'CHEMICAL',
      version: '1.0.0',
      status: 'PUBLISHED',
      default_pipe_class_ids: [],
      checklist_item_count: 2,
      // ⚠️ **故意用 US** ⇒ ⇒ ⇒ 与表单默认的 SI **不一致**
      //   ⇒ ⇒ ⇒ 用来验 D1 的「**明确告知**」（不静默）
      unit_system: 'US',
    },
  ]);
  refresh.mockResolvedValue(undefined);
});

describe('ProjectWizardPage —— 4 步（P10-K · W-6）', () => {
  it('4 步的标题都摆出来', () => {
    renderPage();
    expect(screen.getByTestId('project-wizard-page')).toBeInTheDocument();
    expect(screen.getByTestId('wizard-steps')).toBeInTheDocument();
    // ⚠️ 「建项目」**出现两次**（步骤标题 + 提交按钮）⇒ ⇒ ⇒ 用 getAllByText
    expect(screen.getAllByText('建项目').length).toBeGreaterThan(0);
    expect(screen.getByText('项目人员')).toBeInTheDocument();
    expect(screen.getByText('选模板')).toBeInTheDocument();
    expect(screen.getByText('确认')).toBeInTheDocument();
  });

  it('⚠️ **第 1 步建的项目一律 `DRAFT`**（中途弃单可被识别）', async () => {
    renderPage();
    await submitStep1();
    const body = create.mock.calls[0][0] as { status?: string };
    expect(body.status).toBe('DRAFT');
  });

  it('建完项目 ⇒ 进第 2 步 ⇒ ⇒ ⇒ 并**刷新**项目作用域（新建的项目要出现在候选里）', async () => {
    renderPage();
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());
    expect(refresh).toHaveBeenCalled();
  });

  it('第 2 步：加人员 ⇒ ⇒ ⇒ 调 `grant` ⇒ ⇒ ⇒ 进第 3 步', async () => {
    renderPage();
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('wizard-grant-user-id'), {
      target: { value: 'u-1' },
    });
    fireEvent.click(screen.getByTestId('wizard-grant-submit'));
    await waitFor(() => expect(grant).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.getByTestId('wizard-template-select')).toBeInTheDocument(),
    );
  });

  it('⚠️ **第 2 步失败 ⇒ ⇒ ⇒ 项目保留 + 明确告知 + 两个出口（不删项目）', async () => {
    grant.mockRejectedValue({ response: { status: 403, data: { code: 'HTTP_403' } } });
    renderPage();
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());

    fireEvent.change(screen.getByTestId('wizard-grant-user-id'), {
      target: { value: 'u-1' },
    });
    fireEvent.click(screen.getByTestId('wizard-grant-submit'));
    await waitFor(() => expect(screen.getByTestId('wizard-partial')).toBeInTheDocument());
    expect(screen.getByTestId('wizard-partial').textContent).toContain('P-001');
    expect(screen.getByTestId('wizard-goto-project')).toBeInTheDocument();
    expect(screen.getByTestId('wizard-retry')).toBeInTheDocument();
    // ⚠️ **没有任何删除调用**（本仓没有删除项目的端点 ⇒ ⇒ ⇒ 也不引入）
    expect(create).toHaveBeenCalledTimes(1);
  });

  it('第 3 步：**模板必选**（不选不能继续）', async () => {
    renderPage();
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('wizard-skip-people'));
    await waitFor(() =>
      expect(screen.getByTestId('wizard-template-select')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('wizard-apply-template')).toBeDisabled();
  });

  it('第 3 步：应用模板 ⇒ ⇒ ⇒ 调 `apply-template`', async () => {
    renderPage();
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('wizard-skip-people'));
    await waitFor(() =>
      expect(screen.getByTestId('wizard-template-select')).toBeInTheDocument(),
    );
    // ⇒ ⇒ ⇒ 选中模板（antd Select ⇒ 驱动 popup）
    fireEvent.mouseDown(
      screen.getByTestId('wizard-template-select').querySelector(
        '.ant-select-selector',
      ) as HTMLElement,
    );
    const option = await screen.findByTitle('通用项目模板（v1.0.0）· 2 项清单');
    fireEvent.click(option);
    await waitFor(() =>
      expect(screen.getByTestId('wizard-apply-template')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('wizard-apply-template'));
    // ⚠️ **第三个参数 = 「单位制由谁决定」**（D1）⇒ ⇒ ⇒ 用户**没动过**单位制
    //   ⇒ ⇒ ⇒ 传 `TEMPLATE`（模板的默认值生效）
    await waitFor(() => expect(apply).toHaveBeenCalledWith('p-new', 't-1', 'TEMPLATE'));
  });

  it('第 4 步：激活 ⇒ ⇒ ⇒ 切当前项目 + 跳 BEDD', async () => {
    renderPage();
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('wizard-skip-people'));
    await waitFor(() =>
      expect(screen.getByTestId('wizard-template-select')).toBeInTheDocument(),
    );
    fireEvent.mouseDown(
      screen.getByTestId('wizard-template-select').querySelector(
        '.ant-select-selector',
      ) as HTMLElement,
    );
    const option = await screen.findByTitle('通用项目模板（v1.0.0）· 2 项清单');
    fireEvent.click(option);
    await waitFor(() =>
      expect(screen.getByTestId('wizard-apply-template')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('wizard-apply-template'));
    await waitFor(() => expect(screen.getByTestId('wizard-activate')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('wizard-activate'));
    await waitFor(() => expect(setStatus).toHaveBeenCalledWith('p-new', 'ACTIVE'));
    expect(selectProject).toHaveBeenCalledWith('p-new');
    await waitFor(() => expect(screen.getByTestId('bedd-page')).toBeInTheDocument());
  });

  it('⚠️ **D1 · 用户没动过单位制 ⇒ ⇒ ⇒ 传 `TEMPLATE`**（模板的默认值生效）', async () => {
    renderPage();
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('wizard-skip-people'));
    await waitFor(() =>
      expect(screen.getByTestId('wizard-template-select')).toBeInTheDocument(),
    );
    fireEvent.mouseDown(
      screen.getByTestId('wizard-template-select').querySelector(
        '.ant-select-selector',
      ) as HTMLElement,
    );
    const option = await screen.findByTitle('通用项目模板（v1.0.0）· 2 项清单');
    fireEvent.click(option);
    await waitFor(() =>
      expect(screen.getByTestId('wizard-apply-template')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('wizard-apply-template'));
    await waitFor(() => expect(apply).toHaveBeenCalled());
    expect(apply).toHaveBeenCalledWith('p-new', 't-1', 'TEMPLATE');
  });

  it('⚠️ **D1 · 用户动过单位制 ⇒ ⇒ ⇒ 传 `FORM`**（用户的显式选择优先）', async () => {
    renderPage();
    // ⇒ ⇒ ⇒ **先动单位制**（⇒ ⇒ ⇒ 「动没动过」= true）
    await waitFor(() => expect(screen.getByTestId('project-unit-system')).toBeTruthy());
    fireEvent.mouseDown(
      screen.getByTestId('project-unit-system').querySelector(
        '.ant-select-selector',
      ) as HTMLElement,
    );
    const us = await screen.findByTitle('US（psi · ℉ · ft）');
    fireEvent.click(us);
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('wizard-skip-people'));
    await waitFor(() =>
      expect(screen.getByTestId('wizard-template-select')).toBeInTheDocument(),
    );
    fireEvent.mouseDown(
      screen.getByTestId('wizard-template-select').querySelector(
        '.ant-select-selector',
      ) as HTMLElement,
    );
    const option = await screen.findByTitle('通用项目模板（v1.0.0）· 2 项清单');
    fireEvent.click(option);
    await waitFor(() =>
      expect(screen.getByTestId('wizard-apply-template')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('wizard-apply-template'));
    await waitFor(() => expect(apply).toHaveBeenCalled());
    expect(apply).toHaveBeenCalledWith('p-new', 't-1', 'FORM');
  });

  it('⚠️ **D1 · 两者不一致 ⇒ ⇒ ⇒ 明确告知**（不静默）', async () => {
    renderPage();
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('wizard-skip-people'));
    await waitFor(() =>
      expect(screen.getByTestId('wizard-template-select')).toBeInTheDocument(),
    );
    fireEvent.mouseDown(
      screen.getByTestId('wizard-template-select').querySelector(
        '.ant-select-selector',
      ) as HTMLElement,
    );
    const option = await screen.findByTitle('通用项目模板（v1.0.0）· 2 项清单');
    fireEvent.click(option);
    await waitFor(() =>
      expect(screen.getByTestId('wizard-apply-template')).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByTestId('wizard-apply-template'));
    await waitFor(() =>
      expect(screen.getByTestId('wizard-unit-system-notice')).toBeInTheDocument(),
    );
    const notice = screen.getByTestId('wizard-unit-system-notice').textContent ?? '';
    expect(notice).toContain('US');
    expect(notice).toContain('SI');
  });

  it('⚠️ **没有已发布模板 ⇒ ⇒ ⇒ 明确报错**（不静默空列表）', async () => {
    listTemplates.mockResolvedValue([]);
    renderPage();
    await submitStep1();
    await waitFor(() => expect(screen.getByTestId('wizard-grant-user-id')).toBeInTheDocument());
    fireEvent.click(screen.getByTestId('wizard-skip-people'));
    await waitFor(() =>
      expect(screen.getByTestId('wizard-templates-error')).toBeInTheDocument(),
    );
    expect(screen.getByTestId('wizard-templates-error').textContent).toContain('seed');
  });
});
