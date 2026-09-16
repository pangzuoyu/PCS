/**
 * PropertySearchPage 测试（P45-3-3 / Task 30）。
 */
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { PropertySearchPage } from '../../../src/pages/common/PropertySearchPage';
import type { ComponentProperty } from '../../../src/types/common';

const components: ComponentProperty[] = [
  { component_id: 'c-1', name: 'Methane', formula: 'CH4', cas_number: '74-82-8', mw: 16.04, tc_k: 190.6, pc_mpa: 4.6, omega: 0.011 },
  { component_id: 'c-2', name: 'Water',   formula: 'H2O', cas_number: '7732-18-5', mw: 18.02, tc_k: 647.1, pc_mpa: 22.06, omega: 0.344 },
  { component_id: 'c-3', name: 'Benzene', formula: 'C6H6', cas_number: '71-43-2', mw: 78.11, tc_k: 562.1, pc_mpa: 4.9, omega: 0.21 },
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
    expect(onFavorite).toHaveBeenCalledWith('c-1');
  });
});