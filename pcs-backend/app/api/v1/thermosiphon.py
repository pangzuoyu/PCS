"""P5-0-1b T1 热虹吸循环安装高度 API：POST /calculate 端点契约。

按 SUP-010 §3.5（thermosiphon_circulation_results）+ GPSA §20.4 壳程压力平衡：

端点：
- POST /api/v1/thermosiphon/calculate
    body: ThermosiphonCalculateRequest（几何 + 物性 + 三段 P11/P12 阻力项）
    response: ThermosiphonCalculateResponse（Hx / Hxo / 推动力比 / 校核 + formula_ref）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与 psv / vessel / sep_equip 一致）
- 纯计算端点：安装高度是安装尺寸核算，不产生物流变化，故**不落库**
  （落库由 ThermosiphonCirculationPersistService 显式调用，POST /persist 端点）
- 业务异常 → ThermosiphonCirculationError（ServicePcsError 子类，status=422）
  由 install_exception_handlers 兜底转 422 envelope
  （THERMOSIPHON_INPUT_ERROR），此处不显式 try/except
  （与 /restriction/drain-orifice/size 对齐）

不做：
- 不落库（见上）
- 不做 outlet stream（安装尺寸核算无物流变化，区别 restriction / cv）
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status

from app.api.v1.config import _Actor, current_actor, require_roles
from app.schemas.thermosiphon import (
    ThermosiphonCalculateRequest,
    ThermosiphonCalculateResponse,
)
from app.services.heat.thermosiphon_service import (
    ThermosiphonCirculationInput,
    calc_thermosiphon_circulation,
)

router = APIRouter(prefix="/thermosiphon", tags=["thermosiphon"])


@router.post(
    "/calculate",
    response_model=ThermosiphonCalculateResponse,
    status_code=status.HTTP_200_OK,
)
async def thermosiphon_calculate(
    req: ThermosiphonCalculateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
) -> ThermosiphonCalculateResponse:
    """POST /api/v1/thermosiphon/calculate：热虹吸循环安装高度计算。

    纯计算，不落库（落库由 ThermosiphonCirculationPersistService 负责）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    result = calc_thermosiphon_circulation(ThermosiphonCirculationInput(**req.model_dump()))
    return ThermosiphonCalculateResponse(
        installation_height_calc_m=result.installation_height_calc_m,
        installation_height_final_m=result.installation_height_final_m,
        driving_coeff_per_m=result.driving_coeff_per_m,
        resistance_const_m=result.resistance_const_m,
        resistance_coeff_per_m=result.resistance_coeff_per_m,
        circulation_drive_ratio=result.circulation_drive_ratio,
        check_result=result.check_result,
        formula_ref_standard=result.formula_ref.standard,
        formula_ref_version=result.formula_ref.version,
        formula_ref_clause=result.formula_ref.clause,
        formula_ref_source=result.formula_ref.source,
    )


__all__ = ["router"]
