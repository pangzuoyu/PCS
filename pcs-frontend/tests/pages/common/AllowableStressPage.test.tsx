/**
 * AllowableStressPage 测试（P45-3-3 / Task 30）。
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { AllowableStressPage } from '../../../src/pages/common/AllowableStressPage';
import type { AllowableStress } from '../../../src/types/common';

const stresses: AllowableStress[] = [
  { material: 'A106-B', temperature_c: 100, allowable_stress_mpa: 137.0, standard: 'ASME' },
  { material: 'A106-B', temperature_c: 200, allowable_stress_mpa: 124.0, standard: 'ASME' },
  { material: 'Q245R',  temperature_c: 100, allowable_stress_mpa: 110.0, standard: 'GB' },
];

describe('AllowableStressPage — 渲染 (P45-3-3)', () => {
  it('渲染 3 行 + ASME/GB 标准 Tag', () => {
    render(<AllowableStressPage stresses={stresses} />);
    expect(screen.getByTestId('allowable-stress-page')).toBeTruthy();
    const tags = document.querySelectorAll('[data-testid="stress-standard"]');
    expect(tags.length).toBe(3);
    expect(document.body.textContent).toContain('ASME');
    expect(document.body.textContent).toContain('GB');
  });

  it('按材料过滤：输入 "Q245R" → 只剩 1 行', () => {
    render(<AllowableStressPage stresses={stresses} />);
    fireEvent.change(screen.getByTestId('stress-search'), { target: { value: 'Q245R' } });
    const tags = document.querySelectorAll('[data-testid="stress-standard"]');
    expect(tags.length).toBe(1);
    expect(tags[0].textContent).toBe('GB');
  });

  it('空结果 → 显示 Empty', () => {
    render(<AllowableStressPage stresses={[]} />);
    expect(document.body.textContent).toContain('无记录');
  });
});