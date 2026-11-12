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
from typing import Any

from sqlalchemy import delete, select
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


def _seed_user_ids() -> list[uuid.UUID]:
    return [derive_user_id(name) for name in SEED_USERNAMES]


async def _delete_own_rows(db: AsyncSession) -> None:
    """删掉**种子集合**的行（不碰业务数据）。

    ⚠️ **删除顺序必须遵守外键约束**：

        user_projects → streams → projects → workspaces → users

    ⚠️ **workspaces 必须在 projects 之后删** —— `projects.workspace_id`
    是指向 `workspaces` 的 FK ⇒ 项目还在时删工作区会撞 FK。
    """
    user_ids = _seed_user_ids()
    project_ids = [SEED_PROJECT_ID]
    workspace_ids = [SEED_WORKSPACE_ID]

    await db.execute(delete(UserProject).where(UserProject.project_id.in_(project_ids)))
    await db.execute(delete(Stream).where(Stream.project_id.in_(project_ids)))
    await db.execute(delete(Project).where(Project.project_id.in_(project_ids)))
    await db.execute(delete(Workspace).where(Workspace.workspace_id.in_(workspace_ids)))
    await db.execute(delete(User).where(User.user_id.in_(user_ids)))
    await db.commit()


async def _ensure_workspace(db: AsyncSession) -> Workspace:
    """建/取种子工作区。

    ⚠️ `Project.workspace_id` 是 NOT NULL ⇒ 没有工作区就**建不出项目**
    ⇒ 工作区是种子链的第一环。
    """
    existing = (
        await db.execute(
            select(Workspace).where(Workspace.workspace_id == SEED_WORKSPACE_ID)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    ws = Workspace(
        workspace_id=SEED_WORKSPACE_ID,
        workspace_type="FORMAL",
        name="E2E Workspace",
        status="ACTIVE",
    )
    db.add(ws)
    await db.flush()
    return ws


async def _ensure_project(db: AsyncSession, workspace: Workspace) -> Project:
    existing = (
        await db.execute(
            select(Project).where(Project.project_id == SEED_PROJECT_ID)
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    project = Project(
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
    )
    db.add(project)
    await db.flush()
    return project


async def _ensure_users(db: AsyncSession) -> list[User]:
    """建/取种子用户。

    ⚠️ `roles` 写**空数组** —— 与 `ensure_user_row` 同款：
    **真实登录会覆盖** `users.roles`（不是合并）⇒ 预置角色也白写。
    ⚠️ `roles` **不影响鉴权**（ACL 的权威是 JWT 的 role claim）⇒ 空数组安全。
    """
    users: list[User] = []
    for username in SEED_USERNAMES:
        user_id = derive_user_id(username)
        existing = (
            await db.execute(select(User).where(User.user_id == user_id))
        ).scalar_one_or_none()
        if existing is None:
            existing = User(
                user_id=user_id,
                username=username,
                display_name=username,
                roles=[],
                ad_groups=[],
                status="ACTIVE",
            )
            db.add(existing)
            await db.flush()
        users.append(existing)
    return users


async def _ensure_grants(
    db: AsyncSession, users: list[User], project: Project
) -> None:
    """建/取 `UserProject` 授权行（项目守卫的判据）。"""
    for user in users:
        existing = (
            await db.execute(
                select(UserProject).where(
                    UserProject.user_id == user.user_id,
                    UserProject.project_id == project.project_id,
                )
            )
        ).scalar_one_or_none()
        if existing is None:
            db.add(
                UserProject(
                    user_id=user.user_id,
                    project_id=project.project_id,
                    role_in_project=SEED_PROJECT_ROLE,
                )
            )
            await db.flush()


async def _ensure_streams(
    db: AsyncSession, project: Project, workspace: Workspace
) -> int:
    """建/取种子物流（管段）。返回物流条数。"""
    for index, name in enumerate(SEED_STREAM_NAMES):
        sid = _stream_id(name)
        existing = (
            await db.execute(select(Stream).where(Stream.stream_id == sid))
        ).scalar_one_or_none()
        if existing is not None:
            continue
        db.add(
            Stream(
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
            )
        )
        await db.flush()
    return len(SEED_STREAM_NAMES)


async def seed(db: AsyncSession, *, reset: bool = False) -> dict[str, int]:
    """幂等灌种子数据。

    Args:
        db: 调用方给 session（⚠️ 本函数**不 commit** —— 事务归调用方管）。
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
