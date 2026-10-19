/**
 * PipeClassListPage — PIPE_CLASS 等级列表（P45-3-2 / Task 29）。
 *
 * SPEC §7.9.1~2：
 * - 表格列：等级号 / 材料标准 / 壁厚 / DN 范围 / 设计压力 / 设计温度 / 腐蚀余量 / 状态
 * - 过滤：按等级号 / 材料标准 / 壁厚模糊查询
 * - 行点击 → onSelect
 *
 * ## 字段名以**契约**为准（2026-10-19，bug-180）
 *
 * 此前本页读的是手写副本的 `code` / `material` / `schedule` /
 * `size_range_json` / `sign_status` / `pipe_class_id`，而真后端返
 * `class_name` / `material_standard` / `sch_series_json` /
 * `dn_series_json` / `status` / `class_id` —— 生产上全是 `undefined`
 * （`rowKey` 也是），是 `src/mocks/seed/pipe-classes.ts` 一直在遮着。
 * 类型现已并到 `components['schemas']['PipeClassResponse']`，改不掉。
 *
 * ## 「壁厚」列：契约给的是**映射**，不是单个值（用户裁决 2026-10-19）
 *
 * `sch_series_json` 是 `{DN: Sch}` —— 每个 DN 对应一个 Sch，
 * 它是**函数**不是可选集合，所以不能说「3 档可选」。
 * 摘要逻辑在 `src/lib/pipeClassSch.ts`（共享模块，导出/搜索将来复用），
 * 本页只负责把它渲染成列。
 *
 * Props：
 *   classes: PipeClass[]
 *   onSelect?: (cls: PipeClass) => void
 */
import { useMemo, useState } from 'react';
import { Input, Space, Table, Tag, Tooltip, Typography } from 'antd';

import { NumericCell } from '../../components/common/NumericCell';
import {
  StateBadge,
  type PipeClassStatus,
} from '../../components/common/StateBadge';
import {
  schSummarySearchText,
  schSummaryText,
  schSummaryTooltip,
  summarizeSchSeries,
} from '../../lib/pipeClassSch';
import type { PipeClass } from '../../types/pipeClass';
import type { StrictColumns } from '../../types/strictColumns';

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
        c.class_name.toLowerCase().includes(q) ||
        c.material_standard.toLowerCase().includes(q) ||
        // 壁厚按**值**过滤：用户输入 "Sch 40" 要能命中 DN50 与 DN100 两档，
        // 不能只匹配 DN 键。用摘要的 UNIFORM 值，或 VARIED 里任一段的值。
        // toLowerCase 与上面两行一致 —— q 已小写，摘要文本也必须小写，
        // 否则搜 "sch 160" 搜不到 "Sch 160"。
        schSummarySearchText(c.sch_series_json).toLowerCase().includes(q),
    );
  }, [classes, query]);

  const columns: StrictColumns<PipeClass> = [
    {
      title: '等级号',
      dataIndex: 'class_name',
      width: 140,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    { title: '材料标准', dataIndex: 'material_standard', width: 120 },
    {
      // ⚠️ 契约里**没有**单个 schedule，只有 DN→Sch 映射（用户裁决 2026-10-19）。
      // 删列会丢掉「这个等级在其 DN 范围内壁厚是否统一」这个信号 ——
      // 那正是用户扫一眼表格要判断的。措辞用「按 DN 分档」而非「多档」：
      // 「多档」会被读成「多个可选档位」，而这里是一个函数不是一个集合。
      title: '壁厚',
      width: 160,
      render: (_: unknown, row: PipeClass) => {
        const summary = summarizeSchSeries(row.sch_series_json);
        const text = schSummaryText(summary);
        const tip = schSummaryTooltip(summary);
        return tip ? (
          <Tooltip title={tip}>{text}</Tooltip>
        ) : text;
      },
    },
    {
      title: 'DN 范围',
      width: 140,
      render: (_: unknown, row: PipeClass) =>
        `DN${row.dn_series_json.min}–${row.dn_series_json.max}`,
    },
    {
      title: '设计压力 (MPa)',
      dataIndex: 'design_pressure',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={2} precisionType="decimal" unit="MPa" />,
    },
    {
      title: '设计温度 (°C)',
      dataIndex: 'design_temperature',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={0} precisionType="decimal" unit="°C" />,
    },
    {
      title: '腐蚀余量 (mm)',
      dataIndex: 'corrosion_allowance',
      width: 130,
      render: (v: number) => <NumericCell value={v} precision={1} precisionType="decimal" unit="mm" />,
    },
    {
      // ⚠️ 契约的 `status` 是**裸 string**（后端 `PipeClassResponse.status`
      // 没写 Literal），但词表是 DRAFT / ACTIVE / OBSOLETE 三态。
      // 原实现用 `module="PIPE"` 传 `sign_status`，两处都错：
      //   字段名错 → 生产上 `undefined` → 静默兜底成「草稿」
      //   module 错 → 即使有值，`ACTIVE` 也不在 PIPE 的渲染表里
      // 现在走 PIPE_CLASS 独立词表；未知值交给 StateBadge 的显形分支
      // （dev 抛错 / prod「未知状态: X」），**不再猜成草稿**。
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (s: string) => (
        <Space size={4}>
          <StateBadge module="PIPE_CLASS" status={s as PipeClassStatus} />
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
          'data-pipe-class-id': record.class_id,
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