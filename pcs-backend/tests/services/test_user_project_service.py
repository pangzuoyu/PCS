"""P7-7+ UserProjectService tests (BLOCKER-3 全面修复).

覆盖:
1. grant_project_access 新建 + 重复 grant 覆盖
2. revoke_project_access 撤销 + revoked_at 保留历史
3. check_user_project_access 有/无/已撤销
4. list_user_projects 默认排除 revoked
5. invalid role 抛 ValueError
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import UserProject
from app.services.user_project_service import UserProjectService


@pytest.mark.asyncio
async def test_grant_creates_new_user_project(db_session: AsyncSession):
    """新建 UserProject 行 (user_id+project_id 之前不存在)。"""
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    granted_by = uuid.uuid4()
    record = await UserProjectService.grant_project_access(
        db_session,
        user_id=user_id,
        project_id=project_id,
        role_in_project="DESIGNER",
        granted_by=granted_by,
    )
    assert record.user_id == user_id
    assert record.project_id == project_id
    assert record.role_in_project == "DESIGNER"
    assert record.granted_by == granted_by
    assert record.revoked_at is None


@pytest.mark.asyncio
async def test_grant_overwrites_existing_role(db_session: AsyncSession):
    """重复 grant 同 (user_id, project_id) 覆盖 role 不创建新行。"""
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    await UserProjectService.grant_project_access(
        db_session,
        user_id=user_id, project_id=project_id,
        role_in_project="DESIGNER",
    )
    record2 = await UserProjectService.grant_project_access(
        db_session,
        user_id=user_id, project_id=project_id,
        role_in_project="APPROVER",
    )
    # 行数应为 1 (覆盖)
    from sqlalchemy import select, func
    cnt = (await db_session.execute(
        select(func.count()).select_from(UserProject).where(
            UserProject.user_id == user_id,
            UserProject.project_id == project_id,
        )
    )).scalar_one()
    assert cnt == 1
    assert record2.role_in_project == "APPROVER"
    assert record2.id is not None


@pytest.mark.asyncio
async def test_grant_invalid_role_raises(db_session: AsyncSession):
    """非 5 角色之一抛 ValueError。"""
    with pytest.raises(ValueError, match="role_in_project"):
        await UserProjectService.grant_project_access(
            db_session,
            user_id=uuid.uuid4(), project_id=uuid.uuid4(),
            role_in_project="INVALID_ROLE",
        )


@pytest.mark.asyncio
async def test_revoke_sets_revoked_at(db_session: AsyncSession):
    """revoke 后 revoked_at 非空, 保留行 (历史)。"""
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    granted_by = uuid.uuid4()
    record = await UserProjectService.grant_project_access(
        db_session,
        user_id=user_id, project_id=project_id,
        role_in_project="DESIGNER", granted_by=granted_by,
    )
    revoked = await UserProjectService.revoke_project_access(
        db_session,
        user_id=user_id, project_id=project_id, revoked_by=granted_by,
    )
    assert revoked is not None
    assert revoked.id == record.id  # 同一行
    assert revoked.revoked_at is not None
    assert revoked.revoked_by == granted_by


@pytest.mark.asyncio
async def test_check_user_project_access_granted(db_session: AsyncSession):
    """check_user_project_access: granted user → True。"""
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    await UserProjectService.grant_project_access(
        db_session,
        user_id=user_id, project_id=project_id, role_in_project="DESIGNER",
    )
    has_access = await UserProjectService.check_user_project_access(
        db_session, user_id=user_id, project_id=project_id,
    )
    assert has_access is True


@pytest.mark.asyncio
async def test_check_user_project_access_not_granted(db_session: AsyncSession):
    """check_user_project_access: 无 UserProject 行 → False。"""
    has_access = await UserProjectService.check_user_project_access(
        db_session,
        user_id=uuid.uuid4(), project_id=uuid.uuid4(),
    )
    assert has_access is False


@pytest.mark.asyncio
async def test_check_user_project_access_revoked(db_session: AsyncSession):
    """check_user_project_access: 已 revoke → False (虽然行存在)。"""
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    await UserProjectService.grant_project_access(
        db_session,
        user_id=user_id, project_id=project_id, role_in_project="DESIGNER",
    )
    await UserProjectService.revoke_project_access(
        db_session,
        user_id=user_id, project_id=project_id, revoked_by=uuid.uuid4(),
    )
    has_access = await UserProjectService.check_user_project_access(
        db_session, user_id=user_id, project_id=project_id,
    )
    assert has_access is False


@pytest.mark.asyncio
async def test_check_user_project_access_required_role(db_session: AsyncSession):
    """check_user_project_access(required_role=...): 角色不匹配 → False。"""
    user_id = uuid.uuid4()
    project_id = uuid.uuid4()
    await UserProjectService.grant_project_access(
        db_session,
        user_id=user_id, project_id=project_id, role_in_project="DESIGNER",
    )
    # DESIGNER != APPROVER → False
    has_access = await UserProjectService.check_user_project_access(
        db_session, user_id=user_id, project_id=project_id,
        required_role="APPROVER",
    )
    assert has_access is False
    # DESIGNER == DESIGNER → True
    has_access = await UserProjectService.check_user_project_access(
        db_session, user_id=user_id, project_id=project_id,
        required_role="DESIGNER",
    )
    assert has_access is True


@pytest.mark.asyncio
async def test_list_user_projects_excludes_revoked(db_session: AsyncSession):
    """list_user_projects 默认排除 revoked。"""
    user_id = uuid.uuid4()
    proj_active = uuid.uuid4()
    proj_revoked = uuid.uuid4()
    await UserProjectService.grant_project_access(
        db_session, user_id=user_id, project_id=proj_active,
        role_in_project="DESIGNER",
    )
    await UserProjectService.grant_project_access(
        db_session, user_id=user_id, project_id=proj_revoked,
        role_in_project="DESIGNER",
    )
    await UserProjectService.revoke_project_access(
        db_session, user_id=user_id, project_id=proj_revoked,
        revoked_by=uuid.uuid4(),
    )
    projects = await UserProjectService.list_user_projects(
        db_session, user_id=user_id
    )
    assert len(projects) == 1
    assert projects[0].project_id == proj_active


@pytest.mark.asyncio
async def test_list_user_projects_includes_revoked(db_session: AsyncSession):
    """list_user_projects(include_revoked=True) 含 revoked。"""
    user_id = uuid.uuid4()
    proj_active = uuid.uuid4()
    proj_revoked = uuid.uuid4()
    await UserProjectService.grant_project_access(
        db_session, user_id=user_id, project_id=proj_active, role_in_project="DESIGNER",
    )
    await UserProjectService.grant_project_access(
        db_session, user_id=user_id, project_id=proj_revoked, role_in_project="DESIGNER",
    )
    await UserProjectService.revoke_project_access(
        db_session, user_id=user_id, project_id=proj_revoked, revoked_by=uuid.uuid4(),
    )
    projects = await UserProjectService.list_user_projects(
        db_session, user_id=user_id, include_revoked=True
    )
    assert len(projects) == 2


async def test_project_lead_role_is_grantable(db, user_id, project_id):
    """⚠️ 「项目负责人」（`PROJECT_LEAD`）是合法项目内角色（用户 2026-10-26 裁决）。

    「只有项目负责人能绑签署矩阵」⇒ 这个角色**必须能被授予** ⇒
    词表里没有它 = 守卫永远 403 = 功能不可用。
    """
    record = await UserProjectService.grant_project_access(
        db,
        user_id=user_id,
        project_id=project_id,
        role_in_project="PROJECT_LEAD",
    )
    assert record.role_in_project == "PROJECT_LEAD"


# ---------------------------------------------------------------------------
# get-or-create 的 savepoint 兜底（ce-code-review P2 #11 · bug-2149）
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_grant_insert_failure_does_not_abort_the_caller_transaction(
    db_session: AsyncSession, monkeypatch
):
    """撞唯一约束时**不得**中止**调用方**的事务。

    ## 为什么（ce-code-review P2 #11）

    `grant_project_access` 是**无锁 get-or-create**（`SELECT` 后 `INSERT`），
    而 `users` / `user_projects` 都有唯一约束 ⇒ 两个并发请求都会「SELECT-见空」
    ⇒ 都 INSERT ⇒ 输家撞约束。

    ⚠️ **savepoint 之外的 INSERT 撞约束会中止整个事务** ⇒ 调用方
    （`POST /projects`）的**项目 INSERT 与本插入同事务** ⇒ 整体回滚 ⇒
    偶发 500 + 项目建不出来。

    ⇒ 配方（`docs/solutions/database-issues/get-or-create-default-row-race-savepoint-reread.md`）：
    `db.add()` 放进 `async with db.begin_nested():` 之内。

    ## 本测试钉什么

    真正的并发赢家**在 SQLite 上复现不了**（单连接串行）⇒ 这里钉**配方本身**：
    插入失败**之后**，**调用方的事务仍然可用**（未被 abort）。
    """
    from sqlalchemy.exc import IntegrityError

    original_flush = db_session.flush

    async def boom(*args, **kwargs):
        raise IntegrityError(
            "INSERT INTO user_projects ...",
            None,
            Exception("模拟唯一约束冲突"),
        )

    monkeypatch.setattr(db_session, "flush", boom)

    with pytest.raises(IntegrityError):
        await UserProjectService.grant_project_access(
            db_session,
            user_id=uuid.uuid4(),
            project_id=uuid.uuid4(),
            role_in_project="DESIGNER",
            granted_by=uuid.uuid4(),
        )

    # ⚠️⚠️ **关键**：调用方的事务**没有被中止** ⇒ 后续 DB 操作照常
    #    （没有 savepoint 时这里会抛 `PendingRollbackError` ⇒ 整个项目创建回滚）
    monkeypatch.setattr(db_session, "flush", original_flush)
    from sqlalchemy import func, select

    count = (
        await db_session.execute(select(func.count()).select_from(UserProject))
    ).scalar_one()
    assert count == 0


@pytest.mark.asyncio
async def test_ensure_user_row_insert_failure_does_not_abort_the_caller_transaction(
    db_session: AsyncSession, monkeypatch
):
    """`ensure_user_row` 同款：撞唯一约束**不得**中止调用方的事务。

    见上一条的说明（同一个配方、同一个理由）。`ensure_user_row` 是
    `POST /projects` 的**必经之路**（`user_projects.user_id` 是 NOT NULL FK）
    ⇒ 它一旦中止事务 ⇒ 建项目整体回滚。
    """
    from sqlalchemy.exc import IntegrityError

    from app.services.user_project_service import ensure_user_row

    original_flush = db_session.flush

    async def boom(*args, **kwargs):
        raise IntegrityError(
            "INSERT INTO users ...",
            None,
            Exception("模拟唯一约束冲突"),
        )

    monkeypatch.setattr(db_session, "flush", boom)

    with pytest.raises(IntegrityError):
        await ensure_user_row(
            db_session,
            user_id=uuid.uuid4(),
            username="savepoint-user",
        )

    monkeypatch.setattr(db_session, "flush", original_flush)
    from sqlalchemy import func, select

    from app.models.project import User

    count = (
        await db_session.execute(select(func.count()).select_from(User))
    ).scalar_one()
    assert count == 0
