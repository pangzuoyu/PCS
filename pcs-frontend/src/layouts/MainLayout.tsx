import { Button, Layout, Menu, Space, Typography } from 'antd';
import { Outlet, useNavigate } from 'react-router-dom';
import { useAuth } from '../store/auth';

const { Header, Content, Sider } = Layout;

export default function MainLayout() {
  const username = useAuth((s) => s.username);
  const role = useAuth((s) => s.role);
  const clear = useAuth((s) => s.clearSession);
  const nav = useNavigate();

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
          <Typography.Text style={{ color: '#fff' }}>
            {username} ({role})
          </Typography.Text>
          <Button onClick={onLogout}>登出</Button>
        </Space>
      </Header>
      <Layout>
        <Sider width={200}>
          <Menu
            mode="inline"
            defaultSelectedKeys={['dashboard']}
            items={[{ key: 'dashboard', label: '仪表盘' }]}
          />
        </Sider>
        <Content style={{ padding: 24 }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  );
}
