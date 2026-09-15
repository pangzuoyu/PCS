/**
 * WorkspaceSwitcher 升级版测试（P45-1-6 / Task 11）。
 *
 * 覆盖（SPEC §6.9 + plan P45-1-6）：
 * - 三类视觉差异化（FORMAL/PERSONAL/TEMPORARY）：label / glyph / color / tag
 * - 选择后 onSelect(ws) + onTypeChange(type) 联动触发
 * - ownerId 拉取（mock workspaceApi.list）
 *
 * antd Select popup 通过 portal 渲染到 document.body；用 fireEvent.mouseDown
 * 触发下拉，再 click option。
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';

vi.mock('../../../src/api/sprint1', () => ({
  workspaceApi: {
    list: vi.fn().mockResolvedValue([
      { workspace_id: 'ws-formal', workspace_type: 'FORMAL', name: '炼油项目 A' },
      { workspace_id: 'ws-personal', workspace_type: 'PERSONAL', name: '张三' },
      { workspace_id: 'ws-temp', workspace_type: 'TEMPORARY', name: '2026-09-15' },
    ]),
  },
}));

import { WorkspaceSwitcher } from '../../../src/components/common/WorkspaceSwitcher';

async function openDropdown(): Promise<void> {
  const select = document.querySelector('.ant-select-selector');
  if (select) {
    fireEvent.mouseDown(select);
  }
  // 等待 popup 出现
  await waitFor(() => {
    expect(document.querySelector('.ant-select-dropdown')).toBeTruthy();
  });
}

describe('WorkspaceSwitcher — ownerId 拉取 (P45-1-6)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('ownerId 传入触发 workspaceApi.list', async () => {
    const { workspaceApi } = await import('../../../src/api/sprint1');
    render(<WorkspaceSwitcher ownerId="u1" onSelect={() => {}} />);
    await new Promise((r) => setTimeout(r, 20));
    expect(workspaceApi.list).toHaveBeenCalledWith('u1');
  });
});

describe('WorkspaceSwitcher — 三类视觉', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('FORMAL：● 蓝色 var(--color-primary) + Tag blue', async () => {
    render(<WorkspaceSwitcher ownerId="u1" onSelect={() => {}} />);
    await openDropdown();
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    const formalOption = within(dropdown).getByText(/炼油项目 A/).closest('.ant-select-item');
    expect(formalOption).toBeTruthy();
    const glyphSpan = formalOption!.querySelector('span[aria-hidden="true"]');
    const glyphStyle = glyphSpan?.getAttribute('style') || '';
    expect(glyphStyle).toContain('var(--color-primary');
  });

  it('PERSONAL：○ 紫色 var(--state-change-pending)', async () => {
    render(<WorkspaceSwitcher ownerId="u1" onSelect={() => {}} />);
    await openDropdown();
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    const personalOption = within(dropdown).getByText(/张三/).closest('.ant-select-item');
    expect(personalOption).toBeTruthy();
    const glyphSpan = personalOption!.querySelector('span[aria-hidden="true"]');
    expect(glyphSpan?.getAttribute('style') || '').toContain('var(--state-change-pending');
  });

  it('TEMPORARY：○ 橙色 var(--state-stale)', async () => {
    render(<WorkspaceSwitcher ownerId="u1" onSelect={() => {}} />);
    await openDropdown();
    const dropdown = document.querySelector('.ant-select-dropdown') as HTMLElement;
    const tempOption = within(dropdown).getByText(/2026-09-15/).closest('.ant-select-item');
    expect(tempOption).toBeTruthy();
    const glyphSpan = tempOption!.querySelector('span[aria-hidden="true"]');
    expect(glyphSpan?.getAttribute('style') || '').toContain('var(--state-stale');
  });

  it('每 option 含 type tag', async () => {
    render(<WorkspaceSwitcher ownerId="u1" onSelect={() => {}} />);
    await openDropdown();
    const tags = document.querySelectorAll('.ant-select-dropdown .ant-tag');
    expect(tags.length).toBe(3);
    expect(tags[0].textContent).toBe('FORMAL');
    expect(tags[1].textContent).toBe('PERSONAL');
    expect(tags[2].textContent).toBe('TEMPORARY');
  });
});

describe('WorkspaceSwitcher — 联动回调', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('选择 FORMAL → onSelect(ws) + onTypeChange("FORMAL")', async () => {
    const onSelect = vi.fn();
    const onTypeChange = vi.fn();
    render(
      <WorkspaceSwitcher ownerId="u1" onSelect={onSelect} onTypeChange={onTypeChange} />,
    );
    await openDropdown();
    const formalItem = screen.getByText(/炼油项目 A/).closest('.ant-select-item');
    expect(formalItem).toBeTruthy();
    fireEvent.click(formalItem!);
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ workspace_type: 'FORMAL' }));
    expect(onTypeChange).toHaveBeenCalledWith('FORMAL');
  });

  it('选择 PERSONAL → onTypeChange("PERSONAL")', async () => {
    const onSelect = vi.fn();
    const onTypeChange = vi.fn();
    render(
      <WorkspaceSwitcher ownerId="u1" onSelect={onSelect} onTypeChange={onTypeChange} />,
    );
    await openDropdown();
    const item = screen.getByText(/张三/).closest('.ant-select-item');
    fireEvent.click(item!);
    expect(onTypeChange).toHaveBeenCalledWith('PERSONAL');
  });

  it('onTypeChange 可选：不传不报错', async () => {
    const onSelect = vi.fn();
    render(<WorkspaceSwitcher ownerId="u1" onSelect={onSelect} />);
    await openDropdown();
    const item = screen.getByText(/张三/).closest('.ant-select-item');
    fireEvent.click(item!);
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ workspace_type: 'PERSONAL' }));
  });
});