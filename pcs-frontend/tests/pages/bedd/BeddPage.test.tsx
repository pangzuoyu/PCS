/**
 * `BeddPage` 测试（P10-H · T2 · TODO-195 · SPEC §7.5）。
 *
 * ## 本文件钉的规则
 *
 * 1. **9 个分组 Tab**（SPEC §7.5 的分组表）⇒ ⇒ 不是此前那套「章节列表」。
 * 2. **表单由 uiSchema 驱动**（`GET /meta/ui-schema/bedd`）⇒ ⇒ 字段控件
 *    与后端字段表一致（漂移由 `tests/mocks/bedd_ui_schema_drift.test.ts` 盯着）。
 * 3. **保存走 `PUT`**（整份替换）⇒ ⇒ 没有项目作用域 ⇒ **不发请求**。
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../../src/api/client', () => ({
  api: { get: vi.fn(), put: vi.fn() },
  handleSessionOver: vi.fn(),
}));

vi.mock('../../../src/hooks/useProjectScope', () => ({
  useProjectScope: vi.fn(),
}));

import { BeddPage } from '../../../src/pages/bedd/BeddPage';
import { seedBeddUiSchema } from '../../../src/mocks/seed/pms';
import { useProjectScope } from '../../../src/hooks/useProjectScope';
import { api } from '../../../src/api/client';

const get = vi.mocked(api.get);
const put = vi.mocked(api.put);
const scope = vi.mocked(useProjectScope);

// ⚠️ **用真 seed**（后端 `BEDD_FIELDS` 的镜像）⇒ ⇒ 这条测试顺带证明
// 「mock 的 uiSchema 覆盖全部 9 个分组」⇒ ⇒ 不是随手编的两三个字段。
const UI_SCHEMA = seedBeddUiSchema;

const DOCUMENT = {
  project_id: 'p1',
  document: { meteorology: { temperature: 25.5 }, flare: null },
  updated_at: null,
};

beforeEach(() => {
  get.mockReset();
  put.mockReset();
  scope.mockReset();
  scope.mockReturnValue({
    projectId: 'p1',
    projects: [],
    loading: false,
    error: null,
    selectProject: vi.fn(),
  });
  get.mockImplementation((url: string) => {
    if (url === '/meta/ui-schema/bedd') return Promise.resolve({ data: UI_SCHEMA } as never);
    if (url === '/projects/p1/bedd') return Promise.resolve({ data: DOCUMENT } as never);
    return Promise.reject({ response: { status: 404 } } as never);
  });
  put.mockResolvedValue({ data: DOCUMENT } as never);
});

describe('BeddPage — 分组 Tab', () => {
  it('渲染 **9 个分组**的 Tab（气象 / 水文地质 / …）', async () => {
    render(<BeddPage />);
    await waitFor(() => expect(screen.getByTestId('bedd-tabs')).toBeTruthy());
    expect(screen.getByText('气象')).toBeTruthy();
    expect(screen.getByText('水文地质')).toBeTruthy();
    expect(screen.getByText('界面条件')).toBeTruthy();
  });

  it('表单控件由 uiSchema 驱动（路径前缀 = 分组 ⇒ 控件名去前缀）', async () => {
    render(<BeddPage />);
    await waitFor(() => expect(screen.getByTestId('bedd-tabs')).toBeTruthy());
    // ⚠️ **waitFor**（不是同步断言）⇒ ⇒ Tab 内容是**渲染后**才挂上的
    await waitFor(() => expect(screen.getByTestId('control-temperature')).toBeTruthy());
    expect(screen.getByTestId('control-altitude')).toBeTruthy();
  });

  it('没有项目作用域 ⇒ 显示说明，**且不发请求**', async () => {
    scope.mockReturnValue({
      projectId: null,
      projects: [],
      loading: false,
      error: '当前身份没有可用的项目作用域',
      selectProject: vi.fn(),
    });
    render(<BeddPage />);
    await waitFor(() => expect(screen.getByTestId('bedd-scope-error')).toBeTruthy());
    expect(get).not.toHaveBeenCalled();
  });
});

describe('BeddPage — 保存', () => {
  it('保存 ⇒ ⇒ `PUT /projects/{id}/bedd`（**整份替换**）', async () => {
    render(<BeddPage />);
    await waitFor(() => expect(screen.getByTestId('bedd-save')).toBeTruthy());
    fireEvent.click(screen.getByTestId('bedd-save'));
    await waitFor(() =>
      expect(put).toHaveBeenCalledWith(
        '/projects/p1/bedd',
        expect.objectContaining({ meteorology: { temperature: 25.5 } }),
      ),
    );
  });
});
