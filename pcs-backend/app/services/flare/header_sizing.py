"""FLARE_SYS 火炬总管尺寸（Mach 数法 + 等温可压缩管流）。

按 API 521 7th Ed. §5.15.4：
- 总管直径按目标 Mach 数确定（默认 0.5，保守）
- 等温可压缩管流（泄放过程快速接近等温）
- 输入：W_mass / T / P / MW / k
- 输出：D / 实际 Mach / G / 声速 / 密度 / 流速

不依赖 DB（纯计算函数）；输入 W_mass 可由 Task 19 aggregate_flare_load 提供。

公式溯源：
- API 521 7th Ed. §5.15.4（泄放总管 Mach 数法 + 等温可压缩管流）
- 等温声速 a = sqrt(k * R * T / MW)
- 等温理想气体密度 ρ = P * MW / (R * T)
- Mach = u / a = G / (ρ * a) → 反求面积 A = W_mass / (target_Mach * ρ * a)
- D = sqrt(4 A / π)
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.exceptions import PcsError


@dataclass(frozen=True)
class HeaderSizingInput:
    """总管尺寸输入。

    字段：

    - relief_mass_flow_kgs: 总泄放质量流量 kg/s（来自 Task 19 aggregate_flare_load）
    - avg_temperature_k: 管内平均温度 K
    - avg_pressure_pa: 管内平均压力 Pa
    - mw_kg_kmol: 气体分子量 kg/kmol
    - specific_heat_ratio: 比热比 k = cp/cv
    - target_mach: 目标 Mach 数（默认 0.5 保守）
    """

    relief_mass_flow_kgs: float  # kg/s（来自 aggregate_flare_load.total_relief_area 但转 kg/s）
    avg_temperature_k: float  # K
    avg_pressure_pa: float  # Pa
    mw_kg_kmol: float  # 气体分子量
    specific_heat_ratio: float  # k = cp/cv
    target_mach: float = 0.5  # 默认保守 Mach 0.5


@dataclass(frozen=True)
class HeaderSizingResult:
    """总管尺寸结果。

    字段：

    - diameter_m: 总管直径 m
    - area_m2: 总管截面积 m²
    - actual_mach: 实际 Mach 数（应等于 target_mach）
    - mass_flux_kgs_m2: 质量流速 G kg/(s·m²)
    - velocity_m_s: 气流速度 m/s
    - sound_speed_m_s: 等温声速 m/s
    - gas_density_kg_m3: 管内气体密度 kg/m³（等温理想气体）
    - formula_ref: 公式溯源标记
    """

    diameter_m: float
    area_m2: float
    actual_mach: float
    mass_flux_kgs_m2: float
    velocity_m_s: float
    sound_speed_m_s: float
    gas_density_kg_m3: float
    formula_ref: str  # "API_521_§5.15.4"


class HeaderSizingInputError(PcsError):
    """header_sizing 输入不合法（422）。

    触发场景：relief_mass_flow_kgs / T / P / MW <= 0、specific_heat_ratio <= 1.0、
    target_mach 超出工程范围 [0.05, 1.0] 等。
    """

    code = "FLARE_HEADER_INPUT_ERROR"
    status = 422


# 通用气体常数 R = 8314.462618 J/(kmol·K)（CODATA 2018 常用值）
_R_UNIVERSAL = 8314.462618  # J/(kmol·K)


def calc_header_sizing(inp: HeaderSizingInput) -> HeaderSizingResult:
    """Mach 数法 + 等温可压缩管流计算火炬总管直径。

    实现步骤（API 521 7th Ed. §5.15.4）：
    1. 输入校验（正数 + 工程范围）
    2. 等温理想气体密度 ρ = P * MW / (R * T)
    3. 等温声速 a = sqrt(k * R * T / MW)
    4. 由 Mach 数法反求面积 A = W / (M_target * ρ * a)
    5. D = sqrt(4 * A / π)
    6. 计算实际 Mach / 流速 / 质量流速（实际 Mach 应等于 M_target）

    Args:
        inp: HeaderSizingInput（已冻结 dataclass）。

    Returns:
        HeaderSizingResult（含 diameter_m / 声速 / 密度 / 实际 Mach 等）。

    Raises:
        HeaderSizingInputError: 输入字段越界或非正（422）。
    """
    # 输入校验
    if inp.relief_mass_flow_kgs <= 0:
        raise HeaderSizingInputError(
            f"relief_mass_flow_kgs={inp.relief_mass_flow_kgs} 必须 > 0"
        )
    if inp.avg_temperature_k <= 0:
        raise HeaderSizingInputError(
            f"avg_temperature_k={inp.avg_temperature_k} 必须 > 0"
        )
    if inp.avg_pressure_pa <= 0:
        raise HeaderSizingInputError(
            f"avg_pressure_pa={inp.avg_pressure_pa} 必须 > 0"
        )
    if inp.mw_kg_kmol <= 0:
        raise HeaderSizingInputError(
            f"mw_kg_kmol={inp.mw_kg_kmol} 必须 > 0"
        )
    if inp.specific_heat_ratio <= 1.0:
        raise HeaderSizingInputError(
            f"specific_heat_ratio={inp.specific_heat_ratio} 必须 > 1.0"
        )
    if not (0.05 <= inp.target_mach <= 1.0):
        raise HeaderSizingInputError(
            f"target_mach={inp.target_mach} 超出工程范围 [0.05, 1.0]"
        )

    # 公式变量命名
    T = inp.avg_temperature_k
    P = inp.avg_pressure_pa
    MW = inp.mw_kg_kmol
    k = inp.specific_heat_ratio
    W = inp.relief_mass_flow_kgs
    M_target = inp.target_mach

    # 等温理想气体密度
    rho = (P * MW) / (_R_UNIVERSAL * T)  # kg/m³

    # 等温声速（理想气体）
    a = math.sqrt(k * _R_UNIVERSAL * T / MW)  # m/s

    # 由 Mach 数法反求面积
    area = W / (M_target * rho * a)  # m²
    diameter = math.sqrt(4 * area / math.pi)  # m

    # 实际 Mach + 流速 + 质量流速
    actual_mach = W / (area * rho * a)  # 必然 == M_target
    velocity = actual_mach * a
    mass_flux = W / area

    return HeaderSizingResult(
        diameter_m=diameter,
        area_m2=area,
        actual_mach=actual_mach,
        mass_flux_kgs_m2=mass_flux,
        velocity_m_s=velocity,
        sound_speed_m_s=a,
        gas_density_kg_m3=rho,
        formula_ref="API_521_§5.15.4",
    )


__all__ = [
    "HeaderSizingInput",
    "HeaderSizingResult",
    "HeaderSizingInputError",
    "calc_header_sizing",
]