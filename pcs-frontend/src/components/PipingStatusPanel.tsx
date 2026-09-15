import { useEffect, useState } from 'react';
import { Card, List, Space } from 'antd';
import axios from 'axios';
import { StateBadge } from './common/StateBadge';
import type { RecordSignStatus } from '../types/records';

interface PipingRow {
  pipe_id: string;
  line_no: string;
  sign_status: RecordSignStatus;
}

export function PipingStatusPanel({ workspaceId }: { workspaceId?: string }) {
  const [rows, setRows] = useState<PipingRow[]>([]);

  useEffect(() => {
    if (!workspaceId) return;
    axios
      .get<PipingRow[]>('/api/v1/records/piping', { params: { workspace_id: workspaceId } })
      .then((r) => setRows(r.data))
      .catch(() => setRows([]));
  }, [workspaceId]);

  return (
    <Card title="管段状态" size="small">
      <List
        size="small"
        dataSource={rows}
        renderItem={(r) => (
          <List.Item>
            <Space>
              <span>{r.line_no}</span>
              <StateBadge status={r.sign_status} />
            </Space>
          </List.Item>
        )}
      />
    </Card>
  );
}