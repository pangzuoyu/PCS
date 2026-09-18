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