"""API endpoint 守卫 helper（BLOCKER-3 修复共享函数）。

供 21+ endpoint 调用，避免代码重复：
- check_project_access_or_404(db, user, project_id): 检查 user 对 project_id 访问权
  无权时抛 HTTPException(404)（不泄漏存在性）。
- check_record_access_or_404(db, user, record): 检查 user 对 record.project_id 访问权
  record 无 project_id 字段的先抛 500 (开发期 catch)。

BLOCKER-3 fix: 调用方只需在 endpoint 里加一行 await check_project_access_or_404(...) 即可。
"""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_project_service import UserProjectService


async def check_project_access_or_404(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    actor_roles: list[str] | None = None,
) -> None:
    """检查 user 对 project_id 的访问权；无权抛 404。

    用 404 而非 403：不向攻击者泄漏项目存在性。

    SYSTEM_ADMIN 全局 bypass: actor 含 SYSTEM_ADMIN 角色时跳过 UserProject 校验
    （运维/测试用 — production 应通过 admin API 显式 grant，不应依赖 bypass）

    role-string 收敛 (2026-10-04): 历史双写 "SYSADMIN" 已全量收敛为
    "SYSTEM_ADMIN" (state_machine/cia_engine/mock_auth/LDAP 同步)。
    """
    if actor_roles and "SYSTEM_ADMIN" in actor_roles:
        return  # SYSTEM_ADMIN 全局访问权
    has_access = await UserProjectService.check_user_project_access(
        db, user_id=user_id, project_id=project_id,
    )
    if not has_access:
        raise HTTPException(
            status_code=404,
            detail=f"Project not found: {project_id}",
        )


async def check_record_access_or_404(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    record: Any,
    actor_roles: list[str] | None = None,
) -> None:
    """检查 user 对 record.project_id 的访问权；无权抛 404。

    record 必须有 project_id 属性（ORM 模型）。无此字段抛 500（开发期漏调用）。
    """
    project_id = getattr(record, "project_id", None)
    if project_id is None:
        raise HTTPException(
            status_code=500,
            detail="Record missing project_id (guard misconfigured)",
        )
    await check_project_access_or_404(
        db, user_id=user_id, project_id=project_id, actor_roles=actor_roles,
    )

async def require_formal_project_workspace(
    db: AsyncSession, *, project_id: uuid.UUID
) -> None:
    """工作区门禁：**只有 FORMAL 工作区**能做本操作（UI-SPEC §5.3）。

    UI-SPEC §5.3：「创建变更单」在 PERSONAL / TEMPORARY 工作区 ⇒ 403。
    个人草稿区里的变更单没有工程效力（明天就过期了），却会占用签署流程。

    ## 为什么**不叫** `require_formal_workspace`（评审 I-7）

    `app/api/deps.py` 里已有一个**同名**函数（FastAPI 依赖形式，参数是
    `Workspace`）⇒ 两个语义相近的函数同名 = 后面的人 import 错了
    ⇒ 一个是「拿不到工作区就 404」，一个是「拿不到工作区就放行」。
    ⇒ 本函数改名 `require_formal_project_workspace`（**按项目**查）。

    ## ⚠️ 本守卫是 **fail-open** 的（与 deps.py 那版相反）

    | 情况 | 本守卫 | `deps.require_formal_workspace` |
    |---|---|---|
    | 项目不存在 / 没挂工作区 | **放行** | 404（工作区取不到） |
    | 工作区行不存在 | **放行** | 404 |
    | 工作区不是 FORMAL | 403 | 403 |

    「放行」是**有意的**：项目是历史数据、没挂工作区 ⇒ 不是个人草稿区
    ⇒ 不该因缺元数据把正常操作挡掉。⇒ 但这是**两处 fail-open 分支**，
    已登记 TODO-076（门禁覆盖面 + 两条放行分支的显式化）。

    ⚠️ **本守卫只覆盖本批端点** —— 全端点的工作区门禁仍缺（已登记 TODOS.md）。
    """
    from app.core.errors import PcsError
    from app.models.enums import WorkspaceType
    from app.models.project import Project, Workspace

    project = await db.get(Project, project_id)
    if project is None or project.workspace_id is None:
        # 没有工作区 ⇒ 不是个人草稿区 ⇒ 放行（不因缺元数据把正常操作挡掉）
        return
    workspace = await db.get(Workspace, project.workspace_id)
    if workspace is None:
        return
    if workspace.workspace_type != WorkspaceType.FORMAL.value:
        raise PcsError(
            code="WORKSPACE_TYPE_NOT_ALLOWED",
            message=(
                f"当前工作区类型 {workspace.workspace_type}，只允许在 FORMAL "
                f"工作区创建变更单（UI-SPEC §5.3）"
            ),
            status=403,
        )


async def require_active_project_member(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    project_id: uuid.UUID,
    actor_roles: list[str] | None = None,
) -> None:
    """项目内角色必须是**活跃参与者**（不是 VIEWER）⇒ 否则 403。

    ## 为什么要有这一层（评审 I-5）

    `check_project_access_or_404` 只问「有没有访问权」⇒ **任何**有效授权
    （含 VIEWER）都算 ⇒ 一个「只读成员」也能做「决定这个项目谁该签」的事
    （改签署矩阵）—— 权力比它的角色大。

    ## 为什么用「不是 VIEWER」而不是「≥ DESIGNER」

    `user_projects.role_in_project` 的词表是 **DESIGNER / CHECKER / REVIEWER /
    APPROVER / VIEWER** —— **平行职责，不是等级** ⇒ 「≥ DESIGNER」无定义。
    ⇒ 用「**不是 VIEWER**」表达「是活跃参与者」—— 唯一的等级含义（只读 vs 参与）
    恰好是真实存在的那个。

    ⚠️ SYSTEM_ADMIN 全局 bypass（与 `check_project_access_or_404` 一致）。
    """
    from app.core.errors import PcsError
    from app.models.project import UserProject

    if actor_roles and "SYSTEM_ADMIN" in actor_roles:
        return
    row = (
        await db.execute(
            select(UserProject).where(
                UserProject.user_id == user_id,
                UserProject.project_id == project_id,
                UserProject.revoked_at.is_(None),
            )
        )
    ).scalar_one_or_none()
    if row is None:
        # 无授权 ⇒ 交给 `check_project_access_or_404` 报 404（不泄漏存在性）
        return
    if row.role_in_project == "VIEWER":
        raise PcsError(
            code="PROJECT_ROLE_FORBIDDEN",
            message=(
                f"你在项目 {project_id} 内的角色是 VIEWER（只读），"
                f"不能做这件事"
            ),
            status=403,
        )
