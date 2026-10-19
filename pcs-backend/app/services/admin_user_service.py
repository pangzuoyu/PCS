"""ADMIN 用户管理的**写入层**（SPEC P9A-ADM-002，ADR-0046 §⑤）。

放在 service 而不是 API 路由里，是 ADR-0047 §① 的 🔒 约束：
观测/审计写入必须在 service 层。AD 同步任务将来也会调 `disable_user()` ——
若写死在路由里，那条 cron 驱动的路径就会**系统性隐形且不报错**。
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.enums import AuditAction, UserStatus
from app.models.project import User


async def list_users(db: AsyncSession) -> list[dict[str, Any]]:
    """按 username 排序返回全部用户（`P9A-ADM-001`）。

    排序固定：ADMIN 列表没有分页时，顺序必须是确定的 ——
    否则每次刷新行序跳动，无法对比 disable 前后的状态。
    """
    rows = (
        await db.execute(select(User).order_by(User.username))
    ).scalars().all()
    return [
        {
            "user_id": u.user_id,
            "username": u.username,
            "display_name": u.display_name,
            "email": u.email,
            "department": u.department,
            "roles": list(u.roles or []),
            "status": u.status,
            "token_version": u.token_version,
            "last_login_at": u.last_login_at,
        }
        for u in rows
    ]


async def disable_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    actor_user_id: uuid.UUID,
    actor_username: str,
) -> dict[str, Any]:
    """停用一个用户：同事务 `status=DISABLED` + `token_version += 1` + 审计。

    三个动作必须**同一个事务**：分开提交会出现「已停用但 tv 没涨」的窗口，
    那个窗口里用户手里的 refresh 仍能换成新 access —— 停用看起来做了，实际没生效。

    Returns:
        停用后的用户摘要。

    Raises:
        PcsError: 404 —— 用户不存在。
    """
    user = await db.get(User, user_id)
    if user is None:
        raise PcsError(code="USER_NOT_FOUND", message=f"no such user: {user_id}", status=404)

    from app.services.audit_service import AuditService

    user.status = UserStatus.DISABLED.value
    user.token_version += 1
    await AuditService(db).write(
        action=AuditAction.USER_DISABLED,
        resource_type="USER",
        resource_id=user.user_id,
        user_id=actor_user_id,
        detail={
            "username": user.username,
            "actor_username": actor_username,
            "token_version": user.token_version,
        },
    )
    await db.commit()
    return {
        "user_id": user.user_id,
        "username": user.username,
        "status": user.status,
        "token_version": user.token_version,
    }
