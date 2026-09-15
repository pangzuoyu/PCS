"""P4-4-3：厂家泵曲线多点线性插值（Q-H / Q-η / Q-NPSHr 三曲线）。

设计要点：
- 厂家给定典型 5–10 点曲线，区间内点间线性插值
- 不外推：Q < 最小点 或 Q > 最大点 → 拒绝
- 三曲线（Q-H / Q-η / Q-NPSHr）独立插值，结构相同
- 设计点（rated）判定：浮点等值用 math.isclose
- 偏离设计点百分比：|Q - rated| / rated × 100

不做：
- 不引入 scipy / numpy（自实现线性插值）
- 不落库（落库 P4-4-4 接管）
- 不联动 select_pump / calc_npsha（仅消费 points 数据）
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.services.exceptions import PcsError

PumpType = Literal["CENTRIFUGAL", "MIXED_FLOW", "AXIAL"]
API610Type = Literal["OH2", "OH3", "BB1", "BB3", "VS1"]

# 设计点 Q 等值容差（rel_tol）
_RATED_FLOW_RELTOL: float = 1e-9


class PumpCurveInputError(PcsError):
    """PUMP 曲线输入错误（业务非法）。"""

    code = "PUMP_CURVE_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class PumpCurvePoint:
    """泵曲线单点（厂家给定）。"""

    flow_m3_s: float
    head_m: float
    efficiency: float
    npshr_m: float


@dataclass(frozen=True)
class PumpCurve:
    """厂家泵曲线（多点，按 Q 升序）。

    Attributes:
        pump_tag: 泵位号
        pump_type: 泵类型 CENTRIFUGAL/MIXED_FLOW/AXIAL
        api610_type: API 610 型号
        speed_rpm: 额定转速 (rpm)
        points: 曲线数据点（按 Q 升序，>=2 点）
        rated_flow_m3_s: 设计点流量 (m³/s)
        rated_head_m: 设计点扬程 (m)
        rated_efficiency: 设计点效率 (0~1)
    """

    pump_tag: str
    pump_type: PumpType
    api610_type: API610Type
    speed_rpm: float
    points: tuple[PumpCurvePoint, ...]
    rated_flow_m3_s: float
    rated_head_m: float
    rated_efficiency: float


@dataclass(frozen=True)
class PumpCurveInterp:
    """单点插值结果。

    Attributes:
        flow_m3_s: 查询流量 (m³/s)
        head_m: 插值扬程 (m)
        efficiency: 插值效率 (0~1)
        npshr_m: 插值必需 NPSH (m)
        is_rated_point: 是否设计点（浮点等值）
        distance_from_rated_pct: 偏离设计点百分比（绝对值）
    """

    flow_m3_s: float
    head_m: float
    efficiency: float
    npshr_m: float
    is_rated_point: bool
    distance_from_rated_pct: float


def _validate_curve(curve: PumpCurve) -> None:
    if len(curve.points) < 2:
        raise PumpCurveInputError(
            f"泵曲线至少 2 个数据点（got {len(curve.points)}）"
        )
    if curve.rated_flow_m3_s <= 0:
        raise PumpCurveInputError(
            f"rated_flow_m3_s 必须 > 0（got {curve.rated_flow_m3_s}）"
        )
    if not (0.0 < curve.rated_efficiency <= 1.0):
        raise PumpCurveInputError(
            f"rated_efficiency 必须在 (0, 1]（got {curve.rated_efficiency}）"
        )
    if curve.speed_rpm <= 0:
        raise PumpCurveInputError(
            f"speed_rpm 必须 > 0（got {curve.speed_rpm}）"
        )


def _validate_q_in_range(curve: PumpCurve, q: float) -> None:
    q_min = curve.points[0].flow_m3_s
    q_max = curve.points[-1].flow_m3_s
    if q < q_min or q > q_max:
        raise PumpCurveInputError(
            f"flow_m3_s 越界 [{q_min}, {q_max}]（got {q}，不外推）"
        )


def _find_segment(points: tuple[PumpCurvePoint, ...], q: float) -> tuple[int, int]:
    """定位 Q 所在区间 [i, i+1]。

    区间内：单调增 Q 序列中找 i 使 points[i].flow <= q <= points[i+1].flow。
    端点：q == points[0].flow → 区间 [0, 1]；q == points[-1].flow → 区间 [-2, -1]。
    """
    n = len(points)
    if q <= points[0].flow_m3_s:
        return 0, 1
    if q >= points[-1].flow_m3_s:
        return n - 2, n - 1
    for i in range(n - 1):
        if points[i].flow_m3_s <= q <= points[i + 1].flow_m3_s:
            return i, i + 1
    # 不应到达此处（区间内单调）
    raise PumpCurveInputError(f"无法定位 flow_m3_s={q} 所在区间")


def _linear_interp(
    x: float, x0: float, y0: float, x1: float, y1: float
) -> float:
    """点间线性插值（自实现）。

    y = y0 + (x - x0) / (x1 - x0) × (y1 - y0)
    """
    return y0 + (x - x0) / (x1 - x0) * (y1 - y0)


def _interp_field(
    points: tuple[PumpCurvePoint, ...],
    i: int,
    j: int,
    q: float,
    getter,
) -> float:
    """对单一字段（H / η / NPSHr）做线性插值。"""
    p0 = points[i]
    p1 = points[j]
    return _linear_interp(
        q,
        p0.flow_m3_s,
        getter(p0),
        p1.flow_m3_s,
        getter(p1),
    )


def interpolate_curve(curve: PumpCurve, flow_m3_s: float) -> PumpCurveInterp:
    """泵曲线单点插值。

    1. 校验曲线完整性（点数 / rated / speed）
    2. 校验 Q 在 [min, max]（不外推）
    3. 定位区间 [i, i+1]
    4. 线性插值 H / η / NPSHr
    5. 设计点判定（浮点等值 isclose）
    6. 偏离设计点百分比

    Args:
        curve: 厂家泵曲线
        flow_m3_s: 查询流量 (m³/s)

    Returns:
        PumpCurveInterp

    Raises:
        PumpCurveInputError: 曲线非法 / Q 越界
    """
    _validate_curve(curve)
    _validate_q_in_range(curve, flow_m3_s)
    i, j = _find_segment(curve.points, flow_m3_s)
    head = _interp_field(curve.points, i, j, flow_m3_s, lambda p: p.head_m)
    eta = _interp_field(curve.points, i, j, flow_m3_s, lambda p: p.efficiency)
    npshr = _interp_field(curve.points, i, j, flow_m3_s, lambda p: p.npshr_m)
    is_rated = math.isclose(
        flow_m3_s, curve.rated_flow_m3_s, rel_tol=_RATED_FLOW_RELTOL
    )
    distance_pct = (
        abs(flow_m3_s - curve.rated_flow_m3_s) / curve.rated_flow_m3_s * 100.0
    )
    return PumpCurveInterp(
        flow_m3_s=flow_m3_s,
        head_m=head,
        efficiency=eta,
        npshr_m=npshr,
        is_rated_point=is_rated,
        distance_from_rated_pct=distance_pct,
    )