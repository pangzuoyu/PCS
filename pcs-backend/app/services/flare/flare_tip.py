"""FLARE_SYS 火炬尖端 tip 速度/马赫数计算。

按 API 521 7th Ed. §5.15.6 — 火焰尖端（flare tip）的气体速度与马赫数。
复用 Task 20 header_sizing 的等温声速 + 理想气体密度公式（API 521 §5.15.4），
按尖端工况（header 出口 P/T）计算 tip 点速度分布。

公式溯源（API_521_§5.15.6）：
- 等温声速 a = sqrt(k * R * T / MW)（与 Task 20 一致）
- 等温理想气体密度 rho = P * MW / (R * T)（与 Task 20 一致）
- u_tip = M_target * a（按设计点 Mach 反求目标速度）
- actual_mach = u / a ≡ M_target（构造恒等）
- A_tip = π * D_tip² / 4（尖端与总管同径；单点 tip 假设）
- G = ρ * u（质量流速）

不依赖 DB（纯计算函数）；输入 D_tip 来自 Task 20 header_sizing 输出。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.exceptions import PcsError

# 通用气体常数 R = 8314.462618 J/(kmol·K)（CODATA 2018 常用值；与 header_sizing 一致）
_R_UNIVERSAL = 8314.462618  # J/(kmol·K)


@dataclass(frozen=True)
class FlareTipInput:
    """flare_tip 输入。

    字段：
    - header_diameter_m: 火炬总管直径 m（来自 Task 20 header_sizing）
    - mw_kg_kmol: 气体分子量 kg/kmol
    - tip_temperature_k: 尖端温度 K（工况下）
    - tip_pressure_pa: 尖端压力 Pa（火炬入口压力）
    - specific_heat_ratio: 比热比 k = cp/cv
    - target_mach: 目标 Mach 数（默认 0.2，尖端亚音速常用）
    """

    header_diameter_m: float  # m
    mw_kg_kmol: float  # kg/kmol
    tip_temperature_k: float  # K
    tip_pressure_pa: float  # Pa
    specific_heat_ratio: float  # k
    target_mach: float = 0.2  # 尖端亚音速默认 0.2


@dataclass(frozen=True)
class FlareTipResult:
    """flare_tip 结果。

    字段：
    - tip_diameter_m: 尖端直径 m（与 header_diameter 同；单点 tip）
    - tip_area_m2: 尖端流通面积 m²
    - tip_velocity_m_s: 尖端目标速度 m/s
    - actual_mach: 实际 Mach 数（恒等于 target_mach）
    - sound_speed_m_s: 等温声速 m/s
    - gas_density_kg_m3: 管内气体密度 kg/m³
    - mass_flux_kgs_m2: 质量流速 G kg/(s·m²)
    - formula_ref: 公式溯源标记 "API_521_§5.15.6"
    """

    tip_diameter_m: float
    tip_area_m2: float
    tip_velocity_m_s: float
    actual_mach: float
    sound_speed_m_s: float
    gas_density_kg_m3: float
    mass_flux_kgs_m2: float
    formula_ref: str  # "API_521_§5.15.6"


class FlareTipInputError(PcsError):
    """flare_tip 输入不合法（422）。

    触发场景：D <= 0 / MW <= 0 / T <= 0 / P <= 0 / k <= 1.0 / target_mach
    超出工程范围 [0.05, 1.0] 等。
    """

    code = "FLARE_TIP_INPUT_ERROR"
    status = 422


def calc_flare_tip(inp: FlareTipInput) -> FlareTipResult:
    """API 521 §5.15.6 火炬尖端速度计算。

    实现步骤（API 521 7th Ed. §5.15.6）：
    1. 输入校验（正数 + 工程范围）
    2. 等温理想气体密度 rho = P * MW / (R * T)
    3. 等温声速 a = sqrt(k * R * T / MW)
    4. 面积 A_tip = π * D_tip² / 4（尖端与总管同径，单点 tip 假设）
    5. u_tip = M_target × a（按目标 Mach 反求）
    6. actual_mach = u / a（构造恒等 == M_target）
    7. 质量流速 G = ρ × u

    Args:
        inp: FlareTipInput（已冻结 dataclass）。

    Returns:
        FlareTipResult（含 tip_diameter_m / tip_velocity_m_s / 声速 / 密度 /
        实际 Mach 等）。

    Raises:
        FlareTipInputError: 输入字段越界或非正（422）。
    """
    # 输入校验
    if inp.header_diameter_m <= 0:
        raise FlareTipInputError(
            f"header_diameter_m={inp.header_diameter_m} 必须 > 0"
        )
    if inp.mw_kg_kmol <= 0:
        raise FlareTipInputError(
            f"mw_kg_kmol={inp.mw_kg_kmol} 必须 > 0"
        )
    if inp.tip_temperature_k <= 0:
        raise FlareTipInputError(
            f"tip_temperature_k={inp.tip_temperature_k} 必须 > 0"
        )
    if inp.tip_pressure_pa <= 0:
        raise FlareTipInputError(
            f"tip_pressure_pa={inp.tip_pressure_pa} 必须 > 0"
        )
    if inp.specific_heat_ratio <= 1.0:
        raise FlareTipInputError(
            f"specific_heat_ratio={inp.specific_heat_ratio} 必须 > 1.0"
        )
    if not (0.05 <= inp.target_mach <= 1.0):
        raise FlareTipInputError(
            f"target_mach={inp.target_mach} 超出工程范围 [0.05, 1.0]"
        )

    # 公式变量命名
    D = inp.header_diameter_m
    T = inp.tip_temperature_k
    P = inp.tip_pressure_pa
    MW = inp.mw_kg_kmol
    k = inp.specific_heat_ratio
    M_target = inp.target_mach

    # 等温理想气体密度
    rho = (P * MW) / (_R_UNIVERSAL * T)  # kg/m³

    # 等温声速
    a = math.sqrt(k * _R_UNIVERSAL * T / MW)  # m/s

    # 尖端流通面积（单点 tip：D_tip == D_header）
    area = math.pi * D ** 2 / 4.0  # m²

    # 尖端速度 = M_target × a
    velocity = M_target * a  # m/s

    # 实际 Mach（构造恒等 == M_target）
    actual_mach = velocity / a  # = M_target

    # 质量流速
    mass_flux = rho * velocity  # kg/(s·m²)

    return FlareTipResult(
        tip_diameter_m=D,
        tip_area_m2=area,
        tip_velocity_m_s=velocity,
        actual_mach=actual_mach,
        sound_speed_m_s=a,
        gas_density_kg_m3=rho,
        mass_flux_kgs_m2=mass_flux,
        formula_ref="API_521_§5.15.6",
    )


__all__ = [
    "FlareTipInput",
    "FlareTipResult",
    "FlareTipInputError",
    "calc_flare_tip",
]
