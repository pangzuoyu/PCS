"""临界水深 + Froude 数（SPEC §3.2.6 第三项）。

临界水深 h_c（矩形断面简化）：

    h_c = (q² / g)^(1/3)，q = Q / b（单宽流量 m²/s）

非矩形断面按比能最小迭代求解；本模块对非矩形断面给出基于 h 的
单宽流量 q(h) = Q / b + 0 修正项（rect 专用），非矩形仅计算 Froude。

Froude 数（流态判定）：

    Fr = v / √(g × h_m)，h_m = A / b（矩形平均水深等于水深本身）

判定标准：

- Fr < 1：缓流（subcritical）
- Fr = 1：临界流（critical）
- Fr > 1：急流（supercritical）

手算独立校核：

例 1（矩形 Q=2/b=2/h=1/g=9.81）：

    h_c = (q²/g)^(1/3)，q = Q/b = 1
    h_c = (1/9.81)^(1/3) = 0.4666 m
    v = Q/A = 2/2 = 1 m/s；h_m = A/b = 1
    Fr = 1/√(9.81×1) = 0.3192（Fr<1 → 缓流）✓

例 2（矩形 Q=2/b=2/h=0.4666 临界态）：

    v = 2/(2×0.4666) = 2.1435 m/s
    h_m = 0.4666
    Fr = 2.1435/√(9.81×0.4666) = 2.1435/2.1403 ≈ 1.0016 ≈ 1.0（临界态）✓

例 3（矩形 Q=2/b=2/h=0.2 急流）：

    v = 2/(2×0.2) = 5 m/s
    h_m = 0.2
    Fr = 5/√(9.81×0.2) = 5/1.4007 ≈ 3.5702（Fr>1 → 急流）✓

P6-OPEN-001（G-01 degraded）决议：禁止 import fluids.open_channel，
本模块采用自研兜底（参照 ADR-0030 V1.2 决策 7）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.exceptions import PcsError

GRAVITY = 9.80665  # m/s²（标准重力加速度，CODATA 2018）


# 流态枚举（Froude 判定结果）
FlowRegime = str  # Literal 替代为 str 以避免引入额外类型导入


@dataclass(frozen=True)
class CriticalInput:
    """临界水深 / Froude 输入（§3.2.6）。

    字段：

    - ``flow_rate``：Q（m³/s，>0）
    - ``bottom_width``：底宽 b（m，>0）；矩形用
    - ``depth``：水深 h（m，>0）；计算 Froude 用
    - ``gravity``：重力加速度（m/s²，默认 9.80665）

    注：h_c 仅对矩形断面有解析解；非矩形断面 h_c 需迭代（模块暂支持矩形）。
    """

    flow_rate: float
    bottom_width: float
    depth: float
    gravity: float = GRAVITY


@dataclass(frozen=True)
class CriticalResult:
    """临界水深 / Froude 输出（§3.2.6）。

    字段：

    - ``critical_depth``：h_c（m）
    - ``unit_discharge``：q = Q / b（m²/s）
    - ``froude_number``：Fr = v / √(g × h_m)
    - ``flow_regime``："subcritical"（Fr<1）/ "critical"（Fr≈1）/ "supercritical"（Fr>1）
    - ``velocity``：v（m/s）
    - ``formula_ref``：公式溯源标记，恒等于 "CRITICAL_§3.2.6"
    """

    critical_depth: float
    unit_discharge: float
    froude_number: float
    flow_regime: str
    velocity: float
    formula_ref: str = "CRITICAL_§3.2.6"


class CriticalInputError(PcsError):
    """临界水深 / Froude 输入不合法（422）。

    触发场景：

    - flow_rate / bottom_width / depth / gravity 非正
    """

    code = "CRITICAL_INPUT_ERROR"
    status = 422


def calc_critical_depth(
    flow_rate: float, bottom_width: float, gravity: float = GRAVITY,
) -> float:
    """矩形断面临界水深 h_c（§3.2.6 第三项）。

    公式：h_c = (q² / g)^(1/3)，q = Q / b（单宽流量 m²/s）。

    Args:
        flow_rate: Q（m³/s，>0）。
        bottom_width: 矩形底宽 b（m，>0）。
        gravity: 重力加速度（m/s²，默认 9.80665）。

    Returns:
        h_c（m）。

    Raises:
        CriticalInputError: 输入字段非正（422）。
    """
    if flow_rate <= 0:
        raise CriticalInputError(f"flow_rate ({flow_rate}) 必须 > 0")
    if bottom_width <= 0:
        raise CriticalInputError(f"bottom_width ({bottom_width}) 必须 > 0")
    if gravity <= 0:
        raise CriticalInputError(f"gravity ({gravity}) 必须 > 0")

    q = flow_rate / bottom_width
    h_c = (q * q / gravity) ** (1.0 / 3.0)
    return h_c


def calc_froude_number(
    flow_rate: float, bottom_width: float, depth: float,
    gravity: float = GRAVITY,
) -> tuple[float, float, str]:
    """矩形断面 Froude 数 + 速度 + 流态判定（§3.2.6 第三项）。

    公式：Fr = v / √(g × h_m)；v = Q / (b × h)；h_m = h（矩形）。

    流态判定：

    - Fr < 1 − 1e-3：subcritical（缓流）
    - |Fr − 1| ≤ 1e-3：critical（临界）
    - Fr > 1 + 1e-3：supercritical（急流）

    Args:
        flow_rate: Q（m³/s，>0）。
        bottom_width: 矩形底宽 b（m，>0）。
        depth: 水深 h（m，>0）。
        gravity: 重力加速度（m/s²，默认 9.80665）。

    Returns:
        (Fr, v, regime) 三元组。

    Raises:
        CriticalInputError: 输入字段非正（422）。
    """
    if flow_rate <= 0:
        raise CriticalInputError(f"flow_rate ({flow_rate}) 必须 > 0")
    if bottom_width <= 0:
        raise CriticalInputError(f"bottom_width ({bottom_width}) 必须 > 0")
    if depth <= 0:
        raise CriticalInputError(f"depth ({depth}) 必须 > 0")
    if gravity <= 0:
        raise CriticalInputError(f"gravity ({gravity}) 必须 > 0")

    a = bottom_width * depth  # 过水面积（矩形 A = b × h）
    v = flow_rate / a
    Fr = v / math.sqrt(gravity * depth)

    # 流态判定（容差 1e-3）
    if abs(Fr - 1.0) <= 1e-3:
        regime = "critical"
    elif Fr < 1.0:
        regime = "subcritical"
    else:
        regime = "supercritical"
    return Fr, v, regime


__all__ = [
    "GRAVITY",
    "CriticalInput",
    "CriticalResult",
    "CriticalInputError",
    "calc_critical_depth",
    "calc_froude_number",
]
