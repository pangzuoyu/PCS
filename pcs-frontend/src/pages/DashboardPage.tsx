import { useState } from 'react';
import { Card, Col, Row, Typography } from 'antd';
import { InputChecklistPanel } from '../components/common/InputChecklistPanel';
import { WorkspaceSwitcher } from '../components/common/WorkspaceSwitcher';
import { useAuth } from '../store/auth';
import type { Workspace } from '../types/workspace';

export default function DashboardPage() {
  const userId = useAuth((s) => s.userId);
  const [selected, setSelected] = useState<Workspace | null>(null);

  if (!userId) {
    return <Typography.Text>请先登录</Typography.Text>;
  }

  // ⚠️ **守卫条件是「拿到了真 project_id」**（P10-F · 评审 #24）——
  // ⇒ 原先是「选了工作区」⇒ ⇒ 而**个人 / 临时工作区按设计就没有项目**
  // （`project_id` 恒为 `null`）⇒ ⇒ 原实现拿**占位 id** 兜底 ⇒ ⇒
  // **把占位 id 当真项目用** ⇒ ⇒ 两条 404 + 控制台 error。
  // ⇒ ⇒ 这里**不用占位兜底** ⇒ ⇒ 没有真项目 ⇒ **不渲染面板**。
  const effectiveProjectId = selected?.project_id ?? null;

  const title = selected
    ? effectiveProjectId
      ? `项目 ${effectiveProjectId.slice(0, 8)}…`
      : '该工作区未关联项目'
    : '选择工作区后查看清单';

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
          <Card title={title}>
            {/* ⚠️ **没选工作区就不渲染面板**（P10-B · T7 · bug-2168）：
                面板挂载即取数（list + completeness）⇒ 而此时 `projectId` 是
                **占位 id** `00000000-0000-0000-0000-000000000001`（不存在）
                ⇒ ⇒ 每次开仪表盘都 **2 个 404** ⇒ 控制台两条 error
                ⇒ ⇒ 真后端通道的「控制台无 error」断言直接红。
                ⇒ 卡片标题本来就写着「选择工作区后查看清单」⇒ 未选时**没有内容**
                本来就符合文案 ⇒ 只差把面板一起藏起来。

                ⚠️ **「无项目的工作区」也不渲染**（P10-F · 评审 #24）——
                ⇒ 理由同上（占位 id 兜底）⇒ ⇒ 面板的 `projectId` 必须是
                **真项目 id**，否则**一次请求都不该发**。 */}
            {effectiveProjectId ? (
              <InputChecklistPanel projectId={effectiveProjectId} />
            ) : null}
          </Card>
        </Col>
      </Row>
    </div>
  );
}