/**
 * NotificationCenter — 通知中心（P45-1-13 建 · P9A Z 收口按契约重绑）。
 *
 * SPEC §6.20（本轮扩写）+ §6.22：
 * - 右侧 Drawer，宽 420px
 * - 分组 tabs：待办 / 变更 / 系统 / 全部
 * - 消息结构：kind tag + 标题 + 正文 + 时间 + [查看]；未读左侧蓝点
 *
 * ⚠️ **数据形状逐字取契约**（`NotificationItemResponse` / `TodoResponse`）：
 * `kind` / `title` / `body` / `created_at` / `read_at` / `detail`。
 * ⚠️ **未读判定 = `read_at` 为 null**；红点数字 = 响应的 `unread_count`
 * （**不是**前端数 `items` —— 列表是分页的）。
 * ⚠️ **四个分组的来源**（SPEC §6.20 的来源表）：
 * 待办 ← `GET /todos`（**不是**通知）· 变更 ← `kind = CHANGE_NOTICE_APPROVED` ·
 * 系统 ← 其余三种 kind · 全部 ← 全部**通知**（不含待办）。
 */
import { useMemo, useState } from 'react';
import { Badge, Button, Drawer, Empty, List, Space, Tabs, Tag, Typography } from 'antd';

import {
  CHANGE_NOTICE_KIND,
  NOTIFICATION_KIND_COLOR,
  NOTIFICATION_KIND_LABEL,
  isUnread,
  type NotificationItem,
} from '../../api/notifications';
import type { TodoItem } from '../../api/todos';
import { TodoPanel } from './TodoPanel';

type TabKey = 'todo' | 'change' | 'system' | 'all';

interface Props {
  open: boolean;
  onClose: () => void;
  /** 契约形状的通知条目。 */
  notifications?: NotificationItem[];
  /** 契约形状的待办条目（实时计算，不落库）。 */
  todos?: TodoItem[];
  /** 未读总数（取 `GET /notifications` 的 `unread_count`）。 */
  unreadCount?: number;
  onItemClick?: (notification_id: string) => void;
  onTodoClick?: (todo: TodoItem) => void;
}

export function NotificationCenter({
  open,
  onClose,
  notifications = [],
  todos = [],
  unreadCount,
  onItemClick,
  onTodoClick,
}: Props): JSX.Element {
  const [activeTab, setActiveTab] = useState<TabKey>('all');

  const changeItems = useMemo(
    () => notifications.filter((n) => n.kind === CHANGE_NOTICE_KIND),
    [notifications],
  );
  const systemItems = useMemo(
    () => notifications.filter((n) => n.kind !== CHANGE_NOTICE_KIND),
    [notifications],
  );

  const counts: Record<TabKey, number> = {
    todo: todos.length,
    change: changeItems.length,
    system: systemItems.length,
    all: notifications.length,
  };

  const visible: Record<TabKey, NotificationItem[]> = {
    todo: [],
    change: changeItems,
    system: systemItems,
    all: notifications,
  };

  const badgeCount = unreadCount ?? notifications.filter(isUnread).length;

  return (
    <Drawer
      data-testid="notification-center"
      title="通知中心"
      placement="right"
      width={420}
      open={open}
      onClose={onClose}
      maskClosable  // 默认 true，显式确认未被覆盖（点遮罩关闭抽屉）
      keyboard      // 默认 true，显式确认未被覆盖（ESC 关闭抽屉）
    >
      <Tabs
        data-testid="notification-tabs"
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as TabKey)}
        items={[
          { key: 'todo', label: `待办（${counts.todo}）` },
          { key: 'change', label: `变更（${counts.change}）` },
          { key: 'system', label: `系统（${counts.system}）` },
          {
            key: 'all',
            label: (
              <Badge count={badgeCount} offset={[6, -2]} size="small">
                全部
              </Badge>
            ),
          },
        ]}
      />

      {activeTab === 'todo' ? (
        /* ⚠️ 待办 tab 的内容源是 **`GET /todos`**（不是通知）——
           SPEC §6.20 的分组来源表；且**待办与通知不得合并成一个列表**。 */
        <TodoPanel items={todos} onOpen={onTodoClick} />
      ) : visible[activeTab].length === 0 ? (
        <Empty description="暂无通知" data-testid="notification-empty" />
      ) : (
        <List
          data-testid="notification-list"
          size="small"
          dataSource={visible[activeTab]}
          renderItem={(n) => (
            <List.Item
              data-testid="notification-item"
              data-notification-id={n.notification_id}
              data-unread={isUnread(n) ? 'true' : 'false'}
              style={{ alignItems: 'flex-start' }}
            >
              <Space align="start" style={{ width: '100%' }}>
                {isUnread(n) && (
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
                    <Tag color={NOTIFICATION_KIND_COLOR[n.kind]} data-testid="notification-kind">
                      {NOTIFICATION_KIND_LABEL[n.kind] ?? n.kind}
                    </Tag>
                    <Typography.Text strong>{n.title}</Typography.Text>
                  </Space>
                  {n.body && (
                    <Typography.Text type="secondary" data-testid="notification-summary">
                      {n.body}
                    </Typography.Text>
                  )}
                  <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                    {n.created_at}
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
