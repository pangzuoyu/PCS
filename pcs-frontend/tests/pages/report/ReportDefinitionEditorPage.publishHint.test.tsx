/**
 * 「保存并发布」对**创建人自己**是死按钮（2026-11-19 人裁决 · TODO-191）。
 *
 * ## 为什么
 *
 * 后端 `publish()` 对「`created_by == actor`」返 **403**
 * （`REPORT_DEFINITION_SELF_REVIEW_FORBIDDEN`）⇒ ⇒ **创建人点「保存并发布」
 * 必然失败** ⇒ ⇒ ⇒ 此前前端只在 `setError()` 里显示 ⇒ ⇒ 用户要**点一次**
 * 才知道「发布须由他人审核」。
 *
 * ⇒ ⇒ 现在：**创建人** ⇒ ⇒ 「保存并发布」**置灰** + Tooltip + 页面顶部
 * 一条说明 ⇒ ⇒ **一开始就知道**。
 *
 * ## ⚠️ 为什么「置灰」不等于「少了一个功能」
 *
 * 全仓**只有这一个**发布入口 ⇒ ⇒ 且只有创建人能打开编辑器
 * （`update()` 对非创建人返 404）⇒ ⇒ ⇒ 这个按钮**从来就 100% 失败**
 * ⇒ ⇒ 置灰是**如实反映**，不是砍功能。
 *
 * ## 正对照
 *
 * 「非创建人 ⇒ 按钮可用」那条 ⇒ ⇒ 保证「置灰」是**判据驱动的**，
 * 不是「恒灰」。
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
import { useAuth } from '../../../src/store/auth';

const ME = '00000000-0000-0000-0000-00000000aaaa';
const OTHER = '00000000-0000-0000-0000-00000000bbbb';

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

/** 「保存并发布」按钮（按文案找）。 */
function publishButton(): HTMLButtonElement {
  const btn = [...document.querySelectorAll('button')]
    .find((b) => b.textContent?.includes('保存并发布'));
  if (!btn) throw new Error('找不到「保存并发布」按钮');
  return btn as HTMLButtonElement;
}

beforeEach(() => {
  datasources.mockReset();
  get.mockReset();
  datasources.mockResolvedValue({
    datasources: [{
      key: 'EQUIP_LIST', label: '设备清单', model: 'EquipmentList',
      fields: [{ name: 'tag_number', type: 'string', label: '位号',
                 is_jsonb_key: false, level: null }],
    }],
    joins: [],
  });
  useAuth.getState().clearSession();
  useAuth.getState().setSession({
    access_token: 't', refresh_token: 'r', username: 'u1',
    role: 'DESIGNER', user_id: ME,
  });
});

describe('ReportDefinitionEditorPage —— 「保存并发布」对创建人是死按钮', () => {
  it('定义是**我**创建的 ⇒ ⇒ 按钮置灰 + 页面写明「发布须由他人审核」', async () => {
    get.mockResolvedValue(definition(ME));
    renderEditor();
    await flush();
    expect(publishButton().disabled).toBe(true);
    expect(document.body.textContent).toContain('你是这份定义的创建人');
    expect(document.body.textContent).toContain('发布须由他人审核');
  });

  it('⚠️ **非创建人** ⇒ ⇒ 按钮**可用**（置灰必须是判据驱动的，不是恒灰）', async () => {
    get.mockResolvedValue(definition(OTHER));
    renderEditor();
    await flush();
    expect(publishButton().disabled).toBe(false);
    expect(document.body.textContent).not.toContain('你是这份定义的创建人');
  });

  it('**新建**态 ⇒ ⇒ 我就是（未来的）创建人 ⇒ ⇒ 按钮置灰', async () => {
    render(
      <MemoryRouter initialEntries={['/report/definitions/new/edit']}>
        <Routes>
          <Route path="/report/definitions/:defId/edit"
                 element={<ReportDefinitionEditorPage />} />
        </Routes>
      </MemoryRouter>,
    );
    await flush();
    expect(publishButton().disabled).toBe(true);
  });
});

function definition(createdBy: string) {
  return {
    def_id: 'd1',
    project_id: null,
    name: '设备一览',
    category: '设备类',
    description: '按位号列设备',
    definition_json: {
      DataSources: [{ source: 'EQUIP_LIST' }],
      SelectedFields: [
        { source: 'EQUIP_LIST', field: 'tag_number', alias: '位号',
          order: 0, visible: true },
      ],
      FilterConditions: [],
    },
    output_format: 'xlsx',
    max_rows: 10000,
    version: '1.0.0',
    status: 'DRAFT',
    shared_with: 'ALL_USERS',
    created_by: createdBy,
    created_at: null,
    updated_at: null,
  };
}
