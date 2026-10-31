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
import { describePcsError } from '../../api/errors';
import { downloadCsv, toCsv } from '../../lib/csv';
import { useAuth } from '../../store/auth';
import type { StrictColumns } from '../../types/strictColumns';

type TabKey = 'config-audit' | 'equipment-deletion' | 'audit-logs';

/** 导出上限（RF-11）：超限**显式提示截断**。 */
const EXPORT_LIMIT = 5000;
/** 导出时每页的行数。 */
const EXPORT_PAGE_SIZE = 200;

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
  // ⚠️ **列表加载失败**与**导出失败**分开：
  //    列表失败 ⇒ 提示**不可关闭** + **不渲染空表**（关掉就退化成「共 0 条」
  //    的空表 ⇒ 读成「系统没有审计日志」⇒ 真相可能是「你没权限」，RF-12）；
  //    导出失败 ⇒ 只影响导出 ⇒ 提示**可关闭**，列表照常显示。
  const [listError, setListError] = useState<string | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);

  // CONFIG tab 过滤
  const [assetId, setAssetId] = useState<number | undefined>(undefined);
  // equipment-deletion tab 过滤
  const [projectId, setProjectId] = useState<string | undefined>(undefined);
  // ⚠️ 通用 audit tab 的**筛选条件**（P9B-2）—— 直接映射 api 层已有的参数名
  const [auditFilter, setAuditFilter] = useState<ListAuditLogsParams>({});
  // ⚠️ **已应用**的筛选条件（点「查询」时冻结）—— 导出必须用**它**，
  //    不是输入框的实时值 ⇒ 否则 CSV 与屏幕上看到的行**对不上**。
  const [appliedFilter, setAppliedFilter] = useState<ListAuditLogsParams>({});
  const [exporting, setExporting] = useState(false);
  const [exportNotice, setExportNotice] = useState<string | null>(null);
  // ⚠️ **服务端分页**（P9B-2 · 延后的 minor）：此前 `limit: 50` 不带 offset +
  //    antd **前端**分页 ⇒ 表格**永远只有 50 行**，标题却写「共 N 条」⇒
  //    三处数字互相打架（用户以为看到的就是全部）。
  //    ⇒ 页码 / 每页行数 / offset 全部由前端算，**页数由后端的 `total` 决定**。
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);

  async function loadConfigAudit(offset: number): Promise<void> {
    setListError(null);
    setLoading(true);
    try {
      const r = await auditApi.listConfigAudit({
        ...(assetId !== undefined ? { asset_id: assetId } : {}),
        limit: pageSize,
        offset,
      });
      setItems(r.items);
      setTotal(r.total);
    } catch (err: unknown) {
      setListError(describePcsError(err, 'CONFIG audit 查询失败'));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  async function loadEquipmentDeletionAudit(offset: number): Promise<void> {
    if (!projectId) {
      setListError('project_id 必填 (非 SYSTEM_ADMIN 必须传)');
      return;
    }
    setListError(null);
    setLoading(true);
    try {
      const r = await auditApi.listEquipmentDeletionAudit({
        project_id: projectId,
        limit: pageSize,
        offset,
      });
      setItems(r.items as unknown as AuditLogItem[]);
      setTotal(r.total);
    } catch (err: unknown) {
      setListError(describePcsError(err, '设备删除 audit 查询失败'));
      setItems([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }

  async function loadAuditLogs(
    offset: number,
    filter: ListAuditLogsParams = appliedFilter,
  ): Promise<void> {
    setListError(null);
    setLoading(true);
    // ⚠️ 本次查询用的筛选条件 = **已应用**的筛选条件（冻结）——
    //    ⚠️ 评审 #10：**冻结只发生在点「查询」时**（那里显式 setAppliedFilter +
    //    把新条件传进来）。默认读 state ⇒ 翻页（effect 调本函数）永远用
    //    上次应用的条件 ⇒ 不会把「改了没查」的条件**偷换**进第 2 页。
    try {
      const r = await auditApi.listAuditLogs({
        ...filter,
        limit: pageSize,
        offset,
      });
      setItems(r.items);
      setTotal(r.total);
    } catch (err: unknown) {
      setListError(describePcsError(err, 'audit-logs 查询失败'));
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
    setExportError(null);
    try {
      const collected: AuditLogItem[] = [];
      let offset = 0;
      /** 后端说的**结果集总数**（最后一页的 `total`）。 */
      let lastTotal: number | null = null;
      // ⚠️ 最多 25 页 × 200 行 = 5000 行（上限）
      while (offset < EXPORT_LIMIT) {
        const r = await auditApi.listAuditLogs({
          ...appliedFilter,
          limit: EXPORT_PAGE_SIZE,
          offset,
        });
        collected.push(...r.items);
        lastTotal = r.total;
        if (collected.length >= EXPORT_LIMIT) break;
        if (r.items.length < EXPORT_PAGE_SIZE) break;
        offset += EXPORT_PAGE_SIZE;
      }
      // ⚠️ **与后端 `total` 核对**（RF-11）：排序是 `occurred_at DESC, audit_id
      //    DESC`（**有**决胜列，P9B-2 评审 #8 已钉测试）⇒ 分页稳定；这个核对
      //    防的是**导出循环期间新行写入**（25 页拉取窗口内 total 漂移）⇒ 行数
      //    对不上就**明说**（用户据此判断能不能用这份文件当证据）。
      const total = lastTotal;
      // ⚠️ **截断**的判据是「结果集**比上限还大**」，不是「刚好导满了上限」——
      //    恰好 5000 行 ⇒ **没截断** ⇒ 误报「已截断」会让用户以为少了数据。
      const truncatedByLimit = total !== null && total > EXPORT_LIMIT;
      const mismatch = total !== null && collected.length !== total;
      const rows = collected.slice(0, EXPORT_LIMIT).map((i) => [
        // ⚠️ **audit_id（LogID）必须在第一列** —— 同一秒的多条记录靠时间戳分不开
        //    ⇒ 没有 LogID 就**无法回指**原审计行（合规场景拿这份 CSV 当证据）。
        i.audit_id,
        i.occurred_at,
        i.action,
        i.resource_type ?? '',
        i.resource_id ?? '',
        i.user_id ?? '',
        // ⚠️ `detail_json` 是 dict ⇒ 序列化成文本（导出的 CSV 是纯文本）
        i.detail_json ? JSON.stringify(i.detail_json) : '',
      ]);
      const csv = toCsv(
        [
          'audit_id',
          'occurred_at',
          'action',
          'resource_type',
          'resource_id',
          'user_id',
          'detail_json',
        ],
        rows,
      );
      downloadCsv('audit-logs.csv', csv);
      setExportNotice(
        truncatedByLimit
          ? `已导出前 ${EXPORT_LIMIT} 行（结果集共 ${total} 行，超过上限，已截断）`
          : mismatch
            ? `已导出 ${rows.length} 行，但与结果集总数（${lastTotal}）「不一致」 —— 可能重复 / 漏行，请核对后再当证据用`
            : `已导出 ${rows.length} 行（当前筛选条件下的全部结果）`,
      );
    } catch (err: unknown) {
      setExportError(describePcsError(err, '导出失败'));
    } finally {
      setExporting(false);
    }
  }

  /**
   * 回到**第 1 页**重新查。
   *
   * ⚠️ 当前已经在第 1 页 ⇒ 直接查（否则 `setPage(1)` 不产生新状态 ⇒ effect 不触发
   *    ⇒ 「查询」按钮会**毫无反应**）；不在第 1 页 ⇒ 只改页码 ⇒ 让 effect 去查
   *    ⇒ **不重复请求**。
   */
  function reloadFromFirstPage(load: (offset: number) => Promise<void>): void {
    if (page === 1) void load(0);
    else setPage(1);
  }

  useEffect(() => {
    // ⚠️ **服务端分页** ⇒ offset 由 `page` 算；页码变化 ⇒ 重拉。
    const offset = (page - 1) * pageSize;
    if (activeTab === 'config-audit') void loadConfigAudit(offset);
    if (activeTab === 'equipment-deletion') void loadEquipmentDeletionAudit(offset);
    if (activeTab === 'audit-logs') void loadAuditLogs(offset);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [activeTab, assetId, projectId, page, pageSize]);

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

      {/* ⚠️ **列表加载失败 ⇒ 不可关闭 + 不渲染空表**（见 `listError` 注释） */}
      {listError && (
        <Alert
          type="error"
          showIcon
          message={listError}
          data-testid="audit-list-error"
          style={{ marginBottom: 16 }}
        />
      )}
      {exportError && (
        <Alert
          type="error"
          showIcon
          message={exportError}
          data-testid="audit-export-error"
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setExportError(null)}
        />
      )}

      <Tabs
        activeKey={activeTab}
        onChange={(k) => {
          // ⚠️ 换 tab ⇒ 回到第 1 页（否则带着上一个 tab 的页码去查另一个结果集）
          setPage(1);
          setActiveTab(k as TabKey);
        }}
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
                    <Button
                      type="primary"
                      onClick={() => reloadFromFirstPage(loadConfigAudit)}
                    >
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
                      onClick={() => reloadFromFirstPage(loadEquipmentDeletionAudit)}
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
                      onClick={() => {
                        // ⚠️ 评审 #10：**冻结发生在这里且只在这里** ——
                        //    直查路径显式传新条件（setState 不更新当帧闭包），
                        //    翻页路径由 effect 读已更新的 state。
                        setAppliedFilter(auditFilter);
                        reloadFromFirstPage((offset) =>
                          loadAuditLogs(offset, auditFilter),
                        );
                      }}
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
                {/* ⚠️ 输入框改了条件但**没点查询** ⇒ 导出仍按**已应用**的条件
                    ⇒ 不说清楚 ⇒ 用户以为「填了没生效」。 */}
                {JSON.stringify(auditFilter) !== JSON.stringify(appliedFilter) && (
                  <Alert
                    type="warning"
                    showIcon
                    data-testid="audit-filter-pending-hint"
                    message="筛选条件改过但还没点「查询」—— 表格与导出都仍按「上次已应用」的条件。"
                    style={{ marginBottom: 16 }}
                  />
                )}
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

      {/* ⚠️ **列表加载失败 ⇒ 不渲染表**（空表会被读成「没有审计日志」） */}
      {!listError && (
      <Card title={`结果 (共 ${total} 条)`}>
        <Table<AuditLogItem>
          rowKey="audit_id"
          dataSource={items}
          columns={columns}
          loading={loading}
          size="small"
          // ⚠️ **服务端分页**：`total` 来自**后端** ⇒ 页数是真实结果集页数；
          //    `onChange` 只改状态 ⇒ 由上面的 effect 重新拉（不重复请求）。
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            pageSizeOptions: ['50', '100', '200'],
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
        />
      </Card>
      )}
    </div>
  );
}

export default AuditLogPage;