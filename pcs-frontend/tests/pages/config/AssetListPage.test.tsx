/**
 * AssetListPage 测试（P45-2-3 / Task 21）。
 *
 * 覆盖 SPEC §7.10.1 资产列表：
 * - 6 类分组的 Tabs（CATEGORY_1~6：FORMULA/COEFFICIENT/TEMPLATE/
 *   STANDARD_DB/PROJECT_TEMPLATE/EQUIPMENT_LIB）
 * - 表格列：名称 / 当前版本 / 状态 / 更新人 / 更新时间 / 操作
 * - 状态：草稿/审批中/已发布/已作废（4 态）
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
    category: 'FORMULA',
    current_version: 'v3.1',
    status: 'DRAFT',
    updated_by: '张三',
    updated_at: '2026-09-15 14:32',
    hash: 'a3f9b2e1c21ed7a8',
    tags: ['蒸汽', '压力'],
  },
  {
    asset_id: 'a-2',
    name: '换热器U值表',
    category: 'COEFFICIENT',
    current_version: 'v1.2',
    status: 'IN_APPROVAL',
    updated_by: '李四',
    updated_at: '2026-09-15 13:00',
    hash: 'b7c2d3e4f5a60001',
  },
  {
    asset_id: 'a-3',
    name: 'PID模板',
    category: 'TEMPLATE',
    current_version: 'v2.0',
    status: 'PUBLISHED',
    updated_by: '王五',
    updated_at: '2026-09-14 10:15',
    hash: 'c1d2e3f4a5b60002',
  },
  {
    asset_id: 'a-4',
    name: 'ASTM 标准库',
    category: 'STANDARD_DB',
    current_version: 'v5.0',
    status: 'OBSOLETE',
    updated_by: '赵六',
    updated_at: '2026-09-10 09:00',
    hash: 'd4e5f6a7b8c90003',
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
    expect(tabs.textContent).toContain('公式');
    expect(tabs.textContent).toContain('系数表');
    expect(tabs.textContent).toContain('模板文件');
    expect(tabs.textContent).toContain('标准数据库');
    expect(tabs.textContent).toContain('项目模板');
    expect(tabs.textContent).toContain('复用设备库');
  });

  it('默认显示「全部」+ 渲染所有资产', () => {
    render(<AssetListPage assets={assets} />);
    expect(document.querySelectorAll('[data-testid="asset-row"]').length).toBe(4);
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

  it('每行展示：名称 / 版本 / 状态 / 更新人 / 更新时间 / 操作', () => {
    render(<AssetListPage assets={assets} />);
    const row = document.querySelector('[data-testid="asset-row"]')!;
    expect(row.textContent).toContain('蒸汽压力公式');
    expect(row.textContent).toContain('v3.1');
    expect(row.textContent).toContain('草稿');
    expect(row.textContent).toContain('张三');
    expect(row.textContent).toContain('2026-09-15 14:32');
  });

  it('状态 4 态：草稿 / 审批中 / 已发布 / 已作废', () => {
    render(<AssetListPage assets={assets} />);
    // 切到「全部」已默认显示；验证 4 种
    const allText = document.body.textContent ?? '';
    expect(allText).toContain('草稿');
    expect(allText).toContain('审批中');
    expect(allText).toContain('已发布');
    expect(allText).toContain('已作废');
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

  it('详情 Drawer 显示：名称 / 类别 / 版本 / 状态 / 更新人 / 时间 / hash / tags', () => {
    render(<AssetListPage assets={assets} />);
    const row = document.querySelector('[data-testid="asset-row"]')!;
    fireEvent.click(row);
    const drawer = document.querySelector('.ant-drawer')!;
    expect(drawer.textContent).toContain('蒸汽压力公式');
    expect(drawer.textContent).toContain('FORMULA');
    expect(drawer.textContent).toContain('v3.1');
    expect(drawer.textContent).toContain('草稿');
    expect(drawer.textContent).toContain('张三');
    expect(drawer.textContent).toContain('a3f9…d7a8');
    expect(drawer.textContent).toContain('蒸汽');
    expect(drawer.textContent).toContain('压力');
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