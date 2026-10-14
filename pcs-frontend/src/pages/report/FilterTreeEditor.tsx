/**
 * 过滤条件树编辑器（第二批）。
 *
 * ## 为什么是递归组件而不是平铺列表
 *
 * 后端 `ReportDefFilterGroup.conditions` 是**自引用联合**，可以任意嵌套
 * （SPEC §3.2.2(4）「支持 AND/OR 分组，条件可嵌套」）。平铺列表表达不了
 * 嵌套，而**表达不了就会在保存时丢掉那部分** —— 第一批正是这么丢的
 * （TODO-060）：单条模型读不了组，保存把整棵子树抹了。
 *
 * ## 值的渲染按算子分三类
 *
 * 与后端 `query_engine` 严格对齐，三处常量各自都有出处：
 *
 * | 类别 | 算子 | 渲染 | 后端 |
 * |---|---|---|---|
 * | 无值 | `IS_NULL` / `IS_NOT_NULL` | 不给输入框 | `_VALUELESS` |
 * | 列表 | `IN` / `NOT_IN` / `BETWEEN` | 多值输入 | `_LIST_OPS` / `BETWEEN` 需恰好 2 个 |
 * | 标量 | 其余 11 个 | 单输入框 | — |
 *
 * ⚠️ **空值不静默放过**：后端对「缺 value」抛
 * `REPORT_FILTER_VALUE_MISSING` 而不是返回全表（query_engine 安全契约第 3 条）。
 * 所以这里把空值**原样发出去**并在界面上警告 —— 页面擅自改成 null 或删掉
 * 条件，等于把「筛选失败」变成「导出全量」，而后者看起来是成功的。
 */
import { useCallback } from 'react';
import type { JSX } from 'react';
import { Button, Card, Input, Select, Space, Tag, Tooltip, Typography } from 'antd';
import { DeleteOutlined, PlusOutlined } from '@ant-design/icons';

import {
  LIST_OPERATORS,
  VALUELESS_OPERATORS,
  type FilterLeaf,
  type FilterNode,
} from './definitionBody';

/** 列表算子的值元素类型（`mode="tags"` 产出字符串，
 *  但布尔字段的 IN 也可能是 boolean）。 */
type FilterListValue = (string | number | boolean | null)[];

/** 15 个算子（SPEC §3.2.2(4)），顺序与后端 `_OPERATORS` 一致。 */
export const ALL_OPERATORS = [
  'EQ', 'NEQ', 'GT', 'GTE', 'LT', 'LTE',
  'IN', 'NOT_IN', 'CONTAINS', 'STARTS_WITH', 'ENDS_WITH',
  'IS_NULL', 'IS_NOT_NULL', 'BETWEEN', 'LIKE',
] as const;

export interface FilterFieldOption {
  value: string;
  label: string;
  source: string;
}

interface Props {
  nodes: FilterNode[];
  onChange: (next: FilterNode[]) => void;
  fields: FilterFieldOption[];
  /** 嵌套深度上限。防手滑点出几十层点不动的树。 */
  maxDepth?: number;
  /**
   * 当前是「继承定义里的原条件」而非「用户删光了条件」。
   *
   * ⚠️ 只影响**空态文案**（评审 #11）：两者在 `nodes` 上都是 `[]`，
   * 而它们的含义完全相反 —— 前者执行时用定义的条件，后者导出全量。
   * 文案不区分的话，继承状态下界面会显示「将导出全量」而实际不是。
   *
   * 默认 false（按「删光了」处理），因为**直接使用本组件**的调用方
   * 若不传这个开关，宁可显示实际语义也不要显示一个无从证伪的承诺。
   */
  inherited?: boolean;
}

export function FilterTreeEditor(props: Props): JSX.Element {
  const { nodes, onChange, inherited = false } = props;
  const addLeaf = useCallback(() => {
    const f = props.fields[0];
    if (!f) return;
    onChange([...nodes, {
      kind: 'leaf', source: f.source, field: f.value, operator: 'EQ', value: '',
    }]);
  }, [nodes, onChange, props.fields]);

  const addGroup = useCallback(() => {
    onChange([...nodes, { kind: 'group', operator: 'AND', conditions: [] }]);
  }, [nodes, onChange]);

  const patch = useCallback((idx: number, next: FilterNode) =>
    onChange(nodes.map((n, i) => (i === idx ? next : n))), [nodes, onChange]);

  const remove = useCallback((idx: number) =>
    onChange(nodes.filter((_, i) => i !== idx)), [nodes, onChange]);

  const move = useCallback((idx: number, delta: number) => {
    const t = idx + delta;
    if (t < 0 || t >= nodes.length) return;
    const next = [...nodes];
    const [n] = next.splice(idx, 1);
    next.splice(t, 0, n);
    onChange(next);
  }, [nodes, onChange]);

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={8}>
      {/* ⚠️ 空态文案必须随 `inherited` 变（评审 #11，用户裁决）。
          inherited = 「没做临时调整，用定义里的原条件」；
          非 inherited 且为空 = 「用户把条件删光了 = 不筛选，导出全量」。
          原先两者都显示「导出全量」，于是继承状态下界面在骗人。 */}
      {nodes.length === 0 && (
        <Typography.Text type="secondary">
          {inherited
            ? '未做临时调整 —— 执行时使用定义里的原条件。'
            : '无过滤条件 —— 执行时将导出全量（等于覆盖了定义里的原条件）。'}
        </Typography.Text>
      )}
      {nodes.map((node, i) => (
        <Space key={i} wrap align="start">
          {i > 0 && <Tag color="blue">且</Tag>}
          <NodeEditor
            node={node}
            depth={0}
            onChange={(next) => patch(i, next)}
            fields={props.fields}
            maxDepth={props.maxDepth ?? 4}
          />
          <Space size={4}>
            <Button size="small" onClick={() => move(i, -1)}>↑</Button>
            <Button size="small" onClick={() => move(i, 1)}>↓</Button>
            <Button size="small" danger icon={<DeleteOutlined />}
              onClick={() => remove(i)} />
          </Space>
        </Space>
      ))}
      <Space>
        <Button size="small" icon={<PlusOutlined />} onClick={addLeaf}>
          加条件
        </Button>
        <Button size="small" icon={<PlusOutlined />} onClick={addGroup}>
          加条件组（AND/OR）
        </Button>
      </Space>
    </Space>
  );
}

interface NodeProps {
  node: FilterNode;
  depth: number;
  onChange: (next: FilterNode) => void;
  fields: FilterFieldOption[];
  maxDepth: number;
}

function NodeEditor({ node, depth, onChange, fields, maxDepth }: NodeProps) {
  if (node.kind === 'group') {
    return (
      <Card size="small" style={{ background: '#FAFAFA' }}
        title={
          <Select size="small" style={{ width: 90 }}
            value={node.operator}
            onChange={(v) => onChange({ ...node, operator: v })}
            options={[{ value: 'AND', label: '全部满足' },
              { value: 'OR', label: '任一满足' }]} />
        }
        extra={depth >= maxDepth
          ? <Tag color="orange">已达最大嵌套深度</Tag>
          : null}>
        {node.conditions.length === 0
          ? <Typography.Text type="secondary">空组</Typography.Text>
          : <Space direction="vertical" size={6}>
            {node.conditions.map((c, i) => (
              <Space key={i} wrap align="start">
                {i > 0 && <Tag color={node.operator === 'AND' ? 'blue' : 'purple'}>
                  {node.operator === 'AND' ? '且' : '或'}
                </Tag>}
                <NodeEditor node={c} depth={depth + 1}
                  onChange={(next) => onChange({
                    ...node,
                    conditions: node.conditions.map((x, j) => (j === i ? next : x)),
                  })}
                  fields={fields} maxDepth={maxDepth} />
                <Button size="small" danger icon={<DeleteOutlined />}
                  onClick={() => onChange({ ...node,
                    conditions: node.conditions.filter((_, j) => j !== i) })} />
              </Space>
            ))}
          </Space>}
      </Card>
    );
  }
  return <LeafEditor node={node} fields={fields} onChange={onChange} />;
}

interface LeafProps {
  node: FilterLeaf;
  fields: FilterFieldOption[];
  onChange: (next: FilterNode) => void;
}

function LeafEditor({ node, fields, onChange }: LeafProps): JSX.Element {
  const valueless = VALUELESS_OPERATORS.has(node.operator);
  const isList = LIST_OPERATORS.has(node.operator);
  const listValue = Array.isArray(node.value) ? node.value : [];

  return (
    <Space wrap>
      <Select showSearch style={{ width: 200 }} value={node.field}
        onChange={(v) => {
          const f = fields.find((x) => x.value === v);
          onChange({ ...node, field: v, source: f?.source ?? node.source });
        }}
        options={fields.map((f) => ({ value: f.value, label: f.label }))} />

      <Select style={{ width: 140 }} value={node.operator}
        onChange={(v) => onChange({
          ...node, operator: v,
          // 换算子时**清掉不该留的值**：IS_NULL 带 value 是非法的，
          // EQ 带数组也是。留着会在保存时被后端拒，而用户看不懂
          // 「为什么我刚才那个值没了」——所以这里顺手清掉。
          value: VALUELESS_OPERATORS.has(v) ? null
            : LIST_OPERATORS.has(v)
              // 切成列表算子时把标量包成单元素列表（空值包成空列表），
              // 否则用户刚输入的值会凭空消失。
              ? (Array.isArray(node.value) ? listValue
                : (node.value === '' || node.value === null ? [] : [node.value]))
              : (Array.isArray(node.value) ? (node.value[0] ?? '') : node.value),
        })}
        options={ALL_OPERATORS.map((o) => ({ value: o, label: o }))} />

      {isList ? (
        <ListValueEditor
          operator={node.operator}
          values={listValue}
          onChange={(v) => onChange({ ...node, value: v })}
        />
      ) : valueless ? null : (
        <Input style={{ width: 180 }} value={String(node.value ?? '')}
          status={node.value === '' || node.value === null ? 'warning' : undefined}
          placeholder="值"
          onChange={(e) => onChange({ ...node, value: e.target.value })} />
      )}

      {/* ⚠️ 空值必须**原样发出去**让后端报 REPORT_FILTER_VALUE_MISSING。
          页面擅自改成 null 或删掉条件 = 把「筛选失败」变成「导出全量」，
          而后者看起来是成功的。 */}
      {!valueless && (node.value === '' || node.value === null
        || (isList && listValue.length === 0)
        || (node.operator === 'BETWEEN' && listValue.length !== 2)) && (
        <Tooltip title="后端对空值会报 REPORT_FILTER_VALUE_MISSING（而不是放行全表）。这里保留空值，让它报错而不是悄悄导出全量。">
          <Tag color="orange">值不完整</Tag>
        </Tooltip>
      )}
      {node.operator === 'BETWEEN' && listValue.length === 1 && (
        <Tag color="orange">BETWEEN 需要 2 个值</Tag>
      )}
    </Space>
  );
}

function ListValueEditor({
  operator, values, onChange,
}: {
  operator: string;
  values: FilterListValue;
  onChange: (v: FilterListValue) => void;
}): JSX.Element {
  if (operator === 'BETWEEN') {
    // 恰好两个输入框 —— 后端 `len(value) != 2` 就报错，
    // 给三个输入框只会让人填了三个再被拒。
    return (
      <Input.Group compact>
        {[0, 1].map((i) => (
          <Input key={i} style={{ width: 100 }}
            placeholder={i === 0 ? '下界' : '上界'}
            value={String(values[i] ?? '')}
            onChange={(e) => {
              const next = [0, 1].map((k) => values[k] ?? '');
              next[i] = e.target.value;
              onChange(next);
            }} />
        ))}
      </Input.Group>
    );
  }
  return (
    <Select mode="tags" style={{ minWidth: 220 }} value={values.map(String)}
      placeholder="输入后回车，每个值一项"
      onChange={(v) => onChange(v)} tokenSeparators={[',']} />
  );
}
