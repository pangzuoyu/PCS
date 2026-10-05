"""耗能工质 MJ 从 CONFIG 推导 (Q2, 用户裁决 2026-10-05).

背景: `_compute_totals` 硬编码 `T_WATER_TO_MJ = 0.0` / `NM3_GAS_TO_MJ = 0.0`,
水与工艺气体的 MJ 恒为 0, 与 GB 30251-2024 附录A 表A.1 不符 —— 附录A 对每种
耗能工质都给了 MJ 值 (循环水 2.51 MJ/t、氮气 6.28 MJ/m³、净化空气 1.59 MJ/m³…)。

**不需要新增 `unit_to_mj` 列**: 附录A 的 MJ 列全部 = kg标油 × 41.868:
    循环水 0.06 × 41.868 = 2.512 (标准 2.51)
    除盐水 1.0  × 41.868 = 41.87 (标准 41.87)
    氮气   0.15 × 41.868 = 6.28  (标准 6.28)
    低温热 0.012 × 41.868 = 0.502 (标准 0.5)
与蒸汽/燃料气已有的 `toe_factor × TOE_TO_MJ` 推导同源, 存一列纯冗余。
"""

from __future__ import annotations

import pytest

from app.services.util.utility_energy_summary_service import (
    EnergyAggregation,
    _compute_totals,
)

# GB 30251-2024 附录A 表A.1 折标系数 (kg标油/单位)
GB_WATER = {
    "FRESH_WATER": (0.15, 0.214),
    "CIRCULATING_WATER": (0.06, 0.086),
    "DEMINERALIZED_WATER": (1.0, 1.428571),
    "LP_DEAERATED_WATER": (6.5, 9.285714),
}
TOE_TO_MJ = 41.868


def _factors() -> dict:
    """单值 factors dict (shape = (toe, coal))."""
    return {
        "ELECTRICITY": (0.21, 0.30),
        "FUEL_GAS": (0.85, 1.214),
        "STEAM": (76.0, 108.6),
        "WATER": (0.06, 0.086),
        "GAS": (0.85, 1.2143),
        "LOW_TEMP_HEAT": (0.0, 0.0),
    }


def _by_class() -> dict:
    return {
        "WATER": GB_WATER,
        "FUEL_GAS": {"GASFIELD_GAS": (0.85, 1.214)},
        "STEAM": {"0_8_TO_1_2_MPA": (76.0, 108.6)},
    }


def _agg(**kw) -> EnergyAggregation:
    base = dict(
        electricity_kwh_yr=0.0,
        fuel_gas_nm3_yr=0.0,
        steam_t_yr=0.0,
        water_t_yr=0.0,
        gas_nm3_yr=0.0,
        low_temp_heat_gj_yr=0.0,
    )
    base.update(kw)
    return EnergyAggregation(**base)


# ---------------------------------------------------------------------------
# 水: MJ 必须按 water_type 分类从 CONFIG 推导, 不再恒 0
# ---------------------------------------------------------------------------


def test_water_mj_was_hardcoded_zero():
    """RED 的具体表现: 修正前水的 MJ 恒 0."""
    agg = _agg(water_t_yr=1000.0, water_by_type={"CIRCULATING_WATER": 1000.0})
    _toe, _coal, mj = _compute_totals(
        agg, _factors(), electricity_value_type="EQUIVALENT_VALUE",
        factors_by_class=_by_class(),
    )
    assert mj == pytest.approx(1000.0 * 0.06 * TOE_TO_MJ)  # 2512.08 MJ
    assert mj > 0.0


def test_water_mj_matches_gb30251_appendix_a():
    """1 t 循环水 → 附录A 表A.1 序号23 的 2.51 MJ/t (±0.5%)."""
    agg = _agg(water_t_yr=1.0, water_by_type={"CIRCULATING_WATER": 1.0})
    _toe, _coal, mj = _compute_totals(
        agg, _factors(), electricity_value_type="EQUIVALENT_VALUE",
        factors_by_class=_by_class(),
    )
    assert abs(mj - 2.51) / 2.51 * 100 < 0.5


def test_water_mj_sums_across_types():
    """多水类混合时 MJ 按类分别推导后求和."""
    agg = _agg(
        water_t_yr=300.0,
        water_by_type={"CIRCULATING_WATER": 200.0, "FRESH_WATER": 100.0},
    )
    _toe, _coal, mj = _compute_totals(
        agg, _factors(), electricity_value_type="EQUIVALENT_VALUE",
        factors_by_class=_by_class(),
    )
    expected = (200.0 * 0.06 + 100.0 * 0.15) * TOE_TO_MJ
    assert mj == pytest.approx(expected)


def test_water_mj_and_toe_stay_self_consistent():
    """MJ 与 toe 必须同源 (iso_self_consistent 诊断的成立条件)."""
    agg = _agg(
        electricity_kwh_yr=1000.0,
        water_t_yr=100.0,
        water_by_type={"CIRCULATING_WATER": 100.0},
    )
    toe, _coal, mj = _compute_totals(
        agg, _factors(), electricity_value_type="EQUIVALENT_VALUE",
        factors_by_class=_by_class(),
    )
    assert mj == pytest.approx(toe * 1000.0 * TOE_TO_MJ, rel=1e-9)


def test_water_mj_falls_back_to_single_value():
    """无 water_by_type 分类时用单值 fallback (R0 兼容路径)."""
    agg = _agg(water_t_yr=10.0)
    _toe, _coal, mj = _compute_totals(
        agg, _factors(), electricity_value_type="EQUIVALENT_VALUE",
        factors_by_class=_by_class(),
    )
    assert mj == pytest.approx(10.0 * 0.06 * TOE_TO_MJ)


# ---------------------------------------------------------------------------
# 工艺气体: MJ 从 CONFIG 的 GAS 行推导
# ---------------------------------------------------------------------------


def test_gas_mj_from_config():
    """工艺气体 MJ 不再恒 0."""
    agg = _agg(gas_nm3_yr=1000.0)
    _toe, _coal, mj = _compute_totals(
        agg, _factors(), electricity_value_type="EQUIVALENT_VALUE",
        factors_by_class=_by_class(),
    )
    assert mj == pytest.approx(1000.0 * 0.85 * TOE_TO_MJ)


def test_gas_mj_and_toe_stay_self_consistent():
    agg = _agg(gas_nm3_yr=500.0, electricity_kwh_yr=100.0)
    toe, _coal, mj = _compute_totals(
        agg, _factors(), electricity_value_type="EQUIVALENT_VALUE",
        factors_by_class=_by_class(),
    )
    assert mj == pytest.approx(toe * 1000.0 * TOE_TO_MJ, rel=1e-9)


def test_zero_consumption_yields_zero_mj():
    """无任何耗能工质数据时 MJ 仍为 0 (不得因新逻辑凭空产生)."""
    _toe, _coal, mj = _compute_totals(
        _agg(), _factors(), electricity_value_type="EQUIVALENT_VALUE",
        factors_by_class=_by_class(),
    )
    assert mj == 0.0
