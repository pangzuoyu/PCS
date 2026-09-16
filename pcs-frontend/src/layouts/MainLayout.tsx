import { useEffect, useState } from 'react';
import { Badge, Button, Layout, Menu, Space, Typography } from 'antd';
import { BellOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../store/auth';
import { NotificationCenter, type Notification } from '../components/common/NotificationCenter';

const { Header, Content, Sider } = Layout;

type MenuItem = Required<MenuProps>['items'][number];

function group(label: string, key: string, children: MenuItem[]): MenuItem {
  return { type: 'group', label, key, children };
}

const MENU_ITEMS: MenuItem[] = [
  { key: '/', label: '仪表盘' },
  group('基础配置', 'config', [
    { key: '/config/asset-list', label: '设备一览' },
    { key: '/config/approval-panel', label: '审批面板' },
    { key: '/config/formula-editor', label: '公式编辑器' },
    { key: '/config/template-file', label: '模板文件' },
    { key: '/config/coefficient-editor', label: '系数表编辑器' },
  ]),
  group('物流', 'sim', [
    { key: '/sim/streams', label: '物流一览' },
    { key: '/sim/import', label: '导入向导' },
  ]),
  group('管道等级', 'pipe-class', [
    { key: '/pipe-class', label: '等级一览' },
    { key: '/pipe-class/symbols', label: '符号表' },
    { key: '/pipe-class/code-format', label: '代码格式设计器' },
  ]),
  group('物性', 'common', [
    { key: '/common/properties', label: '物性查询' },
    { key: '/common/stress', label: '许用应力' },
    { key: '/common/toxicity', label: '毒性爆炸' },
  ]),
  group('工艺计算', 'calc', [
    { key: '/flash', label: '闪蒸' },
    { key: '/pipe', label: '管道计算' },
    { key: '/pipe/line-list', label: '管道一览表' },
    { key: '/pipe-net', label: '管网拓扑' },
    { key: '/pump', label: '泵计算' },
  ]),
  group('项目文档', 'docs', [
    { key: '/pms', label: 'PMS 规格' },
    { key: '/bedd', label: 'BEDD 文档' },
    { key: '/wizard', label: '项目向导' },
  ]),
];

/** 在 MENU_ITEMS 中找 path 命中的条目（含父 group）。找不到返回 []。 */
function findSelectedKeys(pathname: string): string[] {
  for (const item of MENU_ITEMS) {
    if (item && 'children' in item && item.children) {
      for (const c of item.children) {
        if (c && 'key' in c && c.key === pathname) {
          return [String(item.key), pathname];
        }
      }
    }
  }
  return [pathname];
}

export default function MainLayout() {
  const username = useAuth((s) => s.username);
  const role = useAuth((s) => s.role);
  const clear = useAuth((s) => s.clearSession);
  const nav = useNavigate();
  const location = useLocation();
  const [notifOpen, setNotifOpen] = useState(false);
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    void fetch('/api/v1/notifications', {
      headers: { Authorization: 'Bearer mock-jwt-token' },
    })
      .then((r) => (r.ok ? r.json() : []))
      .then((j: Notification[]) => setNotifications(j))
      .catch(() => {/* offline */});
  }, []);

  const unreadCount = notifications.filter((n) => n.unread).length;

  const selectedKeys = findSelectedKeys(location.pathname);
  const openKeys = selectedKeys.length > 1 ? [selectedKeys[0]] : [];

  function onLogout() {
    clear();
    nav('/login');
  }

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
        <Typography.Title level={4} style={{ color: '#fff', margin: 0 }}>
          PCS
        </Typography.Title>
        <div style={{ flex: 1 }} />
        <Space>
          <Badge count={unreadCount} size="small" data-testid="notif-badge">
            <Button
              type="text"
              icon={<BellOutlined style={{ color: '#fff', fontSize: 18 }} />}
              data-testid="notif-bell"
              onClick={() => setNotifOpen(true)}
            />
          </Badge>
          <Typography.Text style={{ color: '#fff' }}>
            {username} ({role})
          </Typography.Text>
          <Button onClick={onLogout}>登出</Button>
        </Space>
      </Header>
      <Layout>
        <Sider width={220} style={{ overflow: 'auto' }}>
          <Menu
            mode="inline"
            selectedKeys={selectedKeys}
            defaultOpenKeys={openKeys}
            items={MENU_ITEMS}
            onClick={(e) => {
              if (typeof e.key === 'string' && e.key.startsWith('/')) nav(e.key);
            }}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Outlet />
        </Content>
      </Layout>

      <NotificationCenter
        open={notifOpen}
        onClose={() => setNotifOpen(false)}
        notifications={notifications}
        onItemClick={(id) => {
          // 简单点击行为：标记为已读（前端 mock）
          setNotifications((prev) => prev.map((n) => (n.notification_id === id ? { ...n, unread: false } : n)));
        }}
      />
    </Layout>
  );
}