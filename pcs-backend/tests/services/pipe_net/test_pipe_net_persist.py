"""P4-3-3 管网求解落库 helper + outlet_stream 测试。

覆盖：
1. 落库 roundtrip：solve → persist → SELECT → input_json/output_json 全字段保留
2. finalize_calc_record 收口：record_hash 16 hex + DataLineage 一条
3. outlet_stream helper 复用：source_type="PIPE_NET_CALCULATED" →
   upstream_equipment_type="PIPE_NET" + sign_status=DRAFT
4. project_id 一致性校验：PIPE_NET.project_id != outlet.project_id → raise
5. 不 commit 验证：调用后 session.dirty 仍有未提交对象

DB 约定（与 P4-2-5 test_pipe_chain.py 一致）：落库测试仅 pcs_test 库运行
（fixture 需外键 Project/Workspace/Stream CHECKED；SQLite in-memory + shim
不保证 finalize_calc_record 全功能）。
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import dispose_engines_async, get_async_session_factory
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace
from app.models.system import DataLineage
from app.services.outlet_stream import OutletStreamProjectMismatchError
from app.services.pipe.pipe_chain_service import (
    PipeChainInput,
    PipeSegmentInput,
)
from app.services.pipe_net import (
    EdgeInput,
    NodeInput,
    PipeNetworkInput,
    SolverConfig,
    persist_pipe_network_result,
    solve_network,
)

# ---------------------------------------------------------------------------
# 守卫：仅 pcs_test 库允许（与 P4-2-5 一致）
# ---------------------------------------------------------------------------

_ONLY_PCS_TEST = pytest.mark.skipif(
    not get_settings().database_url.rstrip("/").endswith("pcs_test"),
    reason="落库 roundtrip 仅允许 pcs_test 库；"
    "需 DATABASE_URL=postgresql+psycopg://pcs:pcs_dev@localhost:5432/pcs_test",
)


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine() -> None:
    """每次用例 reset 全局 async engine（绑定当前 event loop）。"""
    await dispose_engines_async()
    yield
    await dispose_engines_async()


# ---------------------------------------------------------------------------
# 辅助构造（最小可解 4 节点 5 边等 R 环）
# ---------------------------------------------------------------------------


def _liq_seg() -> PipeSegmentInput:
    """最小合法液相段（求解器会重算 mass_flow）。"""
    return PipeSegmentInput(
        fluid_phase="LIQUID",
        mass_flow_kg_s=10.0,  # 占位
        density_kg_m3=1000.0,
        viscosity_pa_s=1.0e-3,
        pipe_diameter_m=0.05,
        pipe_roughness_m=4.6e-5,
        length_m=10.0,
    )


def _chain(tag: str) -> PipeChainInput:
    """单段均匀 chain。project/workspace/source 在 _make_inp 里覆盖。"""
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
    pressure_pa: float | None = 150_000.0,
    demand_m3_s: float = 0.0,
    elevation_m: float = 0.0,
) -> NodeInput:
    return NodeInput(
        node_id=node_id,
        elevation_m=elevation_m,
        node_type=node_type,  # type: ignore[arg-type]
        demand_m3_s=demand_m3_s,
        pressure_pa=pressure_pa,
    )


def _edge(
    edge_id: str,
    from_node: str,
    to_node: str,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
) -> EdgeInput:
    chain = PipeChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number=f"chain-{edge_id}",
        segments=[_liq_seg()],
        inlet_pressure_pa=200_000.0,
    )
    return EdgeInput(
        edge_id=edge_id,
        from_node=from_node,
        to_node=to_node,
        pipe_chain=chain,
    )


def _two_loop_inp(
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
) -> PipeNetworkInput:
    """4 节点 + 5 边 = 2 个独立环（与 P4-3-2 solver 测试同拓扑）。"""
    nodes = [
        _node("N1", node_type="SOURCE", pressure_pa=200_000.0),
        _node("N2"),
        _node("N3"),
        _node("N4", node_type="SINK", demand_m3_s=0.02),
    ]
    edges = [
        _edge("E1", "N1", "N2", project_id, workspace_id, source_stream_id),
        _edge("E2", "N2", "N3", project_id, workspace_id, source_stream_id),
        _edge("E3", "N1", "N3", project_id, workspace_id, source_stream_id),
        _edge("E4", "N3", "N4", project_id, workspace_id, source_stream_id),
        _edge("E5", "N2", "N4", project_id, workspace_id, source_stream_id),
    ]
    return PipeNetworkInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number="net-rt-001",
        nodes=nodes,
        edges=edges,
    )


async def _make_project_workspace_stream(
    db: AsyncSession,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    *,
    stream_project_id: uuid.UUID | None = None,
) -> None:
    """最小 Project + Workspace + Stream 构造。

    stream_project_id：源流所属项目（默认 = project_id；显式可造 mismatch）。
    """
    sp_id = stream_project_id or project_id
    # 顺序：Workspace（project_id NULL）先 flush → Project.workspace_id 引用
    # flush → Workspace.project_id 回填 flush → Stream
    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type="FORMAL",
        project_id=None,  # 先 NULL；Project 落库后回填（FK 可空）
        name="test",
    )
    db.add(ws)
    await db.flush()
    proj = Project(
        project_id=project_id,
        project_no=f"P-{project_id.hex[:8]}",
        project_name="test",
        owner_company="test",
        location="test",
        project_type="test",
        design_phase="BASIC",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.flush()
    ws.project_id = project_id
    await db.flush()
    stream = Stream(
        stream_id=source_stream_id,
        project_id=sp_id,
        workspace_id=workspace_id,
        stream_name=f"S-{source_stream_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        sign_status=StreamSignStatus.CHECKED,
        approval_depth=1,
        press=200_000.0,
        temp=298.15,
        composition_json={"C1": 1.0},
    )
    db.add(stream)
    await db.flush()


async def _make_project_workspace(
    db: AsyncSession,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
) -> None:
    """仅 Project + Workspace 构造（无 Stream；用于造 mismatch 场景的"另一 project"）。"""
    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type="FORMAL",
        project_id=None,
        name="test",
    )
    db.add(ws)
    await db.flush()
    proj = Project(
        project_id=project_id,
        project_no=f"P-{project_id.hex[:8]}",
        project_name="test",
        owner_company="test",
        location="test",
        project_type="test",
        design_phase="BASIC",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.flush()
    ws.project_id = project_id
    await db.flush()


# ---------------------------------------------------------------------------
# 1) 落库 roundtrip
# ---------------------------------------------------------------------------


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_persist_pipe_network_result_roundtrip_pcs_test():
    """P4-3-3：solve → persist → SELECT → input_json/output_json 全字段保留。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    inp = _two_loop_inp(project_id, workspace_id, source_stream_id)
    config = SolverConfig(tolerance_m3_s=1e-6, max_iterations=100)
    result = solve_network(inp, config)

    factory = get_async_session_factory()
    async with factory() as db:
        await _make_project_workspace_stream(
            db, project_id, workspace_id, source_stream_id
        )
        row, outlet = await persist_pipe_network_result(db, inp, result)
        await db.commit()
        net_id = row.network_id
        outlet_id = outlet.stream_id

    # SELECT pipe_network_results 全字段
    async with factory() as db:
        rs = await db.execute(
            text(
                "SELECT network_id, project_id, workspace_id, tag_number, "
                "       record_hash, input_json, output_json, sign_status "
                "FROM pipe_network_results WHERE network_id = :pk"
            ),
            {"pk": str(net_id)},
        )
        rec = rs.mappings().one()
    got = dict(rec)

    # 主键 / 三元组（project/workspace/tag）
    assert str(got["network_id"]) == str(net_id)
    assert str(got["project_id"]) == str(project_id)
    assert str(got["workspace_id"]) == str(workspace_id)
    assert got["tag_number"] == "net-rt-001"
    # sign_status 默认 DRAFT（TaggedRecordMixin 默认）
    assert got["sign_status"] == "DRAFT"
    # input_json 包含 source_stream_id / tag_number / nodes / edges（dataclass 序列）
    ij = got["input_json"]
    assert isinstance(ij, dict)
    assert str(ij["source_stream_id"]) == str(source_stream_id)
    assert ij["tag_number"] == "net-rt-001"
    assert len(ij["nodes"]) == 4
    assert len(ij["edges"]) == 5
    # output_json 包含 solver 输出字段
    oj = got["output_json"]
    assert isinstance(oj, dict)
    assert oj["converged"] is True
    assert oj["iterations"] >= 1
    assert len(oj["edge_flows"]) == 5
    assert len(oj["node_pressures"]) == 4
    assert oj["confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert oj["check_result"] in ("PASS", "WARNING", "FAIL")
    # outlet_stream 真实落库
    async with factory() as db:
        sr = await db.execute(
            text(
                "SELECT stream_id, project_id, source_type, upstream_equipment_type, "
                "       sign_status FROM streams WHERE stream_id = :pk"
            ),
            {"pk": str(outlet_id)},
        )
        srow = sr.mappings().one()
    assert str(srow["project_id"]) == str(project_id)
    assert srow["source_type"] == "PIPE_NET_CALCULATED"
    assert srow["upstream_equipment_type"] == "PIPE_NET"
    assert srow["sign_status"] == "DRAFT"


# ---------------------------------------------------------------------------
# 2) finalize_calc_record 收口：record_hash 16 hex + DataLineage 一条
# ---------------------------------------------------------------------------


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_persist_finalizes_record_hash_and_data_lineage_pcs_test():
    """P4-3-3：record_hash 16 hex + DataLineage 一条（source="CALC"）。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    inp = _two_loop_inp(project_id, workspace_id, source_stream_id)
    config = SolverConfig(tolerance_m3_s=1e-6, max_iterations=100)
    result = solve_network(inp, config)

    factory = get_async_session_factory()
    async with factory() as db:
        await _make_project_workspace_stream(
            db, project_id, workspace_id, source_stream_id
        )
        row, _ = await persist_pipe_network_result(db, inp, result)
        await db.commit()
        net_id = row.network_id
        record_hash = row.record_hash

    # record_hash 16 hex（与 finalize_calc_record._HASH_PREFIX 一致）
    assert len(record_hash) == 16
    assert all(c in "0123456789abcdef" for c in record_hash)

    # DataLineage 一条：source=CALC, source_ref_type="Stream",
    # source_ref_id=source_stream_id
    async with factory() as db:
        lr = await db.execute(
            select(DataLineage).where(
                DataLineage.record_type == "PipeNetworkResult",
                DataLineage.record_id == net_id,
            )
        )
        rows = list(lr.scalars().all())
    assert len(rows) == 1
    assert rows[0].source == "CALC"
    assert rows[0].source_ref_type == "Stream"
    assert str(rows[0].source_ref_id) == str(source_stream_id)


# ---------------------------------------------------------------------------
# 3) outlet_stream helper 复用契约
# ---------------------------------------------------------------------------


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_persist_outlet_stream_helper_contract_pcs_test():
    """P4-3-3：source_type=PIPE_NET_CALCULATED → upstream_equipment_type=PIPE_NET
    + sign_status=DRAFT（P4-1-3 helper Literal 扩展向后兼容）。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    inp = _two_loop_inp(project_id, workspace_id, source_stream_id)
    config = SolverConfig(tolerance_m3_s=1e-6, max_iterations=100)
    result = solve_network(inp, config)

    factory = get_async_session_factory()
    async with factory() as db:
        await _make_project_workspace_stream(
            db, project_id, workspace_id, source_stream_id
        )
        _, outlet = await persist_pipe_network_result(db, inp, result)
        await db.commit()
        outlet_id = outlet.stream_id
        outlet_source_type = outlet.source_type
        outlet_upstream_equip = outlet.upstream_equipment_type
        outlet_sign = outlet.sign_status
        outlet_properties = outlet.stream_properties_json
        outlet_upstream_stream = outlet.upstream_stream_id

    # source_type 扩展契约
    assert outlet_source_type == "PIPE_NET_CALCULATED"
    # upstream_equipment_type 映射：PIPE_NET_CALCULATED → PIPE_NET（不是 PIPE！）
    assert outlet_upstream_equip == "PIPE_NET"
    # sign_status=DRAFT（outlet_stream helper 约定）
    assert outlet_sign.value == "DRAFT" or str(outlet_sign) == "DRAFT"
    # properties 包含收敛态 + 节点 / 边数 + 置信度 / 校核
    assert outlet_properties["converged"] is True
    assert outlet_properties["edge_count"] == 5
    assert outlet_properties["node_count"] == 4
    assert outlet_properties["confidence"] in ("HIGH", "MEDIUM", "LOW")
    # upstream_stream_id 链回源流
    assert str(outlet_upstream_stream) == str(source_stream_id)
    # outlet 也实际落库（与源流不在同一行）
    async with factory() as db:
        sr = await db.execute(
            text(
                "SELECT source_type, upstream_equipment_type FROM streams "
                "WHERE stream_id = :pk"
            ),
            {"pk": str(outlet_id)},
        )
        srow = sr.mappings().one()
    assert srow["source_type"] == "PIPE_NET_CALCULATED"
    assert srow["upstream_equipment_type"] == "PIPE_NET"


# ---------------------------------------------------------------------------
# 4) project_id 一致性校验
# ---------------------------------------------------------------------------


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_persist_project_id_mismatch_raises_pcs_test():
    """P4-3-3：PIPE_NET.project_id != outlet.project_id → raise
    OutletStreamProjectMismatchError。

    构造：源流位于另一 project（sp_project_id），但 inp.project_id 仍指向主
    project；create_outlet_stream 内部 source.project_id != project_id 检查
    触发。
    """
    main_project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    other_project_id = uuid.uuid4()

    inp = _two_loop_inp(main_project_id, workspace_id, source_stream_id)
    config = SolverConfig(tolerance_m3_s=1e-6, max_iterations=100)
    result = solve_network(inp, config)

    factory = get_async_session_factory()
    async with factory() as db:
        # 1) 主 project + workspace + 源流（source_stream.project_id = main_project_id）
        await _make_project_workspace_stream(
            db, main_project_id, workspace_id, source_stream_id,
        )
        # 2) 另一 project（满足 FK；源流本身仍属 main_project，但我们要造
        #    cross-project 不一致：把源流.project_id 改成 other_project_id）
        other_workspace_id = uuid.uuid4()
        await _make_project_workspace(
            db, other_project_id, other_workspace_id,
        )
        # 3) UPDATE 源流.project_id 到 other_project_id（造 mismatch）
        from sqlalchemy import update
        await db.execute(
            update(Stream)
            .where(Stream.stream_id == source_stream_id)
            .values(project_id=other_project_id)
        )
        await db.flush()
        with pytest.raises(OutletStreamProjectMismatchError):
            await persist_pipe_network_result(db, inp, result)


# ---------------------------------------------------------------------------
# 5) 不 commit 验证
# ---------------------------------------------------------------------------


@_ONLY_PCS_TEST
@pytest.mark.asyncio
async def test_persist_does_not_commit_pcs_test():
    """P4-3-3：persist_pipe_network_result 不 commit；调用后 session.dirty
    仍有未提交对象（事务由调用方控制）。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()

    inp = _two_loop_inp(project_id, workspace_id, source_stream_id)
    config = SolverConfig(tolerance_m3_s=1e-6, max_iterations=100)
    result = solve_network(inp, config)

    factory = get_async_session_factory()
    async with factory() as db:
        await _make_project_workspace_stream(
            db, project_id, workspace_id, source_stream_id
        )
        row, outlet = await persist_pipe_network_result(db, inp, result)
        # persist 内部 flush 但不 commit；外部观察者未 commit 时不可见。
        # 验证：跨事务 SELECT COUNT=0，commit 后 COUNT=1。
        net_id = row.network_id
        outlet_id = outlet.stream_id
        pre_check = await db.execute(
            text(
                "SELECT COUNT(*) AS c FROM pipe_network_results "
                "WHERE network_id = :pk"
            ),
            {"pk": str(net_id)},
        )
        # flush 后同事务可见，但跨事务不可见
        assert pre_check.scalar() == 1

    # 新事务：commit 前不应可见（外部观察者）
    async with factory() as db:
        post_check = await db.execute(
            text(
                "SELECT COUNT(*) AS c FROM pipe_network_results "
                "WHERE network_id = :pk"
            ),
            {"pk": str(net_id)},
        )
        assert post_check.scalar() == 0
        # outlet 同样
        post_outlet = await db.execute(
            text(
                "SELECT COUNT(*) AS c FROM streams WHERE stream_id = :pk"
            ),
            {"pk": str(outlet_id)},
        )
        assert post_outlet.scalar() == 0

    # commit 后才可见
    async with factory() as db:
        await _make_project_workspace_stream(
            db, project_id, workspace_id, source_stream_id
        )
        row2, outlet2 = await persist_pipe_network_result(db, inp, result)
        await db.commit()
        net_id2 = row2.network_id
    async with factory() as db:
        rs = await db.execute(
            text(
                "SELECT COUNT(*) AS c FROM pipe_network_results "
                "WHERE network_id = :pk"
            ),
            {"pk": str(net_id2)},
        )
        assert rs.scalar() == 1