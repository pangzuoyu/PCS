"""P4-2-5 PIPE 计算链 API。

端点：
- POST /api/v1/pipe/calc-chain
    body: PipeChainRequest
    response: { "chain_result_id": uuid, "outlet_stream_id": uuid, "result": dict }

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
- 三步守卫复用 P4-0-3 ``check_calc_inputs``：DRAFT → 403 / 不可靠 → 422 /
  不存在 → 404
- 落库走 ``persist_pipe_chain_result``：piping_results + outlet_stream
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
from app.models.project import Stream
from app.services.calc_entry import check_calc_inputs
from app.services.exceptions import PcsError
from app.services.pipe.pipe_chain_persist import persist_pipe_chain_result
from app.services.pipe.pipe_chain_service import (
    FluidPhase,
    PipeChainInput,
    PipeSegmentInput,
    calc_chain,
)
from app.services.pipe.pressure_drop_service import Fitting

router = APIRouter(prefix="/pipe", tags=["pipe"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


class SegmentRequest(BaseModel):
    """单管段请求。"""

    fluid_phase: FluidPhase = Field(..., description="LIQUID / VAPOR / TWO_PHASE")
    mass_flow_kg_s: float = Field(..., description="单相质量流量 (kg/s)")
    density_kg_m3: float = Field(..., description="单相密度 (kg/m³)")
    viscosity_pa_s: float = Field(..., description="单相动力粘度 (Pa·s)")
    pipe_diameter_m: float = Field(..., description="管内径 (m)")
    pipe_roughness_m: float = Field(..., description="绝对粗糙度 (m)")
    length_m: float = Field(..., description="直管长度 (m)")
    inclination_deg: float = Field(0.0, description="倾角 (°；0=水平，90=向上)")
    elevation_change_m: float = Field(0.0, description="高程变化 (m；正=向上)")
    # 两相段（仅 TWO_PHASE 必填）
    surface_tension_n_m: float | None = None
    liquid_density_kg_m3: float | None = None
    liquid_viscosity_pa_s: float | None = None
    gas_density_kg_m3: float | None = None
    gas_viscosity_pa_s: float | None = None
    liquid_mass_flow_kg_s: float | None = None
    gas_mass_flow_kg_s: float | None = None
    # 单相 fittings
    fittings: list[Fitting] = Field(default_factory=list)


class CalcChainRequest(BaseModel):
    """POST /pipe/calc-chain 请求体。"""

    project_id: uuid.UUID = Field(..., description="项目 UUID")
    workspace_id: uuid.UUID = Field(..., description="工作区 UUID")
    source_stream_id: uuid.UUID = Field(..., description="入口流 UUID（必须 CHECKED）")
    tag_number: str = Field(..., description="链位号（写入 piping_results.line_no）")
    inlet_pressure_pa: float | None = Field(
        None,
        description="入口压力 (Pa；None 时从 source_stream.press 读取)",
    )
    inlet_temperature_K: float | None = Field(
        None, description="入口温度 (K；预留，本批不参与热损失)"
    )
    parallel_branches: int = Field(1, description="并联支路数（本批仅支持 = 1）")
    segments: list[SegmentRequest] = Field(..., description="管段列表（≥ 1）")


class CalcChainResponse(BaseModel):
    """POST /pipe/calc-chain 响应。"""

    chain_result_id: uuid.UUID = Field(..., description="PipingResult.pipe_id")
    outlet_stream_id: uuid.UUID = Field(..., description="出口流 UUID")
    record_hash: str = Field(..., description="16 hex 数值规范化哈希")
    result: dict[str, Any] = Field(default_factory=dict, description="链计算结果 dict")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    """service PcsError → core PcsError 转换（与 flash.py 行为一致）。"""
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


def _segment_req_to_dataclass(req: SegmentRequest) -> PipeSegmentInput:
    """SegmentRequest → PipeSegmentInput dataclass。"""
    return PipeSegmentInput(
        fluid_phase=req.fluid_phase,
        mass_flow_kg_s=req.mass_flow_kg_s,
        density_kg_m3=req.density_kg_m3,
        viscosity_pa_s=req.viscosity_pa_s,
        pipe_diameter_m=req.pipe_diameter_m,
        pipe_roughness_m=req.pipe_roughness_m,
        length_m=req.length_m,
        inclination_deg=req.inclination_deg,
        elevation_change_m=req.elevation_change_m,
        surface_tension_n_m=req.surface_tension_n_m,
        liquid_density_kg_m3=req.liquid_density_kg_m3,
        liquid_viscosity_pa_s=req.liquid_viscosity_pa_s,
        gas_density_kg_m3=req.gas_density_kg_m3,
        gas_viscosity_pa_s=req.gas_viscosity_pa_s,
        liquid_mass_flow_kg_s=req.liquid_mass_flow_kg_s,
        gas_mass_flow_kg_s=req.gas_mass_flow_kg_s,
        fittings=list(req.fittings),
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/calc-chain",
    status_code=201,
    response_model=CalcChainResponse,
)
async def calc_pipe_chain(
    req: CalcChainRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CalcChainResponse:
    """POST /api/v1/pipe/calc-chain：链式管道压降计算 + 落库 + outlet 流。

    流程：
    1. check_calc_inputs(db, [source_stream_id])：三步守卫
    2. 读 source stream：取 press / temp 兜底
    3. calc_chain → 链计算
    4. persist_pipe_chain_result → piping_results + outlet_stream
    5. commit + 返回响应
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    # 1. 三步守卫
    await check_calc_inputs(db, [req.source_stream_id])

    # 2. 读源流取 press / temp
    source = await db.get(Stream, req.source_stream_id)
    if source is None:
        raise CorePcsError(
            code="SIM_STREAM_NOT_FOUND",
            message=f"源流 {req.source_stream_id} 不存在",
            status=404,
        )
    inlet_p = (
        req.inlet_pressure_pa if req.inlet_pressure_pa is not None else source.press
    )
    if inlet_p is None or inlet_p <= 0.0:
        raise CorePcsError(
            code="PIPE_CHAIN_INPUT_ERROR",
            message="inlet_pressure_pa 未提供且源流 press 不可用",
            status=422,
        )

    # 3. calc_chain
    segments_dc = [_segment_req_to_dataclass(s) for s in req.segments]
    chain_inp = PipeChainInput(
        project_id=req.project_id,
        workspace_id=req.workspace_id,
        source_stream_id=req.source_stream_id,
        tag_number=req.tag_number,
        segments=segments_dc,
        inlet_pressure_pa=float(inlet_p),
        inlet_temperature_K=req.inlet_temperature_K,
        parallel_branches=req.parallel_branches,
    )
    try:
        chain_res = calc_chain(chain_inp)
    except PcsError as e:
        raise _to_http(e) from e

    # 4. 落库 + outlet
    try:
        row, outlet = await persist_pipe_chain_result(db, chain_inp, chain_res)
    except PcsError as e:
        raise _to_http(e) from e

    await db.commit()

    # 5. 响应
    import dataclasses

    return CalcChainResponse(
        chain_result_id=row.pipe_id,
        outlet_stream_id=outlet.stream_id,
        record_hash=row.record_hash,
        result=dataclasses.asdict(chain_res),
    )


__all__ = ["router"]
