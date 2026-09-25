"""P6-2 COOL_TOWER API：Task 25 heat-load-aggregator + fan-power +
water-balance + cool_tower_persist CRUD 端点。

端点：
- POST /api/v1/cool-tower/heat-load-aggregator
    body: HeatLoadAggregatorRequest
    response: HeatLoadAggregatorResponse（§3.2.4.5）
- POST /api/v1/cool-tower/fan-power
    body: FanPowerRequest
    response: FanPowerResponse（§3.2.4.6）
- POST /api/v1/cool-tower/water-balance
    body: WaterBalanceRequest
    response: WaterBalanceResponse（§3.2.4.4 + §3.2.4.7）
- POST   /api/v1/cool-tower/results        创建 CoolingTowerResult（201）
- GET    /api/v1/cool-tower/results        列出（分页，DRAFT/CHECKED filter）
- GET    /api/v1/cool-tower/results/{id}   详情
- PATCH  /api/v1/cool-tower/results/{id}   更新（仅 DRAFT/CHANGE_PENDING 可改）
- DELETE /api/v1/cool-tower/results/{id}   软删除（→ OBSOLETE）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
- 业务异常 → 走 core.errors.PcsError envelope
- 计算端点（heat-load-aggregator / fan-power / water-balance）不写 DB；
  落库统一由 cool_tower_persist endpoints 处理（Task 25
  SPEC §3.2.3 P6-FLR-004 镜像）
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.models.enums import RecordSignStatus9
from app.schemas.cool_tower import (
    CoolTowerResultCreateRequest,
    CoolTowerResultListResponse,
    CoolTowerResultResponse,
    CoolTowerResultUpdateRequest,
    FanPowerRequest,
    FanPowerResponse,
    HeatLoadAggregatorRequest,
    HeatLoadAggregatorResponse,
    WaterBalanceRequest,
    WaterBalanceResponse,
)
from app.services.cool_tower.cool_tower_persist_service import (  # P6-2 Task 25
    CoolTowerPersistInputError,
    save_cool_tower_result,
)
from app.services.cool_tower.cool_tower_persist_service import (
    get_cool_tower_result as get_cool_tower_result_service,
)
from app.services.cool_tower.cool_tower_persist_service import (
    list_cool_tower_results as list_cool_tower_results_service,
)
from app.services.cool_tower.cool_tower_persist_service import (
    soft_delete_cool_tower_result as soft_delete_cool_tower_result_service,
)
from app.services.cool_tower.cool_tower_persist_service import (
    update_cool_tower_result as update_cool_tower_result_service,
)
from app.services.cool_tower.fan_power import (  # P6-2 Task 25
    FanPowerInput,
    calc_fan_power,
)
from app.services.cool_tower.heat_aggregator import (  # P6-2 Task 25
    HeatAggregatorInput,
    aggregate_heat_duty,
)
from app.services.cool_tower.water_balance import (  # P6-2 Task 24
    WaterBalanceInput,
    calc_water_balance,
)
from app.services.exceptions import PcsError

router = APIRouter(prefix="/cool-tower", tags=["cool-tower"])


def _to_http(err: PcsError) -> CorePcsError:
    """service 层 PcsError → FastAPI HTTPException envelope。

    注：P6-OPEN-010 fix — CorePcsError 使用 ``status`` kwarg（非
    ``status_code``，避免与 HTTPException 混淆）。
    """
    return CorePcsError(
        code=err.code, message=str(err), status=err.status
    )


# ───────────────────────────── heat-load-aggregator ─────────────────


@router.post("/heat-load-aggregator", response_model=HeatLoadAggregatorResponse)
async def aggregate_heat_load(
    req: HeatLoadAggregatorRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> HeatLoadAggregatorResponse:
    """HEAT 汇总（§3.2.4.5）：按 project_id + exchanger_category 汇总 duty kW。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        # 字符串 sign_status → enum（非法字面 → 422 PcsError envelope）
        sign_status_filter = tuple(
            RecordSignStatus9(s) for s in (
                req.sign_status_filter or ["DRAFT", "CHECKED"]
            )
        )
        exchanger_categories = tuple(
            req.exchanger_categories_filter or ["SHELL_TUBE", "PLATE"]
        )
        result = await aggregate_heat_duty(
            HeatAggregatorInput(
                session=db,
                project_id=req.project_id,
                exchanger_categories_filter=exchanger_categories,
                sign_status_filter=sign_status_filter,
            )
        )
    except PcsError as e:
        raise _to_http(e) from e
    except ValueError as e:
        # enum 解析失败
        raise _to_http(
            CorePcsError(
                code="HEAT_AGGREGATOR_INPUT_ERROR",
                message=f"sign_status_filter 非法值: {e}",
                status=422,
            )
        ) from e

    return HeatLoadAggregatorResponse(
        h_aggregate_kw=result.h_aggregate_kw,
        heat_record_count=result.heat_record_count,
        per_exchanger_category=result.per_exchanger_category,
        formula_ref=result.formula_ref,
    )


# ───────────────────────────── fan-power ────────────────────────────


@router.post("/fan-power", response_model=FanPowerResponse)
async def calculate_fan_power(
    req: FanPowerRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FanPowerResponse:
    """风机功率（§3.2.4.6）：CTI 1492 经验值 P_fan = Q_air × Δp_total /
    (η_fan × η_motor × 1000)。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        result = calc_fan_power(
            FanPowerInput(
                q_air_m3_s=req.q_air_m3_s,
                delta_p_total_pa=req.delta_p_total_pa,
                fan_efficiency=req.fan_efficiency,
                motor_efficiency=req.motor_efficiency,
            )
        )
    except PcsError as e:
        raise _to_http(e) from e

    # 不写 DB（fan_power 是独立计算，落库由 Task 25 cool_tower_persist
    # 统一处理）
    del db  # 显式不使用 session（避免 pylint unused-argument）

    return FanPowerResponse(
        p_fan_kw=result.p_fan_kw,
        formula_ref=result.formula_ref,
    )


# ───────────────────────────── water-balance ─────────────────────────


@router.post("/water-balance", response_model=WaterBalanceResponse)
async def calculate_water_balance(
    req: WaterBalanceRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> WaterBalanceResponse:
    """补充水量（§3.2.4.4）：M = E + D + B（蒸发 + 风吹 + 排污）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        result = calc_water_balance(
            WaterBalanceInput(
                q_w_m3_s=req.q_w_m3_s,
                delta_t_k=req.delta_t_c,  # ΔT(K) ≈ ΔT(°C) 差值等价
                cp_w=req.c_water_kj_kg_k,
                h_vap=req.h_vap_kj_kg,
                cycle_ratio=req.cycle_ratio,
                drift_fraction=req.drift_fraction,
            )
        )
    except PcsError as e:
        raise _to_http(e) from e

    # 不写 DB（water_balance 是独立计算，落库由 Task 25 cool_tower_persist
    # 统一处理）
    del db

    return WaterBalanceResponse(
        evaporation_m3_s=result.evaporation_m3_s,
        drift_m3_s=result.drift_m3_s,
        blowdown_m3_s=result.blowdown_m3_s,
        makeup_m3_s=result.makeup_m3_s,
        formula_ref=result.formula_ref,
    )


# ───────────────────────────── cool_tower_persist CRUD ──────────────


@router.post("/results", response_model=CoolTowerResultResponse, status_code=201)
async def create_cool_tower_result(
    req: CoolTowerResultCreateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CoolTowerResultResponse:
    """创建 CoolingTowerResult 行（POST → 201）。

    ``save_cool_tower_result`` service 层自动 final record_hash
    （ADR-0028 §决策 4），返回创建后的完整 CoolingTowerResult 行。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # 字符串 sign_status → enum（非法字面 → 422 PcsError envelope）
    try:
        sign_status_enum = RecordSignStatus9(req.sign_status)
    except ValueError as e:
        raise _to_http(
            CorePcsError(
                code="COOL_TOWER_RESULT_SIGN_STATUS_INVALID",
                message=f"sign_status={req.sign_status!r} 非法：{e}",
                status=422,
            )
        ) from e
    # 业务 payload：排除溯源 / mixin 必填（已拆为 save_cool_tower_result
    # 显式 kwarg）
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
        record = await save_cool_tower_result(
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
    except CoolTowerPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return CoolTowerResultResponse.model_validate(record, from_attributes=True)


@router.get("/results", response_model=CoolTowerResultListResponse)
async def list_cool_tower_results(
    project_id: Annotated[uuid.UUID, Query(...)],
    standard_profile_code: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> CoolTowerResultListResponse:
    """按 project_id 列出 CoolingTowerResult（GET list，分页）。

    默认 sign_status filter = (DRAFT, CHECKED) — 排除 OBSOLETE 等门禁态。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    records = await list_cool_tower_results_service(
        db,
        project_id=project_id,
        standard_profile_code=standard_profile_code,
        limit=limit,
        offset=offset,
    )
    items = [
        CoolTowerResultResponse.model_validate(r, from_attributes=True)
        for r in records
    ]
    return CoolTowerResultListResponse(
        items=items, total=len(items), limit=limit, offset=offset
    )


@router.get("/results/{record_id}", response_model=CoolTowerResultResponse)
async def get_cool_tower_result(
    record_id: uuid.UUID,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> CoolTowerResultResponse:
    """按 id 取 CoolingTowerResult（GET detail）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    record = await get_cool_tower_result_service(db, record_id=record_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail="CoolingTowerResult not found"
        )
    return CoolTowerResultResponse.model_validate(record, from_attributes=True)


@router.patch("/results/{record_id}", response_model=CoolTowerResultResponse)
async def update_cool_tower_result(
    record_id: uuid.UUID,
    req: CoolTowerResultUpdateRequest,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> CoolTowerResultResponse:
    """更新 CoolingTowerResult 业务字段（PATCH；仅 DRAFT/CHANGE_PENDING 可改）。

    CHECKED / IN_APPROVAL / REVERSAL_PENDING 等锁定态拒绝更新（避免
    评审中数据漂移）。project_id 由 ACL 在 Phase 后续 PATCH 透传；本
    批次为 None（service 层不强制隔离）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    payload = req.model_dump(exclude_unset=True)
    try:
        record = await update_cool_tower_result_service(
            db,
            record_id=record_id,
            project_id=None,
            payload=payload,
        )
    except CoolTowerPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e
    if record is None:
        raise HTTPException(
            status_code=404, detail="CoolingTowerResult not found"
        )
    return CoolTowerResultResponse.model_validate(record, from_attributes=True)


@router.delete("/results/{record_id}", status_code=204)
async def delete_cool_tower_result(
    record_id: uuid.UUID,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> None:
    """软删除 CoolingTowerResult（DELETE → sign_status=OBSOLETE）。

    软删而非物理删除（SPEC §3.2.3 P6-FLR-004 审计要求）；记录不再被
    list 默认过滤（DRAFT/CHECKED filter）展示。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    ok = await soft_delete_cool_tower_result_service(
        db, record_id=record_id, project_id=None
    )
    if not ok:
        raise HTTPException(
            status_code=404, detail="CoolingTowerResult not found"
        )


__all__ = ["router"]