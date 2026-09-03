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
    svc = ChecklistService(session)
    try:
        row = await svc.update_status(
            checklist_id=checklist_id, payload=payload, user_id=user_id
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    await session.commit()
    return ChecklistItemOut.model_validate(row)