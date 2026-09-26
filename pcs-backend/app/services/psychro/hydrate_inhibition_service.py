"""水合物抑制（SPEC §3.9.4 V1.8）。

按 SPEC §3.9.4 V1.1 计算水合物抑制：

Hammerschmidt 1934 温降公式：
  ΔT = K·X / (M·(1-X))
  X = 抑制剂在水溶液中的质量分数（0..1）
  K = 温降常数（无量纲；H-2 v1 BLOCKER 锁定 5 种文献值）
  M = 抑制剂分子量（g/mol）

K 因子（按文献，H-2 v1 修定）：
  MEOH = 2335
  EG (MEG) = 2220
  DEG = 2335
  TEG = 2500
  NACL = 1297

GPSA §20.3 抑制剂注入率：
  Q_inhib (lb/d) = Q_gas · (W_inlet - W_target) / X_inhib
  Q_inhib (gal/d) = Q_inhib (lb/d) / ρ_inhib (lb/gal)

单位约定：

  - SI 基准（imperial_units=False default，L-3 v1 BLOCKER 修定）
  - imperial_units=True → dual-unit 输出（hydrate_depression_f + injection_rate_gal_d）

冻结接口（A1-A4 + B1-B5 + C1 批次一致性）：

  - dataclass(frozen=True)：Input + Result
  - PcsError 子类（code/status 字段）
  - formula_ref dict 标注公式来源（Hammerschmidt 1934 + GPSA §20.3）

边界拒绝（F2 / F5）：

  - gas_flow_mmscfd ≤ 0 → HydrateInhibitionError
  - operating_pressure_psia ≤ 0 → HydrateInhibitionError
  - inhibitor_concentration_in_water_wt_pct ∉ (0, 100) → HydrateInhibitionError
  - 温度字段未验证（仅用于结果 docstring；公式不依赖温度）

物理范围（H-2 v1）：

  - ΔT > 0 → is_safe=True（温降为正即有效抑制）
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

# Hammerschmidt 1934 K 因子（按文献；H-2 v1 BLOCKER 锁定）
_HAMMERSCHMIDT_K: Final[dict[str, float]] = {
    "MEOH": 2335.0,
    "EG": 2220.0,
    "DEG": 2335.0,
    "TEG": 2500.0,
    "NACL": 1297.0,
}

# 抑制剂分子量（g/mol；MEOH=32.04 / EG=62.07 / DEG=106.12 / TEG=150.17 / NACL=58.44）
_INHIBITOR_MW: Final[dict[str, float]] = {
    "MEOH": 32.04,
    "EG": 62.07,
    "DEG": 106.12,
    "TEG": 150.17,
    "NACL": 58.44,
}

# 抑制剂密度（lb/gal；用于 lb/d → gal/d 换算）
# MEOH=6.63 / EG=9.26 / DEG=9.36 / TEG=9.35 / NaCl 饱和溶液≈10.5
_INHIBITOR_DENSITY_LB_PER_GAL: Final[dict[str, float]] = {
    "MEOH": 6.63,
    "EG": 9.26,
    "DEG": 9.36,
    "TEG": 9.35,
    "NACL": 10.5,
}

InhibitorType = Literal["MEOH", "EG", "DEG", "TEG", "NACL"]


class HydrateInhibitionError(PcsError):
    """水合物抑制输入错误（F2 / F5 边界拒绝）。"""

    code = "HYDRATE_INHIBITION_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class HydrateInhibitionInput:
    """水合物抑制输入。

    字段：
      gas_flow_mmscfd: 干气流量（MMscf/day）
      operating_pressure_psia: 操作压力（psia）
      operating_temperature_f: 操作温度（°F；仅用于记录）
      hydrate_inhibitor_type: 抑制剂类型（MEOH/EG/DEG/TEG/NACL）
      inhibitor_concentration_in_water_wt_pct: 抑制剂在水溶液中的质量分数（0..100 wt%）
      water_content_inlet_lb_per_mmscf: 入口水含量（lb water / MMscf dry gas）
      water_content_target_lb_per_mmscf: 目标出口水含量（lb water / MMscf dry gas）
      imperial_units: True → dual-unit 输出（hydrate_depression_f +
        injection_rate_gal_d）；False（默认，L-3 v1 BLOCKER 修定）→ SI 基准仅
    """

    gas_flow_mmscfd: float
    operating_pressure_psia: float
    operating_temperature_f: float
    hydrate_inhibitor_type: InhibitorType
    inhibitor_concentration_in_water_wt_pct: float
    water_content_inlet_lb_per_mmscf: float = 20.0
    water_content_target_lb_per_mmscf: float = 1.0
    imperial_units: bool = False  # L-3 v1 BLOCKER: SI base per Global Constraints


@dataclass(frozen=True)
class HydrateInhibitionResult:
    """水合物抑制结果。

    字段：
      hydrate_depression_f: Hammerschmidt 温降（°F；Hammerschmidt 1934 Eq）
      hydrate_depression_c: Hammerschmidt 温降（°C；= F × 5/9）
      inhibitor_injection_rate_gpd: 抑制剂注入率（gal/day；GPSA §20.3）
      inhibitor_injection_rate_lb_d: 抑制剂注入率（lb/day；GPSA §20.3）
      water_removed_lb_d: 水移除量（lb/day；= Q_gas·(W_inlet - W_target)）
      is_safe: 温降 > 0（True=安全抑制；False=无抑制效果）
      inhibitor_k_factor: 该抑制剂的 K 因子（无量纲）
      inhibitor_mw: 该抑制剂的分子量（g/mol）
      imperial_conversion: dual-unit 输出（仅 imperial_units=True）
      formula_ref: 公式引用（Hammerschmidt 1934 + GPSA §20.3）
    """

    hydrate_depression_f: float
    hydrate_depression_c: float
    inhibitor_injection_rate_gpd: float
    inhibitor_injection_rate_lb_d: float
    water_removed_lb_d: float
    is_safe: bool
    inhibitor_k_factor: float
    inhibitor_mw: float
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: HydrateInhibitionInput) -> None:
    if inp.gas_flow_mmscfd <= 0:
        raise HydrateInhibitionError(f"Q_gas={inp.gas_flow_mmscfd} 必须 > 0")
    if inp.operating_pressure_psia <= 0:
        raise HydrateInhibitionError(
            f"operating_pressure_psia={inp.operating_pressure_psia} 必须 > 0"
        )
    if not (
        0.0
        < inp.inhibitor_concentration_in_water_wt_pct
        < 100.0
    ):
        raise HydrateInhibitionError(
            f"inhibitor_concentration_in_water_wt_pct="
            f"{inp.inhibitor_concentration_in_water_wt_pct} 必须在 (0, 100) wt%"
        )
    if inp.water_content_inlet_lb_per_mmscf < 0:
        raise HydrateInhibitionError("入口水含量必须 ≥ 0")
    if (
        inp.water_content_target_lb_per_mmscf
        > inp.water_content_inlet_lb_per_mmscf
    ):
        raise HydrateInhibitionError(
            "目标水含量必须 ≤ 入口水含量"
        )


def calc_hydrate_inhibition(
    inp: HydrateInhibitionInput,
) -> HydrateInhibitionResult:
    """水合物抑制主计算入口。

    计算步骤：
      1. _validate_input 边界拒绝（F2/F5）
      2. Hammerschmidt ΔT（°C）= K·X / (M·(1-X))，其中 X = wt% / 100
      3. ΔT_F = ΔT_C × 9/5
      4. 水移除量 W_removed = Q_gas·(W_inlet - W_target)（lb/d）
      5. 注入率（lb/d）= W_removed / X_inhib（GPSA §20.3）
      6. 注入率（gal/d）= injection_lb_d / ρ_inhib（GPSA §20.3）
      7. 封装 result（imperial 双单位若启用）
    """
    _validate_input(inp)

    K = _HAMMERSCHMIDT_K[inp.hydrate_inhibitor_type]
    mw = _INHIBITOR_MW[inp.hydrate_inhibitor_type]
    rho = _INHIBITOR_DENSITY_LB_PER_GAL[inp.hydrate_inhibitor_type]

    X = inp.inhibitor_concentration_in_water_wt_pct / 100.0

    # 1. Hammerschmidt 1934 ΔT（°C）= K·X / (M·(1-X))
    delta_t_c = K * X / (mw * (1.0 - X))
    # 2. °C → °F
    delta_t_f = delta_t_c * 9.0 / 5.0

    # 3. 水移除量（lb/d）= Q_gas (MMscf/d) × (W_inlet - W_target) (lb/MMscf)
    water_removed_lb_d = inp.gas_flow_mmscfd * (
        inp.water_content_inlet_lb_per_mmscf
        - inp.water_content_target_lb_per_mmscf
    )

    # 4. 注入率（lb/d）= W_removed / X_inhib（GPSA §20.3）
    injection_lb_d = water_removed_lb_d / X
    # 5. 注入率（gal/d）= injection_lb_d / ρ_inhib
    injection_gpd = injection_lb_d / rho

    is_safe = delta_t_c > 0

    # 6. imperial dual-unit 输出（L-3 v1 BLOCKER：默认 False）
    imperial: dict[str, float] | None = None
    if inp.imperial_units:
        imperial = {
            "hydrate_depression_f": delta_t_f,
            "injection_rate_gal_d": injection_gpd,
        }

    return HydrateInhibitionResult(
        hydrate_depression_f=delta_t_f,
        hydrate_depression_c=delta_t_c,
        inhibitor_injection_rate_gpd=injection_gpd,
        inhibitor_injection_rate_lb_d=injection_lb_d,
        water_removed_lb_d=water_removed_lb_d,
        is_safe=is_safe,
        inhibitor_k_factor=K,
        inhibitor_mw=mw,
        imperial_conversion=imperial,
        formula_ref={
            "hammerschmidt": (
                "ΔT = K·X / (M·(1-X)) [Hammerschmidt 1934]"
            ),
            "k_factor": (
                f"K = {K}（H-2 v1: MEOH/DEG=2335; EG=2220; TEG=2500; NACL=1297）"
            ),
            "injection_rate": (
                "Q_inhib = Q_gas·(W_inlet - W_target)/C [GPSA §20.3]"
            ),
            "density": (
                f"ρ_inhib = {rho} lb/gal"
                f"（MEOH=6.63/EG=9.26/DEG=9.36/TEG=9.35/NACL=10.5）"
            ),
        },
    )


__all__ = [
    "HydrateInhibitionError",
    "HydrateInhibitionInput",
    "HydrateInhibitionResult",
    "InhibitorType",
    "calc_hydrate_inhibition",
]