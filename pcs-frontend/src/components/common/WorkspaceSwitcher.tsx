/**
 * WorkspaceSwitcher — 工作区切换器（P45-1-6 / Task 11，升级版）。
 *
 * SPEC §6.9 + plan P45-1-6：
 * - 沿用现有 props: ownerId, onSelect(ws)
 * - 新增 onTypeChange(type) callback（联动 hook）：
 *   - 选择 PERSONAL/TEMPORARY 时上层触发 TopBar 橙色横幅 + 菜单隐藏 +
 *     操作区仅保留保存
 * - 三类视觉差异化：
 *   - FORMAL    ：● 蓝（var(--color-primary)）
 *   - PERSONAL  ：○ 紫（var(--state-change-pending)）
 *   - TEMPORARY ：○ 橙（var(--state-stale)）
 * - workspaceStore.type 全局联动：留 P5（zustand store 全局架构）
 *
 * 触发顺序（避免循环）：onSelect(ws) → onTypeChange(ws.workspace_type)
 */
import { useEffect, useState } from 'react';
import { Select, Space, Tag, Typography } from 'antd';

import { workspaceApi } from '../../api/sprint1';
import type { Workspace, WorkspaceType } from '../../types/workspace';

interface Props {
  ownerId: string;
  onSelect: (ws: Workspace) => void;
  /** 可选：选择后同步 workspace.type 给上层（TopBar 横幅 / 菜单控制） */
  onTypeChange?: (type: WorkspaceType) => void;
}

const TYPE_LABEL: Record<WorkspaceType, string> = {
  FORMAL: '正式',
  PERSONAL: '个人',
  TEMPORARY: '临时',
};

const TYPE_GLYPH: Record<WorkspaceType, string> = {
  FORMAL: '●',
  PERSONAL: '○',
  TEMPORARY: '○',
};

const TYPE_COLOR: Record<WorkspaceType, string> = {
  FORMAL: 'var(--color-primary, #2F81F7)',
  PERSONAL: 'var(--state-change-pending, #A371F7)',
  TEMPORARY: 'var(--state-stale, #D29922)',
};

export function WorkspaceSwitcher({ ownerId, onSelect, onTypeChange }: Props): JSX.Element {
  const [list, setList] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    workspaceApi
      .list(ownerId)
      .then(setList)
      .finally(() => setLoading(false));
  }, [ownerId]);

  function handleChange(_value: unknown, option: unknown): void {
    const ws = (option as { data: Workspace }).data;
    onSelect(ws);
    onTypeChange?.(ws.workspace_type);
  }

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Typography.Text strong>工作区切换</Typography.Text>
      <Select<Workspace>
        data-testid="workspace-switcher"
        style={{ width: '100%' }}
        placeholder="选择工作区"
        loading={loading}
        options={list.map((ws) => ({
          value: ws.workspace_id,
          label: (
            <span data-testid="workspace-option" data-type={ws.workspace_type}>
              <span
                aria-hidden="true"
                style={{ color: TYPE_COLOR[ws.workspace_type], marginRight: 4 }}
              >
                {TYPE_GLYPH[ws.workspace_type]}
              </span>
              {TYPE_LABEL[ws.workspace_type]} · {ws.name}
              <Tag
                data-testid="workspace-type-tag"
                style={{ marginLeft: 8 }}
                color={ws.workspace_type === 'FORMAL' ? 'blue' : 'orange'}
              >
                {ws.workspace_type}
              </Tag>
            </span>
          ),
          data: ws,
        }))}
        onChange={handleChange}
      />
    </Space>
  );
}

export default WorkspaceSwitcher;