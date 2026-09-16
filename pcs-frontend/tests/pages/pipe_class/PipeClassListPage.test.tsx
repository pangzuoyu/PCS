/**
 * PipeClassListPage 测试（P45-3-2 / Task 29）。
 *
 * 覆盖 SPEC §7.9.1~2：
 * - 表格列：code / material / schedule / DN 范围 / 压力 / 温度 / 腐蚀 / 状态
 * - 过滤：code / material / schedule
 * - 行点击 → onSelect
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PipeClassListPage } from '../../../src/pages/pipe_class/PipeClassListPage';
import type { PipeClass } from '../../../src/types/pipeClass';

const classes: PipeClass[] = [
  {
    pipe_class_id: 'pc-1',
    code: 'ASME B31.3',
    material: 'A106-B',
    schedule: 'Sch 40',
    size_range_json: { min_dn: 15, max_dn: 600 },
    design_pressure_mpa: 5.0,
    design_temperature_c: 200,
    corrosion_allowance_mm: 1.5,
    sign_status: 'CHECKED',
  },
  {
    pipe_class_id: 'pc-2',
    code: 'GB 150',
    material: 'Q245R',
    schedule: 'Sch 80',
    size_range_json: { min_dn: 50, max_dn: 800 },
    design_pressure_mpa: 10.0,
    design_temperature_c: 350,
    corrosion_allowance_mm: 2.0,
    sign_status: 'DRAFT',
  },
];

describe('PipeClassListPage — 渲染 (P45-3-2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染标题 + 2 条记录', () => {
    render(<PipeClassListPage classes={classes} />);
    expect(screen.getByTestId('pipe-class-list-page')).toBeTruthy();
    const rows = document.querySelectorAll('[data-testid="pipe-class-row"]');
    expect(rows.length).toBe(2);
  });

  it('按 code 过滤：输入 "GB" → 只剩 1 行', () => {
    render(<PipeClassListPage classes={classes} />);
    const search = screen.getByTestId('pipe-class-search');
    fireEvent.change(search, { target: { value: 'GB' } });
    const rows = document.querySelectorAll('[data-testid="pipe-class-row"]');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('GB 150');
  });

  it('按 material 过滤：输入 "Q245R" → 只剩 1 行', () => {
    render(<PipeClassListPage classes={classes} />);
    fireEvent.change(screen.getByTestId('pipe-class-search'), { target: { value: 'Q245R' } });
    const rows = document.querySelectorAll('[data-testid="pipe-class-row"]');
    expect(rows.length).toBe(1);
  });

  it('按 schedule 过滤：输入 "Sch 80" → 只剩 1 行', () => {
    render(<PipeClassListPage classes={classes} />);
    fireEvent.change(screen.getByTestId('pipe-class-search'), { target: { value: 'Sch 80' } });
    const rows = document.querySelectorAll('[data-testid="pipe-class-row"]');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('GB 150');
  });

  it('清空过滤 → 恢复 2 行', () => {
    render(<PipeClassListPage classes={classes} />);
    const search = screen.getByTestId('pipe-class-search');
    fireEvent.change(search, { target: { value: 'GB' } });
    fireEvent.change(search, { target: { value: '' } });
    const rows = document.querySelectorAll('[data-testid="pipe-class-row"]');
    expect(rows.length).toBe(2);
  });
});

describe('PipeClassListPage — 操作', () => {
  it('行点击 → onSelect 回调', () => {
    const onSelect = vi.fn();
    render(<PipeClassListPage classes={classes} onSelect={onSelect} />);
    const row = document.querySelector('[data-testid="pipe-class-row"]');
    fireEvent.click(row!);
    expect(onSelect).toHaveBeenCalledWith(classes[0]);
  });
});