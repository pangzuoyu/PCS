/**
 * ReportExecutePage 的**「执行时选项目」**行为（P10-J-T1 · 公司级模板）。
 *
 * ## 为什么这组要写
 *
 * 公司级模板（`project_id IS NULL`）执行时**必须**选一个项目 ⇒ ⇒ ⇒ 这是
 * 「以为跑的是 A 其实是 B」类事故的**唯一一道闸** ⇒ ⇒ ⇒ 闸的三个面都要钉住：
 *
 * 1. **闸在**：公司级模板 ⇒ ⇒ 「选项目」下拉出现 ⇒ ⇒ **没选 ⇒ 执行按钮禁用**
 *    ⇒ ⇒ ⇒ 不给「点了才 400」的体验；
 * 2. **闸认得对**：选了项目 ⇒ ⇒ **请求 body 里带的就是那个项目**
 *    ⇒ ⇒ ⇒ 项目级模板**不带**（带了不一致的 ⇒ ⇒ ⇒ 后端 400 拒绝）；
 * 3. **闸看得见**：定义下拉里**标出作用域** ⇒ ⇒ ⇒ 否则用户选中公司级模板时
 *    ⇒ ⇒ ⇒ 界面**没有任何提示**说明它需要再选一个项目。
 *
 * ## 观测点
 *
 * 用**请求体**而不是 UI 文案作主要断言 —— 文案是后果，body 才是契约。
 *
 * ⚠️ **antd Select 的 placeholder 不是 `<input placeholder>`** ⇒ ⇒ ⇒
 * `getByPlaceholderText` **找不到**它 ⇒ ⇒ ⇒ 它渲染成
 * `.ant-select-selection-placeholder` 的**文本** ⇒ ⇒ ⇒ 这里用
 * `placeholderTexts()` 取。驱动下拉也按仓库既有做法
 * （`tests/components/common/ProjectSelector.test.tsx`）：
 * `mouseDown(.ant-select-selector)` ⇒ 再点 popup 里的选项。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, act, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const execute = vi.fn();
const executionStatus = vi.fn();
const datasources = vi.fn();
const get = vi.fn();
const list = vi.fn();
const executableProjects = vi.fn();

vi.mock('../../../src/api/reportBuilder', () => ({
  errorMessage: (e: unknown) => String((e as { message?: string })?.message ?? '出错了'),
  reportBuilderApi: {
    execute: (...a: unknown[]) => execute(...a),
    executionStatus: (...a: unknown[]) => executionStatus(...a),
    datasources: (...a: unknown[]) => datasources(...a),
    get: (...a: unknown[]) => get(...a),
    list: (...a: unknown[]) => list(...a),
  },
}));

vi.mock('../../../src/api/projects', () => ({
  projectsApi: {
    executableProjects: (...a: unknown[]) => executableProjects(...a),
  },
}));

import { ReportExecutePage } from '../../../src/pages/report/ReportExecutePage';

/** 页面用 useParams/useNavigate —— 没有 Router 直接渲染会抛 invariant。 */
function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/report-builder/executions/d1']}>
      <Routes>
        <Route path="/report-builder/executions/:defId"
               element={<ReportExecutePage />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function flush(times = 6) {
  for (let i = 0; i < times; i += 1) {
    await act(async () => { await Promise.resolve(); });
  }
}

/** 详情（`ReportDefinitionOut`）—— `project_id: null` = 公司级模板。 */
function detail(projectId: string | null) {
  return {
    def_id: 'd1', name: '泵数据表', version: '0.1.0', status: 'PUBLISHED',
    project_id: projectId,
    output_format: 'pdf', max_rows: 10000,
    definition_json: {
      DataSources: [{ source: 'PUMP_RESULTS' }],
      SelectedFields: [{ source: 'PUMP_RESULTS', field: 'tag_number',
                         alias: '位号', order: 0, visible: true }],
      FilterConditions: [], SortBy: [], MaxRows: 10000,
      OutputFormat: 'pdf', detailLevel: 'BASIC',
    },
  };
}

/** 当前渲染出来的 Select placeholder 文本（antd 不是 input placeholder）。 */
function placeholderTexts(): string[] {
  return [...document.querySelectorAll('.ant-select-selection-placeholder')]
    .map((e) => e.textContent ?? '');
}

/** 打开第 N 个 antd Select 的下拉（0 = 定义，1 = 选项目）。 */
async function openSelect(index: number): Promise<HTMLElement> {
  const target = document.querySelectorAll('.ant-select-selector')[index];
  if (!target) throw new Error(`页面上没有第 ${index} 个 Select`);
  await act(async () => { fireEvent.mouseDown(target); });
  await waitFor(() => {
    expect(document.querySelector('.ant-select-dropdown:not(.ant-select-dropdown-hidden)'))
      .toBeTruthy();
  });
  return document.querySelector(
    '.ant-select-dropdown:not(.ant-select-dropdown-hidden)',
  ) as HTMLElement;
}

/** 打开第 N 个 Select 并选中一个选项（按选项文字点）。 */
async function pickOption(index: number, optionText: string | RegExp) {
  const dropdown = await openSelect(index);
  const node = within(dropdown).getByText(optionText);
  const option = node.closest('.ant-select-item');
  await act(async () => { fireEvent.click(option as HTMLElement); });
  await flush(2);
}

/**
 * 「执行」按钮（页面上只有一个，别的按钮文案是「返回列表」/「下载」）。
 *
 * ⚠️ **用正则不用全等**：按钮里带 `PlayCircleOutlined` 图标 ⇒ ⇒ 图标的
 * `aria-label`（"play-circle"）会**进**可访问名 ⇒ ⇒ 全等 "执行" 匹配不到。
 */
function executeButton(): HTMLButtonElement {
  return screen.getByRole('button', { name: /执行/ }) as HTMLButtonElement;
}

beforeEach(() => {
  execute.mockReset(); executionStatus.mockReset();
  datasources.mockReset(); list.mockReset(); get.mockReset();
  executableProjects.mockReset();
  datasources.mockResolvedValue({ datasources: [] });
  list.mockResolvedValue({
    items: [{ def_id: 'd1', name: '泵数据表', version: '0.1.0', status: 'PUBLISHED',
              project_id: null }],
  });
  get.mockResolvedValue(detail(null));
  execute.mockResolvedValue({ task_id: 'task-1' });
  executableProjects.mockResolvedValue([
    { project_id: 'p1', project_name: '项目一' },
    { project_id: 'p2', project_name: '项目二' },
  ]);
});

// ⚠️ **不用** `vi.restoreAllMocks()` ⇒ 它会把 `tests/setup.ts` 里给
// `window.matchMedia` 装的桩一起还原成「返回 undefined」⇒ ⇒ antd 的
// `responsiveObserver` 立刻抛 `Cannot destructure property 'matches'`。
// （与 `tests/pages/routeWrappers.fetch.test.tsx` 同一处置。）
afterEach(() => { vi.unstubAllGlobals(); });

describe('ReportExecutePage — 公司级模板「执行时选项目」（P10-J-T1）', () => {
  it('公司级模板：出现「选项目」下拉，且没选时执行按钮禁用', async () => {
    renderPage();
    await flush();

    // 下拉出现
    await waitFor(() => {
      expect(placeholderTexts()).toContain('选一个要执行的项目');
    });
    // ⚠️ 候选来自**「我能对它执行的项目」**（普通用户 = 自己的授权行）
    expect(executableProjects).toHaveBeenCalledWith(false);

    // ⚠️ **必选、无默认** ⇒ ⇒ 没选 ⇒ 执行按钮禁用
    expect(executeButton().disabled).toBe(true);
  });

  it('公司级模板：选了项目 ⇒ 执行按钮解禁，且请求 body 带的就是那个项目', async () => {
    renderPage();
    await flush();
    await waitFor(() => {
      expect(placeholderTexts()).toContain('选一个要执行的项目');
    });

    await pickOption(1, '项目二');

    expect(executeButton().disabled).toBe(false);

    await act(async () => { fireEvent.click(executeButton()); });
    await flush();

    expect(execute).toHaveBeenCalledTimes(1);
    const body = execute.mock.calls[0][1] as { project_id?: string };
    expect(body.project_id).toBe('p2');
  });

  it('项目级模板：**不出现**「选项目」下拉，请求 body **不带** project_id', async () => {
    list.mockResolvedValue({
      items: [{ def_id: 'd1', name: '泵数据表', version: '0.1.0', status: 'PUBLISHED',
                project_id: 'p1' }],
    });
    get.mockResolvedValue(detail('p1'));

    renderPage();
    await flush();
    await waitFor(() => { expect(executeButton().disabled).toBe(false); });

    expect(placeholderTexts()).not.toContain('选一个要执行的项目');
    expect(executableProjects).not.toHaveBeenCalled();

    await act(async () => { fireEvent.click(executeButton()); });
    await flush();

    const body = execute.mock.calls[0][1] as { project_id?: string };
    expect(body.project_id).toBeUndefined();
  });

  it('定义下拉里**标出作用域**（公司级 / 项目级）—— 否则用户不知道为什么要多选一个项目', async () => {
    renderPage();
    await flush();

    const dropdown = await openSelect(0);
    expect(within(dropdown).getByText(/公司级/)).toBeTruthy();
  });

  it('后端回 400 REPORT_PROJECT_SCOPE_REQUIRED ⇒ 显示「该干什么」的提示', async () => {
    execute.mockRejectedValue({
      response: {
        status: 400,
        data: {
          code: 'REPORT_PROJECT_SCOPE_REQUIRED',
          message: '该报表定义未绑定项目（公司级模板），执行时必须指定 project_id。',
        },
      },
    });

    renderPage();
    await flush();
    await waitFor(() => {
      expect(placeholderTexts()).toContain('选一个要执行的项目');
    });
    await pickOption(1, '项目一');

    await act(async () => { fireEvent.click(executeButton()); });
    await flush();

    expect(document.body.textContent).toContain('公司级模板执行时必须选一个项目');
  });
});
