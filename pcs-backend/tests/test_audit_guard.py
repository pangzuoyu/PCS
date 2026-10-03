"""P7-7+ BLOCKER-3 guard 集成测试 — /equipment-deletion-audit 端点.

F-P0-001 R1 / Sprint 3 增量: audit endpoint 接入 check_project_access_or_404
(defense-in-depth, 与 RBAC + project_id filter 互补).

覆盖:
- DESIGNER 无 UserProject grant → 404 (guard 拒, _guard.py 故意 404 不泄漏存在性)
- DESIGNER 有 UserProject grant → 200
- SYSTEM_ADMIN bypass guard (与 _guard.py 设计一致)

注: 本测试用独立 client fixture (real_user_project_client), 不应用 conftest.py
的默认 client mock (该 mock 自动 bypass guard 让其他 BLOCKER-3 测试通过).
"""
from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.api.v1._guard import check_project_access_or_404
from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_async_session_factory, get_db
from app.models.equipment import EquipmentDeletionAudit

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def real_user_project_client(db_engine):
    """独立 client — 不应用 conftest.py 的 check_user_project_access bypass mock.
    让 guard 在 HTTP 端点上真正生效。
    """
    from fastapi import FastAPI

    from app.api.v1 import api_router
    from app.core.errors import install_exception_handlers
    from sqlalchemy.ext.asyncio import async_sessionmaker

    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app = FastAPI(title="PCS Test Guard")
    install_exception_handlers(app)
    app.include_router(api_router)
    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def designer_token() -> str:
    return create_access_token(subject="designer-user", role="DESIGNER")


@pytest.fixture
def admin_token() -> str:
    return create_access_token(subject="admin-user", role="SYSTEM_ADMIN")


@pytest.fixture
def designer_user_id() -> uuid.UUID:
    """designer-user 派生 UUID (与 current_actor 一致: uuid5(NAMESPACE_DNS, sub))."""
    return uuid.uuid5(uuid.NAMESPACE_DNS, "designer-user")


async def _insert_audit(db, *, project_id: uuid.UUID):
    row = EquipmentDeletionAudit(
        project_id=project_id,
        workspace_id=uuid.uuid4(),
        equipment_id=uuid.uuid4(),
        equipment_tag="E-GUARD-001",
        deleted_by=uuid.uuid4(),
        orphan_records={},
    )
    db.add(row)
    await db.flush()
    return row


async def test_ungranted_designer_404(real_user_project_client, db, designer_token):
    """P7-7+: DESIGNER 无 grant + project_id filter 命中 → 404 (guard 触发, 不泄漏)."""
    project_id = uuid.uuid4()
    await _insert_audit(db, project_id=project_id)
    await db.commit()

    r = await real_user_project_client.get(
        "/api/v1/equipment-deletion-audit",
        params={"project_id": str(project_id)},
        headers={"Authorization": f"Bearer {designer_token}"},
    )
    assert r.status_code == 404, r.text


async def test_granted_designer_200(real_user_project_client, db, designer_token, designer_user_id):
    """P7-7+: DESIGNER + grant + project_id filter → 200."""
    from app.services.user_project_service import UserProjectService

    project_id = uuid.uuid4()
    await _insert_audit(db, project_id=project_id)
    await UserProjectService.grant_project_access(
        db,
        user_id=designer_user_id,
        project_id=project_id,
        role_in_project="DESIGNER",
    )
    await db.commit()

    r = await real_user_project_client.get(
        "/api/v1/equipment-deletion-audit",
        params={"project_id": str(project_id)},
        headers={"Authorization": f"Bearer {designer_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1


async def test_admin_bypass_guard(real_user_project_client, db, admin_token):
    """P7-7+: SYSTEM_ADMIN 不需要 grant (guard 内 SYSADMIN bypass)."""
    project_id = uuid.uuid4()
    await _insert_audit(db, project_id=project_id)
    await db.commit()

    r = await real_user_project_client.get(
        "/api/v1/equipment-deletion-audit",
        params={"project_id": str(project_id)},
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["total"] == 1