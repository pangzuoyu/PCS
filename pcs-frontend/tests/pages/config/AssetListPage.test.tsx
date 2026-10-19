/**
 * AssetListPage 测试（P45-2-3 / Task 21）。
 *
 * 覆盖 SPEC §7.10.1 资产列表：
 * - 6 类分组的 Tabs（CATEGORY_1~6：FORMULA/COEFFICIENT/TEMPLATE/
 *   STANDARD_DB/PROJECT_TEMPLATE/EQUIPMENT_LIB）
 * - 表格列：名称 / 当前版本 / 状态 / 操作
 *   （⚠️ 「更新人 / 更新时间」两列已删 —— `config_assets` 表**没有**这两列，
 *    恒为空；2026-10-19 随 `ConfigAsset` 并进契约一起去掉，bug-188/190 同族）
 * - 状态：契约的 5 态（草稿/待审批/已批准/已发布/已作废）
 * - 类别：CATEGORY_1~6（此前前端用 FORMULA/COEFFICIENT/… 六个自造值，
 *   而 DB 的 CheckConstraint 只允许 CATEGORY_N ⇒ 过滤 tab 生产上一档都不命中）
 * - 操作按钮：查看/编辑/审批/版本
 * - 行点击 → 详情 Drawer
 * - 详情展示元数据 + hash + tags
 * - 编辑按钮：仅 DRAFT 启用
 * - 审批按钮：仅 IN_APPROVAL 启用
 * - 版本按钮：始终启用
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { AssetListPage } from '../../../src/pages/config/AssetListPage';
import type { ConfigAsset } from '../../../src/types/configAsset';

const assets: ConfigAsset[] = [
  {
    asset_id: 'a-1',
    name: '蒸汽压力公式',
    category: 'CATEGORY_2',
    current_version: 'v3.1',
    status: 'DRAFT',
  },
  {
    asset_id: 'a-2',
    name: '换热器U值表',
    category: 'CATEGORY_3',
    current_version: 'v1.2',
    status: 'PENDING',
  },
  {
    asset_id: 'a-3',
    name: 'PID模板',
    category: 'CATEGORY_4',
    current_version: 'v2.0',
    status: 'PUBLISHED',
  },
  {
    asset_id: 'a-4',
    name: 'ASTM 标准库',
    category: 'CATEGORY_1',
    current_version: 'v5.0',
    status: 'OBSOLETE',
  },
  {   // ⚠️ APPROVED 是**后端真产、前端此前完全没有**的一态（bug-188）：
      // 词表是手写 4 态时，它落进 `CONFIG_STATUS_LABEL[s]` 的 undefined ⇒ 空标签。
      asset_id: 'a-5',
      name: '焓值对照表',
      category: 'CATEGORY_1',
      current_version: 'v0.9',
      status: 'APPROVED',
  },
];

describe('AssetListPage — 渲染 (P45-2-3)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('渲染页面标题 + 6 个类别 tab', () => {
    render(<AssetListPage assets={assets} />);
    expect(screen.getByText('CONFIG 资产')).toBeTruthy();
    const tabs = screen.getByTestId('config-asset-tabs');
    // 标签取自 CATEGORY_N 的真实业务含义（依据见 types/configAsset.ts 的映射表）
    for (const label of ['项目模板', '公式', '系数表', '模板文件', '管道等级/符号', '复用设备库']) {
      expect(tabs.textContent, `缺「${label}」`).toContain(label);
    }
  });

  it('默认显示「全部」+ 渲染所有资产', () => {
    render(<AssetListPage assets={assets} />);
    expect(document.querySelectorAll('[data-testid="asset-row"]').length).toBe(assets.length);
  });

  it('点击 FORMULA tab → 仅显示公式类', () => {
    render(<AssetListPage assets={assets} />);
    const tabs = screen.getByTestId('config-asset-tabs');
    const formulaTab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.includes('公式'),
    );
    fireEvent.click(formulaTab!);
    expect(document.querySelectorAll('[data-testid="asset-row"]').length).toBe(1);
    expect(document.querySelector('[data-testid="asset-row"]')?.textContent).toContain('蒸汽压力公式');
  });

  it('点击 COEFFICIENT tab → 仅显示系数类', () => {
    render(<AssetListPage assets={assets} />);
    const tabs = screen.getByTestId('config-asset-tabs');
    const tab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.includes('系数表'),
    );
    fireEvent.click(tab!);
    expect(document.querySelectorAll('[data-testid="asset-row"]').length).toBe(1);
    expect(document.querySelector('[data-testid="asset-row"]')?.textContent).toContain('换热器U值表');
  });
});

describe('AssetListPage — 表格列', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('每行展示：名称 / 版本 / 状态 / 操作', () => {
    render(<AssetListPage assets={assets} />);
    const row = document.querySelector('[data-testid="asset-row"]')!;
    expect(row.textContent).toContain('蒸汽压力公式');
    expect(row.textContent).toContain('v3.1');
    expect(row.textContent).toContain('草稿');
    expect(row.textContent).toContain('查看');
    expect(row.textContent).toContain('编辑');
    expect(row.textContent).toContain('审批');
    expect(row.textContent).toContain('版本');
    // ⚠️ 反向断言：这两列曾存在但数据源字段（updated_by / updated_at）
    // 在 config_assets 表上**根本不存在**，所以恒为空 —— 留着列只是
    // 让人以为「这行没有更新人」。真值只有 created_by/created_at/updated_at，
    // 而列表响应不带它们（见 AssetResponse）。要显示得先扩后端响应。
    expect(row.textContent).not.toContain('张三');
  });

  // ⚠️ 此前钉的是「4 态」并含前端编造的 `审批中`(IN_APPROVAL)。
  // 真值是契约的 ConfigStatus **5 态**（草稿/待审批/已批准/已发布/已作废），
  // 且 `APPROVED` 此前**完全没有 fixture** ⇒ 它落进 undefined ⇒ 空标签。
  it('状态 5 态逐个有中文标签 —— 少一态就空标签', () => {
    render(<AssetListPage assets={assets} />);
    const allText = document.body.textContent ?? '';
    for (const label of ['草稿', '待审批', '已批准', '已发布', '已作废']) {
      expect(allText, `缺「${label}」—— 该状态落进了未知兜底`).toContain(label);
    }
    expect(allText).not.toContain('审批中'); // 旧的编造值不再出现
  });
});

describe('AssetListPage — 操作按钮', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('DRAFT 行：编辑启用 / 审批禁用 / 版本启用 / 查看启用', () => {
    render(<AssetListPage assets={assets} />);
    // a-1 是 FORMULA DRAFT，需要先切到 FORMULA tab
    const tabs = screen.getByTestId('config-asset-tabs');
    const formulaTab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.includes('公式'),
    );
    fireEvent.click(formulaTab!);
    const draftRow = document.querySelector('[data-testid="asset-row"]')!;
    const editBtn = draftRow.querySelector('[data-testid="asset-action-edit"]');
    const approveBtn = draftRow.querySelector('[data-testid="asset-action-approve"]');
    const versionBtn = draftRow.querySelector('[data-testid="asset-action-version"]');
    expect(editBtn).toBeTruthy();
    expect(approveBtn).toBeTruthy();
    expect((editBtn as HTMLButtonElement).disabled).toBe(false);
    expect((approveBtn as HTMLButtonElement).disabled).toBe(true);
    expect(versionBtn).toBeTruthy();
  });

  it('IN_APPROVAL 行：审批启用 / 编辑禁用', () => {
    render(<AssetListPage assets={assets} />);
    const tabs = screen.getByTestId('config-asset-tabs');
    const tab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.includes('系数表'),
    );
    fireEvent.click(tab!);
    const row = document.querySelector('[data-testid="asset-row"]')!;
    const editBtn = row.querySelector('[data-testid="asset-action-edit"]') as HTMLButtonElement;
    const approveBtn = row.querySelector('[data-testid="asset-action-approve"]') as HTMLButtonElement;
    expect(editBtn.disabled).toBe(true);
    expect(approveBtn.disabled).toBe(false);
  });

  it('PUBLISHED 行：编辑/审批都禁用', () => {
    render(<AssetListPage assets={assets} />);
    const tabs = screen.getByTestId('config-asset-tabs');
    const tab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.includes('模板文件'),
    );
    fireEvent.click(tab!);
    const row = document.querySelector('[data-testid="asset-row"]')!;
    const editBtn = row.querySelector('[data-testid="asset-action-edit"]') as HTMLButtonElement;
    const approveBtn = row.querySelector('[data-testid="asset-action-approve"]') as HTMLButtonElement;
    expect(editBtn.disabled).toBe(true);
    expect(approveBtn.disabled).toBe(true);
  });

  it('点击「版本」按钮 → onVersion 回调收到 asset', () => {
    const onVersion = vi.fn();
    render(<AssetListPage assets={assets} onVersion={onVersion} />);
    const btn = document.querySelector('[data-testid="asset-action-version"]')!;
    fireEvent.click(btn);
    expect(onVersion).toHaveBeenCalledTimes(1);
    expect(onVersion.mock.calls[0][0].asset_id).toBe('a-1');
  });

  it('点击「编辑」按钮 → onEdit 回调收到 asset', () => {
    const onEdit = vi.fn();
    render(<AssetListPage assets={assets} onEdit={onEdit} />);
    const btn = document.querySelector('[data-testid="asset-action-edit"]')!;
    fireEvent.click(btn);
    expect(onEdit).toHaveBeenCalledTimes(1);
    expect(onEdit.mock.calls[0][0].asset_id).toBe('a-1');
  });

  it('点击「审批」按钮 → onApprove 回调收到 asset', () => {
    const onApprove = vi.fn();
    render(<AssetListPage assets={assets} onApprove={onApprove} />);
    // 切到 IN_APPROVAL 那条
    const tabs = screen.getByTestId('config-asset-tabs');
    const tab = Array.from(tabs.querySelectorAll('.ant-tabs-tab')).find(
      (el) => el.textContent?.includes('系数表'),
    );
    fireEvent.click(tab!);
    const btn = document.querySelector('[data-testid="asset-action-approve"]')!;
    fireEvent.click(btn);
    expect(onApprove).toHaveBeenCalledTimes(1);
    expect(onApprove.mock.calls[0][0].asset_id).toBe('a-2');
  });
});

describe('AssetListPage — 详情 Drawer', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('行点击 → 打开详情 Drawer', () => {
    render(<AssetListPage assets={assets} />);
    const row = document.querySelector('[data-testid="asset-row"]')!;
    fireEvent.click(row);
    // antd Drawer 通过 portal；用 document 查询
    expect(document.querySelector('.ant-drawer-open')).toBeTruthy();
    expect(document.body.textContent).toContain('蒸汽压力公式');
  });

  /**
   * ⚠️ 此前这条断言的是「详情 = 名称/类别/版本/状态/更新人/时间/hash/tags」，
   * 而其中 **hash / tags / updated_by 三个字段在 `config_assets` 表上
   * 根本不存在** —— 断言全绿，生产上那三块恒不显示。
   * 现在只断言契约里真实存在的字段，并反向断言旧字段不再出现。
   */
  it('详情 Drawer 显示契约里真实存在的字段', () => {
    render(<AssetListPage assets={assets} />);
    const row = document.querySelector('[data-testid="asset-row"]')!;
    fireEvent.click(row);
    const drawer = document.querySelector('.ant-drawer')!;
    expect(drawer.textContent).toContain('蒸汽压力公式');
    expect(drawer.textContent).toContain('CATEGORY_2');   // 原始枚举值
    expect(drawer.textContent).toContain('公式');          // 业务标签
    expect(drawer.textContent).toContain('v3.1');
    expect(drawer.textContent).toContain('草稿');
    expect(drawer.textContent).not.toContain('FORMULA');   // 旧的自造值
    expect(drawer.textContent).not.toContain('a3f9…d7a8'); // hash 字段不存在
  });

  it('详情 Drawer 关闭按钮 → 关闭', () => {
    render(<AssetListPage assets={assets} />);
    fireEvent.click(document.querySelector('[data-testid="asset-row"]')!);
    const closeBtn = document.querySelector('.ant-drawer-close')!;
    expect(closeBtn).toBeTruthy();
    fireEvent.click(closeBtn);
    // 关闭后 drawer-open 类应消失（动画完成需时，仅断言 closeBtn 可点击）
  });

  it('不传 assets → 显示空状态', () => {
    render(<AssetListPage assets={[]} />);
    expect(screen.getByTestId('asset-empty')).toBeTruthy();
  });
});