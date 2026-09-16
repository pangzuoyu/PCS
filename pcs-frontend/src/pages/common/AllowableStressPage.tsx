/**
 * AllowableStressPage — 许用应力（P45-3-3 / Task 30）。
 *
 * SPEC §7.8.2：
 * - 表格：material / temperature_c / allowable_stress_mpa / standard
 * - 过滤：按 material 模糊查询
 * - 标准来源 Tag
 *
 * Props：
 *   stresses: AllowableStress[]
 */
import { useMemo, useState } from 'react';
import { Empty, Input, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { NumericCell } from '../../components/common/NumericCell';
import type { AllowableStress } from '../../types/common';

interface Props {
  stresses: AllowableStress[];
}

const STANDARD_COLOR: Record<string, string> = {
  ASME: 'blue',
  GB: 'green',
  DIN: 'orange',
};

export function AllowableStressPage({ stresses }: Props): JSX.Element {
  const [query, setQuery] = useState('');

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return stresses;
    return stresses.filter((s) => s.material.toLowerCase().includes(q));
  }, [stresses, query]);

  const columns: ColumnsType<AllowableStress> = [
    {
      title: '材料',
      dataIndex: 'material',
      width: 120,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    {
      title: '温度 (°C)',
      dataIndex: 'temperature_c',
      width: 100,
      render: (v: number) => <NumericCell value={v} precision={0} precisionType="decimal" unit="°C" />,
    },
    {
      title: '许用应力 (MPa)',
      dataIndex: 'allowable_stress_mpa',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={2} precisionType="decimal" unit="MPa" />,
    },
    {
      title: '标准',
      dataIndex: 'standard',
      width: 100,
      render: (s: string) => (
        <Tag color={STANDARD_COLOR[s] ?? 'default'} data-testid="stress-standard">
          {s}
        </Tag>
      ),
    },
  ];

  return (
    <div data-testid="allowable-stress-page">
      <Typography.Title level={3}>许用应力</Typography.Title>

      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          data-testid="stress-search"
          placeholder="按材料过滤"
          allowClear
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          style={{ width: 240 }}
        />
        <Tag color="blue">{filtered.length}</Tag>
      </Space>

      {filtered.length === 0 ? (
        <Empty description="无记录" />
      ) : (
        <Table<AllowableStress>
          rowKey={(r) => `${r.material}-${r.temperature_c}-${r.standard}`}
          columns={columns}
          dataSource={filtered}
          pagination={false}
          size="small"
        />
      )}
    </div>
  );
}

export default AllowableStressPage;