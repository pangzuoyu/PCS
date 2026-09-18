"""P5-3-7 API 520 9th Ed. **Annex C.2.2 Two-Point Omega Method** 完整实现。

依据：API STD 520 Part I **9th Ed.（2014-07）** Annex C.2.2（Sizing for Two-Phase
Vapour/Liquid Relief）— 与 relief_area_service / fire_case_service 一致的项目基线版本。

**Two-Point Omega Method**（DIERS / Leung 1996 标准化形式）：

  Step 1  Eq C.12   ω = 9 × (ρ_lo / ρ_g − 1)  ≡  9 × (v_g / v_o − 1)
                              ρ_lo = PRV 入口两相密度  v_o = 其比容
                              ρ_g  = 0.9 × P_o 处蒸汽密度  v_g = 其比容

  Step 2  Eq C.13   P_c = η_c × P_o  临界当  P_c ≥ P_a  亚临界当  P_c < P_a
          Eq C.14   η_c 隐式方程（二分法求根）：
                   η_c² + (ω² − 2ω)(1 − η_c)² + 2ω² ln η_c + 2ω²(1 − η_c) = 0
          Eq C.15   η_c 近似（fallback，物理大 ω 时精度下降）

  Step 3  Eq C.18   critical:     G = η_c × √(P_o / (v_o × ω))
          Eq C.19   subcritical:  G = √{−2[ω ln η_a + (ω−1)(1−η_a)]} /
                                    (ω(1/η_a − 1) + 1) × √(P_o / v_o)
                              η_a = P_a / P_o

  Step 4  Eq C.21   A = 277.8 × W / (K_d × K_b × K_c × K_v × G)
                              W in kg/h, G in kg/s·m², A in mm²

适用范围：flashing liquid / two-phase vapour-liquid relief（V1 简化 Leung 1996
形式 7th Ed. Appendix D 同源；C7 关闭后 C.2.2 形式为规范）。

**与 V1 简化形式（relief_area_service.calc_relief_area_api520_two_phase）的关系**：
- V1 简化 ω ∈ [0, 1]（x_v / x_v_lim，调用方传）；C.2.2 完整 ω ∈ [0, ∞)
  （密度比推算，与 Leung 1996 形式有可量化的偏差）
- 两者并存：V1 简化保留（向后兼容，outlet 透传），本模块为 Annex C.2.2 完整版
- 默认 `omega_two_point_area` 为新代码首选；C.2.2 与 V1 同时可用，按需选用
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError
from app.services.psv.relief_area_service import ReliefAreaFormulaRef

# ---------- 异常 ----------


class TwoPointOmegaInputError(PcsError):
    """Annex C.2.2 输入非法（422）。"""

    code = "PSV_INPUT_ERROR"
    status = 422


# ---------- 输入输出 ----------


@dataclass(frozen=True)
class TwoPointOmegaInput:
    """API 520 9th Ed. Annex C.2.2 Two-Point Omega Method 输入（SI 主链）。

    字段：
      - mass_flow_kgs: 所需泄放质量流量 kg/s（来自 relief_aggregator）
      - P_relieving_pa: 泄放压力 P_o（Pa）= P_set × 1.10 + P_atm
      - P_backpressure_pa: 背压 P_a（Pa）= 出口侧总压
      - v_inlet_m3_per_kg: PRV 入口两相比容 v_o（m³/kg）= 1/ρ_lo
      - v_vapor_0_9Po_m3_per_kg: 0.9 × P_o 处蒸汽比容 v_g（m³/kg）= 1/ρ_g
      - K_d, K_b, K_c, K_v: 排放/背压/组合/粘度修正系数（默认 API 520 典型值）
    """

    mass_flow_kgs: float
    P_relieving_pa: float
    P_backpressure_pa: float
    v_inlet_m3_per_kg: float
    v_vapor_0_9Po_m3_per_kg: float
    K_d: float = 0.85
    K_b: float = 1.0
    K_c: float = 1.0
    K_v: float = 1.0


@dataclass(frozen=True)
class TwoPointOmegaResult:
    """API 520 9th Ed. Annex C.2.2 Two-Point Omega Method 结果。

    字段：
      - omega: Eq C.12（无量纲，物理上 ≥ 0；高含气率可达 ~10）
      - eta_critical: Eq C.14 解（critical pressure ratio, P_c / P_o）
      - P_critical_pa: Eq C.13b 临界压力（Pa）
      - eta_backpressure: 背压比 P_a / P_o
      - flow_regime: "critical" (P_c ≥ P_a) 或 "subcritical" (P_c < P_a)
      - mass_flux_kgs_per_m2: Eq C.18 (critical) 或 C.19 (subcritical) 质量通量
      - area_mm2: Eq C.21 所需有效泄放面积（mm²）
      - area_m2: 转换至 m²（A_mm² × 1e-6）
      - formula_ref: 公式溯源（standard / version / clause）
    """

    omega: float
    eta_critical: float
    P_critical_pa: float
    eta_backpressure: float
    flow_regime: Literal["critical", "subcritical"]
    mass_flux_kgs_per_m2: float
    area_mm2: float
    area_m2: float
    formula_ref: ReliefAreaFormulaRef


# ---------- 物理常量与二分法配置 ----------


# Eq C.14 单调递增（见 docstring 推导）；二分区间 [η_low, η_high]
_ETA_LOW: Final[float] = 1.0e-6
_ETA_HIGH: Final[float] = 0.999999
_BISECT_TOL: Final[float] = 1.0e-12
_BISECT_MAX_ITER: Final[int] = 200

# Eq C.21: A_mm² = 277.8 × W_kg_h / (K_d × K_b × K_c × K_v × G_kg_s_m²)
# 277.8 ≡ 1e6 / 3600（单位换算 kg/h → kg/s；m² → mm²）
_EQ_C21_SI_CONST: Final[float] = 277.8


# ---------- 核心方程 ----------


def _f_eta_c(eta_c: float, omega: float) -> float:
    """Eq C.14 隐式方程左侧（f(η_c) = 0 为根）。

        f(η_c) = η_c² + (ω² − 2ω)(1 − η_c)² + 2ω² ln η_c + 2ω²(1 − η_c)

    物理性态：ω > 0 时 f 在 (0, 1) 上严格单调递增（df/dη_c > 0，详见
    cerebrum P5-3-7 推导），所以二分法是闭区间唯一根方法。
    """
    if eta_c <= 0.0:
        return float("nan")
    one_minus_eta = 1.0 - eta_c
    return (
        eta_c * eta_c
        + (omega * omega - 2.0 * omega) * (one_minus_eta * one_minus_eta)
        + 2.0 * omega * omega * math.log(eta_c)
        + 2.0 * omega * omega * one_minus_eta
    )


def _solve_eta_critical(omega: float) -> float:
    """Eq C.14 二分法求根 → η_c（P_c / P_o 临界压比）。

    边界：
      - ω ≤ 0：调用方已拦截（v_g/v_o 必须 > 0）
      - ω → 0 (单相气体极限)：η_c → 0.5 附近；二分法自动收敛
      - ω → ∞ (单相液体极限)：η_c → 1.0 附近；二分法自动收敛
    """
    if omega < 0.0:
        raise TwoPointOmegaInputError(f"omega={omega} 必须 ≥ 0（Eq C.12 ρ_lo/ρ_g > 0）")
    if omega == 0.0:
        # 退化情况：两相含气率 0 → 单相气体；η_c 物理上趋近 0.5
        return 0.5
    lo, hi = _ETA_LOW, _ETA_HIGH
    f_lo = _f_eta_c(lo, omega)
    f_hi = _f_eta_c(hi, omega)
    if not (math.isfinite(f_lo) and math.isfinite(f_hi)):
        raise TwoPointOmegaInputError(
            f"Eq C.14 二分区间端点非有限值（ω={omega}, f_lo={f_lo}, f_hi={f_hi}）"
        )
    if f_lo * f_hi > 0:
        # 物理上 f_lo < 0 < f_hi 总应成立；如出现异常给出明确诊断
        raise TwoPointOmegaInputError(
            f"Eq C.14 在 (η_low, η_high) 区间内无变号根（ω={omega}, "
            f"f_lo={f_lo:.3e}, f_hi={f_hi:.3e}）"
        )
    for _ in range(_BISECT_MAX_ITER):
        mid = 0.5 * (lo + hi)
        f_mid = _f_eta_c(mid, omega)
        if f_mid == 0.0 or (hi - lo) < _BISECT_TOL:
            return mid
        if f_lo * f_mid < 0:
            hi, f_hi = mid, f_mid
        else:
            lo, f_lo = mid, f_mid
    return 0.5 * (lo + hi)


# ---------- 主函数 ----------


def omega_two_point_area(inp: TwoPointOmegaInput) -> TwoPointOmegaResult:
    """API 520 9th Ed. Annex C.2.2 Two-Point Omega Method 完整实现。

    步骤（与 API 520 9th Ed. C.2.2.3 一致）：
      a) Step 1 — Eq C.12 由 v_o, v_g 推算 omega
      b) Step 2 — Eq C.14 二分法求 η_c → P_c = η_c × P_o
      c) Step 2 — 判定 critical (P_c ≥ P_a) / subcritical
      d) Step 3 — Eq C.18 (critical) 或 Eq C.19 (subcritical) 算 G
      e) Step 4 — Eq C.21 算 A（mm²）；同步换算到 m²

    边界：
      - v_inlet / v_vapor 必须 > 0（物理量下限）
      - P_relieving 必须 > P_backpressure（否则 η_a ≥ 1，Eq C.19 开方项为负）
      - W 必须 > 0
      - K 系数乘积必须 > 0
      - omega → 0 单相退化：物理上是单相气体，调用方应改走 API 520 §5.6.3
        （本函数仍正确计算但 η_c = 0.5 是经验占位）

    参考算例（API 520 9th Ed. C.2.2.2-3）：
      v_o = 0.01945 m³/kg, v_g = 0.02265 m³/kg → ω = 1.482
      P_o = 556,379 Pa, P_a = 204,700 Pa
      → η_c ≈ 0.658（图 C.1 0.66）→ P_c = 366,950 Pa > 204,700 = critical
      → G = 2900 kg/s·m²（图 C.1 验证为 594.1 lb/s·ft²）
      → W = 216,560 kg/h, K_d = 0.85 → A = 24,400 mm²
    """
    # --- 输入校验 ---
    if inp.mass_flow_kgs <= 0:
        raise TwoPointOmegaInputError(
            f"mass_flow_kgs={inp.mass_flow_kgs} 必须 > 0"
        )
    if inp.P_relieving_pa <= 0:
        raise TwoPointOmegaInputError(
            f"P_relieving_pa={inp.P_relieving_pa} 必须 > 0"
        )
    if inp.P_backpressure_pa <= 0:
        raise TwoPointOmegaInputError(
            f"P_backpressure_pa={inp.P_backpressure_pa} 必须 > 0"
        )
    if inp.P_backpressure_pa >= inp.P_relieving_pa:
        # η_a ≥ 1 物理上不合理；Eq C.19 开方项 (1 − η_a) → 负
        raise TwoPointOmegaInputError(
            f"P_backpressure_pa={inp.P_backpressure_pa} 必须 < "
            f"P_relieving_pa={inp.P_relieving_pa}（否则背压比 η_a ≥ 1 无效）"
        )
    if inp.v_inlet_m3_per_kg <= 0:
        raise TwoPointOmegaInputError(
            f"v_inlet_m3_per_kg={inp.v_inlet_m3_per_kg} 必须 > 0"
        )
    if inp.v_vapor_0_9Po_m3_per_kg <= 0:
        raise TwoPointOmegaInputError(
            f"v_vapor_0_9Po_m3_per_kg={inp.v_vapor_0_9Po_m3_per_kg} 必须 > 0"
        )
    k_product = inp.K_d * inp.K_b * inp.K_c * inp.K_v
    if k_product <= 0:
        raise TwoPointOmegaInputError(
            f"K_d×K_b×K_c×K_v = {k_product} 必须 > 0"
        )

    # --- Step 1: Eq C.12 — ω = 9 × (v_g / v_o − 1) ---
    # 数学上 ρ_lo/ρ_g ≡ v_g/v_o（比容与密度互为倒数）
    omega = 9.0 * (inp.v_vapor_0_9Po_m3_per_kg / inp.v_inlet_m3_per_kg - 1.0)
    if omega < 0.0:
        # 物理上当 v_g < v_o（蒸汽比容小于两相比容，对应 v_g/v_o < 1）会出现；
        # 这时 ω < 0 表明无 vapor 释放（subcooled liquid 路径），非本函数范围
        raise TwoPointOmegaInputError(
            f"ω={omega:.4f} < 0（v_g < v_o）：无 vapor 释放，"
            f"应改用 subcooled liquid 路径（API 520 9th Ed. C.2.3）"
        )

    # --- Step 2: Eq C.14 二分法 → η_c → P_c = η_c × P_o ---
    eta_c = _solve_eta_critical(omega)
    P_c = eta_c * inp.P_relieving_pa
    eta_a = inp.P_backpressure_pa / inp.P_relieving_pa

    # --- Step 2: critical / subcritical 判定 ---
    if P_c >= inp.P_backpressure_pa:
        flow_regime: Literal["critical", "subcritical"] = "critical"
        # --- Step 3 critical: Eq C.18 — G = η_c × √(P_o / (v_o × ω)) ---
        if omega == 0.0:
            # 已在上方 early return 拦截；这里仅作类型守卫
            raise TwoPointOmegaInputError("ω=0 不可达 Eq C.18 分母")
        G = eta_c * math.sqrt(inp.P_relieving_pa / (inp.v_inlet_m3_per_kg * omega))
    else:
        flow_regime = "subcritical"
        # --- Step 3 subcritical: Eq C.19 ---
        # G = √{−2[ω ln η_a + (ω−1)(1−η_a)]} / (ω(1/η_a − 1) + 1) × √(P_o / v_o)
        bracket = -2.0 * (omega * math.log(eta_a) + (omega - 1.0) * (1.0 - eta_a))
        if bracket < 0:
            # 物理上 bracket 应 ≥ 0（P_c < P_a 时亚临界 flow 成立）
            raise TwoPointOmegaInputError(
                f"Eq C.19 开方项 {bracket:.4e} < 0（ω={omega:.4f}, η_a={eta_a:.4f}）"
            )
        denom = omega * (1.0 / eta_a - 1.0) + 1.0
        if denom <= 0:
            raise TwoPointOmegaInputError(
                f"Eq C.19 分母 {denom:.4e} ≤ 0（ω={omega:.4f}, η_a={eta_a:.4f}）"
            )
        G = math.sqrt(bracket) / denom * math.sqrt(inp.P_relieving_pa / inp.v_inlet_m3_per_kg)

    if G <= 0:
        raise TwoPointOmegaInputError(f"Eq C.18/C.19 质量通量 G={G} 非正")

    # --- Step 4: Eq C.21 — A = 277.8 × W_kg_h / (K_d × K_b × K_c × K_v × G) ---
    # W_kg_h = W_kg_s × 3600；A_mm² × 1e-6 = A_m²
    W_kg_h = inp.mass_flow_kgs * 3600.0
    A_mm2 = _EQ_C21_SI_CONST * W_kg_h / (k_product * G)
    if A_mm2 <= 0:
        raise TwoPointOmegaInputError(f"Eq C.21 计算面积 {A_mm2} mm² 非正")
    A_m2 = A_mm2 * 1.0e-6

    return TwoPointOmegaResult(
        omega=omega,
        eta_critical=eta_c,
        P_critical_pa=P_c,
        eta_backpressure=eta_a,
        flow_regime=flow_regime,
        mass_flux_kgs_per_m2=G,
        area_mm2=A_mm2,
        area_m2=A_m2,
        formula_ref=ReliefAreaFormulaRef(
            standard="API_520", version="9th", clause="Annex C.2.2",
        ),
    )


__all__ = [
    "TwoPointOmegaInput",
    "TwoPointOmegaResult",
    "TwoPointOmegaInputError",
    "omega_two_point_area",
]
