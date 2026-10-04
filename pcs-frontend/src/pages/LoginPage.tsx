import { useState } from 'react';
import { App, Button, Card, Form, Input, Select, Space, Typography } from 'antd';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import { useAuth } from '../store/auth';

const MOCK_ACCOUNTS = [
  { value: 'alice', label: 'alice (DESIGNER)' },
  { value: 'bob', label: 'bob (CHECKER)' },
  { value: 'carol', label: 'carol (APPROVER)' },
  { value: 'dan', label: 'dan (SYSTEM_ADMIN)' },
];

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [mockUser, setMockUser] = useState('alice');
  const setSession = useAuth((s) => s.setSession);
  const nav = useNavigate();
  const { message } = App.useApp();

  async function onMockLogin() {
    setLoading(true);
    try {
      const tokens = await authApi.mockLogin(mockUser);
      // F-P7-S2 QA fix: 先 setSession (含 accessToken), 再调 /auth/me
      // 否则 axios 请求拦截器读不到 token, /auth/me 401 → clearSession → 死循环
      setSession({ ...tokens, user_id: '00000000-0000-0000-0000-000000000001' });
      // P7-7+ actor 上下文一致性: 拿权威 user_id 必须调 /auth/me
      // (与 Depends(current_actor) 派生保持一致, 避免前后端分叉)
      const me = await authApi.me();
      setSession({ ...tokens, user_id: me.user_id });
      message.success(`已登录：${me.username} / ${me.role} (${me.user_id.slice(0, 8)}…)`);
      nav('/');
    } catch (e) {
      const msg =
        (e as { response?: { data?: { message?: string } } })?.response?.data?.message ??
        String(e);
      message.error(`登录失败：${msg}`);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div style={{ display: 'flex', justifyContent: 'center', paddingTop: 80 }}>
      <Card title="PCS 工艺计算套件" style={{ width: 420 }}>
        <Space direction="vertical" style={{ width: '100%' }} size="middle">
          <Typography.Paragraph type="secondary">
            开发环境：选择 mock 账号一键登录。生产环境将走 LDAP 域账号登录。
          </Typography.Paragraph>
          <Form layout="vertical">
            <Form.Item label="Mock 账号">
              <Select
                value={mockUser}
                onChange={setMockUser}
                options={MOCK_ACCOUNTS}
              />
            </Form.Item>
            <Form.Item label="密码（mock 忽略）">
              <Input.Password value="mock" disabled />
            </Form.Item>
            <Button
              type="primary"
              block
              loading={loading}
              onClick={onMockLogin}
            >
              登录
            </Button>
          </Form>
        </Space>
      </Card>
    </div>
  );
}
