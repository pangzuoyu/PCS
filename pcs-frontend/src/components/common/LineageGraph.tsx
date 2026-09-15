/**
 * LineageGraph — 数据血缘可视化（P45-1-10 / Task 15）。
 *
 * SPEC §6.6 + plan P45-1-10：
 * - 节点类型：stream/equipment/record/deliverable/assumed（颜色区分）
 * - 边类型：reference/calculation/manual_override/estimate/device_transformation
 * - 交互：direction（upstream 向上追溯 / downstream 向下追溯）切换
 *   + centerRecord 居中 + 工具栏 + 节点点击
 * - 哈希不匹配边红色高亮
 *
 * Props（SPEC 锁定）：
 *   centerRecord: string
 *   direction: 'upstream' | 'downstream'
 *   data: { nodes, edges }
 *   onNodeClick?: (nodeId: string) => void
 *
 * 实现：轻量 SVG（reactflow 体积过大，契约层一致即可后续替换）。
 */
import { useMemo } from 'react';
import { Card, Radio, Space, Typography } from 'antd';

export type LineageNodeKind =
  | 'stream'
  | 'status_point'
  | 'equipment'
  | 'record'
  | 'deliverable'
  | 'assumed';

export interface LineageNode {
  id: string;
  kind: LineageNodeKind;
  label: string;
  /** 标记「假设」节点（kind=assumed 冗余字段，方便上游过滤） */
  is_assumed?: boolean;
}

export interface LineageEdge {
  source: string;
  target: string;
  kind: 'reference' | 'calculation' | 'manual_override' | 'estimate' | 'device_transformation';
  /** 哈希不匹配 → 红色高亮 */
  hash_mismatch?: boolean;
  /** 边标签（仅 device_transformation 常用，如设备位号） */
  label?: string;
}

interface Data {
  nodes: LineageNode[];
  edges: LineageEdge[];
}

interface Props {
  centerRecord: string;
  direction: 'upstream' | 'downstream';
  data: Data;
  onNodeClick?: (nodeId: string) => void;
}

const KIND_COLOR: Record<LineageNodeKind, string> = {
  stream: 'var(--color-primary, #2F81F7)',
  status_point: 'var(--state-info, #54AEFF)',
  equipment: 'var(--state-change-pending, #A371F7)',
  record: 'var(--state-checked, #3FB950)',
  deliverable: 'var(--state-stale, #D29922)',
  assumed: 'var(--state-stale, #D29922)',
};

const EDGE_STYLE: Record<LineageEdge['kind'], { dash: string; width: number }> = {
  reference: { dash: '0', width: 1 },
  calculation: { dash: '4 2', width: 1 },
  manual_override: { dash: '1 3', width: 1 },
  estimate: { dash: '6 2 1 2', width: 1 },
  device_transformation: { dash: '0', width: 3 },
};

/** BFS 层（按 direction 决定方向）；返回节点深度 map + 边的有效子集 */
function computeLayout(
  centerId: string,
  direction: 'upstream' | 'downstream',
  data: Data,
): { depth: Map<string, number>; edges: LineageEdge[] } {
  const nodeMap = new Map(data.nodes.map((n) => [n.id, n]));
  if (!nodeMap.has(centerId)) {
    return { depth: new Map(), edges: [] };
  }

  // upstream：边的 target→source（向中心「来源」遍历）
  // downstream：边的 source→target（向中心「去向」遍历）
  const getNeighbors = (id: string): string[] => {
    const ns: string[] = [];
    for (const e of data.edges) {
      if (direction === 'upstream' && e.target === id) ns.push(e.source);
      if (direction === 'downstream' && e.source === id) ns.push(e.target);
    }
    return ns;
  };

  const depth = new Map<string, number>();
  depth.set(centerId, 0);
  const queue: string[] = [centerId];
  while (queue.length > 0) {
    const cur = queue.shift()!;
    const d = depth.get(cur)!;
    for (const nb of getNeighbors(cur)) {
      if (!depth.has(nb)) {
        depth.set(nb, d + 1);
        queue.push(nb);
      }
    }
  }

  // 仅保留两个端点都在 layout 内的边
  const visibleEdges = data.edges.filter(
    (e) => depth.has(e.source) && depth.has(e.target),
  );
  return { depth, edges: visibleEdges };
}

const NODE_W = 120;
const NODE_H = 40;
const COL_GAP = 60;
const ROW_GAP = 60;
const PADDING = 24;

export function LineageGraph({ centerRecord, direction, data, onNodeClick }: Props): JSX.Element {
  const { depth, edges } = useMemo(
    () => computeLayout(centerRecord, direction, data),
    [centerRecord, direction, data],
  );

  // 按 layer 分组 → 决定 y；同层横向铺开（每层 col 从 0 递增）
  const layers = useMemo(() => {
    const byDepth = new Map<number, string[]>();
    for (const [id, d] of depth.entries()) {
      const arr = byDepth.get(d) ?? [];
      arr.push(id);
      byDepth.set(d, arr);
    }
    return byDepth;
  }, [depth]);

  // 节点位置
  const positions = useMemo(() => {
    const map = new Map<string, { x: number; y: number }>();
    const maxRows = Math.max(...Array.from(layers.values()).map((a) => a.length), 1);
    const height = maxRows * (NODE_H + ROW_GAP) + PADDING;
    for (const [d, ids] of layers.entries()) {
      ids.forEach((id, i) => {
        const x = PADDING + d * (NODE_W + COL_GAP);
        const y =
          PADDING +
          i * (NODE_H + ROW_GAP) -
          ((ids.length - 1) * (NODE_H + ROW_GAP)) / 2 +
          height / 2 -
          NODE_H / 2;
        map.set(id, { x, y });
      });
    }
    return { map, width: layers.size * (NODE_W + COL_GAP), height };
  }, [layers]);

  const nodeMap = new Map(data.nodes.map((n) => [n.id, n]));

  return (
    <Card
      data-testid="lineage-graph"
      title={
        <Space>
          <Typography.Text strong>数据血缘</Typography.Text>
          <Typography.Text type="secondary">
            {direction === 'upstream' ? '上游追溯' : '下游追溯'}
          </Typography.Text>
        </Space>
      }
      extra={
        <Radio.Group
          data-testid="direction-toggle"
          value={direction}
          // 注意：direction 由调用方控制（受控）；此组件不维护可变 state
          // 只读展示当前 direction
          disabled
          size="small"
        >
          <Radio.Button value="upstream">向上追溯</Radio.Button>
          <Radio.Button value="downstream">向下追溯</Radio.Button>
        </Radio.Group>
      }
    >
      {/* 图例（左上） */}
      <Space
        data-testid="lineage-legend"
        size={12}
        wrap
        style={{ marginBottom: 12 }}
      >
        {Object.entries(KIND_COLOR).map(([kind, color]) => (
          <Space key={kind} size={4}>
            <span
              aria-hidden="true"
              style={{
                display: 'inline-block',
                width: 12,
                height: 12,
                background: color,
                borderRadius: 'var(--radius-sm, 2px)',
              }}
            />
            <Typography.Text type="secondary" style={{ fontSize: 12 }}>
              {kind}
            </Typography.Text>
          </Space>
        ))}
      </Space>

      {/* 画布 */}
      <div
        data-testid="lineage-canvas"
        style={{ overflow: 'auto', maxHeight: 480, border: '1px solid var(--border-subtle, #D0D7DE)' }}
      >
        <svg
          width={Math.max(positions.width + 2 * PADDING, 600)}
          height={Math.max(positions.height + 2 * PADDING, 200)}
          role="img"
          aria-label="lineage-graph"
        >
          {/* 边 */}
          {edges.map((e, idx) => {
            const s = positions.map.get(e.source);
            const t = positions.map.get(e.target);
            if (!s || !t) return null;
            const x1 = s.x + NODE_W;
            const y1 = s.y + NODE_H / 2;
            const x2 = t.x;
            const y2 = t.y + NODE_H / 2;
            const style = EDGE_STYLE[e.kind];
            const stroke = e.hash_mismatch ? 'var(--state-check-rejected, #F85149)' : 'var(--text-tertiary, #6E7781)';
            return (
              <line
                key={`edge-${idx}`}
                data-testid="lineage-edge"
                data-hash-mismatch={e.hash_mismatch ? 'true' : 'false'}
                data-edge-kind={e.kind}
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                stroke={stroke}
                strokeWidth={style.width}
                strokeDasharray={e.hash_mismatch ? '0' : style.dash}
              />
            );
          })}

          {/* 节点 */}
          {Array.from(positions.map.entries()).map(([id, p]) => {
            const n = nodeMap.get(id);
            if (!n) return null;
            const isCenter = id === centerRecord;
            const fill = KIND_COLOR[n.kind];
            return (
              <g
                key={id}
                data-testid="lineage-node"
                data-node-id={id}
                data-node-kind={n.kind}
                data-is-center={isCenter ? 'true' : 'false'}
                style={{ cursor: 'pointer' }}
                onClick={() => onNodeClick?.(id)}
              >
                <rect
                  x={p.x}
                  y={p.y}
                  width={NODE_W}
                  height={NODE_H}
                  rx={4}
                  fill={isCenter ? fill : 'var(--surface-bg, #FFFFFF)'}
                  stroke={fill}
                  strokeWidth={isCenter ? 3 : 2}
                />
                <text
                  x={p.x + NODE_W / 2}
                  y={p.y + NODE_H / 2 + 4}
                  textAnchor="middle"
                  fontSize={12}
                  fill={isCenter ? '#FFFFFF' : 'var(--text-primary, #1F2328)'}
                >
                  {n.label}
                </text>
              </g>
            );
          })}
        </svg>
      </div>

      <Typography.Text type="secondary" style={{ display: 'block', marginTop: 8 }} data-testid="lineage-stats">
        节点 {positions.map.size} · 边 {edges.length} · 方向 {direction}
      </Typography.Text>
    </Card>
  );
}

export default LineageGraph;