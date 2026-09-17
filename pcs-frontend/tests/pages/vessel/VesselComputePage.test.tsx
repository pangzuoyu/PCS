/**
 * VesselComputePage 测试（P5-1-4 / Task 5）。
 *
 * 覆盖 SPEC §7.11.3：
 * - PageHeader + 输入表单 + 结果占位
 * - 容器类型 Radio：3 选项（VERTICAL / HORIZONTAL / WITH_DEMISTER）
 * - 计算按钮触发（未选物流 → 错误）
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { VesselComputePage } from '../../../src/pages/vessel/VesselComputePage';

const streams = [
  { stream_id: 's-1', tag_number: 'FEED-101', sign_status: 'CHECKED' },
  { stream_id: 's-2', tag_number: 'PROD-201', sign_status: 'DRAFT' },
];

describe('VesselComputePage — 渲染 (P5-1-4)', () => {
  it('渲染 PageHeader + 输入表单 + 结果占位', () => {
    render(<VesselComputePage streams={streams} />);
    expect(screen.getByTestId('vessel-compute-page')).toBeTruthy();
    expect(screen.getByTestId('vessel-stream-select')).toBeTruthy();
    expect(screen.getByTestId('vessel-type')).toBeTruthy();
    expect(screen.getByTestId('vessel-result-card')).toBeTruthy();
  });

  it('容器类型 Radio：3 选项', () => {
    render(<VesselComputePage streams={streams} />);
    expect(document.body.textContent).toContain('立式容器');
    expect(document.body.textContent).toContain('卧式容器');
    expect(document.body.textContent).toContain('带除沫器');
  });

  it('默认 vessel_type=VERTICAL 时 ρ/流量/K 输入可见', () => {
    render(<VesselComputePage streams={streams} />);
    expect(screen.getByTestId('vessel-rho-L')).toBeTruthy();
    expect(screen.getByTestId('vessel-rho-V')).toBeTruthy();
    expect(screen.getByTestId('vessel-q-L')).toBeTruthy();
    expect(screen.getByTestId('vessel-q-V')).toBeTruthy();
    expect(screen.getByTestId('vessel-K')).toBeTruthy();
  });
});

describe('VesselComputePage — 错误路径 (P5-1-4)', () => {
  it('未选物流 → 点计算 → 显示「请选择物流」', () => {
    render(<VesselComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('vessel-calculate'));
    expect(screen.getByTestId('vessel-error')).toBeTruthy();
    expect(screen.getByTestId('vessel-error').textContent).toContain('请选择物流');
  });
});