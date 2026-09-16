/**
 * PIPE_NET 模块类型（P45-3-6 / Task 33）。
 *
 * SPEC §7.11.3：
 * - 节点：设备 / 管段连接点
 * - 边：管道（连接两节点）
 * - 校验：环路 / 孤立点 / 命名重复
 *
 * TODO(api-migration): V1 极简版前端 mock props shape；P5-1 PipeNetTopology
 * 端点冻结后由 src/types/api.d.ts 替换。
 */

export type PipeNetNodeKind = 'EQUIPMENT' | 'JUNCTION' | 'INLET' | 'OUTLET';

export interface PipeNetNode {
  node_id: string;
  tag_number: string;
  label: string;
  kind: PipeNetNodeKind;
  x: number;          // 画布坐标 (0..100)
  y: number;
}

export interface PipeNetEdge {
  edge_id: string;
  pipe_no: string;
  from_node_id: string;
  to_node_id: string;
}

export interface PipeNetGraph {
  nodes: PipeNetNode[];
  edges: PipeNetEdge[];
}

export interface PipeNetValidation {
  orphans: string[];          // 孤立节点 ID 列表
  duplicate_tags: string[];   // 重复 tag 列表
  cycles: string[][];         // 环路上各节点 ID（每个环一个数组）
}