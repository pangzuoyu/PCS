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
import { Alert, Button, Card, Modal, Space, Table, Tag } from 'antd';

import { PageHeader } from '../../components/common/PageHeader';
import { adminApi, type AdminUser } from '../../api/admin';
import { describePcsError } from '../../api/errors';

/**
 * 时间戳显示（**UTC**，固定格式）。
 *
 * ⚠️ 不用 `toLocaleString` —— 那是**运行机器的时区 / 语言** ⇒ 同一份数据在
 * 不同机器上显示不同 ⇒ 单测没法断言、用户也会怀疑「这时间对不对」。
 */
function formatUtc(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${d.toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

export function UserAdminPage(): JSX.Element {
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  // ⚠️ notice 带**类型**：`skipped_empty`（**什么都没写入**）⇒ warning 条，
  //    不是绿色 success 条（绿色 = 「成功」⇒ 用户以为同步过了）。
  const [notice, setNotice] = useState<{ type: 'success' | 'warning'; text: string } | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  // ⚠️ **停用要二次确认**（P9B-2 · 延后的 minor）：停用会**递增 token_version**
  //    ⇒ 在手 refresh **全部失效**（ADR-0046 §⑤）⇒ 误点即误伤一个人。
  //    ⇒ 点「停用」只**开确认框**，确认后才发 PUT。
  const [pendingDisable, setPendingDisable] = useState<AdminUser | null>(null);
  // ⚠️ **列表加载失败** ⇒ ①错误提示**不可关闭** ②**不渲染空表**。
  //    关掉提示 ⇒ 页面只剩「用户（0）」的空表 ⇒ 管理员读成「系统里一个用户都
  //    没有」⇒ 真相可能是「你没权限」（RF-12）⇒ 两个后果都不可接受。
  const [listFailed, setListFailed] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setErrorMsg(null);
    try {
      setUsers(await adminApi.listUsers());
      setListFailed(false);
    } catch (err) {
      setUsers([]);
      setListFailed(true);
      setErrorMsg(describePcsError(err, '加载用户列表失败'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /** 打开确认框（**不发请求**）。 */
  function askDisable(user: AdminUser): void {
    setPendingDisable(user);
  }

  async function confirmDisable(): Promise<void> {
    const user = pendingDisable;
    if (!user) return;
    setPendingId(user.user_id);
    setErrorMsg(null);
    setNotice(null);
    try {
      const res = await adminApi.disableUser(user.user_id);
      // ⚠️ **重新拉列表**（不乐观更新单行）—— 用户要看的 `token_version`
      //    是「已签发的 refresh 全部失效」的凭据（ADR-0046 §⑤）。
      await load();
      setNotice({
        type: 'success',
        text: `已停用 ${res.username}；token_version = ${res.token_version}`,
      });
      setPendingDisable(null);
    } catch (err) {
      setErrorMsg(describePcsError(err, '停用失败'));
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
        setNotice({ type: 'warning', text: '枚举到 0 个用户，未做任何写入' });
        return;
      }
      setNotice({
        type: 'success',
        text:
          `AD 同步完成：新建 ${res.created} · 更新 ${res.updated} · 离职 ${res.departed}` +
          (res.unmapped ? ` · 未映射 ${res.unmapped}` : ''),
      });
      await load();
    } catch (err) {
      setErrorMsg(describePcsError(err, 'AD 同步失败'));
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
          // ⚠️ **列表加载失败 ⇒ 不可关闭**（关掉 = 假装没有数据）
          closable={!listFailed}
          onClose={() => setErrorMsg(null)}
        />
      )}
      {notice && (
        <Alert
          type={notice.type}
          showIcon
          message={notice.text}
          data-testid="admin-notice"
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setNotice(null)}
        />
      )}

      {/* ⚠️ **列表加载失败 ⇒ 不渲染表**（空表会被读成「没有用户」） */}
      {!listFailed && (
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
            // ⚠️ email / department / last_login_at **后端本来就返回**
            //    （`AdminUserOut`）⇒ 之前没展示 ⇒ 运营「不知道这个人是谁」。
            { title: '邮箱', dataIndex: 'email', key: 'email' },
            { title: '部门', dataIndex: 'department', key: 'department' },
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
              title: '最近登录',
              dataIndex: 'last_login_at',
              key: 'last_login_at',
              render: (v?: string | null) => formatUtc(v),
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
                  onClick={() => askDisable(row)}
                >
                  停用
                </Button>
              ),
            },
          ]}
        />
      </Card>
      )}

      {/* ⚠️ **停用二次确认** —— 误点即误伤一个人（在手 refresh 全失效） */}
      <Modal
        open={pendingDisable !== null}
        title="停用用户"
        footer={null}
        onCancel={() => setPendingDisable(null)}
        destroyOnHidden
      >
        <div data-testid="admin-disable-confirm">
          <p>
            确认停用用户 <strong>{pendingDisable?.username}</strong>
            （{pendingDisable?.display_name}）？
          </p>
          <p>
            ⚠️ 停用后 <strong>token_version 递增</strong> ⇒{' '}
            <strong>在手 refresh 全部失效</strong>（该用户需重新登录）。
          </p>
          <Space>
            <Button
              data-testid="admin-disable-confirm-cancel"
              onClick={() => setPendingDisable(null)}
            >
              取消
            </Button>
            <Button
              danger
              type="primary"
              data-testid="admin-disable-confirm-ok"
              loading={pendingId !== null}
              onClick={() => void confirmDisable()}
            >
              确认停用
            </Button>
          </Space>
        </div>
      </Modal>
    </div>
  );
}

export default UserAdminPage;
