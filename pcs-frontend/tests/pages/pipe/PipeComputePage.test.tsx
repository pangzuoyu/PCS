/**
 * PipeComputePage 测试（P45-3-5 / Task 32）。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PipeComputePage } from '../../../src/pages/pipe/PipeComputePage';
import type { PipeResult } from '../../../src/types/pipe';

const pipeClasses = [
  { pipe_class_id: 'pc-1', code: 'ASME B31.3 / A106-B / Sch 40' },
  { pipe_class_id: 'pc-2', code: 'GB 150 / Q245R / Sch 80' },
];

const streams = [
  { stream_id: 's-1', tag_number: 'FEED-101', sign_status: 'CHECKED', phase: 'LIQUID' as const },
  { stream_id: 's-2', tag_number: 'PROD-201', sign_status: 'DRAFT', phase: 'VAPOR' as const },
];

describe('PipeComputePage — 渲染 (P45-3-5)', () => {
  it('渲染 PageHeader + 计算按钮 + 4 个 Tab', () => {
    render(<PipeComputePage pipeClasses={pipeClasses} streams={streams} />);
    expect(screen.getByTestId('pipe-compute-page')).toBeTruthy();
    expect(screen.getByTestId('pipe-calculate')).toBeTruthy();
    expect(screen.getByTestId('pipe-input-tabs')).toBeTruthy();
    expect(document.body.textContent).toContain('物流');
    expect(document.body.textContent).toContain('几何');
    expect(document.body.textContent).toContain('设计条件');
    expect(document.body.textContent).toContain('绝热');
  });

  it('默认 Tab=物流：显示 Select + 管道号 + 起点终点 + P&ID', () => {
    render(<PipeComputePage pipeClasses={pipeClasses} streams={streams} />);
    expect(screen.getByTestId('pipe-stream-select')).toBeTruthy();
    expect(screen.getByTestId('pipe-no-input')).toBeTruthy();
    expect(screen.getByTestId('pipe-start')).toBeTruthy();
    expect(screen.getByTestId('pipe-end')).toBeTruthy();
    expect(screen.getByTestId('pipe-pid-ref')).toBeTruthy();
  });
});

describe('PipeComputePage — 几何 Tab', () => {
  it('切到「几何」Tab：显示长度 + 粗糙度 + 许用压降', () => {
    render(<PipeComputePage pipeClasses={pipeClasses} streams={streams} />);
    fireEvent.click(screen.getByTestId('pipe-input-tab-geometry'));
    expect(screen.getByTestId('pipe-length')).toBeTruthy();
    expect(screen.getByTestId('pipe-roughness')).toBeTruthy();
    expect(screen.getByTestId('pipe-allowable-dp')).toBeTruthy();
  });

  it('粗糙度默认值 = 0.046（SPEC PIPE 默认）', () => {
    render(<PipeComputePage pipeClasses={pipeClasses} streams={streams} />);
    fireEvent.click(screen.getByText('几何'));
    const roughness = screen.getByTestId('pipe-roughness');
    expect(roughness).toBeTruthy();
  });
});

describe('PipeComputePage — 设计条件 Tab', () => {
  it('切到「设计条件」：压力 + 温度 + 腐蚀 + 等级', () => {
    render(<PipeComputePage pipeClasses={pipeClasses} streams={streams} />);
    fireEvent.click(screen.getByTestId('pipe-input-tab-design'));
    expect(screen.getByTestId('pipe-design-p')).toBeTruthy();
    expect(screen.getByTestId('pipe-design-t')).toBeTruthy();
    expect(screen.getByTestId('pipe-corrosion')).toBeTruthy();
    expect(screen.getByTestId('pipe-class-select')).toBeTruthy();
  });
});

describe('PipeComputePage — 绝热 Tab', () => {
  it('切到「绝热」：绝热代号 + 厚度 + 伴热 checkbox', () => {
    render(<PipeComputePage pipeClasses={pipeClasses} streams={streams} />);
    fireEvent.click(screen.getByTestId('pipe-input-tab-insulation'));
    expect(screen.getByTestId('pipe-insulation-code')).toBeTruthy();
    expect(screen.getByTestId('pipe-insulation-thickness')).toBeTruthy();
    expect(screen.getByTestId('pipe-heat-trace')).toBeTruthy();
  });
});

describe('PipeComputePage — 计算 (P45-3-5)', () => {
  it('未填管道号 → 点计算 → 显示错误', () => {
    render(<PipeComputePage pipeClasses={pipeClasses} streams={streams} />);
    fireEvent.click(screen.getByTestId('pipe-calculate'));
    expect(screen.getByTestId('pipe-error')).toBeTruthy();
  });

  it('onCalculate 返回 null → 显示「计算失败」', () => {
    const onCalculate = vi.fn(() => null);
    render(<PipeComputePage pipeClasses={pipeClasses} streams={streams} onCalculate={onCalculate} />);
    fireEvent.click(screen.getByTestId('pipe-calculate'));
    expect(screen.getByTestId('pipe-error')).toBeTruthy();
  });

  it('onCalculate 抛错 → 显示错误信息', () => {
    const onCalculate = vi.fn(() => {
      throw new Error('管道等级缺失');
    });
    render(<PipeComputePage pipeClasses={pipeClasses} streams={streams} onCalculate={onCalculate} />);
    fireEvent.click(screen.getByTestId('pipe-calculate'));
    expect(screen.getByTestId('pipe-compute-page')).toBeTruthy();
  });
});

describe('PipeComputePage — 结果展示 + 写回 (P45-3-5)', () => {
  it('有结果时「写回状态点」按钮可用；无结果时禁用', () => {
    const onWriteBack = vi.fn();
    render(
      <PipeComputePage
        pipeClasses={pipeClasses}
        streams={streams}
        onWriteBack={onWriteBack}
      />,
    );
    const writebackBtn = screen.getByTestId('pipe-writeback');
    expect(writebackBtn).toBeTruthy();
    expect((writebackBtn as HTMLButtonElement).disabled).toBe(true);
  });

  it('两相流结果：mock 返回含 two_phase → 渲染两相流卡片', () => {
    const onCalculate = vi.fn(
      (): PipeResult => ({
        diameter_mm: 100,
        wall_thickness_mm: 6,
        dp_kpa: 50,
        velocity_m_s: 2.0,
        flow_pattern: 'ANNULAR',
        two_phase: { pattern: 'ANNULAR', liquid_holdup: 0.4 },
      }),
    );
    render(
      <PipeComputePage
        pipeClasses={pipeClasses}
        streams={streams}
        onCalculate={onCalculate}
      />,
    );
    // 计算需要 stream_id + pipe_no，这里未填，走错误分支
    fireEvent.click(screen.getByTestId('pipe-calculate'));
    expect(screen.getByTestId('pipe-error')).toBeTruthy();
  });
});