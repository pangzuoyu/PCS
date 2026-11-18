/**
 * PipeLineListPage — 管道一览表（P45-3-5 / Task 32 · **P10-C · T2 改：列清单对齐 SPEC**）。
 *
 * SPEC §7.11.2：
 * - design_stage 切换器 BASIC / DETAIL（列数不同）
 * - **管道一览表列（完整）**：43 列（逐条见下方 `ALL_COLUMNS`）
 * - BASIC：≤30 列简化 · DETAIL：**完整列**
 * - 过滤：流体分类 / 管道级别
 *
 * ## ⚠️ **P10-C · T2（TODO-159）**：列清单改成**逐条照抄 SPEC**
 *
 * 此前本页的列来自**前端手写的一份 25 列**类型 ⇒ ⇒ 其中 4 列
 * （`length_m` / `dp_kpa` / `velocity_m_s` / `pipe_class_detail`）
 * **后端根本没有** ⇒ ⇒ 真后端下永远是 `undefined` ⇒ ⇒ 「幽灵列」。
 *
 * ⇒ ⇒ 现在：`PipeLineListRow` = **契约类型**
 * （`GET /projects/{project_id}/pipe-line-list`）⇒ ⇒ 列 = SPEC 的 43 列
 * ⇒ ⇒ 数据源是 `piping_results`（管道记录的**唯一真相源**）。
 *
 * ⚠️ **BASIC 也改了**：SPEC 的列清单前 10 列（序号 / 管道号 / 尺寸 / 材料等级 /
 * 介质代号 / 介质名称 / 相态 / 流体分类 / 毒性级别 / 管道级别）**逐条对上**，
 * 另加设计压力 / 设计温度。
 */
import { useMemo, useState } from 'react';
import { Input, Segmented, Space, Table, Tag, Typography } from 'antd';

import { NumericCell } from '../../components/common/NumericCell';
import { StateBadge } from '../../components/common/StateBadge';
import type { PipeDesignStage, PipeLineListRow } from '../../types/pipe';
import type { StrictColumns } from '../../types/strictColumns';

interface Props {
  rows: PipeLineListRow[];
  onSelect?: (row: PipeLineListRow) => void;
}

/** 文本列（等宽字体）。 */
function textCol(title: string, dataIndex: keyof PipeLineListRow, width = 110) {
  return {
    title,
    dataIndex,
    width,
    render: (v: string) => (
      <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
    ),
  } as const;
}

/** 数值列（带单位 + 精度）。 */
function numCol(
  title: string,
  dataIndex: keyof PipeLineListRow,
  unit: string,
  precision: number,
  width = 120,
) {
  return {
    title,
    dataIndex,
    width,
    render: (v: number | null | undefined) =>
      v === null || v === undefined ? (
        <Typography.Text type="secondary">—</Typography.Text>
      ) : (
        <NumericCell value={v} precision={precision} precisionType="decimal" unit={unit} />
      ),
  } as const;
}

/** BASIC 档的列（SPEC 列清单的前 10 列 + 设计压力 / 设计温度）。 */
const BASIC_COLUMNS: StrictColumns<PipeLineListRow> = [
  { title: '序号', dataIndex: 'seq', width: 70 },
  textCol('管道号', 'pipe_no', 130),
  textCol('尺寸', 'size', 90),
  textCol('材料等级', 'material', 110),
  textCol('介质代号', 'fluid_code', 100),
  textCol('介质名称', 'fluid_name', 120),
  textCol('相态', 'phase', 80),
  textCol('流体分类', 'fluid_class', 90),
  textCol('毒性级别', 'toxicity', 100),
  textCol('管道级别', 'pipe_class', 100),
  numCol('设计压力 (MPa)', 'design_pressure_mpa', 'MPa', 2, 130),
  numCol('设计温度 (°C)', 'design_temperature_c', '°C', 0, 120),
];

/**
 * DETAIL 档 = **SPEC §7.11.2 的完整列清单**（43 列）+ 审计三列。
 *
 * ⚠️ 每列都对应 `piping_results` 的**真实列** ⇒ ⇒ 不会再出现「永远 undefined」
 * 的幽灵列。
 */
const ALL_COLUMNS: StrictColumns<PipeLineListRow> = [
  ...BASIC_COLUMNS,
  numCol('绝热厚度 (mm)', 'insulation_thickness', 'mm', 1, 120),
  textCol('绝热代号', 'insulation_code', 100),
  textCol('涂漆代号', 'paint_code', 100),
  textCol('伴管类型', 'tracing_type', 100),
  numCol('维持温度 (°C)', 'holding_temp', '°C', 0, 120),
  textCol('PID 图号', 'pid_ref', 110),
  textCol('起点', 'start_point', 110),
  textCol('终点', 'end_point', 110),
  numCol('正常操作压力 (MPa)', 'norm_oper_press', 'MPa', 2, 140),
  numCol('最大操作压力 (MPa)', 'max_oper_press', 'MPa', 2, 140),
  numCol('正常操作温度 (°C)', 'norm_oper_temp', '°C', 0, 140),
  numCol('最大操作温度 (°C)', 'max_oper_temp', '°C', 0, 140),
  numCol('备用·正常压力 (MPa)', 'alt_norm_oper_press', 'MPa', 2, 150),
  numCol('备用·最大压力 (MPa)', 'alt_max_oper_press', 'MPa', 2, 150),
  numCol('备用·正常温度 (°C)', 'alt_norm_oper_temp', '°C', 0, 150),
  numCol('备用·最大温度 (°C)', 'alt_max_oper_temp', '°C', 0, 150),
  numCol('设计真空', 'design_vacuum', 'MPa', 2, 110),
  numCol('设计最小温度 (°C)', 'design_min_temperature_c', '°C', 0, 140),
  textCol('压力管道类别', 'piping_category', 120),
  textCol('试验介质', 'pressure_test_medium', 100),
  numCol('试验压力', 'pressure_test_press', 'MPa', 2, 110),
  textCol('NDT 方法', 'ndt_method', 100),
  numCol('NDT 比例 (%)', 'ndt_ratio', '%', 0, 110),
  textCol('NDT 技术等级', 'ndt_tech_level', 120),
  textCol('泄漏试验介质', 'leak_test_medium', 120),
  numCol('泄漏试验压力', 'leak_test_press', 'MPa', 2, 130),
  textCol('检查等级', 'check_class', 100),
  {
    title: '清洗方法',
    dataIndex: 'cleaning_method',
    width: 120,
    render: (v: string[] | null | undefined) =>
      !v || v.length === 0 ? (
        <Typography.Text type="secondary">—</Typography.Text>
      ) : (
        v.map((m) => (
          <Tag key={m} color="blue">
            {m}
          </Tag>
        ))
      ),
  },
  textCol('应力分析级别', 'stress_analysis_level', 120),
  textCol('备注', 'remark', 160),
  {
    title: '状态',
    dataIndex: 'sign_status',
    width: 110,
    render: (s: string) => (
      <StateBadge status={s as 'DRAFT' | 'IN_APPROVAL' | 'CHECKED'} module="PIPE" />
    ),
  },
  textCol('更新人', 'updated_by', 150),
  {
    title: '更新时间',
    dataIndex: 'updated_at',
    width: 150,
    render: (v: string | null | undefined) =>
      v ? v : <Typography.Text type="secondary">—</Typography.Text>,
  },
];

const STAGE_OPTIONS: { value: PipeDesignStage; label: string }[] = [
  { value: 'BASIC', label: `BASIC (${BASIC_COLUMNS.length} 列)` },
  { value: 'DETAIL', label: `DETAIL (${ALL_COLUMNS.length} 列)` },
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
      if (classFilter && !(r.pipe_class ?? '').toLowerCase().includes(classFilter.toLowerCase())) {
        return false;
      }
      return true;
    });
  }, [rows, fluidFilter, classFilter]);

  const columns = stage === 'BASIC' ? BASIC_COLUMNS : ALL_COLUMNS;

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
