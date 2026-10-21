/**
 * TodoPanel —— 我的待办（P9B-1 · SPEC §6.22 · ADR-0049 §②）。
 *
 * 依据 P9A-NOT-002：待办**不落库**，每次查询由「签署矩阵的当前步骤 × 当前用户
 * 角色」**实时计算** ⇒ 真值永远是当前矩阵，不是某张快照。
 *
 * ## 两条纪律
 *
 * 1. ⚠️ **`total` 与 `items.length` 可能不等**（分页 / 上限）⇒ 计数用 `total`。
 * 2. ⚠️ **待办为空 ≠ 没有待办** —— 也可能是「当前用户在该项目内**无签署职责**」
 *    ⇒ 空态文案**不得**断言「你没有待办」以外的任何事实。
 *    ⇒ 越权过滤在服务端完成，前端**不得**自行按项目过滤
 *    （那会把「无权限」显示成「无待办」）。
 */
import { Button, Empty, Space, Table, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import type { TodoItem } from '../../api/todos';

interface Props {
  items: TodoItem[];
  /** 紧凑模式（抽屉用）—— 只渲染标题 + 职责。 */
  compact?: boolean;
  onOpen?: (todo: TodoItem) => void;
}

export function TodoPanel({ items, compact = false, onOpen }: Props): JSX.Element {
  if (items.length === 0) {
    return (
      <Empty
        data-testid="todo-panel-empty"
        // ⚠️ 措辞**只陈述事实**：可能是「无签署职责」，不是「没有待办」
        description="当前没有需要你签署的步骤"
      />
    );
  }

  if (compact) {
    return (
      <Space direction="vertical" size={2} style={{ width: '100%' }}>
        {items.map((t) => (
          <div key={`${t.deliverable_id}-${t.version_id}-${t.step_order}`} data-testid="todo-item">
            <Space>
              <Typography.Text strong>{t.title}</Typography.Text>
              <Typography.Text type="secondary" data-testid="todo-step-role">
                {t.step_role}
              </Typography.Text>
              <Button
                type="link"
                size="small"
                data-testid={`todo-open-${t.deliverable_id}`}
                onClick={() => onOpen?.(t)}
              >
                去签署
              </Button>
            </Space>
          </div>
        ))}
      </Space>
    );
  }

  const columns: ColumnsType<TodoItem> = [
    { title: '交付物', dataIndex: 'deliverable_id', key: 'deliverable_id' },
    { title: '版本', dataIndex: 'version_id', key: 'version_id' },
    {
      title: '步骤',
      dataIndex: 'step_order',
      key: 'step_order',
      render: (v: number) => `第 ${v} 步`,
    },
    { title: '签署职责', dataIndex: 'step_role', key: 'step_role' },
    {
      title: '标题',
      dataIndex: 'title',
      key: 'title',
      // ⚠️ 带 testid（NotificationCenter 的既有用例依赖它）
      render: (v: string) => (
        <Typography.Text strong data-testid="todo-title">
          {v}
        </Typography.Text>
      ),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, t: TodoItem) => (
        <Button
          type="link"
          size="small"
          data-testid={`todo-open-${t.deliverable_id}`}
          onClick={() => onOpen?.(t)}
        >
          去签署
        </Button>
      ),
    },
  ];

  return (
    <Table<TodoItem>
      data-testid="todo-panel"
      size="small"
      rowKey={(t) => `${t.deliverable_id}-${t.version_id}-${t.step_order}`}
      columns={columns}
      dataSource={items}
      pagination={false}
    />
  );
}

export default TodoPanel;
