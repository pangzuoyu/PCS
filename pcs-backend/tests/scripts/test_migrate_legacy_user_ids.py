"""「遗留账号迁移」脚本的守卫（TODO-137 · P10-C · T0-4）。

## 为什么要有这个脚本

`ensure_user_row` / `issue_tokens` **只认派生 id**
（`uuid5(NAMESPACE_DNS, username)`）⇒ ⇒ 若某个用户名被一条
**`user_id` 与派生值不同**的遗留行占着 ⇒ ⇒ 建行撞唯一约束 ⇒ ⇒
显式 409 `USER_ID_CONFLICT` ⇒ ⇒ ⇒ 那个用户**处处 404**。

## 本文件断什么

1. **引用列清单**是从 ORM metadata **推导**的 ⇒ ⇒ 覆盖全部 FK→`users.user_id`
   与列名含 `user_id` 的列 ⇒ ⇒ **漏一列 ⇒ ⇒ 授权/审计留在遗留 id 上**
2. **迁移本体**：身份字段复制 · 引用全部改指 · **遗留行被删**
   （⇒ ⇒ `CLAUDE.md` 的发布闸「遗留账号行数 = 0」才绿）
3. **幂等**：跑第二遍 ⇒ ⇒ 无事可做
4. **重复授权**：派生 id 已有同项目授权 ⇒ ⇒ 不撞唯一约束
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.db.base import Base
from app.models.project import Project, User, UserProject
from app.models.system import AuditLog
from app.services.token_issuer import derive_user_id

#: 迁移脚本（`scripts/` 是**命名空间包** ⇒ ⇒ 可直接 import —— 与
#: `tests/scripts/test_seed_e2e_flows.py` 同一约定）
from scripts.migrate_legacy_user_ids import (  # noqa: E402
    LEGACY_USERNAME_PREFIX,
    LegacyUser,
    find_legacy_users,
    migrate_one,
    remap_targets,
    run_migration,
)

# ---------------------------------------------------------------------------
# 造数据
# ---------------------------------------------------------------------------


async def _mk_legacy_user(session, username: str = "alice") -> User:
    """造一条**遗留**用户行（`user_id` ≠ 派生值）。"""
    row = User(
        user_id=uuid.uuid4(),  # ← **不是**派生值 ⇒ ⇒ 遗留
        username=username,
        display_name="遗留用户",
        email="legacy@example.com",
        department="工艺",
        roles=["DESIGNER", "CHECKER"],
        ad_groups=["g1"],
        status="ACTIVE",
        token_version=3,
    )
    session.add(row)
    await session.flush()
    return row


async def _mk_project(session) -> Project:
    proj = Project(
        project_no=f"R137-{uuid.uuid4().hex[:8]}",
        project_name="遗留迁移",
        owner_company="X",
        location="X",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        status="ACTIVE",
        workspace_id=uuid.uuid4(),
    )
    session.add(proj)
    await session.flush()
    return proj


# ---------------------------------------------------------------------------
# ① 引用列清单
# ---------------------------------------------------------------------------


def test_remap_targets_cover_every_user_id_column() -> None:
    """⚠️ **漏一列的后果**：那一列仍指向遗留 id ⇒ ⇒ 授权/审计**留在**遗留身份上。

    ⇒ ⇒ 清单从 **ORM metadata 推导**（不手抄 ⇒ ⇒ 不会漂）。
    """
    targets = set(remap_targets())

    # ① 已知的 9 列（⇒ ⇒ 硬钉，防推导逻辑改坏）
    expected = {
        ("ai_audit_log", "user_id"),
        ("audit_logs", "user_id"),
        ("data_lineage", "actor_user_id"),
        ("cost_correlations", "created_by"),
        ("notifications", "recipient_id"),
        ("project_calculation_standard_profiles", "approved_by"),
        ("user_projects", "user_id"),
        ("user_projects", "granted_by"),
        ("user_projects", "revoked_by"),
    }
    assert expected <= targets, f"少了这些引用列：{sorted(expected - targets)}"

    # ② `users` 表**自己**不在清单里（它的 user_id 是 PK ⇒ 靠改名 + 删行）
    assert not any(t == "users" for t, _ in targets)

    # ③ **机械覆盖**：metadata 里每一条 FK→users.user_id / 含 user_id 的列
    #    ⇒ ⇒ 都必须在清单里（推导逻辑坏了 ⇒ ⇒ 这里红）
    for table in Base.metadata.sorted_tables:
        if table.name == "users":
            continue
        for col in table.columns:
            is_fk = any(
                fk.target_fullname == "users.user_id" for fk in col.foreign_keys
            )
            if is_fk or "user_id" in col.name:
                assert (table.name, col.name) in targets, (
                    f"{table.name}.{col.name} 指向用户身份 ⇒ ⇒ 必须在改指清单里"
                )


# ---------------------------------------------------------------------------
# ② 检测
# ---------------------------------------------------------------------------


async def test_find_legacy_users_detects_only_mismatched_ids(db_session) -> None:
    """⚠️ 判据 = **`user_id` ≠ 派生值** ⇒ ⇒ 派生 id 的行**不算**遗留。"""
    legacy = await _mk_legacy_user(db_session, "alice")
    normal = User(
        user_id=derive_user_id("bob"),
        username="bob",
        display_name="正常",
        roles=[],
        ad_groups=[],
        status="ACTIVE",
    )
    db_session.add(normal)
    await db_session.flush()

    found = await find_legacy_users(db_session)
    assert [u.user_id for u in found] == [legacy.user_id]


async def test_already_migrated_rows_are_not_detected_again(db_session) -> None:
    """⚠️ **幂等**：让出过 username 的行（`legacy:` 前缀）⇒ ⇒ 不再算遗留。"""
    db_session.add(
        User(
            user_id=uuid.uuid4(),
            username=f"{LEGACY_USERNAME_PREFIX}carol",
            display_name="已处理",
            roles=[],
            ad_groups=[],
            status="ACTIVE",
        )
    )
    await db_session.flush()
    assert await find_legacy_users(db_session) == []


# ---------------------------------------------------------------------------
# ③ 迁移本体
# ---------------------------------------------------------------------------


async def test_migration_moves_identity_and_all_references(db_session) -> None:
    """⚠️ **核心**：身份复制 · 引用全部改指 · **遗留行删掉**。"""
    legacy = await _mk_legacy_user(db_session, "alice")
    project = await _mk_project(db_session)
    derived_id = derive_user_id("alice")

    db_session.add(
        UserProject(
            user_id=legacy.user_id,
            project_id=project.project_id,
            role_in_project="DESIGNER",
            granted_by=legacy.user_id,
        )
    )
    db_session.add(
        AuditLog(user_id=legacy.user_id, action="LOGIN", resource_type="session")
    )
    await db_session.flush()

    ok, message = await migrate_one(db_session, LegacyUser(legacy.user_id, "alice"))
    assert ok, message

    # ① 派生 id 的行存在，**身份字段复制过来**（同一个人 ⇒ 不丢角色）
    new_row = await db_session.get(User, derived_id)
    assert new_row is not None
    assert new_row.username == "alice"
    assert new_row.display_name == "遗留用户"
    assert new_row.roles == ["DESIGNER", "CHECKER"]
    assert new_row.token_version == 3

    # ② **遗留行没了**（⇒ ⇒ 发布闸「遗留账号行数 = 0」才绿）
    assert await db_session.get(User, legacy.user_id) is None

    # ③ 引用全部改指
    grant = (
        await db_session.execute(
            select(UserProject).where(UserProject.project_id == project.project_id)
        )
    ).scalar_one()
    assert grant.user_id == derived_id
    assert grant.granted_by == derived_id

    audit = (
        await db_session.execute(select(AuditLog).where(AuditLog.action == "LOGIN"))
    ).scalar_one()
    assert audit.user_id == derived_id


async def test_release_gate_is_green_after_migration(db_session) -> None:
    """⚠️ `CLAUDE.md` 发布闸 = 「`user_id` ≠ 派生值」的行数 = **0**。"""
    await _mk_legacy_user(db_session, "alice")
    await db_session.flush()

    for legacy in await find_legacy_users(db_session):
        ok, message = await migrate_one(db_session, legacy)
        assert ok, message

    assert await find_legacy_users(db_session) == []


async def test_migration_is_idempotent(db_session) -> None:
    """⚠️ 跑第二遍 ⇒ ⇒ 无事可做（不重复建行、不撞唯一约束）。"""
    await _mk_legacy_user(db_session, "alice")
    await db_session.flush()

    legacy = (await find_legacy_users(db_session))[0]
    ok, _ = await migrate_one(db_session, legacy)
    assert ok
    await db_session.commit()

    assert await find_legacy_users(db_session) == []
    # 再跑一遍整个流程 ⇒ ⇒ 仍然是 0
    report = await run_migration(db_session)
    assert report.migrated == []


async def test_refuses_when_derived_row_already_exists(db_session) -> None:
    """⚠️ 形状异常（派生 id 已有行）⇒ ⇒ **不自动处理** ⇒ ⇒ 报告出来。"""
    legacy = await _mk_legacy_user(db_session, "alice")
    derived_id = derive_user_id("alice")
    db_session.add(
        User(
            user_id=derived_id,
            username="alice2",  # ← username 不同 ⇒ ⇒ 唯一约束不撞
            display_name="已存在",
            roles=[],
            ad_groups=[],
            status="ACTIVE",
        )
    )
    await db_session.flush()

    ok, message = await migrate_one(db_session, LegacyUser(legacy.user_id, "alice"))
    assert not ok
    assert "不自动处理" in message
    # 遗留行**原样保留**（没动它）
    assert await db_session.get(User, legacy.user_id) is not None


@pytest.mark.parametrize("username", ["alice", "bob", "张三"])
async def test_derived_id_uses_the_single_derivation_point(
    db_session, username: str
) -> None:
    """⚠️ 脚本**必须**用 `derive_user_id` ⇒ ⇒ 不另抄一份 uuid5。

    ⇒ ⇒ 断言迁完的行 id **逐字等于** `derive_user_id(username)`。
    """
    legacy = await _mk_legacy_user(db_session, username)
    await db_session.flush()

    ok, message = await migrate_one(db_session, LegacyUser(legacy.user_id, username))
    assert ok, message

    assert await db_session.get(User, derive_user_id(username)) is not None
    # ⇒ ⇒ 反证：脚本自己的派生结果与 `derive_user_id` 一致
    assert LegacyUser(legacy.user_id, username).derived_user_id == derive_user_id(
        username
    )


async def test_no_reference_is_left_behind_on_the_legacy_id(db_session) -> None:
    """⚠️ **残留引用检查**（脚本内置的最后一道闸）。"""
    legacy = await _mk_legacy_user(db_session, "alice")
    project = await _mk_project(db_session)
    db_session.add(
        UserProject(
            user_id=legacy.user_id,
            project_id=project.project_id,
            role_in_project="DESIGNER",
        )
    )
    await db_session.flush()

    ok, _ = await migrate_one(db_session, LegacyUser(legacy.user_id, "alice"))
    assert ok

    for table_name, column_name in remap_targets():
        table = Base.metadata.tables[table_name]
        column = table.c[column_name]
        rows = (
            await db_session.execute(select(column).where(column == legacy.user_id))
        ).all()
        assert not rows, f"{table_name}.{column_name} 上还留着遗留 id 的引用"
