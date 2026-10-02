"""F-P3-003 Sprint 3: Workspace archive PATCH 端点测试.

覆盖:
- test_archive_workspace_success: ACTIVE → ARCHIVED 200
- test_archive_workspace_requires_admin_403: 非 SYSTEM_ADMIN 403
- test_archive_workspace_not_found_404: workspace 不存在 404
- test_archive_workspace_idempotent_200: 重复归档 → 200 幂等

参考: pcs-backend/alembic/versions/p7_s3_001_workspace_status.py.
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.security import create_access_token
from app.models.enums import WorkspaceStatus
from app.models.project import Workspace

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# 测试 token fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_token() -> str:
    return create_access_token(subject="admin-user", role="SYSTEM_ADMIN")


@pytest.fixture
def designer_token() -> str:
    return create_access_token(subject="designer-user", role="DESIGNER")


@pytest.fixture
def reviewer_token() -> str:
    return create_access_token(subject="reviewer-user", role="REVIEWER")


# ---------------------------------------------------------------------------
# 工厂: 创建 workspace 行 (避免依赖 POST /workspaces 路由的复杂初始化)
# ---------------------------------------------------------------------------


async def _create_workspace(db, *, workspace_type: str = "FORMAL", name: str = "test-ws"):
    ws = Workspace(
        workspace_type=workspace_type,
        name=name,
        status=WorkspaceStatus.ACTIVE.value,
    )
    db.add(ws)
    await db.flush()
    return ws


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_archive_workspace_success(client, db, admin_token):
    """PATCH /workspaces/{id}/archive: ACTIVE → ARCHIVED 200."""
    ws = await _create_workspace(db)
    await db.commit()

    r = await client.patch(
        f"/api/v1/workspaces/{ws.workspace_id}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["status"] == "ARCHIVED"

    # verify DB
    await db.refresh(ws)
    assert ws.status == "ARCHIVED"


async def test_archive_workspace_requires_admin_403(client, db, designer_token):
    """非 SYSTEM_ADMIN 角色 → 403."""
    ws = await _create_workspace(db)
    await db.commit()

    r = await client.patch(
        f"/api/v1/workspaces/{ws.workspace_id}/archive",
        headers={"Authorization": f"Bearer {designer_token}"},
    )
    assert r.status_code == 403, r.text


async def test_archive_workspace_not_found_404(client, db, admin_token):
    """workspace_id 不存在 → 404."""
    import uuid
    fake_id = uuid.uuid4()

    r = await client.patch(
        f"/api/v1/workspaces/{fake_id}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 404, r.text


async def test_archive_workspace_idempotent_200(client, db, admin_token):
    """重复归档 → 200 幂等返回 (不报 409)."""
    ws = await _create_workspace(db)
    await db.commit()

    # first archive
    r1 = await client.patch(
        f"/api/v1/workspaces/{ws.workspace_id}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r1.status_code == 200
    assert r1.json()["status"] == "ARCHIVED"

    # second archive — must be idempotent (not 409)
    r2 = await client.patch(
        f"/api/v1/workspaces/{ws.workspace_id}/archive",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r2.status_code == 200, f"expected 200 idempotent, got {r2.status_code}: {r2.text}"
    assert r2.json()["status"] == "ARCHIVED"


async def test_archive_workspace_unauthenticated_401(client, db):
    """无 token → 401."""
    import uuid
    fake_id = uuid.uuid4()

    r = await client.patch(f"/api/v1/workspaces/{fake_id}/archive")
    assert r.status_code in (401, 403), r.text


async def test_workspace_model_has_status_column(db):
    """Workspace model 应有 status 列 (B.2 ORM 改动验证)."""
    ws = Workspace(
        workspace_type="FORMAL",
        name="verify-status",
    )
    db.add(ws)
    await db.flush()

    # 验证默认是 ACTIVE
    assert ws.status == WorkspaceStatus.ACTIVE.value

    # 验证列在表里
    cols = {c.name for c in Workspace.__table__.columns}
    assert "status" in cols