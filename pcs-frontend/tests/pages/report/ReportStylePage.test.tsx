/**
 * 样式修订入口（评审 #12，用户裁决：**放** —— 后端端点已存在，
 * 前端入口不可达是纯粹的实现遗漏）。
 *
 * ## 原缺陷（两层）
 *
 * 1. `startEdit` 两个调用点都传 `null` ⇒ `editing` 恒为 null ⇒
 *    `submit` 的 revise 分支和「修订（基于 X）」卡片标题全是死代码；
 *    又因「新建样式」在已有 ACTIVE 时 disabled ⇒ **用户无法修改已存在的样式**。
 * 2. 即便入口通了，revise 只发 `patch`（本次摸过的字段），而后端
 *    `style_json=patch` 整存 ⇒ 改一个字段会把旧版本其余定制**静默丢掉**。
 *    修订必须发**合并后**的完整样式（`{...editing.style, ...patch}`）。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, act } from '@testing-library/react';

const listStyles = vi.fn();
const reviseStyle = vi.fn();
const createStyle = vi.fn();
const activateStyle = vi.fn();

vi.mock('../../../src/api/reportBuilder', () => ({
  reportBuilderApi: {
    listStyles: (...a: unknown[]) => listStyles(...a),
    reviseStyle: (...a: unknown[]) => reviseStyle(...a),
    createStyle: (...a: unknown[]) => createStyle(...a),
    activateStyle: (...a: unknown[]) => activateStyle(...a),
  },
  errorMessage: () => 'x',
}));

import { ReportStylePage } from '../../../src/pages/report/ReportStylePage';

const V_ACTIVE = {
  style_id: 's-active', report_type: 'HEAT_DETAIL', project_id: null,
  version: '0.1.1', status: 'ACTIVE',
  style: { font_size_body: 12, line_spacing: 1.5 },
};
const V_OLD = {
  style_id: 's-old', report_type: 'HEAT_DETAIL', project_id: null,
  version: '0.1.0', status: 'SUPERSEDED',
  style: { font_size_body: 10 },
};

async function flush() {
  for (let i = 0; i < 6; i += 1) {
    await act(async () => { await Promise.resolve(); });
  }
}

beforeEach(() => {
  listStyles.mockReset(); reviseStyle.mockReset();
  createStyle.mockReset(); activateStyle.mockReset();
  listStyles.mockResolvedValue({ items: [V_ACTIVE, V_OLD] });
  reviseStyle.mockResolvedValue(V_ACTIVE);
});

describe('ReportStylePage — 修订入口（评审 #12）', () => {
  it('版本历史每行都有「修订」按钮 —— ACTIVE 行也不例外（改当前样式就是修订它）', async () => {
    render(<ReportStylePage />);
    await flush();
    const btns = screen.getAllByRole('button', { name: /修订/ });
    expect(btns.length).toBe(2);
  });

  it('点「修订」→ 卡片标题变成「修订（基于 <版本>）」，表单回填该版本的值', async () => {
    render(<ReportStylePage />);
    await flush();
    // 点旧版本（0.1.0）那一行的修订 —— 通过行内定位
    fireEvent.click(withinRow(/0\.1\.0/).getByRole('button', { name: /修订/ }));
    await flush();
    expect(document.body.textContent).toContain('修订（基于 0.1.0）');
    // 表单 current 必须来自 **editing**（0.1.0 的 font_size_body=10），
    // 不是 ACTIVE 的 12 —— 否则用户改之前看到的就是错的基线。
    const input = document.querySelector(
      '.ant-input-number-input') as HTMLInputElement;
    expect(input?.value).toBe('10');
  });

  it('修订提交发**合并后**的完整样式 —— 只改一个字段不丢旧版本其余定制', async () => {
    render(<ReportStylePage />);
    await flush();
    // 修订 ACTIVE（0.1.1：font_size_body=12, line_spacing=1.5）
    fireEvent.click(withinRow(/0\.1\.1/).getByRole('button', { name: /修订/ }));
    await flush();
    const input = document.querySelector(
      '.ant-input-number-input') as HTMLInputElement;
    fireEvent.change(input, { target: { value: '14' } });
    await flush();
    fireEvent.click(screen.getByRole('button', { name: /保存为新版本/ }));
    await flush();

    expect(reviseStyle).toHaveBeenCalledTimes(1);
    const [id, body] = reviseStyle.mock.calls[0];
    expect(id).toBe('s-active');
    expect((body as { style: Record<string, unknown> }).style).toEqual(
      { font_size_body: 14, line_spacing: 1.5 });
  });
});

/**
 * 按行内版本号文本定位该行（td 级），返回**只在该行内查找**的查询器。
 *
 * ⚠️ 原签名写 `ReturnType<typeof screen>` 并 `as` 了一下 ——
 * 那是**撒谎**：`screen` 是对象不是函数，`ReturnType<...>` 直接不满足
 * `(...args:any)=>any` 约束（TS2344），而 `as` 让它一路混过去。
 * 而且这里**只用到 `getByRole`**，把整个 `screen` 摊平进来纯属噪音
 * （`getByText` 等仍查全表，只是个会误导人的字段）。
 * 改成结构化类型：只有真正提供的东西，一不多一不少。
 */
function withinRow(versionRe: RegExp): { getByRole: (role: string, opts?: { name?: RegExp }) => HTMLElement } {
  const cells = Array.from(document.querySelectorAll('td'))
    .filter((td) => versionRe.test(td.textContent ?? ''));
  if (!cells.length) throw new Error(`没找到版本 ${versionRe} 的行`);
  const row = cells[0].closest('tr') as HTMLElement;
  return {
    getByRole: (role: string, opts?: { name?: RegExp }) => {
      const hit = Array.from(row.querySelectorAll('button'))
        .find((b) => (opts?.name ?? /.*/).test(b.textContent ?? ''));
      if (!hit) throw new Error(`行内没有 ${role} 按钮`);
      return hit as HTMLElement;
    },
  };
}
