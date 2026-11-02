"""系统参数端点（§7.20.1）。

⚠️ **批量 + 原子**：`PUT /system-settings` 一次提交全部改动，事务内全改或全不改。
⚠️ **权限**：系统参数是**全局**开关（会话超时 / 编辑锁 TTL……）⇒ 只给
`SYSTEM_ADMIN`。写死角色常量在这里而不是散在端点里 —— 漏一处 `require_roles`
就是一条越权路径。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.commit_or_rollback import commit_or_rollback
from app.db.session import get_db
from app.schemas.system_settings import (
    SystemSettingBatchIn,
    SystemSettingBatchOut,
    SystemSettingOut,
)
from app.services.system_setting_service import list_all, update_batch

router = APIRouter(prefix="/system-settings", tags=["system-settings"])

_ADMIN_ROLES = ("SYSTEM_ADMIN",)


@router.get("", response_model=list[SystemSettingOut])
async def get_system_settings(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> list[SystemSettingOut]:
    """GET /system-settings：全部系统参数（键 / 值 / 说明 / 更新时间）。"""
    require_roles(actor, *_ADMIN_ROLES)
    return [SystemSettingOut.model_validate(row) for row in await list_all(db)]


@router.put("", response_model=SystemSettingBatchOut)
async def put_system_settings(
    payload: SystemSettingBatchIn,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> SystemSettingBatchOut:
    """PUT /system-settings：**一次**提交全部改动（全改或全不改）。

    ⚠️ 键不存在 ⇒ 404 `SYSTEM_SETTING_NOT_FOUND` ⇒ **一个键都不改**
    （校验在写入之前 ⇒ 天然原子）。
    """
    require_roles(actor, *_ADMIN_ROLES)
    async with commit_or_rollback(db):
        rows = await update_batch(db, payload.settings.root, actor_user_id=actor.user_id)
    # ⚠️ `updated_at` 是 `onupdate=func.now()`（**服务端**表达式）⇒ flush 后 ORM
    # 上的值是旧的 ⇒ 提交后 refresh 读回（bug-2060 同形：漏了会 500）。
    for row in rows:
        await db.refresh(row)
    return SystemSettingBatchOut(
        updated=[SystemSettingOut.model_validate(row) for row in rows]
    )
