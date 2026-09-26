"""API 14E 两相流管道尺寸（SPEC §3.2.2 V1.8）。

公式：
  ρ_mix = ρ_L·(1-ε) + ρ_V·ε
  V_e = C / √ρ_mix（API 14E 5th Ed §4.3.2 Eq.4）
  D_min = √(4·m / (π·ρ_mix·V_e))（连续性方程 + 冲蚀速度边界）

校核：
  - 临界携液（Turner 1966，气相主导 ε>0.5）：
      V_turner = 5.46·(σ·g·(ρ_L-ρ_V)/ρ_V²)^0.25
      is_safe = (V_g >= V_turner) 其中 V_g = m / (ρ_V·π·D_min²/4)
  - 液相主导 ε≤0.5：跳过 Turner 校核（v_turner=0, is_safe=True）

Imperial 双单位（仅 imperial_units=True）：
  d_in = d_min_m / 0.0254
  v_ft_s = v_m_s / 0.3048
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from app.services.exceptions import PcsError

_SURFACE_TENSION_WATER_AIR_DEFAULT: Final[float] = 0.02  # N/m（水-气 25°C）
_GRAVITY: Final[float] = 9.81  # m/s²


class Api14ePipeSizingInputError(PcsError):
    """API 14E 管道尺寸输入不合法（422）。"""

    code = "API14E_SIZING_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class Api14ePipeSizingInput:
    """API 14E 管道尺寸输入。"""

    mass_flow_kg_s: float
    rho_L_kg_m3: float
    rho_V_kg_m3: float
    void_fraction: float
    c_factor: float
    surface_tension_n_m: float = _SURFACE_TENSION_WATER_AIR_DEFAULT
    imperial_units: bool = False


@dataclass(frozen=True)
class Api14ePipeSizingResult:
    """API 14E 管道尺寸结果。"""

    d_min_m: float
    v_e_m_s: float
    v_turner_m_s: float
    is_liquid_unloading_safe: bool
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: Api14ePipeSizingInput) -> None:
    """校验输入：F5 极端值 + F2 void_fraction 边界。"""
    if inp.mass_flow_kg_s <= 0:
        raise Api14ePipeSizingInputError(
            f"mass_flow={inp.mass_flow_kg_s} 必须 > 0"
        )
    if inp.rho_L_kg_m3 <= 0 or inp.rho_V_kg_m3 <= 0:
        raise Api14ePipeSizingInputError(
            f"密度必须 > 0（ρ_L={inp.rho_L_kg_m3}, ρ_V={inp.rho_V_kg_m3}）"
        )
    if not (0.0 <= inp.void_fraction <= 1.0):
        raise Api14ePipeSizingInputError(
            f"void_fraction={inp.void_fraction} 越界 [0,1]"
        )
    if not (50.0 <= inp.c_factor <= 250.0):
        raise Api14ePipeSizingInputError(
            f"C 因子={inp.c_factor} 越界 [50,250]"
        )


def calc_api14e_pipe_size(inp: Api14ePipeSizingInput) -> Api14ePipeSizingResult:
    """按 API 14E 计算最小管径 + Turner 临界携液校核。"""
    _validate_input(inp)
    rho_mix = (
        inp.rho_L_kg_m3 * (1.0 - inp.void_fraction)
        + inp.rho_V_kg_m3 * inp.void_fraction
    )
    v_e = inp.c_factor / math.sqrt(rho_mix)
    d_min = math.sqrt(
        4.0 * inp.mass_flow_kg_s / (math.pi * rho_mix * v_e)
    )

    # Turner 1966 临界携液（气相主导 ε>0.5；液相主导返回 0 + safe）
    if inp.void_fraction > 0.5:
        v_turner = 5.46 * (
            inp.surface_tension_n_m
            * _GRAVITY
            * (inp.rho_L_kg_m3 - inp.rho_V_kg_m3)
            / inp.rho_V_kg_m3**2
        ) ** 0.25
        v_g = inp.mass_flow_kg_s / (
            inp.rho_V_kg_m3 * math.pi * d_min**2 / 4.0
        )
        is_safe = v_g >= v_turner
    else:
        v_turner = 0.0
        is_safe = True

    imperial = None
    if inp.imperial_units:
        imperial = {
            "d_min_in": d_min / 0.0254,
            "v_e_ft_s": v_e / 0.3048,
            "v_turner_ft_s": v_turner / 0.3048,
        }

    return Api14ePipeSizingResult(
        d_min_m=d_min,
        v_e_m_s=v_e,
        v_turner_m_s=v_turner,
        is_liquid_unloading_safe=is_safe,
        imperial_conversion=imperial,
        formula_ref={
            "rho_mix": "ρ_mix = ρ_L(1-ε) + ρ_V·ε",
            "erosion_velocity": "V_e = C / √ρ_mix [API 14E 5th Ed §4.3.2 Eq.4]",
            "pipe_diameter": "D_min = √(4m/(π·ρ_mix·V_e)) [连续性方程]",
            "turner_critical_velocity": (
                "V_turner = 5.46·(σg(ρ_L-ρ_V)/ρ_V²)^0.25 "
                "[Turner 1966，气相主导 ε>0.5]"
            ),
        },
    )


__all__ = [
    "Api14ePipeSizingInput",
    "Api14ePipeSizingResult",
    "Api14ePipeSizingInputError",
    "calc_api14e_pipe_size",
]