"""API 14E 两相流冲蚀速度（SPEC §3.2.1 V1.8）。

公式：V_e = C / √ρ_mix（API 14E 5th Ed §4.3.2 Eq.4）
   C 因子（按服务类型，SPEC §3.2.1 表 3.2.1）：
     连续 service = 122
     间歇 service = 152.5
     耐蚀连续     = 183~244（默认 200）
     耐蚀间歇     = 305
   ρ_mix：两相流体积加权平均密度

Imperial 双单位（仅 imperial_units=True）：
   V_e(ft/s) = V_e(m/s) / 0.3048

Q-5（OpenWolf 登记）：C 因子 CONFIG 表未建，本批用 SYNTHETIC_TEST_DATA + confirmed_by 占位
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

# C 因子默认值（按服务类型，SPEC §3.2.1 表 3.2.1 SI）
ServiceType = Literal[
    "CONTINUOUS",
    "INTERMITTENT",
    "CORROSIVE_CONTINUOUS",
    "CORROSIVE_INTERMITTENT",
]
_C_FACTOR_BY_SERVICE: Final[dict[str, float]] = {
    "CONTINUOUS": 122.0,
    "INTERMITTENT": 152.5,
    "CORROSIVE_CONTINUOUS": 200.0,
    "CORROSIVE_INTERMITTENT": 305.0,
}


class Api14eErosionInputError(PcsError):
    code = "API14E_EROSION_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class Api14eErosionInput:
    rho_mix_kg_m3: float
    service_type: ServiceType  # 决定 C 因子默认；显式 c_factor 非 None 时覆盖
    c_factor: float | None = None  # None 时按 service_type 查 _C_FACTOR_BY_SERVICE
    mass_flow_kg_s: float = 0.0
    pipe_diameter_m: float = 0.1
    imperial_units: bool = False


@dataclass(frozen=True)
class Api14eErosionResult:
    v_e_m_s: float
    actual_v_m_s: float
    is_erosion_safe: bool
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _resolve_c_factor(inp: Api14eErosionInput) -> float:
    """解析 C 因子：显式 c_factor 非 None 时覆盖，否则按 service_type 查 dict。"""
    if inp.c_factor is not None:
        return inp.c_factor
    return _C_FACTOR_BY_SERVICE[inp.service_type]


def _validate_input(inp: Api14eErosionInput) -> None:
    if inp.rho_mix_kg_m3 <= 0:
        raise Api14eErosionInputError(f"ρ_mix={inp.rho_mix_kg_m3} 必须 > 0")
    c = _resolve_c_factor(inp)
    if not (50.0 <= c <= 400.0):
        raise Api14eErosionInputError(f"C 因子={c} 越界（API 14E 范围 50~400）")
    if inp.mass_flow_kg_s < 0:
        raise Api14eErosionInputError(f"mass_flow={inp.mass_flow_kg_s} 不能为负")
    if inp.pipe_diameter_m <= 0:
        raise Api14eErosionInputError(f"diameter={inp.pipe_diameter_m} 必须 > 0")


def calc_api14e_erosion_velocity(inp: Api14eErosionInput) -> Api14eErosionResult:
    _validate_input(inp)
    c = _resolve_c_factor(inp)
    v_e = c / math.sqrt(inp.rho_mix_kg_m3)
    q_m3_s = inp.mass_flow_kg_s / inp.rho_mix_kg_m3
    a_m2 = math.pi * inp.pipe_diameter_m**2 / 4.0
    v_actual = q_m3_s / a_m2
    is_safe = v_actual < v_e

    imperial = None
    if inp.imperial_units:
        imperial = {
            "v_e_ft_s": v_e / 0.3048,
            "actual_v_ft_s": v_actual / 0.3048,
        }

    return Api14eErosionResult(
        v_e_m_s=v_e,
        actual_v_m_s=v_actual,
        is_erosion_safe=is_safe,
        imperial_conversion=imperial,
        formula_ref={
            "erosion_velocity": "V_e = C / √ρ_mix [API 14E 5th Ed §4.3.2 Eq.4]",
            "c_factor_by_service": (
                "SPEC §3.2.1 表 3.2.1: CONTINUOUS=122 / INTERMITTENT=152.5 "
                "/ CORROSIVE_CONTINUOUS=183~244 / CORROSIVE_INTERMITTENT=305"
            ),
        },
    )


__all__ = [
    "Api14eErosionInput",
    "Api14eErosionResult",
    "Api14eErosionInputError",
    "calc_api14e_erosion_velocity",
]
