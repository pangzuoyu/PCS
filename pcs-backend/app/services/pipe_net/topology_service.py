"""P4-3-1：管网拓扑模型（节点 / 边 / 图结构；pipe_chain 复用为边）。

设计要点：
- dataclass(frozen=True) 不可变；与 P4-2-5 PipeChainInput 对齐。
- ``validate_topology`` 纯函数：只校验合法性，不进入网络解算（解算归 P4-3-2）。
- 图连通性：迭代 BFS（``collections.deque``），O(V+E)；规避递归栈深度。
- 复用 P4-2-5 ``PipeChainInput`` 作为边载体——service 只读，不触 DB。

校验规则（10 项）：
1. node_id 唯一
2. edge_id 唯一
3. edge 端点必须存在
4. ≥1 SOURCE + ≥1 SINK
5. 节点全连通（无孤立子图）
6. nodes ≤ 500（工程上限，防爆栈）
7. edges ≤ 1000
8. 边界节点 pressure_pa=None 且 type 非 SOURCE/SINK → raise
   （JUNCTION / EQUIPMENT_INTERFACE 视为非自由边界，pressure_pa 必须给定）
9. SOURCE / SINK 的 pressure_pa 允许 None（视为开放边界，外部条件决定）
10. BFS 实现验证：连通性算法能正确识别多连通分量

边界节点压力约定（与 SUP-008 网络水力学惯例对齐）：
- SOURCE / SINK：管网与外部系统的接口，pressure_pa 可由调用方给定（泵吸入口 /
  下游罐压）；允许 None 表示开放边界。
- EQUIPMENT_INTERFACE：设备连接点，pressure_pa 由上游设备（PUMP/PSV/...）
  解算后回填；输入必给。
- JUNCTION：纯汇合点，pressure_pa 由网络解算得出；输入必给（初值或外部给）。

落库：本批不实现（解算未做，结果无意义）；P4-0-2 已建 pipe_network_results 表
（``input_json``/``output_json`` JSONB + ``network_id`` PK + TaggedRecordMixin 全
字段），拓扑校验通过后 input 序列化为 input_json / TopologyValidation 入
output_json 直接落库即可（字段无缺失，零迁移）。
"""
from __future__ import annotations

import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Literal

from app.services.exceptions import PcsError
from app.services.pipe.pipe_chain_service import PipeChainInput

# ---------------------------------------------------------------------------
# 节点类型字面量
# ---------------------------------------------------------------------------

NodeType = Literal["JUNCTION", "SOURCE", "SINK", "EQUIPMENT_INTERFACE"]

# 工程上限（节点 / 边）—— 防递归栈爆 + 防内存溢出
_MAX_NODES: int = 500
_MAX_EDGES: int = 1000

# 边界节点（pressure_pa 可 None）— 仅 SOURCE / SINK
_FREE_BOUNDARY_TYPES: frozenset[str] = frozenset({"SOURCE", "SINK"})


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class TopologyInputError(PcsError):
    """管网拓扑输入非法（结构错误）。

    触发场景：
    - 节点 / 边 ID 重复
    - 边端点不存在
    - 缺 SOURCE 或 SINK
    - 节点 / 边数超工程上限
    - 非 SOURCE/SINK 节点 pressure_pa 缺失
    """

    code = "TOPOLOGY_INPUT_ERROR"
    status = 422


class TopologyUnconnectedError(PcsError):
    """管网拓扑存在孤立子图（多连通分量）。

    触发场景：
    - 至少一组节点不与其他节点连通
    """

    code = "TOPOLOGY_UNCONNECTED"
    status = 422


# ---------------------------------------------------------------------------
# 输入 / 输出 dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class NodeInput:
    """管网节点（汇合点 / 设备接口 / 边界）。

    Attributes:
        node_id: 业务标识（如 N-001；项目内唯一）
        elevation_m: 标高 (m)
        node_type: 节点类型 — JUNCTION / SOURCE / SINK / EQUIPMENT_INTERFACE
        demand_m3_s: 净需求 (m³/s；SOURCE 负、SINK 正、JUNCTION 0)
        pressure_pa: 节点压力 (Pa；SOURCE/SINK 可 None 视为开放边界；
            其他类型必给)
        upstream_equipment_type: 设备类型，仅 EQUIPMENT_INTERFACE 填写
            （PUMP / PSV / CONTROL_VALVE / ...）
    """

    node_id: str
    elevation_m: float
    node_type: NodeType
    demand_m3_s: float = 0.0
    pressure_pa: float | None = None
    upstream_equipment_type: str | None = None


@dataclass(frozen=True)
class EdgeInput:
    """管网边（pipe_chain 或单段管道）。

    Attributes:
        edge_id: 业务标识（如 E-001；项目内唯一）
        from_node: 源节点 node_id
        to_node: 目标节点 node_id
        pipe_chain: 边载体（复用 P4-2-5 PipeChainInput）— service 层只读
    """

    edge_id: str
    from_node: str
    to_node: str
    pipe_chain: PipeChainInput


@dataclass(frozen=True)
class PipeNetworkInput:
    """管网总输入。

    Attributes:
        project_id: 项目 UUID
        workspace_id: 工作区 UUID
        source_stream_id: 入口流 UUID（与 P4-2-5 一致；CHECKED 守卫在 API 层）
        tag_number: 管网位号（pipe-net-001）
        nodes: 节点列表（1..500）
        edges: 边列表（0..1000）
        tolerance_pa: 求解收敛容差 (Pa；P4-3-2 使用)
        max_iterations: 求解最大迭代次数（P4-3-2 使用）
    """

    project_id: uuid.UUID
    workspace_id: uuid.UUID
    source_stream_id: uuid.UUID
    tag_number: str
    nodes: list[NodeInput] = field(default_factory=list)
    edges: list[EdgeInput] = field(default_factory=list)
    tolerance_pa: float = 100.0
    max_iterations: int = 100


@dataclass(frozen=True)
class TopologyValidation:
    """拓扑校验结果（不解算）。

    Attributes:
        node_count: 节点总数
        edge_count: 边总数
        source_count: SOURCE 节点数
        sink_count: SINK 节点数
        is_connected: 全图是否单连通分量
        components: 连通分量数（=1 表示全连通）
    """

    node_count: int
    edge_count: int
    source_count: int
    sink_count: int
    is_connected: bool
    components: int


# ---------------------------------------------------------------------------
# 内部工具：连通性（BFS）
# ---------------------------------------------------------------------------


def _count_components(
    node_ids: list[str], edges: list[EdgeInput]
) -> int:
    """迭代 BFS 数连通分量（O(V+E)）。

    选择 BFS 而非 DFS 的理由：
    - 迭代式，无递归栈深度限制（500 节点递归仍安全，但 BFS 更易推理）。
    - ``collections.deque`` 是 stdlib，零新依赖。
    - 顺序确定性：先按节点列表顺序入队，回放稳定。

    Union-Find 也可；但 P4-3-2 求解器还会再走邻接表（Jacobian 组装需要按边遍历），
    BFS 一次建邻接表与后续求解共享同一表示，避免重复实现。
    """
    adj: dict[str, set[str]] = defaultdict(set)
    for e in edges:
        adj[e.from_node].add(e.to_node)
        adj[e.to_node].add(e.from_node)

    visited: set[str] = set()
    components = 0
    for nid in node_ids:
        if nid in visited:
            continue
        components += 1
        queue: deque[str] = deque([nid])
        visited.add(nid)
        while queue:
            u = queue.popleft()
            for v in adj[u]:
                if v not in visited:
                    visited.add(v)
                    queue.append(v)
    return components


# ---------------------------------------------------------------------------
# 入口：validate_topology
# ---------------------------------------------------------------------------


def validate_topology(inp: PipeNetworkInput) -> TopologyValidation:
    """管网拓扑合法性校验（不解算流量 / 压力）。

    Raises:
        TopologyInputError: 输入越界 / ID 重复 / 端点缺失 / 缺 SOURCE/SINK /
            非 SOURCE/SINK 节点无 pressure_pa。
        TopologyUnconnectedError: 至少一边两端未连通（多连通分量）。

    Returns:
        TopologyValidation：节点 / 边 / SOURCE / SINK 计数 + 连通分量数。
    """
    # 6) 节点数上限
    if len(inp.nodes) > _MAX_NODES:
        raise TopologyInputError(
            f"节点数 {len(inp.nodes)} 超过工程上限 {_MAX_NODES}",
            details={"node_count": len(inp.nodes), "limit": _MAX_NODES},
        )

    # 7) 边数上限
    if len(inp.edges) > _MAX_EDGES:
        raise TopologyInputError(
            f"边数 {len(inp.edges)} 超过工程上限 {_MAX_EDGES}",
            details={"edge_count": len(inp.edges), "limit": _MAX_EDGES},
        )

    # 1) node_id 唯一
    seen_nodes: set[str] = set()
    for n in inp.nodes:
        if n.node_id in seen_nodes:
            raise TopologyInputError(
                f"节点 ID 重复：{n.node_id}",
                details={"node_id": n.node_id},
            )
        seen_nodes.add(n.node_id)

    # 3) edge 端点必须存在（在 edge_id 检查前：先确认所有端点可解）
    for e in inp.edges:
        if e.from_node not in seen_nodes:
            raise TopologyInputError(
                f"边 {e.edge_id} 起点 {e.from_node} 不存在",
                details={"edge_id": e.edge_id, "endpoint": e.from_node},
            )
        if e.to_node not in seen_nodes:
            raise TopologyInputError(
                f"边 {e.edge_id} 终点 {e.to_node} 不存在",
                details={"edge_id": e.edge_id, "endpoint": e.to_node},
            )

    # 2) edge_id 唯一
    seen_edges: set[str] = set()
    for e in inp.edges:
        if e.edge_id in seen_edges:
            raise TopologyInputError(
                f"边 ID 重复：{e.edge_id}",
                details={"edge_id": e.edge_id},
            )
        seen_edges.add(e.edge_id)

    # 4) ≥1 SOURCE + ≥1 SINK
    source_count = sum(1 for n in inp.nodes if n.node_type == "SOURCE")
    sink_count = sum(1 for n in inp.nodes if n.node_type == "SINK")
    if source_count == 0:
        raise TopologyInputError(
            "至少需要 1 个 SOURCE 节点",
            details={"source_count": 0},
        )
    if sink_count == 0:
        raise TopologyInputError(
            "至少需要 1 个 SINK 节点",
            details={"sink_count": 0},
        )

    # 8) 边界节点 pressure_pa 语义：非 SOURCE/SINK 必须给定
    for n in inp.nodes:
        if n.pressure_pa is None and n.node_type not in _FREE_BOUNDARY_TYPES:
            raise TopologyInputError(
                (
                    f"节点 {n.node_id} type={n.node_type} 必须给定 pressure_pa "
                    f"（仅 SOURCE/SINK 可为空，视为开放边界）"
                ),
                details={
                    "node_id": n.node_id,
                    "node_type": n.node_type,
                },
            )

    # 5) 图连通性（BFS）
    components = _count_components(
        [n.node_id for n in inp.nodes], inp.edges
    )
    if components > 1:
        raise TopologyUnconnectedError(
            f"管网不连通：{components} 个连通分量",
            details={"components": components},
        )

    return TopologyValidation(
        node_count=len(inp.nodes),
        edge_count=len(inp.edges),
        source_count=source_count,
        sink_count=sink_count,
        is_connected=True,
        components=components,
    )