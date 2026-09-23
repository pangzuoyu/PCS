"""P6-1 Task 14 限制装置计算 API：POST /api/v1/restriction/calculate 端点契约。

按 PCS-PLAN-P6-BATCH.md §Task 14 + SPEC §3.2.2.1~4 + §3.2.2.6 + ADR-0022 V1.0：

端点：
- POST /api/v1/restriction/calculate
    body: RestrictionCalculateRequest（14 字段；SPEC §3.2.2.1~4）
    response: RestrictionCalculateResponse（orifice_id + outlet_stream_id）

设计要点：
- 业务异常 → Pydantic ValidationError（422 默认 envelope）；自定义 RestrictionService
  抛 ValueError → 转 422 envelope（RES_INVALID_INPUT）
- 复用 RestrictionService.persist_calculate（Task 13）：调 RestrictionEngine +
  落 restriction_results + record_hash + outlet stream（RESTRICTION_CALCULATED +
  ISOENTHALPIC；区别 CV FRICTION_PRESSURE_DROP）
- 不做 ACL / 工况守卫（RESTRICTION 是设备计算，不涉 DRAFT→CHECKED 锁）

不做：
- 不调 restriction_api 自身（restriction_persist 已直调 RestrictionEngine）
- 不写 record_hash 算法（service 层复用 calc_lineage.compute_record_hash）
- 不实现 RestrictionEngine 计算（Task 12 已交付）
- 不做 CV 三件套（Task 10 已交付）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Stream
from app.schemas.restriction import (
    RestrictionCalculateRequest,
    RestrictionCalculateResponse,
)
from app.services.restriction.restriction_persist import RestrictionService

router = APIRouter(prefix="/restriction", tags=["restriction"])


@router.post(
    "/calculate",
    status_code=201,
    response_model=RestrictionCalculateResponse,
)
async def restriction_calculate(
    req: RestrictionCalculateRequest,
    db: AsyncSession = Depends(get_db),
) -> RestrictionCalculateResponse:
    """POST /api/v1/restriction/calculate：限制装置单工况计算落库。

    流程：
    1. RestrictionService.persist_calculate（RestrictionEngine + 落库 + outlet）
    2. 查 outlet stream（upstream_stream_id == source_stream_id）
    3. 组装 RestrictionCalculateResponse 返回

    Returns:
        201 + restriction_result_id + outlet_stream_id + 关键计算字段
    """
    try:
        restriction_result = await RestrictionService.persist_calculate(
            db,
            source_stream_id=req.source_stream_id,
            request=req.model_dump(),
        )
    except ValueError as e:
        # RestrictionEngine 参数异常（D<=0 / d>=D / Re_D<=0 / stages<1 等）→ 422 envelope
        raise HTTPException(
            status_code=422,
            detail={"code": "RES_INVALID_INPUT", "message": str(e)},
        ) from e

    # 查 outlet stream（service 层刚创建；单 outlet 锚定 source_stream_id）
    outlet = (
        await db.execute(
            select(Stream).where(Stream.upstream_stream_id == req.source_stream_id)
        )
    ).scalar_one()

    return RestrictionCalculateResponse(
        restriction_result_id=restriction_result.orifice_id,
        tag_number=restriction_result.tag_number,
        device_type=restriction_result.device_type,
        C_discharge=restriction_result.C_discharge,
        beta_ratio=restriction_result.beta_ratio,
        epsilon=restriction_result.epsilon,
        delta_P_pa=restriction_result.delta_P_pa,
        choked=restriction_result.choked,
        flashing=restriction_result.flashing,
        stages=restriction_result.stages,
        standard_profile_code=restriction_result.input_json.get(
            "request", {}
        ).get("standard_profile_code", "ISO-5167"),
        record_hash=restriction_result.record_hash,
        outlet_stream_id=outlet.stream_id,
    )


__all__ = ["router"]