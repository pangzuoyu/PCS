/**
 * AuditLogPage — 审计日志查询（F-P2-009 Sprint 3 / Issue 7 · **P9B-2 扩展**）。
 *
 * 三 tab 切换 3 个 audit 端点:
 * - 通用 audit (/audit-logs, SYSTEM_ADMIN)
 * - 设备删除 audit (/equipment-deletion-audit, DESIGNER+ + project_id)
 * - CONFIG R1 痕迹 (/config-audit, DESIGNER+, 全公司)
 *
 * R1 §7 工艺室可查自己 project 的 CONFIG 修订痕迹 (F-P0-001).
 *
 * ## ⚠️ P9B-2：通用 audit tab 加**筛选 + 导出 CSV**（SPEC §7.20）
 *
 * ⚠️ **导出的数据源是前端循环拉页**（同一筛选条件，上限 **5000 行**）——
 * 后端**没有** audit 导出端点（`/meta/permissions.csv` 是另一个东西）。
 * ⇒ 大结果集会**截断** ⇒ 必须**显式提示**（RF-11），不得让用户以为拿到了全部。
 * ⇒ CSV 字段**必须转义**（`detail_json` 里可能有逗号 / 引号 / 换行）⇒
 * 不转义的话 Excel 会拆错列 ⇒ 用户拿到的数据是**残缺的**。
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

import { PageHeader } from '../../components/common/PageHeader';
import { auditApi, type AuditLogItem, type ListAuditLogsParams } from '../../api/audit';
import { downloadCsv, toCsv } from '../../lib/csv';
import { useAuth } from '../../store/auth';
import type { StrictColumns } from '../../types/strictColumns';

type TabKey = 'config-audit' | 'equipment-deletion' | 'audit-logs';

/** 导出上限（RF-11）：超限**显式提示截断**。 */
const EXPORT_LIMIT = 5000;
/** 导出时每页的行数。 */
const EXPORT_PAGE_SIZE = 200;

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
  // ⚠️ 通用 audit tab 的**筛选条件**（P9B-2）—— 直接映射 api 层已有的参数名
  const [auditFilter, setAuditFilter] = useState<ListAuditLogsParams>({});
  const [exporting, setExporting] = useState(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

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
      const r = await auditApi.listAuditLogs({ ...auditFilter, limit: 50 });
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

  /**
   * 导出 CSV（**当前筛选条件下的全部行**，上限 5000）。
   *
   * ⚠️ **循环拉页**（不是只导当前页）—— 只导当前页却让按钮写着「全部」⇒
   * 用户拿到的数据是**残缺的**（RF-11）。
   * ⚠️ **超限显式提示截断** ⇒ 不得静默截断。
   */
  async function exportAuditCsv(): Promise<void> {
    setExporting(true);
    setExportNotice(null);
    try {
      const collected: AuditLogItem[] = [];
      let offset = 0;
      let truncated = false;
      // ⚠️ 最多 25 页 × 200 行 = 5000 行（上限）
      while (offset < EXPORT_LIMIT) {
        const r = await auditApi.listAuditLogs({
          ...auditFilter,
          limit: EXPORT_PAGE_SIZE,
          offset,
        });
        collected.push(...r.items);
        if (collected.length >= EXPORT_LIMIT) {
          truncated = true;
          break;
        }
        if (r.items.length < EXPORT_PAGE_SIZE) break;
        offset += EXPORT_PAGE_SIZE;
      }
      const rows = collected.slice(0, EXPORT_LIMIT).map((i) => [
        i.occurred_at,
        i.action,
        i.resource_type ?? '',
        i.resource_id ?? '',
        i.user_id ?? '',
        // ⚠️ `detail_json` 是 dict ⇒ 序列化成文本（导出的 CSV 是纯文本）
        i.detail_json ? JSON.stringify(i.detail_json) : '',
      ]);
      const csv = toCsv(
        ['occurred_at', 'action', 'resource_type', 'resource_id', 'user_id', 'detail_json'],
        rows,
      );
      downloadCsv('audit-logs.csv', csv);
      setExportNotice(
        truncated
          ? `已导出前 ${EXPORT_LIMIT} 行（结果集超过上限，已截断）`
          : `已导出 ${rows.length} 行（当前筛选条件下的全部结果）`,
      );
    } catch (err: unknown) {
      setErrorMsg(
        `${extractPcsError(err).code ?? 'HTTP_500'}: ${
          extractPcsError(err).message ?? '导出失败'
        }`,
      );
    } finally {
      setExporting(false);
    }
  }

  useEffect(() => {
    if (activeTab === 'config-audit') void loadConfigAudit();
    if (activeTab === 'equipment-deletion') void loadEquipmentDeletionAudit();
    if (activeTab === 'audit-logs') void loadAuditLogs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, assetId, projectId]);

  const columns: StrictColumns<AuditLogItem> = [
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
        title="审计日志"
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
                <Form layout="inline">
                  <Form.Item label="action">
                    <Input
                      data-testid="audit-filter-action"
                      value={auditFilter.action ?? ''}
                      onChange={(e) =>
                        setAuditFilter((f) => ({ ...f, action: e.target.value || undefined }))
                      }
                      placeholder="可选"
                      style={{ width: 200 }}
                    />
                  </Form.Item>
                  <Form.Item label="resource_type">
                    <Input
                      data-testid="audit-filter-resource-type"
                      value={auditFilter.resource_type ?? ''}
                      onChange={(e) =>
                        setAuditFilter((f) => ({
                          ...f,
                          resource_type: e.target.value || undefined,
                        }))
                      }
                      placeholder="可选"
                      style={{ width: 200 }}
                    />
                  </Form.Item>
                  <Form.Item label="resource_id">
                    <Input
                      data-testid="audit-filter-resource-id"
                      value={auditFilter.resource_id ?? ''}
                      onChange={(e) =>
                        setAuditFilter((f) => ({
                          ...f,
                          resource_id: e.target.value || undefined,
                        }))
                      }
                      placeholder="可选"
                      style={{ width: 200 }}
                    />
                  </Form.Item>
                  <Form.Item label="user_id">
                    <Input
                      data-testid="audit-filter-user-id"
                      value={auditFilter.user_id ?? ''}
                      onChange={(e) =>
                        setAuditFilter((f) => ({ ...f, user_id: e.target.value || undefined }))
                      }
                      placeholder="可选"
                      style={{ width: 200 }}
                    />
                  </Form.Item>
                  <Form.Item label="起始时间">
                    <Input
                      data-testid="audit-filter-occurred-after"
                      value={auditFilter.occurred_after ?? ''}
                      onChange={(e) =>
                        setAuditFilter((f) => ({
                          ...f,
                          occurred_after: e.target.value || undefined,
                        }))
                      }
                      placeholder="ISO 时间"
                      style={{ width: 200 }}
                    />
                  </Form.Item>
                  <Form.Item label="截止时间">
                    <Input
                      data-testid="audit-filter-occurred-before"
                      value={auditFilter.occurred_before ?? ''}
                      onChange={(e) =>
                        setAuditFilter((f) => ({
                          ...f,
                          occurred_before: e.target.value || undefined,
                        }))
                      }
                      placeholder="ISO 时间"
                      style={{ width: 200 }}
                    />
                  </Form.Item>
                  <Form.Item>
                    <Button
                      type="primary"
                      data-testid="audit-filter-submit"
                      onClick={() => void loadAuditLogs()}
                    >
                      查询
                    </Button>
                  </Form.Item>
                  <Form.Item>
                    {/* ⚠️ 按钮文案写明**范围**（当前筛选条件下的全部行） */}
                    <Button
                      data-testid="audit-export-csv"
                      loading={exporting}
                      onClick={() => void exportAuditCsv()}
                    >
                      导出 CSV（当前筛选条件下的全部行）
                    </Button>
                  </Form.Item>
                </Form>
                {exportNotice && (
                  <Alert
                    type="info"
                    showIcon
                    message={exportNotice}
                    data-testid="audit-export-notice"
                  />
                )}
                <Typography.Text type="secondary">
                  通用 audit 日志查询（导出上限 5000 行，超限会显式提示截断）.
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