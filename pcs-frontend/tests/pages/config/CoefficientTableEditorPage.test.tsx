/**
 * CoefficientTableEditorPage 测试（P45-2-5 / Task 23）。
 *
 * 覆盖 SPEC §7.10.3 系数表编辑器：
 * - 表格编辑（in-place）
 * - 条件分行（按温度/压力等条件范围）
 * - 批量修改（选中多行 → 批量改来源/批量删除）
 * - 来源标注（每行 tag 显示 standard 引用）
 * - 版本对比（v1 vs v2 高亮差异）
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { CoefficientTableEditorPage, type CoefficientRow } from '../../../src/pages/config/CoefficientTableEditorPage';

const rows: CoefficientRow[] = [
  {
    row_id: 'r1',
    condition: 'T 300~500K',
    factor_a: 1.2,
    factor_b: 0.5,
    source: 'IAPWS-IF97 §3.2',
  },
  {
    row_id: 'r2',
    condition: 'T 500~800K',
    factor_a: 1.8,
    factor_b: 0.7,
    source: 'Perry 8ed',
  },
  {
    row_id: 'r3',
    condition: 'T >800K',
    factor_a: 2.5,
    factor_b: 1.0,
    source: 'Aspen DB',
  },
];

describe('CoefficientTableEditorPage — 渲染 (P45-2-5)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染标题 + 工具栏 + 表格', () => {
    render(<CoefficientTableEditorPage rows={rows} />);
    expect(screen.getByText('系数表编辑器')).toBeTruthy();
    expect(screen.getByTestId('coefficient-toolbar')).toBeTruthy();
    expect(screen.getByTestId('coefficient-table')).toBeTruthy();
  });

  it('表格列：条件 / 系数 A / 系数 B / 来源', () => {
    render(<CoefficientTableEditorPage rows={rows} />);
    const table = screen.getByTestId('coefficient-table');
    expect(table.textContent).toContain('条件');
    expect(table.textContent).toContain('系数 A');
    expect(table.textContent).toContain('系数 B');
    expect(table.textContent).toContain('来源');
  });

  it('渲染所有行', () => {
    render(<CoefficientTableEditorPage rows={rows} />);
    expect(document.querySelectorAll('[data-testid="coefficient-row"]').length).toBe(3);
  });

  it('每行显示来源 tag', () => {
    render(<CoefficientTableEditorPage rows={rows} />);
    const row = document.querySelector('[data-testid="coefficient-row"]')!;
    expect(row.textContent).toContain('IAPWS-IF97 §3.2');
  });
});

describe('CoefficientTableEditorPage — 表格编辑', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('in-place 编辑条件列 → onChange 收到新 rows', () => {
    const onChange = vi.fn();
    render(<CoefficientTableEditorPage rows={rows} onChange={onChange} />);
    const condInput = document.querySelector(
      '[data-testid="coefficient-row"]:first-child input[data-testid="coefficient-cond-input"]',
    ) as HTMLInputElement;
    fireEvent.change(condInput, { target: { value: 'T 250~550K' } });
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as CoefficientRow[];
    expect(lastCall[0].condition).toBe('T 250~550K');
  });

  it('in-place 编辑 factor_a', () => {
    const onChange = vi.fn();
    render(<CoefficientTableEditorPage rows={rows} onChange={onChange} />);
    const input = document.querySelector(
      '[data-testid="coefficient-row"]:first-child input[data-testid="coefficient-factor_a-input"]',
    ) as HTMLInputElement;
    fireEvent.change(input, { target: { value: '1.5' } });
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as CoefficientRow[];
    expect(lastCall[0].factor_a).toBe(1.5);
  });

  it('点击「添加行」→ rows 增加一行', () => {
    const onChange = vi.fn();
    render(<CoefficientTableEditorPage rows={rows} onChange={onChange} />);
    fireEvent.click(screen.getByTestId('coefficient-add-row'));
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as CoefficientRow[];
    expect(lastCall.length).toBe(4);
  });
});

describe('CoefficientTableEditorPage — 批量修改', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('勾选两行 → 批量修改来源', () => {
    const onChange = vi.fn();
    render(<CoefficientTableEditorPage rows={rows} onChange={onChange} />);
    // 勾选前两行
    const checkboxes = document.querySelectorAll(
      '[data-testid="coefficient-row"] input[data-testid="coefficient-select"]',
    );
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    // 批量改来源
    const sourceInput = screen.getByTestId('coefficient-bulk-source-input');
    fireEvent.change(sourceInput, { target: { value: '新版来源' } });
    fireEvent.click(screen.getByTestId('coefficient-bulk-source-apply'));
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as CoefficientRow[];
    expect(lastCall[0].source).toBe('新版来源');
    expect(lastCall[1].source).toBe('新版来源');
    expect(lastCall[2].source).toBe('Aspen DB'); // 未勾选不动
  });

  it('勾选两行 → 批量删除', () => {
    const onChange = vi.fn();
    render(<CoefficientTableEditorPage rows={rows} onChange={onChange} />);
    const checkboxes = document.querySelectorAll(
      '[data-testid="coefficient-row"] input[data-testid="coefficient-select"]',
    );
    fireEvent.click(checkboxes[0]);
    fireEvent.click(checkboxes[1]);
    fireEvent.click(screen.getByTestId('coefficient-bulk-delete'));
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as CoefficientRow[];
    expect(lastCall.length).toBe(1);
    expect(lastCall[0].row_id).toBe('r3');
  });
});

describe('CoefficientTableEditorPage — 版本对比', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('传入 prevVersion → 显示版本对比面板', () => {
    const prev: CoefficientRow[] = [
      { row_id: 'r1', condition: 'T 300~500K', factor_a: 1.2, factor_b: 0.5, source: 'IAPWS-IF97' },
      { row_id: 'r2', condition: 'T 500~800K', factor_a: 1.5, factor_b: 0.7, source: 'Perry 8ed' },
    ];
    render(
      <CoefficientTableEditorPage rows={rows} prevVersion={prev} prevLabel="v1" currentLabel="v2" />,
    );
    expect(screen.getByTestId('coefficient-diff-panel')).toBeTruthy();
    // r2.factor_a 1.5 → 1.8（变化）
    // r3 是新增（仅 v2 有）
    const diffRows = document.querySelectorAll('[data-testid="coefficient-diff-row"]');
    expect(diffRows.length).toBeGreaterThan(0);
  });

  it('变化行带 data-diff 属性（changed/added/removed）', () => {
    const prev: CoefficientRow[] = [
      { row_id: 'r1', condition: 'T 300~500K', factor_a: 1.2, factor_b: 0.5, source: 'IAPWS-IF97' },
      { row_id: 'r4', condition: 'OLD ROW', factor_a: 99, factor_b: 99, source: 'OLD' },
    ];
    render(
      <CoefficientTableEditorPage rows={rows} prevVersion={prev} prevLabel="v1" currentLabel="v2" />,
    );
    const changed = document.querySelectorAll('[data-testid="coefficient-diff-row"][data-diff="changed"]');
    const added = document.querySelectorAll('[data-testid="coefficient-diff-row"][data-diff="added"]');
    const removed = document.querySelectorAll('[data-testid="coefficient-diff-row"][data-diff="removed"]');
    expect(changed.length).toBeGreaterThan(0);
    expect(added.length).toBeGreaterThan(0); // r3 新增
    expect(removed.length).toBeGreaterThan(0); // r4 仅 v1
  });
});

describe('CoefficientTableEditorPage — 保存', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('点击「保存」→ onSave 回调收到 rows', () => {
    const onSave = vi.fn();
    render(<CoefficientTableEditorPage rows={rows} onSave={onSave} />);
    fireEvent.click(screen.getByTestId('coefficient-save-btn'));
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0].length).toBe(3);
  });
});