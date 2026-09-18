"""P4-2-1：管道选型服务（预定流速法 + 设定压力降法 + DN 圆整）。

算法：
- 预定流速法（``size_by_velocity``）：D = 1000 × √(V / (0.785 × v))
  （V 单位 m³/s，v 单位 m/s；D 单位 mm；0.785 ≈ π/4 简化版）。
  v 取自 _VELOCITY_TARGETS（HG/T 20570.6-95 表 5.1 推荐区间中心），
  按 fluid_phase（LIQUID / GAS / STEAM / TWO_PHASE）取。
- 设定压力降法（``size_by_dp``）：迭代 DN 序列找最小 DN 使 Darcy-Weisbach
  + Colebrook 压降 ≤ dp_per_100m_kpa。
  - Darcy-Weisbach：ΔP = f × (L/D) × (ρ × v²/2)
  - L = 100 m，所以 ΔP_Pa/100m = f × (100/D) × (ρ × v²/2)
  - 转 kPa/100m：除以 1000
  - v = V / (π/4 × D²)，D 用 m
  - 摩擦系数 f：Colebrook-White 隐式方程，brentq 迭代
    1/√f = -2 log10(ε/(3.7D) + 2.51/(Re√f))，Re = ρvD/μ

DN 圆整策略：D > 当前 DN 时取上一档（HG/T 20570.6 越档+安全裕度）。

HG/T 20570.6-95 流速表溯源：``pcs-backend/app/seeds/category3_defaults.json``
``recommended_velocity.rows``（std_source="HG/T 20570.6-95 表 5.1"）。
本模块中心值取推荐区间中位，固化为模块顶部常量便于单测 golden。
"""

from __future__ import annotations

import math
from typing import Final, NamedTuple

from scipy.optimize import brentq

from app.services.exceptions import PcsError

# ---------------------------------------------------------------------------
# 异常
# ---------------------------------------------------------------------------


class PipeSizingInputError(PcsError):
    """PipeSizing 输入错误（业务非法）。

    触发场景：
    - V ≤ 0 或 v ≤ 0（物理非法）
    - fluid_phase 不识别（不在 LIQUID / GAS / STEAM / TWO_PHASE）
    - dp_per_100m_kpa ≤ 0
    - viscosity ≤ 0
    """

    code = "PIPE_SIZING_INPUT_ERROR"
    status = 422


class PipeSizingConvergenceError(PcsError):
    """PipeSizing 迭代未收敛或无合适 DN。

    触发场景：
    - D 计算值 < DN15（最小标准 DN） → 无合适 DN
    - dp 法全部标准 DN 都不满足 dp_per_100m_kpa → 即使最大 DN 也不够
    - Colebrook 方程在 [1e-3, 1e-1] 摩擦系数区间 brentq 未收敛
    """

    code = "PIPE_SIZING_CONVERGENCE_ERROR"
    status = 422


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------


# DN 标准系列（mm；GB/T 1047-2005 + HG/T 20570.6-95 推荐）
_DN_STANDARD_MM: Final[tuple[int, ...]] = (
    15, 20, 25, 32, 40, 50, 65, 80, 100, 125, 150, 200, 250, 300, 350, 400, 500,
)
_MIN_DN_MM: Final[int] = _DN_STANDARD_MM[0]
_MAX_DN_MM: Final[int] = _DN_STANDARD_MM[-1]


# fluid_phase 推荐流速（HG/T 20570.6-95 表 5.1 推荐区间中心）
# 液体 0.5-2.5 → 2.0；气体 10-30 → 20；蒸汽 20-40 饱和蒸汽 → 30；
# 两相 3-15 → 8。
# 溯源：pcs-backend/app/seeds/category3_defaults.json recommended_velocity.rows
_VELOCITY_TARGETS: Final[dict[str, float]] = {
    "LIQUID": 2.0,       # 一般液体
    "GAS": 20.0,         # 一般气体
    "STEAM": 30.0,       # 饱和蒸汽
    "TWO_PHASE": 8.0,    # 两相流（气液）
}


# Colebrook-White 摩擦系数求解区间
_F_LO: Final[float] = 1.0e-3   # 极光滑管下限
_F_HI: Final[float] = 1.0e-1   # 极粗糙管上限


# Darcy-Weisbach 计算长度（100 m），与 dp_per_100m_kpa 对齐
_DP_LENGTH_M: Final[float] = 100.0


# ---------------------------------------------------------------------------
# 类型定义
# ---------------------------------------------------------------------------


class DNResult(NamedTuple):
    """管道选型结果。

    Fields:
    - method: "velocity" 或 "dp"
    - D_calc_mm: 计算管径 (mm)
    - DN: 圆整 DN 字符串（如 "DN80"）
    - v_target_ms: 采用的流速 (m/s)（velocity 法：phase 推荐；dp 法：实际）
    - dp_per_100m_kpa: 压降 (kPa/100m)（dp 法填写；velocity 法为 None）
    - fluid_phase: 输入的流相
    """

    method: str
    D_calc_mm: float
    DN: str
    v_target_ms: float
    dp_per_100m_kpa: float | None
    fluid_phase: str


# ---------------------------------------------------------------------------
# 工具：DN 圆整 + 标签
# ---------------------------------------------------------------------------


def _round_dn(D_calc_mm: float) -> str:
    """圆整到 PIPE_CLASS 标准 DN 系列。

    HG/T 20570.6-95 越档+安全裕度策略：
    - D 在 (prev_DN, mid] 内归到 prev_DN（"D 大于 DN 时取上一档"；
      工程裕度容许 D 比 DN 略大不升档）
    - D 在 (mid, next_DN] 内归到 next_DN（"一档安全裕度"：D 接近 next_DN
      时仍升档，避免选小）
    - mid = (prev_DN + next_DN) / 2

    例：
    - D=50.5 → mid=(50+65)/2=57.5，50.5 ≤ 57.5 → DN50（不越档）
    - D=63.3 → 63.3 > 57.5 → DN65（越档）
    - D=79.788 → mid=(65+80)/2=72.5，79.788 > 72.5 → DN80

    Raises:
        PipeSizingConvergenceError: D < _MIN_DN_MM（最小标准 DN）
    """
    if D_calc_mm < _MIN_DN_MM:
        raise PipeSizingConvergenceError(
            f"D 计算值 {D_calc_mm:.3f} mm 小于最小标准 DN {_MIN_DN_MM} mm（无合适 DN）",
            details={"D_calc_mm": D_calc_mm, "min_DN_mm": _MIN_DN_MM},
        )
    # 向上找 next_DN (>= D)
    for i, dn in enumerate(_DN_STANDARD_MM):
        if dn >= D_calc_mm:
            if i == 0:
                # D 已在最小 DN 范围内或更小（不会触发因为 < _MIN_DN 已 raise）
                return f"DN{dn}"
            prev_dn = _DN_STANDARD_MM[i - 1]
            mid = (prev_dn + dn) / 2.0
            if D_calc_mm <= mid:
                return f"DN{prev_dn}"
            return f"DN{dn}"
    # D > 最大 DN（理论极端场景） → 取最大 DN
    return f"DN{_MAX_DN_MM}"


def _diameter_mm_to_m(d_mm: float) -> float:
    return d_mm / 1000.0


# ---------------------------------------------------------------------------
# Darcy-Weisbach + Colebrook 摩擦系数
# ---------------------------------------------------------------------------


def _colebrook_f(
    D_m: float, v_ms: float, rho: float, mu: float, eps_m: float
) -> float:
    """Colebrook-White 方程 brentq 求解摩擦系数 f。

    Colebrook：1/√f = -2 log10(ε/(3.7D) + 2.51/(Re√f))，Re = ρvD/μ。
    在 [_F_LO, _F_HI] 区间迭代。层流时（Re<2300）按 f=64/Re 返回。

    Args:
        D_m: 管径 (m)
        v_ms: 流速 (m/s)
        rho: 密度 (kg/m³)
        mu: 动力粘度 (Pa·s)
        eps_m: 绝对粗糙度 (m)

    Returns:
        Darcy 摩擦系数 f（无量纲）
    """
    if v_ms <= 0:
        return _F_LO  # 兜底：避免退化
    Re = rho * v_ms * D_m / mu
    if Re < 2300.0:
        return 64.0 / Re

    def colebrook_eq(f: float) -> float:
        """Colebrook-White 摩擦系数方程（隐式方程牛顿迭代残差）。

        步骤：
        1. 计算 1/√f + 2 log10(ε/(3.7D) + 2.51/(Re√f)) 残差
        2. term ≤ 0（log10 越界）→ 返回 1.0 提示需要更大 f（牛顿步方向）
        3. term > 0 → 返回完整残差供牛顿迭代收敛

        用途：在 solve_fluid 中作为 f 牛顿迭代的目标方程（迭代求 f）。
        与 Re 计算区别：本函数接受 f 返回方程残差；Re 仅算雷诺数（前置）。
        """
        # 1/√f + 2 log10(ε/(3.7D) + 2.51/(Re√f)) = 0
        sqrt_f = math.sqrt(f)
        term = eps_m / (3.7 * D_m) + 2.51 / (Re * sqrt_f)
        if term <= 0:
            # log10 越界：f 过大；返回正值提示需要更大 f
            return 1.0
        return 1.0 / sqrt_f + 2.0 * math.log10(term)

    try:
        return brentq(colebrook_eq, _F_LO, _F_HI, xtol=1e-8)
    except ValueError:
        # brentq 失败（区间无解或同号）：用 Swamee-Jain 显式近似兜底
        # Swamee-Jain：f = 0.25 / [log10(ε/(3.7D) + 5.74/Re^0.9)]^2
        sj_term = eps_m / (3.7 * D_m) + 5.74 / (Re ** 0.9)
        if sj_term <= 0:
            return _F_HI
        return 0.25 / (math.log10(sj_term) ** 2)


def _dp_per_100m_pa(
    D_m: float, v_ms: float, rho: float, mu: float, eps_m: float
) -> float:
    """Darcy-Weisbach 压降 (Pa)，长度 100 m。

    ΔP = f × (L/D) × (ρ × v²/2)，L = _DP_LENGTH_M (m)。
    """
    f = _colebrook_f(D_m, v_ms, rho, mu, eps_m)
    return f * (_DP_LENGTH_M / D_m) * (rho * v_ms ** 2 / 2.0)


# ---------------------------------------------------------------------------
# 入口：预定流速法
# ---------------------------------------------------------------------------


def size_by_velocity(
    V: float,
    fluid_phase: str,
    *,
    v_target_ms: float | None = None,
) -> DNResult:
    """预定流速法管道选型。

    公式：D = 1000 × √(V / (0.785 × v))，v 按 fluid_phase 取 HG/T 20570.6-95
    推荐值（默认）或调用者指定（v_target_ms 显式传入优先）。

    Args:
        V: 体积流量 (m³/s)；必须 > 0
        fluid_phase: 流相，必须在 LIQUID / GAS / STEAM / TWO_PHASE 之一
        v_target_ms: 推荐流速 (m/s)；None 时按 fluid_phase 默认值

    Returns:
        DNResult：method="velocity"，D_calc_mm + 圆整 DN。

    Raises:
        PipeSizingInputError: V ≤ 0 / v ≤ 0 / fluid_phase 未识别
        PipeSizingConvergenceError: D < 最小标准 DN
    """
    if V <= 0:
        raise PipeSizingInputError(
            f"velocity 法 V={V} 必须 > 0（物理非法）",
            details={"V_m3s": V},
        )
    if fluid_phase not in _VELOCITY_TARGETS:
        raise PipeSizingInputError(
            f"velocity 法 fluid_phase={fluid_phase!r} 未识别；"
            f"支持：{sorted(_VELOCITY_TARGETS.keys())}",
            details={"fluid_phase": fluid_phase},
        )
    v = v_target_ms if v_target_ms is not None else _VELOCITY_TARGETS[fluid_phase]
    if v <= 0:
        raise PipeSizingInputError(
            f"velocity 法 v_target_ms={v} 必须 > 0",
            details={"v_target_ms": v},
        )
    D_calc_mm = 1000.0 * math.sqrt(V / (0.785 * v))
    dn = _round_dn(D_calc_mm)
    return DNResult(
        method="velocity",
        D_calc_mm=D_calc_mm,
        DN=dn,
        v_target_ms=v,
        dp_per_100m_kpa=None,
        fluid_phase=fluid_phase,
    )


# ---------------------------------------------------------------------------
# 入口：设定压力降法
# ---------------------------------------------------------------------------


def size_by_dp(
    V: float,
    fluid_phase: str,
    dp_per_100m_kpa: float,
    *,
    viscosity: float | None = None,
    density: float | None = None,
    roughness_mm: float | None = None,
    max_dn_mm: float | None = None,
) -> DNResult:
    """设定压力降法管道选型（Darcy-Weisbach + Colebrook）。

    迭代 DN 序列找最小 DN 使 dp_per_100m_kpa ≤ 给定目标。

    Args:
        V: 体积流量 (m³/s)；必须 > 0
        fluid_phase: 流相（仅用于结果标记 + 默认物性；不参与算法）
        dp_per_100m_kpa: 目标压降 (kPa/100m)；必须 > 0
        viscosity: 动力粘度 (Pa·s)；None 时按 fluid_phase 默认
            （LIQUID → 1e-3 水；GAS / STEAM → 1e-5；TWO_PHASE → 1e-4）
        density: 密度 (kg/m³)；None 时按 fluid_phase 默认
            （LIQUID → 1000；GAS / STEAM → 10；TWO_PHASE → 500）
        roughness_mm: 绝对粗糙度 (mm)；None 时默认 0.045（碳钢使用中，
            来自 Crane TP-410 / 种子 pipe_roughness_default）
        max_dn_mm: 上限 DN (mm)；None 时用 _MAX_DN_MM。仅供测试/裁剪场景。

    Returns:
        DNResult：method="dp"，D_calc_mm（迭代中该 DN 的等效 D）+
        圆整 DN + 实际 dp_per_100m_kpa。

    Raises:
        PipeSizingInputError: V ≤ 0 / dp ≤ 0 / viscosity ≤ 0 / density ≤ 0
        PipeSizingConvergenceError: 全 DN 都不满足 / Colebrook 失败
    """
    if V <= 0:
        raise PipeSizingInputError(
            f"dp 法 V={V} 必须 > 0",
            details={"V_m3s": V},
        )
    if dp_per_100m_kpa <= 0:
        raise PipeSizingInputError(
            f"dp 法 dp_per_100m_kpa={dp_per_100m_kpa} 必须 > 0",
            details={"dp_per_100m_kpa": dp_per_100m_kpa},
        )
    # 默认物性（按 fluid_phase；LIQUID = 水）
    if viscosity is None:
        viscosity = {
            "LIQUID": 1.0e-3,
            "GAS": 1.0e-5,
            "STEAM": 1.0e-5,
            "TWO_PHASE": 1.0e-4,
        }.get(fluid_phase, 1.0e-3)
    if density is None:
        density = {
            "LIQUID": 1000.0,
            "GAS": 10.0,
            "STEAM": 10.0,
            "TWO_PHASE": 500.0,
        }.get(fluid_phase, 1000.0)
    if roughness_mm is None:
        roughness_mm = 0.045  # 碳钢使用中（Crane TP-410 / 种子）
    eps_m = roughness_mm / 1000.0

    if viscosity <= 0:
        raise PipeSizingInputError(
            f"dp 法 viscosity={viscosity} 必须 > 0",
            details={"viscosity_Pa_s": viscosity},
        )
    if density <= 0:
        raise PipeSizingInputError(
            f"dp 法 density={density} 必须 > 0",
            details={"density_kg_m3": density},
        )

    upper = max_dn_mm if max_dn_mm is not None else float(_MAX_DN_MM)
    # 在 [_MIN_DN_MM, upper] 区间内按 _DN_STANDARD_MM 顺序找最小满足项
    for d_mm in _DN_STANDARD_MM:
        if d_mm < _MIN_DN_MM or d_mm > upper:
            continue
        D_m = _diameter_mm_to_m(d_mm)
        A = math.pi * D_m ** 2 / 4.0
        v_ms = V / A
        dp_pa = _dp_per_100m_pa(D_m, v_ms, density, viscosity, eps_m)
        dp_kpa = dp_pa / 1000.0
        if dp_kpa <= dp_per_100m_kpa:
            return DNResult(
                method="dp",
                D_calc_mm=float(d_mm),
                DN=f"DN{int(d_mm)}",
                v_target_ms=v_ms,
                dp_per_100m_kpa=dp_kpa,
                fluid_phase=fluid_phase,
            )

    raise PipeSizingConvergenceError(
        f"dp 法全部 DN 至 {upper} mm 都无法满足 dp_per_100m_kpa={dp_per_100m_kpa}；"
        f"建议减小目标 / 检查物性 / 上调 max_dn_mm",
        details={
            "dp_target_kpa": dp_per_100m_kpa,
            "upper_DN_mm": upper,
            "V_m3s": V,
            "fluid_phase": fluid_phase,
        },
    )


__all__ = [
    "DNResult",
    "PipeSizingInputError",
    "PipeSizingConvergenceError",
    "size_by_velocity",
    "size_by_dp",
]