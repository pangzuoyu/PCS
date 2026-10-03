"""P6-3 FILTRATION API（SPEC §3.2.7 + Task 34）。

端点（8 个）：
- POST /api/v1/filtration/ruth-constant-pressure/calculate   POST §3.2.7 Ruth 恒压（201）
- POST /api/v1/filtration/ruth-constant-rate/calculate       POST §3.2.7 Ruth 恒速（201）
- POST /api/v1/filtration/ergun/calculate                     POST §3.2.7 Ergun 介质阻力（201）
- POST   /api/v1/filtration/results         创建 FiltrationResult（201）
- GET    /api/v1/filtration/results         列出（分页）
- GET    /api/v1/filtration/results/{id}    详情
- PATCH  /api/v1/filtration/results/{id}    更新（仅 DRAFT/CHANGE_PENDING 可改）
- DELETE /api/v1/filtration/results/{id}    软删除（→ OBSOLETE）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（8 endpoints 全部用
  ``require_roles``，与 Task 32 OPEN_CHANNEL 一致）
- 业务异常 → 走 core.errors.PcsError envelope
- 3 calc 端点：endpoint 调 calc_* → save_*_result service 层构造 record，
  禁止 endpoint 直构 FiltrationResult（红线 #1）
- PATCH 锁定态：CHECKED / IN_APPROVAL 等拒绝 PATCH（FILTRATION_LOCKED）
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
from app.schemas.filtration import (
    ErgunCalcRequest,
    ErgunCalcResponse,
    FiltrationCreateRequest,
    FiltrationDeleteResponse,
    FiltrationListResponse,
    FiltrationResultResponse,
    FiltrationUpdateRequest,
    RuthConstantPressureCalcRequest,
    RuthConstantPressureCalcResponse,
    RuthConstantRateCalcRequest,
    RuthConstantRateCalcResponse,
)
from app.services.exceptions import PcsError as ServicePcsError
from app.services.filtration import (  # P6-3 Task 34
    ErgunInput,
    ErgunInputError,
    FiltrationPersistInputError,
    RuthConstantPressureInput,
    RuthConstantPressureInputError,
    RuthConstantRateInput,
    RuthConstantRateInputError,
    calc_ergun_pressure_drop,
    calc_ruth_constant_pressure,
    calc_ruth_constant_rate,
    create_filtration_result_direct,
    get_filtration_result_service,
    list_filtration_results_service,
    save_ergun_result,
    save_ruth_constant_pressure_result,
    save_ruth_constant_rate_result,
    soft_delete_filtration_result_service,
    update_filtration_result_service,
)

router = APIRouter(prefix="/filtration", tags=["filtration"])


def _to_http(err: ServicePcsError) -> CorePcsError:
    """service 层 PcsError → FastAPI HTTPException envelope。

    注：P6-OPEN-010 fix — CorePcsError 使用 ``status`` kwarg（非
    ``status_code``，避免与 HTTPException 混淆）。
    """
    return CorePcsError(
        code=err.code, message=str(err), status=err.status
    )


# ============================================================================
# 3 calc endpoints（POST /filtration/{ruth-constant-pressure,ruth-constant-rate,ergun}/calculate）
# ============================================================================


@router.post(
    "/ruth-constant-pressure/calculate",
    response_model=RuthConstantPressureCalcResponse,
    status_code=201,
)
async def calculate_ruth_constant_pressure(
    req: RuthConstantPressureCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RuthConstantPressureCalcResponse:
    """Ruth 恒压过滤计算（§3.2.7 第一项）。

    流程：endpoint 调 ``calc_ruth_constant_pressure`` → save_ruth_constant_
    pressure_result service 落 FiltrationResult 行；禁止 endpoint 直构 ORM
    （红线 #1）。

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
        # 1. 调 calc（RuthConstantPressureInput）
        #    恒压路径：默认 viscosity=1e-3（水），solid_concentration=10
        #    （介质含固量 kg/m³）；cake / R₀ 用户未传则用占位 1e10。
        inp = RuthConstantPressureInput(
            filtration_area=req.area,
            delta_pressure=req.pressure_drop,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=req.cake_resistance_alpha or 1e10,
            solid_concentration=10.0,
            medium_resistance=req.specific_resistance_r0 or 1e10,
            filtration_time=req.cycle_time * 3600.0,  # h → s
        )
        calc_r = calc_ruth_constant_pressure(inp)
    except RuthConstantPressureInputError as e:
        raise _to_http(e) from e

    # 2. save 服务层构造 record（endpoint 不直构 ORM）
    actor_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    try:
        record = await save_ruth_constant_pressure_result(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            media_type=req.media_type,
            area=req.area,
            cycle_time=req.cycle_time,
            pressure_drop=req.pressure_drop,
            cake_resistance_alpha=req.cake_resistance_alpha,
            specific_resistance_r0=req.specific_resistance_r0,
            filter_velocity=(
                calc_r.average_flow_rate / req.area if req.area > 0 else 0.0
            ),
            created_by=actor_id,
        )
    except FiltrationPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return RuthConstantPressureCalcResponse(
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        tag_number=record.tag_number,
        media_type=record.media_type,
        area=record.area,
        cycle_time=record.cycle_time,
        pressure_drop=record.pressure_drop,
        cake_resistance_alpha=record.cake_resistance_alpha,
        specific_resistance_r0=record.specific_resistance_r0,
        permeability_k=record.permeability_k,
        porosity_eps=record.porosity_eps,
        filter_velocity=record.filter_velocity,
        result_id=record.filter_id,
        record_hash=record.record_hash,
        sign_status=record.sign_status.value,
        created_at=record.created_at,
    )


@router.post(
    "/ruth-constant-rate/calculate",
    response_model=RuthConstantRateCalcResponse,
    status_code=201,
)
async def calculate_ruth_constant_rate(
    req: RuthConstantRateCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> RuthConstantRateCalcResponse:
    """Ruth 恒速过滤计算（§3.2.7 第二项）。

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
        # 恒速：默认流速 Q = filter_velocity * area（m/s × m² = m³/s）
        q_default = (req.filter_velocity or 1e-4) * req.area
        inp = RuthConstantRateInput(
            constant_flow_rate=q_default if q_default > 0 else 1e-3,
            filtration_area=req.area,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=req.cake_resistance_alpha or 1e10,
            solid_concentration=10.0,
            medium_resistance=req.specific_resistance_r0 or 1e10,
            filtration_time=req.cycle_time * 3600.0,  # h → s
        )
        calc_ruth_constant_rate(inp)
    except RuthConstantRateInputError as e:
        raise _to_http(e) from e

    actor_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    try:
        record = await save_ruth_constant_rate_result(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            media_type=req.media_type,
            area=req.area,
            cycle_time=req.cycle_time,
            pressure_drop=req.pressure_drop,
            cake_resistance_alpha=req.cake_resistance_alpha,
            specific_resistance_r0=req.specific_resistance_r0,
            filter_velocity=req.filter_velocity,
            created_by=actor_id,
        )
    except FiltrationPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return RuthConstantRateCalcResponse(
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        tag_number=record.tag_number,
        media_type=record.media_type,
        area=record.area,
        cycle_time=record.cycle_time,
        pressure_drop=record.pressure_drop,
        cake_resistance_alpha=record.cake_resistance_alpha,
        specific_resistance_r0=record.specific_resistance_r0,
        permeability_k=record.permeability_k,
        porosity_eps=record.porosity_eps,
        filter_velocity=record.filter_velocity,
        result_id=record.filter_id,
        record_hash=record.record_hash,
        sign_status=record.sign_status.value,
        created_at=record.created_at,
    )


@router.post(
    "/ergun/calculate",
    response_model=ErgunCalcResponse,
    status_code=201,
)
async def calculate_ergun(
    req: ErgunCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ErgunCalcResponse:
    """Ergun 介质阻力计算（§3.2.7 第三项 — 深层过滤）。

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
        # Ergun 默认：dp=0.5e-3（砂 0.5mm），μ=1e-3，ρ=1000，L=1m
        inp = ErgunInput(
            superficial_velocity=req.filter_velocity or 1e-3,
            bed_porosity=req.porosity_eps or 0.4,
            particle_diameter=0.5e-3,
            fluid_viscosity=1e-3,
            fluid_density=1000.0,
            bed_length=1.0,
        )
        calc_ergun_pressure_drop(inp)
    except ErgunInputError as e:
        raise _to_http(e) from e

    actor_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    try:
        record = await save_ergun_result(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            media_type=req.media_type,
            area=req.area,
            cycle_time=req.cycle_time,
            pressure_drop=req.pressure_drop,
            permeability_k=req.permeability_k,
            porosity_eps=req.porosity_eps,
            filter_velocity=req.filter_velocity,
            created_by=actor_id,
        )
    except FiltrationPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return ErgunCalcResponse(
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        tag_number=record.tag_number,
        media_type=record.media_type,
        area=record.area,
        cycle_time=record.cycle_time,
        pressure_drop=record.pressure_drop,
        cake_resistance_alpha=record.cake_resistance_alpha,
        specific_resistance_r0=record.specific_resistance_r0,
        permeability_k=record.permeability_k,
        porosity_eps=record.porosity_eps,
        filter_velocity=record.filter_velocity,
        result_id=record.filter_id,
        record_hash=record.record_hash,
        sign_status=record.sign_status.value,
        created_at=record.created_at,
    )


# ============================================================================
# 5 CRUD endpoints（/filtration/results）
# ============================================================================


@router.post(
    "/results", response_model=FiltrationResultResponse, status_code=201
)
async def create_filtration_result(
    req: FiltrationCreateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FiltrationResultResponse:
    """直接创建 FiltrationResult 行（POST → 201，不走 calc）。

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
    payload = req.model_dump(
        exclude={"project_id", "workspace_id", "tag_number"}
    )
    actor_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    try:
        record = await create_filtration_result_direct(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            created_by=actor_id,
            **payload,
        )
    except FiltrationPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return FiltrationResultResponse.model_validate(record, from_attributes=True)


@router.get("/results", response_model=FiltrationListResponse)
async def list_filtration_results(
    project_id: Annotated[uuid.UUID, Query(...)],
    include_obsolete: Annotated[bool, Query()] = False,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> FiltrationListResponse:
    """按 project_id 列出 FiltrationResult（GET list，分页）。

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
    records = await list_filtration_results_service(
        db,
        project_id=project_id,
        include_obsolete=include_obsolete,
        skip=skip,
        limit=limit,
    )
    items = [
        FiltrationResultResponse.model_validate(r, from_attributes=True)
        for r in records
    ]
    return FiltrationListResponse(
        items=items, total=len(items), skip=skip, limit=limit
    )


@router.get(
    "/results/{result_id}", response_model=FiltrationResultResponse
)
async def get_filtration_result(
    result_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FiltrationResultResponse:
    """按 filter_id 取 FiltrationResult（GET detail）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    try:
        record = await get_filtration_result_service(
            db, result_id=result_id
        )
    except FiltrationPersistInputError as e:
        if e.code == "FILTRATION_NOT_FOUND":
            raise HTTPException(
                status_code=404, detail="FiltrationResult not found"
            ) from e
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e
    # BLOCKER-3 P7-7+: record 级守卫 (SYSADMIN bypass)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=record.project_id,
        actor_roles=actor_roles_list,
    )

    return FiltrationResultResponse.model_validate(record, from_attributes=True)


@router.patch(
    "/results/{result_id}", response_model=FiltrationResultResponse
)
async def update_filtration_result(
    result_id: uuid.UUID,
    req: FiltrationUpdateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FiltrationResultResponse:
    """更新 FiltrationResult 业务字段（PATCH）。

    仅 DRAFT / CHANGE_PENDING 可改；CHECKED 等锁定态拒绝。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    patch = req.model_dump(exclude_unset=True)
    try:
        record = await update_filtration_result_service(
            db, result_id=result_id, patch=patch
        )
    except FiltrationPersistInputError as e:
        if e.code == "FILTRATION_NOT_FOUND":
            raise HTTPException(
                status_code=404, detail="FiltrationResult not found"
            ) from e
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e
    # BLOCKER-3 P7-7+: record 级守卫 (SYSADMIN bypass)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=record.project_id,
        actor_roles=actor_roles_list,
    )

    return FiltrationResultResponse.model_validate(record, from_attributes=True)


@router.delete(
    "/results/{result_id}", response_model=FiltrationDeleteResponse
)
async def soft_delete_filtration_result(
    result_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FiltrationDeleteResponse:
    """软删除 FiltrationResult（DELETE → sign_status=OBSOLETE）。

    位号加 ``__OBSOLETE_<ts>`` 后缀，stale_resolution_path 标记。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = (
        [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
    )
    try:
        record = await soft_delete_filtration_result_service(
            db, result_id=result_id
        )
    except FiltrationPersistInputError as e:
        if e.code == "FILTRATION_NOT_FOUND":
            raise HTTPException(
                status_code=404, detail="FiltrationResult not found"
            ) from e
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e
    # BLOCKER-3 P7-7+: record 级守卫 (SYSADMIN bypass)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=record.project_id,
        actor_roles=actor_roles_list,
    )

    return FiltrationDeleteResponse(
        result_id=record.filter_id,
        tag_number=record.tag_number,
        sign_status=record.sign_status.value,
        deleted_at=record.updated_at,
    )


__all__ = ["router"]