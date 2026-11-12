"""`scripts/seed_e2e_data.py` 的测试 —— 核心是**幂等**（P10-A · Review Focus #4）。

为什么幂等是硬要求：E2E 每次跑之前都要重置种子 ⇒ 脚本不幂等 ⇒
第二次跑要么撞唯一约束（`users.username` / `uq_user_projects_user_project`），
要么留下脏数据让断言飘。**两种失败都很难查** ⇒ 在这里钉死。

⚠️ 另有一条容易漏的：`--reset` **只删自己造的**（按固定 UUID 筛）——
不筛的话会连**业务数据**一起删掉（开发库里跑一次脚本 = 数据没了）。
"""
from __future__ import annotations

import uuid

from sqlalchemy import func, select

from app.models.project import Project, Stream, User, UserProject, Workspace
from scripts.seed_e2e_data import (
    SEED_PROJECT_ROLE,
    SEED_USERNAMES,
    seed,
)


async def _count(db, model) -> int:
    return int((await db.execute(select(func.count()).select_from(model))).scalar_one())


async def test_seed_is_idempotent(db_session) -> None:
    """跑两遍 ⇒ 不炸、行数不变、返回同一组计数。

    ⚠️ 返回值是**种子集合的行数**（不是「本次新建几行」）⇒
    两遍相等就是幂等的直接证据。
    """
    first = await seed(db_session)
    second = await seed(db_session)

    assert first == second
    assert first["projects"] == 1
    assert first["streams"] >= 1
    assert first["users"] == len(SEED_USERNAMES)
    assert first["user_projects"] == len(SEED_USERNAMES)

    # 行数没有翻倍
    assert await _count(db_session, Project) == 1
    assert await _count(db_session, Workspace) == 1
    assert await _count(db_session, User) == len(SEED_USERNAMES)
    assert await _count(db_session, UserProject) == len(SEED_USERNAMES)
    assert await _count(db_session, Stream) == first["streams"]


async def test_reset_only_deletes_our_own_rows(db_session) -> None:
    """⚠️ `--reset` 只删**种子集合**的行 ⇒ 别人的数据一行不动。

    这是「脚本能安全地在开发库上跑」的前提。
    """
    # 一条**不属于**种子集合的外部数据
    other_ws = Workspace(
        workspace_id=uuid.uuid4(),
        workspace_type="FORMAL",
        name="外部工作区",
        status="ACTIVE",
    )
    db_session.add(other_ws)
    await db_session.commit()

    await seed(db_session, reset=True)

    remaining = (
        await db_session.execute(
            select(Workspace).where(Workspace.workspace_id == other_ws.workspace_id)
        )
    ).scalar_one_or_none()
    assert remaining is not None, "--reset 把不属于种子集合的工作区删了"

    # 自己的行被删过又重建（⇒ 仍然只有 1 个）
    assert await _count(db_session, Workspace) == 2  # 外部 1 + 种子 1


async def test_seed_grants_project_access(db_session) -> None:
    """⚠️ **必须造 `UserProject` 行** ⇒ 否则带项目守卫的端点**全 404**
    （这正是 P9B-4 紧急批次的教训：守卫按「有无授权行」判定）。
    """
    await seed(db_session)
    rows = (
        await db_session.execute(select(UserProject))
    ).scalars().all()
    assert len(rows) == len(SEED_USERNAMES)
    for row in rows:
        assert row.role_in_project == SEED_PROJECT_ROLE


async def test_seed_users_have_empty_roles(db_session) -> None:
    """⚠️ `User.roles` 写**空数组**（P9B-4 T0-E 之后）——
    真实登录会**覆盖**它（不是合并）⇒ 预置角色也白写。
    """
    await seed(db_session)
    rows = (await db_session.execute(select(User))).scalars().all()
    assert rows
    for row in rows:
        assert row.roles == []


async def test_seed_users_use_derived_user_ids(db_session) -> None:
    """⚠️ user_id 必须是**派生值** `uuid5(NAMESPACE_DNS, username)`。

    ⇒ 与 mock 登录 / 真实登录算出的 id 一致 ⇒ 否则授权行对不上 ⇒
    **处处 404**（CLAUDE.md「部署前置」的同一条道理）。
    """
    await seed(db_session)
    rows = (await db_session.execute(select(User))).scalars().all()
    by_name = {r.username: r for r in rows}
    for username in SEED_USERNAMES:
        assert by_name[username].user_id == uuid.uuid5(uuid.NAMESPACE_DNS, username)


# === 评审 #1 / #9（2026-11-12 评审修复批） ===


async def test_reset_preserves_a_foreign_user_row(db_session) -> None:
    """⚠️ **评审 #1** —— `--reset` 不得删掉/重建**不是自己造的** users 行。

    `user_id` 是**派生值** `uuid5(NAMESPACE_DNS, username)` ⇒ 与真实 LDAP
    登录算出的 id **完全相同** ⇒ 旧实现按派生 id 无条件 `delete(User)`
    ⇒ 在开发库上跑一次 `--reset` = **真实账号被删**（roles / status /
    token_version 全丢，且其 `user_projects` 授权行被 CASCADE 掉），
    而下一次登录会把它**重建为 ACTIVE** ⇒ **被停用的账号被悄悄启用**。

    ⇒ 契约：reset **不碰 users 表**；已存在的行连 `status`/`roles` 都不许改。
    """
    from app.models.project import User
    from app.services.token_issuer import derive_user_id

    alice_id = derive_user_id("alice")
    db_session.add(
        User(
            user_id=alice_id,
            username="alice",
            display_name="Alice (LDAP)",
            roles=["SYSTEM_ADMIN"],
            ad_groups=["cn=admins"],
            status="DISABLED",
        )
    )
    await db_session.commit()

    await seed(db_session, reset=True)

    row = (
        await db_session.execute(select(User).where(User.user_id == alice_id))
    ).scalar_one_or_none()
    assert row is not None, "--reset 把真实账号删了"
    assert row.status == "DISABLED", "--reset 把停用账号重新启用了"
    assert row.roles == ["SYSTEM_ADMIN"], "--reset 覆盖了真实账号的角色"


async def test_seed_recovers_when_the_row_appears_between_select_and_insert(
    db_session, monkeypatch
) -> None:
    """⚠️ **评审 #9** —— get-or-create 必须是**本仓的 house 形状**：
    `db.add` 在 `begin_nested()` 之内 ⇒ 撞唯一约束时**回滚 savepoint**
    （不是整笔事务）⇒ **重读赢家**（只读、不 update）⇒ 绝不炸。

    ⚠️ 旧实现是「裸 SELECT ⇒ 空 ⇒ INSERT」：**没有 savepoint** ⇒ 撞约束后
    整笔事务被污染 ⇒ 重读也读不到 ⇒ 脚本直接炸 ⇒ E2E 通道起不来。
    """
    from app.models.project import User
    from app.services.token_issuer import derive_user_id
    from scripts.seed_e2e_data import _ensure_users

    # 「对手」先插好了赢家行
    alice_id = derive_user_id("alice")
    db_session.add(
        User(
            user_id=alice_id,
            username="alice",
            display_name="alice",
            roles=[],
            ad_groups=[],
            status="ACTIVE",
        )
    )
    await db_session.commit()

    # 让**第一次** SELECT 谎报「没有」（= 对手在 SELECT 之后才插进去）
    real_execute = db_session.execute
    calls = {"n": 0}

    class _EmptyResult:
        def scalar_one_or_none(self):  # noqa: D102
            return None

    async def racing_execute(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return _EmptyResult()
        return await real_execute(*args, **kwargs)

    monkeypatch.setattr(db_session, "execute", racing_execute)

    users = await _ensure_users(db_session)  # 撞约束 ⇒ 必须被接住

    assert len(users) == 4
    assert users[0].user_id == alice_id
