"""TEG/DEG 甘醇脱水 service 主入口（P6-5 C-16 / P6-6A-6 / SPEC §3.9.1 V1.1）。

按 SPEC §3.9.1 计算 TEG/DEG 接触塔脱水（GPSA §20.4 + Campbell 2000）。

P6-9-PICKUP-5 5C（REF-P6-8-2）后本文件为**编排层**：Behr 查表 / 露点反函数 /
再沸器+汽提气 三段工艺已拆至同包私有子模块 ``psychro/_glycol_dehydration/``：

  - ``_glycol_dehydration.behr`` — Behr 正函数（grid 查表 + 插值 + 酸气修正）
  - ``_glycol_dehydration.dewpoint`` — Behr 反函数（露点求解）
  - ``_glycol_dehydration.reboilers`` — 再沸器负荷 + 汽提气率 + 贫甘醇浓度

本文件保留：public API（``calc_glycol_dehydration`` + ``GlycolDehydration*``）、
L/V 修正 + N_min + 塔盘 + TEG 损失 + 接触塔尺寸编排、v5.1 占位版汽提气率
（填 ``stripping_gas_scf_per_gal_teg``，与 reboilers 的
``stripping_gas_rate_scf_gal`` 是**两个不同字段**，公式亦不同，见 REF-P6-8-1）。

P6-5 v2 5 段计算（contact-tower-only）：

  1. 入口水含量（lb water / MMscf dry gas）
  2. 接触塔塔盘设计（N_min 公式 — GPSA §20.4 Eq.20-4）
  3. 甘醇循环量（gpm；GPSA 经验 3 gpm/MMscf）
  4. TEG 损失（GPSA 经验 0.5 gal/MMscf）
  5. 脱水效率 η = 1 - outlet/inlet

P6-6A-6 v5.1 FULL glycol dehydration system 扩展：

  6. 接触塔高度（H = NTU × HETP）
  7. 接触塔全径（D_full = K·sqrt(Q)；K = 7.1187 单点标定，ADR-0045 Rev A）
  8. 截面积（CSA = π·D²/4）
  9. 水的露点（Behr 反函数 via brentq + Newton fallback）
  10. 酸气修正后的露点（Linear placeholder；P6-6B 接管真 Wichert-Aziz）
  11. 调整后露点（diff method，XLS PR-018 E25）
  12. 汽提气率 stripping gas rate（GPSA §20.4 Eq.20-5）
  13. 再沸器负荷 reboiler duty（简式焓平衡 3 项）
  14. 传质单元数 NTU（Kremser）

公式（GPSA §20.4 Eq.20-4）：

  N_min = ln(y_in / y_out) / ln(α)          原始公式
  N_min_final = ceil(N_min × (L/V)^-0.5)   L/V 修正（M-4 v2 BLOCKER）
  α = TEG/H2O 相对挥发度（典型 4.5；DEG 较低 2.8）

接触塔直径（GPSA §20.4 经验）：

  D_in = (12 + 2·Q^(1/3)·1.5) × (L/V)^0.5    L/V 修正（M-4 v2）

P6-6A-6 v5.1 FULL system 直径（ADR-0045 Rev A）：

  D_full_in = K × sqrt(Q_gas_mmscfd)         单点标定 K=7.1187
  K = 120.76 / sqrt(288)                     XLS PR-018 E40 单点反算

TEG 损失（GPSA 经验）：

  TEG loss = 0.5 × Q_gas (gal/day)            单点估算

Behr 系数（P6-6A-6 v5.1 Day-0 Gate）：

  log10(W) = A0 + A1·T_F + A2·T_F² + A3·log10(P_psia)
  A0 = 3.3552846960018585, A1 = 0.018921959032034738
  A2 = -4.608271243464537e-05, A3 = -1.034805419984532
  max_rel_err = 4.866% vs GPSA Fig 20-2 8 spot checks

单位约定：

  - SI 基准（imperial_units=False default，L-3 v1 BLOCKER 修定）
  - imperial_units=True → dual-unit 输出（tegloss_gal_d + diameter_ft）

冻结接口（A1-A4 + B1-B5 批次一致性）：

  - dataclass(frozen=True): Input + Result
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

P6-6A-6 v5.1 Ruling 5 OUT_OF_SCOPE 闭环：

  FULL system 仅 TEG；DEG 抛 GlycolDehydrationError

P6-6B T9 OUT_OF_SCOPE 4 子模块（reboiler / stripping / full column / lean glycol）
等待 P6-7 服务扩展；CONFIG 表已占位 ``glycol_dehydration_full_system``（10 行典型工况范围）。

术语约定（中文 → 英文，全文统一）：

  - 甘醇：glycol；按分子量区分二甘醇（DEG）/ 三甘醇（TEG）
  - 接触塔：contactor（塔盘 tray 型；本 service 仅 tray，不含 structured packing 计算）
  - 塔盘：tray；N_min 为最小塔盘数，contactor_tray_count 为实际塔盘数
  - 贫甘醇：lean glycol（浓度 wt%，见 lean_glycol_concentration_wt_pct）
  - 汽提气：stripping gas（SCF/gal TEG）
  - 露点：dewpoint（°F；Behr 反函数求解，缺 T/P 时置 None）
  - 再沸器：reboiler（负荷 BTU/hr 主输出，kW 派生见 reboiler_duty_kw）
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Final, Literal

from app.services.exceptions import PcsError
from app.services.psychro._glycol_dehydration.behr import BehrBaseline
from app.services.psychro._glycol_dehydration.dewpoint import _behr_inverse_dewpoint
from app.services.psychro._glycol_dehydration.reboilers import (
    ReboilerStrippingInput,
    ReboilerStrippingResult,
    _calc_lean_glycol_concentration_wt_pct,
    calc_reboiler_stripping,
)

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
# GPSA §20.4 L/V 参考值（gal TEG / lb H2O；典型 3 gpm/MMscf × 1440 min/d 设计）
_LV_REFERENCE: Final[float] = 242.0
# L/V 容差带（±5%）：在此范围内 correction = 1.0 避免浮点边界误升 N_min
_LV_TOLERANCE: Final[float] = 0.05
# L/V 修正指数：c = 0.5（与 brief 公式 1/sqrt(L/V) 对齐；含 L/V_ref 归一化）
_LV_N_CORRECTION_EXP: Final[float] = 0.5
_LV_D_CORRECTION_EXP: Final[float] = 0.5

# P6-6A-6 v5.1 — FULL system bounds
_LEAN_GLYCOL_MIN: Final[float] = 0.95
_LEAN_GLYCOL_MAX: Final[float] = 0.999
_FLOODING_C_SB_MIN: Final[float] = 0.30
_FLOODING_C_SB_MAX: Final[float] = 0.80
_ALPHA_MIN: Final[float] = 1.0
_ALPHA_MAX: Final[float] = 50.0
_CO2_MOL_PCT_MIN: Final[float] = 0.0
_CO2_MOL_PCT_MAX: Final[float] = 100.0
_H2S_MOL_PCT_MIN: Final[float] = 0.0
_H2S_MOL_PCT_MAX: Final[float] = 100.0

# P6-6A-6 v5.1 — physical bounds (column height, lean glycol)
_COLUMN_HEIGHT_MAX_FT: Final[float] = 200.0
_HETP_DEFAULT_FT: Final[float] = 4.0  # GPSA §20.4 typical for structured packing

# P6-6A-6 v5.1 — FULL system diameter constants (H-2 + B-2 落实 — K 单点标定 ADR-0045 Rev A)
_FULL_COLUMN_K_DEFAULT: Final[float] = 7.1187
_FULL_COLUMN_XLS_Q_MMSCF_MIN: Final[float] = 144.0  # 288 ± 50%
_FULL_COLUMN_XLS_Q_MMSCF_MAX: Final[float] = 432.0

# Reboiler 输出单位换算：BTU/hr → kW
_BTU_PER_HR_PER_KW: Final[float] = 3412.14

# P6-6A-6 v5.1 — v5.1 占位版 stripping gas（GPSA §20.4 Eq.20-5 simplified）
# 注：仅服务 result 字段 stripping_gas_scf_per_gal_teg（XLS E32 残差 ~99% 登记）。
# 与 reboilers._calc_stripping_gas_rate_scf_gal_teg（Antoine 真 P_sat,TEG）**不是**
# 同一字段、同一公式，不可互相替代 —— 见 REF-P6-8-1 / 5C report。
_STRIPPING_K_DEFAULT: Final[float] = 1.5  # placeholder; P6-6B 接管真值

_LOGGER = logging.getLogger(__name__)

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

    P6-6A-6 v5.1 追加（10 optional — Ruling 1 现有字段零改动）：
      temperature_f: 接触塔温度 °F（Behr 反函数 / stripping gas 用）
      pressure_psia: 接触塔压力 psia（Behr 反函数 / stripping gas 用）
      lean_glycol_concentration: 贫甘醇浓度（质量分率；reboiler duty 用）
      vapour_space_ft: 蒸汽空间 ft（column height 增量）
      sump_height_ft: 集液段高度 ft（column height 增量）
      hetp_ft: 等板高度 ft（column height = NTU × HETP）
      approach_to_equilibrium_f: 露点接近度 °F（adjusted dewpoint）
      flooding_c_sb: Souders-Brown C_sb（v5.1 预留，v5 helper 不使用 — ADR-0045 Rev A）
      co2_mol_pct: CO2 摩尔百分比（acid gas correction）
      h2s_mol_pct: H2S 摩尔百分比（acid gas correction）

    P6-8 T5 追加（2 optional — OPEN-P6-6A-6 集成，向后兼容）：
      reboiler_temperature_f: 再沸器温度 °F（默认 400.0，与 ReboilerStrippingInput 一致）
      teg_circulation_rate_gal_lb: TEG 循环量 lb/d（None → 由 glycol_circulation_rate_gpm 换算）
    """

    gas_flow_mmscfd: float
    inlet_water_content_lb_per_mmscf: float
    outlet_water_content_lb_per_mmscf: float
    glycol_type: GlycolType
    contactor_tray_count: int
    glycol_circulation_rate_gpm: float
    relative_volatility: float = _TEG_RELATIVE_VOLATILITY_DEFAULT
    imperial_units: bool = False  # L-3 v1 BLOCKER: SI base per Global Constraints
    # P6-6A-6 v5.1 — 10 optional fields appended (Ruling 1: zero change to existing 8)
    temperature_f: float | None = None
    pressure_psia: float | None = None
    lean_glycol_concentration: float | None = None
    vapour_space_ft: float | None = None
    sump_height_ft: float | None = None
    hetp_ft: float | None = None
    approach_to_equilibrium_f: float = 5.0  # GPSA §20.4 typical
    flooding_c_sb: float = 0.65  # reserved; ADR-0045 Rev A (P6-6B 接管)
    co2_mol_pct: float = 0.0
    h2s_mol_pct: float = 0.0
    # P6-8 T5 — OPEN-P6-6A-6 集成（向后兼容；None → service 内部推导）
    reboiler_temperature_f: float = 400.0  # 默认与 ReboilerStrippingInput 一致
    teg_circulation_rate_gal_lb: float | None = None  # None → from glycol_circulation_rate_gpm


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

    P6-6A-6 v5.1 追加（12 optional — Ruling 1 现有字段零改动）：
      water_dewpoint_f: 水的露点 °F（Behr 反函数；T<60°F 标记 extrapolated）
      adjusted_dewpoint_f: 调整后露点 °F（diff method）
      lean_glycol_concentration: 贫甘醇浓度回显
      stripping_gas_scf_per_gal_teg: 汽提气率 SCF/gal TEG（GPSA §20.4 Eq.20-5；
        v5.1 占位版 k_strip=1.5 + 简式 P_sat，占真 Antoine 版本的
        ``stripping_gas_rate_scf_gal`` 字段）
      column_diameter_full_in: 接触塔全径 inch（K=7.1187 单点标定）
      column_height_ft: 接触塔高度 ft（NTU × HETP + vapour space + sump）
      number_of_transfer_units: NTU（Kremser）
      mass_h2o_removed_lb_s: 脱水速率 lb/s
      reboiler_duty_btu_hr: 再沸器负荷 BTU/hr（P6-8 T5 起 = ``ReboilerStrippingResult
        .q_total_btu_hr`` 完整焓平衡含 +10% 裕度；v5.1 简式 3 项版已由
        REF-P6-8-1（5C）去冗余移除）
      column_csa_ft2: 截面积 ft²
      dewpoint_unavailable_reason: dewpoint 不可用原因（如缺 T/P）
      acid_gas_corrected: acid gas correction 是否生效（bool）

    P6-8 T5 追加（4 outputs + warning — OPEN-P6-6A-6 集成，向后兼容）：
      reboiler_duty_kw: 再沸器负荷 kW（reboiler_duty_btu_hr × 0.000293071）
      stripping_gas_rate_scf_gal: 汽提气率 SCF/gal TEG（T1 calc_reboiler_stripping；
        Antoine 真 P_sat,TEG 版本）
      lean_glycol_concentration_wt_pct: 贫甘醇浓度 wt%（T4 GPSA Fig 20-4 查表）
      warnings: 工艺未对账 warning 列表（默认空 list）
    """

    dehydration_efficiency: float
    n_tray_minimum: int
    is_tray_count_ok: bool
    teg_loss_gpd: float
    contactor_diameter_in: float
    imperial_conversion: dict[str, float] | None
    formula_ref: dict[str, str]
    # P6-6A-6 v5.1 — 12 optional fields appended (Ruling 1: zero change to existing 7)
    water_dewpoint_f: float | None = None
    adjusted_dewpoint_f: float | None = None
    lean_glycol_concentration: float | None = None
    stripping_gas_scf_per_gal_teg: float | None = None
    column_diameter_full_in: float | None = None
    column_height_ft: float | None = None
    number_of_transfer_units: float | None = None
    mass_h2o_removed_lb_s: float | None = None
    reboiler_duty_btu_hr: float | None = None
    column_csa_ft2: float | None = None
    dewpoint_unavailable_reason: str | None = None
    acid_gas_corrected: bool = False
    # P6-8 T5 — OPEN-P6-6A-6 集成 4 outputs + WARNING 字段
    reboiler_duty_kw: float | None = None  # Q_total × 0.000293071
    stripping_gas_rate_scf_gal: float | None = None  # T1 calc_reboiler_stripping
    lean_glycol_concentration_wt_pct: float | None = None  # T4 GPSA Fig 20-4
    warnings: list[str] = field(default_factory=list)  # 工艺未对账 warning 列表


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
    """F2 / F5 边界拒绝校验。"""
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
    # P6-6A-6 v5.1 — additional FULL system bounds
    if not (_ALPHA_MIN <= inp.relative_volatility <= _ALPHA_MAX):
        raise GlycolDehydrationError(
            f"relative_volatility={inp.relative_volatility} 越界 "
            f"[{_ALPHA_MIN}, {_ALPHA_MAX}]"
        )
    if inp.lean_glycol_concentration is not None and not (
        _LEAN_GLYCOL_MIN <= inp.lean_glycol_concentration <= _LEAN_GLYCOL_MAX
    ):
        raise GlycolDehydrationError(
            f"lean_glycol_concentration={inp.lean_glycol_concentration} "
            f"必须在 [{_LEAN_GLYCOL_MIN}, {_LEAN_GLYCOL_MAX}]"
        )
    if not (
        _FLOODING_C_SB_MIN <= inp.flooding_c_sb <= _FLOODING_C_SB_MAX
    ):
        raise GlycolDehydrationError(
            f"flooding_c_sb={inp.flooding_c_sb} "
            f"必须在 [{_FLOODING_C_SB_MIN}, {_FLOODING_C_SB_MAX}]"
        )
    if not (_CO2_MOL_PCT_MIN <= inp.co2_mol_pct <= _CO2_MOL_PCT_MAX):
        raise GlycolDehydrationError(
            f"co2_mol_pct={inp.co2_mol_pct} 越界 [0, 100]"
        )
    if not (_H2S_MOL_PCT_MIN <= inp.h2s_mol_pct <= _H2S_MOL_PCT_MAX):
        raise GlycolDehydrationError(
            f"h2s_mol_pct={inp.h2s_mol_pct} 越界 [0, 100]"
        )


# ============================================================================
# P6-6A-6 v5.1 — Private helpers (Ruling 9: 不入 __all__)
# ============================================================================


def _calc_number_of_transfer_units(
    inlet_w_lb_per_mmscf: float,
    outlet_w_lb_per_mmscf: float,
    alpha: float,
) -> float:
    """NTU (Number of Transfer Units) via Kremser for TEG dehydration.

    Kremser simplified form (GPSA §20.4):
        NTU = (W_in/W_out - 1) / (α - 1)

    Args:
        inlet_w_lb_per_mmscf: 入口水含量 lb/MMscf
        outlet_w_lb_per_mmscf: 出口水含量 lb/MMscf
        alpha: 相对挥发度 α = glycol/H2O
    Returns:
        NTU（无量纲）
    """
    if alpha <= 1.0:
        raise GlycolDehydrationError(
            f"alpha={alpha} 必须 > 1（NTU 公式分母 α-1）"
        )
    if outlet_w_lb_per_mmscf <= 0:
        return 0.0
    return (inlet_w_lb_per_mmscf / outlet_w_lb_per_mmscf - 1.0) / (alpha - 1.0)


def _calc_column_height_ft(ntu: float, hetp_ft: float) -> float:
    """Column height = NTU × HETP (GPSA §20.4).

    简化：不加 vapour_space / sump（由 caller 决定是否叠加）。
    """
    return ntu * hetp_ft


def _calc_full_column_diameter_in(
    gas_flow_mmscfd: float,
    flooding_c_sb: float = 0.65,  # NOTE: reserved for P6-6B 工艺扩展; v5.1 helper 不使用
    baseline: BehrBaseline = "general",  # NOTE: reserved, 与 baseline 解耦 (P6-7 T2); K 与酸气无关
) -> float:
    """Full column diameter via XLS PR-018 K=7.1187 single-point calibration.

    v5 修订 (H-2 落实) — 撤回 v4 物理依据（"gas-continuous vs liquid-continuous" 论断
    与主流文献不符）。本公式 = Souders-Brown 在 (sg=0.6, TEG=99%, P=1000 psia,
    T=120°F) 工况下的**标定简化式**，K 值由 XLS PR-018 E40=120.76 in @ Q=288
    MMscfd 单点反算。

    30× 偏差根因 (B-1 落实):
        v3 用 Souders-Brown 计算时 V_actual 用了实际态气速（~3.19 ft/s 实际 flooding，
        实际态设计气速 ~2.71 ft/s），但 XLS E40=120.76 in 对应**标准态当量气速**
        V_std = 3333.33 ft³/s sizing。

    ADR-0045 Rev A 定性:
        - K=7.1187 = Souders-Brown 在 XLS PR-018 工况下的标定简化式
        - **单点标定**，适用范围未经多工况验证
        - 越界 (sg/TEG/P/T 偏离 XLS PR-018 工况) WARNING `[K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]`

    容差: rel ≤ 1e-2 (XLS E40 验证 within 1e-3; K 标定常数)

    Args:
        gas_flow_mmscfd: 气体流量 [MMscf/d] ∈ [1, 500]
        flooding_c_sb: # reserved, unused in v5.1 (P6-6B 工艺接管)
        baseline: reserved, 与 baseline 解耦 (P6-7 T2); K 与酸气 baseline 无关
    Returns:
        Full column diameter [in]
    """
    return _FULL_COLUMN_K_DEFAULT * math.sqrt(gas_flow_mmscfd)


def _calc_stripping_gas_rate_scf_per_gal_teg(
    temperature_f: float,
    pressure_psia: float,
    lean_glycol_concentration: float | None,
) -> float:
    """Stripping gas rate v5.1 占位版（GPSA §20.4 Eq.20-5 simplified）。

    简式：
        SGR = k_strip × (P_sat_TEG / P_total) × (1 - X_lean) / X_lean

    注：占位实现，使用 _STRIPPING_K_DEFAULT；P6-6B 接管真 P_sat_TEG（Antoine 方程）。

    ⚠️ **非** ``_glycol_dehydration.reboilers._calc_stripping_gas_rate_scf_gal_teg``
    的重复：后者填 result 字段 ``stripping_gas_rate_scf_gal``（Antoine 真 P_sat,
    k_strip=6.5），本函数填 ``stripping_gas_scf_per_gal_teg``（占位 P_sat,
    k_strip=1.5）。两者是**不同 result 字段 + 不同公式**，并存不构成冗余
    （REF-P6-8-1 去冗余范围仅限 ``_calc_reboiler_duty_simple_btu_hr``）。

    Args:
        temperature_f: 接触塔温度 °F
        pressure_psia: 接触塔压力 psia
        lean_glycol_concentration: 贫甘醇浓度（质量分率；None 时使用默认 0.99）
    Returns:
        Stripping gas rate [SCF stripping gas / gal TEG]
    """
    x_lean = lean_glycol_concentration if lean_glycol_concentration is not None else 0.99
    # 简化：温度压力影响占位（P6-6B 接管 P_sat_TEG via Antoine）
    pressure_factor = (temperature_f + 459.67) / pressure_psia
    return _STRIPPING_K_DEFAULT * pressure_factor * (1.0 - x_lean) / x_lean


def calc_glycol_dehydration(
    inp: GlycolDehydrationInput,
) -> GlycolDehydrationResult:
    """TEG/DEG 甘醇脱水主计算入口。

    计算步骤（P6-5 v2 5 段 + P6-6A-6 v5.1 FULL 9 段）：
      1. _validate_input 边界拒绝（F2/F5）
      2. 脱水效率 η = 1 - outlet/inlet
      3. L/V 比 = circulation_gpm / water_removed_lb_d（M-4 v2 BLOCKER）
      4. N_min（GPSA §20.4 Eq.20-4）+ L/V 修正
      5. TEG 损失（GPSA 经验）
      6. 接触塔直径（GPSA 经验 + L/V 修正）
      7. (P6-6A-6 v5.1) FULL 系统：NTU + HETP + D_full + CSA
      8. (P6-6A-6 v5.1) Behr 反函数 dewpoint（仅当 T/P 提供）
      9. (P6-6A-6 v5.1) Stripping gas + Reboiler duty
      10. 封装 result（imperial 双单位若启用）

    P6-6A-6 v5.1 Ruling 5 OUT_OF_SCOPE 闭环:
      - FULL system 仅 TEG；DEG 抛 GlycolDehydrationError

    P6-9-PICKUP-5 5C（REF-P6-8-1）: 原 v5.1 简式 ``_calc_reboiler_duty_simple_btu_hr``
    的返回值在 Step 7.11 被 ``ReboilerStrippingResult.q_total_btu_hr`` 完整焓平衡
    无条件覆盖，从未被读取 —— 已去冗余移除。``reboiler_duty_btu_hr`` 字段名与
    语义（= 完整负荷，含 +10% 裕度）保持不变。
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

    # ========== P6-6A-6 v5.1 — FULL system calculations ==========

    # 7. Ruling 5 OUT_OF_SCOPE 字段计算（仅 TEG 全套）
    if inp.glycol_type != "TEG":
        raise GlycolDehydrationError(
            "FULL glycol dehydration system 仅支持 TEG；"
            "DEG 仅有 partial coverage（Ruling 5）"
        )

    # alpha 来源：inp.relative_volatility（默认 4.5，与 SPEC §3.9.1 一致）
    alpha_v51 = inp.relative_volatility

    # 7.1 mass_h2o_removed_lb_s
    mass_h2o_removed_lb_s = (
        (inp.inlet_water_content_lb_per_mmscf - inp.outlet_water_content_lb_per_mmscf)
        * inp.gas_flow_mmscfd
        / 86400.0
    )

    # 7.2 NTU（Kremser; alpha = inp.relative_volatility, default 4.5）
    ntu = _calc_number_of_transfer_units(
        inp.inlet_water_content_lb_per_mmscf,
        inp.outlet_water_content_lb_per_mmscf,
        alpha_v51,
    )

    # 7.3-7.5 column_height, diameter, CSA (v5 TEG Contactor Sizing)
    hetp = inp.hetp_ft if inp.hetp_ft is not None else _HETP_DEFAULT_FT
    # Column height = NTU × HETP + vapour_space + sump (GPSA §20.4 + 工程惯例)
    # vap/sump 是 Optional[v3]; None 时按 0 ft 处理
    column_height_ft = (
        _calc_column_height_ft(ntu, hetp)
        + (inp.vapour_space_ft or 0.0)
        + (inp.sump_height_ft or 0.0)
    )
    if column_height_ft > _COLUMN_HEIGHT_MAX_FT:
        raise GlycolDehydrationError(
            f"column_height_ft={column_height_ft} 超过工程上限 {_COLUMN_HEIGHT_MAX_FT}"
        )
    column_diameter_full_in = _calc_full_column_diameter_in(
        inp.gas_flow_mmscfd,
        inp.flooding_c_sb,  # reserved, unused in v5.1 (per ADR-0045 Rev A)
    )
    column_csa_ft2 = math.pi / 4.0 * (column_diameter_full_in / 12.0) ** 2

    # 7.6 dewpoint + adjusted_dewpoint (v5 _DewpointResult dataclass + T<60°F extrapolation)
    dewpoint_unavailable_reason: str | None = None
    water_dewpoint_f: float | None = None
    adjusted_dewpoint_f: float | None = None
    if inp.temperature_f is None or inp.pressure_psia is None:
        dewpoint_unavailable_reason = (
            "temperature_f/pressure_psia 缺省；Behr dewpoint 计算不可用"
        )
    else:
        dp_result = _behr_inverse_dewpoint(
            inp.outlet_water_content_lb_per_mmscf,
            inp.pressure_psia,
            co2_mol_pct=inp.co2_mol_pct,
            h2s_mol_pct=inp.h2s_mol_pct,
        )
        if dp_result.dewpoint_f is None:
            dewpoint_unavailable_reason = dp_result.reason
        else:
            water_dewpoint_f = dp_result.dewpoint_f
            adjusted_dewpoint_f = water_dewpoint_f - inp.approach_to_equilibrium_f
            if dp_result.extrapolated:
                dewpoint_unavailable_reason = dp_result.reason

    # 7.7 K 单点标定越界检查（v5 修订 H-2 落实）
    formula_ref_d_full = (
        "D_full = K × sqrt(Q_gas) [GPSA §20.4 TEG Contactor Sizing; "
        "K=7.1187 from Worley PR-018 E40 single-point calibration; "
        "ADR-0045 Rev A]"
    )
    if not (
        _FULL_COLUMN_XLS_Q_MMSCF_MIN
        <= inp.gas_flow_mmscfd
        <= _FULL_COLUMN_XLS_Q_MMSCF_MAX
    ):
        formula_ref_d_full += " [K_UNVERIFIED_OUT_OF_XLS_CONDITIONS]"

    # 7.8 stripping gas rate (v5.1 占位版；填 stripping_gas_scf_per_gal_teg)
    stripping_gas_scf_per_gal_teg: float | None = None
    if inp.temperature_f is not None and inp.pressure_psia is not None:
        stripping_gas_scf_per_gal_teg = _calc_stripping_gas_rate_scf_per_gal_teg(
            inp.temperature_f,
            inp.pressure_psia,
            inp.lean_glycol_concentration,
        )

    # 7.9 acid_gas_corrected (v5.1: 纯逻辑判断, H-3 落实)
    acid_gas_corrected: bool = (
        inp.co2_mol_pct > 0.0
    ) or (
        inp.h2s_mol_pct > 0.0
    )

    # ========== P6-8 T5 — OPEN-P6-6A-6 集成（4 子模块 outputs + WARNING） ==========

    # 7.10 T1 Reboiler Duty + Stripping Gas Rate（OPEN-P6-6A-6 子任务 1+2）
    # 完整焓平衡 +10% 设计裕度 + Antoine v5 plan + WARNING 透出
    # REF-P6-8-1（5C）：此处是 reboiler_duty_btu_hr 的**唯一**来源
    # （原 v5.1 简式版在下方无条件覆盖前已算，纯冗余）。
    water_removed_lb_d_t5 = (
        (inp.inlet_water_content_lb_per_mmscf - inp.outlet_water_content_lb_per_mmscf)
        * inp.gas_flow_mmscfd
    )
    water_removal_rate_lb_hr = water_removed_lb_d_t5 / 24.0
    # teg_circulation_rate_gal_lb: API 显式传 → 用；否则从 glycol_circulation_rate_gpm 推导
    if inp.teg_circulation_rate_gal_lb is not None:
        teg_circ_gal_lb = inp.teg_circulation_rate_gal_lb
    else:
        glycol_gal_d_t5 = inp.glycol_circulation_rate_gpm * 1440.0
        teg_circ_gal_lb = glycol_gal_d_t5 / max(water_removed_lb_d_t5, 1e-6)

    reb_strip_input = ReboilerStrippingInput(
        water_removal_rate_lb_hr=water_removal_rate_lb_hr,
        teg_circulation_rate_gal_lb=teg_circ_gal_lb,
        teg_density_lb_gal=_TEG_DENSITY_LB_PER_GAL,
        reboiler_temperature_f=inp.reboiler_temperature_f,
        contactor_temperature_f=inp.temperature_f if inp.temperature_f is not None else 120.0,
        contactor_pressure_psia=inp.pressure_psia if inp.pressure_psia is not None else 1000.0,
        reflux_ratio=0.25,
        lean_glycol_concentration_wt_pct=(
            inp.lean_glycol_concentration if inp.lean_glycol_concentration is not None else 0.99
        ),
    )
    reb_strip_result = calc_reboiler_stripping(reb_strip_input)
    # T1 完整焓平衡为 reboiler_duty_btu_hr 唯一来源（含 +10% 设计裕度；
    # OPEN-P6-6A-6 工艺 2026-11-15 前未对账）
    reboiler_duty_btu_hr = reb_strip_result.q_total_btu_hr
    reboiler_duty_kw_t5 = reb_strip_result.q_total_btu_hr * 0.000293071
    stripping_gas_rate_scf_gal_t5 = reb_strip_result.sgr_scf_gal_teg
    warnings_t5: list[str] = list(reb_strip_result.warnings)

    # 7.11 T4 Lean Glycol Concentration（OPEN-P6-6A-6 子任务 4）
    lean_glycol_wt_pct_t5, lean_glycol_warnings = _calc_lean_glycol_concentration_wt_pct(
        reboiler_temperature_f=inp.reboiler_temperature_f,
        stripping_gas_scf_gal=stripping_gas_rate_scf_gal_t5,
    )
    warnings_t5.extend(lean_glycol_warnings)

    # Step 8. 扩展 result（12 字段追加含 dewpoint_unavailable_reason + acid_gas_corrected）
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
            # P6-6A-6 v5.1 — FULL system formulas
            "ntu": "NTU = (W_in/W_out - 1)/(α - 1) [Kremser]",
            "column_height": "H = NTU × HETP + vap + sump [GPSA §20.4 + 工程惯例]",
            "column_diameter_full": formula_ref_d_full,
            "mass_h2o_removed": "ṁ = (W_in - W_out) × Q × 1e6/86400 [lb/s]",
            "stripping_gas": (
                "SGR = k_strip × (P_sat_TEG/P) × (1-X)/X [GPSA §20.4 Eq.20-5; "
                "placeholder P_sat_TEG]"
            ),
            "reboiler_duty": (
                "Q = m_TEG·Cp·ΔT + m_H2O·Cp·ΔT + m_H2O·ΔH_vap [GPSA §20.4]"
            ),
            "water_dewpoint": (
                "Behr inverse via brentq/Newton returning _DewpointResult frozen "
                "dataclass [scipy; XLS PR-018 E23; v5.1 with acid gas; "
                "T<60°F Antoine extrapolation WARNING]"
            ),
            "adjusted_dewpoint": (
                "= water_dewpoint - approach_to_equilibrium [diff method; "
                "XLS PR-018 E25]"
            ),
            "acid_gas_correction": (
                "W_corr = W_baseline × (1 + 0.024·CO2 + 0.018·H2S) "
                "[LINEAR_PLACEHOLDER, NON-WICHERT-AZIZ; 真 Wichert-Aziz: "
                "ε = 120·[(y_CO2+y_H2S)^0.9 − (y_CO2+y_H2S)^1.6] + "
                "15·(y_H2S^0.5 − y_H2S^4); P6-6B PICKUP]"
            ),
        },
        # P6-6A-6 v5.1 — 12 new optional result fields
        water_dewpoint_f=water_dewpoint_f,
        adjusted_dewpoint_f=adjusted_dewpoint_f,
        lean_glycol_concentration=inp.lean_glycol_concentration,
        stripping_gas_scf_per_gal_teg=stripping_gas_scf_per_gal_teg,
        column_diameter_full_in=column_diameter_full_in,
        column_height_ft=column_height_ft,
        number_of_transfer_units=ntu,
        mass_h2o_removed_lb_s=mass_h2o_removed_lb_s,
        reboiler_duty_btu_hr=reboiler_duty_btu_hr,
        column_csa_ft2=column_csa_ft2,
        dewpoint_unavailable_reason=dewpoint_unavailable_reason,
        acid_gas_corrected=acid_gas_corrected,
        # P6-8 T5 — OPEN-P6-6A-6 集成 4 outputs + WARNING 字段
        reboiler_duty_kw=reboiler_duty_kw_t5,
        stripping_gas_rate_scf_gal=stripping_gas_rate_scf_gal_t5,
        lean_glycol_concentration_wt_pct=lean_glycol_wt_pct_t5,
        warnings=warnings_t5,
    )


# P6-6A-6 v5.1 Ruling 9: _calc_* helpers / _DewpointResult 私有化，不入 __all__
# P6-9-PICKUP-5 5C（REF-P6-8-2）: 下列 3 个 public 名已移至
#   app/services/psychro/_glycol_dehydration/reboilers.py，本处为向后兼容重导出。
# P6-8 T1: ReboilerStripping* 公开供 OPEN-P6-6A-6 工艺 2026-11-15 对账调用
__all__ = [
    "GlycolDehydrationInput",
    "GlycolDehydrationResult",
    "GlycolDehydrationError",
    "calc_glycol_dehydration",
    "GlycolType",
    "ReboilerStrippingInput",
    "ReboilerStrippingResult",
    "calc_reboiler_stripping",
]
