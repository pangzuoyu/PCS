"""P4-4-4 PUMP 链 API。

端点：
- POST /api/v1/pump/calc-chain
    body: PumpChainRequest
    response: { "pump_result_id": uuid, "outlet_stream_id": uuid, "result": dict }

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
- 三步守卫复用 P4-0-3 ``check_calc_inputs``：DRAFT → 403 / 不可靠 → 422 /
  不存在 → 404
- 落库走 ``persist_pump_chain_result``：pump_results + outlet_stream
- 业务异常 → 走 core.errors.PcsError envelope
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
from app.services.calc_entry import check_calc_inputs
from app.services.exceptions import PcsError
from app.services.pipe.pipe_chain_service import PipeChainInput  # 复用类型
from app.services.pump.curve_service import PumpCurve, PumpCurvePoint
from app.services.pump.pump_chain_persist import persist_pump_chain_result
from app.services.pump.pump_chain_service import (
    PumpChainInput,
)
from app.services.pump.pump_chain_service import (
    calc_pump_chain as _calc_pump_chain,
)

router = APIRouter(prefix="/pump", tags=["pump"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


class PipeChainRef(BaseModel):
    """管段链引用（API 层弱类型：完整 dict 透传给 service；此处复用最小入口）。"""

    segments: list[dict[str, Any]] = Field(..., description="管段列表（≥ 1）")
    inlet_pressure_pa: float | None = Field(
        None, description="入口压力 (Pa；None 时由 service 兜底)"
    )
    inlet_temperature_K: float | None = Field(None, description="入口温度 (K)")
    parallel_branches: int = Field(1, description="并联支路数（本批仅支持 = 1）")


class CurvePointRequest(BaseModel):
    """曲线单点请求。"""

    flow_m3_s: float
    head_m: float
    efficiency: float
    npshr_m: float


class PumpCurveRequest(BaseModel):
    """厂家泵曲线请求。"""

    pump_tag: str
    pump_type: str = Field("CENTRIFUGAL", description="CENTRIFUGAL/MIXED_FLOW/AXIAL")
    api610_type: str = Field("OH2", description="OH2/OH3/BB1/BB3/VS1")
    speed_rpm: float = 2950.0
    points: list[CurvePointRequest] = Field(
        ..., min_length=2, description="泵特性曲线点（至少 2 点）"
    )
    rated_flow_m3_s: float
    rated_head_m: float
    rated_efficiency: float


class CalcChainRequest(BaseModel):
    """POST /pump/calc-chain 请求体。"""

    project_id: uuid.UUID
    workspace_id: uuid.UUID
    source_stream_id: uuid.UUID
    tag_number: str
    flow_m3_s: float
    head_m: float
    fluid_density_kg_m3: float
    fluid_viscosity_pa_s: float
    pump_curve: PumpCurveRequest
    vapor_pressure_pa: float
    system_pressure_pa: float
    suction_pipe_chain: PipeChainRef
    discharge_pipe_chain: PipeChainRef | None = None
    speed_rpm: float = 2950.0
    elevation_change_m: float = 0.0
    efficiency_target: float | None = None


class CalcChainResponse(BaseModel):
    """POST /pump/calc-chain 响应。"""

    pump_result_id: uuid.UUID
    outlet_stream_id: uuid.UUID
    record_hash: str
    result: dict[str, Any]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    """service PcsError → core PcsError 转换。"""
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


def _curve_req_to_dataclass(req: PumpCurveRequest) -> PumpCurve:
    """PumpCurveRequest → PumpCurve dataclass。"""
    points = tuple(
        PumpCurvePoint(
            flow_m3_s=p.flow_m3_s,
            head_m=p.head_m,
            efficiency=p.efficiency,
            npshr_m=p.npshr_m,
        )
        for p in req.points
    )
    return PumpCurve(
        pump_tag=req.pump_tag,
        pump_type=req.pump_type,  # type: ignore[arg-type]
        api610_type=req.api610_type,  # type: ignore[arg-type]
        speed_rpm=req.speed_rpm,
        points=points,
        rated_flow_m3_s=req.rated_flow_m3_s,
        rated_head_m=req.rated_head_m,
        rated_efficiency=req.rated_efficiency,
    )


def _pipe_chain_ref_to_dc(
    ref: PipeChainRef,
    *,
    project_id: uuid.UUID,
    workspace_id: uuid.UUID,
    source_stream_id: uuid.UUID,
    tag_number: str,
) -> PipeChainInput:
    """PipeChainRef → PipeChainInput dataclass（透传 segments 列表 dict）。"""
    from app.services.pipe.pipe_chain_service import (
        PipeSegmentInput,
    )

    segments: list[PipeSegmentInput] = []
    for seg in ref.segments:
        segments.append(
            PipeSegmentInput(
                fluid_phase=seg.get("fluid_phase", "LIQUID"),
                mass_flow_kg_s=seg["mass_flow_kg_s"],
                density_kg_m3=seg["density_kg_m3"],
                viscosity_pa_s=seg["viscosity_pa_s"],
                pipe_diameter_m=seg["pipe_diameter_m"],
                pipe_roughness_m=seg["pipe_roughness_m"],
                length_m=seg["length_m"],
                inclination_deg=seg.get("inclination_deg", 0.0),
                elevation_change_m=seg.get("elevation_change_m", 0.0),
            )
        )
    inlet_p = ref.inlet_pressure_pa
    if inlet_p is None:
        inlet_p = 200_000.0  # 占位；NPSHa 算的是相对差，对 inlet P 不敏感
    return PipeChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number=tag_number,
        segments=segments,
        inlet_pressure_pa=inlet_p,
        inlet_temperature_K=ref.inlet_temperature_K,
        parallel_branches=ref.parallel_branches,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/calc-chain",
    status_code=201,
    response_model=CalcChainResponse,
)
async def calc_pump_chain(
    req: CalcChainRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalcChainResponse:
    """POST /api/v1/pump/calc-chain：PUMP 链计算 + 落库 + outlet 流。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    # 1. 三步守卫
    await check_calc_inputs(db, [req.source_stream_id])

    # 2. 构造 service 入参
    suction_dc = _pipe_chain_ref_to_dc(
        req.suction_pipe_chain,
        project_id=req.project_id,
        workspace_id=req.workspace_id,
        source_stream_id=req.source_stream_id,
        tag_number=f"{req.tag_number}-SUC",
    )
    discharge_dc = (
        _pipe_chain_ref_to_dc(
            req.discharge_pipe_chain,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            source_stream_id=req.source_stream_id,
            tag_number=f"{req.tag_number}-DIS",
        )
        if req.discharge_pipe_chain is not None
        else None
    )
    curve_dc = _curve_req_to_dataclass(req.pump_curve)

    chain_inp = PumpChainInput(
        project_id=req.project_id,
        workspace_id=req.workspace_id,
        source_stream_id=req.source_stream_id,
        tag_number=req.tag_number,
        flow_m3_s=req.flow_m3_s,
        head_m=req.head_m,
        fluid_density_kg_m3=req.fluid_density_kg_m3,
        fluid_viscosity_pa_s=req.fluid_viscosity_pa_s,
        pump_curve=curve_dc,
        vapor_pressure_pa=req.vapor_pressure_pa,
        system_pressure_pa=req.system_pressure_pa,
        suction_pipe_chain=suction_dc,
        discharge_pipe_chain=discharge_dc,
        speed_rpm=req.speed_rpm,
        elevation_change_m=req.elevation_change_m,
        efficiency_target=req.efficiency_target,
    )

    # 3. calc_pump_chain
    try:
        chain_res = _calc_pump_chain(chain_inp)
    except PcsError as e:
        raise _to_http(e) from e

    # 4. 落库 + outlet
    try:
        row, outlet = await persist_pump_chain_result(db, chain_inp, chain_res)
    except PcsError as e:
        raise _to_http(e) from e

    await db.commit()

    # 5. 响应
    import dataclasses

    return CalcChainResponse(
        pump_result_id=row.pump_id,
        outlet_stream_id=outlet.stream_id,
        record_hash=row.record_hash,
        result=dataclasses.asdict(chain_res),
    )


__all__ = ["router"]
