import { useEffect, useState } from 'react';
import { Card, List, Progress, Tag, Typography } from 'antd';
import { checklistApi } from '../api/sprint1';
import type { ChecklistCompleteness, ChecklistItem, ChecklistStatus } from '../types/checklist';

interface Props {
  projectId: string;
}

const STATUS_COLOR: Record<ChecklistStatus, string> = {
  NOT_STARTED: 'default',
  IN_PROGRESS: 'processing',
  VERIFIED: 'success',
  ASSUMED: 'warning',
  NOT_APPLICABLE: 'default',
};

const STATUS_LABEL: Record<ChecklistStatus, string> = {
  NOT_STARTED: '未开始',
  IN_PROGRESS: '进行中',
  VERIFIED: '已核验',
  ASSUMED: '已假设',
  NOT_APPLICABLE: '不适用',
};

export function ChecklistDashboard({ projectId }: Props) {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [comp, setComp] = useState<ChecklistCompleteness | null>(null);

  useEffect(() => {
    checklistApi.list(projectId).then(setItems);
    checklistApi.completeness(projectId).then(setComp);
  }, [projectId]);

  return (
    <Card title="项目输入清单" style={{ marginTop: 16 }}>
      {comp && (
        <div style={{ marginBottom: 16 }}>
          <Typography.Text>
            完整性 {comp.completeness_pct.toFixed(1)}%
            （已核验 {comp.required_verified} / 已假设 {comp.required_assumed} /
            阻塞 {comp.required_blocked} / 必填 {comp.required_total}）
          </Typography.Text>
          <Progress
            percent={comp.completeness_pct}
            size="small"
            status={comp.completeness_pct >= 100 ? 'success' : 'active'}
          />
        </div>
      )}
      <List
        size="small"
        dataSource={items}
        renderItem={(it) => (
          <List.Item>
            <Typography.Text style={{ flex: 1 }}>{it.item_label}</Typography.Text>
            <Tag color={STATUS_COLOR[it.status]}>{STATUS_LABEL[it.status]}</Tag>
            {it.input_category && (
              <Tag>
                {it.input_category}
                {it.required ? '·必填' : ''}
              </Tag>
            )}
          </List.Item>
        )}
      />
    </Card>
  );
}