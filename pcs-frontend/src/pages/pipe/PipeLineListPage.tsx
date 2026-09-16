/**
 * PipeLineListPage — 管道一览表（P45-3-5 / Task 32）。
 *
 * SPEC §7.11.2：
 * - design_stage 切换器 BASIC / DETAIL（列数不同）
 * - BASIC：seq / pipe_no / size / material / fluid_xxx / fluid_name / phase / fluid_class / toxicity / pipe_class + 设计压力/温度（10 列）
 * - DETAIL：BASIC + length / dp / velocity / pipe_class_detail / insulation / 起终点 / pid_ref / sign_status / updated_xxx（25 列）
 * - 过滤：流体分类 / 管道级别
 *
 * Props：
 *   rows: PipeLineListRow[]
 *   onSelect?: (row) => void
 */
import { useMemo, useState } from 'react';
import { Input, Segmented, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { NumericCell } from '../../components/common/NumericCell';
import { StateBadge } from '../../components/common/StateBadge';
import type { PipeDesignStage, PipeLineListRow } from '../../types/pipe';

interface Props {
  rows: PipeLineListRow[];
  onSelect?: (row: PipeLineListRow) => void;
}

const STAGE_OPTIONS: { value: PipeDesignStage; label: string }[] = [
  { value: 'BASIC', label: 'BASIC (10 列)' },
  { value: 'DETAIL', label: 'DETAIL (25 列)' },
];

export function PipeLineListPage({ rows, onSelect }: Props): JSX.Element {
  const [stage, setStage] = useState<PipeDesignStage>('BASIC');
  const [fluidFilter, setFluidFilter] = useState('');
  const [classFilter, setClassFilter] = useState('');

  const filtered = useMemo(() => {
    return rows.filter((r) => {
      if (fluidFilter && !r.fluid_name.toLowerCase().includes(fluidFilter.toLowerCase())) {
        return false;
      }
      if (classFilter && !r.pipe_class.toLowerCase().includes(classFilter.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [rows, fluidFilter, classFilter]);

  const basicColumns: ColumnsType<PipeLineListRow> = [
    { title: 'seq', dataIndex: 'seq', width: 60 },
    {
      title: 'pipe_no',
      dataIndex: 'pipe_no',
      width: 120,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    { title: 'size', dataIndex: 'size', width: 80 },
    { title: 'material', dataIndex: 'material', width: 100 },
    { title: 'fluid', dataIndex: 'fluid_name', width: 120 },
    { title: 'phase', dataIndex: 'phase', width: 80 },
    { title: 'class', dataIndex: 'fluid_class', width: 80 },
    { title: 'toxicity', dataIndex: 'toxicity', width: 80 },
    { title: 'pipe_class', dataIndex: 'pipe_class', width: 100 },
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
  ];

  const detailColumns: ColumnsType<PipeLineListRow> = [
    ...basicColumns,
    {
      title: '长度 (m)',
      dataIndex: 'length_m',
      width: 90,
      render: (v?: number) =>
        v === undefined ? <Typography.Text type="secondary">—</Typography.Text> : (
            <NumericCell value={v} precision={1} precisionType="decimal" unit="m" />
          ),
    },
    {
      title: 'dp (kPa)',
      dataIndex: 'dp_kpa',
      width: 90,
      render: (v?: number) =>
        v === undefined ? <Typography.Text type="secondary">—</Typography.Text> : (
            <NumericCell value={v} precision={2} precisionType="decimal" unit="kPa" />
          ),
    },
    {
      title: 'velocity (m/s)',
      dataIndex: 'velocity_m_s',
      width: 100,
      render: (v?: number) =>
        v === undefined ? <Typography.Text type="secondary">—</Typography.Text> : (
            <NumericCell value={v} precision={2} precisionType="decimal" unit="m/s" />
          ),
    },
    { title: 'start', dataIndex: 'start_point', width: 100 },
    { title: 'end', dataIndex: 'end_point', width: 100 },
    { title: 'pid_ref', dataIndex: 'pid_ref', width: 100 },
    { title: 'insulation', dataIndex: 'insulation_code', width: 100 },
    {
      title: '状态',
      dataIndex: 'sign_status',
      width: 100,
      render: (s?: string) =>
        s ? <StateBadge status={s as 'DRAFT' | 'IN_APPROVAL' | 'CHECKED'} module="PIPE" /> :
          <Typography.Text type="secondary">—</Typography.Text>,
    },
    { title: '更新人', dataIndex: 'updated_by', width: 100 },
    { title: '更新时间', dataIndex: 'updated_at', width: 140 },
  ];

  const columns = stage === 'BASIC' ? basicColumns : detailColumns;

  return (
    <div data-testid="pipe-line-list-page">
      <Space style={{ marginBottom: 16, justifyContent: 'space-between', display: 'flex' }}>
        <Typography.Title level={3} style={{ margin: 0 }}>管道一览表</Typography.Title>
        <Segmented
          data-testid="pipe-stage-switcher"
          options={STAGE_OPTIONS}
          value={stage}
          onChange={(v) => setStage(v as PipeDesignStage)}
        />
      </Space>

      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          data-testid="pipe-filter-fluid"
          placeholder="按流体名过滤"
          allowClear
          value={fluidFilter}
          onChange={(e) => setFluidFilter(e.target.value)}
          style={{ width: 200 }}
        />
        <Input.Search
          data-testid="pipe-filter-class"
          placeholder="按管道级别过滤"
          allowClear
          value={classFilter}
          onChange={(e) => setClassFilter(e.target.value)}
          style={{ width: 200 }}
        />
        <Tag color="blue" data-testid="pipe-filter-count">{filtered.length}</Tag>
      </Space>

      <Table<PipeLineListRow>
        rowKey="seq"
        columns={columns}
        dataSource={filtered}
        pagination={false}
        size="small"
        scroll={{ x: 'max-content' }}
        onRow={(record) => ({
          'data-testid': 'pipe-line-row',
          'data-pipe-no': record.pipe_no,
          onClick: () => onSelect?.(record),
        })}
      />
    </div>
  );
}

export default PipeLineListPage;