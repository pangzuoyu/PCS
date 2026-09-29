"""TEG/DEG 甘醇脱水 service（P6-5 C-16 / P6-6A-6 / SPEC §3.9.1 V1.1）。

按 SPEC §3.9.1 计算 TEG/DEG 接触塔脱水（GPSA §20.4 + Campbell 2000）：

P6-5 v2 5 段计算（contact-tower-only）：

  1. 入口水含量（lb water / MMscf dry gas）
  2. 接触塔塔盘设计（N_min 公式 — GPSA §20.4 Eq.20-4）
  3. 甘醇循环量（gpm；GPSA 经验 3 gpm/MMscf）
  4. TEG 损失（GPSA 经验 0.5 gal/MMscf）
  5. 脱水效率 η = 1 - outlet/inlet

P6-6A-6 v5.1 FULL glycol dehydration system 扩展：

  6. 接触塔高度（H = NTU × HETP）
  7. 接触塔全径（D_full = K·sqrt(Q)；K=7.1187 单点标定，ADR-0045 Rev A）
  8. 截面积（CSA = π·D²/4）
  9. 水的露点（Behr 反函数 via brentq + Newton fallback）
  10. 酸气修正后的露点（Linear placeholder, P6-6B 接管真 Wichert-Aziz）
  11. 调整后露点（diff method, XLS PR-018 E25）
  12. Stripping gas rate（GPSA §20.4 Eq.20-5）
  13. Reboiler duty（简式焓平衡 3 项）
  14. 传质单元数 NTU（Kremser）

公式（GPSA §20.4 Eq.20-4）：

  N_min = ln(y_in / y_out) / ln(α)            原始公式
  N_min_final = ceil(N_min × (L/V)^-0.5)     L/V 修正（M-4 v2 BLOCKER）
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

P6-6A-6 v5.1 Ruling 5 OUT_OF_SCOPE 闭环：

  FULL system 仅 TEG；DEG 抛 GlycolDehydrationError

P6-6B T9 OUT_OF_SCOPE 4 子模块（reboiler / stripping / full column /
lean glycol）等待 P6-7 服务扩展；CONFIG 表已占位
``glycol_dehydration_full_system``（10 行典型工况范围）。
"""
from __future__ import annotations

import bisect
import json
import logging
import math
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

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

# P6-6A-6 v5.1 — Behr constants (H-2 + B-2 落实 — K 单点标定 ADR-0045 Rev A)
_FULL_COLUMN_K_DEFAULT: Final[float] = 7.1187
_FULL_COLUMN_XLS_Q_MMSCF_MIN: Final[float] = 144.0  # 288 ± 50%
_FULL_COLUMN_XLS_Q_MMSCF_MAX: Final[float] = 432.0

# P6-8 T9r — Behr baseline 选择 (OPEN-P6-6A-9.5 代码侧闭环)
# general: v3 grid 默认, GPSA Fig 20-2 general zone (McKetta-Wehe sweet gas)
# high_acid: GPSA Fig 20-2 high-acid zone (H2S+CO2 >= 5 mol%), 工艺室 2026-09-29 v3 grid 交付
BehrBaseline = Literal["general", "high_acid"]

# Behr 反函数 bracket
_BEHR_DEWPOINT_BRACKET: Final[tuple[float, float]] = (60.0, 200.0)
_BEHR_DEWPOINT_EXTRAPOLATED_THRESHOLD_F: Final[float] = 60.0
_BEHR_DEWPOINT_EXTRAPOLATION_WARNING_TOL_F: Final[float] = 1e-4

_LOGGER = logging.getLogger(__name__)

# P6-8 T9r — Grid 查表 + 双线性插值 (OPEN-P6-6A-9.5 闭环)
# 工艺室 2026-09-29 第三批交付 v3 (查表 + 双线性插值)
_BEHR_GRID_PATH: Final[Path] = Path(
    __file__).resolve().parents[3] / "data" / "behr_coefficients.json"

# P6-6A-6 v5.1 — Bukacek 1990 T<60°F 延伸系数 (OPEN-P6-6A-9.4, 已闭环)
# 低温段 (T < 60°F) 用 Bukacek 1990 Table 3 延伸 (工艺室 2026-10-15 验证)。
# 边界 T = 60°F 用 grid high-temp (避免不连续 — brief §约束)。
_BEHR_MIX_LOW_T: Final[tuple[float, float, float, float]] = (
    2.1430, 0.01850, -0.000042, -0.9800,
)
_BEHR_T_BOUNDARY_F: Final[float] = 60.0


@dataclass(frozen=True)
class BehrGrid:
    """Behr 查表 + 双线性插值（工艺室 v3 交付）。

    字段:
      name: 'general' | 'high_acid'
      t_grid: T grid (°F)
      p_grid: P grid (psia)
      w_grid: W grid (lb/MMscf), shape=(len(t_grid), len(p_grid))
    """

    name: str
    t_grid: tuple[float, ...]
    p_grid: tuple[float, ...]
    w_grid: tuple[tuple[float, ...], ...]


def _load_behr_grids() -> dict[str, BehrGrid]:
    """从 pcs-backend/data/behr_coefficients.json 加载 grid（v3 工艺室交付）。

    Raises:
        RuntimeError: JSON 缺失 / schema 无效
    """
    try:
        raw = json.loads(_BEHR_GRID_PATH.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RuntimeError(
            f"Behr grid JSON 缺失: {_BEHR_GRID_PATH} ({e})"
        ) from e

    grids_raw = raw.get("grid")
    if not isinstance(grids_raw, dict):
        raise RuntimeError(
            f"Behr grid JSON schema 无效: 缺 'grid' dict 段 (at {_BEHR_GRID_PATH})"
        )

    out: dict[str, BehrGrid] = {}
    for name in ("general", "high_acid"):
        entry = grids_raw.get(name)
        if not isinstance(entry, dict):
            raise RuntimeError(f"Behr grid JSON 缺 grid.{name} 段")
        out[name] = BehrGrid(
            name=name,
            t_grid=tuple(entry["t_grid_f"]),
            p_grid=tuple(entry["p_grid_psia"]),
            w_grid=tuple(tuple(row) for row in entry["w_grid_lb_per_mmscf"]),
        )
    return out


# Module-level eager load (启动期 fail-fast on schema invalid)
_BEHR_GRIDS: Final[dict[str, BehrGrid]] = _load_behr_grids()


def _bilinear_interp_behr(
    grid: BehrGrid,
    temperature_f: float,
    pressure_psia: float,
) -> tuple[float, bool]:
    """Behr grid 双线性插值。

    Returns:
        (w_value, extrap_used) - extrap_used 为 True 表示越界 clamp
    """
    t_grid = grid.t_grid
    p_grid = grid.p_grid
    w_grid = grid.w_grid

    # 越界 clamp
    t_q = max(t_grid[0], min(t_grid[-1], temperature_f))
    p_q = max(p_grid[0], min(p_grid[-1], pressure_psia))
    extrap_used = (t_q != temperature_f) or (p_q != pressure_psia)

    # 找 T bracket
    i = max(0, min(bisect.bisect_right(t_grid, t_q) - 1, len(t_grid) - 2))
    j = max(0, min(bisect.bisect_right(p_grid, p_q) - 1, len(p_grid) - 2))

    t0, t1 = t_grid[i], t_grid[i + 1]
    p0, p1 = p_grid[j], p_grid[j + 1]
    w00 = w_grid[i][j]
    w01 = w_grid[i][j + 1]
    w10 = w_grid[i + 1][j]
    w11 = w_grid[i + 1][j + 1]

    ft = (t_q - t0) / (t1 - t0) if t1 > t0 else 0.0
    fp = (p_q - p0) / (p1 - p0) if p1 > p0 else 0.0
    w = (
        w00 * (1 - ft) * (1 - fp)
        + w01 * (1 - ft) * fp
        + w10 * ft * (1 - fp)
        + w11 * ft * fp
    )
    return w, extrap_used


# P6-6A-6 v5.1 — Acid gas linear correction placeholder coefficients (H-1 落实)
_ACID_GAS_CO2_COEF: Final[float] = 0.024
_ACID_GAS_H2S_COEF: Final[float] = 0.018

# P6-6A-6 v5.1 — Reboiler duty 简式焓平衡 3 项 (GPSA §20.4)
# NOTE: 这些是工艺侧占位常数；P6-6B 接管 TEG 物性精确值
_REBOILER_CP_TEG_BTU_PER_LB_F: Final[float] = 0.55  # TEG 比热
_REBOILER_CP_WATER_BTU_PER_LB_F: Final[float] = 1.0  # 水比热
_REBOILER_DT_F: Final[float] = 30.0  # rich-to-lean TEG ΔT
_REBOILER_DH_VAP_BTU_PER_LB: Final[float] = 1000.0  # 水蒸发潜热近似
# Reboiler 输出单位换算：BTU/hr → kW
_BTU_PER_HR_PER_KW: Final[float] = 3412.14

# P6-6A-6 v5.1 — Stripping gas placeholder (GPSA §20.4 Eq.20-5 simplified)
_STRIPPING_K_DEFAULT: Final[float] = 1.5  # placeholder; P6-6B 接管真值

GlycolType = Literal["TEG", "DEG"]


class GlycolDehydrationError(PcsError):
    """甘醇脱水输入错误（F2 / F5 边界拒绝）。"""

    code = "GLYCOL_DEHYDRATION_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class _DewpointResult:
    """Behr 反函数结果 (frozen dataclass) — 三态显式避免 tuple 歧义。

    三态语义:
      FOUND          — dewpoint_f 非 None, extrapolated=False, reason=None
      EXTRAPOLATED   — dewpoint_f 非 None, extrapolated=True (T<60°F Antoine 外推),
                       reason=外推说明
      NOT_FOUND      — dewpoint_f=None, extrapolated=False/True,
                       reason="brentq and Newton both failed"
    """

    dewpoint_f: float | None
    extrapolated: bool = False
    reason: str | None = None


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
      stripping_gas_scf_per_gal_teg: 汽提气率 SCF/gal TEG（GPSA §20.4 Eq.20-5）
      column_diameter_full_in: 接触塔全径 inch（K=7.1187 单点标定）
      column_height_ft: 接触塔高度 ft（NTU × HETP + vapour space + sump）
      number_of_transfer_units: NTU（Kremser）
      mass_h2o_removed_lb_s: 脱水速率 lb/s
      reboiler_duty_btu_hr: 再沸器负荷 BTU/hr（简式焓平衡 3 项）
      column_csa_ft2: 截面积 ft²
      dewpoint_unavailable_reason: dewpoint 不可用原因（如缺 T/P）
      acid_gas_corrected: acid gas correction 是否生效（bool）
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


def _correct_behr_for_acid_gas(
    w_baseline: float, co2_mol_pct: float, h2s_mol_pct: float,
) -> float:
    """Linear acid gas correction placeholder (NON-Wichert-Aziz).

    ⚠️ 本函数**不是** Wichert-Aziz 公式 —— Wichert-Aziz 是非线性形式（reference）:
        ε = 120 × [(y_CO2+y_H2S)^0.9 − (y_CO2+y_H2S)^1.6]
            + 15 × (y_H2S^0.5 − y_H2S^4)
        W_corr = W_baseline × (1 + ε/100)

    本函数是**线性 placeholder**（v5 plan 阶段占位）:
        W_corr = W_baseline × (1 + 0.024·co2_mol_pct + 0.018·h2s_mol_pct)

    与 XLS PR-018 E20=103.91 对照:
        GPSA baseline (120°F, 1000 psia) = 70
        线性修正 +5% 酸气 = 70 × 1.102 = 77.1
        残差 = (103.91 − 77.1)/103.91 = 25.8% 未解释

    XLS PR-018 E20 残差可能来自:
        (a) XLS 用不同 baseline（非 GPSA Fig 20-2）
        (b) XLS 工况含额外酸气/盐度
        (c) XLS 内部用非线性 Wichert-Aziz

    P6-6B 工艺工程师接管真 Wichert-Aziz + XLS 残差根因。

    Source: [LINEAR_PLACEHOLDER, NON-WICHERT-AZIZ, P6-6B PICKUP]
    Range: co2/h2s ∈ [0, 100] mol%
    """
    return w_baseline * (
        1.0 + _ACID_GAS_CO2_COEF * co2_mol_pct
        + _ACID_GAS_H2S_COEF * h2s_mol_pct
    )


def _calc_behr_water_content_lb_per_mmscf(
    temperature_f: float, pressure_psia: float,
    co2_mol_pct: float = 0.0,
    h2s_mol_pct: float = 0.0,
    baseline: BehrBaseline = "general",
) -> tuple[float, list[str]]:
    """Behr correlation: Grid 查表 + 双线性插值 (T >= 60°F) + Bukacek (T < 60°F) + Acid gas.

    P6-8 T9r (OPEN-P6-6A-9.5 代码侧闭环):
      工艺室 2026-09-29 第三批交付 v3 grid (7 T × 4 P 矩阵, general + high_acid)
      替代经验公式拟合（4-param quadratic / Katz 5-param / Behr 3-param 均失败）;
      无拟合误差, 无 Jacobian 病态。

      T >= 60°F 段: grid 查表 + 双线性插值
      T < 60°F 段: Bukacek 1990 Table 3 延伸 (OPEN-P6-6A-9.4 已闭环)
      Acid gas correction:
        general   → Linear placeholder (向后兼容, 既有 _correct_behr_for_acid_gas)
        high_acid → 真 Wichert-Aziz (T2 工艺室 2026-10-31 闭合 OPEN-P6-6A-9.5,
                    ε = 120·[(y_CO2+y_H2S)^0.9 − (y_CO2+y_H2S)^1.6]
                        + 15·(y_H2S^0.5 − y_H2S^4))

    XLS PR-018 E20=103.91 验证 (high_acid baseline):
        W_baseline(120°F, 1000 psia) = 93.5 lb/MMscf (v3 grid 直接读出)
        W_corr(93.5, +5% acid gas) ≈ 93.5 × 1.0971 = 102.59
        残差 ~1.27% vs XLS 103.91 ✓ (< 5% 容差)

    Source: pcs-backend/data/behr_coefficients.json v3 (工艺室 2026-09-29 交付)
            GPSA Engineering Data Book 13th Ed §20.4 Fig 20-2
            Bukacek (1990) "Water content of natural gas" (low-T extension)
            Wichert & Aziz (1972) HP 51(4) 119-122 (high_acid acid gas correction)

    NOT Behr (1981) primary 原文 — 适用于 natural gas (sg 0.6).
    PRIVATE helper (_ 前缀 + 不入 __all__), **不**与 calc_saturation_water_content 互调
    (Ruling 9 working fluid 边界: natural gas vs humid air).

    Args:
        temperature_f: Temperature [°F]; T >= 60°F 用 grid 查表 + 双线性插值,
                       T < 60°F 用 Bukacek 1990 延伸 (validity T ∈ [-40, 60]°F, 仅 general)
        pressure_psia: Pressure [psia] ∈ [500, 2000] (grid validity domain);
                       越界 clamp + WARNING
        co2_mol_pct: CO2 摩尔百分比 (default 0)
        h2s_mol_pct: H2S 摩尔百分比 (default 0)
        baseline: 'general' (default, 向后兼容) / 'high_acid' (XLS PR-018 path)
    Returns:
        (water_content_lb_per_mmscf, warnings)
        warnings 列表可能含:
          - "BEHR_GRID_EXTRAPOLATED: T/P out of validity domain; clamp to nearest grid"
    """
    warnings: list[str] = []
    if temperature_f < _BEHR_T_BOUNDARY_F:
        # 低 T 段：Bukacek 1990 Table 3 公式（OPEN-P6-6A-9.4 已闭环，仅 general baseline）
        A0, A1, A2, A3 = _BEHR_MIX_LOW_T
        log10_w = (
            A0
            + A1 * temperature_f
            + A2 * temperature_f ** 2
            + A3 * math.log10(pressure_psia)
        )
        w_baseline = 10 ** log10_w
    else:
        # 高 T 段：grid 查表 + 双线性插值（v3 工艺室交付）
        grid = _BEHR_GRIDS[baseline]
        w_baseline, extrap_used = _bilinear_interp_behr(grid, temperature_f, pressure_psia)
        if extrap_used:
            warnings.append(
                "BEHR_GRID_EXTRAPOLATED: T/P out of validity domain; clamp to nearest grid"
            )

    # Acid gas correction
    acid_gas_applied = (co2_mol_pct > 0) or (h2s_mol_pct > 0)
    if not acid_gas_applied:
        return (w_baseline, warnings)
    if baseline == "high_acid":
        # 真 Wichert-Aziz (OPEN-P6-6A-9.5)
        y_sum = (co2_mol_pct + h2s_mol_pct) / 100.0
        y_h2s = h2s_mol_pct / 100.0
        epsilon = (
            120.0 * (y_sum ** 0.9 - y_sum ** 1.6)
            + 15.0 * (y_h2s ** 0.5 - y_h2s ** 4)
        )
        return (w_baseline * (1.0 + epsilon / 100.0), warnings)
    # general baseline: 保持线性 placeholder (向后兼容, 既有 _correct_behr_for_acid_gas)
    w_corr = _correct_behr_for_acid_gas(w_baseline, co2_mol_pct, h2s_mol_pct)
    return (w_corr, warnings)


def _behr_inverse_dewpoint(
    target_w_lb_per_mmscf: float, pressure_psia: float,
    co2_mol_pct: float = 0.0, h2s_mol_pct: float = 0.0,
) -> _DewpointResult:
    """Behr 反函数 — 给定 W 反算 T_dew (°F), scipy brentq + Newton fallback.

    v5.1 完整实现 (B-3 + H-3 落实):
        求解 f(T) = W_baseline(T, P) - W_target = 0
        若 f(60°F) × f(200°F) 同号 → 扩展 bracket 到 [-100°F, 300°F]
        若 brentq 失败 (maxiter=100) → Newton fallback (analytical derivative)
        若都失败 → 返回 _DewpointResult(None, ..., reason="...")
        若 T < 60°F → extrapolated=True, reason="T<60°F extrapolation, accuracy±20%"

    Returns:
        _DewpointResult dataclass (frozen): 三态显式 FOUND/EXTRAPOLATED/NOT_FOUND
    """
    from scipy.optimize import brentq

    T_BRACKET: tuple[float, float] = (_BEHR_DEWPOINT_BRACKET[0], _BEHR_DEWPOINT_BRACKET[1])
    T_EXTENDED_BRACKET: tuple[float, float] = (-100.0, 300.0)

    def _residual_w(T_f: float) -> float:
        w, _ = _calc_behr_water_content_lb_per_mmscf(
            T_f, pressure_psia, co2_mol_pct, h2s_mol_pct,
        )
        return w - target_w_lb_per_mmscf

    dewpoint_f: float | None = None

    try:
        # 缩 bracket 到 f(a)·f(b) < 0
        a, b = T_BRACKET
        fa, fb = _residual_w(a), _residual_w(b)
        if fa * fb > 0:
            a, b = T_EXTENDED_BRACKET
            fa, fb = _residual_w(a), _residual_w(b)
            if fa * fb > 0:
                raise ValueError("no sign change in extended bracket")
        dewpoint_f = brentq(_residual_w, a, b, maxiter=100, xtol=1e-4)
    except Exception:
        # Newton fallback (numerical derivative; grid lookup 无 closed-form derivative)
        try:
            T = 60.0  # 初值
            h_deriv = 1e-2  # 中央差分步长 (°F)
            for _ in range(50):
                w, _ = _calc_behr_water_content_lb_per_mmscf(
                    T, pressure_psia, co2_mol_pct, h2s_mol_pct,
                )
                w_plus, _ = _calc_behr_water_content_lb_per_mmscf(
                    T + h_deriv, pressure_psia, co2_mol_pct, h2s_mol_pct,
                )
                w_minus, _ = _calc_behr_water_content_lb_per_mmscf(
                    T - h_deriv, pressure_psia, co2_mol_pct, h2s_mol_pct,
                )
                dw_dT = (w_plus - w_minus) / (2.0 * h_deriv)
                if abs(dw_dT) < 1e-10:
                    break
                delta = (w - target_w_lb_per_mmscf) / dw_dT
                T -= delta
                if abs(delta) < _BEHR_DEWPOINT_EXTRAPOLATION_WARNING_TOL_F:
                    break
            dewpoint_f = T
        except Exception:
            return _DewpointResult(
                dewpoint_f=None,
                extrapolated=False,
                reason="brentq and Newton both failed",
            )

    if (
        dewpoint_f is not None
        and dewpoint_f < _BEHR_DEWPOINT_EXTRAPOLATED_THRESHOLD_F
    ):
        return _DewpointResult(
            dewpoint_f=dewpoint_f,
            extrapolated=True,
            reason=(
                f"T<{_BEHR_DEWPOINT_EXTRAPOLATED_THRESHOLD_F:.0f}°F "
                f"extrapolation (T={dewpoint_f:.1f}°F), accuracy ±20%"
            ),
        )
    return _DewpointResult(dewpoint_f=dewpoint_f, extrapolated=False, reason=None)


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


def _calc_reboiler_duty_simple_btu_hr(
    glycol_circulation_rate_gpm: float,
    lean_glycol_concentration: float | None,
    inlet_w_lb_per_mmscf: float,
    outlet_w_lb_per_mmscf: float,
    gas_flow_mmscfd: float,
) -> float:
    """Reboiler duty 简式焓平衡 3 项 (GPSA §20.4)。

    Q_reboiler = m_TEG·Cp_TEG·ΔT + m_H2O·Cp_H2O·ΔT + m_H2O·ΔH_vap

    m_TEG = circulation_gpm × 1440 min/d × TEG_density [lb/d]
    m_H2O = (W_in - W_out) × Q_gas [lb/d]
    总能量 = 各分量 [BTU/day] → 转换 [BTU/hr] by / 24

    P6-8 T1 rename: 原名 _calc_reboiler_duty_btu_hr 被独立 ReboilerStripping 服务占用
    （OPEN-P6-6A-6 子任务 1），简式版仅在 calc_glycol_dehydration 内调用，无外部依赖。
    """
    m_teg_lb_d = glycol_circulation_rate_gpm * 1440.0 * _TEG_DENSITY_LB_PER_GAL
    m_water_lb_d = (
        (inlet_w_lb_per_mmscf - outlet_w_lb_per_mmscf) * gas_flow_mmscfd
    )
    q_teg_btu_d = m_teg_lb_d * _REBOILER_CP_TEG_BTU_PER_LB_F * _REBOILER_DT_F
    q_water_sensible_btu_d = (
        m_water_lb_d * _REBOILER_CP_WATER_BTU_PER_LB_F * _REBOILER_DT_F
    )
    q_water_vap_btu_d = m_water_lb_d * _REBOILER_DH_VAP_BTU_PER_LB
    return (q_teg_btu_d + q_water_sensible_btu_d + q_water_vap_btu_d) / 24.0


def _calc_stripping_gas_rate_scf_per_gal_teg(
    temperature_f: float,
    pressure_psia: float,
    lean_glycol_concentration: float | None,
) -> float:
    """Stripping gas rate (GPSA §20.4 Eq.20-5 simplified)。

    简式：
        SGR = k_strip × (P_sat_TEG / P_total) × (1 - X_lean) / X_lean

    注：占位实现，使用 _STRIPPING_K_DEFAULT；P6-6B 接管真 P_sat_TEG（Antoine 方程）。

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

    # 7.8 stripping gas rate (v5 with acid gas input)
    stripping_gas_scf_per_gal_teg: float | None = None
    if inp.temperature_f is not None and inp.pressure_psia is not None:
        stripping_gas_scf_per_gal_teg = _calc_stripping_gas_rate_scf_per_gal_teg(
            inp.temperature_f,
            inp.pressure_psia,
            inp.lean_glycol_concentration,
        )

    # 7.9 reboiler duty
    reboiler_duty_btu_hr = _calc_reboiler_duty_simple_btu_hr(
        inp.glycol_circulation_rate_gpm,
        inp.lean_glycol_concentration,
        inp.inlet_water_content_lb_per_mmscf,
        inp.outlet_water_content_lb_per_mmscf,
        inp.gas_flow_mmscfd,
    )

    # 7.10 v5.1: 纯逻辑判断 (H-3 落实 — 删 v4 Step 7.9 冗余调用)
    acid_gas_corrected: bool = (
        inp.co2_mol_pct > 0.0
    ) or (
        inp.h2s_mol_pct > 0.0
    )

    # ========== P6-8 T5 — OPEN-P6-6A-6 集成（4 子模块 outputs + WARNING） ==========

    # 7.11 T1 Reboiler Duty + Stripping Gas Rate（OPEN-P6-6A-6 子任务 1+2）
    # 完整焓平衡 +10% 设计裕度 + Antoine v5 plan + WARNING 透出
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
    # T1 完整焓平衡覆盖 v5.1 简式版（OPEN-P6-6A-6 工艺 2026-11-15 前未对账）
    reboiler_duty_btu_hr = reb_strip_result.q_total_btu_hr
    reboiler_duty_kw_t5 = reb_strip_result.q_total_btu_hr * 0.000293071
    stripping_gas_rate_scf_gal_t5 = reb_strip_result.sgr_scf_gal_teg
    warnings_t5: list[str] = list(reb_strip_result.warnings)

    # 7.12 T4 Lean Glycol Concentration（OPEN-P6-6A-6 子任务 4）
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


# =============================================================================
# P6-8 T1 — Reboiler Duty + Stripping Gas Rate 独立服务路径
# (OPEN-P6-6A-6 子任务 1+2)
#
# 与上面 calc_glycol_dehydration 内嵌的 _calc_reboiler_duty_simple_btu_hr 不同：
#   * 完整焓平衡 Q_total = Q_evap + Q_cond + Q_TEG (+10% 设计裕度)
#   * GPSA §20.4 Eq.20-5 + v5 plan Antoine (A=15.30 / B=8500) 真 P_sat_TEG
#   * WARNING 字段透出：TEG 循环量待对账
#
# 这是 Path A1A1 决议（OPEN-P6-6A-6 工艺 2026-11-15 前未对账）的 standalone 服务，
# 不在 calc_glycol_dehydration 内调用，避免污染 v5.1 主路径。
# =============================================================================


class ReboilerStrippingInput(BaseModel):
    """Reboiler Duty + Stripping Gas Rate 输入（OPEN-P6-6A-6 子任务 1+2）。

    与 GlycolDehydrationInput 解耦：直接以水脱除量 (lb H2O/hr) 与 TEG 循环量
    (gal TEG / lb H2O) 为入口，不绑定气体流量 / 入口水含量 / 塔盘数。
    """

    model_config = ConfigDict(frozen=False, extra="forbid")

    # 水脱除（默认值 = XLS PR-018 E80 基准 2377 lb/hr；stripping-gas-only 算例可省略）
    water_removal_rate_lb_hr: float = Field(default=2377.0, gt=0)
    # TEG 循环
    teg_circulation_rate_gal_lb: float = Field(default=3.0, gt=0)
    teg_density_lb_gal: float = Field(default=9.32, gt=0)
    # 操作条件
    reboiler_temperature_f: float = Field(default=400.0, ge=300.0, le=450.0)
    contactor_temperature_f: float = Field(default=120.0, ge=60.0, le=300.0)
    contactor_pressure_psia: float = Field(default=1000.0, ge=100.0, le=3000.0)
    # 回流比（GPSA 推荐 0.20–0.35）
    reflux_ratio: float = Field(default=0.25, ge=0.0, le=1.0)
    # 贫甘醇浓度（质量分率；XLS E29 default 0.9938；98–100 wt% TEG）
    lean_glycol_concentration_wt_pct: float = Field(default=0.9938, gt=0.0, le=1.0)


@dataclass(frozen=True)
class ReboilerStrippingResult:
    """Reboiler Duty + Stripping Gas Rate 输出（OPEN-P6-6A-6）。

    WARNING 字段（OPEN-P6-6A-6 工艺 2026-11-15 前未对账）：
      * te_circulation_rate_unverified: bool  — 标记 TEG 循环量未对账
      * warnings: list[str]                   — 透出的人类可读 warning 列表
    """

    # Reboiler Duty（BTU/hr）
    q_evap_btu_hr: float
    q_cond_btu_hr: float
    q_teg_btu_hr: float
    q_total_btu_hr: float
    # Stripping Gas Rate
    p_sat_te_mmhg: float
    sgr_scf_gal_teg: float
    # 公式溯源
    formula_ref: dict[str, str]
    # WARNING 字段（OPEN-P6-6A-6 工艺 2026-11-15 前未对账）
    te_circulation_rate_unverified: bool
    warnings: list[str] = field(default_factory=list)


def _calc_reboiler_duty_btu_hr(
    water_removal_rate_lb_hr: float,
    teg_circulation_rate_gal_lb: float,
    teg_density_lb_gal: float,
    reboiler_temperature_f: float,
    contactor_temperature_f: float,
    reflux_ratio: float,
) -> tuple[float, float, float, float, bool, list[str]]:
    """完整焓平衡 Reboiler Duty 计算（OPEN-P6-6A-6 子任务 1）。

    Q_total = (Q_evap + Q_cond + Q_TEG) × 1.10   (+10% 设计裕度)

    Q_evap  = m_H2O × (Cp_H2O · ΔT + ΔH_vap_H2O)
        Cp_H2O   = 1.00 BTU/(lb·°F)
        ΔH_vap   = 826 BTU/lb @ 400°F (steam tables)
        ΔT       = reboiler_T - contactor_T
    Q_cond  = reflux_ratio × Q_evap
    Q_TEG   = m_TEG × Cp_TEG × ΔT
        Cp_TEG   = 0.57 BTU/(lb·°F) @ 98–100 wt%
        m_TEG    = water_removal × teg_circulation × teg_density

    Returns:
        (q_evap, q_cond, q_teg, q_total, te_circulation_unverified, warnings)
    """
    warnings: list[str] = []

    # Q_evap
    cp_h2o = 1.00  # BTU/(lb·°F)
    delta_h_h2o = 826.0  # BTU/lb @ 400°F (steam tables)
    delta_t = reboiler_temperature_f - contactor_temperature_f
    q_evap = water_removal_rate_lb_hr * (cp_h2o * delta_t + delta_h_h2o)

    # Q_cond
    q_cond = reflux_ratio * q_evap

    # Q_TEG
    cp_teg = 0.57  # BTU/(lb·°F) @ 98–100 wt%
    m_teg = water_removal_rate_lb_hr * teg_circulation_rate_gal_lb * teg_density_lb_gal
    q_teg = m_teg * cp_teg * delta_t

    # Q_total 含 +10% 设计裕度
    q_total = (q_evap + q_cond + q_teg) * 1.10

    # WARNING：TEG 循环量未对账（OPEN-P6-6A-6 工艺 2026-11-15）
    te_circulation_unverified = bool(teg_circulation_rate_gal_lb == 3.0)
    if te_circulation_unverified:
        warnings.append(
            "TEG_CIRCULATION_RATE_UNVERIFIED: "
            "default 3.0 gal/lb 与 XLS 实际值可能不同"
            "（工艺室 2026-11-15 对账）"
        )

    return (
        q_evap,
        q_cond,
        q_teg,
        q_total,
        te_circulation_unverified,
        warnings,
    )


def _calc_stripping_gas_rate_scf_gal_teg(
    reboiler_temperature_f: float,
    contactor_temperature_f: float,
    contactor_pressure_psia: float,
    lean_glycol_concentration_wt_pct: float,
) -> tuple[float, float]:
    """Stripping Gas Rate 计算（OPEN-P6-6A-6 子任务 2, F2 P6-9-PICKUP-2 patch）。

    GPSA §20.4 Eq.20-5 简式（工艺室 2026-10-31 复盘后确认）：
        SGR = k_strip × (P_sat,TEG / P_total) × (1 - X) / X
            k_strip ≈ 6.5（经验常数）
            P_sat,TEG via Antoine 简式（v5 plan 原值 A=15.30 / B=8500）：
                log10(P_mmHg) = A − B / T_K
            X = 贫甘醇质量分率

    ⚠️ F2 patch (2026-10-31): 修复前公式 `k×(P_total/P_sat)×X/(1−X)` 比例项
    和 X-fraction 项双双反向，残差 4e12% vs XLS。修复后形式与 GPSA §20.4 Eq.20-5
    标准形式一致（OPEN-P6-9-PICKUP-2-1 工艺室复盘跟踪）。

    注：函数名 `_scf_gal_teg`（无 `per_`）区别于 calc_glycol_dehydration 内
    占位版 _calc_stripping_gas_rate_scf_per_gal_teg（用 P6-6B 占位 P_sat）。
    """
    k_strip = 6.5
    a_te = 15.30  # Antoine A (log10 P_mmHg = A - B/T_K), v5 plan 原值
    b_te = 8500.0  # Antoine B, v5 plan 原值

    # T_K 转换：°F → K
    t_k = (reboiler_temperature_f - 32.0) * 5.0 / 9.0 + 273.15

    # log10(P_sat,TEG [mmHg]) = A − B/T_K
    log10_p_sat_mmhg = a_te - b_te / t_k
    p_sat_te_mmhg = 10.0 ** log10_p_sat_mmhg

    # SGR = k_strip × (P_sat / P_total) × (1 - X) / X（GPSA §20.4 Eq.20-5）
    # P_total 单位转换：psi → mmHg (1 psi = 51.7149 mmHg)
    p_total_mmhg = contactor_pressure_psia * 51.7149
    x_frac = lean_glycol_concentration_wt_pct  # 已是质量分率 (0..1)
    sgr = k_strip * (p_sat_te_mmhg / p_total_mmhg) * (1.0 - x_frac) / x_frac

    return p_sat_te_mmhg, sgr


@dataclass(frozen=True)
class LeanGlycolDataPoint:
    """GPSA Fig 20-4 数据点（再沸器温度 + 汽提气速率 → 贫 TEG 浓度）。"""

    reboiler_temperature_f: float
    stripping_gas_scf_gal: float
    lean_glycol_concentration_wt_pct: float


# GPSA Fig 20-4 数据点（工艺室 2026-10-31 抄录 4 数据点；完整曲线待 2026-11-15）
_GPSA_FIG_20_4_DATA_POINTS: tuple[LeanGlycolDataPoint, ...] = (
    # (T_reboiler_F, SGR_scf_gal, lean_glycol_wt_pct)
    LeanGlycolDataPoint(380.0, 0.0, 98.8),
    LeanGlycolDataPoint(400.0, 0.0, 99.3),
    LeanGlycolDataPoint(400.0, 3.0, 99.7),
    LeanGlycolDataPoint(400.0, 6.0, 99.9),
)


def _calc_lean_glycol_concentration_wt_pct(
    reboiler_temperature_f: float,
    stripping_gas_scf_gal: float,
) -> tuple[float, list[str]]:
    """贫 TEG 浓度（GPSA Fig 20-4 数据点 + 插值, OPEN-P6-6A-6 子任务 4）。

    T_reboiler 维度：双线性插值（先 T 后 SGR）
    T=400°F 段用 SGR 线性插值；T≠400°F 用 T=380/400 两段线性

    Returns:
        (lean_glycol_concentration_wt_pct, warnings)
    """
    warnings: list[str] = []

    # 按 T 分组
    if reboiler_temperature_f <= 380.0:
        # T=380°F 段：仅 SGR=0 数据点
        return _GPSA_FIG_20_4_DATA_POINTS[0].lean_glycol_concentration_wt_pct, warnings
    elif reboiler_temperature_f >= 400.0:
        # T=400°F 段：SGR 线性插值（3 个数据点）
        T = 400.0
        points = [p for p in _GPSA_FIG_20_4_DATA_POINTS if p.reboiler_temperature_f == T]
        if stripping_gas_scf_gal <= points[0].stripping_gas_scf_gal:
            return points[0].lean_glycol_concentration_wt_pct, warnings
        elif stripping_gas_scf_gal >= points[-1].stripping_gas_scf_gal:
            return points[-1].lean_glycol_concentration_wt_pct, warnings
        # 线性插值
        for i in range(len(points) - 1):
            x1 = points[i].stripping_gas_scf_gal
            y1 = points[i].lean_glycol_concentration_wt_pct
            x2 = points[i + 1].stripping_gas_scf_gal
            y2 = points[i + 1].lean_glycol_concentration_wt_pct
            if x1 <= stripping_gas_scf_gal <= x2:
                lean_glycol = y1 + (stripping_gas_scf_gal - x1) * (y2 - y1) / (x2 - x1)
                return lean_glycol, warnings
    else:
        # T=380~400°F 段：T 线性插值（仅 SGR=0 数据点可用）
        # 注：完整 Fig 20-4 曲线待工艺室 2026-11-15 抄录
        T = reboiler_temperature_f
        # 双线性插值（sgr=0 段）
        lean_at_380 = _GPSA_FIG_20_4_DATA_POINTS[0].lean_glycol_concentration_wt_pct  # 98.8
        lean_at_400 = _GPSA_FIG_20_4_DATA_POINTS[1].lean_glycol_concentration_wt_pct  # 99.3
        lean_glycol = lean_at_380 + (T - 380.0) * (lean_at_400 - lean_at_380) / (400.0 - 380.0)
        warnings.append(
            "LEAN_GLYCOL_INTERPOLATION_PARTIAL: "
            "仅 380/400°F 两数据点线性插值；完整 Fig 20-4 待工艺室 2026-11-15 抄录"
        )
        return lean_glycol, warnings


def calc_reboiler_stripping(inp: ReboilerStrippingInput) -> ReboilerStrippingResult:
    """Reboiler Duty + Stripping Gas Rate 主入口（OPEN-P6-6A-6 子任务 1+2）。

    Path A1A1 决议（工艺 2026-11-15 前未对账）：
      * 完整焓平衡 +10% 设计裕度
      * WARNING 字段透出：TEG_CIRCULATION_RATE_UNVERIFIED
      * Antoine v5 plan 原值 A=15.30 / B=8500
    """
    q_evap, q_cond, q_teg, q_total, te_circ_unverif, warnings = (
        _calc_reboiler_duty_btu_hr(
            inp.water_removal_rate_lb_hr,
            inp.teg_circulation_rate_gal_lb,
            inp.teg_density_lb_gal,
            inp.reboiler_temperature_f,
            inp.contactor_temperature_f,
            inp.reflux_ratio,
        )
    )

    p_sat, sgr = _calc_stripping_gas_rate_scf_gal_teg(
        inp.reboiler_temperature_f,
        inp.contactor_temperature_f,
        inp.contactor_pressure_psia,
        inp.lean_glycol_concentration_wt_pct,
    )

    return ReboilerStrippingResult(
        q_evap_btu_hr=q_evap,
        q_cond_btu_hr=q_cond,
        q_teg_btu_hr=q_teg,
        q_total_btu_hr=q_total,
        p_sat_te_mmhg=p_sat,
        sgr_scf_gal_teg=sgr,
        formula_ref={
            "reboiler": (
                "Q_total = (Q_evap + Q_cond + Q_TEG) × 1.10 "
                "(+10% 设计裕度; GPSA §20.4)"
            ),
            "stripping": (
                "SGR = k_strip × (P_sat,TEG/P_total) × (1-X)/X "
                "[GPSA §20.4 Eq.20-5; P_sat via Antoine v5 plan A=15.30/B=8500]"
            ),
        },
        te_circulation_rate_unverified=te_circ_unverif,
        warnings=warnings,
    )


# P6-6A-6 v5.1 Ruling 9: _calc_* helpers / _DewpointResult 私有化，不入 __all__
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
