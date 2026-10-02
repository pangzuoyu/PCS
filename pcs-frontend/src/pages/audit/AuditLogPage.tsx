/**
 * AuditLogPage — Audit Query viewer (F-P2-009 Sprint 3 / Issue 7).
 *
 * 三 tab 切换 3 个 audit 端点:
 * - 通用 audit (/audit-logs, SYSTEM_ADMIN)
 * - 设备删除 audit (/equipment-deletion-audit, DESIGNER+ + project_id)
 * - CONFIG R1 痕迹 (/config-audit, DESIGNER+, 全公司)
 *
 * R1 §7 工艺室可查自己 project 的 CONFIG 修订痕迹 (F-P0-001).
 */
import { useEffect, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Card,
  Form,
  Input,
  InputNumber,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import { auditApi, type AuditLogItem } from '../../api/audit';
import { useAuth } from '../../store/auth';

type TabKey = 'config-audit' | 'equipment-deletion' | 'audit-logs';

interface PcsErrorEnvelope {
  code?: string;
  message?: string;
}
function extractPcsError(err: unknown): PcsErrorEnvelope {
  if (err && typeof err === 'object' && 'response' in err) {
    const data = (err as { response?: { data?: PcsErrorEnvelope } }).response?.data;
    if (data && typeof data === 'object') return data;
  }
  return {};
}

const TAB_LABELS: Record<TabKey, string> = {
  'config-audit': 'CONFIG R1 修订痕迹 (工艺室可查)',
  'equipment-deletion': '设备删除审计 (DESIGNER+)',
  'audit-logs': '通用 audit (SYSTEM_ADMIN)',
};

export function AuditLogPage(): JSX.Element {
  const role = useAuth((s) => s.role);
  const [activeTab, setActiveTab] = useState<TabKey>('config-audit');
  const [items, setItems] = useState<AuditLogItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // CONFIG tab 过滤
  const [assetId, setAssetId] = useState<number | undefined>(undefined);
  // equipment-deletion tab 过滤
  const [projectId, setProjectId] = useState<string | undefined>(undefined);

  async function loadConfigAudit(): Promise<void> {
    setErrorMsg(null);
    setLoading(true);
    try {
      const r = await auditApi.listConfigAudit(
        assetId !== undefined ? { asset_id: assetId, limit: 50 } : { limit: 50 },
      );
      setItems(r.items);
      setTotal(r.total);
    } catch (err: unknown) {
      setErrorMsg(
        `${extractPcsError(err).code ?? 'HTTP_500'}: ${
          extractPcsError(err).message ?? 'CONFIG audit 查询失败'
        }`,
      );
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  async function loadEquipmentDeletionAudit(): Promise<void> {
    if (!projectId) {
      setErrorMsg('project_id 必填 (非 SYSTEM_ADMIN 必须传)');
      return;
    }
    setErrorMsg(null);
    setLoading(true);
    try {
      const r = await auditApi.listEquipmentDeletionAudit({
        project_id: projectId,
        limit: 50,
      });
      setItems(r.items as unknown as AuditLogItem[]);
      setTotal(r.total);
    } catch (err: unknown) {
      setErrorMsg(
        `${extractPcsError(err).code ?? 'HTTP_500'}: ${
          extractPcsError(err).message ?? '设备删除 audit 查询失败'
        }`,
      );
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  async function loadAuditLogs(): Promise<void> {
    setErrorMsg(null);
    setLoading(true);
    try {
      const r = await auditApi.listAuditLogs({ limit: 50 });
      setItems(r.items);
      setTotal(r.total);
    } catch (err: unknown) {
      setErrorMsg(
        `${extractPcsError(err).code ?? 'HTTP_500'}: ${
          extractPcsError(err).message ?? 'audit-logs 查询失败'
        }`,
      );
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (activeTab === 'config-audit') void loadConfigAudit();
    if (activeTab === 'equipment-deletion') void loadEquipmentDeletionAudit();
    if (activeTab === 'audit-logs') void loadAuditLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, assetId, projectId]);

  const columns: ColumnsType<AuditLogItem> = [
    { title: '时间', dataIndex: 'occurred_at', width: 200 },
    { title: '动作', dataIndex: 'action', width: 180 },
    {
      title: '资源类型',
      dataIndex: 'resource_type',
      width: 220,
      render: (v?: string) =>
        v ? <Tag color="blue">{v}</Tag> : <Tag>—</Tag>,
    },
    { title: '资源 ID', dataIndex: 'resource_id', width: 120 },
    { title: '操作者', dataIndex: 'user_id', width: 280 },
  ];

  const canAdmin = role === 'SYSTEM_ADMIN';

  return (
    <div>
      <PageHeader
        title="Audit Query (F-P2-009 Sprint 3)"
        actions={
          <Button onClick={() => setItems([])} disabled={!items.length}>
            清空结果
          </Button>
        }
      />

      <Alert
        type="info"
        showIcon
        message={
          <span>
            当前角色 <Tag>{role ?? 'anonymous'}</Tag>.{' '}
            /config-audit 与 /equipment-deletion-audit 限 DESIGNER+;
            /audit-logs 限 SYSTEM_ADMIN.
          </span>
        }
        style={{ marginBottom: 16 }}
      />

      {errorMsg && (
        <Alert
          type="error"
          showIcon
          message={errorMsg}
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setErrorMsg(null)}
        />
      )}

      <Tabs
        activeKey={activeTab}
        onChange={(k) => setActiveTab(k as TabKey)}
        items={[
          {
            key: 'config-audit',
            label: TAB_LABELS['config-audit'],
            children: (
              <Card style={{ marginBottom: 16 }}>
                <Form layout="inline">
                  <Form.Item label="asset_id (ConfigEnergyConversionFactor.id)">
                    <InputNumber
                      min={1}
                      value={assetId}
                      onChange={(v) => setAssetId(v ?? undefined)}
                      placeholder="可选 — 过滤单行"
                    />
                  </Form.Item>
                  <Form.Item>
                    <Button type="primary" onClick={() => void loadConfigAudit()}>
                      查询
                    </Button>
                  </Form.Item>
                </Form>
              </Card>
            ),
          },
          {
            key: 'equipment-deletion',
            label: TAB_LABELS['equipment-deletion'],
            children: (
              <Card style={{ marginBottom: 16 }}>
                <Form layout="inline">
                  <Form.Item label="project_id (UUID)" required>
                    <Input
                      value={projectId ?? ''}
                      onChange={(e) => setProjectId(e.target.value || undefined)}
                      placeholder="必填 (非 admin)"
                      style={{ width: 360 }}
                    />
                  </Form.Item>
                  <Form.Item>
                    <Button
                      type="primary"
                      onClick={() => void loadEquipmentDeletionAudit()}
                      disabled={!projectId}
                    >
                      查询
                    </Button>
                  </Form.Item>
                </Form>
              </Card>
            ),
          },
          {
            key: 'audit-logs',
            label: TAB_LABELS['audit-logs'],
            disabled: !canAdmin,
            children: (
              <Card style={{ marginBottom: 16 }}>
                <Typography.Text type="secondary">
                  通用 audit 日志查询 (无 9-dim filter UI — 全表拉取).
                </Typography.Text>
              </Card>
            ),
          },
        ]}
      />

      <Card title={`结果 (共 ${total} 条)`}>
        <Table<AuditLogItem>
          rowKey="audit_id"
          dataSource={items}
          columns={columns}
          loading={loading}
          size="small"
          pagination={{ pageSize: 50, showSizeChanger: false }}
        />
      </Card>
    </div>
  );
}

export default AuditLogPage;