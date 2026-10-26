import { useEffect, useState } from 'react';
import { Alert, Badge, Button, Layout, Menu, Space, Typography } from 'antd';
import { BellOutlined } from '@ant-design/icons';
import type { MenuProps } from 'antd';
import { Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../store/auth';
import { NotificationCenter } from '../components/common/NotificationCenter';
import {
  notificationsApi,
  type NotificationItem,
} from '../api/notifications';
import { todosApi, type TodoItem } from '../api/todos';
import { healthApi } from '../api/health';
import { RealtimeStatusBanner } from '../components/common/RealtimeStatusBanner';
import { useDegradation } from '../store/degradation';

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
    { key: '/common/heating-value', label: '气体热值' },
  ]),
  group('工艺计算', 'calc', [
    { key: '/flash', label: '闪蒸' },
    { key: '/pipe', label: '管道计算' },
    { key: '/pipe/line-list', label: '管道一览表' },
    { key: '/pipe-net', label: '管网拓扑' },
    { key: '/pump', label: '泵计算' },
    { key: '/vessel', label: '容器计算' },
    { key: '/sep-equip', label: '分离设备' },
    { key: '/psv', label: '安全阀' },
    { key: '/heat', label: '换热器' },
    { key: '/cv', label: '控制阀' },
    { key: '/psychro/saturation-water-content', label: '饱和水含量' },
  ]),
  group('公用工程', 'util', [
    { key: '/util/cooling-water', label: '冷却水子表' },
    { key: '/util/energy-summary', label: '综合能耗聚合' },
  ]),
  group('报表', 'report', [
    { key: '/report/definitions', label: '报表定义' },
    { key: '/report/styles', label: '报表样式' },
  ]),
  group('结果记录', 'results', [
    { key: '/results/cool-tower', label: '冷却塔结果' },
    { key: '/results/filtration', label: '过滤结果' },
    { key: '/results/flare', label: '火炬系统结果' },
    { key: '/results/open-channel', label: '明渠结果' },
    { key: '/results/psychro', label: '湿空气结果' },
    { key: '/results/cost-est', label: '成本估算结果' },
  ]),
  group('交付物', 'deliverables', [
    { key: '/deliverables/progress', label: '签署进度' },
    { key: '/deliverables/signature-matrices', label: '签署矩阵' },
  ]),
  group('审计', 'audit', [
    { key: '/audit/logs', label: 'Audit Query (F-P2-009)' },
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
  const [notifications, setNotifications] = useState<NotificationItem[]>([]);
  const [todos, setTodos] = useState<TodoItem[]>([]);
  const [unreadCount, setUnreadCount] = useState(0);
  // ⚠️ 降级横幅的文案取**后端 message 原文**（前端不拼接、不自造）。
  const degradationMessage = useDegradation((s) => s.message);
  // ⚠️ **实时推送状态**（SPEC §6.23）—— 数据源是 `GET /health` 的
  // `realtime` / `realtime_reason`。
  // ⚠️ 这条横幅必须有**宿主** ⇒ 组件只活在测试里 = 功能没交付
  // （最终评审 Important ④）⇒ 挂在顶栏，与降级横幅并列。
  const [realtime, setRealtime] = useState<{
    status: 'ok' | 'degraded';
    reason: string | null;
  }>({ status: 'ok', reason: null });

  useEffect(() => {
    // ⚠️ `/health` **始终 200**（后端约定）⇒ 只在**请求本身失败**时保持
    // 「ok」（不显示横幅）—— 拿不到状态**不等于**降级。
    let cancelled = false;
    const load = (): void => {
      void healthApi
        .get()
        .then((h) => {
          if (cancelled) return;
          setRealtime({
            status: h.realtime === 'degraded' ? 'degraded' : 'ok',
            reason: h.realtime_reason ?? null,
          });
        })
        .catch(() => {
          // offline / 未登录 ⇒ 不显示横幅（不是「已关闭」）
        });
    };
    load();
    const timer = setInterval(load, 60_000);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, []);

  useEffect(() => {
    // ⚠️ **走 axios 实例**（`api`）而不是裸 `fetch`：
    // ① 实例带 token 拦截器 + 401 清会话；② 响应形状**逐字取契约**
    // （`{items, unread_count}`）—— 原来的裸 fetch 把响应**当数组**用
    // （`as Notification[]` 是类型断言，运行时零检查）⇒ 生产构建下
    // `notifications.filter` 抛 TypeError ⇒ **整个壳崩**（TODO-065）。
    void notificationsApi
      .list()
      .then((res) => {
        setNotifications(res.items);
        setUnreadCount(res.unread_count);
      })
      .catch(() => {/* offline */});
    // 待办**实时计算**（不落库）⇒ 每次挂载现拉，不缓存。
    void todosApi
      .list()
      .then((res) => setTodos(res.items))
      .catch(() => {/* offline */});
  }, []);

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
      {degradationMessage && (
        <Alert
          type="warning"
          showIcon
          data-testid="degradation-banner"
          message={degradationMessage}
          style={{ margin: '8px 24px 0' }}
        />
      )}
      {/* ⚠️ 实时推送降级（SPEC §6.23）—— 与「编辑锁降级」是**两回事**：
          一个是 Redis pub/sub 不可达（通知改轮询），一个是锁服务不可用
          （并发检测降级）。**都不阻断任何操作**。 */}
      <div style={{ margin: '8px 24px 0' }}>
        <RealtimeStatusBanner realtime={realtime.status} reason={realtime.reason} />
      </div>
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
        todos={todos}
        unreadCount={unreadCount}
        onItemClick={(id) => {
          // 标已读是**幂等**的服务端动作 ⇒ 标完**重新拉列表**，
          // 不要就地改本地 `read_at`（那会让计数与真值漂移）。
          void notificationsApi
            .markRead(id)
            .then(() => notificationsApi.list())
            .then((res) => {
              setNotifications(res.items);
              setUnreadCount(res.unread_count);
            })
            .catch(() => {/* offline */});
        }}
      />
    </Layout>
  );
}