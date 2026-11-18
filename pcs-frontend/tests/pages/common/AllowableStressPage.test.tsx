/**
 * AllowableStressPage 测试（P45-3-3 / Task 30 · **P10-C · T1 改：查询驱动**）。
 *
 * ## ⚠️ 本文件现在测的是**「首屏不发请求」**（TODO-160）
 *
 * 契约 `GET /common/allowable-stress` 的 `material` + `temp_c` **都必填**
 * ⇒ ⇒ 此前页面首屏发**空查询** ⇒ 后端 **422**。
 * ⇒ ⇒ 现在的行为是：**两个参数都填了才发请求** ⇒ 首屏**零请求**。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import { AllowableStressPage } from '../../../src/pages/common/AllowableStressPage';
import { commonQueryApi } from '../../../src/api/common';
import type { AllowableStress } from '../../../src/types/common';

vi.mock('../../../src/api/common', () => ({
  commonQueryApi: {
    allowableStress: vi.fn(),
  },
}));

const allowableStress = vi.mocked(commonQueryApi.allowableStress);

// ⚠️ 字段名对齐契约 `AllowableStressResult`（2026-10-19）。
// 此前 fixture 与页面共用同一套**错名字**，于是测试绿、页面生产上空白
// —— 「fixture 与被测对象同源 ⇒ 零信号」的又一例。
//
// `source` 用契约里的真实取值形态（`ASME_B31.3_TABLE_A1`），
// 页面按前缀着色，所以 `ASME_…` 仍是蓝色、`GB_…` 仍是绿色。
const a106b100: AllowableStress = {
  material: 'A106-B',
  temp_c: 100,
  stress_mpa: 137.0,
  source: 'ASME_B31.3_TABLE_A1',
};

describe('AllowableStressPage — 首屏零请求 (P10-C · T1 · TODO-160)', () => {
  beforeEach(() => {
    allowableStress.mockReset();
  });

  it('**首屏不发请求**（契约的 material + temp_c 必填 ⇒ 空查询 422）', () => {
    render(<AllowableStressPage />);
    expect(allowableStress).not.toHaveBeenCalled();
    expect(document.body.textContent).toContain('输入材料牌号与温度后查询');
  });

  it('只填材料（缺温度）⇒ 仍不发请求', () => {
    render(<AllowableStressPage />);
    fireEvent.change(screen.getByTestId('stress-material-input'), {
      target: { value: 'A106-B' },
    });
    expect(allowableStress).not.toHaveBeenCalled();
  });
});

describe('AllowableStressPage — 查询驱动', () => {
  beforeEach(() => {
    allowableStress.mockReset();
    allowableStress.mockResolvedValue(a106b100);
  });

  it('材料 + 温度都填了 ⇒ 带两个必填参数发请求 ⇒ 渲染 1 行', async () => {
    render(<AllowableStressPage />);
    fireEvent.change(screen.getByTestId('stress-material-input'), {
      target: { value: 'A106-B' },
    });
    fireEvent.change(screen.getByTestId('stress-temp-input'), { target: { value: '100' } });
    await waitFor(() => expect(allowableStress).toHaveBeenCalledTimes(1));
    // ⚠️ **参数断言**：漏任一必填参数 ⇒ 后端 422 ⇒ 这条会红。
    expect(allowableStress).toHaveBeenCalledWith('A106-B', 100);
    await waitFor(() => {
      const tags = document.querySelectorAll('[data-testid="stress-standard"]');
      expect(tags.length).toBe(1);
      expect(tags[0].textContent).toBe('ASME_B31.3_TABLE_A1');
    });
    expect(document.body.textContent).toContain('ASME');
  });

  it('查询失败 ⇒ 显示错误（而不是空表）', async () => {
    allowableStress.mockRejectedValue({
      response: { status: 404, data: { code: 'COMMON_MATERIAL_NOT_FOUND', message: '材料 X 不在 ASME B31.3 Table A-1' } },
    });
    render(<AllowableStressPage />);
    fireEvent.change(screen.getByTestId('stress-material-input'), {
      target: { value: 'X' },
    });
    fireEvent.change(screen.getByTestId('stress-temp-input'), { target: { value: '100' } });
    await waitFor(() => {
      expect(screen.getByTestId('stress-error').textContent).toContain('不在 ASME B31.3 Table A-1');
    });
  });
});
