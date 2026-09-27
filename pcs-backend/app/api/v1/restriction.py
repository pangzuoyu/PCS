"""P6-1 Task 14 + P6-2 S-01 限制装置计算 API +
P6-6A-7 排污孔板 sizing API：POST /api/v1/restriction/{calculate,drain-orifice/size} 端点契约。

按 PCS-PLAN-P6-BATCH.md §Task 14 + SPEC §3.2.2.1~4 + §3.2.2.6 + ADR-0022 V1.0 +
评审委员会 2026-09-24 闪蒸路径裁决 + OPEN-P6-6A-7 drain orifice sizing inverse problem：

端点：
- POST /api/v1/restriction/calculate
    body: RestrictionCalculateRequest（14 + 5 = 19 字段；含 P6-2 S-01 flash 输入）
    response: RestrictionCalculateResponse（含 flash 元数据 + outlet_stream_id）
- POST /api/v1/restriction/drain-orifice/size
    body: DrainOrificeSizeRequest（14 字段；SPEC §3.7.2 inverse problem）
    response: DrainOrificeSizeResponse（求解得到的 d + 流动状态元数据）
    ACL：DESIGNER / PROCESS_CONTROLLER

设计要点：
- 业务异常 → Pydantic ValidationError（422 默认 envelope）；自定义 RestrictionService
  抛 ValueError → 转 422 envelope（RES_INVALID_INPUT）；DrainOrifice*PcsError
  子类 → install_exception_handlers 兜底转 422 envelope
  （DRAIN_ORIFICE_INPUT_ERROR / DRAIN_ORIFICE_SIZING_NOT_CONVERGED）
- 复用 RestrictionService.persist_calculate（Task 13 + S-01）：调 await RestrictionEngine
  + 落 restriction_results + record_hash + outlet stream（RESTRICTION_CALCULATED +
  ISOENTHALPIC；区别 CV FRICTION_PRESSURE_DROP）
- 不做 ACL / 工况守卫（RESTRICTION 是设备计算，不涉 DRAFT→CHECKED 锁）
- drain-orifice sizing 不写 DB（落库由 restriction_persist 统一处理；sizing 是
  独立纯计算，沿用 flare.py kod-sizing 模式）

不做：
- 不调 restriction_api 自身（restriction_persist 已直调 RestrictionEngine）
- 不写 record_hash 算法（service 层复用 calc_lineage.compute_record_hash）
- 不实现 RestrictionEngine 计算（P6-1 已交付 + P6-2 S-01 升级）
- 不实现 drain-orifice sizing 算法（P6-6A-7 service 已交付）
- 不做 CV 三件套（Task 10 已交付）
"""
from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.project import Stream
from app.schemas.restriction import (
    DrainOrificeSizeRequest,
    DrainOrificeSizeResponse,
    RestrictionCalculateRequest,
    RestrictionCalculateResponse,
)
from app.services.restriction.drain_orifice_service import (
    DrainOrificeSizeInput,
    calc_drain_orifice_size,
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
    1. await RestrictionService.persist_calculate（RestrictionEngine async + 落库 +
       outlet；含 P6-2 S-01 flash 联动）
    2. 查 outlet stream（upstream_stream_id == source_stream_id）
    3. 组装 RestrictionCalculateResponse 返回（含 flash 元数据）

    Returns:
        201 + restriction_result_id + outlet_stream_id + 关键计算字段 + flash 元数据
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

    # P6-2 S-01 flash 元数据回填（input_json / output_json 容器承载）
    output_json = restriction_result.output_json or {}
    input_json = restriction_result.input_json or {}
    flash_check = input_json.get("flash_check", {})

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
        P_sat_pa=output_json.get("P_sat_pa") or flash_check.get("P_sat_pa"),
        vapor_fraction_at_outlet=output_json.get(
            "vapor_fraction_at_outlet", 0.0
        ),
        model_used=output_json.get("model_used", "ISO_5167"),
        stages=restriction_result.stages,
        standard_profile_code=input_json.get(
            "request", {}
        ).get("standard_profile_code", "ISO-5167"),
        record_hash=restriction_result.record_hash,
        outlet_stream_id=outlet.stream_id,
    )


# ============================================================================
# P6-6A-7 / OPEN-P6-6A-7：drain orifice sizing inverse problem（SPEC §3.7.2）
# ============================================================================


@router.post(
    "/drain-orifice/size",
    response_model=DrainOrificeSizeResponse,
    status_code=status.HTTP_200_OK,
)
async def calculate_drain_orifice_size(
    req: DrainOrificeSizeRequest,
    user: Annotated[_Actor, Depends(current_actor)],
) -> DrainOrificeSizeResponse:
    """POST /api/v1/restriction/drain-orifice/size：排污孔板 sizing（OPEN-P6-6A-7）。

    Inverse problem：已知泄放量 W + 工况反推 orifice diameter d。
    仅适用于阻塞流场景（SPEC §3.7.2 sizing 仅在临界流成立；非阻塞流抛
    DrainOrificeInputError → install_exception_handlers 转 422 envelope）。

    不写 DB（落库由 restriction_persist 统一处理；sizing 是独立纯计算，
    沿用 flare.py kod-sizing / header-sizing 模式）。

    ACL：DESIGNER / PROCESS_CONTROLLER
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER")
    # DrainOrificeSizeInputError / DrainOrificeSizingNotConvergedError（均继承
    # ServicePcsError，status=422）由 install_exception_handlers 兜底转 422 envelope，
    # 此处不显式 try/except（与 /restriction/calculate 仅 try/except ValueError 对齐）。
    inp = DrainOrificeSizeInput(**req.model_dump())
    result = calc_drain_orifice_size(inp)
    return DrainOrificeSizeResponse(**result.__dict__)


__all__ = ["router"]