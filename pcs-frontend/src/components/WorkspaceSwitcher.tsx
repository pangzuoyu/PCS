import { useEffect, useState } from 'react';
import { Select, Space, Typography } from 'antd';
import { workspaceApi } from '../api/sprint1';
import type { Workspace, WorkspaceType } from '../types/workspace';

interface Props {
  ownerId: string;
  onSelect: (ws: Workspace) => void;
}

const TYPE_LABEL: Record<WorkspaceType, string> = {
  FORMAL: '正式',
  PERSONAL: '个人',
  TEMPORARY: '临时',
};

export function WorkspaceSwitcher({ ownerId, onSelect }: Props) {
  const [list, setList] = useState<Workspace[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    setLoading(true);
    workspaceApi
      .list(ownerId)
      .then(setList)
      .finally(() => setLoading(false));
  }, [ownerId]);

  return (
    <Space direction="vertical" style={{ width: '100%' }}>
      <Typography.Text strong>工作区切换</Typography.Text>
      <Select<Workspace>
        style={{ width: '100%' }}
        placeholder="选择工作区"
        loading={loading}
        options={list.map((ws) => ({
          value: ws.workspace_id,
          label: `${TYPE_LABEL[ws.workspace_type]} · ${ws.name}`,
          data: ws,
        }))}
        onChange={(_value, option) => {
          const ws = (option as { data: Workspace }).data;
          onSelect(ws);
        }}
      />
    </Space>
  );
}