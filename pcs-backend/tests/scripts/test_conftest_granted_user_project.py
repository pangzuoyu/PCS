"""BLOCKER-3 conftest fixture 集成测试.

验证 granted_user_project fixture 自动 grant UserProject 访问权,
让既有测试透明通过 BLOCKER-3 _check_project_access_or_404 守卫.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import UserProject
from app.services.user_project_service import UserProjectService


@pytest.mark.asyncio
async def test_granted_user_project_fixture_creates_row(
    db_session: AsyncSession, user_id, project_id,
):
    """granted_user_project fixture: 自动 grant UserProject 行."""
    # 调用 fixture (隐式通过参数列表)
    # fixture 内部已 grant DESIGNER 角色
    stmt = select(UserProject).where(
        UserProject.user_id == user_id,
        UserProject.project_id == project_id,
        UserProject.revoked_at.is_(None),
    )
    row = (await db_session.execute(stmt)).scalars().first()
    assert row is not None
    assert row.role_in_project == "DESIGNER"


@pytest.mark.asyncio
async def test_granted_user_project_check_access(
    db_session: AsyncSession, user_id, project_id,
):
    """granted_user_project 后, check_user_project_access 返回 True."""
    has_access = await UserProjectService.check_user_project_access(
        db_session, user_id=user_id, project_id=project_id,
    )
    assert has_access is True


@pytest.mark.asyncio
async def test_granted_user_project_idempotent(
    db_session: AsyncSession, user_id, project_id,
):
    """granted_user_project 重复调用 idempotent (不创建重复行)."""
    from app.services.user_project_service import UserProjectService
    # 二次调用 (模拟其他 fixture 可能再次 grant)
    await UserProjectService.grant_project_access(
        db_session, user_id=user_id, project_id=project_id,
        role_in_project="APPROVER",  # 第二次换成不同角色
    )
    stmt = select(UserProject).where(
        UserProject.user_id == user_id,
        UserProject.project_id == project_id,
        UserProject.revoked_at.is_(None),
    )
    rows = (await db_session.execute(stmt)).scalars().all()
    # 应该只 1 行 (覆盖更新)
    assert len(rows) == 1
    assert rows[0].role_in_project == "APPROVER"
