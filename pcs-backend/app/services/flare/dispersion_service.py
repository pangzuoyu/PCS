"""C-22 FLARE 扩散计算（API 521 §5.15 + Pasquill-Gifford + 辐射热强度）。

按 SPEC §3.10.2 V1.5：
- Pasquill-Gifford 6 类稳定度（A-F；Briggs 1973 公式）
- 中心线浓度：点源高斯 C(x,0,0) = Q/(π·σ_y·σ_z·u)·exp(-H²/(2σ_z²))（M-3 v2：含地面反射，π 而非 2π）
- API 521 §5.15 辐射热强度：q = χ·ΔH_comb/(4π·r²)
- 致死/致伤距离：二分查找（简化 r = sqrt(Q_comb/(4π·threshold)))

Global Constraints:
- M-1 v2 BLOCKER: imperial_units 豁免 — FLARE 物理量仅 SI
- C-12 frozen contract — 不调用 vessel_service
- PasquillClass ∈ {"A","B","C","D","E","F"}（F2 boundary）
- wind_speed_m_s > 0（F5 extreme values）
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Final, Literal

from app.services._compound_config_cache import (
    get_api521_thresholds_table,
    get_pasquill_sigma_table,
)
from app.services.exceptions import PcsError

PasquillClass = Literal["A", "B", "C", "D", "E", "F"]

# 内联常量：fallback（DB 不可达 / 表空时使用）。
_BRIGGS_SIGMA: Final[dict[str, tuple[float, float, float, float]]] = {
    "A": (0.22, 0.0001, 0.20, 0.0),
    "B": (0.16, 0.0001, 0.12, 0.0),
    "C": (0.11, 0.0001, 0.08, 0.0002),
    "D": (0.08, 0.0001, 0.06, 0.0015),
    "E": (0.06, 0.0001, 0.03, 0.0003),
    "F": (0.04, 0.0001, 0.016, 0.0003),
}

_HEAT_OF_COMBUSTION_MJ_PER_KG: Final[float] = 50.0

_INJURY_THRESHOLD_KW_M2: Final[float] = 4.7
_LETHALITY_THRESHOLD_KW_M2: Final[float] = 12.6


def _resolve_pasquill_sigma() -> dict[str, tuple[float, float, float, float]]:
    """5 min TTL 缓存加载 Briggs 1973 系数；DB 不可达时 fallback 到内联常量。

    返回字典（DB 命中 → DB 数据；DB 失败 → _BRIGGS_SIGMA）。
    """
    db_table = get_pasquill_sigma_table()
    return db_table if db_table else _BRIGGS_SIGMA


def _resolve_api521_thresholds() -> tuple[float, float]:
    """5 min TTL 缓存加载 API 521 §5.15 阈值；DB 不可达时 fallback 到内联常量。

    返回 ``(injury_kw_m2, lethality_kw_m2)`` 元组。
    """
    db_table = get_api521_thresholds_table()
    if db_table and "INJURY" in db_table and "LETHALITY" in db_table:
        return db_table["INJURY"], db_table["LETHALITY"]
    return _INJURY_THRESHOLD_KW_M2, _LETHALITY_THRESHOLD_KW_M2


class DispersionInputError(PcsError):
    code = "DISPERSION_INPUT_ERROR"
    status = 422


@dataclass(frozen=True)
class DispersionInput:
    gas_release_rate_kg_s: float
    molecular_weight_kg_kmol: float
    release_height_m: float
    wind_speed_m_s: float
    pasquill_stability_class: PasquillClass
    ambient_temperature_k: float
    downwind_distance_m: float


@dataclass(frozen=True)
class DispersionResult:
    centerline_conc_mol_m3: float
    sigma_y_m: float
    sigma_z_m: float
    heat_intensity_kw_m2: float
    r_injury_m: float
    r_lethality_m: float
    pasquill_stability_used: str
    formula_ref: dict[str, str]


def _validate_input(inp: DispersionInput) -> None:
    if inp.gas_release_rate_kg_s <= 0:
        raise DispersionInputError(f"Q={inp.gas_release_rate_kg_s} 必须 > 0")
    if inp.molecular_weight_kg_kmol <= 0:
        raise DispersionInputError(f"MW={inp.molecular_weight_kg_kmol} 必须 > 0")
    if inp.release_height_m < 0:
        raise DispersionInputError(f"H={inp.release_height_m} 必须 ≥ 0")
    if inp.wind_speed_m_s <= 0:
        raise DispersionInputError(f"u={inp.wind_speed_m_s} 必须 > 0")
    if inp.pasquill_stability_class not in _BRIGGS_SIGMA:
        raise DispersionInputError(
            f"稳定度 {inp.pasquill_stability_class} 必须 ∈ A/B/C/D/E/F"
        )
    if inp.ambient_temperature_k <= 0:
        raise DispersionInputError(f"T={inp.ambient_temperature_k} 必须 > 0 K")
    if inp.downwind_distance_m <= 0:
        raise DispersionInputError(f"x={inp.downwind_distance_m} 必须 > 0")


def _sigma_briggs(x: float, alpha: float, beta: float) -> float:
    return alpha * x * math.sqrt(1.0 / (1.0 + beta * x))


def _solve_distance_for_flux(Q_comb_w: float, threshold_w_m2: float) -> float:
    if Q_comb_w <= 0:
        return 0.0
    return math.sqrt(Q_comb_w / (4.0 * math.pi * threshold_w_m2))


def calc_dispersion(inp: DispersionInput) -> DispersionResult:
    """Pasquill-Gifford 高斯点源扩散 + API 521 辐射热强度 + 致死/致伤距离。

    Args:
        inp: DispersionInput（含 Q/MW/H/u/稳定度/T/x）。

    Returns:
        DispersionResult（含 centerline_conc / sigma_y/z / heat_intensity /
        r_injury / r_lethality / pasquill_stability_used / formula_ref）。

    Raises:
        DispersionInputError: 输入字段越界或非正（422）。
    """
    _validate_input(inp)

    Q_mol_s = inp.gas_release_rate_kg_s / inp.molecular_weight_kg_kmol * 1000.0
    x = inp.downwind_distance_m
    H = inp.release_height_m
    u = inp.wind_speed_m_s
    # C5: 5 min TTL cache 加载；DB 失败 fallback 到内联 _BRIGGS_SIGMA
    pasquill_table = _resolve_pasquill_sigma()
    a_y, b_y, a_z, b_z = pasquill_table[inp.pasquill_stability_class]

    sigma_y = _sigma_briggs(x, a_y, b_y)
    sigma_z = _sigma_briggs(x, a_z, b_z)
    # M-3 v2 含地面反射：Q/(π·σy·σz·u)（源+镜像=2 倍 → π 而非 2π）
    conc = Q_mol_s / (math.pi * sigma_y * sigma_z * u) * math.exp(
        -H * H / (2.0 * sigma_z * sigma_z)
    )

    r_ref = inp.downwind_distance_m
    Q_comb_w = inp.gas_release_rate_kg_s * _HEAT_OF_COMBUSTION_MJ_PER_KG * 1.0e6
    q_ref = Q_comb_w / (4.0 * math.pi * r_ref * r_ref) / 1000.0  # kW/m²

    # C5: 5 min TTL cache 加载 API 521 §5.15 阈值
    injury_kw_m2, lethality_kw_m2 = _resolve_api521_thresholds()
    r_injury = _solve_distance_for_flux(Q_comb_w, injury_kw_m2 * 1000.0)
    r_lethality = _solve_distance_for_flux(Q_comb_w, lethality_kw_m2 * 1000.0)

    return DispersionResult(
        centerline_conc_mol_m3=conc,
        sigma_y_m=sigma_y,
        sigma_z_m=sigma_z,
        heat_intensity_kw_m2=q_ref,
        r_injury_m=r_injury,
        r_lethality_m=r_lethality,
        pasquill_stability_used=inp.pasquill_stability_class,
        formula_ref={
            "concentration": "API 521 §5.15 / Briggs 1973 (point source Gaussian, 含地面反射)",
            "sigma": "Briggs 1973 Pasquill-Gifford σ_y/z",
            "radiation": "API 521 §5.15 点源辐射模型 q = Q_comb/(4π·r²)",
            "injury_threshold": (
                f"API 521 §5.15 Table 5-15 ({injury_kw_m2} kW/m²; C5: CONFIG 表优先)"
            ),
            "lethality_threshold": (
                f"API 521 §5.15 Table 5-15 ({lethality_kw_m2} kW/m²; C5: CONFIG 表优先)"
            ),
        },
    )


__all__ = [
    "PasquillClass",
    "DispersionInput",
    "DispersionInputError",
    "DispersionResult",
    "calc_dispersion",
]