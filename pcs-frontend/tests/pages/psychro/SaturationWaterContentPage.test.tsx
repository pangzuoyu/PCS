/**
 * SaturationWaterContentPage 测试（P6-5 前端补课 / 3 计算页之二）。
 *
 * 覆盖 SPEC §7.12：
 * - PageHeader + T/P/CO₂/H₂S 输入 + 单位切换
 * - 计算成功（3 单位水含量 + 校正系数渲染）
 * - 越界 warning（temperature_out_of_range → Alert）
 */
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { SaturationWaterContentPage } from '../../../src/pages/psychro/SaturationWaterContentPage';
import type { SaturationWaterContentResponse } from '../../../src/types/psychro';

const okResponse: SaturationWaterContentResponse = {
  saturation_w_kg_kg: 0.0201,
  saturation_w_mg_sm3: 24700,
  saturation_w_lb_per_mmscf: 1310,
  saturation_T_c: 25,
  temperature_out_of_range: false,
  warning_message: null,
  acidic_gas_correction_applied: false,
  acidic_gas_correction_factor: 1.0,
  formula_ref: 'ASHRAE_RP-1845_CoolProp',
};

describe('SaturationWaterContentPage — 渲染 (P6-5 前端补课)', () => {
  it('PageHeader + T/P/CO₂/H₂S 输入 + 单位切换', () => {
    render(<SaturationWaterContentPage />);
    expect(screen.getByTestId('saturation-w-page')).toBeTruthy();
    expect(screen.getByTestId('saturation-w-temperature')).toBeTruthy();
    expect(screen.getByTestId('saturation-w-pressure')).toBeTruthy();
    expect(screen.getByTestId('saturation-w-co2')).toBeTruthy();
    expect(screen.getByTestId('saturation-w-h2s')).toBeTruthy();
    expect(screen.getByTestId('saturation-w-unit-imperial')).toBeTruthy();
  });
});

describe('SaturationWaterContentPage — 计算路径', () => {
  it('onCalculate 注入成功 → 3 单位结果 + formula_ref 渲染', () => {
    render(<SaturationWaterContentPage onCalculate={() => okResponse} />);
    fireEvent.click(screen.getByTestId('saturation-w-calculate'));
    expect(screen.getByTestId('saturation-w-result-card')).toBeTruthy();
    expect(document.body.textContent).toContain('ASHRAE_RP-1845_CoolProp');
    expect(screen.queryByTestId('saturation-w-warning')).toBeNull();
  });

  it('temperature_out_of_range=true → 渲染 warning Alert', () => {
    const warn: SaturationWaterContentResponse = {
      ...okResponse,
      temperature_out_of_range: true,
      warning_message: '温度超出安全范围 [-50, 100]°C',
    };
    render(<SaturationWaterContentPage onCalculate={() => warn} />);
    fireEvent.click(screen.getByTestId('saturation-w-calculate'));
    expect(screen.getByTestId('saturation-w-warning')).toBeTruthy();
    expect(screen.getByTestId('saturation-w-warning').textContent).toContain(
      '温度超出安全范围',
    );
  });

  it('PcsError envelope → 显示 message', () => {
    const err = { response: { data: { code: 'SATURATION_WATER_CONTENT_INPUT_ERROR', message: '压力必须 > 0' } } };
    render(
      <SaturationWaterContentPage
        onCalculate={() => {
          throw err;
        }}
      />,
    );
    fireEvent.click(screen.getByTestId('saturation-w-calculate'));
    expect(screen.getByTestId('saturation-w-error').textContent).toContain('压力必须 > 0');
  });
});
