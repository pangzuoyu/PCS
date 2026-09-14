"""P4-3-3 管网 Hardy-Cross 计算 + 落库 + outlet_stream API。

端点：
- POST /api/v1/pipe-net/solve
    body: PipeNetSolveRequest（含拓扑 + 求解配置）
    response: { "network_result_id": uuid, "outlet_stream_id": uuid,
                "converged": bool, "iterations": int,
                "max_flow_error_m3_s": float,
                "edge_flows": [...], "node_pressures": [...],
                "confidence": str, "check_result": str,
                "check_result_reason": str | None }

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
- 三步守卫复用 P4-0-3 ``check_calc_inputs``：DRAFT → 403 / 不可靠 → 422 /
  不存在 → 404
- 拓扑校验复用 P4-3-1 ``validate_topology``：非法 → 422
- 求解复用 P4-3-2 ``solve_network``：不收敛 → 422
- 落库走 ``persist_pipe_network_result``：pipe_network_results + outlet_stream
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
from app.services.pipe.pipe_chain_service import (
    PipeChainInput,
    PipeSegmentInput,
)
from app.services.pipe_net import (
    EdgeInput,
    NodeInput,
    PipeNetworkInput,
    SolverConfig,
    persist_pipe_network_result,
    solve_network,
)
from app.services.pipe_net.solver_service import (
    EdgeFlowResult,
    NodePressureResult,
    PressureDropCheck,
    PressureDropConfidence,
)

router = APIRouter(prefix="/pipe-net", tags=["pipe-net"])


# ---------------------------------------------------------------------------
# 请求 / 响应封装
# ---------------------------------------------------------------------------


class SegmentReq(BaseModel):
    """管段请求（P4-2-5 segment 子集；拓扑入参所需最小字段）。"""

    fluid_phase: str = Field("LIQUID", description="LIQUID / VAPOR / TWO_PHASE")
    mass_flow_kg_s: float = Field(1.0, description="单相质量流量 (kg/s；占位)")
    density_kg_m3: float = Field(1000.0, description="单相密度")
    viscosity_pa_s: float = Field(1.0e-3, description="单相动力粘度 (Pa·s)")
    pipe_diameter_m: float = Field(0.05, description="管内径 (m)")
    pipe_roughness_m: float = Field(4.6e-5, description="绝对粗糙度 (m)")
    length_m: float = Field(10.0, description="直管长度 (m)")
    inclination_deg: float = Field(0.0, description="倾角 (°)")
    elevation_change_m: float = Field(0.0, description="高程变化 (m)")
    surface_tension_n_m: float | None = None
    liquid_density_kg_m3: float | None = None
    liquid_viscosity_pa_s: float | None = None
    gas_density_kg_m3: float | None = None
    gas_viscosity_pa_s: float | None = None
    liquid_mass_flow_kg_s: float | None = None
    gas_mass_flow_kg_s: float | None = None
    fittings: list[dict[str, Any]] = Field(default_factory=list)


class EdgeReq(BaseModel):
    """管网边请求。"""

    edge_id: str = Field(..., description="边 ID")
    from_node: str = Field(..., description="源节点 ID")
    to_node: str = Field(..., description="目标节点 ID")
    # pipe_chain 字段（链入参简化；project/workspace/source 复用外层）
    tag_number: str = Field(..., description="边链位号（落链 tag_number）")
    segments: list[SegmentReq] = Field(..., description="管段列表 (≥ 1)")
    inlet_pressure_pa: float = Field(200_000.0, description="链入口压力 (Pa)")
    inlet_temperature_K: float | None = None
    parallel_branches: int = Field(1, description="并联支路数（仅 = 1）")


class NodeReq(BaseModel):
    """管网节点请求。"""

    node_id: str = Field(..., description="节点 ID")
    elevation_m: float = Field(0.0, description="标高 (m)")
    node_type: str = Field(
        "JUNCTION", description="JUNCTION / SOURCE / SINK / EQUIPMENT_INTERFACE"
    )
    demand_m3_s: float = Field(0.0, description="净需求 (m³/s)")
    pressure_pa: float | None = Field(None, description="节点压力 (Pa)")
    upstream_equipment_type: str | None = Field(
        None, description="设备类型（仅 EQUIPMENT_INTERFACE）"
    )


class SolverConfigReq(BaseModel):
    """求解配置（可选；缺省 SolverConfig 默认值）。"""

    tolerance_m3_s: float = Field(1e-6, description="流量收敛容差 (m³/s)")
    max_iterations: int = Field(100, description="最大迭代次数")
    initial_flow_strategy: str = Field("EVEN_DEMAND_PROPORTIONAL")


class PipeNetSolveRequest(BaseModel):
    """POST /pipe-net/solve 请求体。"""

    project_id: uuid.UUID = Field(..., description="项目 UUID")
    workspace_id: uuid.UUID = Field(..., description="工作区 UUID")
    source_stream_id: uuid.UUID = Field(..., description="入口流 UUID（必须 CHECKED）")
    tag_number: str = Field(..., description="管网位号（pipe-net-001）")
    nodes: list[NodeReq] = Field(..., description="节点列表（≥ 1 SOURCE + ≥ 1 SINK）")
    edges: list[EdgeReq] = Field(..., description="边列表")
    tolerance_pa: float = Field(
        100.0, description="保留兼容字段；本批走 solver_config.tolerance_m3_s"
    )
    max_iterations: int = Field(
        100, description="保留兼容字段；本批走 solver_config.max_iterations"
    )
    solver_config: SolverConfigReq | None = Field(None, description="求解配置（可选）")


class EdgeFlowJson(BaseModel):
    """边流量解 JSON（响应）。"""

    edge_id: str
    flow_m3_s: float
    flow_direction: str
    dp_pa: float
    iterations_to_converge: int | None


class NodePressureJson(BaseModel):
    """节点压力解 JSON（响应）。"""

    node_id: str
    pressure_pa: float
    elevation_m: float
    velocity_head_m: float | None


class PipeNetSolveResponse(BaseModel):
    """POST /pipe-net/solve 响应。"""

    network_result_id: uuid.UUID
    outlet_stream_id: uuid.UUID
    converged: bool
    iterations: int
    max_flow_error_m3_s: float
    edge_flows: list[EdgeFlowJson]
    node_pressures: list[NodePressureJson]
    confidence: PressureDropConfidence
    check_result: PressureDropCheck
    check_result_reason: str | None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    """service PcsError → core PcsError 转换（与 pipe.py 行为一致）。"""
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


def _segment_req_to_dc(req: SegmentReq) -> PipeSegmentInput:
    """SegmentReq → PipeSegmentInput dataclass。"""
    return PipeSegmentInput(
        fluid_phase=req.fluid_phase,  # type: ignore[arg-type]
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
        fittings=list(req.fittings),  # type: ignore[arg-type]
    )


def _edge_req_to_dc(
    req: EdgeReq, project_id: uuid.UUID, workspace_id: uuid.UUID, source_stream_id: uuid.UUID
) -> EdgeInput:
    """EdgeReq → EdgeInput dataclass。"""
    chain = PipeChainInput(
        project_id=project_id,
        workspace_id=workspace_id,
        source_stream_id=source_stream_id,
        tag_number=req.tag_number,
        segments=[_segment_req_to_dc(s) for s in req.segments],
        inlet_pressure_pa=req.inlet_pressure_pa,
        inlet_temperature_K=req.inlet_temperature_K,
        parallel_branches=req.parallel_branches,
    )
    return EdgeInput(
        edge_id=req.edge_id,
        from_node=req.from_node,
        to_node=req.to_node,
        pipe_chain=chain,
    )


def _node_req_to_dc(req: NodeReq) -> NodeInput:
    """NodeReq → NodeInput dataclass。"""
    return NodeInput(
        node_id=req.node_id,
        elevation_m=req.elevation_m,
        node_type=req.node_type,  # type: ignore[arg-type]
        demand_m3_s=req.demand_m3_s,
        pressure_pa=req.pressure_pa,
        upstream_equipment_type=req.upstream_equipment_type,
    )


def _edge_flow_to_json(ef: EdgeFlowResult) -> EdgeFlowJson:
    return EdgeFlowJson(
        edge_id=ef.edge_id,
        flow_m3_s=ef.flow_m3_s,
        flow_direction=ef.flow_direction,
        dp_pa=ef.dp_pa,
        iterations_to_converge=ef.iterations_to_converge,
    )


def _node_pressure_to_json(np: NodePressureResult) -> NodePressureJson:
    return NodePressureJson(
        node_id=np.node_id,
        pressure_pa=np.pressure_pa,
        elevation_m=np.elevation_m,
        velocity_head_m=np.velocity_head_m,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/solve",
    status_code=201,
    response_model=PipeNetSolveResponse,
)
async def solve_pipe_net(
    req: PipeNetSolveRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> PipeNetSolveResponse:
    """POST /api/v1/pipe-net/solve：管网求解 + 落库 + outlet 流。

    流程：
    1. check_calc_inputs(db, [source_stream_id])：三步守卫（exists → CHECKED → unreliable）
    2. 构造 PipeNetworkInput dataclass（拓扑 + 求解配置）
    3. solve_network → 管网 Hardy-Cross 求解（拓扑校验内嵌）
    4. persist_pipe_network_result → pipe_network_results + outlet_stream
    5. commit + 返回响应
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    # 1. 三步守卫
    await check_calc_inputs(db, [req.source_stream_id])

    # 2. 构造 PipeNetworkInput
    nodes_dc = [_node_req_to_dc(n) for n in req.nodes]
    edges_dc = [
        _edge_req_to_dc(e, req.project_id, req.workspace_id, req.source_stream_id)
        for e in req.edges
    ]
    if req.solver_config is not None:
        solver_cfg = SolverConfig(
            tolerance_m3_s=req.solver_config.tolerance_m3_s,
            max_iterations=req.solver_config.max_iterations,
            initial_flow_strategy=req.solver_config.initial_flow_strategy,  # type: ignore[arg-type]
        )
    else:
        solver_cfg = SolverConfig(
            tolerance_m3_s=1e-6,
            max_iterations=req.max_iterations,
            initial_flow_strategy="EVEN_DEMAND_PROPORTIONAL",
        )

    inp = PipeNetworkInput(
        project_id=req.project_id,
        workspace_id=req.workspace_id,
        source_stream_id=req.source_stream_id,
        tag_number=req.tag_number,
        nodes=nodes_dc,
        edges=edges_dc,
        tolerance_pa=req.tolerance_pa,
        max_iterations=req.max_iterations,
    )

    # 3. solve_network（含拓扑校验 + Hardy-Cross 求解）
    try:
        result = solve_network(inp, solver_cfg)
    except PcsError as e:
        raise _to_http(e) from e

    # 4. 落库 + outlet
    try:
        row, outlet = await persist_pipe_network_result(db, inp, result)
    except PcsError as e:
        raise _to_http(e) from e

    await db.commit()

    # 5. 响应
    return PipeNetSolveResponse(
        network_result_id=row.network_id,
        outlet_stream_id=outlet.stream_id,
        converged=result.converged,
        iterations=result.iterations,
        max_flow_error_m3_s=result.max_flow_error_m3_s,
        edge_flows=[_edge_flow_to_json(ef) for ef in result.edge_flows],
        node_pressures=[_node_pressure_to_json(np) for np in result.node_pressures],
        confidence=result.confidence,
        check_result=result.check_result,
        check_result_reason=result.check_result_reason,
    )


__all__ = ["router"]