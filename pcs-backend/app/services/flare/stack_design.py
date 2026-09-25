"""FLARE_SYS 火炬高度与地面辐射计算。

按 API 521 7th Ed.：
- §7.4.2.2 Stack Height Determination（Pasquill-Gifford 大气稳定度修正）
- §7.4.2.3 Thermal Radiation at Grade（点源模型 + BEDD 限值校验）

输入 Q_total_mw / MW 来自 Task 19 aggregate_flare_load（总泄放面积 × 燃烧热值转换）。
H_stack 落库由 Task 23 flare_persist 统一处理。

公式溯源：API_521_§7.4.2.2 + API_521_§7.4.2.3；BEDD 限值依 GB 50489 / API 521 默认。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.exceptions import PcsError

# 物理与工程常数
_H_MIN_DEFAULT = 10.0  # m（良好工程实践最小高度，API 521 推荐）
_FLAME_HEIGHT_FRAC = 0.5  # 火焰长度 / 火炬高度（工程经验）
_FRACTION_RAD_DEFAULT = 0.20  # 火焰辐射分数（API 521 默认）
_BEDD_LIMIT_PROPERTY_LINE_KW_M2 = 4.73  # kW/m²（property line / 公众区域）
_BEDD_LIMIT_PERSONNEL_KW_M2 = 6.31  # kW/m²（人员可达区）
_BEDD_LIMIT_EMERGENCY_KW_M2 = 12.6  # kW/m²（应急通道）


# Pasquill-Gifford 稳定度等级 → dispersion_factor
_STABILITY_DISPERSION_FACTOR = {
    "A": 1.5,  # 极不稳定
    "B": 1.3,  # 不稳定
    "C": 1.15,  # 弱不稳定
    "D": 1.0,  # 中性（默认）
    "E": 0.85,  # 稳定
    "F": 0.7,  # 极稳定
}


# ───────────────────────────── Stack Height ─────────────────────────────


@dataclass(frozen=True)
class StackHeightInput:
    """火炬高度计算输入。

    字段：
    - total_heat_release_mw: 总热释放速率 MW（来自 Task 19 推导）
    - stability_class: Pasquill-Gifford 大气稳定度等级（A–F，默认 D 中性）
    - h_min_engineering_m: 工程最小高度 m（默认 10 m，范围 [5, 200]）
    - wind_speed_m_s: 设计风速 m/s（默认 5；范围 [0, 50]）
    """

    total_heat_release_mw: float  # MW（来自 Task 19 推导）
    stability_class: str = "D"  # Pasquill-Gifford（A-F，默认 D）
    h_min_engineering_m: float = _H_MIN_DEFAULT  # m（工程最小）
    wind_speed_m_s: float = 5.0  # m/s（设计风速）


@dataclass(frozen=True)
class StackHeightResult:
    """火炬高度计算结果（API 521 §7.4.2.2）。

    字段：
    - h_stack_m: 推荐火炬高度 m（max(h_min, h_eff)）
    - h_effective_m: 含 dispersion_factor 的有效高度 m
    - buoyancy_rise_m: 浮升抬升 ΔH_buoy = 1.5 × √Q_total m
    - dispersion_factor: Pasquill-Gifford 修正因子（依 stability_class）
    - formula_ref: 公式溯源标记 "API_521_§7.4.2.2"
    """

    h_stack_m: float  # m（推荐高度）
    h_effective_m: float  # m（含 dispersion_factor）
    buoyancy_rise_m: float  # m（浮升抬升 ΔH_buoy）
    dispersion_factor: float  # (-)（依 stability_class）
    formula_ref: str  # "API_521_§7.4.2.2"


# ───────────────────────────── Radiation Check ─────────────────────────────


@dataclass(frozen=True)
class RadiationCheckInput:
    """地面辐射计算输入（API 521 §7.4.2.3）。

    字段：
    - q_radiated_mw: 火焰辐射热释放 MW（Q_total × fraction_rad）
    - h_stack_m: 火炬高度 m（来自 stack_height 计算或外部输入）
    - receptor_distance_m: 受体距火炬底水平距离 m（property line）
    - flame_height_m: 火焰长度 m（None 则自动用 H_stack × 0.5）
    - tilt_angle_deg: 火焰倾斜角 度（默认 0 无风）
    - bedd_limit_kw_m2: BEDD 限值 kW/m²（property line 4.73 / personnel 6.31 / emergency 12.6）
    """

    q_radiated_mw: float  # MW（火焰辐射热释放）
    h_stack_m: float  # m（火炬高度）
    receptor_distance_m: float  # m（受体距火炬底水平距离）
    flame_height_m: float | None = None  # m（默认 None 自动用 H_stack × 0.5）
    tilt_angle_deg: float = 0.0  # 度（火焰倾斜，默认 0 无风）
    bedd_limit_kw_m2: float = _BEDD_LIMIT_PROPERTY_LINE_KW_M2  # kW/m²（property line）


@dataclass(frozen=True)
class RadiationCheckResult:
    """地面辐射计算结果（API 521 §7.4.2.3 + BEDD）。

    字段：
    - q_at_receptor_w_m2: 受体处辐射强度 W/m²
    - q_at_receptor_kw_m2: 同上 kW/m²（常用）
    - bedd_compliant: 是否满足 BEDD 限值（True = q ≤ bedd_limit）
    - bedd_limit_kw_m2: BEDD 限值 kW/m²（输入阈值）
    - flame_center_height_m: 火焰中心高度 m
    - slant_distance_m: 受体处斜距 R m
    - formula_ref: 公式溯源标记 "API_521_§7.4.2.3+BEDD"
    """

    q_at_receptor_w_m2: float  # W/m²
    q_at_receptor_kw_m2: float  # kW/m²
    bedd_compliant: bool  # True = q ≤ bedd_limit
    bedd_limit_kw_m2: float  # kW/m²（输入阈值）
    flame_center_height_m: float  # m（火焰中心高度）
    slant_distance_m: float  # m（受体处斜距 R）
    formula_ref: str  # "API_521_§7.4.2.3+BEDD"


# ───────────────────────────── 综合响应 ─────────────────────────────


@dataclass(frozen=True)
class StackDesignResult:
    """stack_height + radiation_check 综合计算结果。

    字段：
    - stack_height: Stack Height 子结果（API 521 §7.4.2.2）
    - radiation: Radiation Check 子结果（API 521 §7.4.2.3 + BEDD）
    - formula_ref: 综合公式溯源标记 "API_521_§7.4.2.2+§7.4.2.3"
    """

    stack_height: StackHeightResult
    radiation: RadiationCheckResult
    formula_ref: str  # "API_521_§7.4.2.2+§7.4.2.3"


# ───────────────────────────── 异常类 ─────────────────────────────


class StackHeightInputError(PcsError):
    """stack_height 输入不合法（422）。

    触发场景：total_heat_release_mw <= 0、stability_class 不在 {A..F}、
    h_min_engineering_m 超出工程范围 [5, 200]、wind_speed_m_s 超出 (0, 50] 等。
    """

    code = "FLARE_STACK_HEIGHT_INPUT_ERROR"
    status = 422


class RadiationCheckInputError(PcsError):
    """radiation_check 输入不合法（422）。

    触发场景：q_radiated_mw <= 0、h_stack_m <= 0、receptor_distance_m <= 0、
    bedd_limit_kw_m2 <= 0 等。
    """

    code = "FLARE_RADIATION_INPUT_ERROR"
    status = 422


# ───────────────────────────── 计算函数 ─────────────────────────────


def calc_stack_height(inp: StackHeightInput) -> StackHeightResult:
    """API 521 §7.4.2.2 火炬高度计算。

    实现步骤：
    1. 浮升抬升 ΔH_buoy = 1.5 × √Q_total（API 521 简化经验式）
    2. 有效高度 H_eff = h_min + ΔH_buoy × dispersion_factor(stability_class)
    3. 设计高度 H_stack = max(h_min, H_eff)

    Args:
        inp: StackHeightInput（已冻结 dataclass）。

    Returns:
        StackHeightResult（含 h_stack_m / h_effective_m / buoyancy_rise_m /
        dispersion_factor）。

    Raises:
        StackHeightInputError: 输入字段越界或非正（422）。
    """
    # 输入校验
    if inp.total_heat_release_mw <= 0:
        raise StackHeightInputError(
            f"total_heat_release_mw={inp.total_heat_release_mw} 必须 > 0"
        )
    if inp.stability_class not in _STABILITY_DISPERSION_FACTOR:
        raise StackHeightInputError(
            f"stability_class={inp.stability_class} 不在 {{A,B,C,D,E,F}}"
        )
    if inp.h_min_engineering_m < 5.0 or inp.h_min_engineering_m > 200.0:
        raise StackHeightInputError(
            f"h_min_engineering_m={inp.h_min_engineering_m} 超出工程范围 [5, 200]"
        )
    if inp.wind_speed_m_s < 0 or inp.wind_speed_m_s > 50.0:
        raise StackHeightInputError(
            f"wind_speed_m_s={inp.wind_speed_m_s} 超出工程范围 [0, 50]"
        )

    dispersion_factor = _STABILITY_DISPERSION_FACTOR[inp.stability_class]
    # 浮升抬升 ΔH_buoy = 1.5 × √Q_total（API 521 简化经验式）
    buoyancy_rise = 1.5 * (inp.total_heat_release_mw ** 0.5)
    # 有效高度
    h_effective = inp.h_min_engineering_m + buoyancy_rise * dispersion_factor
    # 设计高度（取大）
    h_stack = max(inp.h_min_engineering_m, h_effective)

    return StackHeightResult(
        h_stack_m=h_stack,
        h_effective_m=h_effective,
        buoyancy_rise_m=buoyancy_rise,
        dispersion_factor=dispersion_factor,
        formula_ref="API_521_§7.4.2.2",
    )


def calc_radiation_check(inp: RadiationCheckInput) -> RadiationCheckResult:
    """API 521 §7.4.2.3 地面辐射 + BEDD 限值校验。

    公式（点源模型）：
        θ_rad = tilt_angle_deg × π / 180
        火焰中心高度 H_flame_center = H_stack + flame_height × cos(θ_rad) / 2
        斜距 R = sqrt(receptor_distance² + H_flame_center²)
        辐射强度 q = Q_radiated × 1e6 × cos(θ_rad) / (4π × R²)  [W/m²]
        BEDD 校验：q_kw_m2 ≤ bedd_limit_kw_m2

    Args:
        inp: RadiationCheckInput（已冻结 dataclass）。

    Returns:
        RadiationCheckResult（含 q_at_receptor_w_m2 / q_at_receptor_kw_m2 /
        bedd_compliant / flame_center_height_m / slant_distance_m）。

    Raises:
        RadiationCheckInputError: 输入字段越界或非正（422）。
    """
    if inp.q_radiated_mw <= 0:
        raise RadiationCheckInputError(
            f"q_radiated_mw={inp.q_radiated_mw} 必须 > 0"
        )
    if inp.h_stack_m <= 0:
        raise RadiationCheckInputError(f"h_stack_m={inp.h_stack_m} 必须 > 0")
    if inp.receptor_distance_m <= 0:
        raise RadiationCheckInputError(
            f"receptor_distance_m={inp.receptor_distance_m} 必须 > 0"
        )
    if inp.bedd_limit_kw_m2 <= 0:
        raise RadiationCheckInputError(
            f"bedd_limit_kw_m2={inp.bedd_limit_kw_m2} 必须 > 0"
        )

    # 火焰高度（默认 0.5 × H_stack）
    flame_h = (
        inp.flame_height_m
        if inp.flame_height_m is not None
        else inp.h_stack_m * _FLAME_HEIGHT_FRAC
    )
    # 倾斜角
    tilt_rad = math.radians(inp.tilt_angle_deg)
    cos_tilt = math.cos(tilt_rad)
    # 火焰中心高度
    h_flame_center = inp.h_stack_m + flame_h * cos_tilt / 2.0
    # 斜距
    slant_distance = math.sqrt(inp.receptor_distance_m ** 2 + h_flame_center ** 2)
    # 点源辐射（W/m²）
    q_w_m2 = (
        inp.q_radiated_mw * 1.0e6 * cos_tilt / (4.0 * math.pi * slant_distance ** 2)
    )
    q_kw_m2 = q_w_m2 / 1000.0

    return RadiationCheckResult(
        q_at_receptor_w_m2=q_w_m2,
        q_at_receptor_kw_m2=q_kw_m2,
        bedd_compliant=q_kw_m2 <= inp.bedd_limit_kw_m2,
        bedd_limit_kw_m2=inp.bedd_limit_kw_m2,
        flame_center_height_m=h_flame_center,
        slant_distance_m=slant_distance,
        formula_ref="API_521_§7.4.2.3+BEDD",
    )


def calc_stack_design(
    stack: StackHeightInput,
    radiation: RadiationCheckInput,
) -> StackDesignResult:
    """综合 stack_height + radiation_check。

    调用 ``calc_stack_height`` 与 ``calc_radiation_check`` 后组合为
    ``StackDesignResult``。

    注意：endpoint 调用时若需要把 stack_height 结果中的 h_stack 串入
    radiation_check，须在 endpoint 内**先单独调 calc_stack_height** 拿到
    h_stack_m，再构造含 h_stack_m 的 RadiationCheckInput 调用
    calc_radiation_check —— 不可对 calc_stack_design 直接传 h_stack_m=0.0
    占位（详见 api/v1/flare.py calculate_stack_design 实现）。

    Args:
        stack: Stack Height 子输入（StackHeightInput）。
        radiation: Radiation Check 子输入（RadiationCheckInput）。

    Returns:
        StackDesignResult（含 stack_height / radiation 子结果与综合 formula_ref）。

    Raises:
        StackHeightInputError / RadiationCheckInputError: 任一子计算输入不合法（422）。
    """
    stack_r = calc_stack_height(stack)
    radiation_r = calc_radiation_check(radiation)
    return StackDesignResult(
        stack_height=stack_r,
        radiation=radiation_r,
        formula_ref="API_521_§7.4.2.2+§7.4.2.3",
    )


__all__ = [
    "StackHeightInput",
    "StackHeightResult",
    "RadiationCheckInput",
    "RadiationCheckResult",
    "StackDesignResult",
    "StackHeightInputError",
    "RadiationCheckInputError",
    "calc_stack_height",
    "calc_radiation_check",
    "calc_stack_design",
]