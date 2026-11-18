/**
 * ToxicityExplosivityPage 测试（P45-3-3 / Task 30 · **P10-C · T1 改：查询驱动**）。
 *
 * ## ⚠️ 本文件现在测的是**「首屏不发请求」**（TODO-160）
 *
 * 契约 `GET /common/safety` 的 `cas` **必填** ⇒ ⇒ 此前页面首屏发**空查询**
 * ⇒ 后端 **422** ⇒ 首屏错误态。
 * ⇒ ⇒ 现在的行为是：**输入 CAS 才发请求** ⇒ 首屏**零请求**。
 *
 * ⚠️ 字段名对齐契约 `SafetyResult`（2026-10-19）。
 * LD50 / PEL 已砍：后端 `_SAFETY_DATA` 每条只有 `{name, tox, lfl, ufl}`，
 * 没有任何 LD50/PEL 数据，也没有对应的 DB 表（用户裁决：先查后端再决定）。
 * 毒性等级改用后端 `tox` 的真实词表 —— 比旧的 HazardClass 多一个 `NONE`。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { ToxicityExplosivityPage } from '../../../src/pages/common/ToxicityExplosivityPage';
import { commonQueryApi } from '../../../src/api/common';
import type { ToxicityClass } from '../../../src/types/common';

vi.mock('../../../src/api/common', () => ({
  commonQueryApi: {
    safety: vi.fn(),
  },
}));

const safety = vi.mocked(commonQueryApi.safety);

const benzene: ToxicityClass = {
  cas: '71-43-2',
  name: 'Benzene',
  toxicity_class: 'HIGH',
  lel_vol_pct: 1.2,
  uel_vol_pct: 7.8,
};

describe('ToxicityExplosivityPage — 首屏零请求 (P10-C · T1 · TODO-160)', () => {
  beforeEach(() => {
    safety.mockReset();
  });

  it('**首屏不发请求**（契约的 cas 必填 ⇒ 空查询 422）', () => {
    render(<ToxicityExplosivityPage />);
    expect(safety).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain('输入 CAS 后查询');
  });
});

describe('ToxicityExplosivityPage — 查询驱动', () => {
  beforeEach(() => {
    safety.mockReset();
    safety.mockResolvedValue(benzene);
  });

  it('输入 CAS ⇒ 带 cas 发请求 ⇒ 渲染 HIGH 卡片', async () => {
    render(<ToxicityExplosivityPage />);
    fireEvent.change(screen.getByTestId('toxicity-cas-input'), {
      target: { value: '71-43-2' },
    });
    await waitFor(() => expect(safety).toHaveBeenCalledTimes(1));
    // ⚠️ **参数断言**：漏了 cas ⇒ 后端 422 ⇒ 这条会红。
    expect(safety).toHaveBeenCalledWith('71-43-2');
    await waitFor(() => {
      const highCard = document.querySelector('[data-toxicity-class="HIGH"]');
      expect(highCard).toBeTruthy();
      expect(highCard!.textContent).toContain('Benzene');
      const tags = highCard!.querySelectorAll('[data-testid="toxicity-tag"]');
      expect(tags.length).toBe(1);
    });
  });

  it('爆炸极限按契约的拍平字段显示', async () => {
    render(<ToxicityExplosivityPage />);
    fireEvent.change(screen.getByTestId('toxicity-cas-input'), {
      target: { value: '71-43-2' },
    });
    await waitFor(() => {
      expect(document.querySelector('[data-toxicity-class="HIGH"]')).toBeTruthy();
    });
    expect(document.body.textContent).toContain('1.2–7.8');
  });

  it('无爆炸极限 ⇒ 显示「—」而不是 "null–null"', async () => {
    safety.mockResolvedValue({
      cas: '7732-18-5',
      name: 'Water',
      toxicity_class: 'NONE',
      lel_vol_pct: null,
      uel_vol_pct: null,
    });
    render(<ToxicityExplosivityPage />);
    fireEvent.change(screen.getByTestId('toxicity-cas-input'), {
      target: { value: '7732-18-5' },
    });
    await waitFor(() => {
      expect(document.querySelector('[data-toxicity-class="NONE"]')).toBeTruthy();
    });
    expect(document.body.textContent).toContain('—');
  });

  it('查询失败 ⇒ 显示错误（而不是空卡片）', async () => {
    safety.mockRejectedValue({
      response: { status: 404, data: { code: 'COMMON_MATERIAL_NOT_FOUND', message: 'CAS X 未命中' } },
    });
    render(<ToxicityExplosivityPage />);
    fireEvent.change(screen.getByTestId('toxicity-cas-input'), { target: { value: 'X' } });
    await waitFor(() => {
      expect(screen.getByTestId('toxicity-error').textContent).toContain('CAS X 未命中');
    });
  });

  it('显示标题「毒性爆炸分类」', () => {
    render(<ToxicityExplosivityPage />);
    expect(screen.getByTestId('toxicity-explosivity-page')).toBeTruthy();
  });
});
