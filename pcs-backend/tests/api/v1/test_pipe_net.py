"""P4-3-3 管网 API 端到端测试（in-memory SQLite + httpx async client）。

端点：POST /api/v1/pipe-net/solve

覆盖（7 项验收）：
1. happy path：POST /solve → 200/201 + result dict
2. DRAFT source → 403
3. 不存在 → 404
4. 不可靠 → 422
5. 拓扑不合法 → 422
6. 不收敛 → 422
7. 空 nodes / edges → 422

设计要点：
- 使用 conftest.py 的 client / db_session / sample_designer_token fixtures
  （in-memory SQLite + JSONB shim；不依赖 pcs_test 真库）
- 复用 test_pipe_chain.py 模式：构造最小 Project + Workspace + Stream
- 拓扑不合法用例：缺 SINK 节点 → validate_topology 422
- 不收敛用例：极小 max_iterations + 极紧 tolerance
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _make_full_pws(
    db: AsyncSession,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    *,
    sign_status: StreamSignStatus = StreamSignStatus.CHECKED,
) -> None:
    """API 测试用：完整 Project + Workspace + Stream（默认 CHECKED）。"""
    ws = Workspace(
        workspace_id=workspace_id,
        workspace_type="FORMAL",
        project_id=project_id,
        name="t",
    )
    db.add(ws)
    await db.flush()
    proj = Project(
        project_id=project_id,
        project_no=f"P-{project_id.hex[:8]}",
        project_name="t",
        owner_company="t",
        location="t",
        project_type="test",
        design_phase="BASIC",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=ws.workspace_id,
    )
    stream = Stream(
        stream_id=source_stream_id,
        project_id=project_id,
        workspace_id=workspace_id,
        stream_name=f"S-{source_stream_id.hex[:8]}",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        sign_status=sign_status,
        approval_depth=1,
        press=200_000.0,
        temp=298.15,
        composition_json={"C1": 1.0},
    )
    db.add_all([proj, stream])
    await db.flush()


def _segment_req() -> dict[str, Any]:
    return {
        "fluid_phase": "LIQUID",
        "mass_flow_kg_s": 10.0,
        "density_kg_m3": 1000.0,
        "viscosity_pa_s": 1.0e-3,
        "pipe_diameter_m": 0.05,
        "pipe_roughness_m": 4.6e-5,
        "length_m": 10.0,
    }


def _edge_req(
    edge_id: str, from_node: str, to_node: str, tag: str | None = None
) -> dict[str, Any]:
    return {
        "edge_id": edge_id,
        "from_node": from_node,
        "to_node": to_node,
        "tag_number": tag or f"chain-{edge_id}",
        "segments": [_segment_req()],
        "inlet_pressure_pa": 200_000.0,
        "inlet_temperature_K": 298.15,
        "parallel_branches": 1,
    }


def _two_loop_body(
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    *,
    solver_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    nodes = [
        {
            "node_id": "N1",
            "elevation_m": 0.0,
            "node_type": "SOURCE",
            "demand_m3_s": 0.0,
            "pressure_pa": 200_000.0,
        },
        {
            "node_id": "N2",
            "elevation_m": 0.0,
            "node_type": "JUNCTION",
            "demand_m3_s": 0.0,
            "pressure_pa": 150_000.0,
        },
        {
            "node_id": "N3",
            "elevation_m": 0.0,
            "node_type": "JUNCTION",
            "demand_m3_s": 0.0,
            "pressure_pa": 150_000.0,
        },
        {
            "node_id": "N4",
            "elevation_m": 0.0,
            "node_type": "SINK",
            "demand_m3_s": 0.02,
            "pressure_pa": 100_000.0,
        },
    ]
    edges = [
        _edge_req("E1", "N1", "N2"),
        _edge_req("E2", "N2", "N3"),
        _edge_req("E3", "N1", "N3"),
        _edge_req("E4", "N3", "N4"),
        _edge_req("E5", "N2", "N4"),
    ]
    body: dict[str, Any] = {
        "project_id": str(project_id),
        "workspace_id": str(workspace_id),
        "source_stream_id": str(source_stream_id),
        "tag_number": "net-api-001",
        "nodes": nodes,
        "edges": edges,
    }
    if solver_config is not None:
        body["solver_config"] = solver_config
    return body


# ---------------------------------------------------------------------------
# 1) Happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_solve_pipe_net_happy_path(
    client, db_session, sample_designer_token
):
    """POST /api/v1/pipe-net/solve：4 节点 5 边等 R 网络 → 201 + outlet 流。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    await _make_full_pws(db_session, project_id, workspace_id, source_stream_id)

    body = _two_loop_body(project_id, workspace_id, source_stream_id)
    r = await client.post(
        "/api/v1/pipe-net/solve",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 201, r.text
    data = r.json()

    # 必含字段
    assert "network_result_id" in data
    assert "outlet_stream_id" in data
    assert data["converged"] is True
    assert data["iterations"] >= 1
    assert data["max_flow_error_m3_s"] >= 0.0
    # edge_flows / node_pressures 数量匹配
    assert len(data["edge_flows"]) == 5
    assert len(data["node_pressures"]) == 4
    # confidence / check_result 在合法集合
    assert data["confidence"] in ("HIGH", "MEDIUM", "LOW")
    assert data["check_result"] in ("PASS", "WARNING", "FAIL")


# ---------------------------------------------------------------------------
# 2) DRAFT source → 403
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_solve_pipe_net_draft_source_403(
    client, db_session, sample_designer_token
):
    """源流 sign_status=DRAFT → 403 STREAM_NOT_CHECKED。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    await _make_full_pws(
        db_session, project_id, workspace_id, source_stream_id,
        sign_status=StreamSignStatus.DRAFT,
    )

    body = _two_loop_body(project_id, workspace_id, source_stream_id)
    r = await client.post(
        "/api/v1/pipe-net/solve",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 403
    assert r.json()["code"] == "STREAM_NOT_CHECKED"


# ---------------------------------------------------------------------------
# 3) 不存在 → 404
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_solve_pipe_net_not_found_404(client, sample_designer_token):
    """源流不存在 → 404 SIM_STREAM_NOT_FOUND。"""
    body = _two_loop_body(uuid.uuid4(), uuid.uuid4(), uuid.uuid4())
    r = await client.post(
        "/api/v1/pipe-net/solve",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 404
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"


# ---------------------------------------------------------------------------
# 4) 不可靠 → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_solve_pipe_net_unreliable_422(
    client, db_session, sample_designer_token, monkeypatch
):
    """不可靠流守卫（UnreliableStreamGuard.check）→ 422。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    await _make_full_pws(db_session, project_id, workspace_id, source_stream_id)

    # monkey-patch UnreliableStreamGuard.check 让其抛错
    from app.services import calc_entry
    from app.services.exceptions import PcsError

    async def fake_check(db, stream_ids):
        raise PcsError(
            code="STREAM_UNRELIABLE_BLOCKED",
            message="mock unreliable",
            status=422,
        )

    monkeypatch.setattr(
        calc_entry.UnreliableStreamGuard, "check", fake_check
    )

    body = _two_loop_body(project_id, workspace_id, source_stream_id)
    r = await client.post(
        "/api/v1/pipe-net/solve",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "STREAM_UNRELIABLE_BLOCKED"


# ---------------------------------------------------------------------------
# 5) 拓扑不合法 → 422（缺 SINK → validate_topology raise）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_solve_pipe_net_topology_invalid_422(
    client, db_session, sample_designer_token
):
    """拓扑不合法（缺 SINK 节点）→ 422 TOPOLOGY_INPUT_ERROR。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    await _make_full_pws(db_session, project_id, workspace_id, source_stream_id)

    body = _two_loop_body(project_id, workspace_id, source_stream_id)
    # 删 SINK 节点 N4 → validate_topology 422（缺 SOURCE/SINK）
    body["nodes"] = [n for n in body["nodes"] if n["node_type"] != "SINK"]

    r = await client.post(
        "/api/v1/pipe-net/solve",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "TOPOLOGY_INPUT_ERROR"


# ---------------------------------------------------------------------------
# 6) 不收敛 → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_solve_pipe_net_not_converged_422(
    client, db_session, sample_designer_token
):
    """不收敛（max_iterations=1 + tolerance=1e-12）→ 422 NETWORK_CONVERGENCE_ERROR。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    await _make_full_pws(db_session, project_id, workspace_id, source_stream_id)

    body = _two_loop_body(
        project_id, workspace_id, source_stream_id,
        solver_config={
            "tolerance_m3_s": 1.0e-12,
            "max_iterations": 1,
            "initial_flow_strategy": "EVEN_DEMAND_PROPORTIONAL",
        },
    )
    r = await client.post(
        "/api/v1/pipe-net/solve",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "NETWORK_CONVERGENCE_ERROR"


# ---------------------------------------------------------------------------
# 7) 空 nodes / edges → 422
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_api_solve_pipe_net_empty_nodes_422(
    client, db_session, sample_designer_token
):
    """空 nodes → 422 TOPOLOGY_INPUT_ERROR（validate_topology 缺 SOURCE/SINK）。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    source_stream_id = uuid.uuid4()
    await _make_full_pws(db_session, project_id, workspace_id, source_stream_id)

    body = _two_loop_body(project_id, workspace_id, source_stream_id)
    body["nodes"] = []
    body["edges"] = []

    r = await client.post(
        "/api/v1/pipe-net/solve",
        json=body,
        headers={"Authorization": f"Bearer {sample_designer_token}"},
    )
    assert r.status_code == 422
    # 422 来自 Pydantic（nodes/edges min_length）或业务（validate_topology）；
    # 任一 422 即通过
    assert r.json()["code"] in (
        "TOPOLOGY_INPUT_ERROR",
        "VALIDATION_ERROR",
    )