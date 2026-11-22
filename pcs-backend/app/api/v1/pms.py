"""PMS 管道材料规格 API（P10-H · T2 · TODO-195）。

端点（挂 `/projects` 前缀 ⇒ ⇒ 路径与前端 `/pms` 页一致）：

- `GET    /api/v1/projects/{project_id}/pms` —— 列（分页）
- `POST   /api/v1/projects/{project_id}/pms` —— 建（DRAFT）
- `GET    /api/v1/projects/{project_id}/pms/{item_id}` —— 详情
- `PATCH  /api/v1/projects/{project_id}/pms/{item_id}` —— 改（仅 DRAFT）

⚠️ **签署不在这里**：送审 / 审批 / 作废走**通用记录工作流**
（`/records/PmsItem/{item_id}/submit-approval` 等）⇒ ⇒ 本模块不碰
`sign_status` ⇒ ⇒ 不会与工作流抢状态。

ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
守卫：`check_project_access_or_404`（无权 ⇒ ⇒ **404**，不泄漏存在性）。
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.project import Project
from app.schemas.pms import (
    PmsItemCreate,
    PmsItemListResponse,
    PmsItemResponse,
    PmsItemUpdate,
)
from app.services.exceptions import PcsError
from app.services.pms_service import (
    create_pms_item,
    get_pms_item,
    list_pms_items,
    update_pms_item,
)

router = APIRouter(prefix="/projects", tags=["pms"])

_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")


async def _get_project(
    db: AsyncSession, project_id: uuid.UUID, actor: _Actor
) -> Project:
    """取项目行（**先守卫再取** ⇒ ⇒ 无权时不存在「取到了才知道」的窗口）。"""
    await check_project_access_or_404(
        db,
        user_id=actor.user_id,
        project_id=project_id,
        actor_roles=list(actor.roles),
    )
    project = await db.get(Project, project_id)
    if project is None:
        raise PcsError(
            code="PROJECT_NOT_FOUND",
            status=404,
            message=f"Project not found: {project_id}",
        )
    return project


@router.get("/{project_id}/pms", response_model=PmsItemListResponse)
async def list_pms(
    project_id: uuid.UUID,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    actor: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> PmsItemListResponse:
    """列项目的 PMS 条目（默认只返 DRAFT / CHECKED ⇒ 排除作废等门禁态）。"""
    require_roles(actor, *_ROLES)
    await _get_project(db, project_id, actor)
    rows = await list_pms_items(db, project_id=project_id, limit=limit, offset=offset)
    items = [PmsItemResponse.model_validate(r, from_attributes=True) for r in rows]
    return PmsItemListResponse(
        items=items, total=len(items), limit=limit, offset=offset
    )


@router.post(
    "/{project_id}/pms",
    response_model=PmsItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_pms(
    project_id: uuid.UUID,
    payload: PmsItemCreate,
    actor: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> PmsItemResponse:
    """新建一条 PMS 条目（**DRAFT** ⇒ ⇒ 送审走通用工作流）。"""
    require_roles(actor, *_ROLES)
    project = await _get_project(db, project_id, actor)
    item = await create_pms_item(
        db, project=project, payload=payload, created_by=actor.user_id
    )
    await db.commit()
    await db.refresh(item)
    return PmsItemResponse.model_validate(item, from_attributes=True)


@router.get("/{project_id}/pms/{item_id}", response_model=PmsItemResponse)
async def get_pms(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    actor: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> PmsItemResponse:
    """取一条 PMS 条目（**别的项目的条目 ⇒ 404** ⇒ 不泄漏存在性）。"""
    require_roles(actor, *_ROLES)
    await _get_project(db, project_id, actor)
    item = await get_pms_item(db, item_id=item_id)
    if item is None or item.project_id != project_id:
        raise PcsError(
            code="PMS_ITEM_NOT_FOUND",
            status=404,
            message=f"PMS item not found: {item_id}",
        )
    return PmsItemResponse.model_validate(item, from_attributes=True)


@router.patch("/{project_id}/pms/{item_id}", response_model=PmsItemResponse)
async def update_pms(
    project_id: uuid.UUID,
    item_id: uuid.UUID,
    payload: PmsItemUpdate,
    actor: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> PmsItemResponse:
    """改一条 PMS 条目（**仅 DRAFT** ⇒ 锁定态 409）。"""
    require_roles(actor, *_ROLES)
    await _get_project(db, project_id, actor)
    item = await get_pms_item(db, item_id=item_id)
    if item is None or item.project_id != project_id:
        raise PcsError(
            code="PMS_ITEM_NOT_FOUND",
            status=404,
            message=f"PMS item not found: {item_id}",
        )
    item = await update_pms_item(db, item=item, payload=payload)
    await db.commit()
    await db.refresh(item)
    return PmsItemResponse.model_validate(item, from_attributes=True)
