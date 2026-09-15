/**
 * InputChecklistPanel — 项目输入清单面板（P45-1-7 / Task 12，升级版）。
 *
 * SPEC §6.8 + plan P45-1-7：
 * - 顶部统计：完成 N/Total + 环形进度 + 分类计数
 *   (REQUIRED/CONDITIONAL/OPTIONAL) + 假设 + 未验证
 * - 列表列：模块 / 输入项 / 分类 / 当前值（NumericCell 等宽）/ 来源 /
 *   状态 / 核验人 / 操作（详情联动）
 * - 筛选：按状态、模块、分类（Select 下拉）
 * - 假设数据清单：可展开 Collapse，列出 ASSUMED 项及理由
 *
 * Props：projectId（保留）+ onItemClick?（新增联动 hook）
 * 数据源：复用 checklistApi（list + completeness）
 */
import { useEffect, useMemo, useState } from 'react';
import { Card, Collapse, List, Progress, Select, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { checklistApi } from '../../api/sprint1';
import { NumericCell } from './NumericCell';
import { StateBadge } from './StateBadge';
import type {
  ChecklistCompleteness,
  ChecklistItem,
  ChecklistStatus,
} from '../../types/checklist';

interface Props {
  projectId: string;
  onItemClick?: (item: ChecklistItem) => void;
}

const STATUS_LABEL: Record<ChecklistStatus, string> = {
  NOT_STARTED: '未开始',
  IN_PROGRESS: '进行中',
  VERIFIED: '已核验',
  ASSUMED: '已假设',
  NOT_APPLICABLE: '不适用',
};

const STATUS_TO_BADGE: Record<
  ChecklistStatus,
  'DRAFT' | 'IN_APPROVAL' | 'CHECKED' | 'STALE' | 'OBSOLETE'
> = {
  NOT_STARTED: 'DRAFT',
  IN_PROGRESS: 'IN_APPROVAL',
  VERIFIED: 'CHECKED',
  ASSUMED: 'STALE',
  NOT_APPLICABLE: 'OBSOLETE',
};

type FilterValue = 'all' | string;

/** 从 input_value_json 提取数字（如 {"value": 1.5} / 直接数字 / null） */
function extractNumeric(it: ChecklistItem): number | null {
  const v = it.input_value_json;
  if (v == null) return null;
  if (typeof v === 'number') return v;
  if (typeof v === 'string') {
    const n = Number(v);
    return Number.isFinite(n) ? n : null;
  }
  if (typeof v === 'object' && 'value' in v) {
    const inner = (v as { value: unknown }).value;
    if (typeof inner === 'number') return inner;
    if (typeof inner === 'string') {
      const n = Number(inner);
      return Number.isFinite(n) ? n : null;
    }
  }
  return null;
}

export function InputChecklistPanel({ projectId, onItemClick }: Props): JSX.Element {
  const [items, setItems] = useState<ChecklistItem[]>([]);
  const [comp, setComp] = useState<ChecklistCompleteness | null>(null);
  const [statusFilter, setStatusFilter] = useState<FilterValue>('all');
  const [moduleFilter, setModuleFilter] = useState<FilterValue>('all');
  const [categoryFilter, setCategoryFilter] = useState<FilterValue>('all');

  useEffect(() => {
    checklistApi.list(projectId).then(setItems);
    checklistApi.completeness(projectId).then(setComp);
  }, [projectId]);

  const modules = useMemo(() => {
    const set = new Set<string>();
    for (const it of items) {
      if (it.module) set.add(it.module);
    }
    return Array.from(set).sort();
  }, [items]);

  const categories = useMemo(() => {
    const set = new Set<string>();
    for (const it of items) {
      if (it.input_category) set.add(it.input_category);
    }
    return Array.from(set).sort();
  }, [items]);

  const filtered = useMemo(() => {
    return items.filter((it) => {
      if (statusFilter !== 'all' && it.status !== statusFilter) return false;
      if (moduleFilter !== 'all' && it.module !== moduleFilter) return false;
      if (categoryFilter !== 'all' && it.input_category !== categoryFilter) return false;
      return true;
    });
  }, [items, statusFilter, moduleFilter, categoryFilter]);

  const assumedItems = useMemo(
    () => items.filter((it) => it.status === 'ASSUMED'),
    [items],
  );

  // 完成计数：local 计算（SPEC §6.8 显示「完成 N/Total」）
  const completed = items.filter((it) => it.status === 'VERIFIED').length;
  const total = items.length;

  const columns: ColumnsType<ChecklistItem> = [
    {
      title: '模块',
      dataIndex: 'module',
      key: 'module',
      width: 80,
      render: (m: string | null) => m || '—',
    },
    { title: '输入项', dataIndex: 'item_label', key: 'item_label' },
    {
      title: '分类',
      dataIndex: 'input_category',
      key: 'input_category',
      width: 100,
      render: (cat: ChecklistItem['input_category'], record: ChecklistItem) =>
        cat ? (
          <Tag data-testid="category-tag">{cat}{record.required ? '·必填' : ''}</Tag>
        ) : (
          '—'
        ),
    },
    {
      title: '当前值',
      dataIndex: 'input_value_json',
      key: 'current_value',
      width: 140,
      render: (_: unknown, record: ChecklistItem) => {
        const num = extractNumeric(record);
        return <NumericCell value={num} precision={4} precisionType="significant" />;
      },
    },
    {
      title: '来源',
      dataIndex: 'source_type',
      key: 'source',
      width: 100,
      render: (s: string | null) => s || '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (_: unknown, record: ChecklistItem) => (
        <StateBadge status={STATUS_TO_BADGE[record.status]} module="SIM" size="sm" />
      ),
    },
    {
      title: '核验人',
      dataIndex: 'verified_by',
      key: 'verified_by',
      width: 100,
      render: (v: string | null) => v || '—',
    },
    {
      title: '操作',
      key: 'actions',
      width: 80,
      render: (_: unknown, record: ChecklistItem) => (
        <a
          data-testid="checklist-item-action"
          data-item-id={record.checklist_id}
          onClick={(e) => {
            e.preventDefault();
            onItemClick?.(record);
          }}
          href="#"
        >
          详情
        </a>
      ),
    },
  ];

  return (
    <Card title="项目输入清单" data-testid="input-checklist-panel" style={{ marginTop: 16 }}>
      {/* 顶部统计 + 环形进度 */}
      <div
        data-testid="input-checklist-header"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 24,
          marginBottom: 16,
          flexWrap: 'wrap',
        }}
      >
        <Progress
          type="circle"
          percent={total > 0 ? (completed / total) * 100 : 0}
          size={64}
          status={completed === total ? 'success' : 'active'}
        />
        <Space direction="vertical" size={4}>
          <Typography.Text strong data-testid="completion-summary">
            完成 {completed}/{total}
          </Typography.Text>
          {comp && (
            <Typography.Text type="secondary" data-testid="completion-detail">
              REQUIRED {comp.required_verified}/{comp.required_total} ·
              假设 {comp.required_assumed} · 阻塞 {comp.required_blocked}
            </Typography.Text>
          )}
          <Typography.Text type="secondary">
            假设 {assumedItems.length} · 未验证 {items.filter((it) => it.status === 'IN_PROGRESS').length}
          </Typography.Text>
        </Space>
      </div>

      {/* 筛选 */}
      <Space style={{ marginBottom: 12 }} wrap>
        <Select<FilterValue>
          data-testid="filter-status"
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 120 }}
          options={[
            { value: 'all', label: '全部状态' },
            { value: 'NOT_STARTED', label: STATUS_LABEL.NOT_STARTED },
            { value: 'IN_PROGRESS', label: STATUS_LABEL.IN_PROGRESS },
            { value: 'VERIFIED', label: STATUS_LABEL.VERIFIED },
            { value: 'ASSUMED', label: STATUS_LABEL.ASSUMED },
            { value: 'NOT_APPLICABLE', label: STATUS_LABEL.NOT_APPLICABLE },
          ]}
        />
        <Select<FilterValue>
          data-testid="filter-module"
          value={moduleFilter}
          onChange={setModuleFilter}
          style={{ width: 120 }}
          options={[
            { value: 'all', label: '全部模块' },
            ...modules.map((m) => ({ value: m, label: m })),
          ]}
        />
        <Select<FilterValue>
          data-testid="filter-category"
          value={categoryFilter}
          onChange={setCategoryFilter}
          style={{ width: 120 }}
          options={[
            { value: 'all', label: '全部分类' },
            ...categories.map((c) => ({ value: c, label: c })),
          ]}
        />
      </Space>

      {/* 列表 */}
      <Table<ChecklistItem>
        data-testid="checklist-table"
        rowKey="checklist_id"
        size="small"
        columns={columns}
        dataSource={filtered}
        pagination={false}
      />

      {/* 假设数据清单（可展开） */}
      <Collapse
        ghost
        style={{ marginTop: 16 }}
        items={[
          {
            key: 'assumed',
            label: (
              <Typography.Text strong>
                假设数据清单（{assumedItems.length}）
              </Typography.Text>
            ),
            children: (
              <List
                data-testid="assumed-list"
                size="small"
                dataSource={assumedItems}
                renderItem={(it) => (
                  <List.Item data-testid="assumed-item">
                    <span style={{ flex: 1 }}>{it.item_label}</span>
                    <Tag color="warning">{STATUS_LABEL[it.status]}</Tag>
                    {it.assumption_reason && (
                      <Typography.Text type="secondary" style={{ marginLeft: 8 }}>
                        理由：{it.assumption_reason}
                      </Typography.Text>
                    )}
                  </List.Item>
                )}
              />
            ),
          },
        ]}
      />
    </Card>
  );
}

export default InputChecklistPanel;