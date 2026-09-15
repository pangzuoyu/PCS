import { useState } from 'react';
import { Card, Col, Row, Typography } from 'antd';
import { InputChecklistPanel } from '../components/common/InputChecklistPanel';
import { WorkspaceSwitcher } from '../components/common/WorkspaceSwitcher';
import { useAuth } from '../store/auth';
import type { Workspace } from '../types/workspace';

function workspaceProjectId(ws: Workspace): string {
  return ws.project_id ?? '00000000-0000-0000-0000-000000000001';
}

export default function DashboardPage() {
  const userId = useAuth((s) => s.userId);
  const [selected, setSelected] = useState<Workspace | null>(null);

  if (!userId) {
    return <Typography.Text>请先登录</Typography.Text>;
  }

  const projectId = selected ? workspaceProjectId(selected) : '00000000-0000-0000-0000-000000000001';

  return (
    <div>
      <Typography.Title level={3}>仪表盘</Typography.Title>
      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <WorkspaceSwitcher ownerId={userId} onSelect={setSelected} />
          </Card>
        </Col>
        <Col span={16}>
          <Card title={selected ? `项目 ${projectId.slice(0, 8)}…` : '选择工作区后查看清单'}>
            <InputChecklistPanel projectId={projectId} />
          </Card>
        </Col>
      </Row>
    </div>
  );
}