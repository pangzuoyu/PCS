"""P4-3-1 管网拓扑模型单元测试。

覆盖（10 项验收）：
1. 基础拓扑合法：3 节点 + 3 边构成简单环 → PASS
2. 节点 ID 重复 → TopologyInputError
3. 边 ID 重复 → TopologyInputError
4. 边端点不存在 → TopologyInputError
5. 无 SOURCE / 无 SINK → TopologyInputError
6. 孤立子图（多连通分量）→ TopologyUnconnectedError
7. 节点数 > 500 → TopologyInputError
8. 边数 > 1000 → TopologyInputError
9. 边界节点 pressure_pa=None 且 type 非 SOURCE/SINK → TopologyInputError
10. 图连通性 BFS 实现验证：人造连通 / 隔离子图 / 单节点

拓扑校验只解算合法性，不触 DB（纯函数）；P4-3-2 求解器解算迭代不属本批。
"""
from __future__ import annotations

import uuid

import pytest

from app.services.pipe.pipe_chain_service import (
    PipeChainInput,
    PipeSegmentInput,
)
from app.services.pipe_net.topology_service import (
    EdgeInput,
    NodeInput,
    PipeNetworkInput,
    TopologyInputError,
    TopologyUnconnectedError,
    TopologyValidation,
    validate_topology,
)

# ---------------------------------------------------------------------------
# 辅助构造
# ---------------------------------------------------------------------------


def _liq_seg() -> PipeSegmentInput:
    """最小合法段（拓扑校验不进入链计算，字段不会被读到）。"""
    return PipeSegmentInput(
        fluid_phase="LIQUID",
        mass_flow_kg_s=1.0,
        density_kg_m3=1000.0,
        viscosity_pa_s=1.0e-3,
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.6e-5,
        length_m=10.0,
    )


def _chain(tag: str = "pipe-edge") -> PipeChainInput:
    """最小合法 PipeChainInput（EdgeInput 复用字段）。"""
    return PipeChainInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number=tag,
        segments=[_liq_seg()],
        inlet_pressure_pa=200_000.0,
    )


def _node(
    node_id: str,
    *,
    node_type: str = "JUNCTION",
    pressure_pa: float | None = None,
    demand_m3_s: float = 0.0,
    elevation_m: float = 0.0,
    upstream_equipment_type: str | None = None,
) -> NodeInput:
    return NodeInput(
        node_id=node_id,
        elevation_m=elevation_m,
        node_type=node_type,
        demand_m3_s=demand_m3_s,
        pressure_pa=pressure_pa,
        upstream_equipment_type=upstream_equipment_type,
    )


def _edge(
    edge_id: str,
    from_node: str,
    to_node: str,
) -> EdgeInput:
    return EdgeInput(
        edge_id=edge_id,
        from_node=from_node,
        to_node=to_node,
        pipe_chain=_chain(f"chain-{edge_id}"),
    )


def _simple_loop_input() -> PipeNetworkInput:
    """3 节点 + 3 边 → 简单环（src → mid1 → mid2 → src）。

    节点：
    - N-SRC (SOURCE, P=200kPa)
    - N-MID (JUNCTION, P=150kPa)
    - N-SNK (SINK, P=120kPa)
    边：
    - E-1: N-SRC → N-MID
    - E-2: N-MID → N-SNK
    - E-3: N-SNK → N-SRC（反向回流边，模拟循环）
    """
    nodes = [
        _node("N-SRC", node_type="SOURCE", pressure_pa=200_000.0),
        _node("N-MID", node_type="JUNCTION", pressure_pa=150_000.0),
        _node("N-SNK", node_type="SINK", pressure_pa=120_000.0),
    ]
    edges = [
        _edge("E-1", "N-SRC", "N-MID"),
        _edge("E-2", "N-MID", "N-SNK"),
        _edge("E-3", "N-SNK", "N-SRC"),
    ]
    return PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-001",
        nodes=nodes,
        edges=edges,
    )


# ---------------------------------------------------------------------------
# 1) 基础拓扑合法
# ---------------------------------------------------------------------------


def test_validate_topology_simple_loop_passes():
    """3 节点 + 3 边简单环 → validate_topology 返回 TopologyValidation 不抛错。"""
    inp = _simple_loop_input()
    result = validate_topology(inp)

    assert isinstance(result, TopologyValidation)
    assert result.node_count == 3
    assert result.edge_count == 3
    assert result.source_count == 1
    assert result.sink_count == 1
    assert result.is_connected is True
    assert result.components == 1


# ---------------------------------------------------------------------------
# 2) 节点 ID 重复
# ---------------------------------------------------------------------------


def test_duplicate_node_id_raises_input_error():
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-dup-node",
        nodes=[
            _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
            _node("N-A", node_type="SINK", pressure_pa=120_000.0),  # 重复
        ],
        edges=[_edge("E-1", "N-A", "N-A")],  # 自环避开端点校验
    )
    with pytest.raises(TopologyInputError, match="节点 ID 重复"):
        validate_topology(inp)


# ---------------------------------------------------------------------------
# 3) 边 ID 重复
# ---------------------------------------------------------------------------


def test_duplicate_edge_id_raises_input_error():
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-dup-edge",
        nodes=[
            _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
            _node("N-B", node_type="SINK", pressure_pa=120_000.0),
        ],
        edges=[
            _edge("E-1", "N-A", "N-B"),
            _edge("E-1", "N-A", "N-B"),  # 重复
        ],
    )
    with pytest.raises(TopologyInputError, match="边 ID 重复"):
        validate_topology(inp)


# ---------------------------------------------------------------------------
# 4) 边端点不存在
# ---------------------------------------------------------------------------


def test_edge_endpoint_missing_raises_input_error():
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-missing-endpoint",
        nodes=[
            _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
            _node("N-B", node_type="SINK", pressure_pa=120_000.0),
        ],
        edges=[_edge("E-1", "N-A", "N-X")],  # N-X 不存在
    )
    with pytest.raises(TopologyInputError, match="不存在"):
        validate_topology(inp)


# ---------------------------------------------------------------------------
# 5) 无 SOURCE / 无 SINK
# ---------------------------------------------------------------------------


def test_no_source_raises_input_error():
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-no-source",
        nodes=[
            _node("N-A", node_type="JUNCTION", pressure_pa=200_000.0),
            _node("N-B", node_type="SINK", pressure_pa=120_000.0),
        ],
        edges=[_edge("E-1", "N-A", "N-B")],
    )
    with pytest.raises(TopologyInputError, match="SOURCE"):
        validate_topology(inp)


def test_no_sink_raises_input_error():
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-no-sink",
        nodes=[
            _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
            _node("N-B", node_type="JUNCTION", pressure_pa=120_000.0),
        ],
        edges=[_edge("E-1", "N-A", "N-B")],
    )
    with pytest.raises(TopologyInputError, match="SINK"):
        validate_topology(inp)


# ---------------------------------------------------------------------------
# 6) 孤立子图（多连通分量）
# ---------------------------------------------------------------------------


def test_isolated_subgraph_raises_unconnected_error():
    """两独立子图：(A→B) + (C→D) → 2 连通分量 → TopologyUnconnectedError。"""
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-isolated",
        nodes=[
            _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
            _node("N-B", node_type="SINK", pressure_pa=120_000.0),
            _node("N-C", node_type="SOURCE", pressure_pa=180_000.0),
            _node("N-D", node_type="SINK", pressure_pa=110_000.0),
        ],
        edges=[
            _edge("E-1", "N-A", "N-B"),
            _edge("E-2", "N-C", "N-D"),
        ],
    )
    with pytest.raises(TopologyUnconnectedError, match="不连通"):
        validate_topology(inp)


# ---------------------------------------------------------------------------
# 7) 节点数 > 500
# ---------------------------------------------------------------------------


def test_node_count_exceeds_limit_raises_input_error():
    nodes = [
        _node("N-SRC", node_type="SOURCE", pressure_pa=200_000.0),
        _node("N-SNK", node_type="SINK", pressure_pa=120_000.0),
    ] + [
        _node(f"N-J{i}", node_type="JUNCTION", pressure_pa=150_000.0)
        for i in range(500)  # 共 502 节点
    ]
    # 维持连通：所有 J 节点串入一条链
    edges = [
        _edge("E-0", "N-SRC", "N-J0"),
        *[_edge(f"E-{i + 1}", f"N-J{i}", f"N-J{i + 1}") for i in range(499)],
        _edge("E-500", "N-J499", "N-SNK"),
    ]
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-too-many-nodes",
        nodes=nodes,
        edges=edges,
    )
    with pytest.raises(TopologyInputError, match="节点数"):
        validate_topology(inp)


# ---------------------------------------------------------------------------
# 8) 边数 > 1000
# ---------------------------------------------------------------------------


def test_edge_count_exceeds_limit_raises_input_error():
    """合法 3 节点，但边数 > 1000（自环堆积）。"""
    nodes = [
        _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
        _node("N-B", node_type="JUNCTION", pressure_pa=150_000.0),
        _node("N-C", node_type="SINK", pressure_pa=120_000.0),
    ]
    # 1001 自环 + 1 连通边 → 边数 1002
    edges = [_edge(f"E-{i}", "N-A", "N-A") for i in range(1001)] + [
        _edge("E-connect", "N-A", "N-B"),
        _edge("E-connect2", "N-B", "N-C"),
    ]
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-too-many-edges",
        nodes=nodes,
        edges=edges,
    )
    with pytest.raises(TopologyInputError, match="边数"):
        validate_topology(inp)


# ---------------------------------------------------------------------------
# 9) 边界节点 pressure_pa=None 且 type 非 SOURCE/SINK
# ---------------------------------------------------------------------------


def test_junction_without_pressure_pa_raises_input_error():
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-junction-no-p",
        nodes=[
            _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
            _node("N-B", node_type="JUNCTION", pressure_pa=None),  # 违规
            _node("N-C", node_type="SINK", pressure_pa=120_000.0),
        ],
        edges=[
            _edge("E-1", "N-A", "N-B"),
            _edge("E-2", "N-B", "N-C"),
        ],
    )
    with pytest.raises(TopologyInputError, match="pressure_pa"):
        validate_topology(inp)


def test_equipment_interface_without_pressure_pa_raises_input_error():
    """EQUIPMENT_INTERFACE 必须 pressure_pa（与 JUNCTION 同属"非边界自由类型"）。"""
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-equip-no-p",
        nodes=[
            _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
            _node(
                "N-EQ",
                node_type="EQUIPMENT_INTERFACE",
                pressure_pa=None,
                upstream_equipment_type="PUMP",
            ),
            _node("N-C", node_type="SINK", pressure_pa=120_000.0),
        ],
        edges=[
            _edge("E-1", "N-A", "N-EQ"),
            _edge("E-2", "N-EQ", "N-C"),
        ],
    )
    with pytest.raises(TopologyInputError, match="pressure_pa"):
        validate_topology(inp)


# ---------------------------------------------------------------------------
# 10) 图连通性 BFS 实现验证
# ---------------------------------------------------------------------------


def test_bfs_connectivity_full_graph_one_component():
    """4 节点 + 4 边全连通图 → components=1。"""
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-bfs-full",
        nodes=[
            _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
            _node("N-B", node_type="JUNCTION", pressure_pa=180_000.0),
            _node("N-C", node_type="JUNCTION", pressure_pa=150_000.0),
            _node("N-D", node_type="SINK", pressure_pa=120_000.0),
        ],
        edges=[
            _edge("E-1", "N-A", "N-B"),
            _edge("E-2", "N-B", "N-C"),
            _edge("E-3", "N-C", "N-D"),
            _edge("E-4", "N-A", "N-C"),  # 旁路
        ],
    )
    result = validate_topology(inp)
    assert result.components == 1
    assert result.is_connected is True


def test_bfs_connectivity_isolated_node_detected():
    """5 节点：4 全连通 + 1 孤立 → components=2 → raise TopologyUnconnectedError。"""
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-bfs-iso",
        nodes=[
            _node("N-A", node_type="SOURCE", pressure_pa=200_000.0),
            _node("N-B", node_type="JUNCTION", pressure_pa=180_000.0),
            _node("N-C", node_type="JUNCTION", pressure_pa=150_000.0),
            _node("N-D", node_type="SINK", pressure_pa=120_000.0),
            _node("N-ISO", node_type="JUNCTION", pressure_pa=100_000.0),  # 孤立
        ],
        edges=[
            _edge("E-1", "N-A", "N-B"),
            _edge("E-2", "N-B", "N-C"),
            _edge("E-3", "N-C", "N-D"),
        ],
    )
    with pytest.raises(TopologyUnconnectedError):
        validate_topology(inp)


def test_bfs_handles_single_source_sink_pair_minimal_graph():
    """极小图：2 节点 (SOURCE + SINK) + 1 边 → components=1。"""
    inp = PipeNetworkInput(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        source_stream_id=uuid.uuid4(),
        tag_number="net-min",
        nodes=[
            _node("N-SRC", node_type="SOURCE", pressure_pa=200_000.0),
            _node("N-SNK", node_type="SINK", pressure_pa=120_000.0),
        ],
        edges=[_edge("E-1", "N-SRC", "N-SNK")],
    )
    result = validate_topology(inp)
    assert result.components == 1
    assert result.is_connected is True
    assert result.node_count == 2
    assert result.edge_count == 1