"""S1-4b EQUIP_LIST API endpoints。

Per R8 ruling 补 API 层；与 sync_service (S1-4) 协同：

端点（4 endpoints）：
- GET    /api/v1/equipment-list             → EquipListListResponse（按过滤条件分页查询）
- GET    /api/v1/equipment-list/{id}        → EquipListResponse（单条记录）
- POST   /api/v1/equipment-list/{id}/sync   → EquipListSyncResponse（手动 trigger sync_from_source）
- POST   /api/v1/equipment-list/bulk-sync   → EquipListBulkSyncResponse（批量 sync）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与 sync_from_source 写路径一致）
- POST /sync + /bulk-sync：调 sync_from_source / bulk_sync_from_sources
- GET list：调 list_equipment_records；带 limit/offset + 6 维 filter
- 不写 EquipmentList CRUD（POST 创建/PUT 更新/DELETE）—— 留 S1-4c follow-up
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.enums import to_value
from app.schemas.equip_list import (
    EquipListBulkSyncRequest,
    EquipListBulkSyncResponse,
    EquipListListResponse,
    EquipListResponse,
    EquipListSyncRequest,
    EquipListSyncResponse,
)
from app.services.equip_list import persist_service, sync_service

router = APIRouter(prefix="/equipment-list", tags=["equipment-list"])


def _to_response(record) -> EquipListResponse:
    """ORM → Pydantic response mapper。

    sign_status 接受 enum 或 str（per bug-116 lesson：跨 DB dual-format）。
    """
    ss_value = to_value(record.sign_status)
    return EquipListResponse(
        equipment_id=record.equipment_id,
        equipment_type_project_id=record.equipment_type_project_id,
        type_code=record.type_code,
        equipment_name=record.equipment_name,
        equipment_description=record.equipment_description,
        tag_number=record.tag_number,
        vendor=record.vendor,
        vendor_model=record.vendor_model,
        source_module=record.source_module,
        source_service=record.source_service,
        source_record_id=record.source_record_id,
        procurement_status=record.procurement_status,
        installation_location=record.installation_location,
        net_weight=record.net_weight,
        equipment_status=record.equipment_status,
        sign_status=ss_value,
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


@router.get("", response_model=EquipListListResponse)
async def list_equipment(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
    project_id: uuid.UUID | None = Query(None),
    workspace_id: uuid.UUID | None = Query(None),
    source_module: str | None = Query(None, max_length=30),
    sign_status: str | None = Query(None, max_length=20),
    equipment_status: str | None = Query(None, max_length=2),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> EquipListListResponse:
    """分页查询 EquipmentList；按 project/workspace/source_module/sign/equipment status 过滤。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    rows, total = await persist_service.list_equipment_records(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        source_module=source_module,
        sign_status=sign_status,
        equipment_status=equipment_status,
        limit=limit,
        offset=offset,
    )
    return EquipListListResponse(
        items=[_to_response(r) for r in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{equipment_id}", response_model=EquipListResponse)
async def get_equipment(
    equipment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> EquipListResponse:
    """单条 EquipmentList 查询。

    F-P1-014 + BLOCKER-3: 当前仅 require_roles role 校验, 未做
    _check_user_project_access(db, user, record.project_id) 校验.
    P7-7+ UserProject model 立项后加 (P7 Sprint 主线外 BLOCKER-3).
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    from fastapi import HTTPException

    from app.models.equipment import EquipmentList
    from sqlalchemy import select

    record = (
        await db.execute(
            select(EquipmentList).where(EquipmentList.equipment_id == equipment_id)
        )
    ).scalar_one_or_none()
    if record is None:
        raise HTTPException(status_code=404, detail=f"EquipmentList not found: {equipment_id}")
    return _to_response(record)


@router.post("/{equipment_id}/sync", response_model=EquipListSyncResponse)
async def sync_equipment(
    equipment_id: uuid.UUID,
    body: EquipListSyncRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> EquipListSyncResponse:
    """手动 trigger sync_from_source（已有 equipment_id 的 source_record）。

    注：equipment_id 参数保留用于 API 一致性（resource-action pattern），但实际
    sync 由 body.source_record_id 决定；同步结果会写到同 (project_id, tag_number)
    EquipmentList（即本 equipment_id）。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    from fastapi import HTTPException

    from app.models.equipment import EquipmentList
    from sqlalchemy import select

    # 验证 equipment_id 存在（404 fast-fail）
    existing = (
        await db.execute(
            select(EquipmentList).where(EquipmentList.equipment_id == equipment_id)
        )
    ).scalar_one_or_none()
    if existing is None:
        raise HTTPException(
            status_code=404, detail=f"EquipmentList not found: {equipment_id}"
        )

    record = await sync_service.sync_from_source(
        source_module=body.source_module,
        source_service=body.source_service,
        source_record_id=body.source_record_id,
        db=db,
    )
    was_created = (record.equipment_id != existing.equipment_id)
    return EquipListSyncResponse(
        item=_to_response(record),
        was_created=was_created,
    )


@router.post(
    "/bulk-sync",
    response_model=EquipListBulkSyncResponse,
    status_code=status.HTTP_200_OK,
)
async def bulk_sync_equipment(
    body: EquipListBulkSyncRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> EquipListBulkSyncResponse:
    """批量 sync_from_source（1-100 条目）；partial failure 容错。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    entries = [e.model_dump() for e in body.entries]
    succeeded, failed = await persist_service.bulk_sync_from_sources(entries, db)
    return EquipListBulkSyncResponse(
        succeeded=[
            EquipListSyncResponse(item=_to_response(r), was_created=True)
            for r in succeeded
        ],
        failed=failed,
    )
