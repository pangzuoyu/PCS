/**
 * AllowableStressPage — 许用应力（P45-3-3 / Task 30）。
 *
 * SPEC §7.8.2：
 * - 表格：material / temp_c / stress_mpa / source
 *   （字段名 2026-10-19 对齐契约 `AllowableStressResult`，见 types/common.ts）
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

/**
 * `source` 的实际取值形如 `ASME_B31.3_TABLE_A1` / `GB_T_20801…`，
 * 而这张表按**前缀**着色。
 *
 * ⚠️ 2026-10-19 字段从 `standard`（值是 `ASME`/`GB`/`DIN`）改为契约的
 * `source` 之后，若照抄旧键表，`STANDARD_COLOR['ASME_B31.3_TABLE_A1']`
 * 是 undefined ⇒ **每一条标签都变灰**，看起来像「数据有问题」。
 * 改成前缀匹配后观感与之前一致。
 */
const SOURCE_COLOR: { prefix: string; color: string }[] = [
  { prefix: 'ASME', color: 'blue' },
  { prefix: 'GB', color: 'green' },
  { prefix: 'DIN', color: 'orange' },
];

const sourceColor = (src: string): string =>
  SOURCE_COLOR.find((r) => src.startsWith(r.prefix))?.color ?? 'default';

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
      dataIndex: 'temp_c',
      width: 100,
      render: (v: number) => <NumericCell value={v} precision={0} precisionType="decimal" unit="°C" />,
    },
    {
      title: '许用应力 (MPa)',
      dataIndex: 'stress_mpa',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={2} precisionType="decimal" unit="MPa" />,
    },
    {
      title: '数据来源',
      dataIndex: 'source',
      width: 100,
      render: (s: string) => (
        <Tag color={sourceColor(s)} data-testid="stress-standard">
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
          rowKey={(r) => `${r.material}-${r.temp_c}-${r.source}`}
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