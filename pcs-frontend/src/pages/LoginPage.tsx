import { useState } from 'react';
import { Button, Card, Form, Input, Select, Space, Typography, message } from 'antd';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/client';
import { useAuth } from '../store/auth';

const MOCK_ACCOUNTS = [
  { value: 'alice', label: 'alice (DESIGNER)' },
  { value: 'bob', label: 'bob (CHECKER)' },
  { value: 'carol', label: 'carol (APPROVER)' },
  { value: 'dan', label: 'dan (SYSADMIN)' },
];

export default function LoginPage() {
  const [loading, setLoading] = useState(false);
  const [mockUser, setMockUser] = useState('alice');
  const setSession = useAuth((s) => s.setSession);
  const nav = useNavigate();

  async function onMockLogin() {
    setLoading(true);
    try {
      const data = await authApi.mockLogin(mockUser);
      setSession(data);
      message.success(`已登录：${data.username} / ${data.role}`);
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
