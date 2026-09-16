/**
 * PipeLineListPage 测试（P45-3-5 / Task 32）。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PipeLineListPage } from '../../../src/pages/pipe/PipeLineListPage';
import type { PipeLineListRow } from '../../../src/types/pipe';

const basicRows: PipeLineListRow[] = [
  {
    seq: 1,
    pipe_no: 'P-101',
    size: 'DN50',
    material: 'A106-B',
    fluid_code: 'W',
    fluid_name: 'Water',
    phase: 'LIQUID',
    fluid_class: 'NORMAL',
    toxicity: 'NON',
    pipe_class: 'ASME B31.3',
    design_pressure_mpa: 1.0,
    design_temperature_c: 50,
  },
  {
    seq: 2,
    pipe_no: 'P-102',
    size: 'DN80',
    material: 'A106-B',
    fluid_code: 'O',
    fluid_name: 'Oil',
    phase: 'LIQUID',
    fluid_class: 'FLAMMABLE',
    toxicity: 'NON',
    pipe_class: 'ASME B31.3',
    design_pressure_mpa: 1.5,
    design_temperature_c: 80,
  },
  {
    seq: 3,
    pipe_no: 'P-103',
    size: 'DN100',
    material: 'Q245R',
    fluid_code: 'S',
    fluid_name: 'Steam',
    phase: 'VAPOR',
    fluid_class: 'HIGH_TEMP',
    toxicity: 'NON',
    pipe_class: 'GB 150',
    design_pressure_mpa: 3.5,
    design_temperature_c: 350,
    length_m: 50,
    dp_kpa: 20,
    velocity_m_s: 25.0,
    start_point: 'E-101',
    end_point: 'V-201',
    pid_ref: 'PID-001',
    sign_status: 'CHECKED',
    updated_by: '张三',
    updated_at: '2026-09-10',
  },
];

describe('PipeLineListPage — BASIC 阶段 (P45-3-5)', () => {
  it('默认 BASIC 阶段：渲染所有行', () => {
    render(<PipeLineListPage rows={basicRows} />);
    expect(screen.getByTestId('pipe-line-list-page')).toBeTruthy();
    const rows = document.querySelectorAll('[data-testid="pipe-line-row"]');
    expect(rows.length).toBe(3);
  });

  it('BASIC 列：seq / pipe_no / size / material / fluid / phase / class / toxicity / pipe_class / 设计压力 / 设计温度', () => {
    render(<PipeLineListPage rows={basicRows} />);
    const headers = document.querySelectorAll('.ant-table-thead th');
    const headerTexts = Array.from(headers).map((h) => h.textContent ?? '');
    expect(headerTexts).toContain('seq');
    expect(headerTexts).toContain('pipe_no');
    expect(headerTexts).toContain('size');
    expect(headerTexts).toContain('material');
    expect(headerTexts).toContain('fluid');
    expect(headerTexts).toContain('phase');
    expect(headerTexts).toContain('class');
    expect(headerTexts).toContain('toxicity');
    expect(headerTexts).toContain('pipe_class');
    expect(headerTexts).toContain('设计压力 (MPa)');
    expect(headerTexts).toContain('设计温度 (°C)');
  });

  it('BASIC 列数 = 11（含 seq）', () => {
    render(<PipeLineListPage rows={basicRows} />);
    const headers = document.querySelectorAll('.ant-table-thead th');
    expect(headers.length).toBe(11);
  });

  it('按流体名过滤：输入 "Oil" → 只剩 1 行', () => {
    render(<PipeLineListPage rows={basicRows} />);
    fireEvent.change(screen.getByTestId('pipe-filter-fluid'), { target: { value: 'Oil' } });
    const rows = document.querySelectorAll('[data-testid="pipe-line-row"]');
    expect(rows.length).toBe(1);
  });

  it('按管道级别过滤：输入 "GB 150" → 只剩 1 行', () => {
    render(<PipeLineListPage rows={basicRows} />);
    fireEvent.change(screen.getByTestId('pipe-filter-class'), { target: { value: 'GB 150' } });
    const rows = document.querySelectorAll('[data-testid="pipe-line-row"]');
    expect(rows.length).toBe(1);
  });

  it('过滤计数 Tag 显示当前过滤结果数', () => {
    render(<PipeLineListPage rows={basicRows} />);
    fireEvent.change(screen.getByTestId('pipe-filter-fluid'), { target: { value: 'Oil' } });
    const count = screen.getByTestId('pipe-filter-count');
    expect(count.textContent).toBe('1');
  });
});

describe('PipeLineListPage — DETAIL 阶段 (P45-3-5)', () => {
  it('切到 DETAIL：列数 > BASIC', () => {
    render(<PipeLineListPage rows={basicRows} />);
    const basicHeaders = document.querySelectorAll('.ant-table-thead th').length;
    fireEvent.click(screen.getByTestId('pipe-stage-switcher'));
    // 弹出 Segmented 选项，点 DETAIL
    const detailLabel = screen.getByText('DETAIL (25 列)');
    fireEvent.click(detailLabel);
    const detailHeaders = document.querySelectorAll('.ant-table-thead th').length;
    expect(detailHeaders).toBeGreaterThan(basicHeaders);
  });

  it('DETAIL 列包含：长度 / dp / velocity / start / end / pid_ref / insulation / 状态', () => {
    render(<PipeLineListPage rows={basicRows} />);
    fireEvent.click(screen.getByTestId('pipe-stage-switcher'));
    fireEvent.click(screen.getByText('DETAIL (25 列)'));
    const headers = Array.from(document.querySelectorAll('.ant-table-thead th')).map((h) => h.textContent ?? '');
    expect(headers).toContain('长度 (m)');
    expect(headers).toContain('dp (kPa)');
    expect(headers).toContain('velocity (m/s)');
    expect(headers).toContain('start');
    expect(headers).toContain('end');
    expect(headers).toContain('pid_ref');
    expect(headers).toContain('insulation');
    expect(headers).toContain('状态');
  });

  it('DETAIL 行：缺数据列显示「—」', () => {
    render(<PipeLineListPage rows={basicRows} />);
    fireEvent.click(screen.getByTestId('pipe-stage-switcher'));
    fireEvent.click(screen.getByText('DETAIL (25 列)'));
    // seq=1 行 length/dp/velocity 都是 undefined → 显示 —
    const dashes = document.body.textContent?.match(/—/g) ?? [];
    expect(dashes.length).toBeGreaterThan(0);
  });
});

describe('PipeLineListPage — 操作 (P45-3-5)', () => {
  it('行点击 → onSelect 回调（row 数据）', () => {
    const onSelect = vi.fn();
    render(<PipeLineListPage rows={basicRows} onSelect={onSelect} />);
    const row = document.querySelector('[data-testid="pipe-line-row"]');
    fireEvent.click(row!);
    expect(onSelect).toHaveBeenCalledWith(basicRows[0]);
  });

  it('空数据 → 显示 0 行（不崩）', () => {
    render(<PipeLineListPage rows={[]} />);
    const rows = document.querySelectorAll('[data-testid="pipe-line-row"]');
    expect(rows.length).toBe(0);
  });
});