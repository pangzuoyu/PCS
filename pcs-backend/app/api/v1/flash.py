"""P4-1-3 FLASH API：3 端点契约。

端点：
- POST /api/v1/flash/calculate
    body: { calc_type, stream_id, T_K, P_Pa, H_target?, S_target?, fluid? }
- POST /api/v1/flash/bubble
    body: { stream_id, mode: "T"|"P", value: float }
- POST /api/v1/flash/dew
    body: { stream_id, mode: "T"|"P", value: float }

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
- 业务异常 → 走 core.errors.PcsError envelope（422/403/404 一致）
- 所有端点共用 flash_persist 调度（service 层统一流程：守卫 → 计算 → 落库 →
  状态点联动 → 出口物流 → commit）
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.services.exceptions import PcsError
from app.services.flash import flash_persist

router = APIRouter(prefix="/flash", tags=["flash"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


class CalculateRequest(BaseModel):
    """POST /flash/calculate 请求体。"""

    calc_type: str = Field(
        ...,
        description="PT_FLASH / PH_FLASH / PS_FLASH / SATURATION",
    )
    stream_id: uuid.UUID = Field(..., description="输入流 UUID（必须 CHECKED）")
    T_K: float | None = Field(None, description="温度 K（PT/PH/PS_FLASH + SATURATION 用）")
    P_Pa: float | None = Field(None, description="压力 Pa（PT_FLASH + SATURATION 用）")
    H_target: float | None = Field(None, description="目标焓 J/mol（PH_FLASH）")
    S_target: float | None = Field(None, description="目标熵 J/mol/K（PS_FLASH）")
    fluid: str | None = Field(
        None,
        description="流体名/CAS（SATURATION 用，例如 PROPANE / 74-98-6）",
    )


class BubbleDewRequest(BaseModel):
    """POST /flash/bubble 与 POST /flash/dew 请求体。"""

    stream_id: uuid.UUID = Field(..., description="输入流 UUID（必须 CHECKED）")
    mode: str = Field(
        ...,
        description='给定变量："T" 给 T 算 P_bubble/dew；"P" 给 P 算 T_bubble/dew',
    )
    value: float = Field(..., description="给定变量值（T_K 或 P_Pa）")


class CalculateResponse(BaseModel):
    """POST /flash/calculate 响应：calc_id + record_hash + lineage_ids + outlet。"""

    calc_id: uuid.UUID = Field(..., description="FlashResult.flash_id")
    calc_type: str = Field(..., description="回显计算类型")
    record_hash: str = Field(..., description="16 hex 数值规范化哈希")
    stream_id: uuid.UUID = Field(..., description="输入流 UUID")
    lineage_ids: list[uuid.UUID] = Field(
        default_factory=list, description="DataLineage 行 ID 列表（每 source_stream 一条）"
    )
    result: dict[str, Any] = Field(default_factory=dict, description="计算结果")
    outlet_stream_id: uuid.UUID | None = Field(
        None, description="出口流 UUID（SATURATION 时为 null）"
    )
    outlet_stream_name: str | None = Field(None, description="出口流名称（SATURATION 时为 null）")


class BubbleDewResponse(BaseModel):
    """POST /flash/bubble 与 POST /flash/dew 响应。"""

    calc_id: uuid.UUID
    calc_type: str
    record_hash: str
    stream_id: uuid.UUID
    bubble_T_K: float | None = None
    bubble_P_Pa: float | None = None
    dew_T_K: float | None = None
    dew_P_Pa: float | None = None
    outlet_stream_id: uuid.UUID | None = None
    outlet_stream_name: str | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    """service PcsError → core PcsError 转换（与 streams.py 行为一致）。"""
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


async def _lineage_ids(db: AsyncSession, calc_id: uuid.UUID) -> list[uuid.UUID]:
    """查 record_id=calc_id 的血缘 ID 列表（DataLineage.source_ref_id 已记录；
    返回 calc 级 lineage_id 供前端审计）。"""
    from sqlalchemy import select

    from app.models.system import DataLineage

    rows = (
        await db.execute(
            select(DataLineage.lineage_id).where(
                DataLineage.record_type == "FlashResult",
                DataLineage.record_id == calc_id,
            )
        )
    ).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/calculate",
    status_code=201,
    response_model=CalculateResponse,
)
async def calculate_flash(
    req: CalculateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalculateResponse:
    """POST /api/v1/flash/calculate：PT/PH/PS_FLASH + SATURATION 统一入口。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        data = await flash_persist.persist_calculate(
            db,
            calc_type=req.calc_type,
            stream_id=req.stream_id,
            T_K=req.T_K,
            P_Pa=req.P_Pa,
            H_target=req.H_target,
            S_target=req.S_target,
            fluid=req.fluid,
            actor=user.user_id,
        )
    except PcsError as e:
        raise _to_http(e) from e
    lineage_ids = await _lineage_ids(db, data["calc_id"])
    return CalculateResponse(
        calc_id=data["calc_id"],
        calc_type=data["calc_type"],
        record_hash=data["record_hash"],
        stream_id=data["stream_id"],
        lineage_ids=lineage_ids,
        result=data.get("result", {}),
        outlet_stream_id=data.get("outlet_stream_id"),
        outlet_stream_name=data.get("outlet_stream_name"),
    )


@router.post(
    "/bubble",
    status_code=201,
    response_model=BubbleDewResponse,
)
async def calculate_bubble(
    req: BubbleDewRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BubbleDewResponse:
    """POST /api/v1/flash/bubble：mode=T 给 T 算 P_bubble；mode=P 给 P 算 T_bubble。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        data = await flash_persist.persist_bubble(
            db,
            stream_id=req.stream_id,
            mode=req.mode,
            value=req.value,
            actor=user.user_id,
        )
    except PcsError as e:
        raise _to_http(e) from e
    return BubbleDewResponse(
        calc_id=data["calc_id"],
        calc_type=data["calc_type"],
        record_hash=data["record_hash"],
        stream_id=data["stream_id"],
        bubble_T_K=data.get("bubble_T_K"),
        bubble_P_Pa=data.get("bubble_P_Pa"),
        dew_T_K=None,
        dew_P_Pa=None,
        outlet_stream_id=data.get("outlet_stream_id"),
        outlet_stream_name=data.get("outlet_stream_name"),
    )


@router.post(
    "/dew",
    status_code=201,
    response_model=BubbleDewResponse,
)
async def calculate_dew(
    req: BubbleDewRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> BubbleDewResponse:
    """POST /api/v1/flash/dew：mode=T 给 T 算 P_dew；mode=P 给 P 算 T_dew。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        data = await flash_persist.persist_dew(
            db,
            stream_id=req.stream_id,
            mode=req.mode,
            value=req.value,
            actor=user.user_id,
        )
    except PcsError as e:
        raise _to_http(e) from e
    return BubbleDewResponse(
        calc_id=data["calc_id"],
        calc_type=data["calc_type"],
        record_hash=data["record_hash"],
        stream_id=data["stream_id"],
        bubble_T_K=None,
        bubble_P_Pa=None,
        dew_T_K=data.get("dew_T_K"),
        dew_P_Pa=data.get("dew_P_Pa"),
        outlet_stream_id=data.get("outlet_stream_id"),
        outlet_stream_name=data.get("outlet_stream_name"),
    )


__all__ = ["router"]
