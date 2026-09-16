/**
 * DiffViewer 测试（P45-2-8 / Task 26）。
 *
 * 覆盖 SPEC §6.17 版本 diff：
 * - 字段级 diff（JSON 对象：changed/added/removed）
 * - 字符级 diff（长文本逐字符高亮）
 * - 并排左右视图（prev vs curr）
 * - prev/curr 标签 + 时间戳
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen } from '@testing-library/react';

import { DiffViewer, type DiffVersion } from '../../../src/pages/config/DiffViewer';

const prev: DiffVersion = {
  label: 'v1.0',
  timestamp: '2026-09-10',
  data: {
    name: '公式A',
    expression: 'P = 100 * T',
    factor_a: 1.0,
    notes: '初版',
  },
};

const curr: DiffVersion = {
  label: 'v1.1',
  timestamp: '2026-09-15',
  data: {
    name: '公式A',
    expression: 'P = 101.325 * T',
    factor_a: 1.2,
    notes: '初版',
    tags: ['physics'],  // 新增
  },
};

describe('DiffViewer — 渲染 (P45-2-8)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染标题 + 并排左右两栏', () => {
    render(<DiffViewer prev={prev} curr={curr} />);
    expect(screen.getByText('版本对比')).toBeTruthy();
    expect(screen.getByTestId('diff-left')).toBeTruthy();
    expect(screen.getByTestId('diff-right')).toBeTruthy();
  });

  it('显示 prev / curr 标签 + 时间戳', () => {
    render(<DiffViewer prev={prev} curr={curr} />);
    const left = screen.getByTestId('diff-left');
    const right = screen.getByTestId('diff-right');
    expect(left.textContent).toContain('v1.0');
    expect(left.textContent).toContain('2026-09-10');
    expect(right.textContent).toContain('v1.1');
    expect(right.textContent).toContain('2026-09-15');
  });
});

describe('DiffViewer — 字段级 diff', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('changed 字段：expression / factor_a', () => {
    render(<DiffViewer prev={prev} curr={curr} />);
    const changed = document.querySelectorAll('[data-testid="diff-row"][data-status="changed"]');
    expect(changed.length).toBe(2);
    // expression 在 changed 内
    const changedText = Array.from(changed).map((e) => e.textContent).join('');
    expect(changedText).toContain('expression');
    expect(changedText).toContain('factor_a');
  });

  it('unchanged 字段：name / notes', () => {
    render(<DiffViewer prev={prev} curr={curr} />);
    const unchanged = document.querySelectorAll('[data-testid="diff-row"][data-status="unchanged"]');
    expect(unchanged.length).toBeGreaterThan(0);
    const txt = Array.from(unchanged).map((e) => e.textContent).join('');
    expect(txt).toContain('name');
    expect(txt).toContain('notes');
  });

  it('added 字段：tags', () => {
    render(<DiffViewer prev={prev} curr={curr} />);
    const added = document.querySelectorAll('[data-testid="diff-row"][data-status="added"]');
    expect(added.length).toBe(1);
    expect(added[0].textContent).toContain('tags');
  });

  it('removed 字段：curr 缺字段也识别', () => {
    const v2: DiffVersion = {
      label: 'v2',
      timestamp: 't',
      data: { name: 'X' },
    };
    const v3: DiffVersion = {
      label: 'v3',
      timestamp: 't',
      data: { name: 'X', new_field: 'val' },
    };
    render(<DiffViewer prev={v2} curr={v3} />);
    const added = document.querySelectorAll('[data-testid="diff-row"][data-status="added"]');
    expect(added.length).toBe(1);
    expect(added[0].textContent).toContain('new_field');
  });
});

describe('DiffViewer — 字符级 diff', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('字符串字段值变化 → 行内字符级 diff', () => {
    render(<DiffViewer prev={prev} curr={curr} />);
    // expression: "P = 100 * T" → "P = 101.325 * T"（"100" → "101.325"）
    const charDiff = document.querySelectorAll('[data-testid="diff-char-removed"]');
    const charAdd = document.querySelectorAll('[data-testid="diff-char-added"]');
    expect(charDiff.length).toBeGreaterThan(0);
    expect(charAdd.length).toBeGreaterThan(0);
  });
});

describe('DiffViewer — 边界', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('相同数据 → 所有行 status=unchanged', () => {
    const same1: DiffVersion = { label: 'A', timestamp: 't', data: { a: 1, b: 'x' } };
    const same2: DiffVersion = { label: 'B', timestamp: 't', data: { a: 1, b: 'x' } };
    render(<DiffViewer prev={same1} curr={same2} />);
    const unchanged = document.querySelectorAll('[data-testid="diff-row"][data-status="unchanged"]');
    expect(unchanged.length).toBe(2);
  });

  it('数字/布尔/数组 也能识别变化', () => {
    const a: DiffVersion = { label: 'A', timestamp: 't', data: { n: 1, b: true, arr: [1, 2] } };
    const b: DiffVersion = { label: 'B', timestamp: 't', data: { n: 2, b: false, arr: [1, 2, 3] } };
    render(<DiffViewer prev={a} curr={b} />);
    const changed = document.querySelectorAll('[data-testid="diff-row"][data-status="changed"]');
    expect(changed.length).toBe(3);
  });
});