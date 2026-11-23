/**
 * `PmsPage` 测试（P10-H · T2 · TODO-195）。
 *
 * ## 本文件钉的规则
 *
 * 1. **真端点**：列表走 `GET /projects/{id}/pms` ⇒ ⇒ 页面自己取数
 *    （项目作用域来自顶栏的选择器）。
 * 2. **没有项目作用域 ⇒ 不发请求**（不发 ⇒ ⇒ 不会 404）。
 * 3. **送审走通用记录工作流**（`/records/PmsItem/{id}/submit-approval`）
 *    ⇒ ⇒ 只有 **DRAFT** 行给按钮。
 * 4. **新建走 `POST`**（后端建出来是 DRAFT）。
 */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

vi.mock('../../../src/api/client', () => ({
  api: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
  handleSessionOver: vi.fn(),
}));

vi.mock('../../../src/hooks/useProjectScope', () => ({
  useProjectScope: vi.fn(),
}));

import { PmsPage } from '../../../src/pages/pms/PmsPage';
import { useProjectScope } from '../../../src/hooks/useProjectScope';
import { api } from '../../../src/api/client';

const get = vi.mocked(api.get);
const post = vi.mocked(api.post);
const patch = vi.mocked(api.patch);
const scope = vi.mocked(useProjectScope);

const ITEMS = [
  {
    item_id: 'i1',
    project_id: 'p1',
    pms_no: 'PMS-001',
    description: '碳钢 A106',
    pms_class: 'CL1',
    hazard_level: 'HIGH',
    sign_status: 'CHECKED',
    record_hash: 'h1',
    created_by: null,
    created_at: null,
    updated_at: null,
  },
  {
    item_id: 'i2',
    project_id: 'p1',
    pms_no: 'PMS-002',
    description: '不锈钢 304',
    pms_class: 'CL2',
    hazard_level: 'LOW',
    sign_status: 'DRAFT',
    record_hash: 'h2',
    created_by: null,
    created_at: null,
    updated_at: null,
  },
];

beforeEach(() => {
  get.mockReset();
  post.mockReset();
  patch.mockReset();
  scope.mockReset();
  scope.mockReturnValue({
    projectId: 'p1',
    projects: [],
    loading: false,
    error: null,
    selectProject: vi.fn(),
  });
  get.mockResolvedValue({ data: { items: ITEMS, total: 2, limit: 100, offset: 0 } } as never);
  post.mockResolvedValue({ data: ITEMS[1] } as never);
  patch.mockResolvedValue({ data: ITEMS[1] } as never);
});

describe('PmsPage — 取数与渲染', () => {
  it('列表走 **真端点** `/projects/{id}/pms` ⇒ ⇒ 渲染两行', async () => {
    render(<PmsPage />);
    await waitFor(() => expect(screen.getAllByRole('row').length).toBeGreaterThan(2));
    expect(get).toHaveBeenCalledWith('/projects/p1/pms');
    expect(screen.getByText('PMS-001')).toBeTruthy();
    expect(screen.getByText('PMS-002')).toBeTruthy();
  });

  it('没有项目作用域 ⇒ 显示说明，**且不发请求**', async () => {
    scope.mockReturnValue({
      projectId: null,
      projects: [],
      loading: false,
      error: '当前身份没有可用的项目作用域',
      selectProject: vi.fn(),
    });
    render(<PmsPage />);
    await waitFor(() => expect(screen.getByTestId('pms-scope-error')).toBeTruthy());
    expect(get).not.toHaveBeenCalled();
  });

  it('危险等级渲染成 Tag', async () => {
    render(<PmsPage />);
    await waitFor(() => expect(screen.getAllByTestId('pms-hazard').length).toBe(2));
    expect(screen.getAllByTestId('pms-hazard')[0].textContent).toContain('HIGH');
  });
});

describe('PmsPage — 签署', () => {
  it('⚠️ **只有 DRAFT 行**给「提交审核」⇒ ⇒ 点它走通用工作流', async () => {
    render(<PmsPage />);
    await waitFor(() => expect(screen.getAllByTestId('pms-submit').length).toBe(1));
    fireEvent.click(screen.getByTestId('pms-submit'));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/records/PmsItem/i2/submit-approval',
        { reason: '提交审核' },
      ),
    );
  });
});

describe('PmsPage — 编辑', () => {
  it('编辑一行 ⇒ ⇒ `PATCH /projects/{id}/pms/{item_id}`（带**该行**的值）', async () => {
    render(<PmsPage />);
    await waitFor(() => expect(screen.getAllByTestId('pms-edit').length).toBe(1));
    fireEvent.click(screen.getAllByTestId('pms-edit')[0]);
    // ⚠️ **表单必须带出该行的值**（`setFieldsValue` 在 Modal 首次挂载**之前**调用
    // ⇒ ⇒ 忘了同步就���提交一份**空表单**）
    await waitFor(() => expect(screen.getByTestId('pms-form-no')).toBeTruthy());
    expect((screen.getByTestId('pms-form-no') as HTMLInputElement).value).toBe('PMS-002');
    fireEvent.change(screen.getByTestId('pms-form-desc'), { target: { value: '改过的描述' } });
    fireEvent.click(screen.getByRole('button', { name: /^(OK|确 定)$/ }));
    await waitFor(() =>
      expect(patch).toHaveBeenCalledWith(
        '/projects/p1/pms/i2',
        expect.objectContaining({ pms_no: 'PMS-002', description: '改过的描述' }),
      ),
    );
  });
});

describe('PmsPage — 新建', () => {
  it('新建 ⇒ ⇒ `POST /projects/{id}/pms`', async () => {
    render(<PmsPage />);
    await waitFor(() => expect(screen.getByTestId('pms-create')).toBeTruthy());
    fireEvent.click(screen.getByTestId('pms-create'));
    await waitFor(() => expect(screen.getByTestId('pms-form-no')).toBeTruthy());
    fireEvent.change(screen.getByTestId('pms-form-no'), { target: { value: 'PMS-NEW-001' } });
    fireEvent.click(screen.getByRole('button', { name: /^(OK|确 定)$/ }));
    await waitFor(() =>
      expect(post).toHaveBeenCalledWith(
        '/projects/p1/pms',
        expect.objectContaining({ pms_no: 'PMS-NEW-001' }),
      ),
    );
  });
});
