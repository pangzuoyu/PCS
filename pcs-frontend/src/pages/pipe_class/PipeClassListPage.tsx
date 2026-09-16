/**
 * PipeClassListPage — PIPE_CLASS 等级列表（P45-3-2 / Task 29）。
 *
 * SPEC §7.9.1~2：
 * - 表格列：code / material / schedule / DN 范围 / 设计压力 / 设计温度 / 腐蚀余量 / 状态
 * - 过滤：按 code / material / schedule 模糊查询
 * - 行点击 → onSelect
 *
 * Props：
 *   classes: PipeClass[]
 *   onSelect?: (cls: PipeClass) => void
 */
import { useMemo, useState } from 'react';
import { Input, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { NumericCell } from '../../components/common/NumericCell';
import { StateBadge } from '../../components/common/StateBadge';
import type { PipeClass } from '../../types/pipeClass';

interface Props {
  classes: PipeClass[];
  onSelect?: (cls: PipeClass) => void;
}

export function PipeClassListPage({ classes, onSelect }: Props): JSX.Element {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return classes;
    return classes.filter(
      (c) =>
        c.code.toLowerCase().includes(q) ||
        c.material.toLowerCase().includes(q) ||
        c.schedule.toLowerCase().includes(q),
    );
  }, [classes, query]);

  const columns: ColumnsType<PipeClass> = [
    {
      title: 'code',
      dataIndex: 'code',
      width: 140,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    { title: 'material', dataIndex: 'material', width: 120 },
    { title: 'schedule', dataIndex: 'schedule', width: 100 },
    {
      title: 'DN 范围',
      width: 140,
      render: (_: unknown, row: PipeClass) =>
        `DN${row.size_range_json.min_dn}–${row.size_range_json.max_dn}`,
    },
    {
      title: '设计压力 (MPa)',
      dataIndex: 'design_pressure_mpa',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={2} precisionType="decimal" unit="MPa" />,
    },
    {
      title: '设计温度 (°C)',
      dataIndex: 'design_temperature_c',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={0} precisionType="decimal" unit="°C" />,
    },
    {
      title: '腐蚀余量 (mm)',
      dataIndex: 'corrosion_allowance_mm',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={1} precisionType="decimal" unit="mm" />,
    },
    {
      title: '状态',
      dataIndex: 'sign_status',
      width: 100,
      render: (s: PipeClass['sign_status']) => (
        <Space size={4}>
          <StateBadge status={s} module="PIPE" />
        </Space>
      ),
    },
  ];

  return (
    <div data-testid="pipe-class-list-page">
      <Typography.Title level={3}>管子等级</Typography.Title>

      <Input.Search
        data-testid="pipe-class-search"
        placeholder="按 code / material / schedule 过滤"
        allowClear
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        style={{ maxWidth: 360, marginBottom: 16 }}
      />

      <Table<PipeClass>
        rowKey="pipe_class_id"
        columns={columns}
        dataSource={filtered}
        pagination={false}
        onRow={(record) => ({
          'data-testid': 'pipe-class-row',
          'data-pipe-class-id': record.pipe_class_id,
          onClick: () => onSelect?.(record),
        })}
      />

      <Typography.Text type="secondary" style={{ display: 'block', marginTop: 12 }}>
        <Tag color="blue">{filtered.length}</Tag> 条记录
      </Typography.Text>
    </div>
  );
}

export default PipeClassListPage;