"""P6-2 FLARE_SYS API：Task 20 header_sizing 端点。

端点：
- POST /api/v1/flare/header-sizing
    body: HeaderSizingRequest
    response: HeaderSizingResponse

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
- 业务异常 → 走 core.errors.PcsError envelope
- 不写 DB（header_sizing 是独立计算，结果由 flare_persist 统一落库 — Task 23）
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.schemas.flare import HeaderSizingRequest, HeaderSizingResponse
from app.services.exceptions import PcsError
from app.services.flare.header_sizing import (
    HeaderSizingInput,
    calc_header_sizing,
)

router = APIRouter(prefix="/flare", tags=["flare"])


def _to_http(err: PcsError) -> CorePcsError:
    """service 层 PcsError → FastAPI HTTPException envelope。"""
    return CorePcsError(
        code=err.code, message=str(err), status_code=err.status
    )


@router.post("/header-sizing", response_model=HeaderSizingResponse)
async def calculate_header_sizing(
    req: HeaderSizingRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HeaderSizingResponse:
    """Mach 数法 + 等温可压缩管流计算火炬总管直径（API 521 §5.15.4）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        result = calc_header_sizing(
            HeaderSizingInput(
                relief_mass_flow_kgs=req.relief_mass_flow_kgs,
                avg_temperature_k=req.avg_temperature_k,
                avg_pressure_pa=req.avg_pressure_pa,
                mw_kg_kmol=req.mw_kg_kmol,
                specific_heat_ratio=req.specific_heat_ratio,
                target_mach=req.target_mach,
            )
        )
    except PcsError as e:
        raise _to_http(e) from e

    # 不写 DB（header_sizing 是独立计算，落库由 Task 23 flare_persist 统一处理）
    del db  # 显式不使用 session（避免 pylint unused-argument）

    return HeaderSizingResponse(
        diameter_m=result.diameter_m,
        area_m2=result.area_m2,
        actual_mach=result.actual_mach,
        mass_flux_kgs_m2=result.mass_flux_kgs_m2,
        velocity_m_s=result.velocity_m_s,
        sound_speed_m_s=result.sound_speed_m_s,
        gas_density_kg_m3=result.gas_density_kg_m3,
        formula_ref=result.formula_ref,
        project_id=req.project_id,
        standard_profile_code=req.standard_profile_code,
    )


__all__ = ["router"]