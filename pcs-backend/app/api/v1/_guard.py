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
