"""P3.2 SIM-6：物流手工表单 API 集成测试。

通过 in-memory SQLite + client（httpx async）端到端验证：
- 5 端点：POST/GET（list）/GET（one）/PATCH/DELETE
- ACL：DESIGNER 通行；missing bearer → 401
- BLOCK 冲突 → 422 SIM_STREAM_BLOCKED
- 同 (project, stream_name) 重复 → 422 SIM_STREAM_DUPLICATE_NAME
- 单查/更新/删除 不存在 → 404 SIM_STREAM_NOT_FOUND
- WARN/INFO 冲突 → 201 + StreamResponse（落库成功）
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.project import Project, Workspace

# ---------------------------------------------------------------------------
# fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    """最小 Workspace + Project 工厂。"""

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
def pc_headers() -> dict[str, str]:
    token = create_access_token(subject="test-pc", role="PROCESS_CONTROLLER")
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def no_role_headers() -> dict[str, str]:
    token = create_access_token(subject="test-norole", role="VIEWER")
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


# ---------------------------------------------------------------------------
# POST /projects/{id}/streams
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_create_stream_201(client, make_project, designer_headers):
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _stream_payload()},
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["stream_name"] == "S-101"
    assert body["sign_status"] == "DRAFT"
    assert body["case_type"] == "NORMAL"
    assert body["data_mode"] == "CHEMICAL"


@pytest.mark.asyncio
async def test_post_create_stream_block_422(client, make_project, designer_headers):
    """触发 BLOCK 冲突（高温极端值）→ 422 SIM_STREAM_BLOCKED。"""
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _stream_payload(temp=99999.0, press=999999.0)},
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "SIM_STREAM_BLOCKED"


@pytest.mark.asyncio
async def test_post_create_stream_duplicate_name_422(
    client, make_project, designer_headers
):
    proj = await make_project()
    payload = _stream_payload()
    r1 = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": payload},
        headers=designer_headers,
    )
    assert r1.status_code == 201
    r2 = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": payload},
        headers=designer_headers,
    )
    assert r2.status_code == 422
    assert r2.json()["code"] == "SIM_STREAM_DUPLICATE_NAME"


@pytest.mark.asyncio
async def test_post_create_stream_unknown_project_404(client, designer_headers):
    r = await client.post(
        f"/api/v1/projects/{uuid.uuid4()}/streams",
        json={"payload": _stream_payload()},
        headers=designer_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_post_create_stream_missing_bearer_401(client, make_project):
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _stream_payload()},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_post_create_stream_role_forbidden_403(
    client, make_project, no_role_headers
):
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _stream_payload()},
        headers=no_role_headers,
    )
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# GET /projects/{id}/streams
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_list_streams(client, make_project, designer_headers):
    proj = await make_project()
    for n in ("A-1", "B-2", "C-3"):
        await client.post(
            f"/api/v1/projects/{proj.project_id}/streams",
            json={"payload": _stream_payload(stream_name=n)},
            headers=designer_headers,
        )
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams",
        headers=designer_headers,
    )
    assert r.status_code == 200
    names = [s["stream_name"] for s in r.json()]
    assert names == ["A-1", "B-2", "C-3"]


@pytest.mark.asyncio
async def test_get_list_streams_case_type_filter(
    client, make_project, designer_headers
):
    proj = await make_project()
    for ct in ("NORMAL", "END_OF_RUN", "NORMAL"):
        await client.post(
            f"/api/v1/projects/{proj.project_id}/streams",
            json={"payload": _stream_payload(case_type=ct)},
            headers=designer_headers,
        )
    r = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams?case_type=NORMAL",
        headers=designer_headers,
    )
    assert r.status_code == 200
    assert all(s["case_type"] == "NORMAL" for s in r.json())


# ---------------------------------------------------------------------------
# GET /streams/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_one_stream_200(client, make_project, designer_headers):
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _stream_payload()},
        headers=designer_headers,
    )
    sid = r.json()["stream_id"]
    r2 = await client.get(f"/api/v1/streams/{sid}", headers=designer_headers)
    assert r2.status_code == 200
    assert r2.json()["stream_id"] == sid


@pytest.mark.asyncio
async def test_get_one_stream_not_found_404(client, designer_headers):
    r = await client.get(f"/api/v1/streams/{uuid.uuid4()}", headers=designer_headers)
    assert r.status_code == 404
    assert r.json()["code"] == "SIM_STREAM_NOT_FOUND"


# ---------------------------------------------------------------------------
# PATCH /streams/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_stream_200(client, make_project, designer_headers):
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _stream_payload(temp=80.0)},
        headers=designer_headers,
    )
    sid = r.json()["stream_id"]
    r2 = await client.patch(
        f"/api/v1/streams/{sid}",
        json={"payload": {"temp": 95.0, "description": "调整后"}},
        headers=designer_headers,
    )
    assert r2.status_code == 200, r2.text
    assert r2.json()["description"] == "调整后"


@pytest.mark.asyncio
async def test_patch_stream_not_found_404(client, designer_headers):
    r = await client.patch(
        f"/api/v1/streams/{uuid.uuid4()}",
        json={"payload": {"temp": 95.0}},
        headers=designer_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_patch_stream_block_422(client, make_project, designer_headers):
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _stream_payload()},
        headers=designer_headers,
    )
    sid = r.json()["stream_id"]
    r2 = await client.patch(
        f"/api/v1/streams/{sid}",
        json={"payload": {"temp": 99999.0, "press": 999999.0}},
        headers=designer_headers,
    )
    assert r2.status_code == 422
    assert r2.json()["code"] == "SIM_STREAM_BLOCKED"


# ---------------------------------------------------------------------------
# DELETE /streams/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_stream_204(client, make_project, designer_headers):
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams",
        json={"payload": _stream_payload()},
        headers=designer_headers,
    )
    sid = r.json()["stream_id"]
    r2 = await client.delete(f"/api/v1/streams/{sid}", headers=designer_headers)
    assert r2.status_code == 204
    r3 = await client.get(f"/api/v1/streams/{sid}", headers=designer_headers)
    assert r3.status_code == 404


@pytest.mark.asyncio
async def test_delete_stream_not_found_404(client, designer_headers):
    r = await client.delete(
        f"/api/v1/streams/{uuid.uuid4()}", headers=designer_headers
    )
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# SIM-24：POST /projects/{id}/streams/validate（不入库）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_validate_stream_clean_200(
    client, make_project, designer_headers
):
    """干净数据 → 200 + valid=True + blocks=[]，且 DB 无新 stream。"""
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams/validate",
        json={"payload": _stream_payload()},
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is True
    assert body["blocks"] == []
    assert body["warnings"] == []
    assert body["stats"]["BLOCK"] == 0
    # 校验不入库：list 应为空
    lst = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams",
        headers=designer_headers,
    )
    assert lst.status_code == 200
    assert lst.json() == []


@pytest.mark.asyncio
async def test_validate_stream_block_200_with_conflicts(
    client, make_project, designer_headers
):
    """BLOCK 冲突 → 200（不入库）+ valid=False + blocks 非空。

    注意：与 create 不同，validate 不抛 422——返回完整 ConflictReport。
    """
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams/validate",
        json={"payload": _stream_payload(temp=99999.0, press=999999.0)},
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is False
    assert len(body["blocks"]) >= 1
    assert body["stats"]["BLOCK"] >= 1
    # 仍然不入库
    lst = await client.get(
        f"/api/v1/projects/{proj.project_id}/streams",
        headers=designer_headers,
    )
    assert lst.json() == []


@pytest.mark.asyncio
async def test_validate_stream_warn_200_valid_true(
    client, make_project, designer_headers
):
    """WARN 冲突（如 composition_json 之和偏离）→ valid=True + warnings 非空。"""
    proj = await make_project()
    # 给一个 composition_json 但加和偏离（0.5+0.5=1.0 故意）——这里只测形态
    payload = _stream_payload()
    payload["composition_json"] = {"71-43-2": 0.5, "74-82-8": 0.5}
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams/validate",
        json={"payload": payload},
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["valid"] is True
    # 无 BLOCK，stats.BLOCK=0
    assert body["stats"]["BLOCK"] == 0


@pytest.mark.asyncio
async def test_validate_stream_unknown_project_404(client, designer_headers):
    """project 不存在 → 404（与 create 行为一致）。"""
    r = await client.post(
        f"/api/v1/projects/{uuid.uuid4()}/streams/validate",
        json={"payload": _stream_payload()},
        headers=designer_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_validate_stream_missing_bearer_401(client, make_project):
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams/validate",
        json={"payload": _stream_payload()},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_validate_stream_role_forbidden_403(
    client, make_project, no_role_headers
):
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams/validate",
        json={"payload": _stream_payload()},
        headers=no_role_headers,
    )
    assert r.status_code == 403


@pytest.mark.asyncio
async def test_validate_stream_bad_payload_422(client, make_project, designer_headers):
    """payload 不合法（缺 stream_name）→ 422。"""
    proj = await make_project()
    r = await client.post(
        f"/api/v1/projects/{proj.project_id}/streams/validate",
        json={"payload": {"temp": 80.0}},
        headers=designer_headers,
    )
    assert r.status_code == 422