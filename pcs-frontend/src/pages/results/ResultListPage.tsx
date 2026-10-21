/**
 * ResultListPage —— 通用结果列表页（P9B-1 · SPEC §6.21）。
 *
 * **一个页面 + 6 个模块描述符** ⇒ 6 张结果表的差异（路径 / 主键 / 字段）
 * 全在 `resultModules.ts` 里，**页面不硬编码任何字段**。
 *
 * ## 三条纪律
 *
 * 1. **编辑按钮在渲染时就禁用**（RF-7）：`sign_status` 不在
 *    `DRAFT` / `CHANGE_PENDING` 的行**点都点不动** —— 否则用户进了编辑态
 *    才发现不能改。
 * 2. **保存后就地更新本地 state**（RF-1 + 补充 2）：**不重拉整个列表**
 *    （浪费请求，还会让滚动位置与分页跳变）。
 * 3. **禁用原因要分类**（RF-12）：「状态不可编辑」与「无基线（联系管理员）」
 *    是**两回事**，混同会让用户找错人。
 */
import { useEffect, useState } from 'react';
import { Button, Table, Tooltip } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import { HashBadge } from '../../components/common/HashBadge';
import { StateBadge } from '../../components/common/StateBadge';
import { NumericCell } from '../../components/common/NumericCell';
import { recordsApi } from '../../api/records';
import { useEditBaseline, isRowEditable } from '../../hooks/useEditBaseline';
import { PROJECT_ID } from '../../constants/env';
import { ResultEditDrawer } from './ResultEditDrawer';
import type { CommonResultRow, ResultModule } from './resultModules';

/** 行 = 公共字段 + 该模块自己的字段（主键名逐模块不同 ⇒ 只能动态取）。 */
type ResultRow = CommonResultRow & Record<string, unknown>;

interface Props {
  module: ResultModule;
}

/**
 * 每行的 [编辑] 按钮 —— **单独一个组件**。
 *
 * ⚠️ **必须**是独立组件：基线 hook 不能在 `map()` 里调（React 规则）。
 */
function ResultEditButton({
  row,
  onEdit,
}: {
  row: ResultRow;
  onEdit: (row: ResultRow) => void;
}): JSX.Element {
  const baseline = useEditBaseline({
    record_hash: row.record_hash,
    updated_at: row.updated_at,
    canEdit: isRowEditable(row.sign_status),
  });

  const reason =
    baseline.reason === 'no-permission'
      ? `当前状态 ${row.sign_status ?? '未知'} 不可编辑`
      : baseline.reason === 'no-baseline'
        ? '该记录缺少并发校验基线，无法安全编辑，请联系管理员'
        : undefined;

  return (
    <Tooltip title={reason}>
      {/* ⚠️ **必须套一层 `<span>`**：antd 的 Tooltip 挂在**禁用**按钮上
       * **不会弹出**（禁用元素不派发鼠标事件）⇒ 用户看不到「为什么不能编辑」
       * ⇒ RF-12 的「禁用原因可区分」就白做了。 */}
      <span>
        <Button
          size="small"
          disabled={baseline.disabled}
          data-testid="result-edit-button"
          onClick={() => onEdit(row)}
        >
          编辑
        </Button>
      </span>
    </Tooltip>
  );
}

export function ResultListPage({ module }: Props): JSX.Element {
  const [records, setRecords] = useState<ResultRow[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [loading, setLoading] = useState(false);
  const [editing, setEditing] = useState<ResultRow | null>(null);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    // ⚠️ 换模块时**先清空**旧行：否则会短暂渲染「上一模块的行 + 本模块的
    // 主键名」⇒ 主键取不到 ⇒ React 重复 key 警告 + 表格显示错模块的数据。
    setRecords([]);
    void recordsApi
      .list<ResultRow>(module.base, {
        project_id: PROJECT_ID,
        limit: pageSize,
        offset: (page - 1) * pageSize,
      })
      .then((res) => {
        if (cancelled) return;
        setRecords(res.items ?? []);
        setTotal(res.total ?? 0);
      })
      .catch(() => {
        if (!cancelled) {
          setRecords([]);
          setTotal(0);
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [module.base, page, pageSize]);

  // ⚠️ 保存成功后**就地更新**本地 state（不重拉列表）：只改 `record_hash`
  // ⇒ 下一次保存带的是**新**基线（RF-1）。
  function onSaved(updated: { record_hash: string }): void {
    setRecords((prev) =>
      prev.map((r) =>
        String(r[module.pk]) === String(editing?.[module.pk])
          ? { ...r, record_hash: updated.record_hash }
          : r,
      ),
    );
  }

  const columns: ColumnsType<ResultRow> = module.columns.map((field) => ({
    title: field.label,
    dataIndex: field.key,
    key: field.key,
    render: (value: unknown) => {
      if (field.key === 'record_hash') {
        return value ? <HashBadge hash={String(value)} /> : '—';
      }
      if (field.key === 'sign_status') {
        // ⚠️ `StateBadge` 的 `module` 省略 ⇒ 按 CONFIG（9 态全集）处理。
        return value ? <StateBadge status={value as never} /> : '—';
      }
      if (field.kind === 'number') {
        return (
          <NumericCell
            value={typeof value === 'number' ? value : null}
            unit={field.unit}
            precision={field.precision}
          />
        );
      }
      return value === undefined || value === null || value === '' ? '—' : String(value);
    },
  }));

  columns.push({
    title: '操作',
    key: '__actions',
    render: (_: unknown, row: ResultRow) => (
      <ResultEditButton row={row} onEdit={setEditing} />
    ),
  });

  return (
    <div data-testid="result-list-page" data-module={module.recordType}>
      <PageHeader title={module.title} actions={<span />} />
      <Table<ResultRow>
        // ⚠️ 主键取不到时**用行号兜底**（不产生重复 key）：
        // 正常路径下每个模块的行都带自己的主键；取不到只可能是「状态里
        // 混进了别的模块的行」（见 routeWrappers 的 `key` 注释）。
        rowKey={(row, index) => String(row[module.pk] ?? `row-${index}`)}
        columns={columns}
        dataSource={records}
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: page,
          pageSize,
          total,
          showSizeChanger: true,
          onChange: (p, ps) => {
            setPage(p);
            setPageSize(ps);
          },
        }}
      />
      {editing && (
        <ResultEditDrawer
          open
          module={module}
          record={editing}
          onClose={() => setEditing(null)}
          onSaved={onSaved}
        />
      )}
    </div>
  );
}
