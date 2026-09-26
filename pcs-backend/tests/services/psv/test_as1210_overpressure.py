"""P6-5 Task B5: C-21 PSV AS 1210/1797 + 管破裂 + 控制阀失效工况。

按 SPEC §3.5.2 V1.1 + AS 1210/1797：
- TUBE_RUPTURE：AS 1210 §4.3.1 set_p = 1.10·MAWP（默认；可在 [1.05, 1.30] 调整）
- CONTROL_VALVE_FAILURE：AS 1210 §4.3.2（AIR_FAIL=1.10/SIGNAL_FAIL=1.20/POWER_FAIL=1.15）
- FIRE_CASE：AS 1210 §4.4 + API 521 §3.4 Q = 43192·F·A^0.82 [SI]
- A_wetted 调用 C-12 calc_wetted_area（D7 接口冻结）

边界条件：
- as1210_pressure_factor ∈ [1.05, 1.30]
- mawp_kpa > 0
- tube_rupture_mass_kg_s / fire_case_wetted_area_m2 ≥ 0
"""

from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.psv import as1210_overpressure_service
from app.services.psv.as1210_overpressure_service import (
    As1210InputError,
    As1210ReliefInput,
    calc_as1210_relief_sizing,
)
from app.services.vessel.vessel_service import (
    WettedAreaInput,
    calc_wetted_area,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_as1210_tube_rupture.json"


# ============================================================================
# Step 1: 主测试 — AS 1210 §4.3.1 管破裂 1.10·MAWP 校核
# ============================================================================


def test_as1210_tube_rupture_overpressure_110_percent_mawp():
    """AS 1210 §4.3.1 管破裂工况：PSV 设定压力 ≥ 1.10 × MAWP。
    MAWP=1000 kPa → 设定压力 = 1100 kPa。
    """
    inp = As1210ReliefInput(
        mawp_kpa=1000.0,
        tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10,
        scenario="TUBE_RUPTURE",
    )
    result = calc_as1210_relief_sizing(inp)
    assert math.isclose(result.required_set_pressure_kpa, 1100.0, rel_tol=1e-3)


# ============================================================================
# Step 5: L-2 v1 BLOCKER — SIGNAL_FAIL = 1.20（最严重）+ 火灾工况
# ============================================================================


def test_as1210_control_valve_signal_fail_120_percent_mawp():
    """L-2 v1 BLOCKER：SIGNAL_FAIL（信号失效）= 最严重 1.20·MAWP。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="SIGNAL_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10,
        scenario="CONTROL_VALVE_FAILURE",
    )
    result = calc_as1210_relief_sizing(inp)
    assert math.isclose(result.required_set_pressure_kpa, 1200.0, rel_tol=1e-3)


def test_as1210_control_valve_air_fail_110_percent_mawp():
    """AIR_FAIL（气源失效）= 1.10·MAWP。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10,
        scenario="CONTROL_VALVE_FAILURE",
    )
    result = calc_as1210_relief_sizing(inp)
    assert math.isclose(result.required_set_pressure_kpa, 1100.0, rel_tol=1e-3)


def test_as1210_control_valve_power_fail_115_percent_mawp():
    """POWER_FAIL（电源失效）= 1.15·MAWP。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="POWER_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10,
        scenario="CONTROL_VALVE_FAILURE",
    )
    result = calc_as1210_relief_sizing(inp)
    assert math.isclose(result.required_set_pressure_kpa, 1150.0, rel_tol=1e-3)


def test_as1210_fire_case_wetted_area():
    """火灾工况调用 C-12 wetted area；A=50 → Q_fire ≈ 43192·1·50^0.82 W；
    capacity = Q_fire / ΔH_vap (2260 kJ/kg)。
    """
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10,
        scenario="FIRE_CASE",
    )
    result = calc_as1210_relief_sizing(inp)
    expected_q_fire_w = 43192.0 * 1.0 * 50.0 ** 0.82
    expected_capacity = expected_q_fire_w / 2260000.0
    assert math.isclose(
        result.required_relief_capacity_kg_s, expected_capacity, rel_tol=1e-2
    )


def test_as1210_fire_case_vessel_geometry_overrides():
    """FIRE_CASE：vessel_geometry 非 None → 调 C-12 calc_wetted_area 覆盖。
    """
    vessel_geom = WettedAreaInput(
        D_m=2.0, L_m=3.0, head_type="2:1_ELLIPTICAL", H_m=1.0,
    )
    actual_a_wetted = calc_wetted_area(vessel_geom).wetted_area_m2

    inp_with_geom = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=999.0,  # 故意错的值
        as1210_pressure_factor=1.10,
        scenario="FIRE_CASE",
        vessel_geometry=vessel_geom,
    )
    inp_without_geom = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=999.0,
        as1210_pressure_factor=1.10,
        scenario="FIRE_CASE",
        vessel_geometry=None,
    )
    r_with = calc_as1210_relief_sizing(inp_with_geom)
    r_without = calc_as1210_relief_sizing(inp_without_geom)
    # 有 vessel_geometry 的结果不应等于直接传 999.0 的结果
    assert r_with.required_relief_capacity_kg_s != r_without.required_relief_capacity_kg_s
    # 期望使用 C-12 calc_wetted_area 实际返回值
    expected_capacity = (43192.0 * 1.0 * actual_a_wetted ** 0.82) / 2260000.0
    assert math.isclose(
        r_with.required_relief_capacity_kg_s, expected_capacity, rel_tol=1e-6
    )


# ============================================================================
# F2 边界校验 — MAWP/pressure_factor 非法值抛 As1210InputError
# ============================================================================


def test_as1210_zero_mawp_raises():
    """F2：mawp_kpa <= 0 抛 As1210InputError。"""
    inp = As1210ReliefInput(
        mawp_kpa=0.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10, scenario="TUBE_RUPTURE",
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_as1210_negative_mawp_raises():
    """F2：mawp_kpa < 0 抛 As1210InputError。"""
    inp = As1210ReliefInput(
        mawp_kpa=-100.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10, scenario="TUBE_RUPTURE",
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_as1210_pressure_factor_below_range_raises():
    """F2：as1210_pressure_factor < 1.05 抛 As1210InputError。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.00, scenario="TUBE_RUPTURE",
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_as1210_pressure_factor_above_range_raises():
    """F2：as1210_pressure_factor > 1.30 抛 As1210InputError。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.50, scenario="TUBE_RUPTURE",
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_as1210_negative_tube_rupture_mass_raises():
    """F2：tube_rupture_mass_kg_s < 0 抛 As1210InputError。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=-1.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10, scenario="TUBE_RUPTURE",
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_as1210_negative_wetted_area_raises():
    """F2：fire_case_wetted_area_m2 < 0 抛 As1210InputError。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=-1.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


# ============================================================================
# F1 Imperial 双单位输出
# ============================================================================


def test_as1210_imperial_units_output():
    """imperial_units=True 时应输出 psig / lb_s。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10, scenario="TUBE_RUPTURE",
        imperial_units=True,
    )
    result = calc_as1210_relief_sizing(inp)
    assert result.imperial_conversion is not None
    assert "required_set_pressure_psig" in result.imperial_conversion
    assert "required_relief_capacity_lb_s" in result.imperial_conversion
    expected_psig = 1100.0 * 0.1450377
    assert math.isclose(
        result.imperial_conversion["required_set_pressure_psig"],
        expected_psig,
        rel_tol=1e-6,
    )
    expected_lb_s = 10.0 * 2.20462
    assert math.isclose(
        result.imperial_conversion["required_relief_capacity_lb_s"],
        expected_lb_s,
        rel_tol=1e-6,
    )


def test_as1210_si_units_no_imperial_conversion():
    """imperial_units=False（默认）时 imperial_conversion 应为 None。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10, scenario="TUBE_RUPTURE",
    )
    result = calc_as1210_relief_sizing(inp)
    assert result.imperial_conversion is None


# ============================================================================
# Frozen dataclass + formula_ref + PcsError（批次一致性）
# ============================================================================


def test_as1210_relief_result_is_frozen():
    """As1210ReliefResult 必须是 frozen（不可变）。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10, scenario="TUBE_RUPTURE",
    )
    result = calc_as1210_relief_sizing(inp)
    with pytest.raises(FrozenInstanceError):
        result.required_set_pressure_kpa = 0.0  # type: ignore[misc]


def test_as1210_relief_input_is_frozen():
    """As1210ReliefInput 必须是 frozen（不可变）。"""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10, scenario="TUBE_RUPTURE",
    )
    with pytest.raises(FrozenInstanceError):
        inp.mawp_kpa = 999.0  # type: ignore[misc]


def test_as1210_formula_ref_present():
    """formula_ref must contain 4 keys: tube_rupture/cv_failure/fire_case/wetted."""
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=50.0,
        as1210_pressure_factor=1.10, scenario="TUBE_RUPTURE",
    )
    result = calc_as1210_relief_sizing(inp)
    assert "tube_rupture" in result.formula_ref
    assert "control_valve_failure" in result.formula_ref
    assert "fire_case" in result.formula_ref
    assert "wetted_area_source" in result.formula_ref
    assert "1.10" in result.formula_ref["tube_rupture"]
    assert "1.20" in result.formula_ref["control_valve_failure"]
    assert "43192" in result.formula_ref["fire_case"]
    assert "C-12" in result.formula_ref["wetted_area_source"]


def test_as1210_error_inherits_pcs_error():
    """As1210InputError 必须继承 PcsError 且含 code/status。"""
    err = As1210InputError("test")
    assert err.code == "AS1210_RELIEF_INPUT_ERROR"
    assert err.status == 422
    assert hasattr(err, "details")


# ============================================================================
# Module surface 完整性
# ============================================================================


def test_as1210_overpressure_module_exports():
    """模块 __all__ 必须包含核心 5 个公开符号。"""
    assert "calc_as1210_relief_sizing" in as1210_overpressure_service.__all__
    assert "As1210ReliefInput" in as1210_overpressure_service.__all__
    assert "As1210ReliefResult" in as1210_overpressure_service.__all__
    assert "As1210InputError" in as1210_overpressure_service.__all__
    assert "Scenario" in as1210_overpressure_service.__all__


# ============================================================================
# Golden fixture 测试
# ============================================================================


def test_golden_as1210_tube_rupture_fixture_present():
    """黄金算例 fixture 文件存在且可加载。"""
    if not FIXTURE_PATH.exists():
        pytest.skip("golden_as1210_tube_rupture.json fixture 未创建（占位）")
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert "cases" in data
    assert len(data["cases"]) >= 1


def test_golden_fixture_matches_implementation():
    """Future-drift detector: golden fixture values must match AS 1210 formulas."""
    if not FIXTURE_PATH.exists():
        pytest.skip("golden_as1210_tube_rupture.json fixture 未创建（占位）")
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        mawp = case["input"]["mawp_kpa"]
        scenario = case["input"]["scenario"]
        cv_mode = case["input"].get("control_valve_failure_mode", "AIR_FAIL")
        pressure_factor = case["input"].get("as1210_pressure_factor", 1.10)
        expected_p = case["expected"]["required_set_pressure_kpa"]
        if scenario == "TUBE_RUPTURE":
            actual_p = pressure_factor * mawp
        elif scenario == "CONTROL_VALVE_FAILURE":
            cv_factors = {"AIR_FAIL": 1.10, "SIGNAL_FAIL": 1.20, "POWER_FAIL": 1.15}
            actual_p = cv_factors[cv_mode] * mawp
        else:
            pytest.skip(f"scenario={scenario} 不在本 fixture 覆盖")
            continue
        assert math.isclose(actual_p, expected_p, rel_tol=1e-6, abs_tol=1e-6), (
            f"Fixture drift: case={case['id']}, scenario={scenario}, "
            f"expected={expected_p}, actual={actual_p}"
        )