/**
 * 系统状态页（P10-C · T1b · SPEC §7.22）。
 *
 * ## 为什么是**只读**页
 *
 * 这是**看**系统状态的页面 ⇒ ⇒ ⇒ 没有任何写操作 ⇒ ⇒ ⇒ 不需要角色闸
 * ⇒ ⇒ ⇒ （真要限制 ⇒ ⇒ ⇒ 后端加守卫 ⇒ ⇒ ⇒ 端点是 `GET /status`）。
 *
 * ## ⚠️ 与 `/health` 的区别
 *
 * 顶部横幅那个 `/health` 是 **liveness probe** 的信息 ⇒ ⇒ ⇒ 只管
 * 「实时推送通不通」⇒ ⇒ ⇒ 本页是**完整状态**（DB / Redis / 队列 / worker / LDAP）。
 *
 * ## ⚠️ 不显示敏感值
 *
 * 后端只给「通不通 / 有多深 / 什么时候心跳」⇒ ⇒ ⇒ 前端**原样显示**
 * ⇒ ⇒ ⇒ 不额外拼 URL / 口令。
 */
import { useCallback, useEffect, useState } from 'react';
import { Alert, Button, Card, Descriptions, Space, Spin, Table, Tag, Typography } from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import {
  STATUS_COLOR,
  STATUS_LABEL,
  statusApi,
  type ComponentStatus,
  type StatusResponse,
} from '../../api/status';

const { Paragraph, Title } = Typography;

/** 组件名（**与后端字段同名** ⇒ ⇒ 映射零歧义）。 */
const COMPONENT_NAMES: Record<string, string> = {
  database: '数据库',
  redis: 'Redis',
  queue: '任务队列',
  ldap: 'LDAP',
};

function StatusTag({ value }: { value: ComponentStatus['status'] }): JSX.Element {
  return <Tag color={STATUS_COLOR[value]}>{STATUS_LABEL[value]}</Tag>;
}

export default function StatusPage(): JSX.Element {
  const [data, setData] = useState<StatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const resp = await statusApi.get();
      setData(resp);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : '状态读取失败');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  if (loading && !data) {
    return (
      <Card>
        <Spin tip="读取系统状态…">
          <div style={{ height: 120 }} />
        </Spin>
      </Card>
    );
  }

  return (
    <Space direction="vertical" size="middle" style={{ width: '100%' }}>
      <Title level={3}>系统状态</Title>

      {error && (
        <Alert
          type="error"
          showIcon
          message="状态读取失败"
          description={error}
          action={
            <Button size="small" onClick={() => void load()}>
              重试
            </Button>
          }
        />
      )}

      {data && (
        <>
          <Card
            title="总体"
            extra={
              <Button icon={<ReloadOutlined />} onClick={() => void load()} loading={loading}>
                刷新
              </Button>
            }
          >
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="总体状态">
                <StatusTag value={data.status} />
              </Descriptions.Item>
              <Descriptions.Item label="探测时刻">
                {new Date(data.checked_at * 1000).toLocaleString()}
              </Descriptions.Item>
            </Descriptions>
          </Card>

          <Card title="组件">
            <Table
              size="small"
              rowKey="name"
              pagination={false}
              dataSource={(['database', 'redis', 'queue', 'ldap'] as const).map((key) => ({
                name: COMPONENT_NAMES[key],
                status: key === 'queue' ? data.queue.status : data[key].status,
                detail:
                  key === 'queue'
                    ? (data.queue.worker_last_heartbeat ?? '—')
                    : (data[key].detail ?? '—'),
                latency:
                  key === 'queue' ? null : (data[key].latency_ms ?? null),
              }))}
              columns={[
                { title: '组件', dataIndex: 'name', key: 'name' },
                {
                  title: '状态',
                  dataIndex: 'status',
                  key: 'status',
                  render: (value: ComponentStatus['status']) => <StatusTag value={value} />,
                },
                { title: '说明', dataIndex: 'detail', key: 'detail' },
                {
                  title: '耗时',
                  dataIndex: 'latency',
                  key: 'latency',
                  render: (value: number | null) => (value === null ? '—' : `${value} ms`),
                },
              ]}
            />
          </Card>

          <Card title="任务队列">
            <Descriptions column={2} size="small" bordered>
              <Descriptions.Item label="待处理任务数">
                {data.queue.depth ?? '—'}
              </Descriptions.Item>
              <Descriptions.Item label="Worker 存活">
                {data.queue.worker_alive === null ? '—' : data.queue.worker_alive ? '是' : '否'}
              </Descriptions.Item>
              <Descriptions.Item label="最近心跳" span={2}>
                <Paragraph style={{ marginBottom: 0, wordBreak: 'break-all' }}>
                  {data.queue.worker_last_heartbeat ?? '—'}
                </Paragraph>
              </Descriptions.Item>
            </Descriptions>
          </Card>
        </>
      )}
    </Space>
  );
}
