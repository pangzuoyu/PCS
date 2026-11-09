"""「建项目 ⇒ 自动授权创建者」—— P9B-4 紧急批次 T0。

## 为什么这个测试存在

补上**物流面项目守卫**之后，**任何没有 `UserProject` 授权行的用户访问任何
物流端点都 404**。而仓里能持续产生授权行的路径只有
`POST /user-projects/grant`（SYSTEM_ADMIN only、无前端页面）⇒
「**建项目的人自己进不去**」是必然结果 ⇒ 本测试钉住「建项目 ⇒ 自动授权」。

## 三个断言各自钉一件事

1. **授权行存在**（1 行 · `PROJECT_LEAD`）—— 核心不变量。
2. **`users` 行存在**（FK 前置）—— ⚠️ `user_projects.user_id` 是 NOT NULL 的
   FK → `users.user_id`，**PG 强制、SQLite 单测默认不强制** ⇒ 缺这一行，
   本地绿、生产炸 ⇒ 所以这里**直接断言 `users` 行存在**，而不是依赖 SQLite
   的 FK 行为。
3. **幂等** —— 重复授权不产生第二行。

## fixture 沿用 `tests/api/v1/test_project_creation.py` 的本地写法

`admin_headers` / `_make_workspace` / `_payload` 在那边是**模块内**的本地
fixture ⇒ 这里自建同款（不跨测试模块 import）。
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.project import User, UserProject
from app.services.user_project_service import UserProjectService

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# fixtures / helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def admin_headers() -> dict:
    return {
        "Authorization": f"Bearer {create_access_token(subject='admin-user', role='SYSTEM_ADMIN')}"
    }


@pytest.fixture
def creator_user_id() -> uuid.UUID:
    """`admin-user` 的派生 UUID（与 `current_actor` 一致：uuid5(DNS, sub)）。"""
    return uuid.uuid5(uuid.NAMESPACE_DNS, "admin-user")


async def _make_workspace(db_session) -> uuid.UUID:
    from app.models.project import Workspace

    workspace_id = uuid.uuid4()
    db_session.add(
        Workspace(
            workspace_id=workspace_id,
            workspace_type="FORMAL",
            name="WS",
            status="ACTIVE",
        )
    )
    await db_session.commit()
    return workspace_id


def _payload(workspace_id: uuid.UUID, **over: object) -> dict:
    payload = {
        "project_no": f"P-{uuid.uuid4().hex[:8]}",
        "project_name": "测试项目",
        "owner_company": "PCS",
        "location": "惠州",
        "project_type": "PETROLEUM",
        "design_phase": "EXECUTIVE_DESIGN",
        "unit_system": "SI",
        "workspace_id": str(workspace_id),
    }
    payload.update(over)
    return payload


async def _create_project(client, db_session, admin_headers) -> uuid.UUID:
    """建一个项目 ⇒ 返回 project_id。"""
    workspace_id = await _make_workspace(db_session)
    resp = await client.post(
        "/api/v1/projects", json=_payload(workspace_id), headers=admin_headers
    )
    assert resp.status_code == 201, resp.text
    return uuid.UUID(resp.json()["project_id"])


async def _grants(db_session, project_id: uuid.UUID) -> list[UserProject]:
    return list(
        (
            await db_session.execute(
                select(UserProject).where(UserProject.project_id == project_id)
            )
        ).scalars().all()
    )


# ---------------------------------------------------------------------------
# 建项目 ⇒ 自动授权
# ---------------------------------------------------------------------------


async def test_creating_a_project_grants_the_creator_access(
    client, db_session, admin_headers, creator_user_id
):
    """建项目 ⇒ 创建者对该项目有 **1 行** `UserProject`（`PROJECT_LEAD`）。"""
    project_id = await _create_project(client, db_session, admin_headers)

    rows = await _grants(db_session, project_id)
    assert len(rows) == 1, f"应有 1 行授权，实际 {len(rows)} 行"
    row = rows[0]
    assert row.user_id == creator_user_id
    assert row.role_in_project == "PROJECT_LEAD"
    assert row.granted_by == creator_user_id
    assert row.revoked_at is None


async def test_creating_a_project_creates_the_creator_user_row(
    client, db_session, admin_headers, creator_user_id
):
    """⚠️ **FK 前置**：创建者必须先在 `users` 表有行。

    `user_projects.user_id` 是 NOT NULL 的 FK → `users.user_id`：**PG 强制**、
    SQLite 单测默认**不强制** ⇒ 缺这一行时本地绿、生产炸 ⇒ 这里直接断言
    `users` 行存在，而不是依赖 SQLite 的 FK 行为。
    """
    project_id = await _create_project(client, db_session, admin_headers)

    user = await db_session.get(User, creator_user_id)
    assert user is not None, "创建者没有 users 行 ⇒ 授权行的 FK 在 PG 上会炸"
    assert user.username == "admin-user"
    # ⚠️ 建行时**不猜角色** ⇒ roles 是空数组（ADR-0046 §③b：mock 不污染 roles）
    assert user.roles == []

    # 授权行引用的必须是**真实存在**的那个 user_id
    rows = await _grants(db_session, project_id)
    assert rows[0].user_id == user.user_id


async def test_granting_the_creator_again_keeps_one_row(
    client, db_session, admin_headers, creator_user_id
):
    """幂等：重复授权不报错、也不产生第二行（`grant_project_access` 是 upsert）。"""
    project_id = await _create_project(client, db_session, admin_headers)

    await UserProjectService.grant_project_access(
        db_session,
        user_id=creator_user_id,
        project_id=project_id,
        role_in_project="DESIGNER",
    )
    await db_session.commit()

    rows = await _grants(db_session, project_id)
    assert len(rows) == 1, f"重复授权后应仍是 1 行，实际 {len(rows)} 行"
    # upsert ⇒ 角色被覆盖
    assert rows[0].role_in_project == "DESIGNER"


async def test_creating_a_project_does_not_grant_other_users(
    client, db_session, admin_headers
):
    """建项目只授权**创建者** ⇒ 别的用户不会顺带拿到访问权。"""
    project_id = await _create_project(client, db_session, admin_headers)

    others = await db_session.scalar(
        select(func.count())
        .select_from(UserProject)
        .where(UserProject.project_id == project_id)
        .where(UserProject.user_id != uuid.uuid5(uuid.NAMESPACE_DNS, "admin-user"))
    )
    assert others == 0


# ---------------------------------------------------------------------------
# seed 脚本的核心逻辑（CLI 的可测部分）
# ---------------------------------------------------------------------------


async def test_seed_grants_by_username_and_creates_the_user_row(
    client, db_session, admin_headers, creator_user_id
):
    """seed 脚本：按 username 授权 ⇒ **顺带**建 `users` 行（mock 用户没有行）。

    ⚠️ 这条是 dev 环境能用的**前提**：mock 登录刻意不落 `users` 表
    （ADR-0046 §③b）⇒ 若 seed 不建行，dev 永远无法授权 ⇒ 守卫一落地
    dev 前端全站 404。
    """
    from scripts.seed_user_project_access import seed_user_project_access

    project_id = await _create_project(client, db_session, admin_headers)

    grant, user_created = await seed_user_project_access(
        db_session,
        username="mock-designer",
        project_id=project_id,
        role_in_project="DESIGNER",
    )

    assert user_created is True, "users 表原本没有该用户 ⇒ 应为新建"
    assert grant.role_in_project == "DESIGNER"
    assert grant.revoked_at is None

    # 授权行引用的 user_id 必须在 `users` 表里真实存在（FK 前置）
    user = await db_session.get(User, grant.user_id)
    assert user is not None
    assert user.username == "mock-designer"
    assert user.roles == []


async def test_seed_is_idempotent(client, db_session, admin_headers):
    """seed 跑两遍 ⇒ 仍然只有 1 行授权，且第二次**不**再建 users 行。"""
    from scripts.seed_user_project_access import seed_user_project_access

    project_id = await _create_project(client, db_session, admin_headers)

    await seed_user_project_access(
        db_session, username="mock-designer", project_id=project_id
    )
    grant2, user_created2 = await seed_user_project_access(
        db_session, username="mock-designer", project_id=project_id
    )

    assert user_created2 is False, "第二次跑不该再新建 users 行"
    rows = (
        await db_session.execute(
            select(UserProject).where(
                UserProject.project_id == project_id,
                UserProject.user_id == grant2.user_id,
            )
        )
    ).scalars().all()
    assert len(rows) == 1
