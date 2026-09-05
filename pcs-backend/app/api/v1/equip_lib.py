"""equip-lib 端点（Task 1.9.5 / P2-EQL-001）。

沉淀（settle）建 CATEGORY_6 ConfigAsset（DRAFT），审批复用 /config/assets 既有
submit/approve/publish 链；检索（search）仅返回 PUBLISHED。

ACL：写（settle）= PROCESS_CONTROLLER + SYSTEM_ADMIN；
读（search）= DESIGNER + PROCESS_CONTROLLER + SYSTEM_ADMIN。
`current_actor / require_roles / _Actor` 与 config.py 同源（该模块 `__all__` 导出）。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.config import AssetResponse
from app.schemas.equip_lib import EquipLibSettleRequest
from app.services.equip_lib_service import EquipLibService

router = APIRouter(prefix="/equip-lib", tags=["equip-lib"])


@router.get("/search", response_model=list[AssetResponse])
async def search(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    keyword: str | None = Query(None),
    equipment_type: str | None = Query(None),
    limit: int = Query(50),
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await EquipLibService.search(
        db, keyword=keyword, equipment_type=equipment_type, limit=limit
    )


@router.post("/settle", response_model=AssetResponse, status_code=201)
async def settle(
    payload: EquipLibSettleRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await EquipLibService.settle(
        db,
        payload=payload,
        source_equipment_id=payload.source_equipment_id,
        source_project_id=payload.source_project_id,
        created_by=user.user_id,
    )
