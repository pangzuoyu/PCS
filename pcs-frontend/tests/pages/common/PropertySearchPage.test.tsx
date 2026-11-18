/**
 * PropertySearchPage 测试（P45-3-3 / Task 30 · **P10-C · T1 改：查询驱动**）。
 *
 * ## ⚠️ 本文件现在测的是**「首屏不发请求」**（TODO-160）
 *
 * 契约 `GET /common/materials/search` 的 `keyword` **必填**（`min_length=1`）
 * ⇒ ⇒ 此前页面首屏发**空查询** ⇒ 后端 **422**。
 * ⇒ ⇒ 现在的行为是：**填了关键字才发请求** ⇒ 首屏**零请求**。
 *
 * ⚠️ 断言写在**调用参数**上（`searchMaterials` 收到了哪个 keyword）⇒ ⇒
 * 「参数漏了 ⇒ 422」这条缺陷**一定会被这条断言逮到**。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { PropertySearchPage } from '../../../src/pages/common/PropertySearchPage';
import { commonQueryApi } from '../../../src/api/common';
import type { ComponentProperty } from '../../../src/types/common';

vi.mock('../../../src/api/common', () => ({
  commonQueryApi: {
    searchMaterials: vi.fn(),
  },
}));

const searchMaterials = vi.mocked(commonQueryApi.searchMaterials);

// ⚠️ 字段名对齐契约 `MaterialSearchResult`（2026-10-19）。
// 契约只有 5 个字段；`component_id`/`cas_number` 不存在，临界参数属于
// 另一个 schema（用户裁决：砍列，不做 N+1）。
const methane: ComponentProperty = {
  cas: '74-82-8',
  name: 'Methane',
  formula: 'CH4',
  mw: 16.04,
  source: 'CHEMICALS_LIBRARY',
};

describe('PropertySearchPage — 首屏零请求 (P10-C · T1 · TODO-160)', () => {
  beforeEach(() => {
    searchMaterials.mockReset();
  });

  it('**首屏不发请求**（契约的 keyword 必填 ⇒ 空查询 422）', () => {
    render(<PropertySearchPage />);
    // ⚠️ 同步断言：首屏**一次都没调** ⇒ 不可能有 422。
    expect(searchMaterials).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain('输入关键字后查询');
  });
});

describe('PropertySearchPage — 查询驱动', () => {
  beforeEach(() => {
    searchMaterials.mockReset();
    searchMaterials.mockResolvedValue([methane]);
  });

  it('输入关键字 ⇒ 带上 keyword 发请求 ⇒ 渲染命中卡片', async () => {
    render(<PropertySearchPage />);
    fireEvent.change(screen.getByTestId('property-search-input'), {
      target: { value: 'Meth' },
    });
    await waitFor(() => expect(searchMaterials).toHaveBeenCalledTimes(1));
    // ⚠️ **参数断言**：漏了 keyword ⇒ 后端 422 ⇒ 这条会红。
    expect(searchMaterials).toHaveBeenCalledWith('Meth');
    await waitFor(() => {
      const cards = document.querySelectorAll('[data-testid="property-card"]');
      expect(cards.length).toBe(1);
      expect(cards[0].textContent).toContain('CH4');
    });
  });

  it('清空输入 ⇒ 回到「没查过」且不再有结果', async () => {
    render(<PropertySearchPage />);
    const input = screen.getByTestId('property-search-input');
    fireEvent.change(input, { target: { value: 'Meth' } });
    await waitFor(() => expect(searchMaterials).toHaveBeenCalledTimes(1));
    fireEvent.change(input, { target: { value: '' } });
    await waitFor(() => {
      expect(document.querySelectorAll('[data-testid="property-card"]').length).toBe(0);
    });
    expect(document.body.textContent).toContain('输入关键字后查询');
  });

  it('查询失败 ⇒ 显示错误（而不是空表）', async () => {
    searchMaterials.mockRejectedValue({
      response: { status: 422, data: { code: 'COMMON_MISSING_KEYWORD', message: 'keyword 必填' } },
    });
    render(<PropertySearchPage />);
    fireEvent.change(screen.getByTestId('property-search-input'), {
      target: { value: 'X' },
    });
    await waitFor(() => {
      expect(screen.getByTestId('property-search-error').textContent).toContain('keyword 必填');
    });
  });
});

describe('PropertySearchPage — 操作', () => {
  beforeEach(() => {
    searchMaterials.mockReset();
    searchMaterials.mockResolvedValue([methane]);
  });

  it('点击收藏 → onFavorite 回调', async () => {
    const onFavorite = vi.fn();
    render(<PropertySearchPage onFavorite={onFavorite} />);
    fireEvent.change(screen.getByTestId('property-search-input'), {
      target: { value: 'Meth' },
    });
    await waitFor(() => {
      expect(document.querySelectorAll('[data-testid="property-card"]').length).toBe(1);
    });
    const stars = document.querySelectorAll('[data-testid="property-favorite"]');
    fireEvent.click(stars[0]);
    // 契约里没有 component_id，回调收到的是 cas
    expect(onFavorite).toHaveBeenCalledWith('74-82-8');
  });
});
