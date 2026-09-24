"""Ruth 恒速过滤方程（SPEC §3.2.7 第二项）。

恒速过滤方程（恒流量 Q 供给）：

    t/V = (μ · α · c₀) / (2 · ΔP · A²) · V + μ · Rm / (ΔP · A)

或解出 ΔP 随 t 变化：

    ΔP = (μ · α · c₀ · V) / (2 · t · A²) + μ · Rm / t

本模块直接以流量 Q 推 ΔP：

    V = Q · t
    R_total = α · c₀ · V / A + Rm
    ΔP = μ · Q · R_total / A²

工程场景：板框过滤末期压榨（恒速泵入）+ 转鼓真空过滤（恒速吸滤）。

手算独立校核（3 例）：

例 1（Q=1e-3/A=1/μ=1e-3/α=1e10/c₀=10/Rm=1e10/t=3600）：

    V = Q · t = 1e-3 · 3600 = 3.6 m³
    R_total = 1e10 · 10 · 3.6 / 1 + 1e10 = 3.6e11 + 1e10 = 3.7e11 1/m
    ΔP = 1e-3 · 1e-3 · 3.7e11 / 1 = 3.7e5 Pa

例 2（α=0/c₀=0 无饼）：

    R_total = 0 · V / A + Rm = Rm
    ΔP = μ · Q · Rm / A² = 1e-3 · 1e-3 · 1e10 / 1 = 1e4 Pa（仅介质阻力）

例 3（t=1800 → t=3600）：

    V 翻倍 → R_total 翻倍（α · c₀ · V / A 项主导） → ΔP 近似翻倍

P6-OPEN-001（G-01 degraded）决议：禁止 import fluids.filtration，
本模块采用自研兜底（参照 ADR-0030 V1.2 决策 7）。
"""
from __future__ import annotations

from dataclasses import dataclass

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class RuthConstantRateInput:
    """Ruth 恒速过滤输入（§3.2.7 第二项）。

    字段：

    - ``constant_flow_rate``：Q（m³/s，>0）
    - ``filtration_area``：A（m²，>0）
    - ``filtrate_viscosity``：μ（Pa·s，>0）
    - ``cake_specific_resistance``：α（m/kg，≥0；=0 表示无饼理想）
    - ``solid_concentration``：c₀（kg/m³，≥0；=0 表示无饼理想）
    - ``medium_resistance``：Rm（1/m，≥0）
    - ``filtration_time``：t（s，≥0）
    """

    constant_flow_rate: float
    filtration_area: float
    filtrate_viscosity: float
    cake_specific_resistance: float
    solid_concentration: float
    medium_resistance: float
    filtration_time: float


@dataclass(frozen=True)
class RuthConstantRateResult:
    """Ruth 恒速过滤输出（§3.2.7）。

    字段：

    - ``instantaneous_pressure_drop``：ΔP（Pa）
    - ``cumulative_volume``：V = Q · t（m³）
    - ``resistance_total``：总阻力 R_total = α · c₀ · V / A + Rm（1/m）
    - ``formula_ref``：公式溯源标记，恒等于 "RUTH_CONST_RATE_§3.2.7"
    """

    instantaneous_pressure_drop: float
    cumulative_volume: float
    resistance_total: float
    formula_ref: str = "RUTH_CONST_RATE_§3.2.7"


class RuthConstantRateInputError(PcsError):
    """Ruth 恒速过滤输入不合法（422）。

    触发场景：

    - constant_flow_rate / filtration_area / filtrate_viscosity 非正
    - cake_specific_resistance / solid_concentration / medium_resistance / filtration_time < 0
    """

    code = "RUTH_CONST_RATE_INPUT_ERROR"
    status = 422


def calc_ruth_constant_rate(
    inp: RuthConstantRateInput,
) -> RuthConstantRateResult:
    """Ruth 恒速过滤瞬时压差计算（§3.2.7 第二项）。

    公式：V = Q · t；R_total = α · c₀ · V / A + Rm；ΔP = μ · Q · R_total / A²

    实现步骤：

    1. 输入校验：Q > 0 / A > 0 / μ > 0；α / c₀ / Rm / t ≥ 0
    2. 累计滤液体积 V = Q · t
    3. 总阻力 R_total = α · c₀ · V / A + Rm（无饼时 R_total = Rm）
    4. 瞬时压差 ΔP = μ · Q · R_total / A²

    Args:
        inp: RuthConstantRateInput（已冻结 dataclass）。

    Returns:
        RuthConstantRateResult（含 ΔP / V / R_total）。

    Raises:
        RuthConstantRateInputError: 输入字段越界或非正（422）。
    """
    if inp.constant_flow_rate <= 0:
        raise RuthConstantRateInputError(
            f"constant_flow_rate ({inp.constant_flow_rate}) 必须 > 0"
        )
    if inp.filtration_area <= 0:
        raise RuthConstantRateInputError(
            f"filtration_area ({inp.filtration_area}) 必须 > 0"
        )
    if inp.filtrate_viscosity <= 0:
        raise RuthConstantRateInputError(
            f"filtrate_viscosity ({inp.filtrate_viscosity}) 必须 > 0"
        )
    if inp.cake_specific_resistance < 0:
        raise RuthConstantRateInputError(
            f"cake_specific_resistance ({inp.cake_specific_resistance}) 必须 ≥ 0"
        )
    if inp.solid_concentration < 0:
        raise RuthConstantRateInputError(
            f"solid_concentration ({inp.solid_concentration}) 必须 ≥ 0"
        )
    if inp.medium_resistance < 0:
        raise RuthConstantRateInputError(
            f"medium_resistance ({inp.medium_resistance}) 必须 ≥ 0"
        )
    if inp.filtration_time < 0:
        raise RuthConstantRateInputError(
            f"filtration_time ({inp.filtration_time}) 必须 ≥ 0"
        )

    # 累计滤液体积 V = Q · t
    volume = inp.constant_flow_rate * inp.filtration_time

    # 总阻力 R_total = α · c₀ · V / A + Rm
    r_total = (
        inp.cake_specific_resistance
        * inp.solid_concentration
        * volume
        / inp.filtration_area
        + inp.medium_resistance
    )

    # 瞬时压差 ΔP = μ · Q · R_total / A²
    dp = (
        inp.filtrate_viscosity
        * inp.constant_flow_rate
        * r_total
        / (inp.filtration_area ** 2)
    )

    return RuthConstantRateResult(
        instantaneous_pressure_drop=dp,
        cumulative_volume=volume,
        resistance_total=r_total,
    )


__all__ = [
    "RuthConstantRateInput",
    "RuthConstantRateResult",
    "RuthConstantRateInputError",
    "calc_ruth_constant_rate",
]