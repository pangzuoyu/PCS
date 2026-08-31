import { Card, Statistic, Typography } from 'antd';

export default function DashboardPage() {
  return (
    <div>
      <Typography.Title level={3}>仪表盘</Typography.Title>
      <div style={{ display: 'flex', gap: 16 }}>
        <Card>
          <Statistic title="项目" value={0} />
        </Card>
        <Card>
          <Statistic title="记录" value={0} />
        </Card>
        <Card>
          <Statistic title="交付物" value={0} />
        </Card>
      </div>
      <Typography.Paragraph type="secondary" style={{ marginTop: 24 }}>
        P0 骨架占位：仪表盘、计算模块、交付物模块、变更管理将在后续 P1–P10 阶段填充。
      </Typography.Paragraph>
    </div>
  );
}
