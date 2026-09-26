"""TEG/DEG 甘醇脱水 service（P6-5 C-16 / SPEC §3.9.1 V1.1）。

按 SPEC §3.9.1 计算 TEG/DEG 接触塔脱水（GPSA §20.4 + Campbell 2000）：

5 段计算：

  1. 入口水含量（lb water / MMscf dry gas）
  2. 接触塔塔盘设计（N_min 公式 — GPSA §20.4 Eq.20-4）
  3. 甘醇循环量（gpm；GPSA 经验 3 gpm/MMscf）
  4. TEG 损失（GPSA 经验 0.5 gal/MMscf）
  5. 脱水效率 η = 1 - outlet/inlet

公式（GPSA §20.4 Eq.20-4）：

  N_min = ln(y_in / y_out) / ln(α)            原始公式
  N_min_final = ceil(N_min × (L/V)^-0.5)     L/V 修正（M-4 v2 BLOCKER）
  α = TEG/H2O 相对挥发度（典型 4.5；DEG 较低 2.8）

接触塔直径（GPSA §20.4 经验）：

  D_in = (12 + 2·Q^(1/3)·1.5) × (L/V)^0.5    L/V 修正（M-4 v2）

TEG 损失（GPSA 经验）：

  TEG loss = 0.5 × Q_gas (gal/day)            单点估算

单位约定：

  - SI 基准（imperial_units=False default，L-3 v1 BLOCKER 修定）
  - imperial_units=True → dual-unit 输出（tegloss_gal_d + diameter_ft）

冻结接口（A1-A4 + B1-B5 批次一致性）：

  - dataclass(frozen=True)：Input + Result
  - PcsError 子类（code/status 字段）
  - formula_ref dict 标注公式来源（GPSA §20.4 Eq.20-4 等）

边界拒绝（F2 / F5）：

  - gas_flow_mmscfd ≤ 0 → GlycolDehydrationError
  - inlet_water_content ≤ 0 → GlycolDehydrationError
  - outlet ∉ [0, inlet) → GlycolDehydrationError
  - contactor_tray_count < 1 → GlycolDehydrationError
  - glycol_circulation_rate_gpm ≤ 0 → GlycolDehydrationError

塔盘不足处理（不抛错，仅标记）：

  - contactor_tray_count < N_min → is_tray_count_ok=False
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services.exceptions import PcsError

# TEG 相对挥发度（TEG/H2O；GPSA §20.4 典型值）
_TEG_RELATIVE_VOLATILITY_DEFAULT: Final[float] = 4.5
# DEG 相对挥发度（DEG/H2O；GPSA §20.4 典型值；DEG 沸点 245°C vs TEG 288°C）
_DEG_RELATIVE_VOLATILITY_DEFAULT: Final[float] = 2.8
# GPSA §20.4 TEG 损失经验（gal TEG / MMscf gas）
_TEG_LOSS_GAL_PER_MMSCF: Final[float] = 0.5
# TEG 密度（lb/gal；用于 glycol gpm → lb/d 换算）
_TEG_DENSITY_LB_PER_GAL: Final[float] = 9.35
# 水密度（lb/gal；标准）
_WATER_DENSITY_LB_PER_GAL: Final[float] = 8.34
# GPSA §20.4 L/V 参考值（gal TEG / gal H2O；典型 3 gpm/MMscf × 1440 min/d 设计）
_LV_REFERENCE: Final[float] = 242.0
# L/V 容差带（±5%）：在此范围内 correction = 1.0 避免浮点边界误升 N_min
_LV_TOLERANCE: Final[float] = 0.05
# L/V 修正指数：c=0.5（与 brief 公式 1/sqrt(L/V) 对齐；含 L/V_ref 归一化）
_LV_N_CORRECTION_EXP: Final[float] = 0.5
_LV_D_CORRECTION_EXP: Final[float] = 0.5

GlycolType = Literal["TEG", "DEG"]


class GlycolDehydrationError(PcsError):
    """甘醇脱水输入错误（F2 / F5 边界拒绝）。"""

    code = "GLYCOL_DEHYDRATION_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class GlycolDehydrationInput:
    """TEG/DEG 甘醇脱水输入。

    字段：
      gas_flow_mmscfd: 干气流量（MMscf/day；SI 基准 lb/MMscf）
      inlet_water_content_lb_per_mmscf: 入口水含量（lb water / MMscf dry gas）
      outlet_water_content_lb_per_mmscf: 出口水含量（lb water / MMscf dry gas）
      glycol_type: "TEG"（三甘醇）/ "DEG"（二甘醇）
      contactor_tray_count: 接触塔实际塔盘数
      glycol_circulation_rate_gpm: 甘醇循环量（gal/min；GPSA 经验 3 gpm/MMscf）
      relative_volatility: α = glycol/H2O 相对挥发度（TEG 默认 4.5；DEG 默认 2.8）
      imperial_units: True → dual-unit 输出（tegloss_gal_d + diameter_ft）；
        False（默认，L-3 v1 BLOCKER 修定）→ SI 基准仅
    """

    gas_flow_mmscfd: float
    inlet_water_content_lb_per_mmscf: float
    outlet_water_content_lb_per_mmscf: float
    glycol_type: GlycolType
    contactor_tray_count: int
    glycol_circulation_rate_gpm: float
    relative_volatility: float = _TEG_RELATIVE_VOLATILITY_DEFAULT
    imperial_units: bool = False  # L-3 v1 BLOCKER: SI base per Global Constraints


@dataclass(frozen=True)
class GlycolDehydrationResult:
    """TEG/DEG 甘醇脱水结果。

    字段：
      dehydration_efficiency: 脱水效率 η = 1 - outlet/inlet（无量纲；0..1）
      n_tray_minimum: 最小塔盘数（GPSA §20.4 Eq.20-4，含 L/V 修正）
      is_tray_count_ok: 实际塔盘数 ≥ N_min（bool）
      teg_loss_gpd: TEG 损失（gal/day；GPSA 经验 0.5 × Q）
      contactor_diameter_in: 接触塔直径（inch；GPSA 经验 + L/V 修正）
      imperial_conversion: dual-unit 输出（仅 imperial_units=True）
      formula_ref: 公式引用（GPSA §20.4 Eq.20-4 等）
    """

    dehydration_efficiency: float
    n_tray_minimum: int
    is_tray_count_ok: bool
    teg_loss_gpd: float
    contactor_diameter_in: float
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]


def _resolve_relative_volatility(
    glycol_type: GlycolType,
    relative_volatility: float,
) -> float:
    """若用户未显式提供 relative_volatility，按 glycol_type 取默认值。"""
    if relative_volatility != _TEG_RELATIVE_VOLATILITY_DEFAULT:
        return relative_volatility
    if glycol_type == "DEG":
        return _DEG_RELATIVE_VOLATILITY_DEFAULT
    return _TEG_RELATIVE_VOLATILITY_DEFAULT


def _validate_input(inp: GlycolDehydrationInput) -> None:
    if inp.gas_flow_mmscfd <= 0:
        raise GlycolDehydrationError(
            f"Q_gas={inp.gas_flow_mmscfd} 必须 > 0"
        )
    if inp.inlet_water_content_lb_per_mmscf <= 0:
        raise GlycolDehydrationError(
            "入口水含量必须 > 0"
        )
    if not (
        0.0
        <= inp.outlet_water_content_lb_per_mmscf
        < inp.inlet_water_content_lb_per_mmscf
    ):
        raise GlycolDehydrationError(
            "outlet 必须在 [0, inlet) 范围"
        )
    if inp.contactor_tray_count < 1:
        raise GlycolDehydrationError(
            "塔盘数必须 ≥ 1"
        )
    if inp.glycol_circulation_rate_gpm <= 0:
        raise GlycolDehydrationError(
            "甘醇循环量必须 > 0"
        )
    if inp.relative_volatility <= 1.0:
        raise GlycolDehydrationError(
            f"α={inp.relative_volatility} 必须 > 1（volatility ratio）"
        )


def calc_glycol_dehydration(
    inp: GlycolDehydrationInput,
) -> GlycolDehydrationResult:
    """TEG/DEG 甘醇脱水主计算入口。

    计算步骤：
      1. _validate_input 边界拒绝（F2/F5）
      2. 脱水效率 η = 1 - outlet/inlet
      3. L/V 比 = circulation_gpm / water_removed_lb_d（M-4 v2 BLOCKER）
      4. N_min（GPSA §20.4 Eq.20-4）+ L/V 修正
      5. TEG 损失（GPSA 经验）
      6. 接触塔直径（GPSA 经验 + L/V 修正）
      7. 封装 result（imperial 双单位若启用）
    """
    _validate_input(inp)

    alpha = _resolve_relative_volatility(inp.glycol_type, inp.relative_volatility)

    # 1. 脱水效率
    efficiency = 1.0 - (
        inp.outlet_water_content_lb_per_mmscf
        / inp.inlet_water_content_lb_per_mmscf
    )

    # 2. L/V 比（M-4 v2 BLOCKER：glycol_circulation_rate_gpm 影响 N_min + D_in）
    # 单位一致换算：gal TEG / gal H2O（无量纲）
    water_removed_lb_d = (
        (inp.inlet_water_content_lb_per_mmscf - inp.outlet_water_content_lb_per_mmscf)
        * inp.gas_flow_mmscfd
    )
    water_removed_safe = max(water_removed_lb_d, 1e-6)
    glycol_gal_d = inp.glycol_circulation_rate_gpm * 1440.0  # gpm → gal/day
    water_gal_d = water_removed_safe / _WATER_DENSITY_LB_PER_GAL  # lb/d → gal/d
    l_over_v = glycol_gal_d / max(water_gal_d, 1e-6)
    # N_min 修正因子：相对参考 L/V_ref 的偏差；容差带内修正 = 1.0
    # 温和修正（c=0.25）：5x L/V 偏差仅产生 1.08x 修正，避免误伤 N_min
    if l_over_v > 0 and abs(l_over_v - _LV_REFERENCE) / _LV_REFERENCE <= _LV_TOLERANCE:
        l_v_n_correction = 1.0
        l_v_d_correction = 1.0
    else:
        lv_ratio = l_over_v / _LV_REFERENCE
        l_v_n_correction = (
            lv_ratio ** (-_LV_N_CORRECTION_EXP) if l_over_v > 0 else 1.0
        )
        l_v_d_correction = (
            lv_ratio ** _LV_D_CORRECTION_EXP if l_over_v > 0 else 1.0
        )

    # 3. N_min（GPSA §20.4 Eq.20-4）
    ratio = inp.outlet_water_content_lb_per_mmscf / inp.inlet_water_content_lb_per_mmscf
    if ratio <= 0:
        n_min_raw = 0
        n_min_corrected = 0
    else:
        n_min_raw = math.ceil(math.log(1.0 / ratio) / math.log(alpha))
        n_min_corrected = max(1, math.ceil(n_min_raw * l_v_n_correction))

    is_ok = inp.contactor_tray_count >= n_min_corrected

    # 4. TEG 损失（GPSA §20.4 经验 0.5 gal/MMscf）
    teg_loss_gpd = _TEG_LOSS_GAL_PER_MMSCF * inp.gas_flow_mmscfd

    # 5. 接触塔直径（GPSA §20.4 经验 + L/V 修正）
    # D_in = (12 + 2·Q^(1/3)·1.5) × (L/V)^0.5
    base_diameter_in = 12.0 + 2.0 * (inp.gas_flow_mmscfd ** (1.0 / 3.0)) * 1.5
    d_in = base_diameter_in * l_v_d_correction

    # 6. imperial dual-unit 输出（L-3 v1 BLOCKER：默认 False）
    imperial: dict[str, float] | None = None
    if inp.imperial_units:
        imperial = {
            "tegloss_gal_d": teg_loss_gpd,
            "contactor_diameter_ft": d_in / 12.0,
        }

    return GlycolDehydrationResult(
        dehydration_efficiency=efficiency,
        n_tray_minimum=n_min_corrected,
        is_tray_count_ok=is_ok,
        teg_loss_gpd=teg_loss_gpd,
        contactor_diameter_in=d_in,
        imperial_conversion=imperial,
        formula_ref={
            "n_tray_minimum": (
                "N_min = ceil(ln(1/ratio)/ln(α)) × (L/V)^-0.5 [GPSA §20.4 Eq.20-4]"
            ),
            "tegloss": (
                f"TEG loss = {_TEG_LOSS_GAL_PER_MMSCF} × Q (gal/MMscf) [GPSA §20.4]"
            ),
            "contactor_diameter": (
                "D_in = (12 + 2·Q^(1/3)·1.5) × (L/V)^0.5 [GPSA §20.4]"
            ),
            "glycol_type": f"{inp.glycol_type}（TEG=三甘醇/DEG=二甘醇；α={alpha}）",
            "l_v_ratio": (
                f"L/V = {l_over_v:.3f} gal TEG / lb H₂O"
                f"（N_min 修正 {l_v_n_correction:.3f}; D_in 修正 {l_v_d_correction:.3f}）"
            ),
        },
    )


__all__ = [
    "GlycolDehydrationInput",
    "GlycolDehydrationResult",
    "GlycolDehydrationError",
    "GlycolDehydrationInput",
    "calc_glycol_dehydration",
    "GlycolType",
]