"""P3.2 SIM-8：状态点 API 集成测试。

端到端验证 5 路由：
- POST   /api/v1/streams/{stream_id}/state-points
- GET    /api/v1/streams/{stream_id}/state-points
- GET    /api/v1/state-points/{state_point_id}
- PATCH  /api/v1/state-points/{state_point_id}
- DELETE /api/v1/state-points/{state_point_id}

错误码：
- 父流不存在 → 404 SIM_STREAM_NOT_FOUND
- 状态点不存在 → 404 SIM_STATEPOINT_NOT_FOUND
- composition 和偏差过大 → 422 SIM_STATEPOINT_BLOCKED（SIM-SV03 BLOCK）
- 401 missing bearer / 403 role forbidden
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Stream, Workspace
from app.schemas.stream import StreamCreate
from app.services.stream_service import StreamService

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_stream(db: AsyncSession) -> Stream:
    """Workspace + Project + Stream（state point 测试前置）。"""
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="测试项目",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.flush()
    sp, _ = await StreamService.create(
        db,
        StreamCreate(
            project_id=proj.project_id,
            workspace_id=ws.workspace_id,
            stream_name="S-101",
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            temp=80.0,
            press=200.0,
            phase="LIQUID",
            mass_flow=1000.0,
        ),
        actor=uuid.uuid4(),
    )
    return sp


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def no_role_headers() -> dict[str, str]:
    token = create_access_token(subject="test-norole", role="VIEWER")
    return {"Authorization": f"Bearer {token}"}


def _state_point_body(**kw) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        state_label="设计工况",
        case_type="NORMAL",
        temp=80.0,
        press=200.0,
        phase="LIQUID",
        mass_flow=1000.0,
        composition_json={"WATER": 1.0},
        source_type="MANUAL_ENTRY",
    )
    base.update(kw)
    return base


# ---------------------------------------------------------------------------
# POST /streams/{stream_id}/state-points
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_state_point_201(client, seeded_stream, designer_headers):
    r = await client.post(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        json=_state_point_body(),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["state_label"] == "设计工况"
    assert body["case_type"] == "NORMAL"
    assert body["stream_id"] == str(seeded_stream.stream_id)
    assert body["created_at"] is not None


@pytest.mark.asyncio
async def test_post_state_point_parent_not_found_404(client, designer_headers):
    r = await client.post(
        f"/api/v1/streams/{uuid.uuid4()}/state-points",
        json=_state_point_body(),
        headers=designer_headers,
    )
    assert r.status_code == 404
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"


@pytest.mark.asyncio
async def test_post_state_point_missing_bearer_401(client, seeded_stream):
    r = await client.post(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        json=_state_point_body(),
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_post_state_point_role_forbidden_403(
    client, seeded_stream, no_role_headers
):
    r = await client.post(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        json=_state_point_body(),
        headers=no_role_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_post_state_point_block_composition_sum(
    client, seeded_stream, designer_headers
):
    """SIM-SV03 BLOCK：组成和偏差 > 1%（sum=0.5，dev=50%）→ 422 SIM_STATEPOINT_BLOCKED。

    spec 工艺实践参考阈值：PRO/II/Aspen reject 1%、工艺包 < 0.5%、安全泄放 < 0.5% 可信。
    """
    r = await client.post(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        json=_state_point_body(composition_json={"WATER": 0.5}),
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "SIM_STATEPOINT_BLOCKED"


@pytest.mark.asyncio
async def test_post_state_point_warn_composition_sum_within_tolerance(
    client, seeded_stream, designer_headers
):
    """SIM-SV03 WARN：组成和偏差在 (0.1%, 1%] 区间 → 201 落库。"""
    r = await client.post(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        json=_state_point_body(composition_json={"WATER": 0.995}),
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    assert r.json()["state_point_id"] is not None


# ---------------------------------------------------------------------------
# GET /streams/{stream_id}/state-points
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_state_points_sorted_by_case_type(
    client, seeded_stream, designer_headers
):
    for label, ct in [("最大工况", "MAX"), ("设计工况", "NORMAL"), ("最小工况", "MIN")]:
        await client.post(
            f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
            json=_state_point_body(state_label=label, case_type=ct),
            headers=designer_headers,
        )
    r = await client.get(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        headers=designer_headers,
    )
    assert r.status_code == 200
    assert [sp["case_type"] for sp in r.json()] == ["MAX", "MIN", "NORMAL"]


@pytest.mark.asyncio
async def test_list_state_points_empty(client, seeded_stream, designer_headers):
    r = await client.get(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        headers=designer_headers,
    )
    assert r.status_code == 200
    assert r.json() == []


@pytest.mark.asyncio
async def test_list_state_points_stream_not_found_404(client, designer_headers):
    r = await client.get(
        f"/api/v1/streams/{uuid.uuid4()}/state-points",
        headers=designer_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# GET /state-points/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_one_state_point_200(client, seeded_stream, designer_headers):
    r1 = await client.post(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        json=_state_point_body(),
        headers=designer_headers,
    )
    sp_id = r1.json()["state_point_id"]
    r2 = await client.get(
        f"/api/v1/state-points/{sp_id}", headers=designer_headers
    )
    assert r2.status_code == 200
    assert r2.json()["state_point_id"] == sp_id


@pytest.mark.asyncio
async def test_get_one_state_point_not_found_404(client, designer_headers):
    r = await client.get(
        f"/api/v1/state-points/{uuid.uuid4()}", headers=designer_headers
    )
    assert r.status_code == 404
    assert r.json()["code"] == "SIM_STATEPOINT_NOT_FOUND"


# ---------------------------------------------------------------------------
# PATCH /state-points/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_state_point_200(client, seeded_stream, designer_headers):
    r1 = await client.post(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        json=_state_point_body(),
        headers=designer_headers,
    )
    sp_id = r1.json()["state_point_id"]
    r2 = await client.patch(
        f"/api/v1/state-points/{sp_id}",
        json={"state_label": "调整后", "temp": 100.0},
        headers=designer_headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["state_label"] == "调整后"
    assert r2.json()["temp"] == 100.0


@pytest.mark.asyncio
async def test_patch_state_point_not_found_404(client, designer_headers):
    r = await client.patch(
        f"/api/v1/state-points/{uuid.uuid4()}",
        json={"state_label": "X"},
        headers=designer_headers,
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /state-points/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_state_point_204(client, seeded_stream, designer_headers):
    r1 = await client.post(
        f"/api/v1/streams/{seeded_stream.stream_id}/state-points",
        json=_state_point_body(),
        headers=designer_headers,
    )
    sp_id = r1.json()["state_point_id"]
    r2 = await client.delete(
        f"/api/v1/state-points/{sp_id}", headers=designer_headers
    )
    assert r2.status_code == 204
    r3 = await client.get(
        f"/api/v1/state-points/{sp_id}", headers=designer_headers
    )
    assert r3.status_code == 404


@pytest.mark.asyncio
async def test_delete_state_point_not_found_404(client, designer_headers):
    r = await client.delete(
        f"/api/v1/state-points/{uuid.uuid4()}", headers=designer_headers
    )
    assert r.status_code == 404