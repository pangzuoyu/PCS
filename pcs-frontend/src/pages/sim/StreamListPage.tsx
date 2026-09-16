/**
 * StreamListPage — SIM 物流列表（P45-3-1 / Task 28）。
 *
 * SPEC §7.7.1：
 * - 表格列：tag_number / 名称 / 相态 / 温压 / 流量 / 状态
 * - 状态点 tabs：DRAFT / CHECKED / IN_APPROVAL / 全部
 * - 行点击 → onSelect（路由跳转由父组件负责）
 *
 * Props：
 *   streams: Stream[]
 *   onSelect?: (stream) => void
 */
import { useMemo, useState } from 'react';
import { Empty, Space, Table, Tabs, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { NumericCell } from '../../components/common/NumericCell';
import { StateBadge } from '../../components/common/StateBadge';
import { STREAM_PHASE_LABEL, type Stream } from '../../types/stream';

interface Props {
  streams: Stream[];
  onSelect?: (stream: Stream) => void;
}

type StatusFilter = 'ALL' | Stream['sign_status'];

const STATUS_TABS: { key: StatusFilter; label: string }[] = [
  { key: 'ALL', label: '全部' },
  { key: 'DRAFT', label: 'DRAFT' },
  { key: 'IN_APPROVAL', label: 'IN_APPROVAL' },
  { key: 'CHECKED', label: 'CHECKED' },
];

const PHASE_COLOR: Record<Stream['phase'], string> = {
  LIQUID: 'blue',
  VAPOR: 'orange',
  MIXED: 'purple',
  AQUEOUS: 'cyan',
};

export function StreamListPage({ streams, onSelect }: Props): JSX.Element {
  const [statusFilter, setStatusFilter] = useState<StatusFilter>('ALL');

  const filtered = useMemo(() => {
    if (statusFilter === 'ALL') return streams;
    return streams.filter((s) => s.sign_status === statusFilter);
  }, [streams, statusFilter]);

  const columns: ColumnsType<Stream> = [
    {
      title: 'tag_number',
      dataIndex: 'tag_number',
      width: 140,
      render: (v: string) => (
        <span data-testid="stream-tag" style={{ fontFamily: 'var(--font-mono, monospace)' }}>
          {v}
        </span>
      ),
    },
    {
      title: '名称',
      dataIndex: 'stream_name',
      render: (v: string) => <span data-testid="stream-name">{v}</span>,
    },
    {
      title: '相态',
      dataIndex: 'phase',
      width: 100,
      render: (p: Stream['phase'], row: Stream) => (
        <Space size={4}>
          <Tag color={PHASE_COLOR[p]} data-testid="stream-phase">
            {STREAM_PHASE_LABEL[p]}
          </Tag>
          {row.subphase && (
            <Tag color="default" data-testid="stream-subphase">
              {row.subphase}
            </Tag>
          )}
        </Space>
      ),
    },
    {
      title: '温度 (°C)',
      dataIndex: 'temperature_c',
      width: 110,
      render: (v: number) => <NumericCell value={v} precision={1} precisionType="decimal" unit="°C" />,
    },
    {
      title: '压力 (MPa)',
      dataIndex: 'pressure_mpa',
      width: 110,
      render: (v: number) => <NumericCell value={v} precision={2} precisionType="decimal" unit="MPa" />,
    },
    {
      title: '流量 (kg/h)',
      dataIndex: 'total_mass_flow_kg_h',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={0} precisionType="decimal" unit="kg/h" />,
    },
    {
      title: '状态',
      dataIndex: 'sign_status',
      width: 100,
      render: (s: Stream['sign_status']) => <StateBadge status={s} module="SIM" />,
    },
    {
      title: '更新人',
      dataIndex: 'updated_by',
      width: 100,
    },
  ];

  return (
    <div data-testid="stream-list-page">
      <Typography.Title level={3}>SIM 物流列表</Typography.Title>

      <Tabs
        data-testid="stream-list-tabs"
        activeKey={statusFilter}
        onChange={(k) => setStatusFilter(k as StatusFilter)}
        items={STATUS_TABS.map((t) => ({ key: t.key, label: t.label }))}
      />

      {filtered.length === 0 ? (
        <Empty description="无物流" data-testid="stream-list-empty" />
      ) : (
        <Table<Stream>
          rowKey="stream_id"
          columns={columns}
          dataSource={filtered}
          pagination={false}
          onRow={(record) => ({
            'data-testid': 'stream-row',
            'data-stream-id': record.stream_id,
            'data-status': record.sign_status,
            onClick: () => onSelect?.(record),
          })}
        />
      )}
    </div>
  );
}

export default StreamListPage;