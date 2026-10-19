/**
 * PropertySearchPage 测试（P45-3-3 / Task 30）。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PropertySearchPage } from '../../../src/pages/common/PropertySearchPage';
import type { ComponentProperty } from '../../../src/types/common';

// ⚠️ 字段名对齐契约 `MaterialSearchResult`（2026-10-19）。
// 契约只有 5 个字段；`component_id`/`cas_number` 不存在，临界参数属于
// 另一个 schema（用户裁决：砍列，不做 N+1）。
const components: ComponentProperty[] = [
  { cas: '74-82-8',   name: 'Methane', formula: 'CH4',  mw: 16.04, source: 'CHEMICALS_LIBRARY' },
  { cas: '7732-18-5', name: 'Water',   formula: 'H2O',  mw: 18.02, source: 'CHEMICALS_LIBRARY' },
  { cas: '71-43-2',   name: 'Benzene', formula: 'C6H6', mw: 78.11, source: 'CHEMICALS_LIBRARY' },
];

describe('PropertySearchPage — 渲染 (P45-3-3)', () => {
  it('渲染标题 + 3 张物性卡片', () => {
    render(<PropertySearchPage components={components} />);
    const cards = document.querySelectorAll('[data-testid="property-card"]');
    expect(cards.length).toBe(3);
  });

  it('按 name 过滤：输入 "Meth" → 只剩 1 张', () => {
    render(<PropertySearchPage components={components} />);
    fireEvent.change(screen.getByTestId('property-search-input'), { target: { value: 'Meth' } });
    const cards = document.querySelectorAll('[data-testid="property-card"]');
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain('CH4');
  });

  it('按 formula 过滤：输入 "C6H6" → 只剩 Benzene', () => {
    render(<PropertySearchPage components={components} />);
    fireEvent.change(screen.getByTestId('property-search-input'), { target: { value: 'C6H6' } });
    const cards = document.querySelectorAll('[data-testid="property-card"]');
    expect(cards.length).toBe(1);
  });

  it('按 CAS 过滤：输入 "7732-18-5" → 只剩 Water', () => {
    render(<PropertySearchPage components={components} />);
    fireEvent.change(screen.getByTestId('property-search-input'), { target: { value: '7732-18-5' } });
    const cards = document.querySelectorAll('[data-testid="property-card"]');
    expect(cards.length).toBe(1);
    expect(cards[0].textContent).toContain('Water');
  });
});

describe('PropertySearchPage — 操作', () => {
  it('点击收藏 → onFavorite 回调', () => {
    const onFavorite = vi.fn();
    render(<PropertySearchPage components={components} onFavorite={onFavorite} />);
    const stars = document.querySelectorAll('[data-testid="property-favorite"]');
    fireEvent.click(stars[0]);
    // 契约里没有 component_id，回调收到的是 cas
    expect(onFavorite).toHaveBeenCalledWith('74-82-8');
  });
});