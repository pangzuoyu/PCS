/**
 * SIM 物流列表页（SPEC §7.7.1 · P9B-3 · T6）。
 *
 * ## 数据流
 *
 * 页面**自己取数**（`streamApi.list`）—— 筛选要**带 query 参数重新请求后端**
 * （SPEC §7.7.1「四项均随选择重新请求后端，后端按 AND 组合过滤」）⇒
 * 前端过滤做不到这个口径（同一条记录在别的筛选下也得跟着变）。
 *
 * ## 列（SPEC §7.7.1）
 *
 * 名称（标识 · 首列）· 工况 · 相态 · 温度 · 压力 · 质量流量 · 状态 · 来源 · 操作
 *
 * ⚠️ **「引用 📎×N」列本批不渲染** —— 后端列表响应**不返回**该字段，口径也未定
 * （TODO-108）⇒ 画一列永远空着的东西比不画更糟。
 * ⚠️ **「物流号」列不画** —— 契约里**没有**物流号（`tag_number` 已随「物流没有
 * 位号」的裁决删除）⇒ 沿用 2026-10-19 的裁决：**首列用「名称」当标识**。
 * ⚠️ **只显示 `source`（4 值 · 录入通道）**，**不显示 `source_type`（13 值 ·
 * 产出方式）** —— 后者塞进一列会爆（TODO-105）。
 *
 * ## 行操作
 *
 * - 查看 → 详情页 `/sim/streams/:id`
 * - 校对 → **单条** `POST /streams/{id}/submit`（DRAFT → IN_APPROVAL）
 *   ⚠️ 与工具栏那条「批量提交校对」（⏳ P9B-3b）**不是同一件事**
 * - 变更 → `POST /streams/{id}/initiate-change`（CHECKED → CHANGE_PENDING）
 */
import { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, Button, Modal, Select, Space, Table, Tag, Typography } from 'antd';

import { NumericCell } from '../../components/common/NumericCell';
import { StateBadgeBoundary } from '../../components/common/StateBadgeBoundary';
import { streamApi, type StreamBatchSubmitResponse, type StreamListFilters } from '../../api/stream';
import { describePcsError } from '../../api/errors';
import { downloadCsv, toCsv } from '../../lib/csv';
import { PROJECT_ID } from '../../constants/env';
import {
  STREAM_CASE_TYPE_LABEL,
  STREAM_PHASE_LABEL,
  STREAM_SIGN_STATUS_VALUES,
  STREAM_SOURCE_LABEL,
  streamPhaseColor,
  streamPhaseLabel,
  type Stream,
} from '../../types/stream';

interface Props {
  /** 项目 id（默认取环境常量，与其它页面同口径）。 */
  projectId?: string;
}

export function StreamListPage({ projectId = PROJECT_ID }: Props): JSX.Element {
  const navigate = useNavigate();
  const [streams, setStreams] = useState<Stream[]>([]);
  const [filters, setFilters] = useState<StreamListFilters>({});
  const [loading, setLoading] = useState(false);
  const [listFailed, setListFailed] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  /** 行操作的错误（按 stream id）—— 不打挂整页。 */
  const [rowError, setRowError] = useState<{ id: string; text: string } | null>(null);
  /** 正在提交校对的行（禁用该行的按钮）。 */
  const [submittingId, setSubmittingId] = useState<string | null>(null);
  /** 行多选（批量提交校对的输入）。 */
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  /** 批量提交的结果摘要（成功 N / 失败 M）。 */
  const [batchResult, setBatchResult] = useState<StreamBatchSubmitResponse | null>(null);
  /** 批量提交**本身**失败（网络/超限/403）⇒ 顶部错误条。 */
  const [batchError, setBatchError] = useState<string | null>(null);
  /** 批量提交进行中（禁用按钮，防重复提交）。 */
  const [batchSubmitting, setBatchSubmitting] = useState(false);

  const load = useCallback(async (): Promise<void> => {
    setLoading(true);
    setErrorMsg(null);
    try {
      setStreams(await streamApi.list(projectId, filters));
      setListFailed(false);
    } catch (err) {
      setStreams([]);
      setListFailed(true);
      setErrorMsg(describePcsError(err, '加载物流列表失败'));
    } finally {
      setLoading(false);
    }
  }, [projectId, filters]);

  useEffect(() => {
    void load();
  }, [load]);

  /** 改一项筛选 ⇒ **重新请求后端**（AND 组合）。 */
  function setFilter<K extends keyof StreamListFilters>(key: K, value: StreamListFilters[K]): void {
    setFilters((prev) => {
      const next = { ...prev };
      if (value === undefined) delete next[key];
      else next[key] = value;
      return next;
    });
  }

  /** 行操作：单条提交校对（DRAFT → IN_APPROVAL）。 */
  async function submitForReview(id: string): Promise<void> {
    setRowError(null);
    setSubmittingId(id);
    try {
      await streamApi.submitForReview(id);
      // ⚠️ 重新拉列表（后端返回的**最新态**才是真相；响应体本身是裸 dict，
      //    契约里没有具名 schema ⇒ 不从它读状态）。
      await load();
    } catch (err) {
      // ⚠️ 失败 ⇒ **状态不变**（后端事务回滚）⇒ 徽章不动，只提示。
      setRowError({ id, text: describePcsError(err, '提交校对失败') });
    } finally {
      setSubmittingId(null);
    }
  }

  /** 工具栏：批量提交校对（一次请求 N 条 ⇒ 后端逐条处理、部分成功）。 */
  async function submitBatch(): Promise<void> {
    setBatchError(null);
    setBatchSubmitting(true);
    try {
      const result = await streamApi.batchSubmitForReview(selectedIds);
      setBatchResult(result);
      setSelectedIds([]);
      // ⚠️ 重新拉列表（后端返回的最新态才是真相；成功项的状态已变）
      await load();
    } catch (err) {
      // ⚠️ 207 不会进这里 ⇒ 走到这里的是**整批**失败（超限 / 403 / 网络）
      setBatchResult(null);
      setBatchError(describePcsError(err, '批量提交校对失败'));
    } finally {
      setBatchSubmitting(false);
    }
  }
  /** 行操作：发起变更（CHECKED → CHANGE_PENDING）。 */
  async function initiateChange(id: string): Promise<void> {
    setRowError(null);
    setSubmittingId(id);
    try {
      await streamApi.initiateChange(id);
      await load();
    } catch (err) {
      setRowError({ id, text: describePcsError(err, '发起变更失败') });
    } finally {
      setSubmittingId(null);
    }
  }

  /** 导出当前**筛选后**的行（CSV）。 */
  function exportCsv(): void {
    const headers = ['名称', '工况', '相态', '温度(°C)', '压力(MPaG)', '质量流量(kg/h)', '状态', '来源'];
    const rows = streams.map((s) => [
      s.stream_name,
      s.case_type ? STREAM_CASE_TYPE_LABEL[s.case_type] : '',
      s.phase ? streamPhaseLabel(s.phase) : '',
      s.temp ?? '',
      s.press ?? '',
      s.mass_flow ?? '',
      s.sign_status,
      s.source ? STREAM_SOURCE_LABEL[s.source] : '',
    ]);
    downloadCsv('streams.csv', toCsv(headers, rows));
  }

  const columns = [
      {
        // 首列是**标识**（2026-10-19 用户裁决：不删首列 —— 物流没有位号了）。
        title: '名称',
        dataIndex: 'stream_name',
        width: 180,
        render: (v: string) => <span data-testid="stream-name">{v}</span>,
      },
      {
        title: '工况',
        dataIndex: 'case_type',
        width: 90,
        render: (c: Stream['case_type']) =>
          c ? STREAM_CASE_TYPE_LABEL[c] ?? c : '—',
      },
      {
        title: '相态',
        dataIndex: 'phase',
        width: 90,
        render: (p: Stream['phase']) => (
          <Tag
            color={streamPhaseColor(p)}
            data-testid="stream-phase"
            data-phase={p ?? ''}
          >
            {streamPhaseLabel(p)}
          </Tag>
        ),
      },
      {
        title: '温度 (°C)',
        dataIndex: 'temp',
        width: 110,
        render: (v: number) => <NumericCell value={v} precision={1} precisionType="decimal" unit="°C" />,
      },
      {
        title: '压力 (MPaG)',
        dataIndex: 'press',
        width: 110,
        render: (v: number) => <NumericCell value={v} precision={2} precisionType="decimal" unit="MPaG" />,
      },
      {
        title: '流量 (kg/h)',
        dataIndex: 'mass_flow',
        width: 120,
        render: (v: number) => <NumericCell value={v} precision={0} precisionType="decimal" unit="kg/h" />,
      },
      {
        title: '状态',
        dataIndex: 'sign_status',
        width: 110,
        // ⚠️ 未知状态由 `StateBadgeBoundary` 兜底（**不**打挂整表）。
        render: (s: Stream['sign_status']) => <StateBadgeBoundary status={s} module="SIM" />,
      },
      {
        // ⚠️ 只显示 `source`（4 值 · 录入通道）—— 不是 `source_type`（13 值）。
        title: '来源',
        dataIndex: 'source',
        width: 110,
        render: (s: Stream['source']) => (s ? STREAM_SOURCE_LABEL[s] ?? s : '—'),
      },
      {
        title: '操作',
        key: 'actions',
        width: 220,
        render: (_: unknown, row: Stream) => (
          <Space size={4}>
            <Button
              size="small"
              data-testid={`stream-view-${row.stream_id}`}
              onClick={(e) => {
                // ⚠️ 整行可点 ⇒ 行内按钮必须**阻止冒泡**（否则点「校对」会跳详情）
                e.stopPropagation();
                navigate(`/sim/streams/${row.stream_id}`);
              }}
            >
              查看
            </Button>
            <Button
              size="small"
              data-testid={`stream-submit-${row.stream_id}`}
              loading={submittingId === row.stream_id}
              onClick={(e) => {
                e.stopPropagation();
                void submitForReview(row.stream_id);
              }}
            >
              校对
            </Button>
            <Button
              size="small"
              data-testid={`stream-change-${row.stream_id}`}
              loading={submittingId === row.stream_id}
              onClick={(e) => {
                e.stopPropagation();
                void initiateChange(row.stream_id);
              }}
            >
              变更
            </Button>
          </Space>
        ),
      },
  ];

  return (
    <div data-testid="stream-list-page">
      <Typography.Title level={3}>SIM 物流列表</Typography.Title>

      {/* 工具栏：导入 / 新建物流 / 导出 / **批量提交校对**（P9B-3b 已落地，
          SPEC §7.7.1 该项 ⏳ → ✅）*/}
      <Space style={{ marginBottom: 12 }} wrap>
        <Button data-testid="stream-import" onClick={() => navigate('/sim/import')}>
          导入
        </Button>
        <Button data-testid="stream-create" onClick={() => navigate('/sim/streams/new')}>
          新建物流
        </Button>
        <Button data-testid="stream-export" onClick={exportCsv}>
          导出
        </Button>
        <Button
          data-testid="stream-batch-submit"
          onClick={submitBatch}
          disabled={selectedIds.length === 0 || batchSubmitting}
        >
          批量提交校对
        </Button>
      </Space>

      {/* 筛选：工况 / 相态 / 状态 / 来源 —— 随选择**重新请求后端**（AND 组合）*/}
      <Space style={{ marginBottom: 12 }} wrap>
        <span data-testid="stream-filter-case-type">
          <Select
            allowClear
            placeholder="工况"
            style={{ width: 120 }}
          value={filters.case_type}
          options={Object.entries(STREAM_CASE_TYPE_LABEL).map(([value, label]) => ({ value, label }))}
            onChange={(v) => setFilter('case_type', v)}
          />
        </span>
        <span data-testid="stream-filter-phase">
          <Select
            allowClear
            placeholder="相态"
            style={{ width: 120 }}
          value={filters.phase}
          options={Object.entries(STREAM_PHASE_LABEL).map(([value, label]) => ({ value, label }))}
            onChange={(v) => setFilter('phase', v)}
          />
        </span>
        <span data-testid="stream-filter-sign-status">
          <Select
            allowClear
            placeholder="状态"
            style={{ width: 160 }}
          value={filters.sign_status}
          options={STREAM_SIGN_STATUS_VALUES.map((value) => ({ value, label: value }))}
            onChange={(v) => setFilter('sign_status', v)}
          />
        </span>
        <span data-testid="stream-filter-source">
          <Select
            allowClear
            placeholder="来源"
            style={{ width: 140 }}
          value={filters.source}
          options={Object.entries(STREAM_SOURCE_LABEL).map(([value, label]) => ({ value, label }))}
            onChange={(v) => setFilter('source', v)}
          />
        </span>
      </Space>

      {errorMsg && (
        <Alert
          type="error"
          showIcon
          message={errorMsg}
          data-testid="stream-list-error"
          style={{ marginBottom: 16 }}
          // ⚠️ 列表加载失败 ⇒ 不可关闭（关掉 = 假装没有数据）
          closable={!listFailed}
          onClose={() => setErrorMsg(null)}
        />
      )}
      {rowError && (
        <Alert
          type="error"
          showIcon
          message={rowError.text}
          data-testid="stream-row-error"
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setRowError(null)}
        />
      )}

      <Table<Stream>
        rowKey="stream_id"
        rowSelection={{
          selectedRowKeys: selectedIds,
          onChange: (keys) => setSelectedIds(keys.map(String)),
        }}
        columns={columns}
        dataSource={listFailed ? [] : streams}
        loading={loading}
        pagination={false}
        locale={{ emptyText: '无物流' }}
        onRow={(record) => ({
          // ⚠️ 整行可点 ⇒ 进详情（与「查看」按钮同一条路）。
          'data-testid': 'stream-row',
          'data-stream-id': record.stream_id,
          'data-status': record.sign_status,
          onClick: () => navigate(`/sim/streams/${record.stream_id}`),
        })}
      />

      {batchResult && (
        <Modal
          open
          title="批量提交校对结果"
          onCancel={() => setBatchResult(null)}
          footer={<Button onClick={() => setBatchResult(null)}>关闭</Button>}
        >
          <div data-testid="stream-batch-summary">
            成功 {batchResult.succeeded.length} · 失败 {batchResult.failed.length}
            {batchResult.dry_run ? '（预演：未改状态）' : ''}
          </div>
          {batchResult.warning && (
            <Alert
              type="warning"
              showIcon
              message={batchResult.warning}
              data-testid="stream-batch-warning"
              style={{ marginBottom: 8 }}
            />
          )}
          {batchResult.failed.length > 0 && (
            <>
              <ul data-testid="stream-batch-failures">
                {batchResult.failed.map((f) => (
                  <li key={f.stream_id} data-testid={`stream-batch-failure-${f.stream_id}`}>
                    {f.stream_id}：{f.reason}
                    {f.detail ? `（${f.detail}）` : ''}
                  </li>
                ))}
              </ul>
              {/* ⚠️ **关闭提示**（委员会 2026-11-03 · D8 裁决的「本批必做」）：
                  TODO-116（一键重试失败项）本批**不做** ⇒ 失败清单关闭即丢
                  （`batchResult` 是组件局部 state）⇒ 至少要让用户**知道**
                  这个缺口，而不是默默丢数据。成本 = 一行文案。 */}
              <Typography.Text
                type="secondary"
                data-testid="stream-batch-close-hint"
              >
                ⚠️ 关闭后失败清单将不再显示；如需重试失败项，请先记录它们。
              </Typography.Text>
            </>
          )}
        </Modal>
      )}

      {batchError && (
        <Alert
          type="error"
          showIcon
          message={batchError}
          data-testid="stream-batch-error"
          style={{ marginBottom: 16 }}
          closable
          onClose={() => setBatchError(null)}
        />
      )}
    </div>
  );
}

export default StreamListPage;
