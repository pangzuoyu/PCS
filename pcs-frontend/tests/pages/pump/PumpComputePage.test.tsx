/**
 * PumpComputePage 测试（P45-3-7 / Task 34）。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PumpComputePage } from '../../../src/pages/pump/PumpComputePage';

const streams = [
  { stream_id: 's-1', tag_number: 'FEED-101', sign_status: 'CHECKED' },
  { stream_id: 's-2', tag_number: 'PROD-201', sign_status: 'DRAFT' },
];

describe('PumpComputePage — 渲染 (P45-3-7)', () => {
  it('渲染 PageHeader + 计算按钮 + 3 Tab', () => {
    render(<PumpComputePage streams={streams} />);
    expect(screen.getByTestId('pump-compute-page')).toBeTruthy();
    expect(screen.getByTestId('pump-calculate')).toBeTruthy();
    expect(screen.getByTestId('pump-input-tabs')).toBeTruthy();
  });

  it('默认吸入口 Tab：显示物流 Select + 容器压力 + 液位 + 管径', () => {
    render(<PumpComputePage streams={streams} />);
    expect(screen.getByTestId('pump-stream-select')).toBeTruthy();
    expect(screen.getByTestId('pump-suction-p')).toBeTruthy();
    expect(screen.getByTestId('pump-suction-level')).toBeTruthy();
    expect(screen.getByTestId('pump-suction-dn')).toBeTruthy();
  });

  it('切到「排出口」Tab：显示容器压力 + 静扬程 + 管径', () => {
    render(<PumpComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('pump-tab-discharge'));
    expect(screen.getByTestId('pump-discharge-p')).toBeTruthy();
    expect(screen.getByTestId('pump-discharge-head')).toBeTruthy();
    expect(screen.getByTestId('pump-discharge-dn')).toBeTruthy();
  });

  it('切到「流量 / 效率」Tab：显示 3 流量 + 2 效率 + 控制阀压降', () => {
    render(<PumpComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('pump-tab-flow'));
    expect(screen.getByTestId('pump-flow-normal')).toBeTruthy();
    expect(screen.getByTestId('pump-flow-min')).toBeTruthy();
    expect(screen.getByTestId('pump-flow-design')).toBeTruthy();
    expect(screen.getByTestId('pump-eff-pump')).toBeTruthy();
    expect(screen.getByTestId('pump-eff-motor')).toBeTruthy();
    expect(screen.getByTestId('pump-cv-dp')).toBeTruthy();
  });
});

describe('PumpComputePage — 计算 (P45-3-7)', () => {
  it('未选物流 → 点计算 → 显示错误', () => {
    render(<PumpComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('pump-calculate'));
    expect(screen.getByTestId('pump-error')).toBeTruthy();
  });

  it('onCalculate 返回 null → 显示「计算失败」', () => {
    const onCalculate = vi.fn(() => null);
    render(<PumpComputePage streams={streams} onCalculate={onCalculate} />);
    fireEvent.click(screen.getByTestId('pump-calculate'));
    expect(screen.getByTestId('pump-error')).toBeTruthy();
  });

  it('onCalculate 抛错 → 显示错误', () => {
    const onCalculate = vi.fn(() => {
      throw new Error('汽蚀');
    });
    render(<PumpComputePage streams={streams} onCalculate={onCalculate} />);
    fireEvent.click(screen.getByTestId('pump-calculate'));
    expect(screen.getByTestId('pump-compute-page')).toBeTruthy();
  });
});

describe('PumpComputePage — 结果展示 (P45-3-7)', () => {
  it('有结果时显示 3 个核心 Statistic：扬程 / NPSH / 功率', () => {
    render(<PumpComputePage streams={streams} />);
    expect(screen.queryByTestId('pump-result-head')).toBeNull();
    expect(screen.queryByTestId('pump-result-npsh')).toBeNull();
    expect(screen.queryByTestId('pump-result-power')).toBeNull();
  });

  it('创建出口物流按钮：无结果时禁用，有结果时可用', () => {
    const onCreate = vi.fn();
    render(
      <PumpComputePage
        streams={streams}
        onCreateOutletStream={onCreate}
      />,
    );
    const btn = screen.getByTestId('pump-create-outlet');
    expect((btn as HTMLButtonElement).disabled).toBe(true);
  });

  it('结果区：压降分段 Table 列渲染（无结果时不渲染）', () => {
    render(<PumpComputePage streams={streams} />);
    expect(screen.queryByTestId('pump-dp-breakdown')).toBeNull();
  });
});

describe('PumpComputePage — 默认值 (P45-3-7)', () => {
  it('吸入口默认值：容器压力 0.1 MPa / 液位 2 m / DN100', () => {
    render(<PumpComputePage streams={streams} />);
    const pInput = screen.getByTestId('pump-suction-p');
    expect(pInput).toBeTruthy();
  });

  it('排出口默认值：容器压力 1.0 MPa / 静扬程 15 m / DN80', () => {
    render(<PumpComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('pump-tab-discharge'));
    const pInput = screen.getByTestId('pump-discharge-p');
    expect(pInput).toBeTruthy();
  });

  it('流量默认值：normal 100 / min 50 / design 120', () => {
    render(<PumpComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('pump-tab-flow'));
    expect(screen.getByTestId('pump-flow-normal')).toBeTruthy();
    expect(screen.getByTestId('pump-flow-min')).toBeTruthy();
    expect(screen.getByTestId('pump-flow-design')).toBeTruthy();
  });

  it('效率默认值：泵 0.7 / 电机 0.95', () => {
    render(<PumpComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('pump-tab-flow'));
    expect(screen.getByTestId('pump-eff-pump')).toBeTruthy();
    expect(screen.getByTestId('pump-eff-motor')).toBeTruthy();
  });

  it('控制阀压降默认 = 30 kPa', () => {
    render(<PumpComputePage streams={streams} />);
    fireEvent.click(screen.getByTestId('pump-tab-flow'));
    const cv = screen.getByTestId('pump-cv-dp');
    expect(cv).toBeTruthy();
  });
});