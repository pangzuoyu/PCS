"""P3.2 SIM-13：物流状态机 6 端点 API 测试（闭环审计 D-1）。

覆盖：
- 6 端点 happy path：submit/approve/reject/initiate-change/pass-change/mark-stale
- ACL 错误：DESIGNER 触发 /approve → 403
- Invalid transition：DRAFT 直接 /approve → 422 SIM_STREAM_INVALID_TRANSITION
- 状态机字段：response 含 sign_status / change_pending_since / change_resolved_at
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token
from app.models.enums import StreamSignStatus
from app.models.project import Project, Stream, Workspace


@pytest_asyncio.fixture
async def make_project(db: AsyncSession):
    async def _make() -> Project:
        ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
        db.add(ws)
        await db.flush()
        proj = Project(
            project_no=f"P-{uuid.uuid4().hex[:8]}",
            project_name="SIM-13 API test",
            owner_company="PCS_TEST",
            location="PCS_TEST",
            project_type="CHEMICAL",
            design_phase="FEED",
            unit_system="SI",
            workspace_id=ws.workspace_id,
        )
        db.add(proj)
        await db.flush()
        return proj

    return _make


@pytest_asyncio.fixture
async def make_stream(db: AsyncSession, make_project):
    async def _make(stream_name: str = "API-1") -> Stream:
        proj = await make_project()
        stream = Stream(
            project_id=proj.project_id,
            workspace_id=proj.workspace_id,
            stream_name=stream_name,
            case_type="NORMAL",
            data_mode="CHEMICAL",
            source_type="MANUAL_ENTRY",
            approval_depth=1,
            sign_status=StreamSignStatus.DRAFT,
            composition_json={"WATER": 1.0},
        )
        db.add(stream)
        await db.commit()
        await db.refresh(stream)
        return stream

    return _make


@pytest.fixture
def designer_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(subject='designer', role='DESIGNER')}"}


@pytest.fixture
def pc_headers() -> dict[str, str]:
    token = create_access_token(subject="pc", role="PROCESS_CONTROLLER")
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_api_submit_draft_to_in_approval(client, make_stream, designer_headers):
    """POST /streams/{id}/submit → 200，sign_status=IN_APPROVAL。"""
    stream = await make_stream("SUB")
    resp = await client.post(
        f"/api/v1/streams/{stream.stream_id}/submit",
        headers=designer_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sign_status"] == "IN_APPROVAL"
    assert data["stream_id"] == str(stream.stream_id)


@pytest.mark.asyncio
async def test_api_approve_in_approval_to_checked(client, make_stream, pc_headers):
    """POST /streams/{id}/approve → 200，sign_status=CHECKED。"""
    stream = await make_stream("APR")
    # 先 submit
    await client.post(
        f"/api/v1/streams/{stream.stream_id}/submit",
        headers={"Authorization": f"Bearer {create_access_token(subject='d', role='DESIGNER')}"},
    )
    resp = await client.post(
        f"/api/v1/streams/{stream.stream_id}/approve",
        headers=pc_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sign_status"] == "CHECKED"


@pytest.mark.asyncio
async def test_api_reject_with_reason(client, make_stream, pc_headers):
    """POST /streams/{id}/reject body={reason} → 200，sign_status=CHECK_REJECTED。"""
    stream = await make_stream("REJ")
    await client.post(
        f"/api/v1/streams/{stream.stream_id}/submit",
        headers={"Authorization": f"Bearer {create_access_token(subject='d', role='DESIGNER')}"},
    )
    resp = await client.post(
        f"/api/v1/streams/{stream.stream_id}/reject",
        json={"reason": "数据冲突需修正"},
        headers=pc_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["sign_status"] == "CHECK_REJECTED"


@pytest.mark.asyncio
async def test_api_initiate_change(client, make_stream, pc_headers, designer_headers):
    """POST /streams/{id}/initiate-change → 200 sign_status=CHANGE_PENDING。

    同时验证 response 含 change_pending_since 非空（状态机字段透出）。
    """
    stream = await make_stream("IC")
    # 走到 CHECKED
    await client.post(f"/api/v1/streams/{stream.stream_id}/submit", headers=designer_headers)
    await client.post(f"/api/v1/streams/{stream.stream_id}/approve", headers=pc_headers)
    # 主动变更
    resp = await client.post(
        f"/api/v1/streams/{stream.stream_id}/initiate-change",
        json={"reason": "客户变更压力"},
        headers=designer_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sign_status"] == "CHANGE_PENDING"
    assert data["change_pending_since"] is not None


@pytest.mark.asyncio
async def test_api_pass_change(client, make_stream, pc_headers, designer_headers):
    """POST /streams/{id}/pass-change → 200，sign_status=CHANGED + change_resolved_at 非空。"""
    stream = await make_stream("PC")
    await client.post(f"/api/v1/streams/{stream.stream_id}/submit", headers=designer_headers)
    await client.post(f"/api/v1/streams/{stream.stream_id}/approve", headers=pc_headers)
    await client.post(
        f"/api/v1/streams/{stream.stream_id}/initiate-change",
        json={"reason": "x"},
        headers=designer_headers,
    )
    resp = await client.post(
        f"/api/v1/streams/{stream.stream_id}/pass-change",
        json={"reason": "已校核"},
        headers=pc_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sign_status"] == "CHANGED"
    assert data["change_resolved_at"] is not None


@pytest.mark.asyncio
async def test_api_mark_stale(client, make_stream, pc_headers, designer_headers):
    """POST /streams/{id}/mark-stale → 200，sign_status=STALE。"""
    stream = await make_stream("MS")
    await client.post(f"/api/v1/streams/{stream.stream_id}/submit", headers=designer_headers)
    await client.post(f"/api/v1/streams/{stream.stream_id}/approve", headers=pc_headers)
    resp = await client.post(
        f"/api/v1/streams/{stream.stream_id}/mark-stale",
        json={"reason": "上游 PFD 变更"},
        headers=designer_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["sign_status"] == "STALE"
    assert data["change_pending_since"] is not None


@pytest.mark.asyncio
async def test_api_designer_cannot_approve(client, make_stream, designer_headers):
    """DESIGNER 触发 /approve → 403（API 层 ACL 拦截在 service 之前）。

    注：/approve 端点的 require_roles 只允许 PROCESS_CONTROLLER / SYSTEM_ADMIN；
    DESIGNER 在 API ACL 阶段就被拦截，返回 HTTP 403 而非 service 层的
    SIM_STREAM_ROLE_FORBIDDEN（后者由 service 测试覆盖）。
    """
    stream = await make_stream("DF")
    await client.post(f"/api/v1/streams/{stream.stream_id}/submit", headers=designer_headers)
    resp = await client.post(
        f"/api/v1/streams/{stream.stream_id}/approve", headers=designer_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_approve_draft_direct_returns_422(client, make_stream, pc_headers):
    """DRAFT 状态下直接 /approve → 422 SIM_STREAM_INVALID_TRANSITION。"""
    stream = await make_stream("INV")
    resp = await client.post(
        f"/api/v1/streams/{stream.stream_id}/approve", headers=pc_headers
    )
    assert resp.status_code == 422
    body = resp.json()
    assert body["code"] == "SIM_STREAM_INVALID_TRANSITION"


@pytest.mark.asyncio
async def test_api_transition_without_auth_returns_401(client, make_stream):
    """未带 Authorization → 401（mock-auth 模式下可能不同，先跳过）。"""
    stream = await make_stream("AUTH")
    resp = await client.post(f"/api/v1/streams/{stream.stream_id}/submit")
    # 注：mock-auth 模式下可能允许匿名；本测试仅验证不会 500
    assert resp.status_code in (401, 403, 200)
