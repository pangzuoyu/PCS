"""供应商实际数据录入 API (P7 Sprint 4 S4-1 / ADR-0025).

端点（2）：
- GET /api/v1/equipment/{equipment_id}/actual-data → 读回录入值
- PUT /api/v1/equipment/{equipment_id}/actual-data → 录入一整台设备的参数集

录入入口是**手工 UI 页面**（S4-1 裁决）：要求供应商填统一 Excel 不现实，
故无 Excel 批量导入端点 —— 设备方逐项在页面上录入。

PUT 语义是**整体替换**而非合并：页面上「重录」是覆盖，不是追加；合并会让
上轮残留值混入 S4-2 的偏差计算，而录入者以为已经改过。

ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（VIEWER 只读，走 GET）。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.equipment import EquipmentList
from app.schemas.supplier import (
    ActualDataEntryRequest,
    ActualDataResponse,
)
from app.services.supplier.actual_data_service import record_actual_data

router = APIRouter(prefix="/equipment", tags=["supplier"])

_WRITE_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
_READ_ROLES = ("VIEWER", "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")


async def _load_equipment(
    db: AsyncSession, equipment_id: uuid.UUID, actor: _Actor
) -> EquipmentList:
    """取设备并校验访问权；查无或无权统一 404（不泄漏存在性）。"""
    record = (
        await db.execute(
            select(EquipmentList).where(EquipmentList.equipment_id == equipment_id)
        )
    ).scalar_one_or_none()
    if record is None:
        # 与 guard 同语义：设备不存在 = 对该 caller 不可见
        raise HTTPException(status_code=404, detail="Equipment not found")
    await check_project_access_or_404(
        db,
        user_id=actor.user_id,
        project_id=record.project_id,
        actor_roles=actor.roles,
    )
    return record


def _to_response(record: EquipmentList) -> ActualDataResponse:
    return ActualDataResponse(
        equipment_id=str(record.equipment_id),
        tag_number=record.tag_number,
        actual_data_status=record.actual_data_status,
        actual_data_json=record.actual_data_json,
    )


@router.get("/{equipment_id}/actual-data", response_model=ActualDataResponse)
async def get_actual_data(
    equipment_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> ActualDataResponse:
    """读回设备实测值。未录入时 actual_data_json 为 null。"""
    require_roles(actor, *_READ_ROLES)
    record = await _load_equipment(db, equipment_id, actor)
    return _to_response(record)


@router.put("/{equipment_id}/actual-data", response_model=ActualDataResponse)
async def put_actual_data(
    equipment_id: uuid.UUID,
    body: ActualDataEntryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> ActualDataResponse:
    """录入一整台设备的参数集（整体替换），状态转 PENDING_CONFIRM。

    PcsError ACTUAL_DATA_VALIDATION 422 由全局 handler 转 422 —— UI 逐项
    提示，不静默丢值。
    """
    require_roles(actor, *_WRITE_ROLES)
    record = await _load_equipment(db, equipment_id, actor)
    updated = await record_actual_data(
        db, record, [e.model_dump() for e in body.entries]
    )
    return _to_response(updated)
