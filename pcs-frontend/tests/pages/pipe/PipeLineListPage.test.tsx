/**
 * PipeLineListPage 测试（P45-3-5 / Task 32 · **P10-C · T2 改：列清单对齐 SPEC**）。
 *
 * ## ⚠️ 夹具改成**契约形状**（2026-11-19 · P10-C · T2）
 *
 * 此前夹具是**前端手写的 25 列**类型（还带 `length_m` / `dp_kpa` /
 * `velocity_m_s` 三个**后端根本没有**的列）⇒ ⇒ 「fixture 与被测对象同源 ⇒
 * 零信号」⇒ ⇒ 后端补了真端点之后，页面在生产上的列**对不上**也没人发现。
 *
 * ⇒ ⇒ 现在夹具的类型 = **契约类型**（`PipeLineListRow`）⇒ ⇒ 少一个必填字段
 * ⇒ ⇒ `tsc` 直接红。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PipeLineListPage } from '../../../src/pages/pipe/PipeLineListPage';
import type { PipeLineListRow } from '../../../src/types/pipe';

/** 一行**契约形状**的管道记录（必填字段全给上）。 */
function row(over: Partial<PipeLineListRow> = {}): PipeLineListRow {
  return {
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
    pid_ref: 'PID-001',
    start_point: 'E-101',
    end_point: 'V-201',
    norm_oper_press: 0.8,
    max_oper_press: 1.0,
    norm_oper_temp: 40,
    max_oper_temp: 50,
    design_pressure_mpa: 1.0,
    design_temperature_c: 50,
    piping_category: 'GC2',
    pressure_test_medium: 'WATER',
    pressure_test_press: 1.5,
    check_class: 'II',
    sign_status: 'DRAFT',
    ...over,
  };
}

const basicRows: PipeLineListRow[] = [
  row({ seq: 1, pipe_no: 'P-101', fluid_name: 'Water', pipe_class: 'ASME B31.3' }),
  row({
    seq: 2,
    pipe_no: 'P-102',
    size: 'DN80',
    fluid_code: 'O',
    fluid_name: 'Oil',
    fluid_class: 'FLAMMABLE',
    design_pressure_mpa: 1.5,
    design_temperature_c: 80,
  }),
  row({
    seq: 3,
    pipe_no: 'P-103',
    size: 'DN100',
    material: 'Q245R',
    fluid_code: 'S',
    fluid_name: 'Steam',
    phase: 'VAPOR',
    fluid_class: 'HIGH_TEMP',
    pipe_class: 'GB 150',
    design_pressure_mpa: 3.5,
    design_temperature_c: 350,
    insulation_code: 'INS-30',
    insulation_thickness: 30,
    cleaning_method: ['PI'],
    sign_status: 'CHECKED',
    updated_by: '张三',
    updated_at: '2026-09-10',
  }),
];

describe('PipeLineListPage — BASIC 阶段 (P45-3-5)', () => {
  it('默认 BASIC 阶段：渲染所有行', () => {
    render(<PipeLineListPage rows={basicRows} />);
    expect(screen.getByTestId('pipe-line-list-page')).toBeTruthy();
    const rows = document.querySelectorAll('[data-testid="pipe-line-row"]');
    expect(rows.length).toBe(3);
  });

  it('BASIC 列 = SPEC §7.11.2 的前 10 列 + 设计压力/温度', () => {
    render(<PipeLineListPage rows={basicRows} />);
    const headers = document.querySelectorAll('.ant-table-thead th');
    const headerTexts = Array.from(headers).map((h) => h.textContent ?? '');
    expect(headerTexts).toContain('序号');
    expect(headerTexts).toContain('管道号');
    expect(headerTexts).toContain('尺寸');
    expect(headerTexts).toContain('材料等级');
    expect(headerTexts).toContain('介质代号');
    expect(headerTexts).toContain('介质名称');
    expect(headerTexts).toContain('相态');
    expect(headerTexts).toContain('流体分类');
    expect(headerTexts).toContain('毒性级别');
    expect(headerTexts).toContain('管道级别');
    expect(headerTexts).toContain('设计压力 (MPa)');
    expect(headerTexts).toContain('设计温度 (°C)');
  });

  it('BASIC 列数 = 12（含序号）', () => {
    render(<PipeLineListPage rows={basicRows} />);
    const headers = document.querySelectorAll('.ant-table-thead th');
    expect(headers.length).toBe(12);
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

describe('PipeLineListPage — DETAIL 阶段 (P10-C · T2)', () => {
  it('切到 DETAIL：列数 > BASIC', () => {
    render(<PipeLineListPage rows={basicRows} />);
    const basicHeaders = document.querySelectorAll('.ant-table-thead th').length;
    fireEvent.click(screen.getByTestId('pipe-stage-switcher'));
    fireEvent.click(screen.getByText(/DETAIL \(\d+ 列\)/));
    const detailHeaders = document.querySelectorAll('.ant-table-thead th').length;
    expect(detailHeaders).toBeGreaterThan(basicHeaders);
  });

  it('DETAIL 列是 SPEC §7.11.2 的完整列清单（含此前缺失的那些）', () => {
    render(<PipeLineListPage rows={basicRows} />);
    fireEvent.click(screen.getByTestId('pipe-stage-switcher'));
    fireEvent.click(screen.getByText(/DETAIL \(\d+ 列\)/));
    const headers = Array.from(document.querySelectorAll('.ant-table-thead th')).map((h) => h.textContent ?? '');
    // ⚠️ **绝热 / 涂漆 / 伴管 / 维持温度 / PID / 起终点** —— 此前 DETAIL 里没有
    expect(headers).toContain('绝热代号');
    expect(headers).toContain('绝热厚度 (mm)');
    expect(headers).toContain('涂漆代号');
    expect(headers).toContain('伴管类型');
    expect(headers).toContain('维持温度 (°C)');
    expect(headers).toContain('PID 图号');
    expect(headers).toContain('起点');
    expect(headers).toContain('终点');
    // —— 试验 / NDT / 检查 ——
    expect(headers).toContain('压力管道类别');
    expect(headers).toContain('试验介质');
    expect(headers).toContain('NDT 方法');
    expect(headers).toContain('泄漏试验介质');
    expect(headers).toContain('检查等级');
    expect(headers).toContain('清洗方法');
    expect(headers).toContain('备注');
    // —— 审计三列 ——
    expect(headers).toContain('状态');
    expect(headers).toContain('更新人');
    expect(headers).toContain('更新时间');
  });

  it('⚠️ **不再有「后端根本没有」的列**（length / dp / velocity / pipe_class_detail）', () => {
    render(<PipeLineListPage rows={basicRows} />);
    fireEvent.click(screen.getByTestId('pipe-stage-switcher'));
    fireEvent.click(screen.getByText(/DETAIL \(\d+ 列\)/));
    const headers = Array.from(document.querySelectorAll('.ant-table-thead th')).map((h) => h.textContent ?? '');
    // ⇒ ⇒ 这四列此前是**幽灵列**（真后端下永远 undefined）⇒ ⇒ 现在没有了。
    expect(headers).not.toContain('长度 (m)');
    expect(headers).not.toContain('dp (kPa)');
    expect(headers).not.toContain('velocity (m/s)');
  });

  it('DETAIL 行：缺数据列显示「—」', () => {
    render(<PipeLineListPage rows={basicRows} />);
    fireEvent.click(screen.getByTestId('pipe-stage-switcher'));
    fireEvent.click(screen.getByText(/DETAIL \(\d+ 列\)/));
    // seq=1 行没给绝热厚度等 ⇒ 显示 —
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
