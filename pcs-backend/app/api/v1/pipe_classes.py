"""管道等级端点（Task 1.9.2 / P2-STD-001）。

spec §3.2.5 API 表 5 端点 + 验收派生的 DELETE（在用 409 仅可作废）与项目分配 POST。

ACL：读（list/get/project list）= DESIGNER + PROCESS_CONTROLLER + SYSTEM_ADMIN；
写（create/update/delete/assign）= PROCESS_CONTROLLER + SYSTEM_ADMIN。
`current_actor / require_roles / _Actor` 与 config.py 同源（该模块 `__all__` 导出）。
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.pipe_class import (
    PipeClassCreate,
    PipeClassResponse,
    PipeClassUpdate,
    ProjectAssignRequest,
    ProjectPipeClassResponse,
)
from app.services.pipe_class_service import PipeClassService

router = APIRouter(tags=["pipe-classes"])


@router.get("/pipe-classes", response_model=list[PipeClassResponse])
async def list_pipe_classes(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None), keyword: str | None = Query(None),
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.list_company(db, status=status, keyword=keyword)


@router.post("/pipe-classes", response_model=PipeClassResponse, status_code=201)
async def create_pipe_class(
    payload: PipeClassCreate,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.create(db, payload=payload)


@router.get("/pipe-classes/{class_id}", response_model=PipeClassResponse)
async def get_pipe_class(
    class_id: str,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.get(db, class_id)


@router.put("/pipe-classes/{class_id}", response_model=PipeClassResponse)
async def update_pipe_class(
    class_id: str, payload: PipeClassUpdate,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    if payload.class_id != class_id:
        # service 层 update 的 model_dump 含 class_id，不一致会覆写主键
        raise HTTPException(
            status_code=422,
            detail=f"payload.class_id {payload.class_id} 与路径 {class_id} 不一致",
        )
    return await PipeClassService.update(db, class_id, payload=payload)


@router.delete("/pipe-classes/{class_id}", status_code=204)
async def delete_pipe_class(
    class_id: str,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await PipeClassService.delete(db, class_id)


@router.get(
    "/projects/{project_id}/pipe-classes", response_model=list[ProjectPipeClassResponse]
)
async def list_project_pipe_classes(
    project_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.list_project(db, project_id)


@router.post(
    "/projects/{project_id}/pipe-classes",
    response_model=ProjectPipeClassResponse, status_code=201,
)
async def assign_project_pipe_class(
    project_id: UUID, payload: ProjectAssignRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.assign_to_project(
        db, project_id, payload.class_id,
        enabled=payload.enabled, override=payload.custom_override_json,
    )
