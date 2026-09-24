"""COOL_TOWER 冷却塔特性曲线（CTI ATC-105）。

按 SPEC §3.2.4.2 P6-CT-001：
    KaV/L = C × (L/G)^(−m)
    其中：
        C — 塔特性系数（厂商提供；典型逆流 1.0~2.0）
        m — 指数（逆流 0.6~0.8；横流 0.5~0.7）
        L/G — 水气比（无量纲）
    curve_source — "CTI" 典型值 / "MANUFACTURER" 厂商实测

P6-OPEN-003 关闭：默认 CTI ATC-105 典型值；curve_source="CTI" /
"MANUFACTURER" 双模，透传供审计追踪。

不依赖 DB（纯计算函数）；输入 l_g_ratio 来自上游工艺计算或 Karoske 联动。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.services.exceptions import PcsError

# curve_source 双模：CTI 典型值 / MANUFACTURER 厂商实测
CurveSource = Literal["CTI", "MANUFACTURER"]


@dataclass(frozen=True)
class TowerCurveInput:
    """冷却塔特性曲线输入。

    字段：
    - c: 塔特性系数（厂商提供；典型逆流 1.0~2.0）
    - m: 指数（逆流 0.6~0.8；横流 0.5~0.7）
    - l_g_ratio: 水气比 L/G（无量纲）
    - curve_source: "CTI"（默认典型值）/ "MANUFACTURER"（厂商实测）
    """

    c: float  # 塔特性系数
    m: float  # 指数
    l_g_ratio: float  # 水气比 L/G（无量纲）
    curve_source: CurveSource = "CTI"  # "CTI" / "MANUFACTURER"


@dataclass(frozen=True)
class TowerCurveResult:
    """冷却塔特性曲线输出。

    字段：
    - kav_l: 冷却数 KaV/L（无量纲）
    - curve_source: 透传（用于审计）
    - formula_ref: 公式溯源标记 "API_CTI_ATC-105_§3.2.4.2"
    """

    kav_l: float  # 冷却数（无量纲）
    curve_source: CurveSource  # 透传
    formula_ref: str = "API_CTI_ATC-105_§3.2.4.2"


class TowerCurveInputError(PcsError):
    """冷却塔特性曲线输入不合法（422）。

    触发场景：c <= 0 / m < 0 / l_g_ratio <= 0。
    """

    code = "TOWER_CURVE_INPUT_ERROR"
    status = 422


def calc_tower_curve_kav_l(inp: TowerCurveInput) -> TowerCurveResult:
    """CTI ATC-105 特性曲线 KaV/L = C × (L/G)^(−m)。

    实现步骤（SPEC §3.2.4.2）：
    1. 输入校验：c > 0 / m ≥ 0 / l_g_ratio > 0
    2. KaV/L = c × (l_g_ratio)^(−m)
    3. 透传 curve_source 与 formula_ref 供审计

    Args:
        inp: TowerCurveInput（已冻结 dataclass）。

    Returns:
        TowerCurveResult（含 kav_l / curve_source / formula_ref）。

    Raises:
        TowerCurveInputError: 输入字段越界或非正（422）。
    """
    # 输入校验
    if inp.c <= 0:
        raise TowerCurveInputError(f"c ({inp.c}) 必须 > 0")
    if inp.m < 0:
        raise TowerCurveInputError(f"m ({inp.m}) 必须 ≥ 0")
    if inp.l_g_ratio <= 0:
        raise TowerCurveInputError(
            f"l_g_ratio ({inp.l_g_ratio}) 必须 > 0"
        )

    # KaV/L = c × (L/G)^(−m)
    kav_l = inp.c * (inp.l_g_ratio ** (-inp.m))
    return TowerCurveResult(
        kav_l=kav_l,
        curve_source=inp.curve_source,
    )


__all__ = [
    "CurveSource",
    "TowerCurveInput",
    "TowerCurveResult",
    "TowerCurveInputError",
    "calc_tower_curve_kav_l",
]
