/**
 * ReportReviewQueuePage —— **「待我审核」队列**（P10-I · T1 · TODO-197）。
 *
 * ## 它解的是哪个洞
 *
 * 「创建 ⇒ 交给审核者 ⇒ 审核者发布」这条链，**在 UI 上断在第二环**：
 * 创建人发布 ⇒ **403 自审**；审核者在列表页找草稿 ⇒ **看不见**（草稿只有创建人可见）
 * ⇒ ⇒ ⇒ 「发布」按钮对所有角色 **100% 死** ⇒ ⇒ ⇒ SPEC §3.2.2 在 UI 上不成立。
 *
 * ## 三个约束（人裁 2026-11-23）

 * | # | 约束 | 这里怎么落 |
 * |---|---|---|
 * | 1 | 队列是**只读视图**，**不能进编辑器** | 名称列**不是链接**；页面上**没有**进编辑器的入口 |
 * | 2 | 过滤条件与可见性**分离** | 队列走**独立端点** `/report-builder/definitions/pending-review` |
 * | 3 | ⚠️ **2026-11-24 · P10-J · T2 追加了「打回」**（TODO-197b）| 队列现在有「发布 / 打回 / 忽略」三个动作；「打回」**状态不变**（仍是 DRAFT）⇒ ⇒ ⇒ 只加「被退回」标记 |
 *
 * ## 为什么「发布」按钮只在**这个页**
 *
 * 列表页看不见别人的草稿 ⇒ ⇒ 那里的「发布」对审核者是**死按钮**
 * ⇒ ⇒ ⇒ 放队列页才是唯一有效位置（人裁 ②）。
 */
import { useCallback, useEffect, useMemo, useState } from 'react';
import type { JSX } from 'react';
import {
  Alert,
  Button,
  Input,
  Modal,
  Space,
  Spin,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
} from 'antd';
import { ReloadOutlined } from '@ant-design/icons';

import { PageHeader } from '../../components/common/PageHeader';
import { errorMessage, reportBuilderApi } from '../../api/reportBuilder';
import type { ReportDefinitionReviewItem } from '../../api/reportBuilder';
import {
  clearIgnored,
  isIgnored,
  markIgnored,
  readIgnored,
  writeIgnored,
} from './reviewIgnored';
import type { IgnoredMap } from './reviewIgnored';

/** 从 axios 错误里取状态码 + 错误码（`errorMessage` 只给文案）。 */
function errorParts(err: unknown): { status?: number; code?: string; message: string } {
  const e = err as {
    response?: { status?: number; data?: { code?: string; message?: string } };
  };
  return {
    status: e?.response?.status,
    code: e?.response?.data?.code,
    message: errorMessage(err),
  };
}

/** 按错误码给一句**人话**（文案不自己编 ⇒ 后端 message 才是真相）。 */
function hintFor(code: string | undefined, status: number | undefined): string | null {
  switch (code) {
    case 'REPORT_DEFINITION_SELF_REVIEW_FORBIDDEN':
      return '不能发布自己创建的报表定义 —— 发布须由他人审核。';
    case 'REPORT_DEFINITION_NOT_SHAREABLE':
      return '该定义仅创建人可见，不能由他人发布。';
    case 'REPORT_DEFINITION_ROLE_REQUIRED':
      return '需要审核角色（REVIEWER / APPROVER / SYSTEM_ADMIN）才能查看待审队列。';
    case 'REPORT_DEFINITION_NOT_FOUND':
      return '该定义不存在，或你没有该项目的权限。';
    case 'REPORT_DEFINITION_STATE':
      return '该定义已发布过（重复发布不是静默成功）。';
    case 'REPORT_DEFINITION_ALREADY_REJECTED':
      return '这条已经被打回过了 —— 先等创建人改完再交审。';
    case 'REPORT_DEFINITION_REJECT_REASON_REQUIRED':
      return '打回必须写原因（创建人要看得懂要改什么）。';
    default:
      return status === 404 ? '该定义不存在，或你没有该项目的权限。' : null;
  }
}

export function ReportReviewQueuePage(): JSX.Element {
  const [rows, setRows] = useState<ReportDefinitionReviewItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [loadError, setLoadError] = useState<{ message: string; hint: string | null } | null>(null);
  const [ignored, setIgnored] = useState<IgnoredMap>({});
  const [showIgnored, setShowIgnored] = useState(false);
  const [acting, setActing] = useState<string | null>(null);
  const [actionError, setActionError] = useState<{ message: string; hint: string | null } | null>(null);
  // ⚠️ **「打回」需要原因**（P10-J · T2 · TODO-197b）⇒ ⇒ ⇒ 创建人要看得懂要改什么
  // ⇒ ⇒ ⇒ 空原因 = 无信息 ⇒ ⇒ ⇒ 弹窗里必须填。
  const [rejecting, setRejecting] = useState<ReportDefinitionReviewItem | null>(null);
  const [rejectReason, setRejectReason] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setLoadError(null);
    try {
      const data = await reportBuilderApi.pendingReview();
      setRows(data.items);
    } catch (err) {
      const parts = errorParts(err);
      setLoadError({ message: parts.message, hint: hintFor(parts.code, parts.status) });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { void load(); }, [load]);
  useEffect(() => { setIgnored(readIgnored()); }, []);

  const onPublish = useCallback(async (row: ReportDefinitionReviewItem) => {
    setActing(row.def_id);
    setActionError(null);
    try {
      await reportBuilderApi.publish(row.def_id);
      await load();
    } catch (err) {
      const parts = errorParts(err);
      setActionError({ message: parts.message, hint: hintFor(parts.code, parts.status) });
    } finally {
      setActing(null);
    }
  }, [load]);

  /** 「打回」⇒ ⇒ ⇒ 状态**不变**（仍是 DRAFT）⇒ ⇒ ⇒ 后端只加「被退回」标记。 */
  const onReject = useCallback(async () => {
    if (!rejecting) return;
    const row = rejecting;
    setActing(row.def_id);
    setActionError(null);
    try {
      await reportBuilderApi.reject(row.def_id, rejectReason.trim());
      setRejecting(null);
      setRejectReason('');
      await load();
    } catch (err) {
      const parts = errorParts(err);
      setActionError({ message: parts.message, hint: hintFor(parts.code, parts.status) });
    } finally {
      setActing(null);
    }
  }, [load, rejecting, rejectReason]);

  const onIgnore = useCallback((row: ReportDefinitionReviewItem) => {
    const next = markIgnored(ignored, row.def_id, row.updated_at);
    setIgnored(next);
    writeIgnored(next);
  }, [ignored]);

  const onUnignore = useCallback((row: ReportDefinitionReviewItem) => {
    const next = clearIgnored(ignored, row.def_id);
    setIgnored(next);
    writeIgnored(next);
  }, [ignored]);

  /** 可见行 = 队列行（**后端说了算**）− 已忽略的（除非「显示已忽略」打开）。 */
  const visible = useMemo(
    () => rows.filter((r) => showIgnored || !isIgnored(ignored, r.def_id, r.updated_at)),
    [rows, ignored, showIgnored],
  );

  const columns = useMemo(() => [
    {
      // ⚠️ **不是链接** —— 队列是只读视图（人裁约束 1）⇒ ⇒ **不能进编辑器**
      title: '名称',
      dataIndex: 'name',
      key: 'name',
    },
    { title: '分类', dataIndex: 'category', key: 'category', width: 110 },
    {
      title: '创建人',
      dataIndex: 'created_by',
      key: 'created_by',
      width: 150,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '作用域',
      dataIndex: 'project_id',
      key: 'project_id',
      width: 160,
      // ⚠️ `project_id` 为空 = 公司级模板（与后端 `visible_clause` 同口径）
      render: (v: string | null) => (v
        ? <Typography.Text code>{v}</Typography.Text>
        : <Tag color="blue">公司级</Tag>),
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 190,
      render: (v: string | null) => v ?? '—',
    },
    {
      title: '',
      key: 'actions',
      width: 190,
      render: (_: unknown, row: ReportDefinitionReviewItem) => {
        const ignoredRow = isIgnored(ignored, row.def_id, row.updated_at);
        return (
          <Space size="small">
            <Button
              size="small"
              type="primary"
              loading={acting === row.def_id}
              onClick={() => void onPublish(row)}
            >
              发布
            </Button>
            <Tooltip title="退回给创建人修改（**状态不变** · 他改完再交审）">
              <Button size="small" onClick={() => {
                setRejecting(row);
                setRejectReason('');
              }}>
                打回
              </Button>
            </Tooltip>
            {ignoredRow
              ? (
                <Tooltip title="取消忽略：它会重新出现在队列里">
                  <Button size="small" onClick={() => onUnignore(row)}>
                    取消忽略
                  </Button>
                </Tooltip>
              )
              : (
                <Tooltip title="暂时不看这条（记在本机浏览器里）">
                  <Button size="small" onClick={() => onIgnore(row)}>
                    忽略
                  </Button>
                </Tooltip>
              )}
          </Space>
        );
      },
    },
  ], [acting, ignored, onIgnore, onPublish, onUnignore]);

  /** 权限类错误 ⇒ ⇒ **不渲染空表**（空表会被读成「没有待审的草稿」）。 */
  const denied = loadError?.hint?.includes('审核角色') ?? false;

  return (
    <div className="page">
      <PageHeader
        title="待我审核"
        actions={
          <Space>
            <Space size="small">
              <Switch
                size="small"
                checked={showIgnored}
                onChange={setShowIgnored}
              />
              <span>显示已忽略</span>
            </Space>
            <Button icon={<ReloadOutlined />} onClick={() => void load()}>
              刷新
            </Button>
          </Space>
        }
      />

      {loadError && (
        <Alert type="error" showIcon message={loadError.message}
          description={loadError.hint ?? undefined}
          style={{ marginBottom: 16 }} />
      )}

      <Modal
        open={rejecting !== null}
        title="打回这条草稿"
        okText="打回"
        cancelText="取消"
        okButtonProps={{
          disabled: rejectReason.trim().length === 0,
          loading: acting !== null,
        }}
        onCancel={() => setRejecting(null)}
        onOk={() => void onReject()}
      >
        <Typography.Paragraph type="secondary">
          创建人会收到一条通知，并在这里看到「被退回」标记 ⇒ ⇒ ⇒ 请写清**要改什么**。
        </Typography.Paragraph>
        <Input.TextArea
          data-testid="reject-reason-input"
          rows={4}
          maxLength={2000}
          value={rejectReason}
          placeholder="例：「热负荷」字段选了不存在的列 —— 请改用 HEAT_LIST。"
          onChange={(e) => setRejectReason(e.target.value)}
        />
      </Modal>

      {actionError && (
        <Alert type="error" showIcon message={actionError.message}
          description={actionError.hint ?? undefined}
          style={{ marginBottom: 16 }} />
      )}

      <Spin spinning={loading}>
        {denied
          ? <div />
          : (
            <Table<ReportDefinitionReviewItem>
              rowKey="def_id"
              columns={columns}
              dataSource={visible}
              pagination={{ pageSize: 20, showSizeChanger: true }}
              locale={{ emptyText: '没有待审的报表定义。' }}
            />
          )}
      </Spin>
    </div>
  );
}
