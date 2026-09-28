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
  - FIRE_CASE：Q(W) = coeff·F·A^0.82
    - API_521（默认）：coeff=43192 [API 521 §3.4 SI 严格换算]
    - AS_1210 path (a)：coeff=7.2e4 [AS 1210 §4.4 SI 严格换算]
    - fire_case_standard 枚举选系数（OPEN-P6-6A-5 真正关闭，P6-7 T7）
    - **放弃 2.457 系数**（工艺室追溯来源不明）
  - FIRE_CASE path (b) gas/vapor（NEW T8 OPEN-P6-6A-10）：
    m' = m·Y_p + m'_p, Y_p = 10000 / (C_w·t·T_o)（10,000 W/m² pool fire）
  - FIRE_CASE Jet fire（NEW T8 OPEN-P6-6A-10）：
    m' = m·Y_t + m'_p, Y_t = 110000 / (C_w·t·T_r)（110,000 W/m² jet fire）
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final, Literal

from app.services._compound_config_cache import (
    get_api521_thresholds_table,
    get_delta_h_vap_table,
)
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
# T8 OPEN-P6-6A-10: 增加 "Jet fire" 标准（path (b) gas/vapor 仍用 "AS_1210" 标准
# 标识，通过 m_gas_stored_kg > 0 在 calc_fire_case 内分支 path (a)/(b)）。
FireCaseStandard = Literal["API_521", "AS_1210", "Jet fire"]
# Jet fire 热通量（AS 1210 §4.4 jet fire 路径 vs pool fire 10,000 W/m²）
_JET_FIRE_HEAT_FLUX_W_M2: Final[float] = 110_000.0
# AS 1210 §4.4 pool fire 热通量（path (b) gas/vapor 默认）
_POOL_FIRE_HEAT_FLUX_W_M2: Final[float] = 10_000.0


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
    fire_case_standard: FireCaseStandard = "API_521"
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


def _resolve_fire_case_coefficient(standard: FireCaseStandard) -> float:
    """从 ``compound_api521_thresholds`` CONFIG 表读取 fire coefficient。

    Returns:
        API_521 → 43192.0（W = 43192·F·A^0.82，CONFIG 表
        ``FIRE_COEFF_DEFAULT`` key 优先；DB 不可达或 key 缺失时 fallback 到
        内联 43192.0）；AS_1210 → 7.2e4（path (a) m' = 7.2e4·F·A^0.82/L，
        AS 1210 §4.4 SI 严格换算，P6-6A-8 Ruling 15）；
        Jet fire → 110_000.0（AS 1210 §4.4 jet fire 热通量 W/m²，
        P6-7 T8 OPEN-P6-6A-10；用于 calc_fire_case 路由分支 heat flux 上限）。

    OPEN-P6-6A-5 真正关闭（工艺室 2026-09-28 签署"分 path 并存"裁决）；
    **放弃 2.457 系数**（工艺室追溯来源不明，参见 P6-7 T7 brief）。
    """
    if standard == "API_521":
        table = get_api521_thresholds_table()  # 5 min TTL 缓存
        if table is not None:
            return table.get("FIRE_COEFF_DEFAULT", 43192.0)
        return 43192.0  # 内联 fallback
    if standard == "AS_1210":
        return 7.2e4  # AS 1210 path (a) 默认值，硬编码
    if standard == "Jet fire":
        return _JET_FIRE_HEAT_FLUX_W_M2  # 110_000.0 W/m²，AS 1210 §4.4 jet fire
    raise ValueError(f"Unknown fire_case_standard: {standard!r}")


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

    # P6-7 T7 OPEN-P6-6A-5 真正关闭：fire_case_standard 选系数；
    # 用户显式 fire_case_coefficient != 默认 43192 时（worley_c21 /
    # OPEN-P6-6A-8 Ruling 15 XLS G54/G55 对账）保留用户覆盖优先级。
    if inp.fire_case_coefficient != _FIRE_COEFF_W:
        effective_coeff = inp.fire_case_coefficient
    else:
        effective_coeff = _resolve_fire_case_coefficient(inp.fire_case_standard)

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
            effective_coeff
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
                f"Q(W) = {effective_coeff}·F·A^"
                f"{inp.fire_case_exponent} [fluid-specific]; "
                f"capacity = Q/(ΔH_vap·1000); ΔH_vap={dh_vap_resolved} kJ/kg"
            ),
            "wetted_area_source": (
                "调用 C-12 calc_wetted_area (D7 接口冻结) "
                "if vessel_geometry else inp.fire_case_wetted_area_m2"
            ),
            "fire_case_standard": inp.fire_case_standard,
            "coefficient": effective_coeff,
        },
    )


# ============================================================================
# T8 OPEN-P6-6A-10 — AS 1210 §4.4 path (b) gas/vapor + Jet fire (110,000 W/m²)
# path (b) gas/vapor 标准标识仍为 "AS_1210"；通过 m_gas_stored_kg > 0 在
# calc_fire_case 内分支 path (a) 既有公式 vs path (b) m' = m·Y_p + m'_p 公式。
# Jet fire 是独立 FireCaseStandard 枚举值，路由到 _jet_fire 公式。
# ============================================================================


@dataclass(frozen=True)
class FireCaseInput:
    """T8 火灾工况输入（AS 1210 path (b) + Jet fire + 既有 path (a) + API 521）。

    字段：
      - wetted_area_m2: 润湿面积 m²（API_521 / AS_1210 path (a) 用）
      - latent_heat_kj_kg: 气化潜热 kJ/kg（API_521 / AS_1210 path (a) 用）
      - environment_factor_F: 环境因子 F（默认 1.0 无保温）
      - fire_case_standard: 标准枚举（"API_521" / "AS_1210" / "Jet fire"）
      - m_gas_stored_kg: 气体储罐质量 kg（path (b) gas/vapor + Jet fire）
      - c_w_kj_per_m3_k: 壁面体积热容 C_w kJ/(m³·K)（path (b) + Jet fire）
      - t_wall_mm: 壁厚 t mm（path (b) + Jet fire）
      - t_o_k: 设计温度 T_o K（path (b) gas/vapor）
      - t_r_k: 泄放温度 T_r K（Jet fire）
      - m_p_prime_kg_s: 其他泄放流量 m'_p kg/s（path (b) + Jet fire 加项）

    T8 OPEN-P6-6A-10：path (b) 与 Jet fire 字段默认 0.0，不传时 calc_fire_case
    仍走既有 API_521 / AS_1210 path (a) 公式（向后兼容 T7 既有行为）。
    """

    wetted_area_m2: float = 0.0
    latent_heat_kj_kg: float = 0.0
    environment_factor_F: float = 1.0
    fire_case_standard: FireCaseStandard = "API_521"
    m_gas_stored_kg: float = 0.0
    c_w_kj_per_m3_k: float = 0.0
    t_wall_mm: float = 0.0
    t_o_k: float = 0.0
    t_r_k: float = 0.0
    m_p_prime_kg_s: float = 0.0


@dataclass(frozen=True)
class FireCaseResult:
    """T8 火灾工况计算结果。

    字段：
      - required_mass_flow_kg_s: 所需泄放质量流量 kg/s
      - formula_ref: 公式溯源（含 fire_case_standard + coefficient + calculation）
    """

    required_mass_flow_kg_s: float
    formula_ref: dict[str, Any] = field(default_factory=dict)


def _path_b_gas_vapor(
    m_gas_stored_kg: float,
    c_w_kj_per_m3_k: float,
    t_wall_mm: float,
    t_o_k: float,
    m_p_prime_kg_s: float = 0.0,
) -> float:
    """AS 1210 §4.4 path (b) gas/vapor（T8 OPEN-P6-6A-10）。

    m' = m · Y_p + m'_p
    Y_p = 10,000 / (C_w · t · T_o)  [10,000 W/m² = pool fire 热通量]

    Args:
        m_gas_stored_kg: 气体储罐质量 m（kg）
        c_w_kj_per_m3_k: 壁面体积热容 C_w（kJ/(m³·K)）
        t_wall_mm: 壁厚 t（mm）
        t_o_k: 设计温度 T_o（K）
        m_p_prime_kg_s: 其他泄放流量 m'_p（kg/s，加项）

    Returns:
        m' = m · Y_p + m'_p（kg/s）
    """
    y_p = _POOL_FIRE_HEAT_FLUX_W_M2 / (c_w_kj_per_m3_k * t_wall_mm * t_o_k)
    return m_gas_stored_kg * y_p + m_p_prime_kg_s


def _jet_fire(
    m_gas_stored_kg: float,
    c_w_kj_per_m3_k: float,
    t_wall_mm: float,
    t_r_k: float,
    m_p_prime_kg_s: float = 0.0,
) -> float:
    """AS 1210 §4.4 jet fire 110,000 W/m²（T8 OPEN-P6-6A-10）。

    m' = m · Y_t + m'_p
    Y_t = 110,000 / (C_w · t · T_r)  [110,000 W/m² = jet fire 热通量]

    与 path (b) gas/vapor 公式形态一致，热通量从 pool fire 10,000 升至
    jet fire 110,000；泄放温度用 T_r（relief temperature）而非 T_o。

    Args:
        m_gas_stored_kg: 气体储罐质量 m（kg）
        c_w_kj_per_m3_k: 壁面体积热容 C_w（kJ/(m³·K)）
        t_wall_mm: 壁厚 t（mm）
        t_r_k: 泄放温度 T_r（K）
        m_p_prime_kg_s: 其他泄放流量 m'_p（kg/s，加项）

    Returns:
        m' = m · Y_t + m'_p（kg/s）
    """
    y_t = _JET_FIRE_HEAT_FLUX_W_M2 / (c_w_kj_per_m3_k * t_wall_mm * t_r_k)
    return m_gas_stored_kg * y_t + m_p_prime_kg_s


def calc_fire_case(inp: FireCaseInput) -> FireCaseResult:
    """T8 火灾工况计算入口（3-way 路由 by fire_case_standard）。

    路由：
      - "Jet fire" → _jet_fire() 公式（m' = m·Y_t + m'_p，Y_t = 110000/(C_w·t·T_r)）
      - "AS_1210" + m_gas_stored_kg > 0 → _path_b_gas_vapor()（path (b) gas/vapor）
      - "AS_1210" + m_gas_stored_kg == 0 → path (a) 既有公式
        （Q = 7.2e4·F·A^0.82, capacity = Q/(L·1000)）
      - "API_521" → 既有公式（Q = 43192·F·A^0.82, capacity = Q/(L·1000)）

    Args:
        inp: FireCaseInput（frozen）

    Returns:
        FireCaseResult（frozen，含 required_mass_flow_kg_s + formula_ref）

    T8 OPEN-P6-6A-10：本函数是 AS 1210 §4.4 path (b) + Jet fire 的代码侧入口，
    与 calc_as1210_relief_sizing 完全独立（后者仍走 T7 既有的 Q-based 公式）。
    """
    if inp.fire_case_standard == "Jet fire":
        mass_flow = _jet_fire(
            inp.m_gas_stored_kg,
            inp.c_w_kj_per_m3_k,
            inp.t_wall_mm,
            inp.t_r_k,
            inp.m_p_prime_kg_s,
        )
        return FireCaseResult(
            required_mass_flow_kg_s=mass_flow,
            formula_ref={
                "fire_case_standard": "Jet fire",
                "coefficient": _JET_FIRE_HEAT_FLUX_W_M2,
                "calculation": (
                    "AS 1210 §4.4 jet fire (110,000 W/m²): "
                    "m' = m·Y_t + m'_p, Y_t = 110000/(C_w·t·T_r)"
                ),
                "heat_flux_w_m2": _JET_FIRE_HEAT_FLUX_W_M2,
                "Y_t_per_s": (
                    _JET_FIRE_HEAT_FLUX_W_M2
                    / (
                        inp.c_w_kj_per_m3_k
                        * inp.t_wall_mm
                        * inp.t_r_k
                    )
                    if (inp.c_w_kj_per_m3_k > 0 and inp.t_wall_mm > 0 and inp.t_r_k > 0)
                    else None
                ),
            },
        )

    if inp.fire_case_standard == "AS_1210" and inp.m_gas_stored_kg > 0:
        # path (b) gas/vapor：m_gas_stored_kg > 0 触发；与既有 path (a) 公式
        # 完全独立（path (b) 不依赖 wetted_area / latent_heat）
        mass_flow = _path_b_gas_vapor(
            inp.m_gas_stored_kg,
            inp.c_w_kj_per_m3_k,
            inp.t_wall_mm,
            inp.t_o_k,
            inp.m_p_prime_kg_s,
        )
        return FireCaseResult(
            required_mass_flow_kg_s=mass_flow,
            formula_ref={
                "fire_case_standard": "AS_1210",
                "coefficient": _POOL_FIRE_HEAT_FLUX_W_M2,
                "calculation": (
                    "AS 1210 §4.4 path (b) gas/vapor: "
                    "m' = m·Y_p + m'_p, Y_p = 10000/(C_w·t·T_o)"
                ),
                "heat_flux_w_m2": _POOL_FIRE_HEAT_FLUX_W_M2,
                "Y_p_per_s": (
                    _POOL_FIRE_HEAT_FLUX_W_M2
                    / (
                        inp.c_w_kj_per_m3_k
                        * inp.t_wall_mm
                        * inp.t_o_k
                    )
                    if (
                        inp.c_w_kj_per_m3_k > 0
                        and inp.t_wall_mm > 0
                        and inp.t_o_k > 0
                    )
                    else None
                ),
            },
        )

    # 既 path (a) AS_1210 / API_521：Q = coeff·F·A^0.82, capacity = Q/(L·1000)
    if inp.fire_case_standard == "API_521":
        coeff = 43192.0
        clause = "API 521 §3.4 (SI)"
    else:  # AS_1210 path (a)
        coeff = 7.2e4
        clause = "AS 1210 §4.4 path (a) (SI)"
    q_fire_w = coeff * inp.environment_factor_F * inp.wetted_area_m2 ** 0.82
    mass_flow = q_fire_w / (inp.latent_heat_kj_kg * 1000.0) if inp.latent_heat_kj_kg > 0 else 0.0
    return FireCaseResult(
        required_mass_flow_kg_s=mass_flow,
        formula_ref={
            "fire_case_standard": inp.fire_case_standard,
            "coefficient": coeff,
            "calculation": (
                f"{clause}: Q(W) = {coeff}·F·A^0.82; "
                f"capacity = Q/(ΔH_vap·1000); ΔH_vap={inp.latent_heat_kj_kg} kJ/kg"
            ),
            "heat_flux_w_m2": None,
        },
    )


__all__ = [
    "As1210ReliefInput",
    "As1210ReliefResult",
    "As1210InputError",
    "calc_as1210_relief_sizing",
    "Scenario",
    "CvFailureMode",
    "FireCaseStandard",
    "FireCaseInput",
    "FireCaseResult",
    "calc_fire_case",
    "_path_b_gas_vapor",
    "_jet_fire",
]