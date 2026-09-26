/**
 * HeatingValuePage 测试（P6-5 前端补课 / 3 计算页之一）。
 *
 * 覆盖 SPEC §7.8 + §7.12：
 * - PageHeader + 默认 4 组分行 + 结果占位
 * - 计算成功（onCalculate 注入 → HHV/LHV + 烟气组成渲染）
 * - 错误路径（清空组分 → 「至少填写 1 行」；PcsError envelope message）
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { HeatingValuePage } from '../../../src/pages/common/HeatingValuePage';
import type { HeatingValueCalcResponse } from '../../../src/types/common';

const okResponse: HeatingValueCalcResponse = {
  feed_mw_kg_per_kmol: 17.4,
  hhv_mj_per_sm3: 41.6,
  hhv_btu_per_scf: 1116,
  lhv_mj_per_sm3: 37.5,
  lhv_btu_per_scf: 1006,
  stoichiometric_air_sm3_per_sm3: 9.85,
  flue_gas_sm3_per_sm3: 10.6,
  flue_gas_composition: { CO2: 0.087, H2O: 0.173, N2: 0.73 },
  flue_gas_mw_kg_per_kmol: 27.6,
  formula_ref: { '74-82-8': 'GPSA_23-2' },
};

describe('HeatingValuePage — 渲染 (P6-5 前端补课)', () => {
  it('PageHeader + 默认天然气 4 组分行 + 结果占位', () => {
    render(<HeatingValuePage />);
    expect(screen.getByTestId('heating-value-page')).toBeTruthy();
    expect(screen.getByTestId('heating-value-cas-0')).toBeTruthy();
    expect(screen.getByTestId('heating-value-cas-3')).toBeTruthy();
    expect(screen.getByTestId('heating-value-frac-0')).toBeTruthy();
    expect(screen.getByTestId('heating-value-excess-air')).toBeTruthy();
  });

  it('添加 / 删除组分行', () => {
    render(<HeatingValuePage />);
    fireEvent.click(screen.getByTestId('heating-value-add'));
    expect(screen.getByTestId('heating-value-cas-4')).toBeTruthy();
    fireEvent.click(screen.getByTestId('heating-value-remove-4'));
    expect(screen.queryByTestId('heating-value-cas-4')).toBeNull();
  });
});

describe('HeatingValuePage — 计算路径', () => {
  it('onCalculate 注入成功 → HHV/LHV + 烟气组成 + formula_ref 渲染', () => {
    render(<HeatingValuePage onCalculate={() => okResponse} />);
    fireEvent.click(screen.getByTestId('heating-value-calculate'));
    expect(screen.getByTestId('heating-value-result-card')).toBeTruthy();
    expect(screen.getByTestId('heating-value-formula-ref').textContent).toContain(
      'GPSA_23-2',
    );
    // 烟气组成表渲染（CO₂ / N₂ 标签）
    expect(document.body.textContent).toContain('CO₂');
    expect(document.body.textContent).toContain('N₂');
  });

  it('onCalculate 返回 undefined → 显示计算失败', () => {
    render(<HeatingValuePage onCalculate={() => undefined} />);
    fireEvent.click(screen.getByTestId('heating-value-calculate'));
    expect(screen.getByTestId('heating-value-error').textContent).toContain('计算失败');
  });

  it('PcsError envelope → 显示 message', () => {
    const err = { response: { data: { code: 'HEATING_VALUE_INPUT_ERROR', message: '空 compositions' } } };
    render(
      <HeatingValuePage
        onCalculate={() => {
          throw err;
        }}
      />,
    );
    fireEvent.click(screen.getByTestId('heating-value-calculate'));
    expect(screen.getByTestId('heating-value-error').textContent).toContain('空 compositions');
  });
});
