/**
 * FormulaEditorPage 测试（P45-2-4 / Task 22）。
 *
 * 覆盖 SPEC §7.10.2 公式编辑器：
 * - 左编辑右预览布局
 * - 编辑区：公式名 / 模块 / 表达式 / 参数表 / preconditions / 标准来源 / 单元测试
 * - 预览区：LaTeX 渲染 / 测试参数 → 结果 / 单测运行结果
 * - preconditions 变量来源标注（input.* / params.* / result）
 * - onChange 全量回传 / onSave 保存回调
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { FormulaEditorPage, type FormulaEditor } from '../../../src/pages/config/FormulaEditorPage';

const base: FormulaEditor = {
  formula_id: 'f-1',
  name: '蒸汽压力公式',
  module: 'FLASH',
  expression: 'P = 101.325 * exp(-molecular_weight / (R * T))',
  params: [
    { name: 'T', unit: 'K', description: '温度', default_value: 500 },
    { name: 'molecular_weight', unit: 'g/mol', description: '分子量', default_value: 18 },
  ],
  preconditions: [
    { id: 'p1', expression: 'T > 0', source: 'input.T', reject_message: 'T 必须 > 0' },
  ],
  standard_source: 'IAPWS-IF97',
  test_cases: [
    { case_id: 'tc1', name: '正常工况', params: { T: 500 }, expected: 101.325 },
  ],
};

describe('FormulaEditorPage — 布局 (P45-2-4)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染标题 + 左右两栏', () => {
    render(<FormulaEditorPage formula={base} />);
    expect(screen.getByText('公式编辑器')).toBeTruthy();
    expect(screen.getByTestId('formula-editor-left')).toBeTruthy();
    expect(screen.getByTestId('formula-editor-right')).toBeTruthy();
  });

  it('左侧编辑区字段：公式名 / 模块 / 表达式 / 参数表 / preconditions / 标准来源 / 单测', () => {
    render(<FormulaEditorPage formula={base} />);
    const left = screen.getByTestId('formula-editor-left');
    expect(left.textContent).toContain('公式名');
    expect(left.textContent).toContain('模块');
    expect(left.textContent).toContain('表达式');
    expect(left.textContent).toContain('参数表');
    expect(left.textContent).toContain('preconditions');
    expect(left.textContent).toContain('标准来源');
    expect(left.textContent).toContain('单元测试');
  });

  it('右侧预览区：LaTeX 预览 / 测试参数 / 单测运行', () => {
    render(<FormulaEditorPage formula={base} />);
    const right = screen.getByTestId('formula-editor-right');
    expect(right.textContent).toContain('LaTeX');
    expect(right.textContent).toContain('测试参数');
    expect(right.textContent).toContain('运行结果');
  });
});

describe('FormulaEditorPage — 数据渲染', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('公式名 / 模块 / 标准来源渲染', () => {
    render(<FormulaEditorPage formula={base} />);
    const nameInput = screen.getByTestId('formula-name-input') as HTMLInputElement;
    expect(nameInput.value).toBe('蒸汽压力公式');
    const moduleSelect = screen.getByTestId('formula-module-select');
    expect(moduleSelect.textContent).toContain('FLASH');
    const standardInput = screen.getByTestId('formula-standard-input') as HTMLInputElement;
    expect(standardInput.value).toBe('IAPWS-IF97');
  });

  it('参数表行：名称 / 单位 / 描述 / 默认值', () => {
    render(<FormulaEditorPage formula={base} />);
    const rows = document.querySelectorAll('[data-testid="formula-param-row"]');
    expect(rows.length).toBe(2);
    const nameInput = document.querySelector(
      '[data-testid="formula-param-row"]:first-child input[data-testid="formula-param-name"]',
    ) as HTMLInputElement;
    expect(nameInput?.value).toBe('T');
    const unitInput = document.querySelector(
      '[data-testid="formula-param-row"]:first-child input[data-testid="formula-param-unit"]',
    ) as HTMLInputElement;
    expect(unitInput?.value).toBe('K');
    const descInput = document.querySelector(
      '[data-testid="formula-param-row"]:first-child input[data-testid="formula-param-desc"]',
    ) as HTMLInputElement;
    expect(descInput?.value).toBe('温度');
  });

  it('preconditions 显示 + 变量来源标注', () => {
    render(<FormulaEditorPage formula={base} />);
    const items = document.querySelectorAll('[data-testid="formula-precondition-item"]');
    expect(items.length).toBe(1);
    expect(items[0].textContent).toContain('T > 0');
    expect(items[0].textContent).toContain('input.T');
    expect(items[0].textContent).toContain('T 必须 > 0');
  });

  it('precondition 来源类型：input.* / params.* / result', () => {
    const formula: FormulaEditor = {
      ...base,
      preconditions: [
        { id: 'p1', expression: 'T > 0', source: 'input.T' },
        { id: 'p2', expression: 'mw > 0', source: 'params.molecular_weight' },
        { id: 'p3', expression: 'result != null', source: 'result' },
      ],
    };
    render(<FormulaEditorPage formula={formula} />);
    const items = document.querySelectorAll('[data-testid="formula-precondition-item"]');
    expect(items.length).toBe(3);
    expect(items[0].getAttribute('data-source')).toBe('input');
    expect(items[1].getAttribute('data-source')).toBe('params');
    expect(items[2].getAttribute('data-source')).toBe('result');
  });

  it('LaTeX 预览显示', () => {
    render(<FormulaEditorPage formula={base} />);
    const preview = screen.getByTestId('formula-latex-preview');
    expect(preview).toBeTruthy();
    expect(preview.textContent).toContain('P');
  });

  it('单元测试用例渲染', () => {
    render(<FormulaEditorPage formula={base} />);
    const cases = document.querySelectorAll('[data-testid="formula-test-case"]');
    expect(cases.length).toBe(1);
    expect(cases[0].textContent).toContain('正常工况');
  });
});

describe('FormulaEditorPage — 联动', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('公式名修改 → onChange 回调收到新值', () => {
    const onChange = vi.fn();
    render(<FormulaEditorPage formula={base} onChange={onChange} />);
    const nameInput = screen.getByTestId('formula-name-input') as HTMLInputElement;
    fireEvent.change(nameInput, { target: { value: '新公式名' } });
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as FormulaEditor;
    expect(lastCall.name).toBe('新公式名');
  });

  it('点击「保存」→ onSave 回调', () => {
    const onSave = vi.fn();
    render(<FormulaEditorPage formula={base} onSave={onSave} />);
    const saveBtn = screen.getByTestId('formula-save-btn');
    fireEvent.click(saveBtn);
    expect(onSave).toHaveBeenCalledTimes(1);
    expect(onSave.mock.calls[0][0].formula_id).toBe('f-1');
  });

  it('点击「添加参数」→ onChange 增加一行', () => {
    const onChange = vi.fn();
    render(<FormulaEditorPage formula={base} onChange={onChange} />);
    fireEvent.click(screen.getByTestId('formula-add-param-btn'));
    expect(onChange).toHaveBeenCalled();
    const lastCall = onChange.mock.calls[onChange.mock.calls.length - 1][0] as FormulaEditor;
    expect(lastCall.params.length).toBe(3);
  });
});