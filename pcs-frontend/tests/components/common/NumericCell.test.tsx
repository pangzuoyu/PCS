/**
 * NumericCell 测试（P45-1-4 / Task 9）。
 *
 * 覆盖（SPEC §6.12）：
 * - 6 位有效数字（toPrecision）+ 2 位小数（toFixed）
 * - null → — ；NaN → —
 * - unit 显示 + 小一号 + 次要色 + 不换行 + 间距 4px
 * - assumed：橙色三角 ⚠ + value 正常色
 * - stale：橙色文字 var(--state-stale)
 * - conflict：红色文字 var(--state-check-rejected)
 * - monospace 默认 on（off 时 inherit）
 * - align default right
 * - 0 / 负数 / 大数（科学计数法自动）
 */
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';

import { NumericCell } from '../../../src/components/common/NumericCell';

describe('NumericCell — 格式化 (P45-1-4)', () => {
  it('默认 6 位有效数字', () => {
    render(<NumericCell value={123456.789} />);
    // toPrecision(6) + Number 转换 → '123457'（取整）
    expect(screen.getByTestId('numeric-cell-value').textContent).toBe('123457');
  });

  it('precisionType=decimal precision=2 → 货币 2 位小数', () => {
    render(<NumericCell value={1234.5} precision={2} precisionType="decimal" />);
    expect(screen.getByTestId('numeric-cell-value').textContent).toBe('1234.50');
  });

  it('precisionType=significant precision=3 → 3 位有效数字（toPrecision 直传）', () => {
    render(<NumericCell value={1234.5} precision={3} precisionType="significant" />);
    expect(screen.getByTestId('numeric-cell-value').textContent).toBe('1.23e+3');
  });

  it('null → — ', () => {
    render(<NumericCell value={null} />);
    expect(screen.getByTestId('numeric-cell-value').textContent).toBe('—');
    expect(screen.getByTestId('numeric-cell').getAttribute('data-null')).toBe('true');
  });

  it('NaN → — ', () => {
    render(<NumericCell value={Number.NaN} />);
    expect(screen.getByTestId('numeric-cell-value').textContent).toBe('—');
  });

  it('0 显示（toPrecision(6)=0.00000，data-null=false）', () => {
    render(<NumericCell value={0} />);
    // toPrecision(6) 对 0 → '0.00000'，区分于 null 的 '—'
    expect(screen.getByTestId('numeric-cell-value').textContent).toBe('0.00000');
    expect(screen.getByTestId('numeric-cell').getAttribute('data-null')).toBe('false');
  });

  it('负数 + precisionType=decimal', () => {
    render(<NumericCell value={-1.23456} precision={2} precisionType="decimal" />);
    expect(screen.getByTestId('numeric-cell-value').textContent).toBe('-1.23');
  });

  it('极大数 toPrecision 自动科学计数法', () => {
    // 1234567890123 toPrecision(6) → "1.23457e+12"
    render(<NumericCell value={1234567890123} precision={6} precisionType="significant" />);
    const text = screen.getByTestId('numeric-cell-value').textContent || '';
    expect(text.toLowerCase()).toContain('e+');
  });
});

describe('NumericCell — unit / 字体 / 对齐', () => {
  it('unit 渲染 + marginLeft 4 + whiteSpace nowrap', () => {
    render(<NumericCell value={100} unit="kPa" />);
    const unit = screen.getByTestId('numeric-cell-unit');
    expect(unit.textContent).toBe('kPa');
    const style = unit.getAttribute('style') || '';
    expect(style).toMatch(/margin-left:\s*4px/);
    expect(style).toMatch(/white-space:\s*nowrap/);
    expect(style).toMatch(/font-size:\s*11px/);
  });

  it('unit 缺省时不渲染 numeric-cell-unit', () => {
    render(<NumericCell value={100} />);
    expect(screen.queryByTestId('numeric-cell-unit')).toBeNull();
  });

  it('monospace 默认 on → fontFamily 含 mono', () => {
    render(<NumericCell value={100} />);
    const style = screen.getByTestId('numeric-cell-value').getAttribute('style') || '';
    expect(style).toContain('var(--font-mono');
  });

  it('monospace=false → fontFamily inherit', () => {
    render(<NumericCell value={100} monospace={false} />);
    const style = screen.getByTestId('numeric-cell-value').getAttribute('style') || '';
    expect(style).toContain('font-family: inherit');
  });

  it('align 默认 right', () => {
    render(<NumericCell value={100} />);
    expect(screen.getByTestId('numeric-cell').getAttribute('data-align')).toBe('right');
    const style = screen.getByTestId('numeric-cell-value').getAttribute('style') || '';
    expect(style).toMatch(/text-align:\s*right/);
  });

  it('align=left', () => {
    render(<NumericCell value={100} align="left" />);
    expect(screen.getByTestId('numeric-cell').getAttribute('data-align')).toBe('left');
  });
});

describe('NumericCell — status 着色', () => {
  it('assumed → ⚠ marker + value 正常色（不染橙）', () => {
    render(<NumericCell value={100} status="assumed" />);
    const marker = screen.getByTestId('numeric-cell-marker');
    expect(marker.textContent).toBe('⚠');
    expect(marker.getAttribute('style') || '').toContain('var(--state-change-pending)');
    // value 仍是 normal
    const valueStyle = screen.getByTestId('numeric-cell-value').getAttribute('style') || '';
    expect(valueStyle).toContain('var(--text-primary)');
  });

  it('stale → 橙色文字 var(--state-stale)', () => {
    render(<NumericCell value={100} status="stale" />);
    const valueStyle = screen.getByTestId('numeric-cell-value').getAttribute('style') || '';
    expect(valueStyle).toContain('var(--state-stale)');
  });

  it('conflict → 红色文字 var(--state-check-rejected)', () => {
    render(<NumericCell value={100} status="conflict" />);
    const valueStyle = screen.getByTestId('numeric-cell-value').getAttribute('style') || '';
    expect(valueStyle).toContain('var(--state-check-rejected)');
  });

  it('normal → 文字 var(--text-primary)', () => {
    render(<NumericCell value={100} status="normal" />);
    const valueStyle = screen.getByTestId('numeric-cell-value').getAttribute('style') || '';
    expect(valueStyle).toContain('var(--text-primary)');
  });

  it('non-assumed status 不渲染 ⚠ marker', () => {
    render(<NumericCell value={100} status="stale" />);
    expect(screen.queryByTestId('numeric-cell-marker')).toBeNull();
  });
});