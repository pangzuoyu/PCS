"""P4-1-2 step 3：SATURATION 纯组分饱和 + golden fixtures。

P4-1-2 step 1 已落 PT_FLASH；step 2 落地其余 6 个计算（BUBBLE/DEW/PH/PS）；
step 3 收口纯组分饱和 SATURATION。

算法：
- BUBBLE_P / DEW_P：直接公式（Raoult 定律，sum(z*K)=1 / sum(z/K)=1）
- BUBBLE_T / DEW_T：brentq in [200, 600] K（RR 单相容差 1e-10）
- PH_FLASH：brentq on P in [1e3, 1e8] Pa（外层 P 迭代，内层 PT_FLASH 算 H）
- PS_FLASH：brentq on vfrac in [eps, 1-eps]，内层 brentq on P 求 vfrac→P 映射
           （vfrac 与 P 在 2-phase 区是一一对应；按 spec 字面要求 iterate vfrac）
- SATURATION（step 3）：water → iapws95_Tsat/Psat；hydrocarbon → Wagner + Clapeyron；
                     fluid 名/CAS 双输入；临界检查 + h_fg J/kg。

H/S 模型：占位（理想液体 + 理想气体 + Raoult K），由 ``_WagnerBaseThermo.H_PT`` /
``_WagnerBaseThermo.S_PT`` 提供；P4-1-3+ 由 native 物性包替换为 Peng-Robinson /
SRK / NRTL 真实物性（仅影响精度，PH/PS roundtrip 自洽性不受影响）。

收敛失败：``FlashConvergenceError``（继承 PcsError，status=422，
code=FLASH_CONVERGENCE_ERROR）。
"""
from __future__ import annotations

from typing import NamedTuple

from scipy.optimize import brentq

from app.services.exceptions import PcsError
from app.services.flash.thermo_factory import (
    _CRITICAL_TABLE,
    _TB_TABLE,
    _WAGNER_TABLE,
    ThermoInterface,
    _hydrocarbon_h_fg_j_per_kg,
    _wagner_psat,
    _water_h_fg_j_per_kg,
    _water_Psat,
    _water_Tsat,
    resolve_fluid_cas,
)

# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class FlashConvergenceError(PcsError):
    """Flash 迭代未收敛或目标值超出物理范围。

    触发场景：
    - BUBBLE_T / DEW_T 在 [200, 600] K 无解
    - PH_FLASH H_target 超出 [H(v=1), H(v=0)] 物理范围
    - PS_FLASH S_target 超出 [S(v=1), S(v=0)] 物理范围
    """

    code = "FLASH_CONVERGENCE_ERROR"
    status = 422


class SaturationInputError(PcsError):
    """SATURATION 输入错误。

    触发场景：
    - fluid 不识别（不在 FLUID_NAME_TO_CAS，也不在 _WAGNER_TABLE）
    - P 和 T 都给 / 都不给（互斥约束失败）
    """

    code = "SATURATION_INPUT_ERROR"
    status = 422


class SaturationRangeError(PcsError):
    """SATURATION 范围错误：输入超出临界点（超临界态无法定义饱和曲线）。

    触发场景：
    - P > Pc（超临界压力）
    - T > Tc（超临界温度）
    """

    code = "SATURATION_OUT_OF_RANGE"
    status = 422


# ---------------------------------------------------------------------------
# PT_FLASH（step 1 已实现）
# ---------------------------------------------------------------------------


class PTFlashResult(NamedTuple):
    """PT flash 返回值。"""

    vapor_fraction: float
    y_vapor: list[float]
    x_liquid: list[float]


def PT_FLASH(
    zs: list[float], T: float, P: float, thermo: ThermoInterface
) -> PTFlashResult:
    """PT flash：等温等压闪蒸。

    Args:
        zs: 总组成（须已归一化 — 与 ThermoInterface 契约一致）
        T: 系统温度 (K)
        P: 系统压力 (Pa)
        thermo: thermo 后端实例

    Returns:
        PTFlashResult(vapor_fraction, y_vapor, x_liquid)
    """
    vfrac, x, y = thermo.FlashPT(zs, T, P)
    return PTFlashResult(vapor_fraction=vfrac, y_vapor=list(y), x_liquid=list(x))


# ---------------------------------------------------------------------------
# 工具：bracketing helper
# ---------------------------------------------------------------------------


# P 迭代区间 [P_LO, P_HI]（Pa）— 覆盖真空到高压凝气
_P_LO = 1.0e3
_P_HI = 1.0e8

# T 迭代区间 [T_LO, T_HI]（K）— 覆盖轻烃低温到临界区
_T_LO = 200.0
_T_HI = 600.0

# vfrac 边界 epsilon（避开单相退化）
_VFRAC_EPS = 1.0e-6


# ---------------------------------------------------------------------------
# BUBBLE_P / DEW_P（直接公式 — Raoult 定律）
# ---------------------------------------------------------------------------


def BUBBLE_P(zs: list[float], T: float, thermo: ThermoInterface) -> float:
    """泡点压力：sum(z_i * K_i) = 1 求 P；Raoult 定律下 P = sum(z_i * Psat_i(T))。

    Args:
        zs: 总组成（须已归一化）
        T: 系统温度 (K)
        thermo: thermo 后端实例

    Returns:
        泡点压力 (Pa)
    """
    n = len(zs)
    return sum(zs[i] * thermo.Psat(i, T) for i in range(n))


def DEW_P(zs: list[float], T: float, thermo: ThermoInterface) -> float:
    """露点压力：sum(z_i / K_i) = 1 求 P；Raoult 定律下 P = 1 / sum(z_i / Psat_i(T))。

    Args:
        zs: 总组成（须已归一化）
        T: 系统温度 (K)
        thermo: thermo 后端实例

    Returns:
        露点压力 (Pa)
    """
    n = len(zs)
    return 1.0 / sum(zs[i] / thermo.Psat(i, T) for i in range(n))


# ---------------------------------------------------------------------------
# BUBBLE_T / DEW_T（brentq 迭代）
# ---------------------------------------------------------------------------


def BUBBLE_T(zs: list[float], P: float, thermo: ThermoInterface) -> float:
    """泡点温度：sum(z_i * Psat_i(T)) = P 求 T；brentq in [_T_LO, _T_HI]。

    Args:
        zs: 总组成（须已归一化）
        P: 系统压力 (Pa)
        thermo: thermo 后端实例

    Returns:
        泡点温度 (K)

    Raises:
        FlashConvergenceError: 在 [_T_LO, _T_HI] K 区间内无解
    """
    n = len(zs)

    def f(T: float) -> float:
        return sum(zs[i] * thermo.Psat(i, T) for i in range(n)) - P

    try:
        return brentq(f, _T_LO, _T_HI, xtol=1e-10)
    except ValueError as e:
        raise FlashConvergenceError(
            f"BUBBLE_T 未在 [{_T_LO}, {_T_HI}] K 区间内收敛：P={P}",
            details={"P_Pa": P, "T_range": [_T_LO, _T_HI]},
        ) from e


def DEW_T(zs: list[float], P: float, thermo: ThermoInterface) -> float:
    """露点温度：1 / sum(z_i / Psat_i(T)) = P 求 T；brentq in [_T_LO, _T_HI]。

    Args:
        zs: 总组成（须已归一化）
        P: 系统压力 (Pa)
        thermo: thermo 后端实例

    Returns:
        露点温度 (K)

    Raises:
        FlashConvergenceError: 在 [_T_LO, _T_HI] K 区间内无解
    """
    n = len(zs)

    def f(T: float) -> float:
        return 1.0 / sum(zs[i] / thermo.Psat(i, T) for i in range(n)) - P

    try:
        return brentq(f, _T_LO, _T_HI, xtol=1e-10)
    except ValueError as e:
        raise FlashConvergenceError(
            f"DEW_T 未在 [{_T_LO}, {_T_HI}] K 区间内收敛：P={P}",
            details={"P_Pa": P, "T_range": [_T_LO, _T_HI]},
        ) from e


# ---------------------------------------------------------------------------
# PH_FLASH（brentq on P）
# ---------------------------------------------------------------------------


def PH_FLASH(
    zs: list[float],
    T: float,
    H: float,
    thermo: ThermoInterface,
    P_guess: float = 1.0e5,
) -> tuple[float, float, list[float], list[float]]:
    """PH flash：迭代 P 直到 PT_FLASH 的 H 收敛到给定 H；返回 (P, vfrac, y, x)。

    算法：brentq on P in [_P_LO, _P_HI]；H 来自 ``thermo.H_PT`` 占位模型
    （理想液体 + 理想气体）。H_target 超出 [H(v=1, P_lo), H(v=0, P_hi)]
    物理范围时 raise FlashConvergenceError。

    Args:
        zs: 总组成（须已归一化）
        T: 系统温度 (K)
        H: 目标焓 (J/mol)
        thermo: thermo 后端实例
        P_guess: 初始压力猜测（仅文档化；brentq 内部使用 [_P_LO, _P_HI] 区间）

    Returns:
        (P, vfrac, y_vapor, x_liquid)

    Raises:
        FlashConvergenceError: H_target 超出物理范围或 brentq 失败
    """
    def H_at_P(P: float) -> float:
        res = PT_FLASH(zs, T, P, thermo)
        return thermo.H_PT(zs, T, P, res.vapor_fraction, res.y_vapor, res.x_liquid)

    # 物理范围检查：v=1 (P_lo) → H_min；v=0 (P_hi) → H_max
    H_lo = H_at_P(_P_LO)
    H_hi = H_at_P(_P_HI)
    if H < min(H_lo, H_hi) - 1e-3 or H > max(H_lo, H_hi) + 1e-3:
        raise FlashConvergenceError(
            f"PH_FLASH H_target={H} 超出物理范围 [{H_lo}, {H_hi}]（T={T} K）",
            details={
                "H_target": H,
                "H_range": [H_lo, H_hi],
                "T_K": T,
            },
        )

    try:
        P = brentq(lambda P: H_at_P(P) - H, _P_LO, _P_HI, xtol=1e-3)
    except ValueError as e:
        raise FlashConvergenceError(
            f"PH_FLASH brentq 未在 [{_P_LO}, {_P_HI}] Pa 区间内收敛：H={H} T={T}",
            details={"H_target": H, "T_K": T, "P_range": [_P_LO, _P_HI]},
        ) from e

    res = PT_FLASH(zs, T, P, thermo)
    return (P, res.vapor_fraction, res.y_vapor, res.x_liquid)


# ---------------------------------------------------------------------------
# PS_FLASH（brentq on vfrac，内层 brentq on P 求 vfrac→P 映射）
# ---------------------------------------------------------------------------


def _vfrac_to_P(
    zs: list[float], T: float, vfrac_target: float, thermo: ThermoInterface
) -> float:
    """PS_FLASH 内部：在 2-phase 区反解 PT_FLASH 求 P 使 vfrac 收敛到 vfrac_target。

    使用 brentq in [_P_LO, _P_HI]。若 vfrac_target 在 2-phase 边界外（v=0 或
    v=1 单相），P 落在 [_P_LO, _P_HI] 区间边界附近（vfrac 单调，P 收敛）。
    """
    def f(P: float) -> float:
        res = PT_FLASH(zs, T, P, thermo)
        return res.vapor_fraction - vfrac_target

    return brentq(f, _P_LO, _P_HI, xtol=1e-3)


def PS_FLASH(
    zs: list[float],
    T: float,
    S: float,
    thermo: ThermoInterface,
    vfrac_guess: float = 0.5,
) -> tuple[float, list[float], list[float], float]:
    """PS flash：迭代 vfrac 直到 PT_FLASH 的 S 收敛到给定 S；返回 (vfrac, y, x, P)。

    算法：brentq on vfrac in [_VFRAC_EPS, 1 - _VFRAC_EPS]；每次内层 brentq on P
    求 vfrac→P 映射（vfrac 与 P 在 2-phase 区一一对应）。S 来自
    ``thermo.S_PT`` 占位模型（理想液体 + 理想气体）。

    Args:
        zs: 总组成（须已归一化）
        T: 系统温度 (K)
        S: 目标熵 (J/mol/K)
        thermo: thermo 后端实例
        vfrac_guess: 初始 vfrac 猜测（仅文档化；brentq 内部使用 [_VFRAC_EPS, 1 - _VFRAC_EPS] 区间）

    Returns:
        (vfrac, y_vapor, x_liquid, P)

    Raises:
        FlashConvergenceError: S_target 超出物理范围或 brentq 失败
    """
    def S_at_vfrac(v: float) -> float:
        P = _vfrac_to_P(zs, T, v, thermo)
        res = PT_FLASH(zs, T, P, thermo)
        return thermo.S_PT(zs, T, P, res.vapor_fraction, res.y_vapor, res.x_liquid)

    # 物理范围检查
    S_lo = S_at_vfrac(1.0 - _VFRAC_EPS)
    S_hi = S_at_vfrac(_VFRAC_EPS)
    if S < min(S_lo, S_hi) - 1e-3 or S > max(S_lo, S_hi) + 1e-3:
        raise FlashConvergenceError(
            f"PS_FLASH S_target={S} 超出物理范围 [{S_lo}, {S_hi}]（T={T} K）",
            details={
                "S_target": S,
                "S_range": [S_lo, S_hi],
                "T_K": T,
            },
        )

    try:
        vfrac = brentq(
            lambda v: S_at_vfrac(v) - S,
            _VFRAC_EPS,
            1.0 - _VFRAC_EPS,
            xtol=1e-9,
        )
    except ValueError as e:
        raise FlashConvergenceError(
            f"PS_FLASH brentq 未在 [{_VFRAC_EPS}, {1.0 - _VFRAC_EPS}] vfrac 区间内收敛：S={S}",
            details={"S_target": S, "T_K": T, "vfrac_range": [_VFRAC_EPS, 1.0 - _VFRAC_EPS]},
        ) from e

    P = _vfrac_to_P(zs, T, vfrac, thermo)
    res = PT_FLASH(zs, T, P, thermo)
    return (res.vapor_fraction, res.y_vapor, res.x_liquid, P)


# ---------------------------------------------------------------------------
# SATURATION（step 3 — 纯组分饱和曲线 P(T) / T(P) + 潜热 h_fg）
# ---------------------------------------------------------------------------


def SATURATION(
    fluid: str, P: float | None = None, T: float | None = None
) -> tuple[float, float]:
    """纯组分饱和：根据给定 P 或 T，返回 (other_var, h_fg)。

    算法：
    - water (CAS 7732-18-5)：T_sat = iapws95_Tsat(P)；P_sat = iapws95_Psat(T)；
      h_fg = T*(V_g - V_l)*dPsat/dT（iapws95 Clapeyron J/kg）
    - 其它流体（hydrocarbon/polar）：T_sat = Wagner 牛顿反演 / P_sat =
      Wagner_original(T)；h_fg = Clapeyron 方程 dZ=1（J/kg）
    - fluid 名大小写不敏感；CAS 号直接接受

    Args:
        fluid: 流体名（如 "WATER" / "PROPANE" / "N_BUTANE"）或 CAS 号
        P: 给定压力 (Pa)；与 T 互斥
        T: 给定温度 (K)；与 P 互斥

    Returns:
        (other_var, h_fg)：
        - P 给定时返回 (T_sat_K, h_fg_J_per_kg)
        - T 给定时返回 (P_sat_Pa, h_fg_J_per_kg)

    Raises:
        SaturationInputError: P 和 T 都给 / 都不给 / fluid 不识别
        SaturationRangeError: 输入超出临界点范围（T > Tc 或 P > Pc）
    """
    # 1) 互斥检查：P 和 T 必须二选一
    if (P is None) == (T is None):
        raise SaturationInputError(
            "SATURATION 必须只给定 P 或 T 之一；"
            f"当前 P={P}, T={T}",
            details={"P": P, "T": T},
        )

    # 2) fluid 解析（名 → CAS；大小写不敏感）
    try:
        cas = resolve_fluid_cas(fluid)
    except KeyError as e:
        raise SaturationInputError(
            f"SATURATION 无法识别 fluid={fluid!r}；"
            f"支持的 fluid 名：WATER / METHANE / ETHANE / PROPANE / N_BUTANE / "
            f"ISOPENTANE / N_HEXANE / METHANOL，或 _WAGNER_TABLE 中的 CAS 号",
            details={"fluid": fluid},
        ) from e

    # 3) 临界检查 + 计算
    Tc, Pc, _omega = _CRITICAL_TABLE[cas]
    is_water = cas == "7732-18-5"

    if P is not None:
        # P 给定 → 求 T_sat + h_fg
        if P > Pc:
            raise SaturationRangeError(
                f"SATURATION P={P} Pa 超出 Pc={Pc} Pa（fluid={fluid} 超临界）",
                details={"P": P, "Pc": Pc, "fluid": fluid},
            )
        if is_water:
            T_sat = _water_Tsat(P)
            h_fg = _water_h_fg_j_per_kg(T_sat)
        else:
            # T_sat：Wagner 牛顿反演
            T_sat = _tsat_from_wagner(cas, P)
            # h_fg：Wagner Psat(T_sat) → Clapeyron
            Psat_at_T = _wagner_psat(cas, T_sat)
            h_fg = _hydrocarbon_h_fg_j_per_kg(cas, T_sat, Psat_at_T)
        return (T_sat, h_fg)

    else:  # T is not None
        # T 给定 → 求 P_sat + h_fg
        if T > Tc:
            raise SaturationRangeError(
                f"SATURATION T={T} K 超出 Tc={Tc} K（fluid={fluid} 超临界）",
                details={"T": T, "Tc": Tc, "fluid": fluid},
            )
        if is_water:
            P_sat = _water_Psat(T)
            h_fg = _water_h_fg_j_per_kg(T)
        else:
            P_sat = _wagner_psat(cas, T)
            h_fg = _hydrocarbon_h_fg_j_per_kg(cas, T, P_sat)
        return (P_sat, h_fg)


def _tsat_from_wagner(cas: str, P: float) -> float:
    """Wagner 方程牛顿反演求 T_sat（hydrocarbon 路径）。

    复用 thermo_factory._WagnerBaseThermo.Tsat 的牛顿逻辑：初值 Tmin*0.9，
    收敛容差 1 Pa。P 与 Psat 差 < 1 Pa 视为收敛。
    """
    from chemicals.vapor_pressure import dWagner_dT

    Tc, Pc, a, b, c, d, _Tmin = _WAGNER_TABLE[cas]
    T_guess = max(_TB_TABLE.get(cas, 300.0) * 0.9, 100.0)
    for _ in range(50):
        P_calc = _wagner_psat(cas, T_guess)
        dPdT = dWagner_dT(T_guess, Tc, Pc, a, b, c, d)
        if dPdT == 0:
            break
        err = P_calc - P
        if abs(err) < 1.0:  # Pa — 1 Pa 是 Wagner 在 T_bubble 量级的精度
            return T_guess
        T_guess = T_guess - err / dPdT
        if T_guess < 50.0:
            T_guess = 50.0
        if T_guess > Tc * 0.999:
            T_guess = Tc * 0.999
    return T_guess


__all__ = [
    "PTFlashResult",
    "PT_FLASH",
    "BUBBLE_P",
    "BUBBLE_T",
    "DEW_P",
    "DEW_T",
    "PH_FLASH",
    "PS_FLASH",
    "SATURATION",
    "FlashConvergenceError",
    "SaturationInputError",
    "SaturationRangeError",
]
