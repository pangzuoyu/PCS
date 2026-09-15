"""P4-4-1：泵选型服务（API 610 + 比转速 ns 分类 + 泵曲线初版）。

公式与判定：
- 比转速：ns = n × √Q / H^0.75（n 单位 rpm，Q 单位 m³/s，H 单位 m）
- 分类（Karassik / Pump Handbook 4th 表）：
    ns < 500    → RADIAL（离心泵）→ API 610 OH2 / OH3 / BB1
    500 ≤ ns<3000 → MIXED（混流泵）→ API 610 BB3
    ns ≥ 3000   → AXIAL（轴流泵） → API 610 VS1
- 功率：P = ρ g Q H / η；默认 η = 0.7
- 效率经验公式（Pump Handbook 4th 表 6.1 简化拟合）：
    η = 0.55 + 0.00012 × ns  → 在 [0.55, 0.88] 区间裁剪
    （高 ns 大泵效率高；低 ns 小泵效率低 — 与实际趋势一致）
- confidence：worst-wins（沿用 P4-2-5 链式规则）
    任一上游 chain LOW → 整体 LOW；MEDIUM → MEDIUM；全 HIGH → HIGH

设计要点：
- dataclass(frozen=True) 输入不可变；纯函数不触 DB（落库 P4-4-4 接管）
- 不实现真正的泵曲线（性能曲线 / NPSH 曲线拟合）— 本批仅算选型点
- 不联动 outlet_stream（P4-1-3，P4-4-4 接管）

不做：
- 不查厂家目录
- 不算 NPSHa（依赖管段阻力 + 罐压；P4-4-3 接管）
- 不落库 / 不创建 outlet（P4-4-4）
"""
from __future__ import annotations

import math
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from app.services.exceptions import PcsError

if TYPE_CHECKING:
    from app.services.pipe.pipe_chain_service import PipeChainInput

# 物理：g = 9.80665 m/s²（ISO 80000-3，与 P4-2-5 对齐）
_G: float = 9.80665

# 泵类型字面量
PumpType = Literal["CENTRIFUGAL", "MIXED_FLOW", "AXIAL"]
API610Type = Literal["OH2", "OH3", "BB1", "BB3", "VS1"]
SpecificSpeedClass = Literal["RADIAL", "MIXED", "AXIAL"]
Confidence = Literal["HIGH", "MEDIUM", "LOW"]
CheckResult = Literal["PASS", "WARNING", "FAIL"]

# 经验默认 η（任务规约）
_DEFAULT_ETA: float = 0.7
# 默认转速（50Hz 2 极）
_DEFAULT_SPEED_RPM: float = 2950.0

# ns 分类阈值
_NS_RADIAL_MAX: float = 500.0
_NS_MIXED_MAX: float = 3000.0


# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class PumpInputError(PcsError):
    """PUMP 选型输入错误（业务非法）。"""

    code = "PUMP_INPUT_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# 类型
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PumpInput:
    """泵选型输入。

    Attributes:
        project_id: 项目 UUID
        workspace_id: 工作区 UUID
        source_stream_id: 源流 UUID（CHECKED 守卫，本 task 不触）
        tag_number: 泵位号
        flow_m3_s: 流量 (m³/s；>0)
        head_m: 扬程 (m；>0)
        fluid_density_kg_m3: 流体密度 (kg/m³；>0)
        fluid_viscosity_pa_s: 动力粘度 (Pa·s；>0)
        npsh_required_m: 厂家给定必需 NPSH (m；可选)
        efficiency_target: 设计目标效率 (0~1；None → 0.7 默认)
        speed_rpm: 转速 (rpm；默认 2950)
        suction_pipe_chain: 入口管段（P4-2-5；可选；复用 confidence）
        discharge_pipe_chain: 出口管段（P4-2-5；可选；复用 confidence）
    """

    project_id: uuid.UUID
    workspace_id: uuid.UUID
    source_stream_id: uuid.UUID
    tag_number: str
    flow_m3_s: float
    head_m: float
    fluid_density_kg_m3: float
    fluid_viscosity_pa_s: float
    npsh_required_m: float | None = None
    efficiency_target: float | None = None
    speed_rpm: float = _DEFAULT_SPEED_RPM
    suction_pipe_chain: PipeChainInput | None = None
    discharge_pipe_chain: PipeChainInput | None = None


@dataclass(frozen=True)
class PumpSelectionResult:
    """泵选型结果。

    Attributes:
        pump_type: 泵类型 CENTRIFUGAL / MIXED_FLOW / AXIAL
        api610_type: API 610 型号 OH2/OH3/BB1/BB3/VS1
        specific_speed_ns: 比转速 ns
        specific_speed_class: ns 分类 RADIAL/MIXED/AXIAL
        selected_speed_rpm: 选用转速 (rpm)
        estimated_power_kw: 估算轴功率 (kW)
        estimated_efficiency: 估算效率 (0~1)
        operating_point: 工况点 (Q, H)
        confidence: 整体置信度 HIGH/MEDIUM/LOW（worst-wins）
        check_result: 校核档 PASS/WARNING/FAIL
        check_result_reason: 校核原因
    """

    pump_type: PumpType
    api610_type: API610Type
    specific_speed_ns: float
    specific_speed_class: SpecificSpeedClass
    selected_speed_rpm: float
    estimated_power_kw: float
    estimated_efficiency: float
    operating_point: tuple[float, float]
    confidence: Confidence
    check_result: CheckResult
    check_result_reason: str | None


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------


_CONFIDENCE_RANK = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def _worst_confidence(c1: Confidence, c2: Confidence | None) -> Confidence:
    """worst-wins：取等级最低者（rank 最大）。"""
    if c2 is None:
        return c1
    return c1 if _CONFIDENCE_RANK[c1] >= _CONFIDENCE_RANK[c2] else c2


def _classify_ns(ns: float) -> SpecificSpeedClass:
    if ns < _NS_RADIAL_MAX:
        return "RADIAL"
    if ns < _NS_MIXED_MAX:
        return "MIXED"
    return "AXIAL"


def _map_api610(pump_type: PumpType) -> API610Type:
    """泵类型 → API 610 型号（按任务规约）。

    离心泵默认 OH2（卧式、单壳、端吸，主流炼油用）。
    """
    if pump_type == "CENTRIFUGAL":
        return "OH2"
    if pump_type == "MIXED_FLOW":
        return "BB3"
    return "VS1"


def _estimate_efficiency(ns: float) -> float:
    """经验效率（Pump Handbook 4th 表 6.1 简化拟合）。

    η 随 ns 单调递增，在 [0.55, 0.88] 区间裁剪。
    """
    # ns=0 → 0.55；ns=3000 → 0.85；ns=5000 → 0.88（封顶）
    raw = 0.55 + 0.00012 * ns  # 0.55 + 0.00012*3000 = 0.91 → 裁剪
    return max(0.55, min(0.88, raw))


def _validate_input(inp: PumpInput) -> None:
    if inp.flow_m3_s <= 0:
        raise PumpInputError(f"flow_m3_s 必须 > 0（got {inp.flow_m3_s}）")
    if inp.head_m <= 0:
        raise PumpInputError(f"head_m 必须 > 0（got {inp.head_m}）")
    if inp.fluid_density_kg_m3 <= 0:
        raise PumpInputError(
            f"fluid_density_kg_m3 必须 > 0（got {inp.fluid_density_kg_m3}）"
        )
    if inp.fluid_viscosity_pa_s <= 0:
        raise PumpInputError(
            f"fluid_viscosity_pa_s 必须 > 0（got {inp.fluid_viscosity_pa_s}）"
        )
    if inp.speed_rpm <= 0:
        raise PumpInputError(f"speed_rpm 必须 > 0（got {inp.speed_rpm}）")
    if inp.efficiency_target is not None and not (
        0.0 < inp.efficiency_target <= 1.0
    ):
        raise PumpInputError(
            f"efficiency_target 必须在 (0, 1]（got {inp.efficiency_target}）"
        )


# ---------------------------------------------------------------------------
# 入口：select_pump
# ---------------------------------------------------------------------------


def select_pump(inp: PumpInput) -> PumpSelectionResult:
    """PUMP 选型。

    流程：
    1. 输入校验
    2. 比转速 ns = n × √Q / H^0.75
    3. ns 分类 → 泵类型 → API 610 型号
    4. 估算功率 P = ρgQH / η
    5. 估算效率（ns 经验公式）
    6. confidence 聚合（沿用 P4-2-5 worst-wins）

    Args:
        inp: 泵选型输入

    Returns:
        PumpSelectionResult

    Raises:
        PumpInputError: 输入越界
    """
    _validate_input(inp)

    # 1) 比转速
    ns = inp.speed_rpm * math.sqrt(inp.flow_m3_s) / (inp.head_m ** 0.75)

    # 2) 分类
    ns_class = _classify_ns(ns)
    pump_type: PumpType = {
        "RADIAL": "CENTRIFUGAL",
        "MIXED": "MIXED_FLOW",
        "AXIAL": "AXIAL",
    }[ns_class]
    api610 = _map_api610(pump_type)

    # 3) 功率计算用 η：用户给定 → 用之；否则默认 0.7（任务规约）
    power_eta = (
        inp.efficiency_target if inp.efficiency_target is not None else _DEFAULT_ETA
    )
    # estimated_efficiency 始终按 ns 经验公式上报（设计目标 vs 经验估计分离）
    eta = _estimate_efficiency(ns)

    # 4) 功率 P = ρgQH / η（W → kW）
    power_w = inp.fluid_density_kg_m3 * _G * inp.flow_m3_s * inp.head_m / power_eta
    power_kw = power_w / 1000.0

    # 5) confidence worst-wins（沿用 P4-2-5）
    confidence: Confidence = "HIGH"
    if inp.suction_pipe_chain is not None:
        # 透传 suction 链 confidence（lazy calc）
        from app.services.pipe.pipe_chain_service import calc_chain

        confidence = _worst_confidence(
            confidence, calc_chain(inp.suction_pipe_chain).confidence
        )
    if inp.discharge_pipe_chain is not None:
        from app.services.pipe.pipe_chain_service import calc_chain

        confidence = _worst_confidence(
            confidence, calc_chain(inp.discharge_pipe_chain).confidence
        )

    # 6) check_result：初版默认 PASS（无 NPSHa 计算 / 无性能曲线校核）
    check_result: CheckResult = "PASS"
    check_reason: str | None = None

    return PumpSelectionResult(
        pump_type=pump_type,
        api610_type=api610,
        specific_speed_ns=ns,
        specific_speed_class=ns_class,
        selected_speed_rpm=inp.speed_rpm,
        estimated_power_kw=power_kw,
        estimated_efficiency=eta,
        operating_point=(inp.flow_m3_s, inp.head_m),
        confidence=confidence,
        check_result=check_result,
        check_result_reason=check_reason,
    )
