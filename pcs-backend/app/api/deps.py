"""FastAPI 依赖（Sprint 2）。"""

from __future__ import annotations

import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.enums import WorkspaceType
from app.models.project import Workspace
from app.services.exceptions import (
    WorkspaceNotFoundError,
    WorkspaceTypeNotAllowedError,
)


async def get_workspace(
    workspace_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> Workspace:
    """FastAPI 依赖：按 workspace_id 取 Workspace 行。

    - 不存在 → WorkspaceNotFoundError（404）
    - 上游 header 改造后由 request header 自动注入（保留 query param 作 fallback）
    - require_formal_workspace 在此基础上叠加 FORMAL 校验
    """
    ws = (
        await session.execute(
            select(Workspace).where(Workspace.workspace_id == workspace_id)
        )
    ).scalar_one_or_none()
    if ws is None:
        raise WorkspaceNotFoundError(
            f"workspace_id={workspace_id} not found",
            details={"workspace_id": str(workspace_id)},
        )
    return ws


async def require_formal_workspace(
    ws: Workspace = Depends(get_workspace),
) -> Workspace:
    """仅 FORMAL workspace 允许业务记录写。PERSONAL/TEMPORARY 只读。"""
    return require_formal_workspace_type(ws)


def require_formal_workspace_type(ws: Workspace) -> Workspace:
    """**类型闸**（FORMAL 才允许写业务记录）⇒ ⇒ 非 FORMAL ⇒ ⇒ **403**。

    ⚠️ **为什么是独立函数**（2026-11-18 · ce-code-review · TODO-192 #1）：
    当它只以 **依赖**形式存在时 ⇒ ⇒ 它在**函数体之前**执行 ⇒ ⇒
    **403 会先于授权守卫的 404 出来** ⇒ ⇒ 无权者拿到**可区分的 403**
    ⇒ ⇒ ⇒ **工作区存在性可枚举**。

    ⇒ ⇒ ⇒ 写端点必须**先授权（404）后判类型（403）** ⇒ ⇒ ⇒
    ⇒ ⇒ 端点里显式两步：`get_workspace` → `require_workspace_access_or_404`
    ⇒ ⇒ ⇒ **再** `require_formal_workspace_type`。
    ⇒ ⇒ ⇒ 本函数是**唯一的类型闸实现** ⇒ ⇒ 依赖版与端点版**同一份口径**。
    """
    if ws.workspace_type != WorkspaceType.FORMAL.value:
        raise WorkspaceTypeNotAllowedError(
            f"workspace_type={ws.workspace_type} 不允许 mutating 业务记录",
            details={
                "workspace_id": str(ws.workspace_id),
                "workspace_type": ws.workspace_type,
                "required": WorkspaceType.FORMAL.value,
            },
        )
    return ws