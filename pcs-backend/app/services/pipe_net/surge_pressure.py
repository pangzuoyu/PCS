"""PIPE_NET 浪涌压力计算（SPEC §3.2.3 V1.8）。

公式：
  纯流体声速：a_f = √(K/ρ)（水 ≈ 1483 m/s，气 ≈ 400 m/s）
  管道波速（含管壁弹性修正，Wylie & Streeter 1993）：
    a = a_f / √(1 + (K·D)/(E·e)·C₁)
    E：管材弹性模量（API 5L X42~X80 / ASTM A106 / A335；pipe_e_modulus 表）
    e：壁厚
    C₁：管锚固系数（1 - ν²；ν=0.3 → C₁=0.91；两端锚固）
  瞬时关阀（Joukowsky 1898）：ΔP = ρ·a·ΔV
  缓慢关阀（MOC/特征线法）：t_c ≥ 2L/a 时无水锤
  段塞捕集（按 C-15 Beggs-Brill 持液率 → 段塞体积 V_s = L·A·(1-H_L(θ))

P6-6B T3：E 模量从 ``pipe_e_modulus`` 表读取（5 min TTL 缓存）；
DB 不可达时 fallback 到内联 5 等级 X42/X52/X65/X70/X80 圆整值
（30e6 psi = 206.84 GPa）。

Q-7：段塞捕集器尺寸走 C-15 Beggs-Brill 接口（Task A4）。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final

from app.services._compound_config_cache import get_pipe_E_modulus_table
from app.services.exceptions import PcsError

# 管材弹性模量（DB 内联 5 等级 fallback：API 5L X42~X80 圆整 30e6 psi
# = 30_000_000 × 6894.76 ≈ 206.84 GPa；DB 不可达时使用）
_PIPE_E_MODULUS_FALLBACK_PA: Final[dict[str, float]] = {
    "X42": 30_000_000 * 6894.76,
    "X52": 30_000_000 * 6894.76,
    "X65": 30_000_000 * 6894.76,
    "X70": 30_000_000 * 6894.76,
    "X80": 30_000_000 * 6894.76,
}


def _load_pipe_E_modulus_table() -> dict[str, float]:
    """5 min TTL 缓存加载管材 E 模量（pipe_e_modulus 表）；DB 不可达时 fallback 到内联 5 等级。

    仿 ``_resolve_hammerschmidt_K`` 模式（_compound_config_cache.py:62）。
    """
    db_table = get_pipe_E_modulus_table()
    return db_table if db_table else _PIPE_E_MODULUS_FALLBACK_PA
# 管锚固系数 C₁ = 1 - ν²（两端锚固 ν=0.3 → 0.91）
_C1_ANCHOR_COEFF: Final[float] = 0.91
# Imperial 换算常数
_PA_PER_PSI: Final[float] = 6894.76
_M_PER_FT: Final[float] = 0.3048


class SurgePressureInputError(PcsError):
    """PIPE_NET 浪涌压力输入不合法（422）。"""

    code = "SURGE_PRESSURE_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class SurgePressureInput:
    """PIPE_NET 浪涌压力输入。

    SI base；imperial_units=True 时输出 imperial 双单位。
    """

    fluid_density_kg_m3: float
    fluid_bulk_modulus_pa: float
    pipe_diameter_m: float
    flow_velocity_m_s: float
    valve_close_time_s: float
    pipe_length_m: float = 1000.0
    wall_thickness_m: float = 0.0
    pipe_material: str = "X65"  # API 5L line pipe（默认；Worley XLS L24 对账）
    imperial_units: bool = False


@dataclass(frozen=True)
class SurgePressureResult:
    """PIPE_NET 浪涌压力结果。"""

    wave_speed_m_s: float
    surge_pressure_pa: float
    critical_close_time_s: float
    is_joukowsky_applicable: bool
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: SurgePressureInput) -> None:
    """校验输入物理量合法性（F2/F5：拒绝非正/负值）。"""
    if inp.fluid_density_kg_m3 <= 0:
        raise SurgePressureInputError(f"ρ={inp.fluid_density_kg_m3} 必须 > 0")
    if inp.fluid_bulk_modulus_pa <= 0:
        raise SurgePressureInputError(f"K={inp.fluid_bulk_modulus_pa} 必须 > 0")
    if inp.pipe_diameter_m <= 0:
        raise SurgePressureInputError(f"D={inp.pipe_diameter_m} 必须 > 0")
    if inp.flow_velocity_m_s <= 0:
        raise SurgePressureInputError(f"V={inp.flow_velocity_m_s} 必须 > 0")
    if inp.valve_close_time_s < 0:
        raise SurgePressureInputError(f"t_c={inp.valve_close_time_s} 不能为负")
    if inp.wall_thickness_m < 0:
        raise SurgePressureInputError(f"e={inp.wall_thickness_m} 不能为负")
    if inp.pipe_length_m <= 0:
        raise SurgePressureInputError(f"L={inp.pipe_length_m} 必须 > 0")
    valid_grades = _load_pipe_E_modulus_table()
    if inp.pipe_material not in valid_grades:
        raise SurgePressureInputError(
            f"管材等级 {inp.pipe_material} 必须是 {sorted(valid_grades.keys())} 之一"
        )


def _wave_speed_with_wall_correction(inp: SurgePressureInput) -> tuple[float, float]:
    """返回 (a, a_fluid)：a 含管壁修正；a_fluid 纯流体声速。

    Wylie & Streeter 1993：a = a_f / √(1 + (K·D)/(E·e)·C₁)
    e=0 时 → 纯流体声速（向后兼容，F3）。
    E 模量从 ``pipe_e_modulus`` 表读取（5 min TTL 缓存）；
    DB 不可达时 fallback 到内联 5 等级 X42~X80 圆整值。
    """
    a_fluid = math.sqrt(inp.fluid_bulk_modulus_pa / inp.fluid_density_kg_m3)
    if inp.wall_thickness_m <= 0.0:
        return a_fluid, a_fluid
    e_table = _load_pipe_E_modulus_table()
    e_modulus = e_table[inp.pipe_material]
    correction = (
        inp.fluid_bulk_modulus_pa * inp.pipe_diameter_m
        / (e_modulus * inp.wall_thickness_m)
        * _C1_ANCHOR_COEFF
    )
    a = a_fluid / math.sqrt(1.0 + correction)
    return a, a_fluid


def calc_water_hammer_surge(inp: SurgePressureInput) -> SurgePressureResult:
    """计算 PIPE_NET 浪涌压力（Joukowsky + MOC 临界关阀）。"""
    _validate_input(inp)
    a, _a_fluid = _wave_speed_with_wall_correction(inp)
    # Joukowsky 1898：ΔP = ρ·a·ΔV
    delta_p = inp.fluid_density_kg_m3 * a * inp.flow_velocity_m_s
    # 临界关阀时间（MOC 边界）：t_c_critical = 2L/a
    t_c_critical = 2.0 * inp.pipe_length_m / a
    is_joukowsky = inp.valve_close_time_s < t_c_critical

    imperial: dict[str, float] | None = None
    if inp.imperial_units:
        imperial = {
            "wave_speed_ft_s": a / _M_PER_FT,
            "surge_pressure_psi": delta_p / _PA_PER_PSI,
            "critical_close_time_s": t_c_critical,
        }

    return SurgePressureResult(
        wave_speed_m_s=a,
        surge_pressure_pa=delta_p,
        critical_close_time_s=t_c_critical,
        is_joukowsky_applicable=is_joukowsky,
        imperial_conversion=imperial,
        formula_ref={
            "wave_speed": (
                "a = √(K/ρ) [纯流体声速，含管壁修正时"
                " a = a_f/√(1+(K·D)/(E·e)·C₁)，Wylie & Streeter 1993]"
            ),
            "joukowsky": "ΔP = ρ·a·ΔV [Joukowsky 1898 瞬时关阀]",
            "critical_close_time": "t_c_critical = 2L/a [MOC 缓慢关阀边界]",
        },
    )


__all__ = [
    "SurgePressureInput",
    "SurgePressureResult",
    "SurgePressureInputError",
    "calc_water_hammer_surge",
]
