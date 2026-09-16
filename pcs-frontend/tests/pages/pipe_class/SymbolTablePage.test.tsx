/**
 * SymbolTablePage 测试（P45-3-2 / Task 29）。
 *
 * 覆盖 SPEC §7.9.3：
 * - 按 category 分组（fluid / service / phase / toxicity）
 * - 表格列：symbol / meaning / 操作
 * - 删除按钮 → onDelete 回调
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { SymbolTablePage } from '../../../src/pages/pipe_class/SymbolTablePage';
import type { SymbolMapping } from '../../../src/types/pipeClass';

const mappings: SymbolMapping[] = [
  { symbol: 'W', meaning: 'Water', category: 'fluid' },
  { symbol: 'O', meaning: 'Oil', category: 'fluid' },
  { symbol: 'P', meaning: 'Process', category: 'service' },
  { symbol: 'V', meaning: 'Vapor', category: 'phase' },
  { symbol: 'T', meaning: 'Toxic', category: 'toxicity' },
];

describe('SymbolTablePage — 渲染 (P45-3-2)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染 4 类标签 + 默认展开 fluid / service', () => {
    render(<SymbolTablePage mappings={mappings} />);
    expect(screen.getByTestId('symbol-table-page')).toBeTruthy();
    expect(document.body.textContent).toContain('介质');
    expect(document.body.textContent).toContain('服务');
    expect(document.body.textContent).toContain('相态');
    expect(document.body.textContent).toContain('毒性');
  });

  it('fluid + service 组：默认展开渲染 3 行（2 fluid + 1 service）', () => {
    render(<SymbolTablePage mappings={mappings} />);
    const rows = document.querySelectorAll('[data-testid="symbol-row"]');
    expect(rows.length).toBe(3);
    expect(rows[0].textContent).toContain('W');
    expect(rows[0].textContent).toContain('Water');
  });
});

describe('SymbolTablePage — 操作', () => {
  it('点击「删除」→ onDelete 回调（symbol 字符串）', () => {
    const onDelete = vi.fn();
    render(<SymbolTablePage mappings={mappings} onDelete={onDelete} />);
    const deleteButtons = document.querySelectorAll('[data-testid="symbol-delete"]');
    fireEvent.click(deleteButtons[0]);
    expect(onDelete).toHaveBeenCalledTimes(1);
    expect(onDelete).toHaveBeenCalledWith('W');
  });
});