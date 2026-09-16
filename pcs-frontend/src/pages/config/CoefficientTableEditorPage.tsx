/**
 * CoefficientTableEditorPage — 系数表编辑器（P45-2-5 / Task 23）。
 *
 * SPEC §7.10.3：
 * - 表格编辑（in-place 改条件/系数/来源）
 * - 条件分行（按 T/P 等范围）
 * - 批量修改（多选 → 批量改来源/批量删除）
 * - 来源标注（每行 tag）
 * - 版本对比（v_prev vs current，标 changed/added/removed）
 *
 * Props（SPEC 锁定）：
 *   rows: CoefficientRow[]
 *   prevVersion?: CoefficientRow[]   // 传入即启用版本对比
 *   prevLabel?: string
 *   currentLabel?: string
 *   onChange?: (rows) => void
 *   onSave?: (rows) => void
 */
import { useMemo, useState } from 'react';
import {
  Alert,
  Button,
  Input,
  InputNumber,
  Space,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';

/** 系数表行（SPEC §7.10.3）。 */
export interface CoefficientRow {
  row_id: string;
  condition: string;
  factor_a: number;
  factor_b: number;
  source: string;
}

interface Props {
  rows: CoefficientRow[];
  prevVersion?: CoefficientRow[];
  prevLabel?: string;
  currentLabel?: string;
  onChange?: (rows: CoefficientRow[]) => void;
  onSave?: (rows: CoefficientRow[]) => void;
}

function rowsEqual(a: CoefficientRow, b: CoefficientRow): boolean {
  return (
    a.condition === b.condition &&
    a.factor_a === b.factor_a &&
    a.factor_b === b.factor_b &&
    a.source === b.source
  );
}

function buildDiff(prev: CoefficientRow[], curr: CoefficientRow[]): Array<{
  key: string;
  diff: 'changed' | 'added' | 'removed';
  row: CoefficientRow;
}> {
  const prevMap = new Map(prev.map((r) => [r.row_id, r]));
  const currMap = new Map(curr.map((r) => [r.row_id, r]));
  const result: Array<{ key: string; diff: 'changed' | 'added' | 'removed'; row: CoefficientRow }> = [];

  for (const [id, row] of currMap) {
    if (!prevMap.has(id)) {
      result.push({ key: id, diff: 'added', row });
    } else if (!rowsEqual(prevMap.get(id)!, row)) {
      result.push({ key: id, diff: 'changed', row });
    }
  }
  for (const [id, row] of prevMap) {
    if (!currMap.has(id)) {
      result.push({ key: id, diff: 'removed', row });
    }
  }
  return result;
}

function newRow(): CoefficientRow {
  return {
    row_id: `r${Math.random().toString(36).slice(2, 9)}`,
    condition: '',
    factor_a: 0,
    factor_b: 0,
    source: '',
  };
}

export function CoefficientTableEditorPage({
  rows,
  prevVersion,
  prevLabel = '上一版本',
  currentLabel = '当前版本',
  onChange,
  onSave,
}: Props): JSX.Element {
  const [draft, setDraft] = useState<CoefficientRow[]>(rows);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [bulkSource, setBulkSource] = useState('');

  const diffs = useMemo(() => {
    if (!prevVersion) return [];
    return buildDiff(prevVersion, draft);
  }, [prevVersion, draft]);

  function update(next: CoefficientRow[]): void {
    setDraft(next);
    onChange?.(next);
  }

  function patchRow(idx: number, patch: Partial<CoefficientRow>): void {
    const next = [...draft];
    next[idx] = { ...next[idx], ...patch };
    update(next);
  }

  function toggleSelect(rowId: string, checked: boolean): void {
    const next = new Set(selected);
    if (checked) next.add(rowId);
    else next.delete(rowId);
    setSelected(next);
  }

  function applyBulkSource(): void {
    if (!bulkSource) return;
    const next = draft.map((r) => (selected.has(r.row_id) ? { ...r, source: bulkSource } : r));
    update(next);
    setBulkSource('');
  }

  function deleteSelected(): void {
    const next = draft.filter((r) => !selected.has(r.row_id));
    update(next);
    setSelected(new Set());
  }

  const columns: ColumnsType<CoefficientRow> = [
    {
      title: (
        <input
          type="checkbox"
          data-testid="coefficient-select-all"
          checked={selected.size === draft.length && draft.length > 0}
          onChange={(e) => {
            if (e.target.checked) setSelected(new Set(draft.map((r) => r.row_id)));
            else setSelected(new Set());
          }}
        />
      ),
      key: 'select',
      width: 50,
      render: (_: unknown, row: CoefficientRow) => (
        <input
          type="checkbox"
          data-testid="coefficient-select"
          checked={selected.has(row.row_id)}
          onChange={(e) => toggleSelect(row.row_id, e.target.checked)}
        />
      ),
    },
    {
      title: '条件',
      dataIndex: 'condition',
      render: (v: string, _row: CoefficientRow, idx: number) => (
        <Input
          size="small"
          data-testid="coefficient-cond-input"
          value={v}
          onChange={(e) => patchRow(idx, { condition: e.target.value })}
        />
      ),
    },
    {
      title: '系数 A',
      dataIndex: 'factor_a',
      width: 110,
      render: (v: number, _row: CoefficientRow, idx: number) => (
        <InputNumber
          size="small"
          data-testid="coefficient-factor_a-input"
          value={v}
          step={0.1}
          onChange={(nv) => patchRow(idx, { factor_a: Number(nv ?? 0) })}
        />
      ),
    },
    {
      title: '系数 B',
      dataIndex: 'factor_b',
      width: 110,
      render: (v: number, _row: CoefficientRow, idx: number) => (
        <InputNumber
          size="small"
          data-testid="coefficient-factor_b-input"
          value={v}
          step={0.1}
          onChange={(nv) => patchRow(idx, { factor_b: Number(nv ?? 0) })}
        />
      ),
    },
    {
      title: '来源',
      dataIndex: 'source',
      render: (v: string, _row: CoefficientRow, idx: number) => (
        <Input
          size="small"
          data-testid="coefficient-source-input"
          value={v}
          onChange={(e) => patchRow(idx, { source: e.target.value })}
        />
      ),
    },
    {
      title: '来源标注',
      key: 'source-tag',
      width: 110,
      render: (_: unknown, row: CoefficientRow) =>
        row.source ? <Tag color="blue">{row.source}</Tag> : <Tag>未标</Tag>,
    },
  ];

  return (
    <div data-testid="coefficient-page">
      <Typography.Title level={3} data-testid="coefficient-title">
        系数表编辑器
      </Typography.Title>

      <Space style={{ marginBottom: 12 }} data-testid="coefficient-toolbar">
        <Button
          type="dashed"
          data-testid="coefficient-add-row"
          onClick={() => update([...draft, newRow()])}
        >
          + 添加行
        </Button>
        <Input
          size="small"
          placeholder="批量来源"
          data-testid="coefficient-bulk-source-input"
          value={bulkSource}
          onChange={(e) => setBulkSource(e.target.value)}
          style={{ width: 180 }}
        />
        <Button
          size="small"
          data-testid="coefficient-bulk-source-apply"
          onClick={applyBulkSource}
          disabled={!bulkSource || selected.size === 0}
        >
          批量改来源（已选 {selected.size}）
        </Button>
        <Button
          size="small"
          danger
          data-testid="coefficient-bulk-delete"
          onClick={deleteSelected}
          disabled={selected.size === 0}
        >
          批量删除（已选 {selected.size}）
        </Button>
        <Button
          type="primary"
          data-testid="coefficient-save-btn"
          onClick={() => onSave?.(draft)}
        >
          保存
        </Button>
      </Space>

      <Table<CoefficientRow>
        rowKey="row_id"
        columns={columns}
        dataSource={draft}
        pagination={false}
        size="small"
        data-testid="coefficient-table"
        onRow={(_, idx) =>
          ({
            'data-testid': 'coefficient-row',
            'data-row-id': idx !== undefined ? draft[idx]?.row_id : '',
          }) as React.HTMLAttributes<HTMLElement>
        }
      />

      {prevVersion && diffs.length > 0 && (
        <div data-testid="coefficient-diff-panel" style={{ marginTop: 24 }}>
          <Typography.Title level={4}>
            版本对比：{prevLabel} → {currentLabel}
          </Typography.Title>
          <Space direction="vertical" style={{ width: '100%' }}>
            {diffs.map((d) => {
              const color = d.diff === 'added' ? 'green' : d.diff === 'removed' ? 'red' : 'orange';
              const label =
                d.diff === 'added' ? '新增' : d.diff === 'removed' ? '删除' : '变更';
              return (
                <Alert
                  key={d.key}
                  type={d.diff === 'removed' ? 'error' : d.diff === 'added' ? 'success' : 'warning'}
                  showIcon
                  message={
                    <Space data-testid="coefficient-diff-row" data-diff={d.diff} data-row-id={d.key}>
                      <Tag color={color}>{label}</Tag>
                      <Typography.Text>{d.row.row_id}：条件 = {d.row.condition || '（无）'}，系数 A = {d.row.factor_a}，系数 B = {d.row.factor_b}</Typography.Text>
                    </Space>
                  }
                />
              );
            })}
          </Space>
        </div>
      )}
    </div>
  );
}

export default CoefficientTableEditorPage;