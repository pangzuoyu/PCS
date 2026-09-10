"""P3.x SIM-26：物流物性端点测试。

端点契约：
- GET    /api/v1/streams/{stream_id}/properties
- POST   /api/v1/streams/{stream_id}/properties/estimate

GET 返回 stream 的 4 JSON 字段（user_provided / calculated / effective /
conflict_resolutions）。

POST 接 CAS 列表，调用 PropertyAutoCompleter.batch_complete，返回每 CAS
的补全结果（不入库，只读计算）。
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Workspace


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
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
        await db.commit()
        return proj

    return _make


@pytest.fixture
def designer_headers() -> dict[str, str]:
    token = create_access_token(subject="test-designer", role="DESIGNER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def no_role_headers() -> dict[str, str]:
    token = create_access_token(subject="test-viewer", role="VIEWER")
    return {"Authorization": f"Bearer {token}"}


def _stream_payload(**kw) -> dict[str, Any]:
    base: dict[str, Any] = dict(
        stream_name="S-101",
        case_type="NORMAL",
        data_mode="CHEMICAL",
        source_type="MANUAL_ENTRY",
        temp=80.0,
        press=200.0,
        phase="LIQUID",
        mass_flow=1000.0,
    )
    base.update(kw)
    return base


async def _create_stream(client, project_id, headers, payload=None, patch=None):
    """POST 一个 stream，可选 PATCH 一些字段。返回 stream_id。"""
    r = await client.post(
        f"/api/v1/projects/{project_id}/streams",
        json={"payload": payload or _stream_payload()},
        headers=headers,
    )
    assert r.status_code == 201, r.text
    sid = r.json()["stream_id"]
    if patch:
        r2 = await client.patch(
            f"/api/v1/streams/{sid}",
            json={"payload": patch},
            headers=headers,
        )
        assert r2.status_code == 200, r2.text
    return sid


# ---------------------------------------------------------------------------
# GET /streams/{id}/properties
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_stream_properties_empty(client, make_project, designer_headers):
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)
    r = await client.get(
        f"/api/v1/streams/{sid}/properties", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stream_id"] == sid
    # 4 JSON 字段都应存在（即使为空）
    assert "user_provided" in body
    assert "calculated" in body
    assert "effective" in body
    assert "conflict_resolutions" in body


@pytest.mark.asyncio
async def test_get_stream_properties_returns_user_provided(
    client, make_project, designer_headers, db
):
    """直接 DB 写 user_provided_properties_json（schema 未暴露该字段，
    实际生产路径是 PropertyConflictResolver 写入），GET 应原样返回。"""
    from sqlalchemy import select

    from app.models.project import Stream

    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)

    # 直接通过 DB 写入（绕过 schema 限制）
    stream = (
        await db.execute(select(Stream).where(Stream.stream_id == uuid.UUID(sid)))
    ).scalar_one()
    stream.user_provided_properties_json = {
        "mw": 100.0,
        "tc_k": 600.0,
        "pc_pa": 1.0e6,
    }
    await db.commit()

    r = await client.get(
        f"/api/v1/streams/{sid}/properties", headers=designer_headers
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["user_provided"] == {
        "mw": 100.0,
        "tc_k": 600.0,
        "pc_pa": 1.0e6,
    }


@pytest.mark.asyncio
async def test_get_stream_properties_unknown_404(client, designer_headers):
    r = await client.get(
        f"/api/v1/streams/{uuid.uuid4()}/properties", headers=designer_headers
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_get_stream_properties_missing_bearer_401(client, make_project, designer_headers):
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)
    r = await client.get(f"/api/v1/streams/{sid}/properties")
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_get_stream_properties_viewer_forbidden(
    client, make_project, designer_headers, no_role_headers
):
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)
    r = await client.get(
        f"/api/v1/streams/{sid}/properties", headers=no_role_headers
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /streams/{id}/properties/estimate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_properties_estimate_benzene(
    client, make_project, designer_headers
):
    """estimate 走 PropertyAutoCompleter.batch_complete：BENZENE 71-43-2 应返回结构。"""
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)
    r = await client.post(
        f"/api/v1/streams/{sid}/properties/estimate",
        json={"cas_list": ["71-43-2"]},
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "results" in body
    assert isinstance(body["results"], list)
    assert len(body["results"]) == 1
    entry = body["results"][0]
    assert entry["cas"] == "71-43-2"
    assert "estimated" in entry


@pytest.mark.asyncio
async def test_post_properties_estimate_multiple_cas(
    client, make_project, designer_headers
):
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)
    r = await client.post(
        f"/api/v1/streams/{sid}/properties/estimate",
        json={"cas_list": ["71-43-2", "7732-18-5"]},
        headers=designer_headers,
    )
    assert r.status_code == 200
    body = r.json()
    assert len(body["results"]) == 2
    assert body["results"][0]["cas"] == "71-43-2"
    assert body["results"][1]["cas"] == "7732-18-5"


@pytest.mark.asyncio
async def test_post_properties_estimate_empty_cas_list(
    client, make_project, designer_headers
):
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)
    r = await client.post(
        f"/api/v1/streams/{sid}/properties/estimate",
        json={"cas_list": []},
        headers=designer_headers,
    )
    assert r.status_code == 200
    assert r.json()["results"] == []


@pytest.mark.asyncio
async def test_post_properties_estimate_unknown_stream_404(client, designer_headers):
    r = await client.post(
        f"/api/v1/streams/{uuid.uuid4()}/properties/estimate",
        json={"cas_list": ["71-43-2"]},
        headers=designer_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_properties_estimate_missing_bearer_401(
    client, make_project, designer_headers
):
    proj = await make_project()
    sid = await _create_stream(client, proj.project_id, designer_headers)
    r = await client.post(
        f"/api/v1/streams/{sid}/properties/estimate",
        json={"cas_list": ["71-43-2"]},
    )
    assert r.status_code == 401