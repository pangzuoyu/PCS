"""P4-4-4：PUMP 链核心算法（select_pump + calc_npsha + interpolate_curve 串联）。

链流程：
    1. select_pump（pump_type / api610 / ns / 功率 / 效率）
    2. calc_npsha（吸入侧阻力 + 精度护栏），传入 npshr 取 margin
    3. interpolate_curve(curve, flow_m3_s)（运行点 H / η / NPSHr）
    4. 校核：
        margin = NPSHa - NPSHr
        margin < 0 → FAIL (reason="NEGATIVE_MARGIN")
        deviation_from_rated_pct > 20 → WARNING (reason="DEVIATION_FROM_RATED")
        suction LOW / TRANSITION → WARNING (reason="SUCTION_LOW_RE_UNCERTAINTY")
    5. overall_confidence worst-wins（select_pump.confidence vs
       npsha.suction_confidence）

不做：
- 不触 DB（落库 P4-4-4 pump_chain_persist）
- 不联动 outlet_stream（persist 接管）
- 不改 P4-4-1/2/3 service 既有契约（只读复用）
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.services.exceptions import PcsError
from app.services.pump.curve_service import (
    PumpCurve,
    PumpCurveInterp,
    interpolate_curve,
)
from app.services.pump.npsha_service import (
    NPSHaInput,
    NPSHaResult,
    calc_npsha,
)
from app.services.pump.pump_service import (
    PumpInput,
    PumpSelectionResult,
    select_pump,
)

if TYPE_CHECKING:
    from app.services.pipe.pipe_chain_service import PipeChainInput

Confidence = Literal["HIGH", "MEDIUM", "LOW"]
CheckResult = Literal["PASS", "WARNING", "FAIL"]

# 偏离设计点告警阈值（%；> 此值 → WARNING）
_DEVIATION_FROM_RATED_PCT: float = 20.0

# worst-wins 等级表（沿用 P4-4-2）
_CONFIDENCE_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class PumpChainInputError(PcsError):
    """PUMP 链输入错误（业务非法）。"""

    code = "PUMP_CHAIN_INPUT_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PumpChainInput:
    """PUMP 链总输入。

    Attributes:
        project_id: 项目 UUID
        workspace_id: 工作区 UUID
        source_stream_id: 源流 UUID
        tag_number: 泵位号（P-001 等）
        flow_m3_s: 工况流量 (m³/s)
        head_m: 工况扬程 (m)
        fluid_density_kg_m3: 流体密度 (kg/m³)
        fluid_viscosity_pa_s: 动力粘度 (Pa·s)
        pump_curve: 厂家泵曲线（P4-4-3）
        vapor_pressure_pa: 饱和蒸汽压 (Pa)
        system_pressure_pa: 上游系统压力 (Pa；必须 > vapor_pressure_pa)
        suction_pipe_chain: 吸入侧管段链（P4-2-5）
        discharge_pipe_chain: 排出侧管段链（可选）
        speed_rpm: 转速 (rpm；默认 2950)
        elevation_change_m: 液位到泵入口高程差 (m；正数=抬升)
        efficiency_target: 设计目标效率（沿用 P4-4-1）
    """

    project_id: uuid.UUID
    workspace_id: uuid.UUID
    source_stream_id: uuid.UUID
    tag_number: str
    flow_m3_s: float
    head_m: float
    fluid_density_kg_m3: float
    fluid_viscosity_pa_s: float
    pump_curve: PumpCurve
    vapor_pressure_pa: float
    system_pressure_pa: float
    suction_pipe_chain: PipeChainInput
    discharge_pipe_chain: PipeChainInput | None = None
    speed_rpm: float = 2950.0
    elevation_change_m: float = 0.0
    efficiency_target: float | None = None


@dataclass
class PumpChainResult:
    """PUMP 链计算结果。

    Attributes:
        selection: 选型结果
        npsha: NPSHa 结果
        operating_point: 曲线插值运行点
        margin_m: NPSHa - NPSHr（m）
        margin_pct: margin / NPSHr × 100（%）
        deviation_from_rated_pct: 偏离设计点百分比
        overall_confidence: 整体置信度（worst-wins）
        overall_check_result: 整体校核档 PASS/WARNING/FAIL
        overall_check_result_reason: 整体校核原因
    """

    selection: PumpSelectionResult
    npsha: NPSHaResult
    operating_point: PumpCurveInterp
    margin_m: float
    margin_pct: float
    deviation_from_rated_pct: float
    overall_confidence: Confidence
    overall_check_result: CheckResult
    overall_check_result_reason: str | None


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


def _worst_confidence(c1: Confidence, c2: Confidence) -> Confidence:
    """worst-wins（rank 较大者更差）。"""
    return c1 if _CONFIDENCE_RANK[c1] >= _CONFIDENCE_RANK[c2] else c2


def _validate_input(inp: PumpChainInput) -> None:
    if inp.flow_m3_s <= 0:
        raise PumpChainInputError(f"flow_m3_s 必须 > 0（got {inp.flow_m3_s}）")
    if inp.head_m <= 0:
        raise PumpChainInputError(f"head_m 必须 > 0（got {inp.head_m}）")
    if inp.fluid_density_kg_m3 <= 0:
        raise PumpChainInputError(
            f"fluid_density_kg_m3 必须 > 0（got {inp.fluid_density_kg_m3}）"
        )
    if inp.fluid_viscosity_pa_s <= 0:
        raise PumpChainInputError(
            f"fluid_viscosity_pa_s 必须 > 0（got {inp.fluid_viscosity_pa_s}）"
        )
    if inp.speed_rpm <= 0:
        raise PumpChainInputError(f"speed_rpm 必须 > 0（got {inp.speed_rpm}）")
    if inp.system_pressure_pa <= inp.vapor_pressure_pa:
        raise PumpChainInputError(
            f"system_pressure_pa 必须 > vapor_pressure_pa "
            f"（Ps={inp.system_pressure_pa}, Pv={inp.vapor_pressure_pa}）"
        )


# ---------------------------------------------------------------------------
# 入口：calc_pump_chain
# ---------------------------------------------------------------------------


def calc_pump_chain(inp: PumpChainInput) -> PumpChainResult:
    """PUMP 链计算（不落库）。

    流程：
    1. 校验输入
    2. select_pump：选型 + 估算功率 / 效率
    3. interpolate_curve：运行点 H / η / NPSHr
    4. calc_npsha：吸入口 NPSHa（传入 NPSHr 取 margin）
    5. 校核档与 confidence 聚合

    Args:
        inp: PUMP 链总输入

    Returns:
        PumpChainResult

    Raises:
        PumpChainInputError / PumpInputError / NPSHaInputError / PumpCurveInputError
    """
    _validate_input(inp)

    # 1) 选型（复用 P4-4-1；透传 suction/discharge 链供 confidence 聚合）
    selection = select_pump(
        PumpInput(
            project_id=inp.project_id,
            workspace_id=inp.workspace_id,
            source_stream_id=inp.source_stream_id,
            tag_number=inp.tag_number,
            flow_m3_s=inp.flow_m3_s,
            head_m=inp.head_m,
            fluid_density_kg_m3=inp.fluid_density_kg_m3,
            fluid_viscosity_pa_s=inp.fluid_viscosity_pa_s,
            efficiency_target=inp.efficiency_target,
            speed_rpm=inp.speed_rpm,
            suction_pipe_chain=inp.suction_pipe_chain,
            discharge_pipe_chain=inp.discharge_pipe_chain,
        )
    )

    # 2) 曲线插值（先取 NPSHr）
    operating_point = interpolate_curve(inp.pump_curve, inp.flow_m3_s)

    # 3) NPSHa（吸入侧；传入 NPSHr 拿 margin）
    npsha = calc_npsha(
        NPSHaInput(
            project_id=inp.project_id,
            workspace_id=inp.workspace_id,
            source_stream_id=inp.source_stream_id,
            tag_number=inp.tag_number,
            system_pressure_pa=inp.system_pressure_pa,
            vapor_pressure_pa=inp.vapor_pressure_pa,
            fluid_density_kg_m3=inp.fluid_density_kg_m3,
            fluid_viscosity_pa_s=inp.fluid_viscosity_pa_s,
            suction_pipe_chain=inp.suction_pipe_chain,
            elevation_change_m=inp.elevation_change_m,
        ),
        npshr_m=operating_point.npshr_m,
    )

    margin_m = npsha.margin_m if npsha.margin_m is not None else 0.0
    margin_pct = npsha.margin_pct if npsha.margin_pct is not None else 0.0

    # 4) 校核档聚合（最差优先）：
    #    a. NPSHa 自身 FAIL（来自 NEGATIVE_MARGIN）→ 整体 FAIL
    #    b. 否则按 NPSHa 的 WARNING（如 LOW/TRANSITION）+ 偏离设计点
    #       告警 → WARNING
    #    c. 否则 PASS
    overall_check: CheckResult
    overall_reason: str | None
    if npsha.check_result == "FAIL":
        overall_check = "FAIL"
        overall_reason = npsha.check_result_reason or "NEGATIVE_MARGIN"
    elif npsha.check_result == "WARNING":
        overall_check = "WARNING"
        overall_reason = npsha.check_result_reason
    elif operating_point.distance_from_rated_pct > _DEVIATION_FROM_RATED_PCT:
        overall_check = "WARNING"
        overall_reason = "DEVIATION_FROM_RATED"
    else:
        overall_check = "PASS"
        overall_reason = None

    # 5) 整体 confidence：worst-wins（select vs npsha）
    overall_confidence = _worst_confidence(
        selection.confidence, npsha.suction_confidence
    )

    return PumpChainResult(
        selection=selection,
        npsha=npsha,
        operating_point=operating_point,
        margin_m=margin_m,
        margin_pct=margin_pct,
        deviation_from_rated_pct=operating_point.distance_from_rated_pct,
        overall_confidence=overall_confidence,
        overall_check_result=overall_check,
        overall_check_result_reason=overall_reason,
    )


__all__ = [
    "PumpChainInput",
    "PumpChainInputError",
    "PumpChainResult",
    "calc_pump_chain",
]
