/**
 * EquipmentListPage 测试（P10-C · T3 · TODO-157）。
 *
 * ## 本文件钉的规则
 *
 * 1. **种子设备可见**（`132-P-101A/B` —— 与后端种子
 *    `seed_e2e_flows.py::FLOW_EQUIPMENT_TAG` 逐字一致）。
 * 2. **请求带 `project_id`**（设备台账是**项目作用域**的数据 ⇒ ⇒ 不带项目
 *    ⇒ 后端返回的是「全部项目」的设备 ⇒ ⇒ 跨项目读）。
 * 3. **类型过滤是前端的**（后端 `GET /equipment-list` **没有** type_code 过滤）
 *    ⇒ ⇒ 不编一个后端不支持的参数。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

import { EquipmentListPage } from '../../../src/pages/equip/EquipmentListPage';
import { equipListApi } from '../../../src/api/equipList';
import { useProjectScope } from '../../../src/hooks/useProjectScope';
import { seedEquipmentList } from '../../../src/mocks/seed/equipment';

vi.mock('../../../src/api/equipList', () => ({
  equipListApi: { list: vi.fn(), get: vi.fn() },
}));

vi.mock('../../../src/hooks/useProjectScope', () => ({
  useProjectScope: vi.fn(),
}));

const list = vi.mocked(equipListApi.list);
const scope = vi.mocked(useProjectScope);

beforeEach(() => {
  list.mockReset();
  scope.mockReset();
  scope.mockReturnValue({
    projectId: '00000000-0000-0000-0000-000000000001',
    projects: [],
    loading: false,
    error: null,
    selectProject: vi.fn(),
  });
  list.mockResolvedValue({
    items: seedEquipmentList,
    total: seedEquipmentList.length,
    limit: 200,
    offset: 0,
  });
});

describe('EquipmentListPage — 渲染 (P10-C · T3)', () => {
  it('渲染表格 + **种子设备 132-P-101A/B 可见**', async () => {
    render(<EquipmentListPage />);
    await waitFor(() => {
      expect(document.querySelectorAll('[data-testid="equipment-row"]').length).toBe(3);
    });
    expect(screen.getByText('132-P-101A/B')).toBeTruthy();
    expect(screen.getByText('E2E 种子泵')).toBeTruthy();
  });

  it('⚠️ **请求带 project_id**（设备台账是项目作用域的数据）', async () => {
    render(<EquipmentListPage />);
    await waitFor(() => expect(list).toHaveBeenCalled());
    expect(list).toHaveBeenCalledWith(
      expect.objectContaining({ project_id: '00000000-0000-0000-0000-000000000001' }),
    );
  });

  it('计数 Tag 显示「过滤后 / 总数」', async () => {
    render(<EquipmentListPage />);
    await waitFor(() => {
      expect(screen.getByTestId('equipment-count').textContent).toBe('3 / 3');
    });
  });
});

describe('EquipmentListPage — 筛选', () => {
  it('按类型过滤（前端过滤）→ 只剩 PUMP 一行', async () => {
    render(<EquipmentListPage />);
    await waitFor(() => {
      expect(document.querySelectorAll('[data-testid="equipment-row"]').length).toBe(3);
    });
    fireEvent.change(screen.getByTestId('equipment-filter-type'), {
      target: { value: 'PUMP' },
    });
    await waitFor(() => {
      expect(document.querySelectorAll('[data-testid="equipment-row"]').length).toBe(1);
    });
    expect(screen.getByText('132-P-101A/B')).toBeTruthy();
  });

  it('按来源筛选（**后端**过滤）⇒ 请求带 source_module', async () => {
    render(<EquipmentListPage />);
    await waitFor(() => expect(list).toHaveBeenCalled());
    // ⚠️ antd Select 的弹层走 portal ⇒ 在 `.ant-select-dropdown` 里找选项
    const box = screen.getByTestId('equipment-filter-source');
    const selector = box.querySelector('.ant-select-selector') as HTMLElement;
    fireEvent.mouseDown(selector);
    await waitFor(() => expect(document.querySelector('.ant-select-dropdown')).toBeTruthy());
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    const option = within(dropdown).getByText('HEAT').closest('.ant-select-item') as HTMLElement;
    fireEvent.click(option);
    await waitFor(() => {
      expect(list).toHaveBeenLastCalledWith(expect.objectContaining({ source_module: 'HEAT' }));
    });
  });
});

describe('EquipmentListPage — 失败与作用域', () => {
  it('加载失败 ⇒ 显示错误', async () => {
    list.mockRejectedValue({ response: { status: 404, data: { code: 'HTTP_404', message: 'not found' } } });
    render(<EquipmentListPage />);
    await waitFor(() => {
      expect(screen.getByTestId('equipment-list-error')).toBeTruthy();
    });
  });

  it('没有项目作用域 ⇒ 显示说明，**且不发请求**', async () => {
    scope.mockReturnValue({
      projectId: null,
      projects: [],
      loading: false,
      error: '当前身份没有可用的项目作用域',
      selectProject: vi.fn(),
    });
    render(<EquipmentListPage />);
    expect(screen.getByTestId('equipment-list-scope-error')).toBeTruthy();
    expect(list).not.toHaveBeenCalled();
  });
});
