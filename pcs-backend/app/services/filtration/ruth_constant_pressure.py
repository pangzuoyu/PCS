"""Ruth 恒压过滤方程（SPEC §3.2.7 第一项）。

经典恒压过滤方程（Ruth 1935）：

    (V + V₀)² = k · A² · t + V₀²

其中：

- ``V`` — 累计滤液体积（m³）
- ``V₀`` — 虚拟滤液体积（m³，等价于介质阻力，对应 t=0 时曲线截距）
- ``k`` — Ruth 系数（m²/s），k = 2 · ΔP / (μ · α · c₀)
    - ``ΔP`` — 过滤压差（Pa）
    - ``μ`` — 滤液粘度（Pa·s）
    - ``α`` — 滤饼比阻（m/kg）
    - ``c₀`` — 单位体积滤液对应的固体质量（kg/m³）
- ``A`` — 过滤面积（m²）
- ``t`` — 过滤时间（s）

简化形式：

    t = μ · α · c₀ · V² / (2 · ΔP · A²) + μ · Rm · V / (ΔP · A)

解出 V：

    V = √(k · A² · t + V₀²) − V₀

其中 V₀ = μ · Rm · A / (α · c₀)。

手算独立校核（3 例）：

例 1（A=1/ΔP=1e5/μ=1e-3/α=1e10/c₀=10/Rm=1e10/t=3600）：

    k = 2 · 1e5 / (1e-3 · 1e10 · 10) = 2e5 / 1e8 = 2e-3 m²/s
    V₀ = 1e-3 · 1e10 · 1 / (1e10 · 10) = 1e7 / 1e11 = 1e-4 m³
    k·A²·t + V₀² = 2e-3 · 1 · 3600 + (1e-4)²
                  = 7.2 + 1e-8 ≈ 7.2
    V = √7.2 − 1e-4 ≈ 2.6833 − 1e-4 ≈ 2.6832 m³

例 2（α=0/c₀=0 无饼理想）：

    has_cake = False → V₀ = 0；k_proxy = 2 · ΔP / μ = 2 · 1e5 / 1e-3 = 2e8（占位）
    V = √(2e8 · 1 · 3600 + 0) − 0 = √7.2e11 ≈ 8.4853e5 m³

    真实"理想"路径（V = ΔP · A · t / (μ · Rm)）：
        V_ideal = 1e5 · 1 · 3600 / (1e-3 · 1e10) = 3.6e-3 m³

    注：无饼路径下本模块取 k = 2·ΔP/μ（占位）与"理想"公式
    不在同一理论域；用户须明确选择有饼路径。

例 3（t=0）：

    V = √(0 + V₀²) − V₀ = V₀ − V₀ = 0（介质阻力截距回零）

    Q_avg = V / t = 0 / 0 → 定义为 0（无时间无流量）

P6-OPEN-001（G-01 degraded）决议：禁止 import fluids.filtration，
本模块采用自研兜底（参照 ADR-0030 V1.2 决策 7）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class RuthConstantPressureInput:
    """Ruth 恒压过滤输入（§3.2.7 第一项）。

    字段：

    - ``filtration_area``：A（m²，>0）
    - ``delta_pressure``：ΔP（Pa，>0）
    - ``filtrate_viscosity``：μ（Pa·s，>0）
    - ``cake_specific_resistance``：α（m/kg，≥0；=0 表示无饼理想）
    - ``solid_concentration``：c₀（kg/m³，≥0；=0 表示无饼理想）
    - ``medium_resistance``：Rm（1/m，≥0）
    - ``filtration_time``：t（s，≥0）
    """

    filtration_area: float
    delta_pressure: float
    filtrate_viscosity: float
    cake_specific_resistance: float
    solid_concentration: float
    medium_resistance: float
    filtration_time: float


@dataclass(frozen=True)
class RuthConstantPressureResult:
    """Ruth 恒压过滤输出（§3.2.7）。

    字段：

    - ``filtrate_volume``：V（m³）
    - ``average_flow_rate``：Q_avg = V / t（m³/s；t=0 时为 0）
    - ``ruth_constant_k``：k（m²/s；无饼路径下取占位 2·ΔP / μ）
    - ``virtual_volume_v0``：V₀（m³）
    - ``formula_ref``：公式溯源标记，恒等于 "RUTH_CONST_PRESSURE_§3.2.7"
    """

    filtrate_volume: float
    average_flow_rate: float
    ruth_constant_k: float
    virtual_volume_v0: float
    formula_ref: str = "RUTH_CONST_PRESSURE_§3.2.7"


class RuthConstantPressureInputError(PcsError):
    """Ruth 恒压过滤输入不合法（422）。

    触发场景：

    - filtration_area / delta_pressure / filtrate_viscosity 非正
    - cake_specific_resistance / solid_concentration / medium_resistance / filtration_time < 0
    """

    code = "RUTH_CONST_PRESSURE_INPUT_ERROR"
    status = 422


def calc_ruth_constant_pressure(
    inp: RuthConstantPressureInput,
) -> RuthConstantPressureResult:
    """Ruth 恒压过滤累计滤液体积计算（§3.2.7 第一项）。

    公式：(V + V₀)² = k · A² · t + V₀² → V = √(k · A² · t + V₀²) − V₀

    实现步骤：

    1. 输入校验：A > 0 / ΔP > 0 / μ > 0；α / c₀ / Rm / t ≥ 0
    2. Ruth 系数 k = 2 · ΔP / (μ · α · c₀)；α 或 c₀ 为 0 时取 k = 2 · ΔP / μ（占位）
    3. 虚拟滤液体积 V₀ = μ · Rm · A / (α · c₀)；α 或 c₀ 为 0 时取 V₀ = 0
    4. V = √(k · A² · t + V₀²) − V₀（钳位 ≥ 0）
    5. Q_avg = V / t；t = 0 时 Q_avg = 0

    Args:
        inp: RuthConstantPressureInput（已冻结 dataclass）。

    Returns:
        RuthConstantPressureResult（含 V / Q_avg / k / V₀）。

    Raises:
        RuthConstantPressureInputError: 输入字段越界或非正（422）。
    """
    if inp.filtration_area <= 0:
        raise RuthConstantPressureInputError(
            f"filtration_area ({inp.filtration_area}) 必须 > 0"
        )
    if inp.delta_pressure <= 0:
        raise RuthConstantPressureInputError(
            f"delta_pressure ({inp.delta_pressure}) 必须 > 0"
        )
    if inp.filtrate_viscosity <= 0:
        raise RuthConstantPressureInputError(
            f"filtrate_viscosity ({inp.filtrate_viscosity}) 必须 > 0"
        )
    if inp.cake_specific_resistance < 0:
        raise RuthConstantPressureInputError(
            f"cake_specific_resistance ({inp.cake_specific_resistance}) 必须 ≥ 0"
        )
    if inp.solid_concentration < 0:
        raise RuthConstantPressureInputError(
            f"solid_concentration ({inp.solid_concentration}) 必须 ≥ 0"
        )
    if inp.medium_resistance < 0:
        raise RuthConstantPressureInputError(
            f"medium_resistance ({inp.medium_resistance}) 必须 ≥ 0"
        )
    if inp.filtration_time < 0:
        raise RuthConstantPressureInputError(
            f"filtration_time ({inp.filtration_time}) 必须 ≥ 0"
        )

    has_cake = inp.cake_specific_resistance > 0 and inp.solid_concentration > 0

    # Ruth 系数 k = 2 · ΔP / (μ · α · c₀)；无饼时取占位 k_proxy = 2 · ΔP / μ
    if has_cake:
        k = (
            2.0 * inp.delta_pressure
            / (
                inp.filtrate_viscosity
                * inp.cake_specific_resistance
                * inp.solid_concentration
            )
        )
        v0 = (
            inp.filtrate_viscosity
            * inp.medium_resistance
            * inp.filtration_area
            / (inp.cake_specific_resistance * inp.solid_concentration)
        )
    else:
        # 无饼：V₀ = 0；k 仅作占位（仍参与 V = √(k·A²·t) 形式）
        k = 2.0 * inp.delta_pressure / inp.filtrate_viscosity
        v0 = 0.0

    # 累计滤液体积：(V + V₀)² = k · A² · t + V₀² → V = √(k · A² · t + V₀²) − V₀
    rhs = k * (inp.filtration_area ** 2) * inp.filtration_time + v0 * v0
    if rhs < 0:
        raise RuthConstantPressureInputError(
            f"内部计算溢出（rhs={rhs} < 0）"
        )
    volume = math.sqrt(rhs) - v0
    if volume < 0:
        volume = 0.0

    q_avg = volume / inp.filtration_time if inp.filtration_time > 0 else 0.0

    return RuthConstantPressureResult(
        filtrate_volume=volume,
        average_flow_rate=q_avg,
        ruth_constant_k=k,
        virtual_volume_v0=v0,
    )


__all__ = [
    "RuthConstantPressureInput",
    "RuthConstantPressureResult",
    "RuthConstantPressureInputError",
    "calc_ruth_constant_pressure",
]