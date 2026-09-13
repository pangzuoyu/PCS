"""P4-1-2 step 2：6 个闪蒸计算（BUBBLE/DEW/PH/PS）+ golden fixtures。

P4-1-2 step 1 已落 PT_FLASH；step 2 落地其余 6 个计算。

算法：
- BUBBLE_P / DEW_P：直接公式（Raoult 定律，sum(z*K)=1 / sum(z/K)=1）
- BUBBLE_T / DEW_T：brentq in [200, 600] K（RR 单相容差 1e-10）
- PH_FLASH：brentq on P in [1e3, 1e8] Pa（外层 P 迭代，内层 PT_FLASH 算 H）
- PS_FLASH：brentq on vfrac in [eps, 1-eps]，内层 brentq on P 求 vfrac→P 映射
           （vfrac 与 P 在 2-phase 区是一一对应；按 spec 字面要求 iterate vfrac）

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
from app.services.flash.thermo_factory import ThermoInterface

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


__all__ = [
    "PTFlashResult",
    "PT_FLASH",
    "BUBBLE_P",
    "BUBBLE_T",
    "DEW_P",
    "DEW_T",
    "PH_FLASH",
    "PS_FLASH",
    "FlashConvergenceError",
]
