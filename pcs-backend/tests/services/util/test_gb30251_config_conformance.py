"""GB 30251-2024 附录A 表A.1 折标系数一致性回归 (2026-10-05).

锁定三处修正 + 8 行新增, 防止回退:

- bug-136 除盐水 / 凝汽机凝结水 1.04 → 1.0 (附录A 序号25/28)
- bug-135 LOW_TEMP_HEAT 0.0341 硬编码 → CONFIG 0.012 (附录A 序号34)
  + 删硬编码 fallback 改 fail-closed
- LPG / 其余 5 项按吨计燃料按标准补齐 (附录A 序号3/4/5/9/10/11)

同时锁定 seed 与标准的一致性: 直接跑审计脚本的 GB 表比对全部行。
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_BACKEND))
sys.path.insert(0, str(_BACKEND / "scripts"))

from p7_open_009_t0_seed_energy_conversion_factors import (  # noqa: E402
    R1_SIGNED_ENERGY_CONVERSION,
)
from p7_open_016_config_conformance_audit import (  # noqa: E402
    COAL_TOLERANCE_PCT,
    GB30251_A1,
    TOLERANCE_PCT,
    _key,
    audit_low_temp_heat_fallback,
)


def _pcs_rows() -> dict[tuple, dict]:
    return {_key(r): r for r in R1_SIGNED_ENERGY_CONVERSION}


# ---------------------------------------------------------------------------
# 1. 全表一致性: 每一行 PCS 系数都对得上标准, 且没有多余/缺失的行
# ---------------------------------------------------------------------------


def test_every_pcs_row_matches_standard_within_tolerance():
    """PCS 每一行 toe_factor 都在标准容差内."""
    violations = []
    for row in R1_SIGNED_ENERGY_CONVERSION:
        std = GB30251_A1.get(_key(row))
        assert std is not None, f"PCS 行在标准表无对应: {_key(row)}"
        _seq, _name, _unit, std_kgoe, _mj = std
        pct = abs(row["toe_factor"] - std_kgoe) / std_kgoe * 100.0
        if pct > TOLERANCE_PCT:
            violations.append(
                f"{_key(row)}: PCS={row['toe_factor']} 标准={std_kgoe} 偏差 {pct:.2f}%"
            )
    assert not violations, "折标系数偏离 GB 30251-2024 附录A:\n" + "\n".join(
        violations
    )


def test_no_extra_rows_beyond_standard():
    """PCS 不得有标准之外的系数行 (防止臆造)."""
    extra = set(_pcs_rows()) - set(GB30251_A1)
    assert not extra, f"PCS 有标准未收录的系数行: {extra}"


def test_all_comparable_standard_rows_modelled():
    """标准里每个可比对的行 PCS 都建模了 (35 数据行 - 序号1/2 换算基准 = 33)."""
    missing = set(GB30251_A1) - set(_pcs_rows())
    assert not missing, f"标准有而 PCS 未建模: {missing}"
    assert len(GB30251_A1) == 33


def test_standard_coal_factor_consistent_with_toe():
    """标煤系数 == toe × 1.4286 (PCS 派生列, 按其记录精度判)."""
    bad = [
        _key(r)
        for r in R1_SIGNED_ENERGY_CONVERSION
        if abs(r["standard_coal_factor"] - r["toe_factor"] * 1.4286)
        / (r["toe_factor"] * 1.4286)
        * 100
        > COAL_TOLERANCE_PCT
    ]
    assert not bad, f"标煤换算不自洽: {bad}"


# ---------------------------------------------------------------------------
# 2. bug-136: 两行水系数回归防护
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("water_type", "std_seq", "std_value"),
    [
        ("DEMINERALIZED_WATER", 25, 1.0),
        ("TURBINE_CONDENSATE", 28, 1.0),
    ],
)
def test_water_coefficients_match_standard(water_type, std_seq, std_value):
    row = _pcs_rows()[("WATER", None, None, water_type, None)]
    assert row["toe_factor"] == std_value
    assert GB30251_A1[("WATER", None, None, water_type, None)][0] == std_seq


# ---------------------------------------------------------------------------
# 3. bug-135: LOW_TEMP_HEAT
# ---------------------------------------------------------------------------


def test_low_temp_heat_row_present_with_standard_value():
    row = _pcs_rows()[("LOW_TEMP_HEAT", None, None, None, None)]
    assert row["toe_factor"] == 0.012  # 附录A 序号34
    assert row["standard_coal_factor"] == pytest.approx(0.012 * 1.4286, abs=1e-6)


def test_service_has_no_hardcoded_low_temp_heat_fallback():
    """service 不得再出现 LOW_TEMP_HEAT 硬编码 fallback (量纲错 + 偏离 +184%)."""
    result = audit_low_temp_heat_fallback()
    assert result["status"] == "OK", result


# ---------------------------------------------------------------------------
# 4. LPG 与按吨计燃料: 归 FUEL 而非 FUEL_GAS (防 Nm³ × 1200 地雷)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sub_type", "std_seq", "std_value"),
    [
        ("FUEL_OIL", 3, 1000.0),
        ("LPG", 4, 1200.0),
        ("METHANE_H2", 5, 1200.0),
        ("PSA_OFF_GAS", 9, 320.0),
        ("CATALYTIC_COKE", 10, 950.0),
        ("PETROLEUM_COKE", 11, 800.0),
    ],
)
def test_mass_fuels_present_under_fuel_energy_type(
    sub_type, std_seq, std_value
):
    """按吨计的燃料必须在 FUEL 下, 且值与标准一致.

    放 FUEL_GAS 下会被 _compute_totals 当 Nm³ 乘 → Nm³ × 1200 荒谬值。
    """
    assert ("FUEL", sub_type, None, None, None) in _pcs_rows()
    assert ("FUEL_GAS", sub_type, None, None, None) not in _pcs_rows()
    row = _pcs_rows()[("FUEL", sub_type, None, None, None)]
    assert row["toe_factor"] == std_value
    assert GB30251_A1[("FUEL", sub_type, None, None, None)][0] == std_seq


def test_lpg_gap_closed():
    """bug: UtilityFuelGas.fuel_type 有 LPG 但 CONFIG 无系数 → 静默落到气田气 0.85."""
    assert _pcs_rows()[("FUEL", "LPG", None, None, None)]["toe_factor"] == 1200.0
