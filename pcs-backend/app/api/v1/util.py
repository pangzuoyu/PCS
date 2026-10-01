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
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.util import (
    UtilAggregationRequest,
    UtilEnergyConsumptionResponse,
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
    """单条 UtilResults 查询。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    record = await persist_service.get_util_result(db, util_result_id)
    if record is None:
        raise HTTPException(
            status_code=404, detail=f"UtilResults not found: {util_result_id}"
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
    if util_result_id is not None:
        record = await persist_service.get_util_result(db, util_result_id)
        if record is None:
            raise HTTPException(status_code=404, detail="UtilResults not found")
    else:
        rows, _ = await persist_service.list_util_results(db, limit=1, offset=0)
        if not rows:
            raise HTTPException(status_code=404, detail="No UtilResults")
        record = rows[0]
    summary = await summary_service.summarize(record, db=db, year=year)

    # 仅 5 能源类（filter from 13）
    energy_keys = {
        UtilityCategory.ELECTRICITY.value,
        UtilityCategory.STEAM_HP.value,
        UtilityCategory.STEAM_MP.value,
        UtilityCategory.STEAM_LP.value,
        UtilityCategory.FUEL_GAS.value,
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
    if util_result_id is not None:
        record = await persist_service.get_util_result(db, util_result_id)
        if record is None:
            raise HTTPException(status_code=404, detail="UtilResults not found")
    else:
        rows, _ = await persist_service.list_util_results(db, limit=1, offset=0)
        if not rows:
            raise HTTPException(status_code=404, detail="No UtilResults")
        record = rows[0]

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
