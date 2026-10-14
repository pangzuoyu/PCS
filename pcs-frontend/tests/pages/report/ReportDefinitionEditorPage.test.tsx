/**
 * 定义编辑器必须**警告**将丢失的过滤条件（评审 #25，用户裁决）。
 *
 * ## 场景（TODO-060 的失败形态）
 *
 * 打开一个含有一条当前前端无法识别的条件（旧定义、手工改过的 payload），
 * 改一个无关字段，保存 —— 那条条件就没了，且无任何提示。
 * `definitionBody.ts` 自己声明「往返无损是硬要求」。
 *
 * 本测试走**真实加载路径**（mock 的是 API 而不是 toFilterTree），
 * 于是它同时钉住了三件事：load 里要计数、Alert 要渲染、计数要用
 * 真的 `countUnparsedFilterNodes`。任何一环掉了，这条都会红。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, act } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';

const datasources = vi.fn();
const get = vi.fn();

vi.mock('../../../src/api/reportBuilder', () => ({
  reportBuilderApi: {
    datasources: (...a: unknown[]) => datasources(...a),
    get: (...a: unknown[]) => get(...a),
    create: vi.fn(),
    update: vi.fn(),
    publish: vi.fn(),
  },
  errorMessage: () => 'x',
}));

import { ReportDefinitionEditorPage } from '../../../src/pages/report/ReportDefinitionEditorPage';

/** 一条合法叶子 + 一条缺 field 的叶子（后者是 toFilterTree 认不了的）。 */
const FILTERS = [
  { source: 'EQUIP_LIST', field: 'tag_number', operator: 'EQ', value: 'P-1' },
  { source: 'EQUIP_LIST', operator: 'EQ', value: 'no-field' },
];

function renderEditor() {
  return render(
    <MemoryRouter initialEntries={['/report/definitions/d1/edit']}>
      <Routes>
        <Route path="/report/definitions/:defId/edit"
               element={<ReportDefinitionEditorPage />} />
      </Routes>
    </MemoryRouter>,
  );
}

async function flush() {
  for (let i = 0; i < 6; i += 1) {
    await act(async () => { await Promise.resolve(); });
  }
}

beforeEach(() => {
  datasources.mockReset(); get.mockReset();
  datasources.mockResolvedValue({
    datasources: [{
      key: 'EQUIP_LIST', label: '设备清单', model: 'EquipmentList',
      fields: [{ name: 'tag_number', type: 'string', label: '位号',
                 is_jsonb_key: false, level: null }],
    }],
    joins: [],
  });
  get.mockResolvedValue(DEFINITION_PAYLOAD(FILTERS));
});

describe('ReportDefinitionEditorPage — 无法识别的过滤条件要警告', () => {
  it('定义里有本页读不了的条件 → 渲染警告 Alert，写明条数与「保存会丢弃」', async () => {
    renderEditor();
    await flush();
    expect(document.body.textContent).toContain('1 条本页无法识别');
    expect(document.body.textContent).toContain('丢弃');
  });

  it('全部条件都能读 → 不渲染警告（不能靠恒显糊弄）', async () => {
    const base = DEFINITION_PAYLOAD(FILTERS.slice(0, 1));   // 只有合法那条
    get.mockReset();
    get.mockResolvedValue(base);
    const { unmount } = renderEditor();
    await flush();
    expect(document.body.textContent).not.toContain('无法识别');
    unmount();
  });
});

function DEFINITION_PAYLOAD(filterConditions: unknown[]) {
  return {
    def_id: 'd1', name: '泵数据表', category: '设备类', description: '',
    output_format: 'pdf', max_rows: 10000, shared_with: 'ALL_USERS',
    project_id: null, status: 'PUBLISHED', version: '1.0.0',
    definition_json: {
      DataSources: [{ source: 'EQUIP_LIST' }],
      SelectedFields: [{ source: 'EQUIP_LIST', field: 'tag_number',
                         alias: '位号', order: 0, visible: true }],
      FilterConditions: filterConditions, SortBy: [], MaxRows: 10000,
      OutputFormat: 'pdf', detailLevel: 'BASIC',
    },
  };
}
