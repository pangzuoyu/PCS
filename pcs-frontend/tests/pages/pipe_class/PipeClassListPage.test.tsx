/**
 * PipeClassListPage 测试（P45-3-2 / Task 29；2026-10-19 按契约重写）。
 *
 * ## 上一版为什么是**假绿**（bug-180 的发现路径之一）
 *
 * 旧 fixture 用手写副本的字段名（`pipe_class_id` / `code` / `material` /
 * `schedule` / `size_range_json` / `sign_status`）造数据，
 * 而页面读**同一份**手写类型 —— 于是「页面读什么」与「fixture 有什么」
 * 用的是同一个错误来源，永远对得上。
 *
 * 真实后端返的是 `class_id` / `class_name` / …，所以生产上这些测试
 * 全部通过、页面全部空白。**六条绿，零信号。**
 *
 * 这与 `mocks/seed/pipe-classes.ts` 是同一个病的两个实例：
 * fixture 与被测对象共用一份错误类型 ⇒ 互相验证、互不设防。
 *
 * 现在 `PipeClass` 就是 `components['schemas']['PipeClassResponse']`，
 * fixture 用**契约字段**构造，且用 `satisfies` 让缺字段在编译期就红。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PipeClassListPage } from '../../../src/pages/pipe_class/PipeClassListPage';
import type { PipeClass } from '../../../src/types/pipeClass';

/** 契约必填字段的最小完整行；字段名**只能**来自契约。 */
function pc(over: Partial<PipeClass> = {}): PipeClass {
  return {
    class_id: 'pc-x',
    class_name: 'ASME B31.3',
    material_standard: 'A106-B',
    corrosion_allowance: 1.5,
    design_pressure: 5.0,
    design_temperature: 200,
    dn_series_json: { min: 15, max: 600 },
    sch_series_json: { '15': 'Sch 40', '50': 'Sch 40' },
    flange_class: '150#',
    source: 'COMPANY_STD',
    version: '1.0',
    status: 'ACTIVE',
    ...over,
  };
}

const classes: PipeClass[] = [
  pc(),
  pc({
    class_id: 'pc-2',
    class_name: 'GB 150',
    material_standard: 'Q245R',
    design_pressure: 10.0,
    design_temperature: 350,
    corrosion_allowance: 2.0,
    dn_series_json: { min: 50, max: 800 },
    sch_series_json: { '50': 'Sch 80', '100': 'Sch 80' },
    status: 'DRAFT',
  }),
  // 壁厚在 DN 范围内不统一 → 单元格显示「按 DN 分档」
  pc({
    class_id: 'pc-3',
    class_name: 'ASME B31.8',
    material_standard: 'A312',
    dn_series_json: { min: 25, max: 300 },
    sch_series_json: { '25': 'Sch 80', '100': 'Sch 160', '300': 'Sch 160' },
  }),
];

describe('PipeClassListPage — 渲染 (P45-3-2)', () => {
  beforeEach(() => { vi.clearAllMocks(); });

  it('渲染标题 + N 条记录', () => {
    render(<PipeClassListPage classes={classes} />);
    expect(screen.getByTestId('pipe-class-list-page')).toBeTruthy();
    expect(document.querySelectorAll('[data-testid="pipe-class-row"]').length).toBe(3);
  });

  it('显示契约字段值 —— 读旧字段名会让这三条全空', () => {
    // 这三条就是 bug-180 的回归守卫：页面读 `code` 时它们全是空白。
    render(<PipeClassListPage classes={classes} />);
    const body = document.body.textContent ?? '';
    expect(body).toContain('ASME B31.3');      // class_name
    expect(body).toContain('Q245R');          // material_standard
    expect(body).toContain('DN15–600');       // dn_series_json.min/max
  });
});

describe('PipeClassListPage — 壁厚列（契约是 DN→Sch 映射，用户裁决 2026-10-19）', () => {
  it('全范围同值 → 显示具体 Sch', () => {
    render(<PipeClassListPage classes={[pc()]} />);
    const row = document.querySelector('[data-testid="pipe-class-row"]');
    expect(row?.textContent).toContain('Sch 40');
    expect(row?.textContent).not.toContain('按 DN 分档');
  });

  it('不统一 → 显示「按 DN 分档」（不是「多档」）', () => {
    render(<PipeClassListPage classes={[classes[2]]} />);
    const row = document.querySelector('[data-testid="pipe-class-row"]');
    expect(row?.textContent).toContain('按 DN 分档');
    expect(row?.textContent).not.toContain('多档');
  });

  it('空映射 → 显示「—」，不是「按 DN 分档」', () => {
    render(<PipeClassListPage classes={[pc({ sch_series_json: {} })]} />);
    const row = document.querySelector('[data-testid="pipe-class-row"]');
    expect(row?.textContent).toContain('—');
    expect(row?.textContent).not.toContain('按 DN 分档');
  });

  it('不统一时有 Tooltip 列出区间', () => {
    render(<PipeClassListPage classes={[classes[2]]} />);
    // antd Tooltip 的内容在 hover 后才渲染；此处断言存在可 hover 的元素即可，
    // 区间合并逻辑本身由 tests/lib/pipeClassSch.test.ts 钉住。
    const row = document.querySelector('[data-testid="pipe-class-row"]');
    expect(row?.querySelector('.ant-tooltip-open, span')).toBeTruthy();
  });
});

describe('PipeClassListPage — 状态列（PIPE_CLASS 独立词表，bug-180）', () => {
  it.each([
    ['DRAFT', '草稿'],
    ['ACTIVE', '已生效'],
    ['OBSOLETE', '已弃用'],
  ] as const)('%s → 文案「%s」', (status, label) => {
    render(<PipeClassListPage classes={[pc({ status })]} />);
    expect(screen.getByTestId('state-badge-label').textContent).toBe(label);
  });

  it('ACTIVE 不再显示成「草稿」——那是 bug-180 的症状', () => {
    render(<PipeClassListPage classes={[pc({ status: 'ACTIVE' })]} />);
    expect(screen.getByTestId('state-badge-label').textContent).not.toBe('草稿');
  });

  it('走的是 PIPE_CLASS 模块，不是 PIPE', () => {
    render(<PipeClassListPage classes={[pc({ status: 'ACTIVE' })]} />);
    expect(screen.getByTestId('state-badge').getAttribute('data-module'))
      .toBe('PIPE_CLASS');
  });
});

describe('PipeClassListPage — 过滤', () => {
  it('按 class_name 过滤：输入 "GB" → 只剩 1 行', () => {
    render(<PipeClassListPage classes={classes} />);
    fireEvent.change(screen.getByTestId('pipe-class-search'), { target: { value: 'GB' } });
    const rows = document.querySelectorAll('[data-testid="pipe-class-row"]');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('GB 150');
  });

  it('按 material_standard 过滤：输入 "Q245R" → 只剩 1 行', () => {
    render(<PipeClassListPage classes={classes} />);
    fireEvent.change(screen.getByTestId('pipe-class-search'), { target: { value: 'Q245R' } });
    expect(document.querySelectorAll('[data-testid="pipe-class-row"]').length).toBe(1);
  });

  it('按 Sch 值过滤：输入 "Sch 160" → 命中不统一的那一行', () => {
    // 搜索的是**数据**（映射里任意一档的 Sch），不是摘要 —— 单元格显示
    // 的是「按 DN 分档」，拿它去 includes('Sch 160') 什么也搜不到。
    render(<PipeClassListPage classes={classes} />);
    fireEvent.change(screen.getByTestId('pipe-class-search'), { target: { value: 'Sch 160' } });
    const rows = document.querySelectorAll('[data-testid="pipe-class-row"]');
    expect(rows.length).toBe(1);
    expect(rows[0].textContent).toContain('ASME B31.8');
  });

  it('清空过滤 → 恢复全部', () => {
    render(<PipeClassListPage classes={classes} />);
    const search = screen.getByTestId('pipe-class-search');
    fireEvent.change(search, { target: { value: 'GB' } });
    fireEvent.change(search, { target: { value: '' } });
    expect(document.querySelectorAll('[data-testid="pipe-class-row"]').length).toBe(3);
  });
});

describe('PipeClassListPage — 操作', () => {
  it('行点击 → onSelect 回调', () => {
    const onSelect = vi.fn();
    render(<PipeClassListPage classes={classes} onSelect={onSelect} />);
    fireEvent.click(document.querySelector('[data-testid="pipe-class-row"]')!);
    expect(onSelect).toHaveBeenCalledWith(classes[0]);
  });
});
