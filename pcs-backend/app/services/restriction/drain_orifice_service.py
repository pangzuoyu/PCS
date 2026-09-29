"""排污孔板（drain orifice）计算（SPEC §3.6.2 + §3.7.2 V1.1）。

公式（GB/T 308 排水孔板 + GB/T 2624 流量孔板）：
  Ftp 修正（GB/T 308 Eq.2.2 排水孔板经验式）：Ftp = 1 - 0.0245·β^4.4
  阻塞判断：P₂/P₁ ≤ r_c（γ=1.4 时 r_c ≈ 0.528）
  阻塞流质量流量：m_max = A × Cd × Y_cr^0.5 × Ftp × ρ × v_max
    （OPEN-P6-6A-4 fix: Cd/Y_cr^0.5 加入，默认 1.0 保持向后兼容；Ruling 12）

OPEN-P6-6A-7 增补 sizing（inverse problem）：
  calc_drain_orifice_size 由 W（泄放量）+ 工况反推 orifice diameter d。
  算法：Newton 简化版 d_new = d × sqrt(W/m_max)；β 越界退 bisection。
  仅适用于阻塞流（SPEC §3.7.2 sizing 仅在临界流场景成立）。

Q-11：Ftp 修正系数 GB/T 308 经验式（无 ISO 5167 标准支撑）

P6-6B T13 feature flag（OPEN-P6-6A-4 关闭）：
  ``_USE_XLS_CD_Y_CR: bool = False``（模块级常量；默认 False）— 当设 True
  时，``_resolve_cd_y_cr(fluid)`` 从 ``drain_orifice_Cd_Y_cr`` CONFIG 表加载
  XLS convention（NATURAL_GAS Cd=0.83932 / Y_cr=0.687 等）；默认 False
  → 返回 (1.0, 1.0) 保持向后兼容现有 drain_orifice API 行为。
  ⚠️ **需 ETL 重新对账后再切 True**（影响所有现有 drain_orifice 计算结果）。
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services._compound_config_cache import get_drain_orifice_Cd_Y_cr_table
from app.services.exceptions import PcsError

_GAMMA_DEFAULT: Final[float] = 1.4
_M2_TO_IN2: Final[float] = 0.0254**2  # 1 in² = (0.0254 m)²
_KPA_PER_PSIA: Final[float] = 0.1450377
_R_GAS: Final[float] = 8.314462618  # J/(mol·K)，理想气体常数
_MOL_PER_KMOL: Final[float] = 1000.0  # 1 kmol = 1000 mol（MW 单位换算用）

# P6-6B T13：XLS convention feature flag（OPEN-P6-6A-4 关闭）。
# 默认 False → 现有 drain_orifice API 行为（Cd=1.0 / Y_cr=1.0，向后兼容）；
# 设 True → ``_resolve_cd_y_cr`` 从 ``drain_orifice_Cd_Y_cr`` CONFIG 表加载
# XLS PR-023 + Miller 1990 取值。⚠️ 切 True 前必须先 ETL 重新对账
# （影响 1.74× capacity 修正）。
_USE_XLS_CD_Y_CR: Final[bool] = False


class DrainOrificeInputError(PcsError):
    """DRAIN_ORIFICE 输入校验失败（422）。"""

    code = "DRAIN_ORIFICE_INPUT_ERROR"
    status = 422


class DrainOrificeSizingNotConvergedError(PcsError):
    """DRAIN_ORIFICE sizing 迭代未收敛（422）。

    OPEN-P6-6A-7：calc_drain_orifice_size 在 max_iter 步内未达到
    tol × W 残差。由 ``app.services.restriction.drain_orifice_service``
    ``calc_drain_orifice_size`` raise。
    """

    code = "DRAIN_ORIFICE_SIZING_NOT_CONVERGED"
    status = 422


@dataclass(frozen=True)
class DrainOrificeInput:
    """排污孔板输入（frozen dataclass）。

    物理量 SI 单位：长度 m、压力 kPa、密度 kg/m³、流量 kg/s。

    OPEN-P6-6A-4（Ruling 12）增补可选字段：
      - discharge_coefficient: Cd（流量系数），默认 1.0（向后兼容 XLS PR-023 Cd=0.83932）
      - expansion_factor: Y_cr^0.5（膨胀因子），默认 1.0（向后兼容 XLS PR-023 Y_cr^0.5=0.687）
    """

    orifice_diameter_m: float
    beta_ratio: float
    inlet_pressure_kpa: float
    outlet_pressure_kpa: float
    fluid_density_kg_m3: float
    mass_flow_kg_s: float
    drain_type: Literal["CONTINUOUS", "INTERMITTENT"]
    imperial_units: bool = False
    discharge_coefficient: float = 1.0
    expansion_factor: float = 1.0


@dataclass(frozen=True)
class DrainOrificeResult:
    """排污孔板结果（frozen dataclass）。"""

    orifice_area_m2: float
    ftp_factor: float
    critical_pressure_ratio: float
    actual_pressure_ratio: float
    is_choked: bool
    mass_flow_capacity_kg_s: float
    is_capacity_ok: bool
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _validate_input(inp: DrainOrificeInput) -> None:
    """F2 + F5：β 直径比 + 极值校验。"""
    if inp.orifice_diameter_m <= 0:
        raise DrainOrificeInputError(f"d={inp.orifice_diameter_m} 必须 > 0")
    # F2 boundary：β 严格 0 < β < 1
    if not (0.0 < inp.beta_ratio < 1.0):
        raise DrainOrificeInputError(f"β={inp.beta_ratio} 越界 (0, 1)")
    if inp.inlet_pressure_kpa <= 0 or inp.outlet_pressure_kpa < 0:
        raise DrainOrificeInputError("压力必须 P₁>0, P₂≥0")
    if inp.fluid_density_kg_m3 <= 0:
        raise DrainOrificeInputError("密度必须 > 0")
    if inp.mass_flow_kg_s < 0:
        raise DrainOrificeInputError("流量不能为负")
    # Ruling 12（OPEN-P6-6A-4）：Cd 与 Y_cr^0.5 ∈ (0, 1]（标准 orifice 范围）
    if not (0.0 < inp.discharge_coefficient <= 1.0):
        raise DrainOrificeInputError(
            f"Cd={inp.discharge_coefficient} 越界 (0, 1]（Ruling 12）"
        )
    if not (0.0 < inp.expansion_factor <= 1.0):
        raise DrainOrificeInputError(
            f"Y_cr^0.5={inp.expansion_factor} 越界 (0, 1]（Ruling 12）"
        )


def _resolve_cd_y_cr(fluid: str) -> tuple[float, float]:
    """从 ``drain_orifice_Cd_Y_cr`` CONFIG 表加载 (Cd, Y_cr)。

    默认 ``_USE_XLS_CD_Y_CR=False`` → 返回 ``(1.0, 1.0)`` 保持向后兼容；
    设 True → 从 CONFIG 表 lookup。

    P6-6B T13 引入；OPEN-P6-6A-4 关闭（feature flag 默认 False）。

    Args:
        fluid: 介质标识（NATURAL_GAS / AIR / STEAM / WATER / N2 / CO2）

    Returns:
        (Cd, Y_cr) 元组；DB 不可达 / fluid 不在表内 / flag 关闭时返回
        ``(1.0, 1.0)``。
    """
    if not _USE_XLS_CD_Y_CR:
        return 1.0, 1.0
    table = get_drain_orifice_Cd_Y_cr_table()
    if table is None or fluid not in table:
        return 1.0, 1.0
    return table[fluid]


def calc_drain_orifice(
    inp: DrainOrificeInput,
    fluid: str | None = None,
    _resolved_cd_y_cr: tuple[float, float] | None = None,
) -> DrainOrificeResult:
    """排污孔板（drain orifice）尺寸校核（SPEC §3.6.2 + §3.7.2 V1.1）。

    计算项：
      - orifice_area_m2 = π·d²/4
      - Ftp = 1 - 0.0245·β^4.4（GB/T 308 排水孔板 Eq.2.2 经验式）
      - critical_pressure_ratio r_c = (2/(γ+1))^(γ/(γ-1))
      - is_choked：P₂/P₁ ≤ r_c
      - mass_flow_capacity：阻塞流时 v_max = √(2ΔP/ρ) →
        m_max = A × Cd × Y_cr^0.5 × Ftp × ρ × v_max（OPEN-P6-6A-4 Ruling 12）

    Args:
        inp: DrainOrificeInput（frozen）
        fluid: 介质标识（NATURAL_GAS / AIR / STEAM / WATER / N2 / CO2）；
            P6-9-PICKUP-2 T6 — flag-driven 覆盖入口。当 ``_USE_XLS_CD_Y_CR=True``
            且 ``fluid`` 非 None → 自动调 ``_resolve_cd_y_cr(fluid)`` 从
            ``drain_orifice_Cd_Y_cr`` CONFIG 表 lookup Cd / Y_cr^0.5。
            ``None`` → 走原路径（向后兼容）。
        _resolved_cd_y_cr: P6-6B T13 内部 override（legacy 集成测试入口）。
            ``None`` → 走原路径；提供 ``(Cd, Y_cr)`` 元组 → 覆盖输入的
            Cd / Y_cr^0.5。优先级高于 ``fluid``（显式 override）。

    Returns:
        DrainOrificeResult（frozen）

    Raises:
        DrainOrificeInputError: 输入校验失败（F2 β 越界、F5 非正极值、Ruling 12 Cd/Y_cr 越界）
    """
    _validate_input(inp)

    # P6-9-PICKUP-2 T6：feature flag 接入。优先级：
    #   1. ``_resolved_cd_y_cr`` 显式 override（legacy 集成测试入口，最高）
    #   2. ``_USE_XLS_CD_Y_CR=True`` + ``fluid`` 非 None → ``_resolve_cd_y_cr`` 自动 lookup
    #   3. back-compat：``inp.discharge_coefficient`` / ``inp.expansion_factor``
    if _resolved_cd_y_cr is not None:
        cd_used, y_cr_used = _resolved_cd_y_cr
        y_cr_sqrt_used = math.sqrt(y_cr_used)
    elif _USE_XLS_CD_Y_CR and fluid is not None:
        cd_used, y_cr_used = _resolve_cd_y_cr(fluid)
        y_cr_sqrt_used = math.sqrt(y_cr_used)
    else:
        cd_used = inp.discharge_coefficient
        y_cr_sqrt_used = inp.expansion_factor

    a_orifice = math.pi * inp.orifice_diameter_m**2 / 4.0
    # GB/T 308 Eq.2.2 Ftp = 1 - 0.0245·β^4.4（标 SYNTHETIC_TEST_DATA）
    ftp = 1.0 - 0.0245 * inp.beta_ratio**4.4
    r_c = (2.0 / (_GAMMA_DEFAULT + 1.0)) ** (_GAMMA_DEFAULT / (_GAMMA_DEFAULT - 1.0))
    p_ratio = inp.outlet_pressure_kpa / inp.inlet_pressure_kpa
    is_choked = p_ratio <= r_c
    if is_choked:
        delta_p_pa = (inp.inlet_pressure_kpa - inp.outlet_pressure_kpa) * 1000.0
        v_max = math.sqrt(2.0 * delta_p_pa / inp.fluid_density_kg_m3)
        # OPEN-P6-6A-4 Ruling 12：m_max 乘以 Cd × Y_cr^0.5（默认 1.0 保持向后兼容）
        mass_max = (
            a_orifice
            * cd_used
            * y_cr_sqrt_used
            * ftp
            * inp.fluid_density_kg_m3
            * v_max
        )
    else:
        mass_max = float("inf")
    is_ok = inp.mass_flow_kg_s <= mass_max if is_choked else True

    imperial = None
    if inp.imperial_units:
        imperial = {
            "orifice_area_in2": a_orifice / _M2_TO_IN2,
            "inlet_pressure_psia": inp.inlet_pressure_kpa * _KPA_PER_PSIA,
        }

    return DrainOrificeResult(
        orifice_area_m2=a_orifice,
        ftp_factor=ftp,
        critical_pressure_ratio=r_c,
        actual_pressure_ratio=p_ratio,
        is_choked=is_choked,
        mass_flow_capacity_kg_s=mass_max,
        is_capacity_ok=is_ok,
        imperial_conversion=imperial,
        formula_ref={
            "ftp_correction": ("Ftp = 1 - 0.0245·β^4.4 [GB/T 308 Eq.2.2; SYNTHETIC_TEST_DATA]"),
            "critical_pressure_ratio": ("r_c = (2/(γ+1))^(γ/(γ-1))"),
            "drain_type": (f"{inp.drain_type}（CONTINUOUS=连续排污/INTERMITTENT=间歇排污）"),
            "discharge_coefficient": (
                f"Cd={inp.discharge_coefficient}（Ruling 12；默认 1.0；XLS PR-023 Cd=0.83932）"
            ),
            "expansion_factor": (
                f"Y_cr^0.5={inp.expansion_factor}（Ruling 12；默认 1.0；XLS PR-023 Y_cr^0.5=0.687）"
            ),
            "mass_flow_capacity": (
                "m_max = A × Cd × Y_cr^0.5 × Ftp × ρ × v_max（Ruling 12；阻塞流分支）"
            ),
        },
    )


__all__ = [
    "DrainOrificeInput",
    "DrainOrificeResult",
    "DrainOrificeInputError",
    "calc_drain_orifice",
    # OPEN-P6-6A-7 sizing (inverse problem)
    "DrainOrificeSizeInput",
    "DrainOrificeSizeResult",
    "DrainOrificeSizingNotConvergedError",
    "calc_drain_orifice_size",
]


# ============================================================================
# OPEN-P6-6A-7：sizing（inverse problem）— 由 W + 工况反推 orifice diameter d
# ============================================================================


@dataclass(frozen=True)
class DrainOrificeSizeInput:
    """排污孔板 sizing 输入（inverse problem）。

    物理量 SI 单位：长度 m、压力 kPa、温度 K、流量 kg/s。

    OPEN-P6-6A-7：求解 d（orifice_diameter_m）。
    """

    inlet_pressure_kpa: float  # P1
    outlet_pressure_kpa: float  # P2
    temperature_k: float  # T
    relief_flow_kg_s: float  # W（泄放量）
    compressibility_z: float  # z
    molecular_weight_kg_kmol: float  # MW
    pipe_diameter_m: float  # D（上游管径）
    specific_heat_ratio: float  # k = Cp/Cv
    specific_gravity: float  # g
    discharge_coefficient: float = 0.83932  # Cd（默认 XLS PR-023；可调）
    initial_d_m: float = 0.015  # d 迭代初值（默认 15 mm）
    tol: float = 1e-6  # 收敛判据
    max_iter: int = 50  # Newton/bisection 最大迭代
    imperial_units: bool = False


@dataclass(frozen=True)
class DrainOrificeSizeResult:
    """排污孔板 sizing 结果。

    OPEN-P6-6A-7：求解得到的 orifice diameter + 迭代元数据 + 流动状态。
    """

    orifice_diameter_m: float
    orifice_area_m2: float
    beta_ratio: float
    ftp_factor: float
    y_cr_sqrt: float  # Y_cr^0.5（Ruling 12 一致）
    critical_pressure_ratio: float
    actual_pressure_ratio: float
    is_choked: bool
    iterations: int
    converged: bool
    residual_kg_s: float  # |m_max - W|
    formula_ref: dict[str, str]


def _y_cr_sqrt(k: float, p_ratio: float, beta: float) -> float:
    """Y_cr^0.5 膨胀因子（OPEN-P6-6A-7 沿用 Ruling 12 简化式）。

    经典 ISO 5167 经验式：
      Y_cr² = (k/(k-1)) × r^(2/k) × (1 - r^((k-1)/k)) / (1 - r)
      其中 r = P₂/P₁
    log 域计算避免 r → 1 时 underflow；r ≤ 0 保守返回 1.0。
    注：标准式 Y_cr 与 β 无关；签名中保留 beta 以与 forward 接口对称，
    未来加入 Reynolds/β 修正时可扩展（Ruling 7 family mismatch 0.2% 容差内）。
    """
    del beta  # 当前公式无 β 依赖，签名保留以备扩展
    if p_ratio <= 0:
        return 1.0
    k_factor = k / (k - 1.0)
    r = p_ratio
    if r >= 1.0:
        # 非物理（sizing 已拦截非阻塞流，此处防御）
        return 1.0
    ln_term = math.log(1.0 - r ** (1.0 - 1.0 / k)) - math.log(1.0 - r)
    y_cr_sq = k_factor * r ** (2.0 / k) * math.exp(ln_term)
    return math.sqrt(max(y_cr_sq, 0.0))


def _ftp_factor(beta: float, k: float, family: str = "GBT308") -> float:
    """Ftp 经验式（Ruling 7 family mismatch 0.2% 容差）。

    默认 GBT308：DRAIN_ORIFICE 经验式 Ftp = 1 - 0.0245·β^4.4（GB/T 308 Eq.2.2）。
    备 ISO5167：通用 orifice Ftp = 1 + (k/2)·(2/(k+1))^((k+1)/(k-1))·β^4（XLS PR-023 E39）。
    """
    if family == "GBT308":
        return 1.0 - 0.0245 * beta**4.4
    if family == "ISO5167":
        term = (2.0 / (k + 1.0)) ** ((k + 1.0) / (k - 1.0))
        return 1.0 + (k / 2.0) * term * beta**4
    raise ValueError(f"Unknown Ftp family: {family}")


def calc_drain_orifice_size(
    inp: DrainOrificeSizeInput,
    fluid: str | None = None,
    _resolved_cd_y_cr: tuple[float, float] | None = None,
) -> DrainOrificeSizeResult:
    """排污孔板 sizing（SPEC §3.7.2 inverse problem；OPEN-P6-6A-7）。

    算法（WS-CA-PR-023 复刻）：
      1. 流体密度（理想气体）ρ = MW × P / (z × R × T)
      2. 临界压力比 r_c = (2/(k+1))^(k/(k-1))
      3. 阻塞判断 P2/P1 ≤ r_c
      4. 阻塞流分支：m_max = A × Cd × Y_cr^0.5 × Ftp × ρ × v_max
         （v_max = √(2 ΔP / ρ)；ΔP = (P1 - P2) × 1000 Pa）
      5. d 迭代：估计 d → β = d/D → Ftp(β, k) → Y_cr(P2/P1, k, β) → m_max(d)
         → 残差 r = m_max - W；调 d 使 r → 0

    Args:
        inp: DrainOrificeSizeInput（frozen）
        fluid: 介质标识（NATURAL_GAS / AIR / STEAM / WATER / N2 / CO2）；
            P6-9-PICKUP-2 T6 — flag-driven 覆盖入口。当 ``_USE_XLS_CD_Y_CR=True``
            且 ``fluid`` 非 None → 自动调 ``_resolve_cd_y_cr(fluid)`` 覆盖 Cd。
            注：sizing 内部 Y_cr^0.5 由 ``_y_cr_sqrt`` 在 r_c 处直接计算
            （与 XLS Y_cr 同义），仅 override Cd。
            ``None`` → 走原路径（向后兼容）。
        _resolved_cd_y_cr: P6-6B T13 内部 override（legacy 集成测试入口）。
            ``None`` → 用 ``inp.discharge_coefficient``（向后兼容）；
            提供 ``(Cd, Y_cr)`` 元组 → 仅 override Cd（与 ``fluid`` 同义但优先级高）。

    Returns:
        DrainOrificeSizeResult（frozen）

    Raises:
        DrainOrificeInputError: 输入校验失败 / 非阻塞流（sizing 仅适用临界流）
        DrainOrificeSizingNotConvergedError: max_iter 步内未达到 tol×W 残差
    """
    # 1. 校验
    if inp.relief_flow_kg_s <= 0:
        raise DrainOrificeInputError("relief_flow_kg_s 必须 > 0")
    if not (0.0 < inp.compressibility_z <= 1.5):
        raise DrainOrificeInputError(f"z={inp.compressibility_z} 越界 (0, 1.5]")
    if inp.specific_heat_ratio <= 1.0:
        raise DrainOrificeInputError(f"k={inp.specific_heat_ratio} 必须 > 1")
    if inp.pipe_diameter_m <= 0:
        raise DrainOrificeInputError("D 必须 > 0")
    if not (0.0 < inp.discharge_coefficient <= 1.0):
        raise DrainOrificeInputError(f"Cd={inp.discharge_coefficient} 越界 (0, 1]")
    if inp.inlet_pressure_kpa <= 0 or inp.outlet_pressure_kpa < 0:
        raise DrainOrificeInputError("压力必须 P₁>0, P₂≥0")
    if inp.outlet_pressure_kpa >= inp.inlet_pressure_kpa:
        raise DrainOrificeInputError("P₂ 必须 < P₁（保证 ΔP>0）")
    if inp.temperature_k <= 0:
        raise DrainOrificeInputError("T 必须 > 0")
    if inp.molecular_weight_kg_kmol <= 0:
        raise DrainOrificeInputError("MW 必须 > 0")
    if inp.initial_d_m <= 0:
        raise DrainOrificeInputError("initial_d_m 必须 > 0")
    if inp.max_iter <= 0:
        raise DrainOrificeInputError("max_iter 必须 > 0")

    # P6-9-PICKUP-2 T6：feature flag 接入。优先级：
    #   1. ``_resolved_cd_y_cr`` 显式 override（legacy，最高）
    #   2. ``_USE_XLS_CD_Y_CR=True`` + ``fluid`` 非 None → ``_resolve_cd_y_cr`` 自动 lookup
    #   3. back-compat：``inp.discharge_coefficient``
    # 注：Y_cr^0.5 由 ``_y_cr_sqrt`` 在 r_c 处直接计算（与 XLS Y_cr 同义），
    # 仅 override Cd。
    cd_used = inp.discharge_coefficient
    if _resolved_cd_y_cr is not None:
        cd_used, _ = _resolved_cd_y_cr
    elif _USE_XLS_CD_Y_CR and fluid is not None:
        cd_used, _ = _resolve_cd_y_cr(fluid)

    # 2. 流体密度（理想气体）ρ = MW × P / (z × R × 1000 × T)
    #    P: kPa → Pa（×1000）；MW 单位 kg/kmol → kg/mol（÷1000）
    rho = (
        inp.molecular_weight_kg_kmol
        * inp.inlet_pressure_kpa
        * 1000.0
        / (inp.compressibility_z * _R_GAS * _MOL_PER_KMOL * inp.temperature_k)
    )  # kg/m³

    # 3. 临界压力比 + 阻塞判断
    r_c = (2.0 / (inp.specific_heat_ratio + 1.0)) ** (
        inp.specific_heat_ratio / (inp.specific_heat_ratio - 1.0)
    )
    p_ratio = inp.outlet_pressure_kpa / inp.inlet_pressure_kpa
    is_choked = p_ratio <= r_c
    if not is_choked:
        # 非阻塞流：sizing 仅适用于临界流场景（SPEC §3.7.2）
        raise DrainOrificeInputError(
            f"非阻塞流（P2/P1={p_ratio:.4f} > r_c={r_c:.4f}）；sizing 仅适用于临界流"
        )

    # 4. v_max
    delta_p_pa = (inp.inlet_pressure_kpa - inp.outlet_pressure_kpa) * 1000.0
    v_max = math.sqrt(2.0 * delta_p_pa / rho)

    # 5. d 迭代（Newton 简化版 + β 越界 bisection fallback）
    d = inp.initial_d_m
    converged = False
    iterations = 0
    residual = 0.0
    m_max = 0.0
    beta = 0.0
    ftp = 0.0
    y_cr_sq = 0.0

    for i in range(1, inp.max_iter + 1):
        iterations = i
        beta = d / inp.pipe_diameter_m
        if not (0.0 < beta < 1.0):
            # β 越界 → 退回 bisection 重新初始化
            d = inp.pipe_diameter_m * 0.5
            continue
        ftp = _ftp_factor(beta, inp.specific_heat_ratio, "GBT308")
        # OPEN-P6-6A-7 Ruling 13 fix: Y_cr must use CRITICAL pressure ratio r_c,
        # not actual p_ratio. By definition (ISO 5167) Y_cr is evaluated at r_c.
        # At p_ratio=0.127 (choked) this would give Y_cr=0.2477 (artificially low);
        # at r_c=0.568 (k=1.18) it gives Y_cr=0.687 — matches XLS PR-023.
        y_cr_sq = _y_cr_sqrt(inp.specific_heat_ratio, r_c, beta)
        a_orifice = math.pi * d**2 / 4.0
        m_max = (
            a_orifice
            * cd_used
            * y_cr_sq
            * ftp
            * rho
            * v_max
        )
        residual = m_max - inp.relief_flow_kg_s

        if abs(residual) < inp.tol * inp.relief_flow_kg_s:
            converged = True
            break

        # Newton 简化：dm/dd = 2·(m_max)/d（忽略 Cd/Y_cr/Ftp 对 d 的导数）
        # → d_new = d × sqrt(W / m_max)
        d_new = (
            d * math.sqrt(inp.relief_flow_kg_s / m_max) if m_max > 0 else d * 0.5
        )
        # 边界保护（防 d_new ≥ D 退 β ≥ 1）
        if not (0.0 < d_new < inp.pipe_diameter_m):
            d_new = (d + inp.pipe_diameter_m) / 2.0  # bisection fallback
        d = d_new

    if not converged:
        raise DrainOrificeSizingNotConvergedError(
            f"d 迭代 {inp.max_iter} 次未收敛；residual={residual:.4g} kg/s"
        )

    # 6. 返回
    orifice_area = math.pi * d**2 / 4.0
    return DrainOrificeSizeResult(
        orifice_diameter_m=d,
        orifice_area_m2=orifice_area,
        beta_ratio=beta,
        ftp_factor=ftp,
        y_cr_sqrt=y_cr_sq,
        critical_pressure_ratio=r_c,
        actual_pressure_ratio=p_ratio,
        is_choked=is_choked,
        iterations=iterations,
        converged=converged,
        residual_kg_s=residual,
        formula_ref={
            "fluid_density": "ρ = MW × P / (z × R × T)（理想气体）",
            "y_cr": "Y_cr = sqrt((k/(k-1)) × r^(2/k) × (1-r^((k-1)/k))/(1-r))（ISO 5167 经验式）",
            "ftp": "Ftp = 1 - 0.0245·β^4.4 [GB/T 308 Eq.2.2; SYNTHETIC_TEST_DATA]",
            "critical_pressure_ratio": "r_c = (2/(k+1))^(k/(k-1))",
            "mass_flow_capacity": (
                "m_max = A × Cd × Y_cr^0.5 × Ftp × ρ × v_max"
                "（Ruling 12；OPEN-P6-6A-7 sizing）"
            ),
            "iteration": "d_new = d × sqrt(W/m_max)（Newton 简化；β 越界退 bisection）",
            "algorithm_source": "WS-CA-PR-023（Ruling 7 family mismatch 0.2% 容差内）",
        },
    )
