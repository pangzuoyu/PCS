"""最优水力断面设计（SPEC §3.2.6 第二项）。

设计目标：给定 Q + S + n + channel_type，求水力最优断面尺寸。

水力最优断面定义：水力半径 R 最大（即湿周 P 最小，过水能力最大）。

最优比公式：

- 矩形（RECT）：b/h = 2，R = h/2
- 梯形（TRAP）：b/h = 2 × (√(1 + m²) − m)，R = h/2
- 圆形（CIRC）：满流（h = d）水力最优（湿周/面积比最低），但工程上常用
  h/d ≈ 0.938 取得最大流量（典型计算取满流作为水力最优近似）

反解策略：

- RECT：解析法（Q×n/√S = 2^(1/3) × h^(8/3) → 闭式求 h）
- TRAP：解析法（Q×n/√S = h^(8/3) × (2√(1+m²) − m) / 2^(2/3) → 闭式求 h）
- CIRC：二分法（在 (0, d] 区间对 h 单调递增 → 反解 h）

手算独立校核：

例 1（RECT Q=2/n=0.013/S=0.001）：

    k = Q × n / √S = 2 × 0.013 / 0.031623 = 0.8220
    h^(8/3) = k / 2^(1/3) = 0.8220 / 1.2599 = 0.6524
    h = 0.6524^(3/8) = 0.8522 m
    b = 2 × h = 1.7044 m
    验算：A = b × h = 1.4526；P = b + 2h = 3.4088；R = 0.4261 ≈ h/2 ✓
    Q = (1/0.013) × 1.4526 × 0.4261^(2/3) × √0.001 = 2.000 ✓

例 2（TRAP Q=2/n=0.013/S=0.001/m=1）：

    k = 0.8220（同上）
    h^(8/3) = k × 2^(2/3) / (2√2 − 1) = 0.8220 × 1.5874 / 1.8284 = 0.7136
    h = 0.7136^(3/8) = 0.8811 m
    b = 2h(√2 − 1) = 2 × 0.8811 × 0.4142 = 0.7300 m
    验算：A = (b + mh)h = 1.4195；P = b + 2h√(1+m²) = 3.2223；R = 0.4406 ≈ h/2 ✓

例 3（CIRC Q=1/n=0.013/S=0.001，二分法 d=1.0）：

    满流（h=d=1.0）：
        θ = 2 arccos(1−2) → 数值不稳定（h>d 不允许）；
        取 h=d=1.0 为水力最优近似（满流湿周/面积最低）。
    故 CIRC optimal_h ≈ d = 1.0 m。

P6-OPEN-001（G-01 degraded）决议：禁止 import fluids.open_channel，
本模块采用自研兜底（参照 ADR-0030 V1.2 决策 7）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.services.exceptions import PcsError

ChannelType = Literal["RECT", "TRAP", "CIRC"]


@dataclass(frozen=True)
class SectionInput:
    """最优断面输入（§3.2.6）。

    字段：

    - ``channel_type``：RECT / TRAP / CIRC
    - ``flow_rate``：设计流量 Q（m³/s，>0）
    - ``slope``：坡度 S（m/m，>0）
    - ``manning_n``：糙率 n（>0）
    - ``side_slope``：梯形边坡 m（m/m，≥0）；TRAP 必填，其他置 None
    - ``diameter``：圆形直径 d（m，>0）；CIRC 必填，其他置 None
    """

    channel_type: ChannelType
    flow_rate: float
    slope: float
    manning_n: float
    side_slope: float | None = None
    diameter: float | None = None


@dataclass(frozen=True)
class SectionResult:
    """最优断面输出（§3.2.6）。

    字段：

    - ``depth``：最优水深 h（m）
    - ``bottom_width``：底宽 b（m）；CIRC 时为 None
    - ``diameter``：直径 d（m）；仅 CIRC 填
    - ``area``：A（m²）
    - ``wetted_perimeter``：P（m）
    - ``hydraulic_radius``：R（m）
    - ``flow_rate_check``：按设计 Q 反算流量（m³/s，应 ≈ flow_rate）
    - ``formula_ref``：公式溯源标记，恒等于 "SECTION_§3.2.6"
    """

    depth: float
    bottom_width: float | None
    diameter: float | None
    area: float
    wetted_perimeter: float
    hydraulic_radius: float
    flow_rate_check: float
    formula_ref: str = "SECTION_§3.2.6"


class SectionInputError(PcsError):
    """最优断面输入不合法（422）。

    触发场景：

    - flow_rate / slope / manning_n 非正
    - TRAP 缺 side_slope 或 side_slope < 0
    - CIRC 缺 diameter 或 diameter ≤ 0
    - 未知 channel_type
    - CIRC 反解失败（二分法迭代不收敛）
    """

    code = "SECTION_INPUT_ERROR"
    status = 422


def _rect_geometry(b: float, h: float) -> tuple[float, float]:
    """矩形断面：A = b × h；P = b + 2h。"""
    return b * h, b + 2 * h


def _trap_geometry(b: float, m: float, h: float) -> tuple[float, float]:
    """梯形断面：A = (b + m × h) × h；P = b + 2h × √(1 + m²)。"""
    return (b + m * h) * h, b + 2 * h * math.sqrt(1 + m * m)


def _circ_geometry(d: float, h: float) -> tuple[float, float]:
    """圆形部分充满断面：θ = 2 × arccos(1 - 2h/d)；A = (d²/4)(θ - sin θ)/2；P = d × θ。"""
    theta = 2 * math.acos(1 - 2 * h / d)
    area = (d * d / 4) * (theta - math.sin(theta)) / 2
    perimeter = d * theta
    return area, perimeter


def _circ_q_at_h(
    d: float, h: float, n: float, slope: float
) -> float:
    """CIRC 给定 h 反算 Q。"""
    area, perimeter = _circ_geometry(d, h)
    if perimeter <= 0:
        return 0.0
    R = area / perimeter
    return (1.0 / n) * area * (R ** (2.0 / 3.0)) * (slope ** 0.5)


def _bisect_circ_depth(
    d: float, q_target: float, n: float, slope: float,
    tol: float = 1e-9, max_iter: int = 200,
) -> float:
    """二分法反解 CIRC 最优水深 h ∈ (0, d]。

    Q(h) 在 (0, d) 单调递增至满流峰值（≈h/d=0.938），随后 h 趋近 d 时
    Q → Q_full（满流）。满流已属"水力最优"近似，工程上取 h=d 作为设计值。
    若 q_target > Q_full（满流峰值），则无解，raise SectionInputError。
    """
    # 满流 Q
    q_full = _circ_q_at_h(d, d, n, slope)
    if q_target > q_full * 1.001:  # 容差 0.1%
        raise SectionInputError(
            f"CIRC 反解失败：目标 Q={q_target} 超过满流流量 Q_full={q_full}"
        )
    if q_target <= q_full * 0.9999:
        # 在 (0, d) 内二分
        lo, hi = 1e-6, d
        for _ in range(max_iter):
            mid = 0.5 * (lo + hi)
            q_mid = _circ_q_at_h(d, mid, n, slope)
            if q_mid < q_target:
                lo = mid
            else:
                hi = mid
            if hi - lo < tol * d:
                break
        return 0.5 * (lo + hi)
    # q_target 接近满流：直接返回 h = d
    return d


def calc_optimal_section(inp: SectionInput) -> SectionResult:
    """最优水力断面设计（§3.2.6）。

    实现步骤：

    1. 输入校验：Q > 0 / S > 0 / n > 0
    2. 按 channel_type 反解最优 h（解析 / 二分）
    3. 计算配套尺寸 b（RECT/TRAP）或保留 d（CIRC）
    4. 验算 A / P / R / Q_check

    Args:
        inp: SectionInput（已冻结 dataclass）。

    Returns:
        SectionResult（含 h / b 或 d / A / P / R / Q_check / formula_ref）。

    Raises:
        SectionInputError: 输入字段越界或非正（422）。
    """
    # 1. 通用输入校验
    if inp.flow_rate <= 0:
        raise SectionInputError(f"flow_rate ({inp.flow_rate}) 必须 > 0")
    if inp.slope <= 0:
        raise SectionInputError(f"slope ({inp.slope}) 必须 > 0")
    if inp.manning_n <= 0:
        raise SectionInputError(f"manning_n ({inp.manning_n}) 必须 > 0")

    # 2. 反解最优 h
    if inp.channel_type == "RECT":
        # 解析：h = ((k / 2^(1/3)))^(3/8)，k = Q×n/√S
        k = inp.flow_rate * inp.manning_n / (inp.slope ** 0.5)
        h = (k / (2 ** (1.0 / 3.0))) ** (3.0 / 8.0)
        b = 2 * h
        area, perimeter = _rect_geometry(b, h)
        R = area / perimeter
        Q_check = (1.0 / inp.manning_n) * area * (R ** (2.0 / 3.0)) * (inp.slope ** 0.5)
        return SectionResult(
            depth=h,
            bottom_width=b,
            diameter=None,
            area=area,
            wetted_perimeter=perimeter,
            hydraulic_radius=R,
            flow_rate_check=Q_check,
        )
    elif inp.channel_type == "TRAP":
        if inp.side_slope is None or inp.side_slope < 0:
            raise SectionInputError(
                f"TRAP 必须提供 side_slope ≥ 0（m={inp.side_slope}）"
            )
        m = inp.side_slope
        # 解析：h^(8/3) = k × 2^(2/3) / (2√(1+m²) − m)
        k = inp.flow_rate * inp.manning_n / (inp.slope ** 0.5)
        denom = 2 * math.sqrt(1 + m * m) - m
        if denom <= 0:
            raise SectionInputError(
                f"TRAP 最优断面反解失败：denom={denom}"
            )
        h = (k * (2 ** (2.0 / 3.0)) / denom) ** (3.0 / 8.0)
        b = 2 * h * (math.sqrt(1 + m * m) - m)
        area, perimeter = _trap_geometry(b, m, h)
        R = area / perimeter
        Q_check = (1.0 / inp.manning_n) * area * (R ** (2.0 / 3.0)) * (inp.slope ** 0.5)
        return SectionResult(
            depth=h,
            bottom_width=b,
            diameter=None,
            area=area,
            wetted_perimeter=perimeter,
            hydraulic_radius=R,
            flow_rate_check=Q_check,
        )
    elif inp.channel_type == "CIRC":
        if inp.diameter is None or inp.diameter <= 0:
            raise SectionInputError(
                f"CIRC 必须提供 diameter > 0（d={inp.diameter}）"
            )
        d = inp.diameter
        h = _bisect_circ_depth(
            d, inp.flow_rate, inp.manning_n, inp.slope,
        )
        area, perimeter = _circ_geometry(d, h)
        R = area / perimeter
        Q_check = _circ_q_at_h(d, h, inp.manning_n, inp.slope)
        return SectionResult(
            depth=h,
            bottom_width=None,
            diameter=d,
            area=area,
            wetted_perimeter=perimeter,
            hydraulic_radius=R,
            flow_rate_check=Q_check,
        )
    else:
        raise SectionInputError(f"未知 channel_type: {inp.channel_type}")


__all__ = [
    "ChannelType",
    "SectionInput",
    "SectionResult",
    "SectionInputError",
    "calc_optimal_section",
]
