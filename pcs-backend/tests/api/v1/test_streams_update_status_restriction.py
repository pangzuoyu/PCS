"""P3.x SIM-32：PATCH /streams/{id} 端点状态限制。

契约：
- sign_status 处于「可编辑」态（DRAFT / IN_APPROVAL）→ PATCH 允许
- sign_status 处于「锁定/终态」（CHECKED / STALE / CHANGED / OBSOLETE /
  CHECK_REJECTED / REVERSAL_PENDING）→ PATCH 拒绝（409 SIM_STREAM_LOCKED）
- 错误码：SIM_STREAM_LOCKED（HTTP 409 Conflict）
- 错误信息含当前 sign_status，便于前端定位
"""
from __future__ import annotations

import uuid
from typing import Any

import pytest
import pytest_asyncio

from app.core.security import create_access_token
from app.models.enums import StreamSignStatus
from app.models.project import Project, Workspace


@pytest_asyncio.fixture
async def make_project(db):
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


def _payload(**kw) -> dict[str, Any]:
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


async def _make_stream(
    client, db, project_id, sign_status: StreamSignStatus, designer_headers
) -> str:
    """通过 API 创建 stream（DRAFT），再用 DB UPDATE 设 sign_status。"""
    from sqlalchemy import update

    # 1. POST 创建（DRAFT）
    r = await client.post(
        f"/api/v1/projects/{project_id}/streams",
        json={"payload": _payload()},
        headers=designer_headers,
    )
    assert r.status_code == 201, r.text
    sid = r.json()["stream_id"]

    # 2. DB 直接 UPDATE sign_status（绕过 API；测试目标不是状态机）
    from app.models.project import Stream as StreamModel

    await db.execute(
        update(StreamModel)
        .where(StreamModel.stream_id == uuid.UUID(sid))
        .values(sign_status=sign_status)
    )
    await db.commit()
    return sid


# ---------------------------------------------------------------------------
# 可编辑状态：DRAFT / IN_APPROVAL 允许 PATCH
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("editable_status", [StreamSignStatus.DRAFT, StreamSignStatus.IN_APPROVAL])
async def test_update_allowed_in_editable_status(
    client, db, make_project, designer_headers, editable_status
):
    """DRAFT / IN_APPROVAL 状态可 PATCH（200）。"""
    proj = await make_project()
    sid = await _make_stream(client, db, proj.project_id, editable_status, designer_headers)

    r = await client.patch(
        f"/api/v1/streams/{sid}",
        json={"payload": {"temp": 90.0}},
        headers=designer_headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["stream_id"] == sid
    assert body["temp"] == pytest.approx(90.0, abs=0.01)


# ---------------------------------------------------------------------------
# 锁定/终态：PATCH 拒绝
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "locked_status",
    [
        StreamSignStatus.CHECKED,
        StreamSignStatus.STALE,
        StreamSignStatus.CHANGED,
        StreamSignStatus.OBSOLETE,
        StreamSignStatus.CHECK_REJECTED,
        StreamSignStatus.REVERSAL_PENDING,
    ],
)
async def test_update_rejected_in_locked_status(
    client, db, make_project, designer_headers, locked_status
):
    """CHECKED / STALE / CHANGED / OBSOLETE / CHECK_REJECTED / REVERSAL_PENDING → 409。"""
    proj = await make_project()
    sid = await _make_stream(client, db, proj.project_id, locked_status, designer_headers)

    r = await client.patch(
        f"/api/v1/streams/{sid}",
        json={"payload": {"temp": 90.0}},
        headers=designer_headers,
    )
    assert r.status_code == 409, (
        f"sign_status={locked_status} 应 409，实际 {r.status_code}: {r.text}"
    )
    body = r.json()
    assert body["code"] == "SIM_STREAM_LOCKED"
    # 错误信息含当前 sign_status
    assert locked_status.value in body["message"]


# ---------------------------------------------------------------------------
# SIM_STREAM_BLOCKED（已有契约）保留
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_blocked_by_validation_returns_422(
    client, db, make_project, designer_headers
):
    """DRAFT 状态下若 payload 触发 SIM-V BLOCK → 422 SIM_STREAM_BLOCKED（已有契约）。"""
    proj = await make_project()
    sid = await _make_stream(client, db, proj.project_id, StreamSignStatus.DRAFT, designer_headers)

    # 压力越界（SIM-V03）
    r = await client.patch(
        f"/api/v1/streams/{sid}",
        json={"payload": {"press": 1e10}},  # > 1e8 Pa
        headers=designer_headers,
    )
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "SIM_STREAM_BLOCKED"


# ---------------------------------------------------------------------------
# 错误信息含状态名（前端定位）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_locked_error_message_includes_status_name(
    client, db, make_project, designer_headers
):
    """409 错误 message 应含 sign_status 枚举名，便于前端定位。"""
    proj = await make_project()
    sid = await _make_stream(
        client, db, proj.project_id, StreamSignStatus.CHECKED, designer_headers
    )

    r = await client.patch(
        f"/api/v1/streams/{sid}",
        json={"payload": {"temp": 90.0}},
        headers=designer_headers,
    )
    assert r.status_code == 409
    body = r.json()
    assert "CHECKED" in body["message"]


# ---------------------------------------------------------------------------
# 404 / 401 / 403 已有契约不破坏
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_unknown_stream_returns_404(client, designer_headers):
    r = await client.patch(
        f"/api/v1/streams/{uuid.uuid4()}",
        json={"payload": {"temp": 90.0}},
        headers=designer_headers,
    )
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_update_missing_bearer_returns_401(
    client, db, make_project, designer_headers
):
    proj = await make_project()
    sid = await _make_stream(client, db, proj.project_id, StreamSignStatus.DRAFT, designer_headers)
    r = await client.patch(
        f"/api/v1/streams/{sid}",
        json={"payload": {"temp": 90.0}},
    )
    assert r.status_code == 401


@pytest.mark.asyncio
async def test_update_viewer_role_forbidden(
    client, db, make_project, designer_headers
):
    viewer_token = create_access_token(subject="viewer", role="VIEWER")
    headers = {"Authorization": f"Bearer {viewer_token}"}
    proj = await make_project()
    sid = await _make_stream(client, db, proj.project_id, StreamSignStatus.DRAFT, designer_headers)
    r = await client.patch(
        f"/api/v1/streams/{sid}",
        json={"payload": {"temp": 90.0}},
        headers=headers,
    )
    assert r.status_code == 403
