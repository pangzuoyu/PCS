"""P6-2 FLARE_SYS API：Task 20 header_sizing + Task 21 kod_sizing + Task 22 stack_design 端点。

端点：
- POST /api/v1/flare/header-sizing
    body: HeaderSizingRequest
    response: HeaderSizingResponse（API 521 §5.15.4 Mach 数法）
- POST /api/v1/flare/kod-sizing
    body: KodSizingRequest
    response: KodSizingResponse（API 521 §5.15.3 Souders-Brown + §5.15.5 Water Seal）
- POST /api/v1/flare/stack-design
    body: StackDesignRequest
    response: StackDesignResponse（API 521 §7.4.2.2 Stack Height + §7.4.2.3 Radiation + BEDD）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
- 业务异常 → 走 core.errors.PcsError envelope
- 不写 DB（header_sizing / kod_sizing / stack_design 是独立计算，结果由 flare_persist
  统一落库 — Task 23）
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.schemas.flare import (
    HeaderSizingRequest,
    HeaderSizingResponse,
    KodInfo,
    KodSizingRequest,
    KodSizingResponse,
    RadiationCheckInfo,
    StackDesignRequest,
    StackDesignResponse,
    StackHeightInfo,
    WaterSealInfo,
)
from app.services.exceptions import PcsError
from app.services.flare.header_sizing import (
    HeaderSizingInput,
    calc_header_sizing,
)
from app.services.flare.kod_sizing import (  # P6-2 Task 21
    KodInput,
    WaterSealInput,
    calc_kod_sizing,
)
from app.services.flare.stack_design import (  # P6-2 Task 22
    RadiationCheckInput,
    StackHeightInput,
    calc_radiation_check,
    calc_stack_height,
)

router = APIRouter(prefix="/flare", tags=["flare"])


def _to_http(err: PcsError) -> CorePcsError:
    """service 层 PcsError → FastAPI HTTPException envelope。"""
    return CorePcsError(
        code=err.code, message=str(err), status=err.status
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


@router.post("/kod-sizing", response_model=KodSizingResponse)
async def calculate_kod_sizing(
    req: KodSizingRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> KodSizingResponse:
    """Souders-Brown KOD 直径 + Water Seal 液柱高度综合计算。

    按 API 521 §5.15.3（Souders-Brown 法 KOD 直径）+ §5.15.5（Water Seal
    液柱高度）综合调用。输入参数来自 Task 19（vapor mass flow）+ Task 20
    （header P/T）；不写 DB（落库由 Task 23 flare_persist 统一处理）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        result = calc_kod_sizing(
            kod=KodInput(
                vapor_mass_flow_kgs=req.vapor_mass_flow_kgs,
                vapor_density_kg_m3=req.vapor_density_kg_m3,
                liquid_density_kg_m3=req.liquid_density_kg_m3,
                k_sb_m_s=req.k_sb_m_s,
            ),
            water=WaterSealInput(
                header_pressure_pa=req.header_pressure_pa,
                seal_pot_pressure_pa=req.seal_pot_pressure_pa,
                water_density_kg_m3=req.water_density_kg_m3,
                gravity_m_s2=req.gravity_m_s2,
                safety_factor=req.safety_factor,
                surge_pressure_pa=req.surge_pressure_pa,
            ),
        )
    except PcsError as e:
        raise _to_http(e) from e

    # 不写 DB（kod_sizing 是独立计算，落库由 Task 23 flare_persist 统一处理）
    del db  # 显式不使用 session（避免 pylint unused-argument）

    return KodSizingResponse(
        kod=KodInfo(
            diameter_m=result.kod.diameter_m,
            area_m2=result.kod.area_m2,
            u_perm_m_s=result.kod.u_perm_m_s,
            u_actual_m_s=result.kod.u_actual_m_s,
            limit_ratio=result.kod.limit_ratio,
            formula_ref=result.kod.formula_ref,
        ),
        water_seal=WaterSealInfo(
            h_seal_m=result.water_seal.h_seal_m,
            h_design_m=result.water_seal.h_design_m,
            delta_pressure_pa=result.water_seal.delta_pressure_pa,
            formula_ref=result.water_seal.formula_ref,
        ),
        project_id=req.project_id,
        standard_profile_code=req.standard_profile_code,
        formula_ref=result.formula_ref,
    )


@router.post("/stack-design", response_model=StackDesignResponse)
async def calculate_stack_design(
    req: StackDesignRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StackDesignResponse:
    """API 521 §7.4.2.2 火炬高度 + §7.4.2.3 地面辐射 + BEDD 限值校验综合端点。

    接力实现要点：
    1. endpoint 内**先单独调** ``calc_stack_height`` 拿到真实 h_stack_m
       （不能用占位 0.0；辐射计算的 h_stack 接力必须用 stack_height 的实际结果）
    2. 用真实 h_stack_m 构造 ``RadiationCheckInput`` 再调 ``calc_radiation_check``
    3. 综合 stack_height + radiation 子结果返回

    输入来自 Task 19（Q_total）+ Task 20（header 几何）；不写 DB（落库由
    Task 23 flare_persist 统一处理）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        # ── 接力 step 1: 先调 stack_height 拿真实 h_stack_m ──
        stack_r = calc_stack_height(
            StackHeightInput(
                total_heat_release_mw=req.total_heat_release_mw,
                stability_class=req.stability_class,
                h_min_engineering_m=req.h_min_engineering_m,
                wind_speed_m_s=req.wind_speed_m_s,
            )
        )
        # ── 接力 step 2: 用真实 h_stack_m 串入 radiation_check ──
        radiation_r = calc_radiation_check(
            RadiationCheckInput(
                q_radiated_mw=req.q_radiated_mw,
                h_stack_m=stack_r.h_stack_m,  # 接力：真实高度（非占位 0.0）
                receptor_distance_m=req.receptor_distance_m,
                flame_height_m=req.flame_height_m,
                tilt_angle_deg=req.tilt_angle_deg,
                bedd_limit_kw_m2=req.bedd_limit_kw_m2,
            )
        )
    except PcsError as e:
        raise _to_http(e) from e

    # 不写 DB（stack_design 是独立计算，落库由 Task 23 flare_persist 统一处理）
    del db  # 显式不使用 session（避免 pylint unused-argument）

    return StackDesignResponse(
        stack_height=StackHeightInfo(
            h_stack_m=stack_r.h_stack_m,
            h_effective_m=stack_r.h_effective_m,
            buoyancy_rise_m=stack_r.buoyancy_rise_m,
            dispersion_factor=stack_r.dispersion_factor,
            formula_ref=stack_r.formula_ref,
        ),
        radiation=RadiationCheckInfo(
            q_at_receptor_w_m2=radiation_r.q_at_receptor_w_m2,
            q_at_receptor_kw_m2=radiation_r.q_at_receptor_kw_m2,
            bedd_compliant=radiation_r.bedd_compliant,
            bedd_limit_kw_m2=radiation_r.bedd_limit_kw_m2,
            flame_center_height_m=radiation_r.flame_center_height_m,
            slant_distance_m=radiation_r.slant_distance_m,
            formula_ref=radiation_r.formula_ref,
        ),
        project_id=req.project_id,
        standard_profile_code=req.standard_profile_code,
        formula_ref="API_521_§7.4.2.2+§7.4.2.3",
    )


__all__ = ["router"]