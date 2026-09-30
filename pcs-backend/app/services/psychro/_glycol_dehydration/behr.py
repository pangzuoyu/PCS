"""Behr 含水量查表 + 双线性插值 + 酸气修正子模块（P6-8 T9r）。

P6-9-PICKUP-5 5C（REF-P6-8-2）自 ``glycol_dehydration_service.py`` 拆出。

本模块负责 W(T, P) 正函数方向：

  - ``BehrGrid`` / ``_load_behr_grids`` / ``_BEHR_GRIDS`` — v3 grid 查表（工艺室
    2026-09-29 交付；``pcs-backend/data/behr_coefficients.json``）
  - ``_bilinear_interp_behr`` — grid 双线性插值（越界 clamp + 标记）
  - ``_calc_behr_water_content_lb_per_mmscf`` — 高 T 段查表 + 低 T 段 Bukacek
    1990 延伸 + 酸气修正（W，lb water / MMscf dry gas）
  - ``_correct_behr_for_acid_gas`` — general baseline 线性酸气 placeholder

与 ``dewpoint``（反函数方向）、``reboilers``（再沸器 / 汽提气）**互不依赖**，
三者共同由 ``glycol_dehydration_service`` 单向引用（无循环依赖）。

Working fluid 边界（Ruling 9）：natural gas (sg 0.6)，**不**与
``calc_saturation_water_content``（humid air）互调。
"""
from __future__ import annotations

import bisect
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

# P6-8 T9r — Behr baseline 选择 (OPEN-P6-6A-9.5 代码侧闭环)
# general: v3 grid 默认, GPSA Fig 20-2 general zone (McKetta-Wehe sweet gas)
# high_acid: GPSA Fig 20-2 high-acid zone (H2S+CO2 >= 5 mol%), 工艺室 2026-09-29 v3 grid 交付
BehrBaseline = Literal["general", "high_acid"]

# P6-8 T9r — Grid 查表 + 双线性插值 (OPEN-P6-6A-9.5 闭环)
# 工艺室 2026-09-29 第三批交付 v3 (查表 + 双线性插值)
# 注：本模块位于 psychro/_glycol_dehydration/，故根目录上溯 4 级
# （glycol_dehydration_service.py 位于 psychro/ 时为 3 级）。
_BEHR_GRID_PATH: Final[Path] = (
    Path(__file__).resolve().parents[4] / "data" / "behr_coefficients.json"
)

# P6-6A-6 v5.1 — Bukacek 1990 T<60°F 延伸系数 (OPEN-P6-6A-9.4, 已闭环)
# 低温段 (T < 60°F) 用 Bukacek 1990 Table 3 延伸 (工艺室 2026-10-15 验证)。
# 边界 T = 60°F 用 grid high-temp (避免不连续 — brief §约束)。
_BEHR_MIX_LOW_T: Final[tuple[float, float, float, float]] = (
    2.1430, 0.01850, -0.000042, -0.9800,
)
_BEHR_T_BOUNDARY_F: Final[float] = 60.0

# P6-6A-6 v5.1 — Acid gas linear correction placeholder coefficients (H-1 落实)
_ACID_GAS_CO2_COEF: Final[float] = 0.024
_ACID_GAS_H2S_COEF: Final[float] = 0.018


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
