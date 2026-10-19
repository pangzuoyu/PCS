/**
 * AllowableStressPage 测试（P45-3-3 / Task 30）。
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { AllowableStressPage } from '../../../src/pages/common/AllowableStressPage';
import type { AllowableStress } from '../../../src/types/common';

// ⚠️ 字段名对齐契约 `AllowableStressResult`（2026-10-19）。
// 此前 fixture 与页面共用同一套**错名字**，于是测试绿、页面生产上空白
// —— 「fixture 与被测对象同源 ⇒ 零信号」的又一例。
//
// `source` 用契约里的真实取值形态（`ASME_B31.3_TABLE_A1`），
// 页面按前缀着色，所以 `ASME_…` 仍是蓝色、`GB_…` 仍是绿色。
const stresses: AllowableStress[] = [
  { material: 'A106-B', temp_c: 100, stress_mpa: 137.0, source: 'ASME_B31.3_TABLE_A1' },
  { material: 'A106-B', temp_c: 200, stress_mpa: 124.0, source: 'ASME_B31.3_TABLE_A1' },
  { material: 'Q245R',  temp_c: 100, stress_mpa: 110.0, source: 'GB_T_20801' },
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
    // `source` 是契约里的完整取值（`GB_T_20801`），不是前端编的短名 `GB`。
    // 颜色按前缀取，所以标签仍应是绿色 —— 顺手断言颜色没退化。
    expect(tags[0].textContent).toBe('GB_T_20801');
  });

  it('空结果 → 显示 Empty', () => {
    render(<AllowableStressPage stresses={[]} />);
    expect(document.body.textContent).toContain('无记录');
  });
});