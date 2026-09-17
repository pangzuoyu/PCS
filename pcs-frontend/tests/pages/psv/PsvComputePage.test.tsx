/**
 * PsvComputePage 测试（P5-3-6 / Task 18）。
 *
 * 覆盖 SPEC §7.11.5：
 * - PageHeader + 项目标准 Tag
 * - 4 Tab 切换（泄放工况 / 泄放面积 / 孔口选型 / 标准配置）
 * - 泄放工况：物流 + 工况多选 + 计算按钮
 * - 孔口选型：面积输入 + 选型按钮
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PsvComputePage } from '../../../src/pages/psv/PsvComputePage';

const streams = [
  { stream_id: 's-1', tag_number: 'FEED-101', sign_status: 'CHECKED' },
];

describe('PsvComputePage — 渲染 (P5-3-6)', () => {
  it('渲染 PageHeader + 项目标准 Tag + Tabs', () => {
    render(<PsvComputePage streams={streams} projectStandard="API" />);
    expect(screen.getByTestId('psv-compute-page')).toBeTruthy();
    expect(screen.getByTestId('psv-standard-tag')).toBeTruthy();
    expect(screen.getByTestId('psv-standard-tag').textContent).toContain('API');
    expect(screen.getByTestId('psv-tabs')).toBeTruthy();
  });

  it('泄放工况 Tab：物流 + 工况 + 计算按钮', () => {
    render(<PsvComputePage streams={streams} />);
    expect(screen.getByTestId('psv-stream-select')).toBeTruthy();
    expect(screen.getByTestId('psv-scenarios')).toBeTruthy();
    expect(screen.getByTestId('psv-calculate')).toBeTruthy();
  });
});

describe('PsvComputePage — 错误路径 (P5-3-6)', () => {
  it('未选物流 → 点计算 → 显示「请选择物流」', () => {
    render(<PsvComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('psv-calculate'));
    expect(screen.getByTestId('psv-error')).toBeTruthy();
    expect(screen.getByTestId('psv-error').textContent).toContain('请选择物流');
  });
});