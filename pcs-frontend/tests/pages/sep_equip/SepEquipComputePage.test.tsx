/**
 * SepEquipComputePage 测试（P5-2-4 / Task 12）。
 *
 * 覆盖 SPEC §7.11.4：
 * - PageHeader + 输入表单 + 结果占位
 * - 设备类型 Radio：5 选项（CYCLONE/MIST_ELIMINATOR/GRAVITY/VANE/FIBER）
 * - 计算按钮触发（未选物流 → 错误）
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { SepEquipComputePage } from '../../../src/pages/sep_equip/SepEquipComputePage';

const streams = [
  { stream_id: 's-1', tag_number: 'FEED-101', sign_status: 'CHECKED' },
  { stream_id: 's-2', tag_number: 'PROD-201', sign_status: 'DRAFT' },
];

describe('SepEquipComputePage — 渲染 (P5-2-4)', () => {
  it('渲染 PageHeader + 输入表单 + 结果占位', () => {
    render(<SepEquipComputePage streams={streams} />);
    expect(screen.getByTestId('sep-equip-compute-page')).toBeTruthy();
    expect(screen.getByTestId('sep-equip-stream-select')).toBeTruthy();
    expect(screen.getByTestId('sep-equip-device-type')).toBeTruthy();
    expect(screen.getByTestId('sep-equip-result-card')).toBeTruthy();
  });

  it('设备类型 Radio：5 选项', () => {
    render(<SepEquipComputePage streams={streams} />);
    expect(document.body.textContent).toContain('旋风分离器');
    expect(document.body.textContent).toContain('丝网除沫器');
    expect(document.body.textContent).toContain('重力沉降器');
    expect(document.body.textContent).toContain('叶片分离器');
    expect(document.body.textContent).toContain('纤维分离器');
  });

  it('默认 CYCLONE 时 Lapple/Swift/Barth Radio 可见', () => {
    render(<SepEquipComputePage streams={streams} />);
    expect(screen.getByTestId('sep-equip-cyclone-method')).toBeTruthy();
    expect(document.body.textContent).toContain('Lapple (GPSA)');
    expect(document.body.textContent).toContain('Swift');
    expect(document.body.textContent).toContain('Barth');
  });
});

describe('SepEquipComputePage — 错误路径 (P5-2-4)', () => {
  it('未选物流 → 点计算 → 显示「请选择物流」', () => {
    render(<SepEquipComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('sep-equip-calculate'));
    expect(screen.getByTestId('sep-equip-error')).toBeTruthy();
    expect(screen.getByTestId('sep-equip-error').textContent).toContain('请选择物流');
  });
});