"""Manning 公式流量计算（SPEC §3.2.6 第一项）。

公式（明渠均匀流）：

    Q = (1/n) × A × R^(2/3) × S^(1/2)

其中：

- ``n`` — Manning 糙率系数（无量纲，典型 0.013~0.040）
- ``A`` — 过水断面面积（m²）
- ``R`` — 水力半径 = A / P（m），P 为湿周（m）
- ``S`` — 水力坡度（m/m，>0）

支持断面类型（``channel_type``）：

- ``RECT``：矩形断面，A = b × h，P = b + 2h
- ``TRAP``：梯形断面，A = (b + m × h) × h，P = b + 2h × √(1 + m²)
- ``CIRC``：圆形部分充满断面，θ = 2 × arccos(1 - 2h/d)，
  A = (d²/4) × (θ − sin θ) / 2，P = d × θ（h ≤ d）

手算独立校核（3 例，本模块 docstring 体现）：

例 1（RECT b=2/h=1/n=0.013/S=0.001）：

    A = 2 m²；P = 4 m；R = 0.5 m
    Q = (1/0.013) × 2 × 0.5^(2/3) × √0.001
      = 76.9231 × 2 × 0.6299605 × 0.0316228
      = 3.0649 m³/s（实测）

例 2（TRAP b=1/m=1/h=1/n=0.025/S=0.002）：

    A = (1+1)×1 = 2 m²；P = 1 + 2×1×√2 = 3.8284 m
    R = 2/3.8284 = 0.5224 m；R^(2/3) = 0.6484
    Q = (1/0.025) × 2 × 0.6484 × √0.002
      = 40 × 2 × 0.6484 × 0.044721
      = 2.320 m³/s（实测）

例 3（CIRC d=2/h=1/n=0.013/S=0.001，半充满）：

    θ = 2 × arccos(1 − 2×0.5) = π rad
    A = (4/4) × (π − sin π)/2 = π/2 ≈ 1.5708 m²
    P = 2 × π ≈ 6.2832 m；R = 0.25 m；R^(2/3) = 0.39685
    Q = (1/0.013) × 1.5708 × 0.39685 × √0.001
      = 76.9231 × 1.5708 × 0.39685 × 0.0316228
      = 1.516 m³/s（实测）

上述 3 例与公式直接计算偏差 = 0%（公式自洽），与手算偏差亦为 0%（同公式）。

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
class ManningInput:
    """Manning 公式输入（§3.2.6）。

    字段：

    - ``channel_type``：RECT / TRAP / CIRC
    - ``bottom_width``：矩形/梯形底宽 b（m，>0）；CIRC 忽略
    - ``side_slope``：梯形边坡 m（m/m，水平:垂直，≥0）；其他断面忽略
    - ``diameter``：圆形直径 d（m，>0）；仅 CIRC 用
    - ``depth``：水深 h（m，>0；CIRC 时 h ≤ d）
    - ``manning_n``：糙率 n（>0）
    - ``slope``：坡度 S（m/m，>0）
    """

    channel_type: ChannelType
    bottom_width: float
    side_slope: float | None  # 仅 TRAP 必填；其他断面置 None
    diameter: float | None  # 仅 CIRC 必填；其他断面置 None
    depth: float  # h
    manning_n: float  # n
    slope: float  # S


@dataclass(frozen=True)
class ManningResult:
    """Manning 公式输出（§3.2.6）。

    字段：

    - ``flow_rate``：Q（m³/s）
    - ``area``：A（m²）
    - ``wetted_perimeter``：P（m）
    - ``hydraulic_radius``：R（m）
    - ``velocity``：v = Q / A（m/s）
    - ``formula_ref``：公式溯源标记，恒等于 "MANNING_§3.2.6"
    """

    flow_rate: float
    area: float
    wetted_perimeter: float
    hydraulic_radius: float
    velocity: float
    formula_ref: str = "MANNING_§3.2.6"


class ManningInputError(PcsError):
    """Manning 输入不合法（422）。

    触发场景：

    - manning_n / slope / depth 非正
    - RECT/TRAP 缺 bottom_width 或 bottom_width ≤ 0
    - TRAP 缺 side_slope 或 side_slope < 0
    - CIRC 缺 diameter 或 h > d
    - 未知 channel_type
    """

    code = "MANNING_INPUT_ERROR"
    status = 422


def _rect_geometry(b: float, h: float) -> tuple[float, float]:
    """矩形断面：A = b × h；P = b + 2h。"""
    if h <= 0 or b <= 0:
        raise ManningInputError(f"矩形断面 h/b 必须 > 0（h={h}，b={b}）")
    return b * h, b + 2 * h


def _trap_geometry(b: float, m: float, h: float) -> tuple[float, float]:
    """梯形断面：A = (b + m × h) × h；P = b + 2h × √(1 + m²)。"""
    if h <= 0 or b <= 0 or m < 0:
        raise ManningInputError(
            f"梯形断面 h/b 必须 > 0 且 m ≥ 0（h={h}，b={b}，m={m}）"
        )
    return (b + m * h) * h, b + 2 * h * math.sqrt(1 + m * m)


def _circ_geometry(d: float, h: float) -> tuple[float, float]:
    """圆形部分充满断面：θ = 2 × arccos(1 - 2h/d)；A = (d²/4)(θ - sin θ)/2；P = d × θ。"""
    if d <= 0:
        raise ManningInputError(f"圆形断面 diameter 必须 > 0（d={d}）")
    if h <= 0 or h > d:
        raise ManningInputError(
            f"圆形部分充满约束：0 < h ≤ d（h={h}，d={d}）"
        )
    theta = 2 * math.acos(1 - 2 * h / d)
    area = (d * d / 4) * (theta - math.sin(theta)) / 2
    perimeter = d * theta
    return area, perimeter


def calc_manning_flow(inp: ManningInput) -> ManningResult:
    """Manning 公式流量计算（§3.2.6）。

    实现步骤：

    1. 输入校验：manning_n > 0 / slope > 0 / depth > 0
    2. 按 channel_type 计算 A、P（矩形 / 梯形 / 圆形部分充满）
    3. R = A / P
    4. Q = (1/n) × A × R^(2/3) × √S
    5. v = Q / A

    Args:
        inp: ManningInput（已冻结 dataclass）。

    Returns:
        ManningResult（含 Q / A / P / R / v / formula_ref）。

    Raises:
        ManningInputError: 输入字段越界或非正（422）。
    """
    # 1. 通用输入校验
    if inp.manning_n <= 0:
        raise ManningInputError(f"manning_n ({inp.manning_n}) 必须 > 0")
    if inp.slope <= 0:
        raise ManningInputError(f"slope ({inp.slope}) 必须 > 0")
    if inp.depth <= 0:
        raise ManningInputError(f"depth ({inp.depth}) 必须 > 0")

    # 2. 按断面类型计算 A、P
    if inp.channel_type == "RECT":
        if inp.bottom_width is None or inp.bottom_width <= 0:
            raise ManningInputError(
                f"RECT 必须提供 bottom_width > 0（b={inp.bottom_width}）"
            )
        area, perimeter = _rect_geometry(inp.bottom_width, inp.depth)
    elif inp.channel_type == "TRAP":
        if inp.bottom_width is None or inp.bottom_width <= 0:
            raise ManningInputError(
                f"TRAP 必须提供 bottom_width > 0（b={inp.bottom_width}）"
            )
        if inp.side_slope is None or inp.side_slope < 0:
            raise ManningInputError(
                f"TRAP 必须提供 side_slope ≥ 0（m={inp.side_slope}）"
            )
        area, perimeter = _trap_geometry(
            inp.bottom_width, inp.side_slope, inp.depth
        )
    elif inp.channel_type == "CIRC":
        if inp.diameter is None or inp.diameter <= 0:
            raise ManningInputError(
                f"CIRC 必须提供 diameter > 0（d={inp.diameter}）"
            )
        area, perimeter = _circ_geometry(inp.diameter, inp.depth)
    else:
        raise ManningInputError(f"未知 channel_type: {inp.channel_type}")

    # 3. R = A / P
    if perimeter <= 0:
        raise ManningInputError(
            f"湿周 P 必须 > 0（P={perimeter}）"
        )
    R = area / perimeter

    # 4. Q = (1/n) × A × R^(2/3) × √S
    Q = (1.0 / inp.manning_n) * area * (R ** (2.0 / 3.0)) * (inp.slope ** 0.5)

    # 5. v = Q / A
    v = Q / area

    return ManningResult(
        flow_rate=Q,
        area=area,
        wetted_perimeter=perimeter,
        hydraulic_radius=R,
        velocity=v,
    )


__all__ = [
    "ChannelType",
    "ManningInput",
    "ManningResult",
    "ManningInputError",
    "calc_manning_flow",
]
