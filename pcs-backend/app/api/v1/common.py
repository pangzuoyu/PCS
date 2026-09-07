"""COMMON 物性 / 许用应力 / 介质安全 端点（P3.3 / spec §3.2.3 + §3.1.2）。

端点：
- GET /api/v1/common/materials/search      物质搜索（按名称/CAS/分子式）
- GET /api/v1/common/materials/{cas}       物质完整物性
- GET /api/v1/common/allowable-stress      材料许用应力（ASME B31.3 Table A-1 插值）
- GET /api/v1/common/safety                介质安全（毒性 + 爆炸极限）

ACL：读 = DESIGNER + PROCESS_CONTROLLER + SYSTEM_ADMIN。
`current_actor / require_roles / _Actor` 与 config.py 同源。
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db  # noqa: F401  预留项目级 DB 注入位
from app.schemas.common import (
    AllowableStressResult,
    MaterialDetail,
    MaterialSearchResult,
    SafetyResult,
)
from app.services.common_service import CommonService

router = APIRouter(prefix="/common", tags=["common"])


@router.get("/materials/search", response_model=list[MaterialSearchResult])
async def search_materials(
    user: Annotated[_Actor, Depends(current_actor)],
    keyword: str = Query(..., min_length=1, description="物质名称/CAS/分子式"),
):
    """按关键字搜索 chemicals 库。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return CommonService.search_material(keyword)


@router.get("/materials/{cas}", response_model=MaterialDetail)
async def get_material(
    cas: str,
    user: Annotated[_Actor, Depends(current_actor)],
):
    """按 CAS 查完整物性（water 走 IAPWS-IF97 精确值）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return CommonService.get_material(cas)


@router.get("/allowable-stress", response_model=AllowableStressResult)
async def get_allowable_stress(
    user: Annotated[_Actor, Depends(current_actor)],
    material: str = Query(..., min_length=1, description="材料牌号（如 A106-GrB）"),
    temp_c: float = Query(..., ge=-200, le=2000, description="温度 °C"),
):
    """ASME B31.3 Table A-1 按温度插值查许用应力。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return CommonService.allowable_stress(material, temp_c)


@router.get("/safety", response_model=SafetyResult)
async def get_safety(
    user: Annotated[_Actor, Depends(current_actor)],
    cas: str = Query(..., min_length=1, description="CAS 注册号"),
):
    """介质毒性 + 爆炸极限（内置安全库）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return CommonService.safety_data(cas)