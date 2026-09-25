"""FLARE_SYS 火炬气液分离罐 KOD 与水封液柱计算。

按 API 521 7th Ed.：
- §5.15.3 Souders-Brown 法计算 KOD 直径
- §5.15.5 Water Seal 液封高度（防总管回火进入 KOD/上游）

输入参数来自 Task 19 aggregate_flare_load（vapor mass flow）+ Task 20
header_sizing（header P/T）。不依赖 DB（纯计算）；落库由 Task 23 flare_persist
统一处理。

公式溯源：API_521_§5.15.3 + API_521_§5.15.5。
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from app.services.exceptions import PcsError

# 通用物理常数
_GRAVITY_DEFAULT = 9.81  # m/s²
_RHO_WATER_DEFAULT = 1000.0  # kg/m³（纯水 4°C）
_K_SB_DEFAULT = 0.3  # m/s（Souders-Brown 保守默认，API 521 工段 0.1–0.4）
_SAFETY_FACTOR_DEFAULT = 1.5  # API 521 推荐 1.25–2.0


# ───────────────────────────── KOD (Souders-Brown) ─────────────────────────────


@dataclass(frozen=True)
class KodInput:
    """KOD Souders-Brown 计算输入。

    字段：

    - vapor_mass_flow_kgs: 闪蒸气（蒸气）质量流量 kg/s（来自 Task 19）
    - vapor_density_kg_m3: 蒸气密度 kg/m³（工况下）
    - liquid_density_kg_m3: 液滴密度 kg/m³
    - k_sb_m_s: Souders-Brown 系数 m/s（默认 0.3 保守）
    """

    vapor_mass_flow_kgs: float  # kg/s
    vapor_density_kg_m3: float  # kg/m³（工况下）
    liquid_density_kg_m3: float  # kg/m³（液滴）
    k_sb_m_s: float = _K_SB_DEFAULT  # Souders-Brown 系数（m/s）


@dataclass(frozen=True)
class KodResult:
    """KOD Souders-Brown 计算结果。

    字段：

    - diameter_m: KOD 直径 m
    - area_m2: KOD 流通截面积 m²
    - u_perm_m_s: 允许蒸气速度 m/s（u_perm = K × sqrt((ρ_L − ρ_V) / ρ_V)）
    - u_actual_m_s: 实际蒸气速度 m/s（数学恒等于 u_perm，作为合规自检）
    - limit_ratio: u_actual / u_perm（应 == 1.0；非物理自检）
    - formula_ref: 公式溯源标记 "API_521_§5.15.3"
    """

    diameter_m: float  # m
    area_m2: float  # m²
    u_perm_m_s: float  # 允许蒸气速度（m/s）
    u_actual_m_s: float  # 实际蒸气速度（m/s）
    limit_ratio: float  # u_actual / u_perm（应 == 1.0）
    formula_ref: str  # "API_521_§5.15.3"


# ───────────────────────────── Water Seal ─────────────────────────────


@dataclass(frozen=True)
class WaterSealInput:
    """水封液柱高度输入。

    字段：

    - header_pressure_pa: 火炬总管在 water seal 连接处压力 Pa（来自 Task 20）
    - seal_pot_pressure_pa: seal pot 下游侧压力 Pa（常为大气压 101325）
    - water_density_kg_m3: 水封液密度 kg/m³（默认 1000 纯水）
    - gravity_m_s2: 重力加速度 m/s²（默认 9.81）
    - safety_factor: 设计安全系数（默认 1.5；API 521 推荐 1.25–2.0）
    - surge_pressure_pa: 浪涌工况下的额外压力 Pa（默认 0；非浪涌工况）
    """

    header_pressure_pa: float  # Pa（火炬总管在 water seal 处）
    seal_pot_pressure_pa: float  # Pa（seal pot 下游侧）
    water_density_kg_m3: float = _RHO_WATER_DEFAULT  # kg/m³
    gravity_m_s2: float = _GRAVITY_DEFAULT  # m/s²
    safety_factor: float = _SAFETY_FACTOR_DEFAULT  # 设计安全系数
    surge_pressure_pa: float = 0.0  # Pa（浪涌工况额外压力，默认 0）


@dataclass(frozen=True)
class WaterSealResult:
    """水封液柱高度结果。

    字段：

    - h_seal_m: 最小液封高度 m（h_seal = ΔP / (ρ_w × g)）
    - h_design_m: 设计液封高度 m（h_design = h_seal × safety_factor）
    - delta_pressure_pa: 有效压差 Pa（= P_header + surge − P_pot）
    - formula_ref: 公式溯源标记 "API_521_§5.15.5"
    """

    h_seal_m: float  # 最小液封高度（m）
    h_design_m: float  # 设计液封高度（m，含 safety_factor）
    delta_pressure_pa: float  # 有效压差（Pa）
    formula_ref: str  # "API_521_§5.15.5"


# ───────────────────────────── 综合响应 ─────────────────────────────


@dataclass(frozen=True)
class KodSizingResult:
    """KOD + Water Seal 综合计算结果。

    字段：

    - kod: KOD 子结果（KodResult）
    - water_seal: Water Seal 子结果（WaterSealResult）
    - formula_ref: 综合公式溯源 "API_521_§5.15.3+§5.15.5"
    """

    kod: KodResult
    water_seal: WaterSealResult
    formula_ref: str  # "API_521_§5.15.3+§5.15.5"


# ───────────────────────────── 异常类 ─────────────────────────────


class KodSizingInputError(PcsError):
    """kod_sizing 输入不合法（422）。

    触发场景：vapor_mass_flow_kgs / ρ_V / ρ_L <= 0、ρ_L <= ρ_V（无气液分离）、
    k_sb_m_s 超出工程范围 (0, 2.0] 等。
    """

    code = "FLARE_KOD_INPUT_ERROR"
    status = 422


class WaterSealInputError(PcsError):
    """water_seal 输入不合法（422）。

    触发场景：header_pressure_pa <= seal_pot_pressure_pa（无压差 → 液封失效）、
    ρ_water / gravity <= 0、safety_factor < 1.0（不安全）、surge_pressure < 0。
    """

    code = "FLARE_WATER_SEAL_INPUT_ERROR"
    status = 422


# ───────────────────────────── 计算函数 ─────────────────────────────


def calc_kod(inp: KodInput) -> KodResult:
    """Souders-Brown 法计算 KOD 直径。

    实现步骤（API 521 7th Ed. §5.15.3 / GPSA Engineering Data Book）：
    1. 允许蒸气速度 u_perm = K_sb × sqrt((ρ_L − ρ_V) / ρ_V)
    2. KOD 流通面积 A = W_vapor / (ρ_V × u_perm)
    3. KOD 直径 D = sqrt(4 × A / π)
    4. 实际蒸气速度 u_actual = W_vapor / (ρ_V × A)（数学恒等 u_perm）
    5. Souders-Brown 极限比 limit_ratio = u_actual / u_perm（== 1.0 合规自检）

    Args:
        inp: KodInput（已冻结 dataclass）。

    Returns:
        KodResult（含 diameter_m / area_m2 / u_perm_m_s / u_actual_m_s / limit_ratio）。

    Raises:
        KodSizingInputError: 输入字段越界或非正（422）。
    """
    # 输入校验
    if inp.vapor_mass_flow_kgs <= 0:
        raise KodSizingInputError(
            f"vapor_mass_flow_kgs={inp.vapor_mass_flow_kgs} 必须 > 0"
        )
    if inp.vapor_density_kg_m3 <= 0:
        raise KodSizingInputError(
            f"vapor_density_kg_m3={inp.vapor_density_kg_m3} 必须 > 0"
        )
    if inp.liquid_density_kg_m3 <= inp.vapor_density_kg_m3:
        raise KodSizingInputError(
            f"liquid_density_kg_m3={inp.liquid_density_kg_m3} 必须 > "
            f"vapor_density={inp.vapor_density_kg_m3}（否则无气液分离）"
        )
    if inp.k_sb_m_s <= 0 or inp.k_sb_m_s > 2.0:
        raise KodSizingInputError(
            f"k_sb_m_s={inp.k_sb_m_s} 超出工程范围 (0, 2.0]"
        )

    W = inp.vapor_mass_flow_kgs
    rho_V = inp.vapor_density_kg_m3
    rho_L = inp.liquid_density_kg_m3
    K = inp.k_sb_m_s

    # 允许蒸气速度（工程经验）
    u_perm = K * ((rho_L - rho_V) / rho_V) ** 0.5  # m/s
    # KOD 流通面积
    area = W / (rho_V * u_perm)  # m²
    # 直径
    diameter = (4.0 * area / math.pi) ** 0.5  # m
    # 实际蒸气速度（数学恒等 u_perm）
    u_actual = W / (rho_V * area)  # = u_perm
    # 极限比（数学恒等 1.0；作为合规自检字段）
    limit_ratio = u_actual / u_perm  # = 1.0

    return KodResult(
        diameter_m=diameter,
        area_m2=area,
        u_perm_m_s=u_perm,
        u_actual_m_s=u_actual,
        limit_ratio=limit_ratio,
        formula_ref="API_521_§5.15.3",
    )


def calc_water_seal(inp: WaterSealInput) -> WaterSealResult:
    """Water Seal 液柱高度计算（API 521 7th Ed. §5.15.5）。

    公式：
        ΔP = (P_header + P_surge) − P_seal_pot
        h_seal = ΔP / (ρ_water × g)
        h_design = h_seal × safety_factor

    Args:
        inp: WaterSealInput（已冻结 dataclass）。

    Returns:
        WaterSealResult（含 h_seal_m / h_design_m / delta_pressure_pa）。

    Raises:
        WaterSealInputError: 输入字段越界或非正（422）。
    """
    if inp.header_pressure_pa <= inp.seal_pot_pressure_pa:
        raise WaterSealInputError(
            f"header_pressure_pa={inp.header_pressure_pa} 必须 > "
            f"seal_pot_pressure_pa={inp.seal_pot_pressure_pa}"
        )
    if inp.water_density_kg_m3 <= 0:
        raise WaterSealInputError(
            f"water_density_kg_m3={inp.water_density_kg_m3} 必须 > 0"
        )
    if inp.gravity_m_s2 <= 0:
        raise WaterSealInputError(
            f"gravity_m_s2={inp.gravity_m_s2} 必须 > 0"
        )
    if inp.safety_factor < 1.0:
        raise WaterSealInputError(
            f"safety_factor={inp.safety_factor} 必须 ≥ 1.0（API 521 推荐 1.25–2.0）"
        )
    if inp.surge_pressure_pa < 0:
        raise WaterSealInputError(
            f"surge_pressure_pa={inp.surge_pressure_pa} 必须 ≥ 0"
        )

    delta_p = (inp.header_pressure_pa + inp.surge_pressure_pa) - inp.seal_pot_pressure_pa
    h_seal = delta_p / (inp.water_density_kg_m3 * inp.gravity_m_s2)  # m
    h_design = h_seal * inp.safety_factor  # m

    return WaterSealResult(
        h_seal_m=h_seal,
        h_design_m=h_design,
        delta_pressure_pa=delta_p,
        formula_ref="API_521_§5.15.5",
    )


def calc_kod_sizing(
    kod: KodInput,
    water: WaterSealInput,
) -> KodSizingResult:
    """综合 KOD + Water Seal 计算。

    调用 ``calc_kod`` 与 ``calc_water_seal`` 后组合为 ``KodSizingResult``。

    Args:
        kod: KOD 子输入（KodInput）。
        water: Water Seal 子输入（WaterSealInput）。

    Returns:
        KodSizingResult（含 kod / water_seal 子结果与综合 formula_ref）。

    Raises:
        KodSizingInputError / WaterSealInputError: 任一子计算输入不合法（422）。
    """
    kod_r = calc_kod(kod)
    water_r = calc_water_seal(water)
    return KodSizingResult(
        kod=kod_r,
        water_seal=water_r,
        formula_ref="API_521_§5.15.3+§5.15.5",
    )


__all__ = [
    "KodInput",
    "KodResult",
    "WaterSealInput",
    "WaterSealResult",
    "KodSizingResult",
    "KodSizingInputError",
    "WaterSealInputError",
    "calc_kod",
    "calc_water_seal",
    "calc_kod_sizing",
]
