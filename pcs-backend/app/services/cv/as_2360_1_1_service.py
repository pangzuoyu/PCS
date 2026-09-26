"""AS 2360.1.1 节流装置 Limit 校核（SPEC §3.6.1 + §3.7.1 V1.1）。

边界条件（SPEC §3.7.1）：
  - d < 1in (25.4mm) 触发 Limit 校核
  - 单相无闪蒸假设
  - 声速理想气体（γ 在 1.2~1.4 范围）
  - SI/Imperial 双单位验收

公式（理想气体）：
  - 声速 a = √(γ·R·T/M) = √(γ·P/ρ)
  - 临界压比 r_c = (2/(γ+1))^(γ/(γ-1))
  - 阻塞流 G_max = C·A·P₁·√(γ·M/(R·T)·(2/(γ+1))^((γ+1)/(γ-1)))

Q-9：d<1in CONFIG 表（AS_LIMIT_FACTOR）由 P6-14 接管。

参考标准：AS 2360.1.1-1993 (R2016) §4.2.3 Limit Factor。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from app.services.exceptions import PcsError

# AS 2360.1.1 Limit 触发阈值：1 inch = 0.0254 m
_D_LIMIT_IN_M: Final[float] = 0.0254

# γ 物理边界：单原子气体 γ=5/3≈1.67（理论上限），双原子 γ≈1.4
# 1.05 是工程下限（防止 γ→1 时 r_c 公式数值不稳定）
_GAMMA_MIN: Final[float] = 1.05
_GAMMA_MAX: Final[float] = 1.67

# Imperial 单位换算
_M_PER_FT: Final[float] = 0.3048
_KPA_PER_PSIA: Final[float] = 0.1450377


class As2360InputError(PcsError):
    """AS 2360.1.1 输入校验失败（422）。"""

    code = "AS_2360_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class As2360LimitInput:
    """AS 2360.1.1 Limit 校核输入（frozen dataclass）。"""

    orifice_diameter_m: float
    inlet_pressure_kpa: float
    outlet_pressure_kpa: float
    fluid_density_kg_m3: float
    gas_specific_heat_ratio: float
    mass_flow_kg_s: float
    imperial_units: bool = False


@dataclass(frozen=True)
class As2360LimitResult:
    """AS 2360.1.1 Limit 校核结果（frozen dataclass）。"""

    orifice_diameter_in: float
    is_limit_applicable: bool
    sonic_velocity_m_s: float
    critical_pressure_ratio: float
    actual_pressure_ratio: float
    is_choked: bool
    warning_message: str | None
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: As2360LimitInput) -> None:
    """F5：极值校验（必填参数均必须正数）。"""
    if inp.orifice_diameter_m <= 0:
        raise As2360InputError(
            f"d={inp.orifice_diameter_m} 必须 > 0"
        )
    if inp.inlet_pressure_kpa <= 0:
        raise As2360InputError(
            f"P₁={inp.inlet_pressure_kpa} 必须 > 0"
        )
    if inp.outlet_pressure_kpa < 0:
        raise As2360InputError(
            f"P₂={inp.outlet_pressure_kpa} 不能为负"
        )
    if inp.fluid_density_kg_m3 <= 0:
        raise As2360InputError("密度必须 > 0")
    if inp.mass_flow_kg_s <= 0:
        raise As2360InputError(
            f"质量流量={inp.mass_flow_kg_s} 必须 > 0"
        )
    # F2：γ 物理边界 [1.05, 1.67]
    if not (_GAMMA_MIN <= inp.gas_specific_heat_ratio <= _GAMMA_MAX):
        raise As2360InputError(
            f"γ={inp.gas_specific_heat_ratio} 越界 [{_GAMMA_MIN}, {_GAMMA_MAX}]"
        )


def calc_as_2360_1_1_limit(inp: As2360LimitInput) -> As2360LimitResult:
    """AS 2360.1.1 节流装置 Limit 校核（SPEC §3.6.1 + §3.7.1 V1.1）。

    触发条件：d < 1in (25.4mm) 建议查表 AS 2360.1.1 Limit Factor C_L；
    本批 Q-9 占位仅 warning，不阻塞。

    计算项：
      - sonic_velocity_m_s：理想气体声速 a = √(γ·P₁/ρ)
      - critical_pressure_ratio：等熵临界压比 r_c
      - is_choked：P₂/P₁ ≤ r_c → 阻塞流
      - imperial_conversion：sonic_velocity_ft_s + inlet_pressure_psia（仅当请求）

    Args:
        inp: As2360LimitInput（frozen）

    Returns:
        As2360LimitResult（frozen）

    Raises:
        As2360InputError: 输入校验失败（F2 γ 越界、F5 非正极值）
    """
    _validate_input(inp)

    d_in = inp.orifice_diameter_m / _D_LIMIT_IN_M
    # F2 boundary：strict < 1in（d=1in exactly 不触发 Limit）
    is_limit = d_in < 1.0

    # 声速（理想气体）：a = √(γ·P₁/ρ)（P₁ 为绝对压力）
    p1_pa = inp.inlet_pressure_kpa * 1000.0
    a = math.sqrt(inp.gas_specific_heat_ratio * p1_pa / inp.fluid_density_kg_m3)

    # 临界压比 r_c = (2/(γ+1))^(γ/(γ-1))（仅气相）
    gamma = inp.gas_specific_heat_ratio
    r_c = (2.0 / (gamma + 1.0)) ** (gamma / (gamma - 1.0))

    # 实际压比 P₂/P₁
    p_ratio = inp.outlet_pressure_kpa / inp.inlet_pressure_kpa
    # 阻塞判断：P₂/P₁ ≤ r_c
    is_choked = p_ratio <= r_c

    warning = None
    if is_limit:
        warning = (
            f"AS 2360.1.1 Limit: orifice d={d_in:.3f}in < 1in，"
            f"建议查表 AS 2360.1.1 Limit Factor C_L（CONFIG 表未命中，"
            f"使用合成占位 Q-9）"
        )

    imperial = None
    if inp.imperial_units:
        imperial = {
            "sonic_velocity_ft_s": a / _M_PER_FT,
            "inlet_pressure_psia": inp.inlet_pressure_kpa * _KPA_PER_PSIA,
        }

    return As2360LimitResult(
        orifice_diameter_in=d_in,
        is_limit_applicable=is_limit,
        sonic_velocity_m_s=a,
        critical_pressure_ratio=r_c,
        actual_pressure_ratio=p_ratio,
        is_choked=is_choked,
        warning_message=warning,
        imperial_conversion=imperial,
        formula_ref={
            "sonic_velocity": "a = √(γ·P₁/ρ) [理想气体声速]",
            "critical_pressure_ratio": "r_c = (2/(γ+1))^(γ/(γ-1)) [等熵临界压比]",
            "limit_threshold": "d < 1in (25.4mm) 触发 AS 2360.1.1 Limit [SPEC §3.7.1]",
            "as_standard": "AS 2360.1.1-1993 (R2016) §4.2.3 Limit Factor",
        },
    )


__all__ = [
    "As2360LimitInput",
    "As2360LimitResult",
    "As2360InputError",
    "calc_as_2360_1_1_limit",
]