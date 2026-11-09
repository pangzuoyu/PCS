"""给「指定用户名 × 指定项目」授权（幂等）—— P9B-4 紧急批次 T0。

## 为什么需要这个脚本

补上**物流面项目守卫**之后，**任何没有 `UserProject` 授权行的用户访问任何
物流端点都 404**。而仓里能持续产生授权行的路径**只有**
`POST /user-projects/grant`（**SYSTEM_ADMIN only**、**前端没有**管理页面）
⇒ 每个环境上线前都得有一次「给实际使用者授权」的操作 ⇒ 本脚本就是那条路径。

## 为什么**用户不在 `users` 表时也要建行**（而不是报错退出）

mock 登录**刻意不落 `users` 表**（ADR-0046 §③b）⇒ dev 环境的 mock 用户
（alice / bob / carol / dan）**永远拿不到授权行** ⇒ 守卫一落地，dev 前端
**全站 404** ⇒ 本批末的浏览器回归**不可能通过**。

⇒ 所以本脚本在授权前**先确保 `users` 行存在**（缺失则建，`roles=[]`）。
建行时 `roles` 写**空数组**（不是从 token 猜角色）⇒ 既满足
`user_projects.user_id` 的 FK，又**不污染**真实 AD 用户的 `roles`
（ADR-0046 §③b 关心的正是 roles 污染）。

## 幂等

`grant_project_access` 是 upsert（同 `(user_id, project_id)` 已存在则覆盖角色）
⇒ 重复跑本脚本**无害**。

用法：

    cd pcs-backend
    uv run python scripts/seed_user_project_access.py --username alice --project <uuid>
    uv run python scripts/seed_user_project_access.py --username alice --project <uuid> --dry-run

⚠️ 数据库口令从 `.env` 的 `DATABASE_URL` 读 —— **不要**出现在命令行。
"""
# ruff: noqa — 一次性运维脚本（非 app 代码），单点收敛
from __future__ import annotations

import argparse
import asyncio
import sys
import uuid
from pathlib import Path

# 允许 ``uv run python scripts/xxx.py`` 直接调用；app 包从 pcs-backend 根解析。
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from sqlalchemy import select  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.db.session import get_async_session_factory  # noqa: E402
from app.models.project import Project, User, UserProject  # noqa: E402
from app.services.token_issuer import derive_user_id  # noqa: E402
from app.services.user_project_service import (  # noqa: E402
    VALID_PROJECT_ROLES,
    UserProjectService,
    ensure_user_row,
)

DEFAULT_ROLE = "DESIGNER"


async def seed_user_project_access(
    session: AsyncSession,
    *,
    username: str,
    project_id: uuid.UUID,
    role_in_project: str = DEFAULT_ROLE,
) -> tuple[UserProject, bool]:
    """给 `username` 授权到 `project_id`（幂等）。

    Returns:
        `(授权行, 是否新建了 users 行)` —— 「是否新建」只用于**回显**，
        让运维知道这次跑出来的是「新建」还是「命中已有」。
    """
    existing = (
        await session.execute(select(User).where(User.username == username))
    ).scalar_one_or_none()
    user_created = existing is None

    creator = await ensure_user_row(
        session,
        user_id=derive_user_id(username),
        username=username,
    )
    grant = await UserProjectService.grant_project_access(
        session,
        user_id=creator.user_id,
        project_id=project_id,
        role_in_project=role_in_project,
        granted_by=creator.user_id,
    )
    return grant, user_created


async def _run(args: argparse.Namespace) -> int:
    """执行一次 seed。返回进程退出码。"""
    if args.role not in VALID_PROJECT_ROLES:
        print(
            f"[ERROR] --role {args.role!r} 不在合法角色词表内："
            f"{sorted(VALID_PROJECT_ROLES)}",
            file=sys.stderr,
        )
        return 2

    try:
        project_id = uuid.UUID(args.project)
    except ValueError:
        print(f"[ERROR] --project {args.project!r} 不是合法的 UUID", file=sys.stderr)
        return 2

    factory = get_async_session_factory()
    async with factory() as session:
        project = await session.get(Project, project_id)
        if project is None:
            print(
                f"[ERROR] 项目 {project_id} 不存在 ⇒ 无法授权"
                "（先建项目，或核对 UUID）",
                file=sys.stderr,
            )
            return 2

        user = (
            await session.execute(select(User).where(User.username == args.username))
        ).scalar_one_or_none()

        if args.dry_run:
            print(
                f"[DRY-RUN] {args.username} → {project_id} : {args.role}"
                f"（users 行：{'已有' if user is not None else '将新建'}）"
            )
            return 0

        grant, user_created = await seed_user_project_access(
            session,
            username=args.username,
            project_id=project_id,
            role_in_project=args.role,
        )
        print(f"{args.username} → {project_id} : {grant.role_in_project}")
        if user_created:
            print(
                f"[NOTE] 用户 {args.username!r} 原本不在 users 表 ⇒ 已建行"
                "（roles=[]；不猜角色 ⇒ 授权行才是权限来源）"
            )
        return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="给指定用户名 × 指定项目授权（幂等）。",
    )
    parser.add_argument("--username", required=True, help="users.username（不存在则建行）")
    parser.add_argument("--project", required=True, help="项目 UUID")
    parser.add_argument(
        "--role",
        default=DEFAULT_ROLE,
        help=f"项目内角色（默认 {DEFAULT_ROLE}；合法值 {sorted(VALID_PROJECT_ROLES)}）",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只回显将要做什么，不写库",
    )
    args = parser.parse_args(argv)

    try:
        return asyncio.run(_run(args))
    except Exception as exc:  # noqa: BLE001 — 运维脚本：把原因说清楚再退出
        print(f"[ERROR] 授权失败：{exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
