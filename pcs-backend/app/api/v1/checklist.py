"""Checklist API（Sprint 1）。"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.schemas.checklist import (
    ChecklistBulkSeed,
    ChecklistCompleteness,
    ChecklistItemOut,
    ChecklistItemPut,
)
from app.services.checklist_service import ChecklistService

router = APIRouter(prefix="/checklist", tags=["checklist"])


@router.get("/projects/{project_id}", response_model=list[ChecklistItemOut])
async def list_for_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ChecklistItemOut]:
    svc = ChecklistService(session)
    rows = await svc.list_for_project(project_id)
    return [ChecklistItemOut.model_validate(r) for r in rows]


@router.post(
    "/projects/{project_id}/seed",
    response_model=list[ChecklistItemOut],
    status_code=201,
)
async def bulk_seed(
    project_id: uuid.UUID,
    payload: ChecklistBulkSeed,
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> list[ChecklistItemOut]:
    """POST 批量种子（项目内 checklist 一次生成）。

    步骤：
    1. 调 ChecklistService.bulk_seed：按 items 列表逐条创建 ChecklistItem
       （status 默认 NOT_STARTED；user_id 记录创建者）
    2. session.commit() 落库（service 已 flush）
    3. ORM 行经 ChecklistItemOut.model_validate 转响应 schema 列表

    与 update_item 区别：本端点批量初始化（一个项目通常一次提交）；
    update_item 单项状态流转（5 态 + Audit）。
    """
    svc = ChecklistService(session)
    rows = await svc.bulk_seed(
        project_id=project_id, items=payload.items, user_id=user_id
    )
    await session.commit()
    return [ChecklistItemOut.model_validate(r) for r in rows]


@router.get(
    "/projects/{project_id}/completeness",
    response_model=ChecklistCompleteness,
)
async def completeness(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ChecklistCompleteness:
    svc = ChecklistService(session)
    return await svc.completeness(project_id)


@router.put("/items/{checklist_id}", response_model=ChecklistItemOut)
async def update_item(
    checklist_id: uuid.UUID,
    payload: ChecklistItemPut,
    user_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> ChecklistItemOut:
    """PUT 校验一项状态（5 态流转 + Audit 落库）。

    步骤：
    1. 调 ChecklistService.update_status（状态校验 + Audit + flush）
    2. service 抛 ValueError → 404（找不到 checklist 项；保留原 ValueError 契约）
    3. session.commit() 落库
    4. ORM 行经 ChecklistItemOut.model_validate 转响应 schema

    ACL：DESIGNER / CHECKER / REVIEWER / APPROVER / SYSADMIN
    （由 ACL middleware 在 user_id 注入前验证）。
    """
    svc = ChecklistService(session)
    try:
        row = await svc.update_status(
            checklist_id=checklist_id, payload=payload, user_id=user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    await session.commit()
    return ChecklistItemOut.model_validate(row)