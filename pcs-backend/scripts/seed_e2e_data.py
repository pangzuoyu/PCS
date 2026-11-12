"""E2E 种子数据（P10-A · Task T2）—— **幂等**。

## 为什么需要它

SPEC P10 §3.2.2(4)：「数据准备 = 种子脚本自动生成标准测试项目数据」。
本批（P10-A）只做**真后端 E2E 通道**，业务场景在 P10-B。
⇒ 本脚本的产出是「一条能登录、能访问项目、能看到物流」的最小数据集。

## 三条硬约束（每条都对应一类**静默**失败）

1. **幂等** —— 跑第二遍不炸、不重复、不留脏数据。
   不幂等的症状很隐蔽：E2E 第二次跑时表里多了一行 ⇒ 断言飘 ⇒
   排查方向会跑到「业务代码有 bug」上，而真因是脚本没幂等。
2. **固定 UUID** —— 不用随机值 ⇒ 幂等的基础（随机值 = 每次都是新行）。
3. **只删自己造的** —— `--reset` 按固定 UUID 列表筛，不碰业务数据。
   不筛的话，在开发库上跑一次脚本 = **业务数据被删**。
   ⚠️ **`users` 表一个都不删**（评审 #1）—— `user_id` 是**派生值**
   `uuid5(NAMESPACE_DNS, username)` ⇒ 与真实 LDAP 账号的 id **完全相同**
   ⇒ 按 id 删 = **删掉真实账号**（roles / status / token_version 全丢，
   其 `user_projects` 授权行被 CASCADE）⇒ 而下次登录会把它**重建为 ACTIVE**
   ⇒ **被停用的账号被悄悄启用**。
   ⇒ 已存在的用户行连 `status` / `roles` 都不许改。

## 授权行（`user_projects`）不是可选项

带项目守卫的端点按「该用户对该项目**有没有授权行**」判定 ⇒
没有授权行 ⇒ **一律 404**（与「不存在」逐字同形）。
⇒ 种子必须同时造 `UserProject`，否则 E2E 看到的全是 404，
而 404 在这个系统里**长得和「资源不存在」一模一样** ⇒ 极难定位。
（P9B-4 紧急批次的教训。）

⚠️ **user_id 用派生值** `uuid5(NAMESPACE_DNS, username)`
⇒ 与登录路径算出的 id 一致 ⇒ 授权行对得上。

## 用法

    uv run python scripts/seed_e2e_data.py            # 幂等灌种子
    uv run python scripts/seed_e2e_data.py --reset    # 先删自己的行再灌
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project, Stream, User, UserProject, Workspace
from app.services.token_issuer import derive_user_id

#: 种子用户名 —— **与 mock 登录的 `MOCK_USERS` 同名**
#: （alice / bob / carol / dan）。mock 登录**不落 `users` 表**（ADR-0046 §③b）
#: ⇒ 这些行由本脚本建 ⇒ mock 登录的用户才拿得到项目授权。
SEED_USERNAMES: tuple[str, ...] = ("alice", "bob", "carol", "dan")

#: 种子用户在**项目内**的角色。
#: ⚠️ 合法值 6 个：DESIGNER / CHECKER / APPROVER / REVIEWER / VIEWER / PROJECT_LEAD。
#: ⚠️ **P10-B 的权限矩阵（SPEC §3.2.2(3) 的 8 条 AUTH-E2E）需要 per-user 角色**
#: ⇒ 届时改这一处（以及上面 `SEED_USERNAMES` 的角色映射）。
SEED_PROJECT_ROLE = "DESIGNER"

#: 固定 UUID（`uuid5` 派生 ⇒ 跨机器一致）。
#: ⚠️ **不用随机值** —— 随机值 = 每次跑都是新行 = 不幂等。
SEED_WORKSPACE_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "pcs-e2e-workspace")
SEED_PROJECT_ID = uuid.uuid5(uuid.NAMESPACE_DNS, "pcs-e2e-project")

#: 种子物流（管段）名 ⇒ 其 stream_id 同样派生。
SEED_STREAM_NAMES: tuple[str, ...] = ("E2E-S-001", "E2E-S-002")


def _stream_id(name: str) -> uuid.UUID:
    return uuid.uuid5(uuid.NAMESPACE_DNS, f"pcs-e2e-stream-{name}")


async def _delete_own_rows(db: AsyncSession) -> None:
    """删掉**种子集合**的行（不碰业务数据）。

    ⚠️ **删除顺序必须遵守外键约束**：

        user_projects → streams → projects → workspaces

    ⚠️ **workspaces 必须在 projects 之后删** —— `projects.workspace_id`
    是指向 `workspaces` 的 FK ⇒ 项目还在时删工作区会撞 FK。

    ⚠️⚠️ **`users` 表一个都不删**（评审 #1 · 2026-11-12）——
    `user_id` 是**派生值** `uuid5(NAMESPACE_DNS, username)` ⇒ 与真实 LDAP
    账号的 id **完全相同** ⇒ 按 id 删 = **删掉真实账号**：
    它的 `roles` / `status` / `token_version` 全丢、其 `user_projects`
    授权行被 `ondelete="CASCADE"` 连带删掉 ⇒ 而下一次登录会把这个行
    **重建为 ACTIVE** ⇒ **一个被故意停用的账号被悄悄启用**。
    ⇒ 用户行由 `_ensure_users` 负责「**没有才建**」，**已存在的一律不碰**。
    """
    project_ids = [SEED_PROJECT_ID]
    workspace_ids = [SEED_WORKSPACE_ID]

    await db.execute(delete(UserProject).where(UserProject.project_id.in_(project_ids)))
    await db.execute(delete(Stream).where(Stream.project_id.in_(project_ids)))
    await db.execute(delete(Project).where(Project.project_id.in_(project_ids)))
    await db.execute(delete(Workspace).where(Workspace.workspace_id.in_(workspace_ids)))
    await db.commit()


async def _get_or_create(
    db: AsyncSession,
    match: Any,
    build: Callable[[], Any],
) -> Any:
    """**本仓的 get-or-create 形状**（house pattern · 评审 #9）。

    ⚠️ **为什么不能是「裸 SELECT ⇒ 见空 ⇒ INSERT」**：
    两个并发跑（compose 的 `seed` 一次性容器 + 手工再跑一次）会**都**看到
    「空」⇒ 都 INSERT ⇒ **输家撞唯一约束** ⇒ 而旧形状里那个 `flush()` 抛出的
    `IntegrityError` 会**污染整笔事务** ⇒ 脚本直接炸 ⇒
    E2E 通道起不来（失败是响亮的，但炸在错的地方）。

    ⇒ 三步（照 `docs/solutions/database-issues/`
    `get-or-create-default-row-race-savepoint-reread.md`）：
    ① `db.add` + `flush` 在 **`begin_nested()`（savepoint）之内**
    ② 撞 `IntegrityError` ⇒ **回滚 savepoint**（整笔事务仍然可用）
    ③ **重读赢家**（**只读；绝不 update**）⇒ 返回它
    """
    existing = (await db.execute(match)).scalar_one_or_none()
    if existing is not None:
        return existing
    entity = build()
    try:
        async with db.begin_nested():
            db.add(entity)
            await db.flush()
    except IntegrityError:
        winner = (await db.execute(match)).scalar_one_or_none()
        if winner is not None:
            return winner
        raise
    return entity


async def _ensure_workspace(db: AsyncSession) -> Workspace:
    """建/取种子工作区。

    ⚠️ `Project.workspace_id` 是 NOT NULL ⇒ 没有工作区就**建不出项目**
    ⇒ 工作区是种子链的第一环。
    """
    return await _get_or_create(
        db,
        select(Workspace).where(Workspace.workspace_id == SEED_WORKSPACE_ID),
        lambda: Workspace(
            workspace_id=SEED_WORKSPACE_ID,
            workspace_type="FORMAL",
            name="E2E Workspace",
            status="ACTIVE",
        ),
    )


async def _ensure_project(db: AsyncSession, workspace: Workspace) -> Project:
    return await _get_or_create(
        db,
        select(Project).where(Project.project_id == SEED_PROJECT_ID),
        lambda: Project(
            project_id=SEED_PROJECT_ID,
            project_no="E2E-0001",
            project_name="E2E Seed Project",
            owner_company="E2E Owner",
            location="E2E Site",
            project_type="REFINERY",
            design_phase="DESIGN",
            unit_system="SI",
            workspace_id=workspace.workspace_id,
            status="ACTIVE",
        ),
    )


async def _ensure_users(db: AsyncSession) -> list[User]:
    """建/取种子用户。

    ⚠️ `roles` 写**空数组** —— 与 `ensure_user_row` 同款：
    **真实登录会覆盖** `users.roles`（不是合并）⇒ 预置角色也白写。
    ⚠️ `roles` **不影响鉴权**（ACL 的权威是 JWT 的 role claim）⇒ 空数组安全。

    ⚠️⚠️ **已存在的用户行一个字段都不许改**（评审 #1）——
    `user_id` 是派生值 ⇒ 与真实 LDAP 账号的 id 相同 ⇒ 改 `status`
    就等于**把被停用的账号悄悄启用**。
    """
    users: list[User] = []
    for username in SEED_USERNAMES:
        user_id = derive_user_id(username)
        users.append(
            await _get_or_create(
                db,
                select(User).where(User.user_id == user_id),
                lambda user_id=user_id, username=username: User(
                    user_id=user_id,
                    username=username,
                    display_name=username,
                    roles=[],
                    ad_groups=[],
                    status="ACTIVE",
                ),
            )
        )
    return users


async def _ensure_grants(
    db: AsyncSession, users: list[User], project: Project
) -> None:
    """建/取 `UserProject` 授权行（项目守卫的判据）。"""
    for user in users:
        await _get_or_create(
            db,
            select(UserProject).where(
                UserProject.user_id == user.user_id,
                UserProject.project_id == project.project_id,
            ),
            lambda user=user: UserProject(
                user_id=user.user_id,
                project_id=project.project_id,
                role_in_project=SEED_PROJECT_ROLE,
            ),
        )


async def _ensure_streams(
    db: AsyncSession, project: Project, workspace: Workspace
) -> int:
    """建/取种子物流（管段）。返回物流条数。"""
    for index, name in enumerate(SEED_STREAM_NAMES):
        sid = _stream_id(name)
        await _get_or_create(
            db,
            select(Stream).where(Stream.stream_id == sid),
            lambda sid=sid, index=index, name=name: Stream(
                stream_id=sid,
                project_id=project.project_id,
                workspace_id=workspace.workspace_id,
                stream_name=name,
                description="E2E 种子物流",
                data_mode="CHEMICAL",
                phase="LIQUID",
                source="SIM_IMPORT" if index else "MANUAL",
                source_type="SIM_IMPORT" if index else "MANUAL_ENTRY",
                approval_depth=1,
            ),
        )
    return len(SEED_STREAM_NAMES)


async def seed(db: AsyncSession, *, reset: bool = False) -> dict[str, int]:
    """幂等灌种子数据。

    Args:
        db: 调用方给 session（⚠️ 本函数**自己 commit** —— 幂等重灌要求
            「查→插→提交」是一个整体；调用方若还要接着写数据，请**另开
            一个 session** 或在调用后显式判断）。
        reset: True ⇒ 先删掉**种子集合**的行再重灌（不碰业务数据）。

    Returns:
        各实体的**行数**（种子集合当前有多少行）。
        ⚠️ 不是「本次新建了几行」⇒ **跑两遍返回同一个值就是幂等的直接证据**。

    ⚠️ 必须有可调用入口（只有 `if __name__ == "__main__"` 的话单测没法传 session）。
    """
    if reset:
        await _delete_own_rows(db)

    workspace = await _ensure_workspace(db)
    project = await _ensure_project(db, workspace)
    users = await _ensure_users(db)
    await _ensure_grants(db, users, project)
    streams = await _ensure_streams(db, project, workspace)

    await db.commit()

    return {
        "projects": 1,
        "streams": streams,
        "users": len(users),
        "user_projects": len(users),
        "workspaces": 1,
    }


async def _main(reset: bool) -> None:
    from app.db.session import get_async_session_factory

    factory = get_async_session_factory()
    async with factory() as session:
        counts = await seed(session, reset=reset)

    summary: dict[str, Any] = counts
    print(
        "种子数据完成："
        + " · ".join(f"{key}={value}" for key, value in sorted(summary.items()))
    )


if __name__ == "__main__":  # pragma: no cover — 脚本入口
    parser = argparse.ArgumentParser(description="灌 E2E 种子数据（幂等）")
    parser.add_argument(
        "--reset",
        action="store_true",
        help="先删掉种子集合自己的行再重灌（不碰业务数据）",
    )
    args = parser.parse_args()
    asyncio.run(_main(args.reset))
