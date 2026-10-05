"""S1-5b UTIL API endpoints。

Per R5 ruling 补 API 层；与 summary_service (S1-5) + persist_service (S1-5b) 协同：

端点（6）：
- GET    /api/v1/util/results             → list UtilResults（按 project/workspace 过滤）
- GET    /api/v1/util/results/{id}        → 单条 UtilResults
- POST   /api/v1/util/results             → 手动 create UtilResults
- POST   /api/v1/util/aggregate           → 触发 source_aggregator + INSERT
- GET    /api/v1/util/summary             → 13 类 + 折标煤（最新一条）
- GET    /api/v1/util/energy-consumption  → 仅能源 5 类 + TOE
- GET    /api/v1/util/water-balance       → 仅水 3 类

ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.util import UtilityGasMedia, UtilityLowTempHeat
from app.schemas.util import (
    UtilAggregationRequest,
    UtilEnergyConsumptionResponse,
    UtilEnergySummaryAggregateRequest,
    UtilEnergySummaryResponse,
    UtilFuelGasCreateRequest,
    UtilFuelGasResponse,
    UtilGasMediaCreateRequest,
    UtilGasMediaResponse,
    UtilHeatExchangeCreateRequest,
    UtilHeatExchangeResponse,
    UtilLowTempHeatCreateRequest,
    UtilLowTempHeatResponse,
    UtilPowerItemCreateRequest,
    UtilPowerItemResponse,
    UtilResultsCreateRequest,
    UtilResultsResponse,
    UtilSummaryResponse,
    UtilWaterBalanceResponse,
)
from app.services.util import persist_service, summary_service
from app.services.util.category_map import (
    UtilityCategory,
    utility_categories,
)

router = APIRouter(prefix="/util", tags=["util"])


def _to_response(record) -> UtilResultsResponse:
    """ORM → Pydantic response mapper。"""
    return UtilResultsResponse(
        util_result_id=record.util_result_id,
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        business_date=record.business_date,
        consumption_json=record.consumption_json,
        jsonb_deprecated=record.jsonb_deprecated,
        source=record.source,
        # F-P1-007: 4 新聚合列透传 (NULL 时不返回)
        annual_total_energy=record.annual_total_energy,
        total_toe=record.total_toe,
        total_standard_coal_kg=record.total_standard_coal_kg,
        tolerance_status=record.tolerance_status,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


@router.get("/results", response_model=list[UtilResultsResponse])
async def list_util_results(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
    project_id: uuid.UUID | None = Query(None),
    workspace_id: uuid.UUID | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> list[UtilResultsResponse]:
    """按过滤条件分页查询 UtilResults。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = list(user.roles)
    if project_id is not None:
        await check_project_access_or_404(
            db, user_id=user.user_id, project_id=project_id,
            actor_roles=actor_roles_list,
        )
    rows, _total = await persist_service.list_util_results(
        db,
        project_id=project_id,
        workspace_id=workspace_id,
        limit=limit,
        offset=offset,
    )
    return [_to_response(r) for r in rows]


@router.get("/results/{util_result_id}", response_model=UtilResultsResponse)
async def get_util_result(
    util_result_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> UtilResultsResponse:
    """单条 UtilResults 查询。

    BLOCKER-3 修复: 查 UserProject 行 (user_id=user.user_id, project_id=record.project_id,
    revoked_at IS NULL) → 404 防 IDOR。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = list(user.roles)
    record = await persist_service.get_util_result(db, util_result_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"UtilResults not found: {util_result_id}"
        )
    # BLOCKER-3 P7-7+: record 级守卫 (SYSTEM_ADMIN bypass)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=record.project_id,
        actor_roles=actor_roles_list,
    )
    return _to_response(record)


@router.post(
    "/results",
    response_model=UtilResultsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_util_results(
    body: UtilResultsCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> UtilResultsResponse:
    """手动 create UtilResults（带 consumption_json）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=body.project_id,
        actor_roles=actor_roles_list,
    )
    record = await persist_service.save_util_results(
        db,
        project_id=body.project_id,
        workspace_id=body.workspace_id,
        consumption_json=body.consumption_json,
        business_date=body.business_date,
        source=body.source,
    )
    return _to_response(record)


@router.post(
    "/aggregate",
    response_model=UtilResultsResponse,
    status_code=status.HTTP_201_CREATED,
)
async def aggregate_util_results(
    body: UtilAggregationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> UtilResultsResponse:
    """触发 source_aggregator + INSERT UtilResults（一体化）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=body.project_id,
        actor_roles=actor_roles_list,
    )
    record = await persist_service.aggregate_and_save(
        db,
        project_id=body.project_id,
        workspace_id=body.workspace_id,
        modules=body.modules,
        business_date=body.business_date,
        source=body.source or "source_aggregator",
    )
    return _to_response(record)


@router.get("/summary", response_model=UtilSummaryResponse)
async def get_util_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
    util_result_id: uuid.UUID | None = Query(
        None, description="指定 UtilResults ID；缺省 = 最新一条"
    ),
    year: int = Query(2026, ge=2020, le=2100, description="折标煤查询年份"),
) -> UtilSummaryResponse:
    """13 类聚合 + 折标煤（来自 summary_service.summarize）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = list(user.roles)
    if util_result_id is not None:
        record = await persist_service.get_util_result(db, util_result_id)
        if record is None:
            raise HTTPException(
                status_code=404, detail=f"UtilResults not found: {util_result_id}"
            )
    else:
        # 默认最新一条（按 util_result_id DESC）
        rows, _ = await persist_service.list_util_results(
            db, limit=1, offset=0
        )
        if not rows:
            raise HTTPException(
                status_code=404, detail="No UtilResults available for summary"
            )
        record = rows[0]
    # BLOCKER-3 P7-7+: record 级守卫 (SYSTEM_ADMIN bypass)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=record.project_id,
        actor_roles=actor_roles_list,
    )
    summary = await summary_service.summarize(record, db=db, year=year)
    return UtilSummaryResponse(
        by_category=summary["by_category"],
        toe_total=summary["toe_total"],
        standard_coal_total=summary["standard_coal_total"],
        jsonb_deprecated=summary["jsonb_deprecated"],
        year=summary["year"],
    )


@router.get("/energy-consumption", response_model=UtilEnergyConsumptionResponse)
async def get_util_energy_consumption(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
    util_result_id: uuid.UUID | None = Query(None),
    year: int = Query(2026, ge=2020, le=2100),
) -> UtilEnergyConsumptionResponse:
    """仅能源 5 类 + TOE（filter 6 能源 from summary）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = list(user.roles)
    if util_result_id is not None:
        record = await persist_service.get_util_result(db, util_result_id)
        if record is None:
            raise HTTPException(status_code=404, detail="UtilResults not found")
    else:
        rows, _ = await persist_service.list_util_results(db, limit=1, offset=0)
        if not rows:
            raise HTTPException(status_code=404, detail="No UtilResults")
        record = rows[0]
    # BLOCKER-3 P7-7+: record 级守卫 (SYSTEM_ADMIN bypass)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=record.project_id,
        actor_roles=actor_roles_list,
    )
    summary = await summary_service.summarize(record, db=db, year=year)

    # 6 能源类（filter from 13）— 与 toe_total 计算口径一致 (F-P1-015 fix)
    energy_keys = {
        UtilityCategory.ELECTRICITY.value,
        UtilityCategory.STEAM_HP.value,
        UtilityCategory.STEAM_MP.value,
        UtilityCategory.STEAM_LP.value,
        UtilityCategory.FUEL_GAS.value,
        UtilityCategory.CONDENSATE.value,  # 冷凝水按 STEAM 折标
    }
    by_category = {k: v for k, v in summary["by_category"].items() if k in energy_keys}
    return UtilEnergyConsumptionResponse(
        by_category=by_category,
        toe_total=summary["toe_total"],
        standard_coal_total=summary["standard_coal_total"],
        year=summary["year"],
    )


@router.get("/water-balance", response_model=UtilWaterBalanceResponse)
async def get_util_water_balance(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
    util_result_id: uuid.UUID | None = Query(None),
) -> UtilWaterBalanceResponse:
    """仅水 3 类（COOLING_WATER + CHILLED_WATER + MAKEUP_WATER）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    actor_roles_list = list(user.roles)
    if util_result_id is not None:
        record = await persist_service.get_util_result(db, util_result_id)
        if record is None:
            raise HTTPException(status_code=404, detail="UtilResults not found")
    else:
        rows, _ = await persist_service.list_util_results(db, limit=1, offset=0)
        if not rows:
            raise HTTPException(status_code=404, detail="No UtilResults")
        record = rows[0]
    # BLOCKER-3 P7-7+: record 级守卫 (SYSTEM_ADMIN bypass)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=record.project_id,
        actor_roles=actor_roles_list,
    )

    water_keys = {
        UtilityCategory.COOLING_WATER.value,
        UtilityCategory.CHILLED_WATER.value,
        UtilityCategory.MAKEUP_WATER.value,
    }
    by_category = {k: record.consumption_json.get(k, 0.0) for k in water_keys}
    total_water = sum(by_category.values())
    return UtilWaterBalanceResponse(
        by_category=by_category,
        total_water_t=total_water,
        year=2026,  # water 无 TOE 年份依赖
    )


# ============================================================================
# P7 Sprint 2 T1-T5 API 端点 (UTIL 5 表 + 综合能耗汇总)
# ============================================================================
# ACL: DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
# ============================================================================


def _power_item_to_response(record) -> UtilPowerItemResponse:
    return UtilPowerItemResponse(
        id=record.id,
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        equipment_id=record.equipment_id,
        equipment_tag=record.equipment_tag,
        motor_power_kw=record.motor_power_kw,
        operating_hours_per_year=record.operating_hours_per_year,
        load_factor=record.load_factor,
        annual_consumption_kwh=record.annual_consumption_kwh,
        source=record.source,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


def _fuel_gas_to_response(record) -> UtilFuelGasResponse:
    return UtilFuelGasResponse(
        id=record.id,
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        equipment_id=record.equipment_id,
        equipment_tag=record.equipment_tag,
        fuel_type=record.fuel_type,
        calorific_value_kcal_nm3=record.calorific_value_kcal_nm3,
        consumption_nm3_h=record.consumption_nm3_h,
        operating_phase=record.operating_phase,
        operating_hours_per_year=record.operating_hours_per_year,
        annual_consumption_nm3=record.annual_consumption_nm3,
        source=record.source,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


def _heat_exchange_to_response(record) -> UtilHeatExchangeResponse:
    return UtilHeatExchangeResponse(
        id=record.id,
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        equipment_id=record.equipment_id,
        equipment_tag=record.equipment_tag,
        steam_pressure_mpa_gauge=record.steam_pressure_mpa_gauge,
        steam_quality_pct=record.steam_quality_pct,
        return_condensate_pct=record.return_condensate_pct,
        temperature_class=record.temperature_class,
        # R1 §7.1 + §7.2 (P7-6B): 同步 medium_type + pressure_level 给前端
        pressure_level=record.pressure_level,
        medium_type=record.medium_type,
        steam_consumption_t_h=record.steam_consumption_t_h,
        operating_hours_per_year=record.operating_hours_per_year,
        annual_consumption_t=record.annual_consumption_t,
        source=record.source,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


def _energy_summary_to_response(record) -> UtilEnergySummaryResponse:
    return UtilEnergySummaryResponse(
        id=record.id,
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        business_year=record.business_year,
        source=record.source,
        electricity_kwh_yr=record.electricity_kwh_yr,
        fuel_gas_nm3_yr=record.fuel_gas_nm3_yr,
        steam_t_yr=record.steam_t_yr,
        water_t_yr=record.water_t_yr,
        gas_nm3_yr=record.gas_nm3_yr,
        low_temp_heat_gj_yr=record.low_temp_heat_gj_yr,
        annual_total_energy=record.annual_total_energy,
        toe_conversion_factor=record.toe_conversion_factor,
        standard_coal_factor=record.standard_coal_factor,
        total_toe=record.total_toe,
        total_standard_coal_kg=record.total_standard_coal_kg,
        tolerance_pct=record.tolerance_pct,
        tolerance_status=record.tolerance_status,
        computed_at=record.computed_at.isoformat() if record.computed_at else None,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


def _derive_annual_consumption_kw(
    motor_power_kw: float,
    operating_hours: float,
    load_factor: float,
) -> float:
    """T1 年用电量派生 (缺省值; 服务层公式)."""
    return motor_power_kw * operating_hours * load_factor


def _derive_annual_consumption_nm3(
    consumption_nm3_h: float,
    operating_hours: float,
) -> float:
    """T2 年燃料气消耗派生."""
    return consumption_nm3_h * operating_hours


def _derive_annual_consumption_t(
    steam_t_h: float,
    operating_hours: float,
) -> float:
    """T3 年蒸汽消耗派生."""
    return steam_t_h * operating_hours


# ----------------------------------------------------------------------------
# T1 utility_power_items
# ----------------------------------------------------------------------------


@router.post(
    "/power-items",
    response_model=UtilPowerItemResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_power_item(
    body: UtilPowerItemCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> UtilPowerItemResponse:
    """T1 手动创建电耗设备清单条目 (annual_consumption_kwh 缺省=派生)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=body.project_id,
        actor_roles=actor_roles_list,
    )
    from app.models.util import UtilityPowerItem

    annual_kwh = body.annual_consumption_kwh
    if annual_kwh is None:
        annual_kwh = _derive_annual_consumption_kw(
            body.motor_power_kw, body.operating_hours_per_year, body.load_factor
        )

    record = UtilityPowerItem(
        project_id=body.project_id,
        workspace_id=body.workspace_id,
        equipment_tag=body.equipment_tag,
        motor_power_kw=body.motor_power_kw,
        operating_hours_per_year=body.operating_hours_per_year,
        load_factor=body.load_factor,
        annual_consumption_kwh=annual_kwh,
        source=body.source or "MANUAL",
    )
    await _commit_or_conflict(db, record)
    return _power_item_to_response(record)


@router.get("/power-items", response_model=list[UtilPowerItemResponse])
async def list_power_items(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
    project_id: uuid.UUID = Query(..., description="项目 UUID"),
) -> list[UtilPowerItemResponse]:
    """T1 列出某项目下所有电耗设备清单 (按 equipment_tag 升序)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=actor_roles_list,
    )
    from sqlalchemy import select

    from app.models.util import UtilityPowerItem

    stmt = (
        select(UtilityPowerItem)
        .where(UtilityPowerItem.project_id == project_id)
        .order_by(UtilityPowerItem.equipment_tag)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [_power_item_to_response(r) for r in rows]


# ----------------------------------------------------------------------------
# T2 utility_fuel_gas
# ----------------------------------------------------------------------------


@router.post(
    "/fuel-gas-items",
    response_model=UtilFuelGasResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_fuel_gas(
    body: UtilFuelGasCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> UtilFuelGasResponse:
    """T2 手动创建燃料气消耗条目 (annual_consumption_nm3 缺省=派生)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=body.project_id,
        actor_roles=actor_roles_list,
    )
    from app.models.util import UtilityFuelGas

    annual_nm3 = body.annual_consumption_nm3
    if annual_nm3 is None:
        annual_nm3 = _derive_annual_consumption_nm3(
            body.consumption_nm3_h, body.operating_hours_per_year
        )

    record = UtilityFuelGas(
        project_id=body.project_id,
        workspace_id=body.workspace_id,
        equipment_tag=body.equipment_tag,
        fuel_type=body.fuel_type,
        calorific_value_kcal_nm3=body.calorific_value_kcal_nm3,
        consumption_nm3_h=body.consumption_nm3_h,
        operating_phase=body.operating_phase,
        operating_hours_per_year=body.operating_hours_per_year,
        annual_consumption_nm3=annual_nm3,
        source=body.source or "MANUAL",
    )
    await _commit_or_conflict(db, record)
    return _fuel_gas_to_response(record)


@router.get("/fuel-gas-items", response_model=list[UtilFuelGasResponse])
async def list_fuel_gas(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
    project_id: uuid.UUID = Query(..., description="项目 UUID"),
) -> list[UtilFuelGasResponse]:
    """T2 列出某项目下所有燃料气消耗条目 (按 equipment_tag + phase 升序)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=actor_roles_list,
    )
    from sqlalchemy import select

    from app.models.util import UtilityFuelGas

    stmt = (
        select(UtilityFuelGas)
        .where(UtilityFuelGas.project_id == project_id)
        .order_by(UtilityFuelGas.equipment_tag, UtilityFuelGas.operating_phase)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [_fuel_gas_to_response(r) for r in rows]


# ----------------------------------------------------------------------------
# T3 utility_heat_exchange
# ----------------------------------------------------------------------------


@router.post(
    "/heat-exchange-items",
    response_model=UtilHeatExchangeResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_heat_exchange(
    body: UtilHeatExchangeCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> UtilHeatExchangeResponse:
    """T3 手动创建蒸汽/冷凝水条目 (annual_consumption_t 缺省=派生)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=body.project_id,
        actor_roles=actor_roles_list,
    )
    from app.models.util import UtilityHeatExchange

    # F-P1-001 fix: reject client annual_consumption_t override unless plausible
    # 派生值 (steam_consumption_t_h × operating_hours_per_year) 是唯一权威来源;
    # client override 仅在 ≤ ±0.5% 误差内接受, 否则 PcsError 422 防 silent data drift
    derived_t = _derive_annual_consumption_t(
        body.steam_consumption_t_h, body.operating_hours_per_year
    )
    annual_t = body.annual_consumption_t
    if annual_t is not None:
        delta_pct = abs(annual_t - derived_t) / derived_t * 100.0 if derived_t > 0 else 0.0
        if delta_pct > 0.5:
            from app.services.exceptions import PcsError
            raise PcsError(
                code="ANNUAL_CONSUMPTION_OVERRIDE_REJECTED",
                message=(
                    f"annual_consumption_t override {annual_t} 与派生 {derived_t} "
                    f"偏差 {delta_pct:.3f}% > 0.5% 阈值; 请保持一致或留空让 service 派生"
                ),
                status=422,
            )

    record = UtilityHeatExchange(
        project_id=body.project_id,
        workspace_id=body.workspace_id,
        equipment_tag=body.equipment_tag,
        steam_pressure_mpa_gauge=body.steam_pressure_mpa_gauge,
        steam_quality_pct=body.steam_quality_pct,
        return_condensate_pct=body.return_condensate_pct,
        temperature_class=body.temperature_class,
        steam_consumption_t_h=body.steam_consumption_t_h,
        operating_hours_per_year=body.operating_hours_per_year,
        annual_consumption_t=annual_t if annual_t is not None else derived_t,
        source=body.source or "MANUAL",
    )
    await _commit_or_conflict(db, record)
    return _heat_exchange_to_response(record)


@router.get("/heat-exchange-items", response_model=list[UtilHeatExchangeResponse])
async def list_heat_exchange(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
    project_id: uuid.UUID = Query(..., description="项目 UUID"),
) -> list[UtilHeatExchangeResponse]:
    """T3 列出某项目下所有蒸汽/冷凝水条目 (按 equipment_tag 升序)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=actor_roles_list,
    )
    from sqlalchemy import select

    from app.models.util import UtilityHeatExchange

    stmt = (
        select(UtilityHeatExchange)
        .where(UtilityHeatExchange.project_id == project_id)
        .order_by(UtilityHeatExchange.equipment_tag)
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [_heat_exchange_to_response(r) for r in rows]


# ----------------------------------------------------------------------------
# T5 utility_energy_summary 聚合
# ----------------------------------------------------------------------------


@router.post(
    "/energy-summary/aggregate",
    response_model=UtilEnergySummaryResponse,
    status_code=status.HTTP_201_CREATED,
)
async def aggregate_energy_summary(
    body: UtilEnergySummaryAggregateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> UtilEnergySummaryResponse:
    """T5 触发综合能耗汇总 (聚合 T1+T2+T3 + 折标系数 CONFIG)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=body.project_id,
        actor_roles=actor_roles_list,
    )
    # F-P2-006: 滑动窗口 rate limit — 防 DOS via 重复点击
    # 5/min/user — 单实例够用, 多实例部署需换 Redis (TODO)
    from fastapi import HTTPException

    from app.services._sliding_window_rate_limit import check_rate_limit

    rate_key = f"energy_summary_aggregate:{user.user_id}"
    if not await check_rate_limit(rate_key, limit=5, window_seconds=60.0):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="aggregate 请求过于频繁，请稍后再试 (limit 5/min/user)",
        )

    from app.services.util.utility_energy_summary_service import (
        summarize_energy_year,
    )

    summary = await summarize_energy_year(
        db=db,
        project_id=body.project_id,
        workspace_id=body.workspace_id,
        business_year=body.business_year,
        source=body.source,  # F-P2-007: 透传 source (CALCULATION / XLS_REFERENCE)
        # 省略时由 service 按项目产品类别强制推导 (GB 30251-2024 §6.1.5);
        # 显式传值与产品类别冲突 → service 抛 422 ELECTRICITY_VALUE_TYPE_MISMATCH
        electricity_value_type=body.electricity_value_type,
    )
    return _energy_summary_to_response(summary)


@router.get(
    "/energy-summary", response_model=list[UtilEnergySummaryResponse]
)
async def list_energy_summary(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
    project_id: uuid.UUID = Query(..., description="项目 UUID"),
    business_year: int | None = Query(
        None, ge=2020, le=2100, description="业务年度过滤 (None=全部)"
    ),
) -> list[UtilEnergySummaryResponse]:
    """T5 列出某项目综合能耗汇总 (按 business_year 升序)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫 (SYSTEM_ADMIN bypass)
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=actor_roles_list,
    )
    from sqlalchemy import select

    from app.models.util import UtilityEnergySummary

    stmt = select(UtilityEnergySummary).where(
        UtilityEnergySummary.project_id == project_id
    )
    if business_year is not None:
        stmt = stmt.where(UtilityEnergySummary.business_year == business_year)
    stmt = stmt.order_by(
        UtilityEnergySummary.business_year, UtilityEnergySummary.source
    )
    result = await db.execute(stmt)
    rows = result.scalars().all()
    return [_energy_summary_to_response(r) for r in rows]


# ===========================================================================
# P7-6B 收尾: 工艺气体 / 低温热 CRUD
#
# 这两类此前无子表 (service 里 gas_nm3_yr / low_temp_heat_gj_yr 硬编码 None),
# 而 CONFIG 系数 (GB 30251-2024 附录A 序号31/32/33/34) 一直存在却无代码读取。
# 介质 → CONFIG 行映射见 app/models/enums.py::GasMedium。
# 沿用既有子表端点约定: ACL DESIGNER/PROCESS_CONTROLLER/SYSTEM_ADMIN +
# check_project_access_or_404 (BLOCKER-3 P7-7+) + annual 缺省服务端派生。
# ===========================================================================


async def _commit_or_conflict(db, record) -> None:
    """提交记录; UNIQUE 冲突转 409 (不冒泡成 500).

    覆盖全部 5 个子表 POST 端点 (power-items / fuel-gas-items /
    heat-exchange-items / gas-media-items / low-temp-heat-items)。
    修正前 3 个既有端点直接 `db.add(); commit()`, 重复 POST 会让
    IntegrityError 冒泡成 500 而非结构化 409。
    """
    from sqlalchemy.exc import IntegrityError

    db.add(record)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"记录冲突 (UNIQUE 约束): "
                f"{getattr(record, 'equipment_tag', '?')}. 请检查 "
                "project_id + equipment_tag + 判别列 是否重复"
            ),
        ) from exc
    await db.refresh(record)


def _gas_media_to_response(record) -> UtilGasMediaResponse:
    return UtilGasMediaResponse(
        id=record.id,
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        equipment_id=record.equipment_id,
        equipment_tag=record.equipment_tag,
        gas_medium=record.gas_medium,
        consumption_nm3_h=record.consumption_nm3_h,
        operating_hours_per_year=record.operating_hours_per_year,
        annual_consumption_nm3=record.annual_consumption_nm3,
        source=record.source,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


def _low_temp_heat_to_response(record) -> UtilLowTempHeatResponse:
    return UtilLowTempHeatResponse(
        id=record.id,
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        equipment_id=record.equipment_id,
        equipment_tag=record.equipment_tag,
        heat_recovery_gj_h=record.heat_recovery_gj_h,
        operating_hours_per_year=record.operating_hours_per_year,
        annual_recovered_heat_gj=record.annual_recovered_heat_gj,
        source=record.source,
        created_at=record.created_at.isoformat() if record.created_at else None,
        updated_at=record.updated_at.isoformat() if record.updated_at else None,
    )


@router.get("/gas-media-items", response_model=list[UtilGasMediaResponse])
async def list_gas_media_items(
    project_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    gas_medium: str | None = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Annotated[AsyncSession, Depends(get_db)] = None,  # type: ignore[assignment]
    user: Annotated[_Actor, Depends(current_actor)] = None,  # type: ignore[assignment]
) -> list[UtilGasMediaResponse]:
    """列 project's 工艺气体条目 (可选按 workspace / 介质过滤)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=list(user.roles),
    )
    stmt = select(UtilityGasMedia).where(UtilityGasMedia.project_id == project_id)
    if workspace_id is not None:
        stmt = stmt.where(UtilityGasMedia.workspace_id == workspace_id)
    if gas_medium is not None:
        stmt = stmt.where(UtilityGasMedia.gas_medium == gas_medium)
    rows = (
        await db.execute(
            stmt.order_by(UtilityGasMedia.equipment_tag).limit(limit).offset(offset)
        )
    ).scalars().all()
    return [_gas_media_to_response(r) for r in rows]


@router.post(
    "/gas-media-items",
    response_model=UtilGasMediaResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_gas_media_item(
    body: UtilGasMediaCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> UtilGasMediaResponse:
    """创建工艺气体条目 (annual_consumption_nm3 缺省=派生)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=body.project_id,
        actor_roles=list(user.roles),
    )
    annual = body.annual_consumption_nm3
    if annual is None:
        annual = body.consumption_nm3_h * body.operating_hours_per_year
    record = UtilityGasMedia(
        project_id=body.project_id,
        workspace_id=body.workspace_id,
        equipment_id=body.equipment_id,
        equipment_tag=body.equipment_tag,
        gas_medium=body.gas_medium.value,
        consumption_nm3_h=body.consumption_nm3_h,
        operating_hours_per_year=body.operating_hours_per_year,
        annual_consumption_nm3=annual,
        source=body.source or "MANUAL",
    )
    await _commit_or_conflict(db, record)
    return _gas_media_to_response(record)


@router.get("/low-temp-heat-items", response_model=list[UtilLowTempHeatResponse])
async def list_low_temp_heat_items(
    project_id: uuid.UUID,
    workspace_id: uuid.UUID | None = None,
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: Annotated[AsyncSession, Depends(get_db)] = None,  # type: ignore[assignment]
    user: Annotated[_Actor, Depends(current_actor)] = None,  # type: ignore[assignment]
) -> list[UtilLowTempHeatResponse]:
    """列 project's 低温余热回收条目."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=list(user.roles),
    )
    stmt = select(UtilityLowTempHeat).where(
        UtilityLowTempHeat.project_id == project_id
    )
    if workspace_id is not None:
        stmt = stmt.where(UtilityLowTempHeat.workspace_id == workspace_id)
    rows = (
        await db.execute(
            stmt.order_by(UtilityLowTempHeat.equipment_tag)
            .limit(limit).offset(offset)
        )
    ).scalars().all()
    return [_low_temp_heat_to_response(r) for r in rows]


@router.post(
    "/low-temp-heat-items",
    response_model=UtilLowTempHeatResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_low_temp_heat_item(
    body: UtilLowTempHeatCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[_Actor, Depends(current_actor)],
) -> UtilLowTempHeatResponse:
    """创建低温余热回收条目 (annual_recovered_heat_gj 缺省=派生)."""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=body.project_id,
        actor_roles=list(user.roles),
    )
    annual = body.annual_recovered_heat_gj
    if annual is None:
        annual = body.heat_recovery_gj_h * body.operating_hours_per_year
    record = UtilityLowTempHeat(
        project_id=body.project_id,
        workspace_id=body.workspace_id,
        equipment_id=body.equipment_id,
        equipment_tag=body.equipment_tag,
        heat_recovery_gj_h=body.heat_recovery_gj_h,
        operating_hours_per_year=body.operating_hours_per_year,
        annual_recovered_heat_gj=annual,
        source=body.source or "MANUAL",
    )
    await _commit_or_conflict(db, record)
    return _low_temp_heat_to_response(record)
