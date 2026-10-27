/**
 * ADMIN 用户管理页（P9B-2 · T7 · SPEC §7.20「用户管理（AD 同步）」/ P9A-ADM-001/002）。
 *
 * ⚠️ **停用后必须重新拉列表** —— 乐观更新单行会让「token_version」显示旧值，
 * 而用户正是靠它确认「已签发的 refresh 全部失效」（ADR-0046 §⑤）。
 *
 * ⚠️ **AD 同步的失败方向**：`ok=false` = **什么都没做**（目录连不上），
 * `skipped_empty=true` = 枚举到 0 个用户 ⇒ 两种都不是「同步成功」。
 */
import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Space, Table, Tag, Typography } from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { adminApi, type AdminUser } from '../../api/admin';
import { extractPcsError } from '../../api/errors';

export function UserAdminPage(): JSX.Element {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      setUsers(await adminApi.listUsers());
    } catch (err) {
      const envelope = extractPcsError(err);
      setUsers([]);
      setErrorMsg(
        envelope?.code
          ? `${envelope.code}：${envelope.message ?? ''}`
          : '加载用户列表失败',
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  async function disable(user: AdminUser) {
    setPendingId(user.user_id);
    setErrorMsg(null);
    setNotice(null);
    try {
      const res = await adminApi.disableUser(user.user_id);
      // ⚠️ **重新拉列表**（不乐观更新单行）—— 用户要看的 `token_version`
      //    是「已签发的 refresh 全部失效」的凭据（ADR-0046 §⑤）。
      await load();
      setNotice(`已停用 ${res.username}；token_version = ${res.token_version}`);
    } catch (err) {
      const envelope = extractPcsError(err);
      setErrorMsg(
        envelope?.code
          ? `${envelope.code}：${envelope.message ?? ''}`
          : '停用失败',
      );
    } finally {
      setPendingId(null);
    }
  }

  async function syncAd() {
    setSyncing(true);
    setErrorMsg(null);
    setNotice(null);
    try {
      const res = await adminApi.syncAdUsers();
      if (!res.ok) {
        // ⚠️ **`ok=false` = 什么都没做** ⇒ 不得显示成「同步成功」
        setErrorMsg(`AD 同步失败：${res.error ?? '（后端未给出原因）'}`);
        return;
      }
      if (res.skipped_empty) {
        // ⚠️ 枚举到 0 个用户 ⇒ **未做任何写入**（不是「同步成功」）
        setNotice('枚举到 0 个用户，未做任何写入');
        return;
      }
      setNotice(
        `AD 同步完成：新建 ${res.created} · 更新 ${res.updated} · 离职 ${res.departed}` +
          (res.unmapped ? ` · 未映射 ${res.unmapped}` : ''),
      );
      await load();
    } catch (err) {
      const envelope = extractPcsError(err);
      setErrorMsg(
        envelope?.code
          ? `${envelope.code}：${envelope.message ?? ''}`
          : 'AD 同步失败',
      );
    } finally {
      setSyncing(false);
    }
  }

  return (
    <div data-testid="user-admin-page">
      <PageHeader
        title="用户管理"
        actions={
          <Space>
            <Button data-testid="admin-sync-ad" loading={syncing} onClick={() => void syncAd()}>
              AD 同步
            </Button>
            <Button data-testid="admin-reload" onClick={() => void load()}>
              刷新
            </Button>
          </Space>
        }
      />

      {errorMsg && (
        <Alert
          type="error"
          showIcon
          message={errorMsg}
          data-testid="admin-error"
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setErrorMsg(null)}
        />
      )}
      {notice && (
        <Alert
          type="success"
          showIcon
          message={notice}
          data-testid="admin-notice"
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setNotice(null)}
        />
      )}

      <Card title={`用户（${users.length}）`}>
        <Table<AdminUser>
          rowKey="user_id"
          dataSource={users}
          loading={loading}
          size="small"
          pagination={{ pageSize: 20, showSizeChanger: false }}
          columns={[
            { title: '用户名', dataIndex: 'username', key: 'username' },
            { title: '姓名', dataIndex: 'display_name', key: 'display_name' },
            {
              title: '角色',
              dataIndex: 'roles',
              key: 'roles',
              render: (roles: string[]) =>
                (roles ?? []).map((r) => (
                  <Tag key={r} color="blue">
                    {r}
                  </Tag>
                )),
            },
            {
              title: '状态',
              dataIndex: 'status',
              key: 'status',
              render: (status: string) => (
                <Tag color={status === 'ACTIVE' ? 'green' : 'red'}>{status}</Tag>
              ),
            },
            {
              title: 'token_version',
              dataIndex: 'token_version',
              key: 'token_version',
            },
            {
              title: '操作',
              key: '__actions',
              render: (_: unknown, row: AdminUser) => (
                <Button
                  size="small"
                  danger
                  data-testid={`admin-disable-${row.user_id}`}
                  disabled={row.status === 'DISABLED' || pendingId === row.user_id}
                  onClick={() => void disable(row)}
                >
                  停用
                </Button>
              ),
            },
          ]}
        />
      </Card>
      <Typography.Text type="secondary" style={{ display: 'none' }}>
        停用后 token_version 递增 ⇒ 在手 refresh 全部失效（ADR-0046 §⑤）
      </Typography.Text>
    </div>
  );
}

export default UserAdminPage;
