"""P6-1 Task 10 调节阀 Cv 计算 API：POST /api/v1/cv/calculate 端点契约。

按 PCS-PLAN-P6-BATCH.md §Task 10 + SPEC §3.2.1.1~1.4 + §3.2.1.6 + ADR-0022 V1.0：

端点：
- POST /api/v1/cv/calculate
    body: CvCalculateRequest（21+ 字段；SPEC §3.2.1.1~1.4）
    response: CvCalculateResponse（cv_result_id + outlet_stream_id）

设计要点：
- 业务异常 → Pydantic ValidationError（422 默认 envelope）；自定义 CvService 抛
  ValueError → 转 422 envelope（CV_INVALID_INPUT）
- 复用 CvService.persist_calculate（Task 9）：调 CvEngine + 落 cv_results +
  record_hash + outlet stream（DEVICE_CALCULATED + FRICTION_PRESSURE_DROP）
- 不做 ACL / 工况守卫（PSV 才需要；CV 是设备计算，不涉 DRAFT→CHECKED 锁）

不做：
- 不调 cv_api 自身（cv_persist 已直调 CvEngine）
- 不写 record_hash 算法（service 层复用 calc_lineage.compute_record_hash）
- 不实现 CvEngine 计算（Task 8 已交付）
- 不做 RESTRICTION 三件套（Task 12-14）
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.project import Stream
from app.schemas.cv import CvCalculateRequest, CvCalculateResponse
from app.services.cv.cv_persist import CvService

router = APIRouter(prefix="/cv", tags=["cv"])


@router.post(
    "/calculate",
    status_code=201,
    response_model=CvCalculateResponse,
)
async def cv_calculate(
    req: CvCalculateRequest,
    db: AsyncSession = Depends(get_db),
) -> CvCalculateResponse:
    """POST /api/v1/cv/calculate：调节阀 Cv 单工况计算落库。

    流程：
    1. CvService.persist_calculate（调 CvEngine + 落 cv_results + outlet stream）
    2. 查 outlet stream（upstream_stream_id == source_stream_id）
    3. 组装 CvCalculateResponse 返回

    Returns:
        201 + cv_result_id + outlet_stream_id + 关键计算字段
    """
    try:
        cv_result = await CvService.persist_calculate(
            db,
            source_stream_id=req.source_stream_id,
            request=req.model_dump(),
        )
    except ValueError as e:
        # CvEngine 参数异常（SG<=0 / Pc<=Pv / Q<=0 等）→ 422 envelope
        raise HTTPException(
            status_code=422,
            detail={"code": "CV_INVALID_INPUT", "message": str(e)},
        ) from e

    # 查 outlet stream（service 层刚创建；单 outlet 锚定 source_stream_id）
    outlet = (
        await db.execute(
            select(Stream).where(Stream.upstream_stream_id == req.source_stream_id)
        )
    ).scalar_one()

    return CvCalculateResponse(
        cv_result_id=cv_result.cv_id,
        tag_number=cv_result.tag_number,
        fluid_phase=cv_result.fluid_phase,
        Cv_calculated=cv_result.Cv_calculated,
        Cv_selected=cv_result.Cv_selected,
        choked=cv_result.choked,
        cavitation=cv_result.cavitation,
        flashing=cv_result.flashing,
        noise_sil_db=cv_result.noise_sil_db,
        standard_profile_code=cv_result.standard_profile_code,
        design_stage=cv_result.design_stage.value
        if hasattr(cv_result.design_stage, "value")
        else str(cv_result.design_stage),
        record_hash=cv_result.record_hash,
        outlet_stream_id=outlet.stream_id,
    )


__all__ = ["router"]
