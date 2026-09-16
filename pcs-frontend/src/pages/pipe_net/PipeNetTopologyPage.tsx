/**
 * PipeNetTopologyPage — PIPE_NET 拓扑编辑器（P45-3-6 / Task 33，V1 极简版）。
 *
 * SPEC §7.11.3：
 * - 节点：设备 / 连接点 / 入口 / 出口
 * - 边：管道（from_node → to_node）
 * - 校验：孤立点 / 命名重复 / 环路
 * - V1：手写 SVG 渲染节点 + 边；不引入 reactflow（依赖 ~200KB，留 PIPE_NET
 *   完整功能时再装；本任务为骨架）
 *
 * Props：
 *   graph: PipeNetGraph
 *   onValidate?: (graph: PipeNetGraph) => PipeNetValidation
 *   onExport?: (graph: PipeNetGraph) => void
 */
import { useMemo } from 'react';
import { Alert, Button, Card, Empty, Space, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';

import { PageHeader } from '../../components/common/PageHeader';
import type {
  PipeNetEdge,
  PipeNetGraph,
  PipeNetNode,
  PipeNetValidation,
} from '../../types/pipeNet';

interface Props {
  graph: PipeNetGraph;
  onValidate?: (graph: PipeNetGraph) => PipeNetValidation;
  onExport?: (graph: PipeNetGraph) => void;
}

const NODE_KIND_COLOR: Record<PipeNetNode['kind'], string> = {
  EQUIPMENT: 'blue',
  JUNCTION: 'default',
  INLET: 'green',
  OUTLET: 'orange',
};

const NODE_KIND_LABEL: Record<PipeNetNode['kind'], string> = {
  EQUIPMENT: '设备',
  JUNCTION: '连接点',
  INLET: '入口',
  OUTLET: '出口',
};

/** V1 mock 校验：找孤立点（无任何边相连）+ 重复 tag */
function defaultValidation(graph: PipeNetGraph): PipeNetValidation {
  const connected = new Set<string>();
  for (const e of graph.edges) {
    connected.add(e.from_node_id);
    connected.add(e.to_node_id);
  }
  // 报告 tag_number（用户可识别）而非 node_id
  const orphans = graph.nodes.filter((n) => !connected.has(n.node_id)).map((n) => n.tag_number);

  const tagSet = new Map<string, number>();
  for (const n of graph.nodes) {
    tagSet.set(n.tag_number, (tagSet.get(n.tag_number) ?? 0) + 1);
  }
  const duplicate_tags: string[] = [];
  for (const [t, c] of tagSet.entries()) {
    if (c > 1) duplicate_tags.push(t);
  }

  return { orphans, duplicate_tags, cycles: [] };
}

export function PipeNetTopologyPage({ graph, onValidate, onExport }: Props): JSX.Element {
  const validation = useMemo(
    () => (onValidate ? onValidate(graph) : defaultValidation(graph)),
    [graph, onValidate],
  );

  const nodeById = useMemo(
    () => new Map(graph.nodes.map((n) => [n.node_id, n])),
    [graph.nodes],
  );

  const nodeColumns: ColumnsType<PipeNetNode> = [
    {
      title: 'tag',
      dataIndex: 'tag_number',
      width: 120,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    { title: '名称', dataIndex: 'label' },
    {
      title: '类型',
      dataIndex: 'kind',
      width: 100,
      render: (k: PipeNetNode['kind']) => (
        <Tag color={NODE_KIND_COLOR[k]}>{NODE_KIND_LABEL[k]}</Tag>
      ),
    },
    { title: 'x', dataIndex: 'x', width: 60 },
    { title: 'y', dataIndex: 'y', width: 60 },
  ];

  const edgeColumns: ColumnsType<PipeNetEdge> = [
    {
      title: 'pipe_no',
      dataIndex: 'pipe_no',
      width: 120,
      render: (v: string) => (
        <span style={{ fontFamily: 'var(--font-mono, monospace)' }}>{v}</span>
      ),
    },
    {
      title: 'from',
      dataIndex: 'from_node_id',
      width: 140,
      render: (id: string) => nodeById.get(id)?.tag_number ?? id,
    },
    {
      title: 'to',
      dataIndex: 'to_node_id',
      width: 140,
      render: (id: string) => nodeById.get(id)?.tag_number ?? id,
    },
  ];

  return (
    <div data-testid="pipe-net-topology-page">
      <PageHeader
        title="PIPE_NET 拓扑"
        module="PIPE_NET"
        actions={
          <Space>
            <Button data-testid="pipe-net-validate">校验</Button>
            <Button
              type="primary"
              data-testid="pipe-net-export"
              onClick={() => onExport?.(graph)}
            >
              导出
            </Button>
          </Space>
        }
      />

      <Space direction="vertical" size={16} style={{ width: '100%' }}>
        <Card title="拓扑画布（V1 SVG 占位）" size="small">
          {graph.nodes.length === 0 ? (
            <Empty description="无节点" />
          ) : (
            <svg
              data-testid="pipe-net-canvas"
              viewBox="0 0 100 100"
              preserveAspectRatio="none"
              style={{ width: '100%', height: 240, background: 'var(--surface-bg-2, #F5F5F5)' }}
            >
              {graph.edges.map((e) => {
                const from = nodeById.get(e.from_node_id);
                const to = nodeById.get(e.to_node_id);
                if (!from || !to) return null;
                return (
                  <line
                    key={e.edge_id}
                    data-testid="pipe-net-edge"
                    x1={from.x}
                    y1={from.y}
                    x2={to.x}
                    y2={to.y}
                    stroke="var(--text-tertiary, #6B7280)"
                    strokeWidth={0.5}
                  />
                );
              })}
              {graph.nodes.map((n) => (
                <g key={n.node_id} data-testid="pipe-net-node" data-node-id={n.node_id}>
                  <circle cx={n.x} cy={n.y} r={3} fill="var(--state-checked, #10B981)" />
                  <text
                    x={n.x + 4}
                    y={n.y + 1}
                    fontSize="3"
                    fill="var(--text-primary, #1F2937)"
                  >
                    {n.tag_number}
                  </text>
                </g>
              ))}
            </svg>
          )}
        </Card>

        {validation.orphans.length > 0 && (
          <Alert
            type="warning"
            message={`孤立节点 ${validation.orphans.length} 个：${validation.orphans.join(', ')}`}
            data-testid="pipe-net-warning-orphans"
          />
        )}
        {validation.duplicate_tags.length > 0 && (
          <Alert
            type="error"
            message={`重复 tag ${validation.duplicate_tags.length} 个：${validation.duplicate_tags.join(', ')}`}
            data-testid="pipe-net-warning-dup"
          />
        )}

        <Card title={`节点 (${graph.nodes.length})`} size="small">
          <Table<PipeNetNode>
            rowKey="node_id"
            columns={nodeColumns}
            dataSource={graph.nodes}
            pagination={false}
            size="small"
          />
        </Card>

        <Card title={`管道边 (${graph.edges.length})`} size="small">
          <Table<PipeNetEdge>
            rowKey="edge_id"
            columns={edgeColumns}
            dataSource={graph.edges}
            pagination={false}
            size="small"
          />
        </Card>

        <Typography.Text type="secondary">
          V1 极简版：手写 SVG 渲染 + 基础校验；完整功能（reactflow 拖拽 / 自动布局 / 环路检测 / 序列化）留 PIPE_NET 完整版。
        </Typography.Text>
      </Space>
    </div>
  );
}

export default PipeNetTopologyPage;