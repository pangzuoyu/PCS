"""AS 1210/1797 + 管破裂 + 控制阀失效工况（SPEC §3.7.2 V1.4）。

3 case + AS 标准：
  - TUBE_RUPTURE（AS 1210 §4.3.1）：PSV 设定 ≥ 1.10·MAWP
  - CONTROL_VALVE_FAILURE（AS 1210 §4.3.2）：按失效模式
  - FIRE_CASE（AS 1210 §4.4 + API 521 §3.4）：外部火灾

调用 C-12 公共服务（D7 接口冻结，ADR-0041 v7）：
  - calc_wetted_area 算 wetted_area_m2（火灾工况，vessel_geometry 非 None 时覆盖）

公式溯源：
  - TUBE_RUPTURE：AS 1210 §4.3.1 set_p = pressure_factor · MAWP
  - CV FAILURE：AS 1210 §4.3.2 AIR_FAIL=1.10 / SIGNAL_FAIL=1.20 / POWER_FAIL=1.15
  - FIRE_CASE：Q(W) = 43192·F·A^0.82 [API 521 §3.4 SI 严格换算]
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.services._compound_config_cache import get_delta_h_vap_table
from app.services.exceptions import PcsError
from app.services.vessel.vessel_service import (
    WettedAreaInput,
    calc_wetted_area,
)

# L-2 v1 BLOCKER：SIGNAL_FAIL = 1.20（最严重）
_CV_FAILURE_FACTORS: Final[dict[str, float]] = {
    "AIR_FAIL": 1.10,
    "SIGNAL_FAIL": 1.20,
    "POWER_FAIL": 1.15,
}
# API 521 §3.4 / AS 1210 §4.4 火灾热输入 SI 严格换算（与 B4 共用系数）
_FIRE_COEFF_W: Final[float] = 43192.0
# 火灾工况环境因子默认（无保温）
_FIRE_ENV_FACTOR_DEFAULT: Final[float] = 1.0
# ΔH_vap 默认 2260 kJ/kg（按典型轻烃/水简化）
_DHVAP_KJ_KG: Final[float] = 2260.0
# 火灾工况指数默认 0.82（API 521 §3.4 / AS 1210 §4.4 SI 严格换算）
_FIRE_COEFF_EXP_DEFAULT: Final[float] = 0.82
# F2 压力因子边界
_PRESSURE_FACTOR_MIN: Final[float] = 1.05
_PRESSURE_FACTOR_MAX: Final[float] = 1.30
# imperial 双单位换算系数
_KPA_PER_PSIA: Final[float] = 0.1450377
_KG_PER_LB: Final[float] = 0.45359237
_KG_S_TO_LB_S: Final[float] = 2.20462  # = 1 / _KG_PER_LB
# 控制阀失效容量折减（失效放空仅承担部分管破裂流量）
_CV_FAIL_CAPACITY_FRACTION: Final[float] = 0.5

Scenario = Literal["TUBE_RUPTURE", "CONTROL_VALVE_FAILURE", "FIRE_CASE"]
CvFailureMode = Literal["AIR_FAIL", "SIGNAL_FAIL", "POWER_FAIL"]


class As1210InputError(PcsError):
    """AS 1210/1797 设定压力输入校验失败（422）。"""

    code = "AS1210_RELIEF_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class As1210ReliefInput:
    """AS 1210/1797 设定压力校核输入（frozen dataclass）。

    物理量 SI 单位：压力 kPa、质量流量 kg/s、面积 m²、压力因子无量纲。
    """

    mawp_kpa: float
    tube_rupture_mass_kg_s: float
    control_valve_failure_mode: CvFailureMode
    fire_case_wetted_area_m2: float
    as1210_pressure_factor: float
    scenario: Scenario
    vessel_geometry: WettedAreaInput | None = None
    environment_factor: float = _FIRE_ENV_FACTOR_DEFAULT
    delta_h_vap_kj_kg: float = _DHVAP_KJ_KG
    use_xls_convention: bool = False  # P6-6B T12: True → XLS 208 (DB), False → 2260
    fire_case_coefficient: float = _FIRE_COEFF_W
    fire_case_exponent: float = _FIRE_COEFF_EXP_DEFAULT
    imperial_units: bool = False


@dataclass(frozen=True)
class As1210ReliefResult:
    """AS 1210/1797 设定压力校核结果（frozen dataclass）。

    字段：
      - required_set_pressure_kpa: PSV 设定压力（kPa）
      - required_relief_capacity_kg_s: 所需泄放容量（kg/s）
      - as_standard: 适用 AS 条款
      - pressure_factor: 实际采用的压力因子
      - imperial_conversion: imperial 双单位输出（imperial_units=True 时填充）
      - formula_ref: 公式溯源（tube_rupture / cv_failure / fire_case / wetted 4 项）
    """

    required_set_pressure_kpa: float
    required_relief_capacity_kg_s: float
    as_standard: str
    pressure_factor: float
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _resolve_delta_h_vap(use_xls_convention: bool = False) -> float:
    """从 ``compound_delta_h_vap_natural_gas`` CONFIG 表加载 ΔH_vap。

    默认 ``use_xls_convention=False`` → ``TYPICAL_2260`` (2260 kJ/kg, GPSA
    §3.4 typical natural gas, 向后兼容默认口径)；
    ``use_xls_convention=True`` → ``XLS_CONVENTION_208`` (208 kJ/kg, XLS
    PR-025 implicit convention, OPEN-P6-6A-5 Ruling 9/14 关闭)；
    DB 不可达或表为空时 fallback 到内联 2260（默认值，向后兼容）。

    P6-6B T12 引入；open OPEN-P6-6A-5 关闭。
    """
    table = get_delta_h_vap_table()
    if table is None:
        return _DHVAP_KJ_KG
    return table.get(
        "XLS_CONVENTION_208" if use_xls_convention else "TYPICAL_2260",
        _DHVAP_KJ_KG,
    )


def _validate_input(inp: As1210ReliefInput) -> None:
    """F2 边界 + MAWP > 0 校验。"""
    if inp.mawp_kpa <= 0:
        raise As1210InputError(f"MAWP={inp.mawp_kpa} 必须 > 0")
    if inp.tube_rupture_mass_kg_s < 0:
        raise As1210InputError(
            f"管破裂流量={inp.tube_rupture_mass_kg_s} 不能为负"
        )
    if inp.fire_case_wetted_area_m2 < 0:
        raise As1210InputError(
            f"火灾 wetted area={inp.fire_case_wetted_area_m2} 不能为负"
        )
    if not (_PRESSURE_FACTOR_MIN <= inp.as1210_pressure_factor <= _PRESSURE_FACTOR_MAX):
        raise As1210InputError(
            f"压力因子={inp.as1210_pressure_factor} "
            f"越界 [{_PRESSURE_FACTOR_MIN}, {_PRESSURE_FACTOR_MAX}]"
        )
    if inp.control_valve_failure_mode not in _CV_FAILURE_FACTORS:
        raise As1210InputError(
            f"控制阀失效模式={inp.control_valve_failure_mode} 不在 "
            f"{list(_CV_FAILURE_FACTORS.keys())} 中"
        )
    if inp.delta_h_vap_kj_kg <= 0:
        raise As1210InputError(f"ΔH_vap={inp.delta_h_vap_kj_kg} 必须 > 0")
    if inp.fire_case_coefficient <= 0:
        raise As1210InputError(f"火灾系数={inp.fire_case_coefficient} 必须 > 0")
    if not (0 < inp.fire_case_exponent <= 5):
        raise As1210InputError(f"火灾指数={inp.fire_case_exponent} 越界 (0, 5]")


def calc_as1210_relief_sizing(inp: As1210ReliefInput) -> As1210ReliefResult:
    """AS 1210/1797 设定压力校核（SPEC §3.7.2 V1.4）。

    计算项：
      - TUBE_RUPTURE：set_p = as1210_pressure_factor · MAWP（默认 1.10）
      - CONTROL_VALVE_FAILURE：set_p = CV factor · MAWP（AIR/SIGNAL/POWER 三模式）
      - FIRE_CASE：set_p = as1210_pressure_factor · MAWP，capacity = Q_fire / ΔH_vap
        其中 Q_fire(W) = 43192·F·A_wetted^0.82

    vessel_geometry 非 None 时调 C-12 calc_wetted_area（D7 接口冻结）覆盖
    inp.fire_case_wetted_area_m2。

    Args:
        inp: As1210ReliefInput（frozen）

    Returns:
        As1210ReliefResult（frozen）

    Raises:
        As1210InputError: 输入校验失败（MAWP ≤ 0、pressure_factor 越界等）
    """
    _validate_input(inp)

    a_wetted_used = inp.fire_case_wetted_area_m2
    if inp.vessel_geometry is not None:
        wa_result = calc_wetted_area(inp.vessel_geometry)
        a_wetted_used = wa_result.wetted_area_m2

    # P6-6B T12: use_xls_convention 切换 ΔH_vap 口径（默认 False → 2260 GPSA 2260 向后兼容）。
    if inp.use_xls_convention:
        dh_vap_resolved = _resolve_delta_h_vap(use_xls_convention=True)
    else:
        dh_vap_resolved = inp.delta_h_vap_kj_kg

    if inp.scenario == "TUBE_RUPTURE":
        set_p = inp.as1210_pressure_factor * inp.mawp_kpa
        capacity = inp.tube_rupture_mass_kg_s
        as_std = "AS 1210 §4.3.1"
        pressure_factor = inp.as1210_pressure_factor
    elif inp.scenario == "CONTROL_VALVE_FAILURE":
        factor = _CV_FAILURE_FACTORS[inp.control_valve_failure_mode]
        set_p = factor * inp.mawp_kpa
        capacity = inp.tube_rupture_mass_kg_s * _CV_FAIL_CAPACITY_FRACTION
        as_std = f"AS 1210 §4.3.2 ({inp.control_valve_failure_mode})"
        pressure_factor = factor
    else:  # FIRE_CASE
        set_p = inp.as1210_pressure_factor * inp.mawp_kpa
        q_fire_w = (
            inp.fire_case_coefficient
            * inp.environment_factor
            * a_wetted_used ** inp.fire_case_exponent
        )
        capacity = q_fire_w / (dh_vap_resolved * 1000.0)  # kJ/kg → J/kg
        as_std = "AS 1210 §4.4 + API 521 §3.4"
        pressure_factor = inp.as1210_pressure_factor

    imperial = None
    if inp.imperial_units:
        imperial = {
            "required_set_pressure_psig": set_p * _KPA_PER_PSIA,
            "required_relief_capacity_lb_s": capacity * _KG_S_TO_LB_S,
        }

    return As1210ReliefResult(
        required_set_pressure_kpa=set_p,
        required_relief_capacity_kg_s=capacity,
        as_standard=as_std,
        pressure_factor=pressure_factor,
        imperial_conversion=imperial,
        formula_ref={
            "tube_rupture": (
                f"AS 1210 §4.3.1 set_p = {inp.as1210_pressure_factor:.2f}·MAWP"
            ),
            "control_valve_failure": (
                f"AS 1210 §4.3.2 factor = {_CV_FAILURE_FACTORS} "
                f"(L-2 BLOCKER: SIGNAL_FAIL=1.20 最严重)"
            ),
            "fire_case": (
                f"AS 1210 §4.4 + API 521 §3.4 "
                f"Q(W) = {inp.fire_case_coefficient}·F·A^"
                f"{inp.fire_case_exponent} [fluid-specific]; "
                f"capacity = Q/(ΔH_vap·1000); ΔH_vap={dh_vap_resolved} kJ/kg"
            ),
            "wetted_area_source": (
                "调用 C-12 calc_wetted_area (D7 接口冻结) "
                "if vessel_geometry else inp.fire_case_wetted_area_m2"
            ),
        },
    )


__all__ = [
    "As1210ReliefInput",
    "As1210ReliefResult",
    "As1210InputError",
    "calc_as1210_relief_sizing",
    "Scenario",
    "CvFailureMode",
]