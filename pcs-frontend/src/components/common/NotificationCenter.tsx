/**
 * NotificationCenter — 通知中心（P45-1-13 / Task 18）。
 *
 * SPEC §6.20 + plan P45-1-13：
 * - 右侧 Drawer，宽 420px
 * - 分组 tabs：待办 / 变更 / 系统 / 全部
 * - 消息结构：[类型 tag] 标题 + 摘要 + 时间 + [查看] 按钮
 * - 未读左侧蓝点
 *
 * Props（SPEC 锁定）：
 *   open: boolean
 *   onClose: () => void
 *   notifications?: Notification[]
 *   onItemClick?: (notification_id: string) => void
 */
import { useMemo, useState } from 'react';
import { Badge, Button, Drawer, Empty, List, Space, Tabs, Tag, Typography } from 'antd';

export type NotificationCategory = 'todo' | 'change' | 'system';
export type NotificationKind = 'CHANGE' | 'TODO' | 'SYSTEM' | 'INFO';

export interface Notification {
  notification_id: string;
  category: NotificationCategory;
  kind: NotificationKind;
  title: string;
  summary?: string;
  issued_at: string;
  unread?: boolean;
}

interface Props {
  open: boolean;
  onClose: () => void;
  notifications?: Notification[];
  onItemClick?: (notification_id: string) => void;
}

const KIND_COLOR: Record<NotificationKind, string> = {
  CHANGE: 'orange',
  TODO: 'blue',
  SYSTEM: 'default',
  INFO: 'cyan',
};

const KIND_LABEL: Record<NotificationKind, string> = {
  CHANGE: '变更',
  TODO: '待办',
  SYSTEM: '系统',
  INFO: '信息',
};

const CATEGORY_LABEL: Record<NotificationCategory | 'all', string> = {
  todo: '待办',
  change: '变更',
  system: '系统',
  all: '全部',
};

export function NotificationCenter({
  open,
  onClose,
  notifications = [],
  onItemClick,
}: Props): JSX.Element {
  const [activeTab, setActiveTab] = useState<'all' | NotificationCategory>('all');

  const filtered = useMemo(() => {
    if (activeTab === 'all') return notifications;
    return notifications.filter((n) => n.category === activeTab);
  }, [notifications, activeTab]);

  const unreadCount = notifications.filter((n) => n.unread).length;

  return (
    <Drawer
      data-testid="notification-center"
      title="通知中心"
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
    >
      <Tabs
        data-testid="notification-tabs"
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as 'all' | NotificationCategory)}
        items={[
          {
            key: 'todo',
            label: CATEGORY_LABEL.todo,
          },
          {
            key: 'change',
            label: CATEGORY_LABEL.change,
          },
          {
            key: 'system',
            label: CATEGORY_LABEL.system,
          },
          {
            key: 'all',
            label: (
              <Badge count={unreadCount} offset={[6, -2]} size="small">
                {CATEGORY_LABEL.all}
              </Badge>
            ),
          },
        ]}
      />

      {filtered.length === 0 ? (
        <Empty description="暂无通知" data-testid="notification-empty" />
      ) : (
        <List
          data-testid="notification-list"
          size="small"
          dataSource={filtered}
          renderItem={(n) => (
            <List.Item
              data-testid="notification-item"
              data-notification-id={n.notification_id}
              data-unread={n.unread ? 'true' : 'false'}
              style={{ alignItems: 'flex-start' }}
            >
              <Space align="start" style={{ width: '100%' }}>
                {n.unread && (
                  <span
                    data-testid="notification-unread-dot"
                    aria-label="未读"
                    style={{
                      display: 'inline-block',
                      width: 8,
                      height: 8,
                      borderRadius: 'var(--radius-full, 50%)',
                      background: 'var(--color-primary, #2F81F7)',
                      marginTop: 6,
                    }}
                  />
                )}
                <Space direction="vertical" size={2} style={{ flex: 1 }}>
                  <Space>
                    <Tag color={KIND_COLOR[n.kind]} data-testid="notification-kind">
                      {KIND_LABEL[n.kind]}
                    </Tag>
                    <Typography.Text strong>{n.title}</Typography.Text>
                  </Space>
                  {n.summary && (
                    <Typography.Text type="secondary" data-testid="notification-summary">
                      {n.summary}
                    </Typography.Text>
                  )}
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {n.issued_at}
                  </Typography.Text>
                </Space>
                <Button
                  type="link"
                  size="small"
                  data-testid="notification-view"
                  data-notification-id={n.notification_id}
                  onClick={() => onItemClick?.(n.notification_id)}
                >
                  查看
                </Button>
              </Space>
            </List.Item>
          )}
        />
      )}
    </Drawer>
  );
}

export default NotificationCenter;