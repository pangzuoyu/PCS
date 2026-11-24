/**
 * 报表定义列表页 —— 「**被退回**」标记（P10-J · T2 · TODO-197b）。
 *
 * ## 断什么
 *
 * | # | 断言 | 为什么 |
 * |---|---|---|
 * | ① | `rejected_at` 有值 ⇒ ⇒ 渲染「被退回」badge | 人裁 ①：状态**不变**（仍 DRAFT）⇒ ⇒ ⇒ 「待审 vs 待改」**只由这个标记**表达 |
 * | ② | badge 的 Tooltip 里是**原因** | 创建人要看得懂**要改什么** ⇒ ⇒ ⇒ 原因不能只是「被打回了」 |
 * | ③ | 没被打回的行 ⇒ ⇒ **没有**这个 badge | 否则 badge 变成「人人都有」⇒ ⇒ ⇒ 等于没有 |
 *
 * ⚠️ **为什么用 `rejected_at` 而不是 `status`** —— 状态**不变**（仍是 DRAFT）
 * ⇒ ⇒ ⇒ 判据只能是被退回标记 ⇒ ⇒ ⇒ 用 `status` 判会**永远为假**。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

const list = vi.fn();

vi.mock('../../../src/api/reportBuilder', () => ({
  reportBuilderApi: {
    list: (...a: unknown[]) => list(...a),
  },
  errorMessage: () => '未知错误',
}));

import { ReportDefinitionListPage } from '../../../src/pages/report/ReportDefinitionListPage';

function def(defId: string, name: string, rejected: boolean) {
  return {
    def_id: defId,
    project_id: null,
    name,
    category: '设备类',
    description: '按位号列设备',
    definition_json: {
      DataSources: [{ source: 'EQUIP_LIST' }],
      SelectedFields: [
        { source: 'EQUIP_LIST', field: 'tag_number', alias: '位号', order: 0, visible: true },
      ],
      FilterConditions: [],
    },
    output_format: 'pdf',
    max_rows: 10000,
    version: '0.1.0',
    status: 'DRAFT',
    shared_with: 'ALL_USERS',
    created_by: '00000000-0000-0000-0000-0000000000a1',
    created_at: '2026-11-23T00:00:00Z',
    updated_at: null,
    rejected_at: rejected ? '2026-11-24T03:00:00Z' : null,
    rejected_by: rejected ? '00000000-0000-0000-0000-0000000000a2' : null,
    reject_reason: rejected ? '「热负荷」字段选了不存在的列' : null,
  };
}

async function flush() {
  for (let i = 0; i < 6; i += 1) {
    await act(async () => { await Promise.resolve(); });
  }
}

beforeEach(() => {
  list.mockReset();
});

describe('ReportDefinitionListPage —— 「被退回」标记', () => {
  it('① + ③ 有「被退回」标记的行 ⇒ ⇒ 显示 badge；没有的 ⇒ ⇒ 不显示', async () => {
    list.mockResolvedValue({
      items: [def('d1', '被打回的草稿', true), def('d2', '正常草稿', false)],
      total: 2,
    });
    render(<MemoryRouter><ReportDefinitionListPage /></MemoryRouter>);
    await flush();

    const badges = screen.getAllByText('被退回');
    expect(badges.length).toBe(1);
  });

  it('② badge 的 Tooltip 里是**原因**（创建人要看得懂要改什么）', async () => {
    list.mockResolvedValue({
      items: [def('d1', '被打回的草稿', true)],
      total: 1,
    });
    render(<MemoryRouter><ReportDefinitionListPage /></MemoryRouter>);
    await flush();

    const badge = screen.getByText('被退回');
    await act(async () => { fireEvent.mouseEnter(badge); });
    // ⚠️ antd Tooltip 有 `mouseEnterDelay`（默认 0.1s）⇒ ⇒ ⇒ **真等一会儿**
    // ⇒ ⇒ ⇒ 只 flush 微任务是不够的 ⇒ ⇒ ⇒ 那是**假失败**。
    await act(async () => {
      await new Promise((resolve) => { setTimeout(resolve, 300); });
    });

    expect(document.body.textContent).toContain('「热负荷」字段选了不存在的列');
  });
});
