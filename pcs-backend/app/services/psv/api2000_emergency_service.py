"""API 2000 7th Ed 储罐通风（emergency/fire/vacuum）工况（SPEC §3.5.1 V1.4）。

4 工况：
  - NORMAL（已有 breathing_valve_service 提供；本任务占位 Q=0）
  - EMERGENCY（API 2000 §3.5：进料失效+火灾耦合，Q = 1.5 × FIRE）
  - FIRE（API 2000 §3.4：wetted area 法，Q(W) = 43192·F·A^0.82 SI）
  - VACUUM（API 2000 §3.6：抽出失效，Q(m³/h) = 1013·A）

调用 C-12 公共服务（D7 接口冻结，ADR-0041 v7）：
  - calc_wetted_area 算 wetted_area_m2（火灾工况必用；调用方传 vessel_geometry 时）

公式溯源（API 2000 7th Ed §3.4 火灾工况 SI 严格换算）：
  imperial 原式 Q(Btu/hr) = 21000·F·A_ft²^0.82
  A_ft² = A_m² × 10.7639
  Q_Btu_hr = 21000 × F × (10.7639·A_m²)^0.82
  Q_W = Q_Btu_hr × 0.293071 = 43192·F·A_m²^0.82
  验算：21000 × 0.293071 × 7.0178 ≈ 43187.6 ≈ 43192 ✓
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError
from app.services.vessel.vessel_service import (
    WettedAreaInput,
    calc_wetted_area,
)

# N-1 v4 BLOCKER：43192（v3 误算 43838；非 709200 imperial 原式）
_API2000_FIRE_COEFF_W: Final[float] = 43192.0
# API 2000 7th §3.6 真空工况：Q(m³/h) = 1013·A
_API2000_VACUUM_COEFF: Final[float] = 1013.0
# EMERGENCY 系数（进料失效 + 火灾耦合）
_API2000_EMERGENCY_MULTIPLIER: Final[float] = 1.5
# 环境因子默认（储罐无保温）
_FIRE_ENV_FACTOR_DEFAULT: Final[float] = 1.0
# W → m³/h 经验换算（保留供双单位输出）
_W_TO_M3H: Final[float] = 0.86
# imperial 双单位换算系数
_BTU_HR_PER_W: Final[float] = 3.41214
_GALLON_US_PER_M3: Final[float] = 264.172
_FT2_PER_M2: Final[float] = 10.7639

Scenario = Literal["NORMAL", "EMERGENCY", "FIRE", "VACUUM"]


class Api2000InputError(PcsError):
    """API 2000 通风量输入校验失败（422）。"""

    code = "API2000_RELIEF_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class Api2000ReliefInput:
    """API 2000 通风量计算输入（frozen dataclass）。

    物理量 SI 单位：体积 m³、面积 m²、压力 kPa、热输入 W。
    """

    tank_volume_m3: float
    wetted_area_m2: float
    design_pressure_kpa: float
    vacuum_pressure_kpa: float
    fire_heat_input_w: float | None
    vessel_geometry: WettedAreaInput | None = None
    environment_factor: float = _FIRE_ENV_FACTOR_DEFAULT
    scenario: Scenario = "FIRE"
    imperial_units: bool = False


@dataclass(frozen=True)
class Api2000ReliefResult:
    """API 2000 通风量计算结果（frozen dataclass）。

    字段：
      - required_relief_rate_w: 火灾/紧急工况热输入率 W
      - required_relief_rate_m3_h: 真空/正常工况体积流量 m³/h
      - scenario_used: 实际使用工况
      - formula_used: 本工况公式描述
      - imperial_conversion: imperial 双单位输出（imperial_units=True 时填充）
      - formula_ref: 公式溯源（fire/vacuum/emergency/wetted_area_source 4 项）
    """

    required_relief_rate_w: float
    required_relief_rate_m3_h: float
    scenario_used: Scenario
    formula_used: str
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: Api2000ReliefInput) -> None:
    """F2 边界 + environment_factor ∈ [0, 1] 校验。"""
    if inp.tank_volume_m3 <= 0:
        raise Api2000InputError(f"V={inp.tank_volume_m3} 必须 > 0")
    if inp.wetted_area_m2 < 0:
        raise Api2000InputError(f"A_wetted={inp.wetted_area_m2} 不能为负")
    if inp.design_pressure_kpa < 0 or inp.vacuum_pressure_kpa < 0:
        raise Api2000InputError("压力不能为负")
    if not (0.0 <= inp.environment_factor <= 1.0):
        raise Api2000InputError(f"F={inp.environment_factor} 越界 [0, 1]")


def calc_api2000_relief_capacity(inp: Api2000ReliefInput) -> Api2000ReliefResult:
    """API 2000 7th Ed 通风量计算（SPEC §3.5.1 V1.4）。

    计算项：
      - NORMAL：Q=0（委派 breathing_valve_service）
      - FIRE：Q(W) = 43192·F·A_wetted^0.82 SI
      - VACUUM：Q(m³/h) = 1013·A_wetted
      - EMERGENCY：Q = 1.5 × FIRE（同 SI 单位）

    vessel_geometry 非 None 时调 C-12 calc_wetted_area（D7 接口冻结）覆盖 inp.wetted_area_m2。

    Args:
        inp: Api2000ReliefInput（frozen）

    Returns:
        Api2000ReliefResult（frozen）

    Raises:
        Api2000InputError: 输入校验失败（F2 V/A 极值、F 环境因子越界）
    """
    _validate_input(inp)

    a_wetted_used = inp.wetted_area_m2
    if inp.vessel_geometry is not None:
        wa_result = calc_wetted_area(inp.vessel_geometry)
        a_wetted_used = wa_result.wetted_area_m2

    if inp.scenario == "FIRE":
        q_w = _API2000_FIRE_COEFF_W * inp.environment_factor * a_wetted_used ** 0.82
        q_m3_h = q_w * _W_TO_M3H
        formula = "Q(W) = 43192·F·A^0.82 [API 2000 7th §3.4 SI]"
    elif inp.scenario == "VACUUM":
        q_m3_h = _API2000_VACUUM_COEFF * a_wetted_used
        q_w = q_m3_h / _W_TO_M3H
        formula = "Q(m³/h) = 1013·A [API 2000 7th §3.6]"
    elif inp.scenario == "EMERGENCY":
        q_fire = _API2000_FIRE_COEFF_W * inp.environment_factor * a_wetted_used ** 0.82
        q_w = q_fire * _API2000_EMERGENCY_MULTIPLIER
        q_m3_h = q_w * _W_TO_M3H
        formula = "Q = 1.5 × FIRE [API 2000 §3.5 emergency]"
    else:  # NORMAL 委派 breathing_valve_service
        q_w = 0.0
        q_m3_h = 0.0
        formula = "NORMAL 走 breathing_valve_service（已有）"

    imperial = None
    if inp.imperial_units:
        imperial = {
            "required_relief_rate_btu_hr": q_w * _BTU_HR_PER_W,
            "tank_volume_gallons_us": inp.tank_volume_m3 * _GALLON_US_PER_M3,
            "wetted_area_ft2": inp.wetted_area_m2 * _FT2_PER_M2,
        }

    return Api2000ReliefResult(
        required_relief_rate_w=q_w,
        required_relief_rate_m3_h=q_m3_h,
        scenario_used=inp.scenario,
        formula_used=formula,
        imperial_conversion=imperial,
        formula_ref={
            "fire_formula": "Q(W) = 43192·F·A^0.82 [API 2000 7th §3.4 SI]",
            "vacuum_formula": "Q(m³/h) = 1013·A [API 2000 7th §3.6]",
            "emergency_formula": "Q = 1.5 × FIRE [API 2000 §3.5]",
            "wetted_area_source": (
                "调用 C-12 calc_wetted_area (D7 接口冻结) "
                "if vessel_geometry else inp.wetted_area_m2"
            ),
        },
    )


__all__ = [
    "Api2000ReliefInput",
    "Api2000ReliefResult",
    "Api2000InputError",
    "calc_api2000_relief_capacity",
    "Scenario",
]