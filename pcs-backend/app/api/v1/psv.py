"""P5-3-6 PSV API：POST /calculate 端点契约。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §395-417 + SUP-P5-PSV-001 + ADR-0028 V1.1：

端点：
- POST /api/v1/psv/calculate
    body: {
        source_stream_id,
        relief_scenario: FIRE / CLOSED_VALVE / REACTION_RUNAWAY / THERMAL_EXPANSION,
        scenario_params: 对应 Input dataclass 字段（FireCaseInput / ClosedValveInput /
                         ReactionRunawayInput / ThermalExpansionInput），
        sizing_params: ReliefAreaInput 字段（phase + P_back + P_set + ...），
        standard_code?: API / GB / CUSTOM（默认项目默认），
        standard_version?: 7th / 2011 / 2024（默认推断），
        blowdown_fraction?: 0.05 默认，
        inlet_size?: "4 inch" 默认，
        outlet_size?: "6 inch" 默认
    }

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与 vessel / sep_equip 一致）
- 业务异常 → core.errors.PcsError envelope（422/403/404）
- 共用 psv_persist 调度（service 层统一流程：守卫 → 项目 profile → 计算 → 落库 → outlet）
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.services.exceptions import PcsError
from app.services.psv import persist_psv_calculate

router = APIRouter(prefix="/psv", tags=["psv"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


ReliefScenarioLit = Literal[
    "FIRE", "CLOSED_VALVE", "REACTION_RUNAWAY", "THERMAL_EXPANSION",
]
StandardCodeLit = Literal["API", "GB", "CUSTOM"]


class CalculateRequest(BaseModel):
    """POST /psv/calculate 请求体。"""

    source_stream_id: uuid.UUID = Field(..., description="输入流 UUID（必须 CHECKED）")
    relief_scenario: ReliefScenarioLit = Field(
        ...,
        description="FIRE / CLOSED_VALVE / REACTION_RUNAWAY / THERMAL_EXPANSION",
    )
    scenario_params: dict[str, Any] = Field(
        ...,
        description=(
            "工况参数：按 relief_scenario 路由 FireCaseInput / ClosedValveInput / "
            "ReactionRunawayInput / ThermalExpansionInput 对应字段"
        ),
    )
    sizing_params: dict[str, Any] = Field(
        ...,
        description="ReliefAreaInput 字段（phase + P_back + P_set + ...）",
    )
    standard_code: StandardCodeLit | None = Field(
        default=None,
        description="API / GB / CUSTOM；缺省走项目默认 PSV profile",
    )
    standard_version: str | None = Field(
        default=None,
        description="7th / 2011 / 2024 / CUSTOM；缺省由项目 profile 推断",
    )
    blowdown_fraction: float = Field(
        default=0.05,
        gt=0,
        lt=1,
        description="blowdown 占比（API 520 惯例 5%）",
    )
    inlet_size: str = Field(default="4 inch", description="进口尺寸")
    outlet_size: str = Field(default="6 inch", description="出口尺寸")


class CalculateResponse(BaseModel):
    """POST /psv/calculate 响应。"""

    calc_id: uuid.UUID = Field(..., description="PsvResult.psv_id")
    calc_type: str = Field("PSV", description="计算类型（固定 PSV）")
    record_hash: str = Field(..., description="16 hex 数值规范化哈希")
    stream_id: uuid.UUID = Field(..., description="源流 UUID")
    lineage_ids: list[uuid.UUID] = Field(
        default_factory=list, description="DataLineage 行 ID 列表"
    )
    result: dict[str, Any] = Field(
        default_factory=dict,
        description="完整 PSV 计算结果（scenario + aggregate + area + orifice + formula_ref）",
    )
    outlet_stream_id: uuid.UUID = Field(..., description="出口流 UUID")
    outlet_stream_name: str = Field(..., description="出口流名称")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    """service PcsError → core PcsError 转换（与 vessel.py 一致）。"""
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


async def _lineage_ids(
    db: AsyncSession, calc_id: uuid.UUID
) -> list[uuid.UUID]:
    """查 psv_id 的血缘 ID 列表（DataLineage.source_ref_id 已记录）。"""
    from sqlalchemy import select

    from app.models.system import DataLineage

    rows = (
        await db.execute(
            select(DataLineage.lineage_id).where(
                DataLineage.record_type == "PsvResult",
                DataLineage.record_id == calc_id,
            )
        )
    ).scalars().all()
    return list(rows)


# ---------------------------------------------------------------------------
# Endpoint
# ---------------------------------------------------------------------------


@router.post(
    "/calculate",
    status_code=201,
    response_model=CalculateResponse,
)
async def calculate_psv(
    req: CalculateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalculateResponse:
    """POST /api/v1/psv/calculate：PSV 单工况计算落库。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        data = await persist_psv_calculate(
            db,
            source_stream_id=req.source_stream_id,
            relief_scenario=req.relief_scenario,
            scenario_params=req.scenario_params,
            sizing_params=req.sizing_params,
            standard_code=req.standard_code,
            standard_version=req.standard_version,
            blowdown_fraction=req.blowdown_fraction,
            inlet_size=req.inlet_size,
            outlet_size=req.outlet_size,
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
        outlet_stream_id=data["outlet_stream_id"],
        outlet_stream_name=data["outlet_stream_name"],
    )


__all__ = ["router"]