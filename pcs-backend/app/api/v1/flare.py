"""P6-2 FLARE_SYS API：Task 20 header_sizing + Task 21 kod_sizing +
Task 22 stack_design + Task 23 flare_tip + flare_persist CRUD 端点。

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
- POST /api/v1/flare/tip
    body: FlareTipRequest
    response: FlareTipResponse（API 521 §5.15.6 Flare Tip Velocity）
- POST   /api/v1/flare/results        创建 FlareSystemResult（201）
- GET    /api/v1/flare/results        列出 FlareSystemResult（分页）
- GET    /api/v1/flare/results/{id}   详情
- PATCH  /api/v1/flare/results/{id}   更新（仅 DRAFT/CHANGE_PENDING 可改）
- DELETE /api/v1/flare/results/{id}   软删除（→ OBSOLETE）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
- 业务异常 → 走 core.errors.PcsError envelope
- 计算端点（header_sizing / kod_sizing / stack_design / tip）不写 DB；落库
  统一由 flare_persist endpoints 处理（Task 23 SPEC §3.2.3 P6-FLR-004）
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.models.enums import RecordSignStatus9
from app.schemas.flare import (
    FlareResultCreateRequest,
    FlareResultListResponse,
    FlareResultResponse,
    FlareResultUpdateRequest,
    FlareTipRequest,
    FlareTipResponse,
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
from app.services.flare.flare_persist_service import (  # P6-2 Task 23
    FlarePersistInputError,
    save_flare_result,
)
from app.services.flare.flare_persist_service import (
    get_flare_result as get_flare_result_service,
)
from app.services.flare.flare_persist_service import (
    list_flare_results as list_flare_results_service,
)
from app.services.flare.flare_persist_service import (
    soft_delete_flare_result as soft_delete_flare_result_service,
)
from app.services.flare.flare_persist_service import (
    update_flare_result as update_flare_result_service,
)
from app.services.flare.flare_tip import (  # P6-2 Task 23
    FlareTipInput,
    calc_flare_tip,
)
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
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSADMIN bypass)
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=req.project_id,
        actor_roles=actor_roles_list,
    )
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
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSADMIN bypass)
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=req.project_id,
        actor_roles=actor_roles_list,
    )
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
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSADMIN bypass)
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=req.project_id,
        actor_roles=actor_roles_list,
    )
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


# ───────────────────────────── Task 23 flare_tip ──────────────────────────────


@router.post("/tip", response_model=FlareTipResponse)
async def calculate_flare_tip(
    req: FlareTipRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FlareTipResponse:
    """API 521 §5.15.6 火炬尖端速度 + Mach 数计算。

    复用 Task 20 header_sizing 的等温声速 / 理想气体密度公式，按尖端工况
    （header 出口 P/T）计算 tip 点速度与马赫数。本接口纯计算不写 DB（落库
    由 Task 23 flare_persist 统一处理）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSADMIN bypass)
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=req.project_id,
        actor_roles=actor_roles_list,
    )
    try:
        result = calc_flare_tip(
            FlareTipInput(
                header_diameter_m=req.header_diameter_m,
                mw_kg_kmol=req.mw_kg_kmol,
                tip_temperature_k=req.tip_temperature_k,
                tip_pressure_pa=req.tip_pressure_pa,
                specific_heat_ratio=req.specific_heat_ratio,
                target_mach=req.target_mach,
            )
        )
    except PcsError as e:
        raise _to_http(e) from e

    # 不写 DB（tip 是纯计算，落库由 flare_persist 统一处理）
    del db

    return FlareTipResponse(
        tip_diameter_m=result.tip_diameter_m,
        tip_area_m2=result.tip_area_m2,
        tip_velocity_m_s=result.tip_velocity_m_s,
        actual_mach=result.actual_mach,
        sound_speed_m_s=result.sound_speed_m_s,
        gas_density_kg_m3=result.gas_density_kg_m3,
        mass_flux_kgs_m2=result.mass_flux_kgs_m2,
        project_id=req.project_id,
        standard_profile_code=req.standard_profile_code,
        formula_ref=result.formula_ref,
    )


# ───────────────────────────── Task 23 flare_persist CRUD ──────────────────────


@router.post("/results", response_model=FlareResultResponse, status_code=201)
async def create_flare_result(
    req: FlareResultCreateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FlareResultResponse:
    """创建 FlareSystemResult 行（POST → 201）。

    save_flare_result service 层自动 final record_hash（ADR-0028 §决策 4），
    返回创建后的完整 FlareSystemResult 行。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSADMIN bypass)
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=req.project_id,
        actor_roles=actor_roles_list,
    )
    # 字符串 sign_status → enum（非法字面 → 422 PcsError envelope）
    try:
        sign_status_enum = RecordSignStatus9(req.sign_status)
    except ValueError as e:
        raise _to_http(
            CorePcsError(
                code="FLARE_RESULT_SIGN_STATUS_INVALID",
                message=f"sign_status={req.sign_status!r} 非法：{e}",
                status=422,
            )
        ) from e
    # 业务 payload：排除溯源 / mixin 必填（已拆为 save_flare_result 显式 kwarg）
    # dump 用 field names（不用 by_alias=True）—— pass_ 字段需映射成 Python
    # 属性名 save_flare_result 才能匹配 _FLARESYSTEM_BUSINESS_FIELDS 白名单
    payload = req.model_dump(
        exclude={
            "project_id",
            "workspace_id",
            "tag_number",
            "standard_profile_code",
            "calc_type",
            "sign_status",
        },
    )
    actor_id = getattr(user, "id", None) or getattr(user, "user_id", None)
    try:
        record = await save_flare_result(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            standard_profile_code=req.standard_profile_code,
            calc_type=req.calc_type,
            sign_status=sign_status_enum,
            payload=payload,
            created_by=actor_id,
        )
    except FlarePersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return FlareResultResponse.model_validate(record, from_attributes=True)


@router.get("/results", response_model=FlareResultListResponse)
async def list_flare_results(
    project_id: Annotated[uuid.UUID, Query(...)],
    standard_profile_code: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> FlareResultListResponse:
    """按 project_id 列出 FlareSystemResult（GET list，分页）。

    默认 sign_status filter = (DRAFT, CHECKED) — 排除 OBSOLETE 等门禁态。
    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSADMIN bypass)
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=actor_roles_list,
    )
    records = await list_flare_results_service(
        db,
        project_id=project_id,
        standard_profile_code=standard_profile_code,
        limit=limit,
        offset=offset,
    )
    items = [
        FlareResultResponse.model_validate(r, from_attributes=True) for r in records
    ]
    return FlareResultListResponse(
        items=items, total=len(items), limit=limit, offset=offset
    )


@router.get("/results/{record_id}", response_model=FlareResultResponse)
async def get_flare_result(
    record_id: uuid.UUID,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> FlareResultResponse:
    """按 id 取 FlareSystemResult（GET detail）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    record = await get_flare_result_service(db, record_id=record_id)
    if record is None:
        raise HTTPException(status_code=404, detail="FlareSystemResult not found")
    # BLOCKER-3 P7-7+: record 级守卫 (SYSADMIN bypass)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=record.project_id,
        actor_roles=actor_roles_list,
    )
    return FlareResultResponse.model_validate(record, from_attributes=True)


@router.patch("/results/{record_id}", response_model=FlareResultResponse)
async def update_flare_result(
    record_id: uuid.UUID,
    req: FlareResultUpdateRequest,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> FlareResultResponse:
    """更新 FlareSystemResult 业务字段（PATCH；仅 DRAFT/CHANGE_PENDING 可改）。

    CHECKED / IN_APPROVAL / REVERSAL_PENDING 等锁定态拒绝更新（避免评审中
    数据漂移）。project_id 由 ACL 在 Phase 后续 PATCH 透传；本批次为
    None（service 层不强制隔离）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    payload = req.model_dump(exclude_unset=True)
    try:
        record = await update_flare_result_service(
            db,
            record_id=record_id,
            project_id=None,
            payload=payload,
        )
    except FlarePersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e
    if record is None:
        raise HTTPException(status_code=404, detail="FlareSystemResult not found")
    # BLOCKER-3 P7-7+: record 级守卫 (SYSADMIN bypass)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=record.project_id,
        actor_roles=actor_roles_list,
    )
    return FlareResultResponse.model_validate(record, from_attributes=True)


@router.delete("/results/{record_id}", status_code=204)
async def delete_flare_result(
    record_id: uuid.UUID,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> None:
    """软删除 FlareSystemResult（DELETE → sign_status=OBSOLETE）。

    软删而非物理删除（SPEC §3.2.3 P6-FLR-004 审计要求）；记录不再被
    list 默认过滤（DRAFT/CHECKED filter）展示。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    # BLOCKER-3 P7-7+: 先 fetch 拿 project_id 再 guard
    pre_record = await get_flare_result_service(db, record_id=record_id)
    if pre_record is None:
        raise HTTPException(status_code=404, detail="FlareSystemResult not found")
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=pre_record.project_id,
        actor_roles=actor_roles_list,
    )
    ok = await soft_delete_flare_result_service(
        db, record_id=record_id, project_id=None
    )
    if not ok:
        raise HTTPException(status_code=404, detail="FlareSystemResult not found")


__all__ = ["router"]