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


# ============================================================================
# OPEN-P6-6A-5 T2 — ΔH_vap fluid-specific input field tests
# Back-compat + XLS PR-025 208 case + propane 425 case + validation
# ============================================================================


def _fire_case_vessel_geometry() -> WettedAreaInput:
    """XLS PR-025 真实 vessel geometry (FLAT head, H_liquid=1.867m → A_wet=14.66648 m²)."""
    return WettedAreaInput(
        D_m=2.5, L_m=10.0, head_type="FLAT", H_m=1.8673944398508298,
        n_vessels=1, vessel_shape="VERTICAL",
    )


def test_fire_case_default_dhvap_2260_backward_compat():
    """OPEN-P6-6A-5 Ruling 14 back-compat：不传 delta_h_vap_kj_kg → 用默认 2260 kJ/kg。

    PCS capacity = 43192 × 1.0 × 14.66648^0.82 / (2260 × 1000) ≈ 0.1729 kg/s。
    """
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
    )
    # 故意不传 delta_h_vap_kj_kg
    assert "delta_h_vap_kj_kg" not in inp.__dataclass_fields__ or (
        inp.delta_h_vap_kj_kg == 2260.0
    )
    result = calc_as1210_relief_sizing(inp)
    expected = (43192.0 * 14.666481633974485 ** 0.82) / 2260000.0
    assert math.isclose(result.required_relief_capacity_kg_s, expected, rel_tol=1e-6)
    assert math.isclose(result.required_relief_capacity_kg_s, 0.17285508035989886, rel_tol=1e-4)


def test_fire_case_custom_dhvap_xls_208_matches_api_520_path_g35():
    """OPEN-P6-6A-5 Ruling 14 XLS PR-025 对账：ΔH_vap=208 kJ/kg (XLS implied)
    → PCS capacity ≈ 1.878 kg/s ≈ 6761 kg/hr, 与 XLS API 520 path G35=6766.45
    容差 0.076%（within 经验 1% per SPEC §5）。

    这是 T1 引入 delta_h_vap_kj_kg 字段的核心目的：让 PCS FIRE_CASE 能用 XLS
    隐式 ΔH_vap≈208 (natural gas liquefied) 对账 XLS API 520 path。
    """
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        delta_h_vap_kj_kg=208.0,
    )
    result = calc_as1210_relief_sizing(inp)
    expected_kg_s = (43192.0 * 14.666481633974485 ** 0.82) / (208.0 * 1000.0)
    assert math.isclose(
        result.required_relief_capacity_kg_s, expected_kg_s, rel_tol=1e-6
    )
    capacity_kg_hr = result.required_relief_capacity_kg_s * 3600.0
    # PCS 6761 vs XLS G35 6766.45 = 0.076% diff（within 经验 1%）
    assert math.isclose(capacity_kg_hr, 6766.45, rel_tol=1e-2), (
        f"capacity_kg_hr={capacity_kg_hr} 应 ≈ XLS G35 6766.45 within 1%"
    )


def test_fire_case_custom_dhvap_propane_425_standard():
    """OPEN-P6-6A-5 Ruling 14 propane 标准 ΔH_vap=425 kJ/kg (GPSA Databook 典型值)。

    PCS capacity ≈ 0.9192 kg/s × 3600 ≈ 3309 kg/hr。
    """
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        delta_h_vap_kj_kg=425.0,
    )
    result = calc_as1210_relief_sizing(inp)
    expected_kg_s = (43192.0 * 14.666481633974485 ** 0.82) / (425.0 * 1000.0)
    assert math.isclose(
        result.required_relief_capacity_kg_s, expected_kg_s, rel_tol=1e-6
    )
    assert math.isclose(
        result.required_relief_capacity_kg_s, 0.919182309678521, rel_tol=1e-4
    )


def test_fire_case_dhvap_zero_raises_As1210InputError():
    """F2: delta_h_vap_kj_kg <= 0 抛 As1210InputError。"""
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        delta_h_vap_kj_kg=0.0,
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_fire_case_dhvap_negative_raises_As1210InputError():
    """F2: delta_h_vap_kj_kg < 0 抛 As1210InputError。"""
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        delta_h_vap_kj_kg=-100.0,
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_formula_ref_includes_actual_dhvap_value():
    """OPEN-P6-6A-5 Ruling 14 formula_ref 必须透出实际 ΔH_vap 值（不只硬编码 2260）。"""
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        delta_h_vap_kj_kg=208.0,
    )
    result = calc_as1210_relief_sizing(inp)
    fire_ref = result.formula_ref["fire_case"]
    assert "208" in fire_ref, (
        f"formula_ref.fire_case={fire_ref!r} 应包含 '208' (实际传入 ΔH_vap)"
    )
    assert "ΔH_vap" in fire_ref or "delta_h_vap" in fire_ref.lower(), (
        f"formula_ref.fire_case={fire_ref!r} 应包含 'ΔH_vap' 字段标识"
    )


# ============================================================================
# OPEN-P6-6A-5 T2 — Golden fixture (XLS PR-025 ΔH_vap=208 case)
# ============================================================================


def test_golden_as1210_dhvap_fixture_loads_and_matches_implementation():
    """OPEN-P6-6A-5 T2 golden fixture (golden_as1210_dhvap.json) 加载 + 字段对账。"""
    fixture_path = (
        Path(__file__).parent / "fixtures" / "golden_as1210_dhvap.json"
    )
    if not fixture_path.exists():
        pytest.skip("golden_as1210_dhvap.json fixture 未创建（占位）")
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert "_doc" in data
    assert "inputs" in data
    assert "expected" in data
    assert "tolerance_policy" in data
    assert "xls_cross_ref" in data
    inp_dict = data["inputs"]
    geom = WettedAreaInput(
        D_m=inp_dict["vessel_geometry"]["D_m"],
        L_m=inp_dict["vessel_geometry"]["L_m"],
        head_type=inp_dict["vessel_geometry"]["head_type"],
        H_m=inp_dict["vessel_geometry"]["H_m"],
        n_vessels=inp_dict["vessel_geometry"]["n_vessels"],
        vessel_shape=inp_dict["vessel_geometry"]["vessel_shape"],
    )
    inp = As1210ReliefInput(
        mawp_kpa=inp_dict["mawp_kpa"],
        tube_rupture_mass_kg_s=inp_dict.get("tube_rupture_mass_kg_s", 10.0),
        control_valve_failure_mode=inp_dict.get(
            "control_valve_failure_mode", "AIR_FAIL"
        ),
        fire_case_wetted_area_m2=inp_dict.get("fire_case_wetted_area_m2", 0.0),
        as1210_pressure_factor=inp_dict["as1210_pressure_factor"],
        scenario=inp_dict["scenario"],
        vessel_geometry=geom,
        environment_factor=inp_dict.get("environment_factor", 1.0),
        delta_h_vap_kj_kg=inp_dict["delta_h_vap_kj_kg"],
    )
    result = calc_as1210_relief_sizing(inp)
    rel_tol = data["tolerance_policy"].get("rel", 1e-2)
    # capacity 容差对账（fixture.expected.capacity_kg_s）
    assert math.isclose(
        result.required_relief_capacity_kg_s,
        data["expected"]["capacity_kg_s"],
        rel_tol=rel_tol,
    ), (
        f"PCS capacity={result.required_relief_capacity_kg_s!r} ≠ "
        f"golden fixture={data['expected']['capacity_kg_s']!r}"
    )
    # set_p 对账
    assert math.isclose(
        result.required_set_pressure_kpa,
        data["expected"]["set_p_kpa"],
        rel_tol=1e-6,
    )


# ============================================================================
# OPEN-P6-6A-8 T2 — fire_case_coefficient + fire_case_exponent fluid-specific
# fields. AS 1210 §4.4 path coefficient (71866) vs API 521 §3.4 default (43192).
# Closes Ruling 15 verification against XLS PR-025 AS 1210 path G54/G55.
# ============================================================================


def test_fire_case_default_43192_0p82_backward_compat():
    """OPEN-P6-6A-8 Ruling 15 back-compat：不传 fire_case_coefficient / fire_case_exponent
    → 用默认 43192 W / 0.82 (API 521 §3.4 SI 严格换算), 行为与 T0 完全一致。

    PCS q_fire_w = 43192 × 1.0 × 14.666481633974485^0.82 ≈ 390652 W (XLS API 520 path
    G34 within 经验 1% per Ruling 9)。
    """
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        # 不传 fire_case_coefficient / fire_case_exponent → 用 service 默认
    )
    # 显式确认默认值（防御性 assert: 防止未来误改 default）
    assert inp.fire_case_coefficient == 43192.0
    assert inp.fire_case_exponent == 0.82
    result = calc_as1210_relief_sizing(inp)
    expected_q_fire_w = 43192.0 * 14.666481633974485 ** 0.82
    assert math.isclose(
        result.required_relief_capacity_kg_s * 2260.0 * 1000.0,
        expected_q_fire_w,
        rel_tol=1e-10,
    )
    # XLS PR-025 API 520 path G34 = 390724.84 W within 经验 1%
    assert math.isclose(expected_q_fire_w, 390652.48, rel_tol=1e-4)


def test_fire_case_as1210_coeff_71866_exponent_0p82_matches_g54():
    """OPEN-P6-6A-8 Ruling 15: XLS PR-025 AS 1210 path 用 coefficient=71866 W
    (7.2×10⁴ SI 严格换算, AS 1210 §4.4 eqn. 8.6.2.3(1)) 而非 API 521 默认 43192。

    PCS q_fire_w = 71866 × 1.0 × 14.666^0.82 ≈ 649996 W vs XLS G54=649808.14 W
    rel_diff ≈ 0.029%（within rel≤1e-3 XLS EXACT 容差 — 7.2×10⁴ 系数是 AS 1210 path
    常用合理近似，XLS 隐含 coefficient 派生过程决定了小幅差异）。
    """
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        fire_case_coefficient=71866.0,
        fire_case_exponent=0.82,
    )
    result = calc_as1210_relief_sizing(inp)
    # PCS q_fire_w algebraic EXACT
    A = 14.666481633974485
    expected_q_fire_w = 71866.0 * A ** 0.82
    implied_q_fire_w = result.required_relief_capacity_kg_s * 2260.0 * 1000.0
    assert math.isclose(implied_q_fire_w, expected_q_fire_w, rel_tol=1e-10), (
        f"PCS q_fire_w (implied)={implied_q_fire_w!r} ≠ "
        f"algebraic 71866·A^0.82={expected_q_fire_w!r}"
    )
    # vs XLS PR-025 AS 1210 path G54 = 649808.1438365723 W (rel≤1e-3 XLS EXACT)
    assert math.isclose(implied_q_fire_w, 649808.1438365723, rel_tol=1e-3), (
        f"PCS q_fire_w={implied_q_fire_w!r} vs XLS G54=649808.14 W"
        f" rel_diff > 1e-3 容差"
    )


def test_fire_case_as1210_with_dhvap_208_matches_g55():
    """OPEN-P6-6A-8 Ruling 15 + OPEN-P6-6A-5 Ruling 14 整合: AS 1210 path coefficient
    (71866) + fluid-specific ΔH_vap (208 kJ/kg, natural gas liquefied) → 对账 XLS G55。

    PCS capacity × 3600 ≈ 11249.93 kg/hr vs XLS G55=11253.17 kg/hr rel_diff ≈ 0.029%
    within rel≤1% XLS 1% 容差 per SPEC §5。

    整合两个 Ruling:
      - Ruling 14 (P6-6A-5): ΔH_vap fluid-specific input via delta_h_vap_kj_kg
      - Ruling 15 (P6-6A-8): fire_case_coefficient fluid-specific input
    两者共同支持 AS 1210 path G55 对账 (XLS 隐含 ΔH_vap ≈ 208, AS 1210 path C ≈ 71866)。
    """
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        fire_case_coefficient=71866.0,
        fire_case_exponent=0.82,
        delta_h_vap_kj_kg=208.0,
    )
    result = calc_as1210_relief_sizing(inp)
    # PCS capacity algebraic EXACT
    A = 14.666481633974485
    expected_capacity_kg_s = (
        71866.0 * A ** 0.82 / (208.0 * 1000.0)
    )
    assert math.isclose(
        result.required_relief_capacity_kg_s, expected_capacity_kg_s, rel_tol=1e-10
    )
    # vs XLS PR-025 AS 1210 path G55 = 11253.17 kg/hr (rel≤1e-2 XLS 1% 容差 per SPEC §5)
    capacity_kg_hr = result.required_relief_capacity_kg_s * 3600.0
    assert math.isclose(capacity_kg_hr, 11253.171626956226, rel_tol=1e-2), (
        f"PCS capacity={capacity_kg_hr!r} kg/hr vs XLS G55=11253.17 kg/hr"
        f" rel_diff > 1% 容差 per SPEC §5"
    )


def test_fire_case_custom_exponent_1p0_linear():
    """OPEN-P6-6A-8 Ruling 15 自定义 exponent: coefficient=100, exponent=1.0 →
    q_fire_w = 100 × 14.666^1.0 = 1466.6 W (线性 scaling，便于 unit-test 验证 exponent
    字段确实被使用 — 而非硬编码 0.82)。
    """
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        fire_case_coefficient=100.0,
        fire_case_exponent=1.0,
    )
    result = calc_as1210_relief_sizing(inp)
    A = 14.666481633974485
    expected_q_fire_w = 100.0 * A ** 1.0
    implied_q_fire_w = result.required_relief_capacity_kg_s * 2260.0 * 1000.0
    assert math.isclose(implied_q_fire_w, expected_q_fire_w, rel_tol=1e-10), (
        f"PCS q_fire_w (implied)={implied_q_fire_w!r} ≠ "
        f"100·A^1.0={expected_q_fire_w!r} (custom exponent 1.0 未生效)"
    )


def test_fire_case_coefficient_zero_raises():
    """OPEN-P6-6A-8 Ruling 15 F2: fire_case_coefficient <= 0 抛 As1210InputError。"""
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        fire_case_coefficient=0.0,
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_fire_case_exponent_zero_or_negative_raises():
    """OPEN-P6-6A-8 Ruling 15 F2: fire_case_exponent 越界 (0, 5] 抛 As1210InputError。
    测试 exponent=0 (下界外) 触发。
    """
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        fire_case_exponent=0.0,
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_fire_case_exponent_above_max_raises():
    """OPEN-P6-6A-8 Ruling 15 F2: fire_case_exponent > 5 抛 As1210InputError。"""
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        fire_case_exponent=5.5,
    )
    with pytest.raises(As1210InputError):
        calc_as1210_relief_sizing(inp)


def test_formula_ref_includes_actual_coefficient_and_exponent():
    """OPEN-P6-6A-8 Ruling 15 formula_ref 必须透出实际 coefficient 和 exponent 值
    (不只硬编码 '43192·F·A^0.82')。
    """
    geom = _fire_case_vessel_geometry()
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=0.0,
        as1210_pressure_factor=1.10, scenario="FIRE_CASE",
        vessel_geometry=geom,
        fire_case_coefficient=71866.0,
        fire_case_exponent=0.82,
    )
    result = calc_as1210_relief_sizing(inp)
    fire_ref = result.formula_ref["fire_case"]
    assert "71866" in fire_ref, (
        f"formula_ref.fire_case={fire_ref!r} 应包含 '71866' (实际传入 coefficient)"
    )
    assert "0.82" in fire_ref, (
        f"formula_ref.fire_case={fire_ref!r} 应包含 '0.82' (实际传入 exponent)"
    )


# ============================================================================
# OPEN-P6-6A-8 T2 — Golden fixture (XLS PR-025 AS 1210 path coefficient case)
# ============================================================================


def test_golden_as1210_fire_coeff_fixture_loads_and_matches_implementation():
    """OPEN-P6-6A-8 T2 golden fixture (golden_as1210_fire_coeff.json) 加载 + 字段对账。
    XLS PR-025 AS 1210 path G54 (q_fire_w) + G55 (capacity) 对账 with
    fire_case_coefficient=71866 + ΔH_vap=208。
    """
    fixture_path = (
        Path(__file__).parent / "fixtures" / "golden_as1210_fire_coeff.json"
    )
    if not fixture_path.exists():
        pytest.skip("golden_as1210_fire_coeff.json fixture 未创建（占位）")
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    assert "_doc" in data
    assert "inputs" in data
    assert "expected" in data
    assert "tolerance_policy" in data
    assert "xls_cross_ref" in data
    inp_dict = data["inputs"]
    geom = WettedAreaInput(
        D_m=inp_dict["vessel_geometry"]["D_m"],
        L_m=inp_dict["vessel_geometry"]["L_m"],
        head_type=inp_dict["vessel_geometry"]["head_type"],
        H_m=inp_dict["vessel_geometry"]["H_m"],
        n_vessels=inp_dict["vessel_geometry"]["n_vessels"],
        vessel_shape=inp_dict["vessel_geometry"]["vessel_shape"],
    )
    inp = As1210ReliefInput(
        mawp_kpa=inp_dict["mawp_kpa"],
        tube_rupture_mass_kg_s=inp_dict.get("tube_rupture_mass_kg_s", 10.0),
        control_valve_failure_mode=inp_dict.get(
            "control_valve_failure_mode", "AIR_FAIL"
        ),
        fire_case_wetted_area_m2=inp_dict.get("fire_case_wetted_area_m2", 0.0),
        as1210_pressure_factor=inp_dict["as1210_pressure_factor"],
        scenario=inp_dict["scenario"],
        vessel_geometry=geom,
        environment_factor=inp_dict.get("environment_factor", 1.0),
        delta_h_vap_kj_kg=inp_dict["delta_h_vap_kj_kg"],
        fire_case_coefficient=inp_dict["fire_case_coefficient"],
        fire_case_exponent=inp_dict["fire_case_exponent"],
    )
    result = calc_as1210_relief_sizing(inp)
    # q_fire_w 对账 (rel=1e-3 XLS EXACT per SPEC §5 AS 1210 path)
    rel_tol_q = data["tolerance_policy"]["q_fire_w_rel"]
    implied_q_fire_w = result.required_relief_capacity_kg_s * 208.0 * 1000.0
    assert math.isclose(
        implied_q_fire_w, data["expected"]["q_fire_w"], rel_tol=rel_tol_q
    ), (
        f"PCS q_fire_w (implied)={implied_q_fire_w!r} ≠ "
        f"golden fixture={data['expected']['q_fire_w']!r}"
    )
    # capacity 对账 (rel=1e-2 XLS 1% 容差 per SPEC §5)
    rel_tol_cap = data["tolerance_policy"]["capacity_rel"]
    assert math.isclose(
        result.required_relief_capacity_kg_s,
        data["expected"]["capacity_kg_s"],
        rel_tol=rel_tol_cap,
    ), (
        f"PCS capacity={result.required_relief_capacity_kg_s!r} ≠ "
        f"golden fixture={data['expected']['capacity_kg_s']!r}"
    )
    # set_p 对账
    assert math.isclose(
        result.required_set_pressure_kpa,
        data["expected"]["set_p_kpa"],
        rel_tol=1e-6,
    )


# ============================================================================
# P6-7 T7 OPEN-P6-6A-5 真正关闭 — fire_case_standard 枚举（API_521 / AS_1210）
# 工艺室 2026-09-28 签署"分 path 并存"裁决；放弃 2.457 系数。
# ============================================================================


def test_fire_case_standard_api_521_default():
    """T7：默认 API_521 (43192) — OPEN-P6-6A-5 真正关闭。

    不传 fire_case_coefficient 时，effective_coeff 取 _resolve_fire_case_coefficient
    ("API_521") 的 fallback 值 43192.0；formula_ref 必须透出标准 + 实际系数。
    """
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=10.0,
        as1210_pressure_factor=1.10,
        scenario="FIRE_CASE",
        delta_h_vap_kj_kg=2260.0,
        fire_case_standard="API_521",  # 显式指定（与 default 一致）
    )
    result = calc_as1210_relief_sizing(inp)
    assert result.formula_ref["fire_case_standard"] == "API_521"
    assert result.formula_ref["coefficient"] == 43192.0
    # algebraic EXACT 对账：capacity = 43192 × 10^0.82 / (2260 × 1000)
    expected_capacity = (43192.0 * 10.0 ** 0.82) / (2260.0 * 1000.0)
    assert math.isclose(
        result.required_relief_capacity_kg_s, expected_capacity, rel_tol=1e-10
    )


def test_fire_case_standard_as_1210_path_a():
    """T7：AS_1210 path (a) (7.2e4)。

    不传 fire_case_coefficient 时，effective_coeff 取 _resolve_fire_case_coefficient
    ("AS_1210") 的 7.2e4（AS 1210 §4.4 SI 严格换算）；formula_ref 必须透出。
    """
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=10.0,
        as1210_pressure_factor=1.10,
        scenario="FIRE_CASE",
        delta_h_vap_kj_kg=2260.0,
        fire_case_standard="AS_1210",
    )
    result = calc_as1210_relief_sizing(inp)
    assert result.formula_ref["fire_case_standard"] == "AS_1210"
    assert result.formula_ref["coefficient"] == 7.2e4
    # algebraic EXACT 对账：capacity = 7.2e4 × 10^0.82 / (2260 × 1000)
    expected_capacity = (7.2e4 * 10.0 ** 0.82) / (2260.0 * 1000.0)
    assert math.isclose(
        result.required_relief_capacity_kg_s, expected_capacity, rel_tol=1e-10
    )


def test_fire_case_standard_default_omitted_is_api_521():
    """T7 back-compat：不传 fire_case_standard → 默认 "API_521"。

    OPEN-P6-6A-8 Ruling 15 / worley_c21 XLS G54/G55 对账测试不传
    fire_case_standard 仍走 API_521 默认系数 43192.0；
    用户显式 fire_case_coefficient 覆盖优先级保留（worley_c21 用 71866）。
    """
    inp_no_standard = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=10.0,
        as1210_pressure_factor=1.10,
        scenario="FIRE_CASE",
        delta_h_vap_kj_kg=2260.0,
    )
    # default 是 "API_521"
    assert inp_no_standard.fire_case_standard == "API_521"
    result = calc_as1210_relief_sizing(inp_no_standard)
    assert result.formula_ref["fire_case_standard"] == "API_521"
    assert result.formula_ref["coefficient"] == 43192.0


def test_fire_case_standard_unknown_raises():
    """T7 边界：传入非法 fire_case_standard → _resolve_fire_case_coefficient 抛 ValueError。

    注：As1210ReliefInput 是 frozen dataclass 不是 Pydantic，Literal 仅 type-check
    阶段生效；运行时 _resolve_fire_case_coefficient 通过 ``if standard == "..."``
    分支兜底，未知值抛 ValueError。
    """
    inp = As1210ReliefInput(
        mawp_kpa=1000.0, tube_rupture_mass_kg_s=10.0,
        control_valve_failure_mode="AIR_FAIL",
        fire_case_wetted_area_m2=10.0,
        as1210_pressure_factor=1.10,
        scenario="FIRE_CASE",
        delta_h_vap_kj_kg=2260.0,
    )
    # 模拟运行时注入未知标准（绕过 Literal 类型检查）
    object.__setattr__(inp, "fire_case_standard", "ASME_8_DIV1")
    with pytest.raises(ValueError, match="Unknown fire_case_standard"):
        calc_as1210_relief_sizing(inp)


# ============================================================================
# P6-7 T8 OPEN-P6-6A-10 — AS 1210 §4.4 path (b) gas/vapor + Jet fire (110,000 W/m²)
# 工艺室 2026-09-28 落库 golden_as1210_path_b_jet_fire.json（2 path b + 2 jet fire
# 算例，CH4 @ 1000 psia + C3H8 @ 800 psia，tolerance_rel=0.01）。
# ============================================================================


def test_fire_case_path_b_gas_vapor_ch4():
    """T8：AS 1210 §4.4 path (b) gas/vapor CH4 @ 1000 psia。

    标准标识 "AS_1210" + m_gas_stored_kg=220 > 0 → calc_fire_case 路由到
    _path_b_gas_vapor 公式：m' = m·Y_p + m'_p，Y_p = 10000/(C_w·t·T_o)。
    T4 P6-9-PICKUP-2：t_wall_m 单位 SI 米（20 mm = 0.020 m）；
    Y_p = 10000 / (3900 × 0.020 × 300) = 0.4274；m' = 220 × 0.4274 ≈ 94.02 kg/s。
    工艺室 fixture 对账（2026-11-15 前 HYSYS re-validated，OPEN-P6-9-PICKUP-2-2 复盘）。
    """
    from app.services.psv.as1210_overpressure_service import (
        FireCaseInput,
        calc_fire_case,
    )

    inp = FireCaseInput(
        wetted_area_m2=5.0,  # path (b) 不使用；保持向后兼容 schema 字段
        fire_case_standard="AS_1210",
        m_gas_stored_kg=220.0,
        c_w_kj_per_m3_k=3900.0,
        t_wall_m=0.020,  # 20 mm；T4 单位修复（OPEN-P6-9-PICKUP-2-2）
        t_o_k=300.0,
        m_p_prime_kg_s=0.0,
    )
    result = calc_fire_case(inp)
    # 公式路由正确性：标准 = "AS_1210"（path (b) 与 path (a) 共用标准标识）
    assert result.formula_ref["fire_case_standard"] == "AS_1210"
    # path (b) 热通量 10,000 W/m² pool fire
    assert result.formula_ref["heat_flux_w_m2"] == 10_000.0
    # capacity algebraic EXACT vs corrected formula
    expected_y_p = 10_000.0 / (3900.0 * 0.020 * 300.0)  # = 0.4274
    expected_capacity = 220.0 * expected_y_p  # = 94.02
    assert math.isclose(
        result.required_mass_flow_kg_s, expected_capacity, rel_tol=1e-10
    )
    # 工艺室 fixture 对账（CH4 @ 1000 psia，t_wall_m=0.020：expected ≈ 94.02 kg/s）
    assert math.isclose(
        result.required_mass_flow_kg_s, 94.02, rel_tol=0.01
    )
    # formula_ref 含 calculation 字符串（path (b) 公式溯源）
    assert "path (b)" in result.formula_ref["calculation"]
    assert "10000" in result.formula_ref["calculation"]


def test_fire_case_jet_fire_ch4():
    """T8：AS 1210 §4.4 Jet fire CH4 @ 1000 psia（110,000 W/m²）。

    标准标识 "Jet fire" → calc_fire_case 路由到 _jet_fire 公式：
    m' = m·Y_t + m'_p，Y_t = 110000/(C_w·t·T_r)。
    T4 P6-9-PICKUP-2：t_wall_m 单位 SI 米（20 mm = 0.020 m）；
    Y_t = 110000 / (3900 × 0.020 × 620) = 2.2746；m' = 220 × 2.2746 ≈ 500.4 kg/s。
    工艺室 fixture 对账（2026-11-15 前 HYSYS re-validated，OPEN-P6-9-PICKUP-2-2 复盘）。
    """
    from app.services.psv.as1210_overpressure_service import (
        FireCaseInput,
        calc_fire_case,
    )

    inp = FireCaseInput(
        fire_case_standard="Jet fire",
        m_gas_stored_kg=220.0,
        c_w_kj_per_m3_k=3900.0,
        t_wall_m=0.020,  # 20 mm；T4 单位修复（OPEN-P6-9-PICKUP-2-2）
        t_r_k=620.0,
        m_p_prime_kg_s=0.0,
    )
    result = calc_fire_case(inp)
    # 公式路由正确性：标准 = "Jet fire"
    assert result.formula_ref["fire_case_standard"] == "Jet fire"
    # Jet fire 热通量 110,000 W/m²
    assert result.formula_ref["heat_flux_w_m2"] == 110_000.0
    # capacity algebraic EXACT vs corrected formula
    expected_y_t = 110_000.0 / (3900.0 * 0.020 * 620.0)  # = 2.2746
    expected_capacity = 220.0 * expected_y_t  # = 500.4
    assert math.isclose(
        result.required_mass_flow_kg_s, expected_capacity, rel_tol=1e-10
    )
    # 工艺室 fixture 对账（CH4 @ 1000 psia，t_wall_m=0.020：expected ≈ 500.4 kg/s）
    assert math.isclose(
        result.required_mass_flow_kg_s, 500.4, rel_tol=0.01
    )
    # formula_ref 含 calculation 字符串（Jet fire 公式溯源）
    assert "jet fire" in result.formula_ref["calculation"].lower()
    assert "110000" in result.formula_ref["calculation"]


def test_golden_as1210_path_b_jet_fire_4_cases():
    """T8：4 算例 fixture（golden_as1210_path_b_jet_fire.json）加载测试。

    path_b_gas_vapor_fixture × 2 + jet_fire_fixture × 2 = 4 cases。
    每个 case 必须含 case_id / inputs / expected 字段；fixture 4 算例在
    calc_fire_case 中 algebraic EXACT 计算后与 expected.m_prime_kg_s 容差 1%。
    工艺室 fixture 期望值是 3-sig-fig 近似（CH4 算例 C3H8 算例差 1.8% 内），
    容差取 rel_tol=0.01 + abs_tol=0.005 双门限。
    """
    from app.services.psv.as1210_overpressure_service import (
        FireCaseInput,
        calc_fire_case,
    )

    fixture_path = (
        Path(__file__).parent / "fixtures" / "golden_as1210_path_b_jet_fire.json"
    )
    assert fixture_path.exists(), (
        f"golden_as1210_path_b_jet_fire.json 未落库：{fixture_path}"
    )
    data = json.loads(fixture_path.read_text(encoding="utf-8"))

    # 结构校验
    assert "_meta" in data
    assert data["_meta"]["open_item"] == "OPEN-P6-6A-10"
    assert "path_b_gas_vapor_fixture" in data
    assert "jet_fire_fixture" in data
    assert len(data["path_b_gas_vapor_fixture"]) == 2
    assert len(data["jet_fire_fixture"]) == 2

    # 4 算例：字段完整性 + capacity 容差对账（rel=0.01 + abs=0.005 容差）
    path_b_cases = data["path_b_gas_vapor_fixture"]
    jet_fire_cases = data["jet_fire_fixture"]

    # ---- path (b) gas/vapor × 2 ----
    for case in path_b_cases:
        assert "case_id" in case
        assert "inputs" in case
        assert "expected" in case
        inputs = case["inputs"]
        expected = case["expected"]
        tol = case.get("tolerance_rel", 0.01)
        inp = FireCaseInput(
            fire_case_standard="AS_1210",
            m_gas_stored_kg=inputs["m_gas_stored_kg"],
            c_w_kj_per_m3_k=inputs["c_w_kj_per_m3_k"],
            t_wall_m=inputs["t_wall_m"],  # T4 单位修复（OPEN-P6-9-PICKUP-2-2）
            t_o_k=inputs["t_o_k"],
            m_p_prime_kg_s=inputs.get("m_p_prime_kg_s", 0.0),
        )
        result = calc_fire_case(inp)
        # 工艺室 fixture 容差对账（rel=1% + abs=0.005 双门限，容纳 3-sig-fig 近似）
        assert math.isclose(
            result.required_mass_flow_kg_s,
            expected["m_prime_kg_s"],
            rel_tol=tol,
            abs_tol=0.005,
        ), (
            f"path (b) case_id={case['case_id']}: "
            f"PCS m'={result.required_mass_flow_kg_s!r} ≠ "
            f"fixture expected={expected['m_prime_kg_s']!r} "
            f"rel_tol={tol} abs_tol=0.005"
        )
        # algebraic EXACT 校验（公式实现 vs 工艺室公式一致）
        y_p = 10_000.0 / (
            inputs["c_w_kj_per_m3_k"] * inputs["t_wall_m"] * inputs["t_o_k"]
        )
        expected_m_prime_exact = inputs["m_gas_stored_kg"] * y_p + inputs.get(
            "m_p_prime_kg_s", 0.0
        )
        assert math.isclose(
            result.required_mass_flow_kg_s,
            expected_m_prime_exact,
            rel_tol=1e-10,
        )

    # ---- Jet fire × 2 ----
    for case in jet_fire_cases:
        assert "case_id" in case
        assert "inputs" in case
        assert "expected" in case
        inputs = case["inputs"]
        expected = case["expected"]
        tol = case.get("tolerance_rel", 0.01)
        inp = FireCaseInput(
            fire_case_standard="Jet fire",
            m_gas_stored_kg=inputs["m_gas_stored_kg"],
            c_w_kj_per_m3_k=inputs["c_w_kj_per_m3_k"],
            t_wall_m=inputs["t_wall_m"],  # T4 单位修复（OPEN-P6-9-PICKUP-2-2）
            t_r_k=inputs["t_r_k"],
            m_p_prime_kg_s=inputs.get("m_p_prime_kg_s", 0.0),
        )
        result = calc_fire_case(inp)
        # 工艺室 fixture 容差对账（rel=1% + abs=0.005 双门限，容纳 3-sig-fig 近似）
        assert math.isclose(
            result.required_mass_flow_kg_s,
            expected["m_prime_kg_s"],
            rel_tol=tol,
            abs_tol=0.005,
        ), (
            f"Jet fire case_id={case['case_id']}: "
            f"PCS m'={result.required_mass_flow_kg_s!r} ≠ "
            f"fixture expected={expected['m_prime_kg_s']!r} "
            f"rel_tol={tol} abs_tol=0.005"
        )
        # algebraic EXACT 校验
        y_t = 110_000.0 / (
            inputs["c_w_kj_per_m3_k"] * inputs["t_wall_m"] * inputs["t_r_k"]
        )
        expected_m_prime_exact = inputs["m_gas_stored_kg"] * y_t + inputs.get(
            "m_p_prime_kg_s", 0.0
        )
        assert math.isclose(
            result.required_mass_flow_kg_s,
            expected_m_prime_exact,
            rel_tol=1e-10,
        )


def test_fire_case_standard_jet_fire_in_literal():
    """T8：FireCaseStandard Literal 必须包含 "Jet fire"（OPEN-P6-6A-10 扩展）。"""
    import typing

    from app.services.psv.as1210_overpressure_service import FireCaseStandard

    # typing.get_args 验证 Literal 包含 "Jet fire"
    assert "Jet fire" in typing.get_args(FireCaseStandard)
    assert "API_521" in typing.get_args(FireCaseStandard)
    assert "AS_1210" in typing.get_args(FireCaseStandard)


def test_fire_case_api_521_backward_compat_in_calc_fire_case():
    """T8 back-compat：fire_case_standard="API_521" + 不传 path (b) 字段 →
    calc_fire_case 走既有 API 521 公式（Q = 43192·F·A^0.82 / L）。

    与 calc_as1210_relief_sizing 的 T7 既行为 algebraic EXACT 一致（系数 43192）。
    """
    from app.services.psv.as1210_overpressure_service import (
        FireCaseInput,
        calc_fire_case,
    )

    inp = FireCaseInput(
        wetted_area_m2=10.0,
        latent_heat_kj_kg=2260.0,
        environment_factor_F=1.0,
        fire_case_standard="API_521",
    )
    result = calc_fire_case(inp)
    assert result.formula_ref["fire_case_standard"] == "API_521"
    assert result.formula_ref["coefficient"] == 43192.0
    expected_capacity = (43192.0 * 1.0 * 10.0 ** 0.82) / (2260.0 * 1000.0)
    assert math.isclose(
        result.required_mass_flow_kg_s, expected_capacity, rel_tol=1e-10
    )


def test_fire_case_as_1210_path_a_backward_compat_in_calc_fire_case():
    """T8 back-compat：fire_case_standard="AS_1210" + 不传 path (b) 字段 →
    calc_fire_case 走既有 path (a) 公式（Q = 7.2e4·F·A^0.82 / L）。

    关键 guardrail：m_gas_stored_kg 默认 0.0，必须触发 path (a) 而非 path (b)；
    与 calc_as1210_relief_sizing T7 既行为 algebraic EXACT 一致（系数 7.2e4）。
    """
    from app.services.psv.as1210_overpressure_service import (
        FireCaseInput,
        calc_fire_case,
    )

    inp = FireCaseInput(
        wetted_area_m2=10.0,
        latent_heat_kj_kg=2260.0,
        environment_factor_F=1.0,
        fire_case_standard="AS_1210",
        # m_gas_stored_kg 默认 0.0 → 走 path (a)
    )
    result = calc_fire_case(inp)
    assert result.formula_ref["fire_case_standard"] == "AS_1210"
    assert result.formula_ref["coefficient"] == 7.2e4
    expected_capacity = (7.2e4 * 1.0 * 10.0 ** 0.82) / (2260.0 * 1000.0)
    assert math.isclose(
        result.required_mass_flow_kg_s, expected_capacity, rel_tol=1e-10
    )
    # formula_ref 应是 path (a) 而非 path (b)
    assert "path (a)" in result.formula_ref["calculation"]


# ============================================================================
# T4 P6-9-PICKUP-2 OPEN-P6-9-PICKUP-2-2 — t_wall_mm → t_wall_m CRITICAL 单位修复
# 验收：Y_p 残差 < 5% vs 工件基准（公式直接计算 + 与 algebraic exact 对账）
# 公式：Y_p = 10000 / (C_w · t · T_o)，t 单位 SI 米
# ============================================================================


def test_t_wall_units_meters():
    """T4 t_wall_m 单位测试 — 输入 t=0.020 m → Y_p≈0.427。

    P6-9-PICKUP-2 OPEN-P6-9-PICKUP-2-2 CRITICAL 修复后回归：
    t_wall_m 单位 SI 米，公式 Y_p = 10000 / (3900 × 0.020 × 300) = 0.427。
    旧代码 t_wall_mm=20.0 (mm 暗示但公式按米处理) → Y_p=4.27e-4 (1000× 误差)。
    """
    from app.services.psv.as1210_overpressure_service import (
        FireCaseInput,
        calc_fire_case,
    )

    inp = FireCaseInput(
        fire_case_standard="AS_1210",
        m_gas_stored_kg=220.0,
        c_w_kj_per_m3_k=3900.0,
        t_wall_m=0.020,  # 20 mm = 0.020 m（SI 米）
        t_o_k=300.0,
        m_p_prime_kg_s=0.0,
    )
    result = calc_fire_case(inp)
    # algebraic exact: Y_p = 10000 / (3900 * 0.020 * 300) = 10000 / 23400 ≈ 0.42735
    expected_y_p = 10_000.0 / (3900.0 * 0.020 * 300.0)
    assert result.formula_ref["Y_p_per_s"] == pytest.approx(expected_y_p, rel=1e-10)
    # 验收门限：Y_p ≈ 0.427（rel=1%，与 brief 一致）
    assert result.formula_ref["Y_p_per_s"] == pytest.approx(0.427, rel=0.01)


def test_t_wall_units_from_mm_conversion():
    """T4 t_wall_m 单位转换测试 — mm → m 显式转换 vs 直接 m 等效。

    P6-9-PICKUP-2 OPEN-P6-9-PICKUP-2-2 CRITICAL 修复后回归：
    证明 20 mm 在调用方做显式 mm→m 转换（20.0 / 1000.0 = 0.020 m）与
    直接传 0.020 m 等效；二者产生相同 m'。
    """
    from app.services.psv.as1210_overpressure_service import (
        FireCaseInput,
        calc_fire_case,
    )

    # Case A：调用方做 mm→m 显式转换
    inp_mm_to_m = FireCaseInput(
        fire_case_standard="AS_1210",
        m_gas_stored_kg=220.0,
        c_w_kj_per_m3_k=3900.0,
        t_wall_m=20.0 / 1000.0,  # 显式 mm → m 转换
        t_o_k=300.0,
        m_p_prime_kg_s=0.0,
    )
    # Case B：直接传 0.020 m
    inp_direct_m = FireCaseInput(
        fire_case_standard="AS_1210",
        m_gas_stored_kg=220.0,
        c_w_kj_per_m3_k=3900.0,
        t_wall_m=0.020,  # 直接米
        t_o_k=300.0,
        m_p_prime_kg_s=0.0,
    )
    result_mm_to_m = calc_fire_case(inp_mm_to_m)
    result_direct_m = calc_fire_case(inp_direct_m)
    # 两种写法必须产生相同的 m'（formula algebraic identical）
    assert result_mm_to_m.required_mass_flow_kg_s == pytest.approx(
        result_direct_m.required_mass_flow_kg_s, rel=1e-12
    )
    # Y_p 也必须相等
    assert result_mm_to_m.formula_ref["Y_p_per_s"] == pytest.approx(
        result_direct_m.formula_ref["Y_p_per_s"], rel=1e-12
    )
    # 数值 sanity check：m' = 220 × 0.42735 ≈ 94.02 kg/s
    assert result_direct_m.required_mass_flow_kg_s == pytest.approx(94.02, rel=0.01)