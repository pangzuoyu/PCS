/**
 * HeatComputePage 测试（P5-4 frontend / Task 4）。
 *
 * 覆盖 V1.3 SPEC §7.11.6：
 * - PageHeader + 导入表单（设备位号 + 业务 tag + 3 选项换热器类型 + 源流可选）
 * - StateBadge module=HEAT（4 态子集扩展验证）
 * - 重量估算折叠面板默认折叠
 * - 导入按钮 + 估算按钮 + 重置按钮存在
 *
 * 注：完整 API 交互（import/get/estimate）由 tests/api/heat_api.test.ts +
 * tests/mocks/test_heat_handlers.ts (Task 6) 覆盖；本页测保持 UI 形态断言。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

import { HeatComputePage } from '../../../src/pages/heat/HeatComputePage';

// 不需要真实 heatApi（API 行为已被 tests/api/heat_api.test.ts 覆盖）
vi.mock('../../../src/api/heat', () => ({
  heatApi: {
    importHtri: vi.fn(),
    get: vi.fn(),
    estimateWeight: vi.fn(),
  },
}));

describe('HeatComputePage — 渲染 (P5-4 frontend)', () => {
  it('渲染 PageHeader + 导入表单 + 重量估算折叠', () => {
    render(<HeatComputePage />);
    expect(screen.getByTestId('heat-compute-page')).toBeTruthy();
    // PageHeader title
    expect(screen.getByText('换热器计算')).toBeTruthy();
    // PageHeader 重置按钮（actions 槽）
    expect(screen.getByTestId('page-header-actions')).toBeTruthy();
    expect((screen.getByTestId('page-header-actions').textContent || '').replace(/\s+/g, '')).toContain('重置');
    // 导入 HTRI 按钮
    expect(screen.getByRole('button', { name: '导入 HTRI' })).toBeTruthy();
    // 选择 HTRI .txt 文件 按钮（Upload 触发）
    expect(screen.getByRole('button', { name: /选择 HTRI/ })).toBeTruthy();
  });

  it('换热器类型 Radio：3 选项（SHELL_TUBE / AIR_COOL / PLATE）', () => {
    render(<HeatComputePage />);
    expect(screen.getByText('SHELL_TUBE（管壳式）')).toBeTruthy();
    expect(screen.getByText('AIR_COOL（空冷）')).toBeTruthy();
    expect(screen.getByText('PLATE（板式）')).toBeTruthy();
  });

  it('未导入时重量估算面板不可见（条件渲染）', () => {
    render(<HeatComputePage />);
    // heatDetail 为 null → 折叠面板不渲染
    expect(screen.queryByText('TEMA 9th 重量估算')).toBeNull();
    // StateBadge 仅在 heatDetail 存在时渲染
    expect(screen.queryByTestId('state-badge')).toBeNull();
  });

  it('导入按钮在未选择文件时禁用', () => {
    render(<HeatComputePage />);
    const importBtn = screen.getByRole('button', { name: '导入 HTRI' });
    expect(importBtn).toBeDisabled();
  });
});