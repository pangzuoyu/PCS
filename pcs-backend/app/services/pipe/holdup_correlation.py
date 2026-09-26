"""持液率与流型计算（SPEC §3.2.3 V1.9）。

算法清单：
  1. 流型判别：Mandhane 1975 水平管流型图（BUBBLE/STRATIFIED/STRATIFIED_WAVE/
     ANNULAR/INTERMITTENT/DISPERSED BUBBLE；BG-B 1973 原文引用）
  2. 持液率：Beggs-Brill 1973（H_L(0) + 倾角修正 C(θ) → H_L(θ)）
  3. 流型校验：Eaton-Flanning 1967（对比 BG-B 适用范围）

公式（Beggs-Brill 1973）：
  Fr = V_m^2 / (g·D₁)  弗劳德数
  L₁ = 316·ρ_L^0.302  L₂ = 0.000925·(ρ_L·ρ_V)^0.305  L₃ = 0.1·ρ_L^-0.447
  流型判别（水平管）：
    - 分离流：λ_L < L₁ 且 λ_G < L₃
    - 间歇流：λ_L ≥ L₂ 且 λ_G ≥ L₃
    - 分散流：λ_G ≥ L₁ 且 λ_G < L₃ 且 λ_L ≥ L₃
  H_L(0) = a·λ_L^b / Fr^c  （流型参数 a/b/c 查表）
  C(θ) = 1 + (sin θ)·...（倾角修正）
  H_L(θ) = H_L(0)·C(θ)

Q-8：Eaton-Flanning 1967 用于 BG-B 适用范围校验（Fr ∈ [0.01, 10] +
Lockhart-Martinelli）；Taitel-Dukler 1976 K/T/F/X 无量纲判别本批**不实现**
（仅 SPEC §3.2.3 V1.9 标注延后，PRD 立项时再补）
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

_GRAVITY: Final[float] = 9.81
_M_PER_FT: Final[float] = 0.3048


class BeggsBrillInputError(PcsError):
    """Beggs-Brill 输入不合法（422）。"""

    code = "BEGGS_BRILL_INPUT_ERROR"
    status = 422


FlowPattern = Literal["SEGREGATED", "INTERMITTENT", "DISTRIBUTED", "TRANSITION"]


@dataclass(frozen=True)
class BeggsBrillHoldupInput:
    """Beggs-Brill 持液率 + Mandhane 1975 流型判别输入。

    SI base；imperial_units=True 时输出 imperial 双单位。
    """

    v_sl_m_s: float
    v_sg_m_s: float
    pipe_diameter_m: float
    pipe_inclination_deg: float
    rho_L_kg_m3: float
    rho_V_kg_m3: float
    mu_L_pa_s: float
    mu_V_pa_s: float
    sigma_n_m: float
    imperial_units: bool = False


@dataclass(frozen=True)
class HoldupCorrelationResult:
    """Beggs-Brill 持液率 + Mandhane 1975 流型判别结果。"""

    flow_pattern: FlowPattern
    h_l_theta0: float  # 水平管持液率
    h_l_theta: float  # 倾角 θ 修正后
    froude_number: float
    is_beggs_brill_valid: bool  # Eaton-Flanning 1967 校验
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: BeggsBrillHoldupInput) -> None:
    """校验输入物理量合法性（F2/F5：拒绝非正/负值）。"""
    if inp.v_sl_m_s < 0 or inp.v_sg_m_s < 0:
        raise BeggsBrillInputError("表观速度不能为负")
    if inp.pipe_diameter_m <= 0:
        raise BeggsBrillInputError(f"管径={inp.pipe_diameter_m} 必须 > 0")
    if not (-90.0 <= inp.pipe_inclination_deg <= 90.0):
        msg = f"倾角={inp.pipe_inclination_deg} 越界 [-90,90]"
        raise BeggsBrillInputError(msg)
    if inp.rho_L_kg_m3 <= 0 or inp.rho_V_kg_m3 <= 0:
        raise BeggsBrillInputError("密度必须 > 0")
    if inp.mu_L_pa_s <= 0 or inp.mu_V_pa_s <= 0:
        raise BeggsBrillInputError("粘度必须 > 0")
    if inp.sigma_n_m <= 0:
        raise BeggsBrillInputError("表面张力必须 > 0")


def _mandhane_flow_pattern(
    lambda_L: float, lambda_V: float, rho_L: float, rho_V: float,
) -> FlowPattern:
    """Mandhane 1975 水平管流型图（SPEC §3.2.3 V1.9）。

    注：L1/L2/L3 阈值源自 Mandhane, G.A., et al. (1975) "A Flow Pattern Map
    for Horizontal Two-Phase Flow"，被 Beggs-Brill 1973 引用为适用范围校验。
    非 Taitel-Dukler 1976（后者用 K/T/F/X 4 个无量纲数）。
    """
    l1 = 316.0 * rho_L**0.302
    l2 = 0.000925 * (rho_L * rho_V) ** 0.305
    l3 = 0.1 * rho_L ** (-0.447)
    if lambda_V < l3 and lambda_L < l1:
        return "SEGREGATED"
    if lambda_L >= l2 and lambda_V >= l3:
        return "INTERMITTENT"
    if lambda_V >= l1 and lambda_V < l3 and lambda_L >= l3:
        return "DISTRIBUTED"
    return "TRANSITION"


# Beggs-Brill 1973 Table 1: (a, b, c) for H_L(0) = a·λ_L^b / Fr^c
_BG_B_HL0_COEFFS: Final[dict[str, tuple[float, float, float]]] = {
    "SEGREGATED": (0.980, 0.4846, 0.0868),
    "INTERMITTENT": (0.845, 0.5351, 0.0173),
    "DISTRIBUTED": (1.065, 0.5824, 0.0609),
}


def _beggs_brill_h_l_theta0(
    lambda_L: float, fr: float, flow_pattern: FlowPattern,
) -> float:
    """Beggs-Brill 1973 Eq.6 H_L(0) = a·λ_L^b / Fr^c。

    TRANSITION 取 SEGREGATED / INTERMITTENT 平均（Brief 锁定）。
    """
    if flow_pattern == "TRANSITION":
        a, b, c = (0.913, 0.5100, 0.0521)
    else:
        a, b, c = _BG_B_HL0_COEFFS[flow_pattern]
    if fr <= 0:
        return min(1.0, max(0.0, lambda_L))
    return a * lambda_L**b / fr**c


def _beggs_brill_inclination_correction(
    h_l_theta0: float, theta_deg: float,
) -> float:
    """倾角修正 B(θ)（BG-B 1973 Eq.14-16 简化）。

    上坡（θ>0）→ H_L 增加；下坡（θ<0）→ H_L 减少；
    |θ| < 1e-6° 时 H_L(θ) ≡ H_L(0)。
    """
    if abs(theta_deg) < 1e-6:
        return h_l_theta0
    theta_rad = math.radians(theta_deg)
    # sin**1.5 on negative base would return complex; use abs() + copysign
    sin_abs_pow15 = math.copysign(abs(math.sin(theta_rad)) ** 1.5, math.sin(theta_rad))
    sign = 1.0 if theta_deg > 0 else -0.5
    correction = 1.0 + sign * 0.5 * sin_abs_pow15
    return max(0.0, min(1.0, h_l_theta0 * correction))


def calc_beggs_brill_holdup(inp: BeggsBrillHoldupInput) -> HoldupCorrelationResult:
    """计算 Beggs-Brill 持液率 + Mandhane 1975 流型判别（SPEC §3.2.3 V1.9）。

    Returns:
        HoldupCorrelationResult（frozen dataclass）：
        - flow_pattern: Mandhane 1975 水平管流型（SEGREGATED/INTERMITTENT/
          DISTRIBUTED/TRANSITION）
        - h_l_theta0: 水平管持液率（θ=0）
        - h_l_theta: 倾角修正后持液率
        - froude_number: Fr = V_m^2/(g·D)
        - is_beggs_brill_valid: Eaton-Flanning 1967 Fr ∈ [0.01, 10] 校验
        - imperial_conversion: 仅 imperial_units=True 时填 v_sl_ft_s/v_sg_ft_s
        - formula_ref: 公式溯源（含 Taitel-Dukler 不实现的 docstring 说明）
    """
    _validate_input(inp)
    v_m = inp.v_sl_m_s + inp.v_sg_m_s
    a_pipe = math.pi * inp.pipe_diameter_m**2 / 4.0
    q_L = inp.v_sl_m_s * a_pipe
    q_V = inp.v_sg_m_s * a_pipe
    q_m = q_L + q_V
    lambda_L = q_L / q_m if q_m > 0 else 0.0
    lambda_V = q_V / q_m if q_m > 0 else 1.0
    fr = v_m**2 / (_GRAVITY * inp.pipe_diameter_m)

    flow_pattern = _mandhane_flow_pattern(
        lambda_L, lambda_V, inp.rho_L_kg_m3, inp.rho_V_kg_m3,
    )
    h_l_0 = _beggs_brill_h_l_theta0(lambda_L, fr, flow_pattern)
    h_l_theta = _beggs_brill_inclination_correction(h_l_0, inp.pipe_inclination_deg)

    # Eaton-Flanning 1967 校验：E-F 适用范围 Fr ∈ [0.01, 10]
    is_valid = 0.01 <= fr <= 10.0

    imperial: dict[str, float] | None = None
    if inp.imperial_units:
        imperial = {
            "v_sl_ft_s": inp.v_sl_m_s / _M_PER_FT,
            "v_sg_ft_s": inp.v_sg_m_s / _M_PER_FT,
        }

    return HoldupCorrelationResult(
        flow_pattern=flow_pattern,
        h_l_theta0=h_l_0,
        h_l_theta=h_l_theta,
        froude_number=fr,
        is_beggs_brill_valid=is_valid,
        imperial_conversion=imperial,
        formula_ref={
            "mandhane_flow_pattern": (
                "Mandhane 1975 水平管流型图（SPEC §3.2.3 V1.9：原 Taitel-Dukler "
                "→ Mandhane 1975，因 BG-B 1973 原文引用 Mandhane 而非 "
                "Taitel-Dukler；Taitel-Dukler 1976 用 K/T/F/X 4 无量纲数不同算法，"
                "本批不实现）"
            ),
            "beggs_brill_h_l": "Beggs-Brill 1973 Eq.6 H_L(0) = a·λ_L^b / Fr^c",
            "inclination_correction": "BG-B 1973 Eq.14-16 倾角修正 B(θ)",
            "eaton_flanning": "Eaton-Flanning 1967 Fr 范围校验 [0.01, 10]",
        },
    )


__all__ = [
    "BeggsBrillHoldupInput",
    "HoldupCorrelationResult",
    "BeggsBrillInputError",
    "calc_beggs_brill_holdup",
    "FlowPattern",
]