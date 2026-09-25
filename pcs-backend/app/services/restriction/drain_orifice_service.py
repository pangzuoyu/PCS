"""排污孔板（drain orifice）计算（SPEC §3.6.2 + §3.7.2 V1.1）。

公式（GB/T 308 排水孔板 + GB/T 2624 流量孔板）：
  Ftp 修正（GB/T 308 Eq.2.2 排水孔板经验式）：Ftp = 1 - 0.0245·β^4.4
  阻塞判断：P₂/P₁ ≤ r_c（γ=1.4 时 r_c ≈ 0.528）

Q-11：Ftp 修正系数 GB/T 308 经验式（无 ISO 5167 标准支撑）
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

_GAMMA_DEFAULT: Final[float] = 1.4
_M2_TO_IN2: Final[float] = 0.0254**2  # 1 in² = (0.0254 m)²
_KPA_PER_PSIA: Final[float] = 0.1450377


class DrainOrificeInputError(PcsError):
    """DRAIN_ORIFICE 输入校验失败（422）。"""

    code = "DRAIN_ORIFICE_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class DrainOrificeInput:
    """排污孔板输入（frozen dataclass）。

    物理量 SI 单位：长度 m、压力 kPa、密度 kg/m³、流量 kg/s。
    """

    orifice_diameter_m: float
    beta_ratio: float
    inlet_pressure_kpa: float
    outlet_pressure_kpa: float
    fluid_density_kg_m3: float
    mass_flow_kg_s: float
    drain_type: Literal["CONTINUOUS", "INTERMITTENT"]
    imperial_units: bool = False


@dataclass(frozen=True)
class DrainOrificeResult:
    """排污孔板结果（frozen dataclass）。"""

    orifice_area_m2: float
    ftp_factor: float
    critical_pressure_ratio: float
    actual_pressure_ratio: float
    is_choked: bool
    mass_flow_capacity_kg_s: float
    is_capacity_ok: bool
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: DrainOrificeInput) -> None:
    """F2 + F5：β 直径比 + 极值校验。"""
    if inp.orifice_diameter_m <= 0:
        raise DrainOrificeInputError(f"d={inp.orifice_diameter_m} 必须 > 0")
    # F2 boundary：β 严格 0 < β < 1
    if not (0.0 < inp.beta_ratio < 1.0):
        raise DrainOrificeInputError(f"β={inp.beta_ratio} 越界 (0, 1)")
    if inp.inlet_pressure_kpa <= 0 or inp.outlet_pressure_kpa < 0:
        raise DrainOrificeInputError("压力必须 P₁>0, P₂≥0")
    if inp.fluid_density_kg_m3 <= 0:
        raise DrainOrificeInputError("密度必须 > 0")
    if inp.mass_flow_kg_s < 0:
        raise DrainOrificeInputError("流量不能为负")


def calc_drain_orifice(inp: DrainOrificeInput) -> DrainOrificeResult:
    """排污孔板（drain orifice）尺寸校核（SPEC §3.6.2 + §3.7.2 V1.1）。

    计算项：
      - orifice_area_m2 = π·d²/4
      - Ftp = 1 - 0.0245·β^4.4（GB/T 308 排水孔板 Eq.2.2 经验式）
      - critical_pressure_ratio r_c = (2/(γ+1))^(γ/(γ-1))
      - is_choked：P₂/P₁ ≤ r_c
      - mass_flow_capacity：阻塞流时 v_max = √(2ΔP/ρ) → A·Ftp·ρ·v_max

    Args:
        inp: DrainOrificeInput（frozen）

    Returns:
        DrainOrificeResult（frozen）

    Raises:
        DrainOrificeInputError: 输入校验失败（F2 β 越界、F5 非正极值）
    """
    _validate_input(inp)

    a_orifice = math.pi * inp.orifice_diameter_m**2 / 4.0
    # GB/T 308 Eq.2.2 Ftp = 1 - 0.0245·β^4.4（标 SYNTHETIC_TEST_DATA）
    ftp = 1.0 - 0.0245 * inp.beta_ratio**4.4
    r_c = (2.0 / (_GAMMA_DEFAULT + 1.0)) ** (_GAMMA_DEFAULT / (_GAMMA_DEFAULT - 1.0))
    p_ratio = inp.outlet_pressure_kpa / inp.inlet_pressure_kpa
    is_choked = p_ratio <= r_c
    if is_choked:
        delta_p_pa = (inp.inlet_pressure_kpa - inp.outlet_pressure_kpa) * 1000.0
        v_max = math.sqrt(2.0 * delta_p_pa / inp.fluid_density_kg_m3)
        mass_max = a_orifice * ftp * inp.fluid_density_kg_m3 * v_max
    else:
        mass_max = float("inf")
    is_ok = inp.mass_flow_kg_s <= mass_max if is_choked else True

    imperial = None
    if inp.imperial_units:
        imperial = {
            "orifice_area_in2": a_orifice / _M2_TO_IN2,
            "inlet_pressure_psia": inp.inlet_pressure_kpa * _KPA_PER_PSIA,
        }

    return DrainOrificeResult(
        orifice_area_m2=a_orifice,
        ftp_factor=ftp,
        critical_pressure_ratio=r_c,
        actual_pressure_ratio=p_ratio,
        is_choked=is_choked,
        mass_flow_capacity_kg_s=mass_max,
        is_capacity_ok=is_ok,
        imperial_conversion=imperial,
        formula_ref={
            "ftp_correction": ("Ftp = 1 - 0.0245·β^4.4 [GB/T 308 Eq.2.2; SYNTHETIC_TEST_DATA]"),
            "critical_pressure_ratio": ("r_c = (2/(γ+1))^(γ/(γ-1))"),
            "drain_type": (f"{inp.drain_type}（CONTINUOUS=连续排污/INTERMITTENT=间歇排污）"),
        },
    )


__all__ = [
    "DrainOrificeInput",
    "DrainOrificeResult",
    "DrainOrificeInputError",
    "calc_drain_orifice",
]
