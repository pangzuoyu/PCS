/**
 * PmsPage — 管道材料规格（P45-3-8 / Task 35）。
 *
 * SPEC §7.5.1：
 * - 表格：pms_no / 描述 / pms_class / hazard_level（Tag）/ sign_status
 * - 过滤：按 hazard_level
 * - 行点击 → onSelect
 */
import { useMemo, useState } from 'react';
import { Segmented, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import { StateBadge } from '../../components/common/StateBadge';
import type { HazardLevel, PmsItem } from '../../types/pms';

interface Props {
  items: PmsItem[];
  onSelect?: (item: PmsItem) => void;
}

const HAZARD_OPTIONS: { value: 'ALL' | HazardLevel; label: string }[] = [
  { value: 'ALL', label: '全部' },
  { value: 'HIGH', label: 'HIGH' },
  { value: 'MEDIUM', label: 'MEDIUM' },
  { value: 'LOW', label: 'LOW' },
];

const HAZARD_COLOR: Record<HazardLevel, string> = {
  HIGH: 'red',
  MEDIUM: 'gold',
  LOW: 'blue',
};

const HAZARD_LABEL: Record<HazardLevel, string> = {
  HIGH: '高',
  MEDIUM: '中',
  LOW: '低',
};

export function PmsPage({ items, onSelect }: Props): JSX.Element {
  const [filter, setFilter] = useState<'ALL' | HazardLevel>('ALL');

  const filtered = useMemo(() => {
    if (filter === 'ALL') return items;
    return items.filter((i) => i.hazard_level === filter);
  }, [items, filter]);

  const columns: ColumnsType<PmsItem> = [
    {
      title: 'pms_no',
      dataIndex: 'pms_no',
      width: 140,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    { title: '描述', dataIndex: 'description' },
    { title: 'pms_class', dataIndex: 'pms_class', width: 120 },
    {
      title: 'hazard',
      dataIndex: 'hazard_level',
      width: 100,
      render: (h: HazardLevel) => (
        <Tag color={HAZARD_COLOR[h]} data-testid="pms-hazard">
          {HAZARD_LABEL[h]}
        </Tag>
      ),
    },
    {
      title: '状态',
      dataIndex: 'sign_status',
      width: 100,
      render: (s: PmsItem['sign_status']) => (
        <StateBadge status={s} module="CONFIG" />
      ),
    },
  ];

  return (
    <div data-testid="pms-page">
      <PageHeader title="PMS 管道材料规格" module="CONFIG" actions={null as unknown as undefined} />

      <Space style={{ marginBottom: 16 }}>
        <Segmented
          data-testid="pms-hazard-filter"
          options={HAZARD_OPTIONS}
          value={filter}
          onChange={(v) => setFilter(v as 'ALL' | HazardLevel)}
        />
        <Tag color="blue" data-testid="pms-count">{filtered.length}</Tag>
      </Space>

      <Typography.Title level={4} style={{ marginTop: 0 }}>PMS 项目</Typography.Title>
      <Table<PmsItem>
        rowKey="item_id"
        columns={columns}
        dataSource={filtered}
        pagination={false}
        size="small"
        onRow={(record) => ({
          'data-testid': 'pms-row',
          'data-pms-no': record.pms_no,
          onClick: () => onSelect?.(record),
        })}
      />
    </div>
  );
}

export default PmsPage;