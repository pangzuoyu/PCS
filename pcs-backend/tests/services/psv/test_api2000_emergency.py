"""P6-5 Task B4: C-20 PSV API 2000 emergency/fire + 真空工况。

按 SPEC §3.5.1 V1.4 + API 2000 7th Ed：
- FIRE：Q(W) = 43192·F·A_wetted^0.82（SI 严格换算自 21000·F·A_ft²^0.82）
- VACUUM：Q(m³/h) = 1013·A（API 2000 §3.6）
- EMERGENCY：Q = 1.5 × FIRE（API 2000 §3.5 进料失效+火灾耦合）
- NORMAL：委派 breathing_valve_service（已有；本任务 Q=0 占位）
- A_wetted 调用 C-12 calc_wetted_area（D7 接口冻结）

边界条件：
- environment_factor ∈ [0, 1]
- vessel_geometry 非 None 时调 C-12 覆盖 wetted_area_m2
- 43192 SI 系数（v4 闭环，N-1 v4 BLOCKER：不是 43838/709200）
"""

from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.psv import api2000_emergency_service
from app.services.psv.api2000_emergency_service import (
    Api2000InputError,
    Api2000ReliefInput,
    calc_api2000_relief_capacity,
)
from app.services.vessel.vessel_service import (
    WettedAreaInput,
    calc_wetted_area,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_api2000_fire.json"


# ============================================================================
# Step 1: 主测试 — FIRE 火灾工况（API 2000 7th §3.4 SI 系数 43192）
# ============================================================================


def test_api2000_fire_scenario_wetted_area():
    """FIRE：Q(W) = 43192·F·A^0.82；F=1, A=50 → Q ≈ 43192·50^0.82 W。

    验算链路：21000 × 0.293071 × 10.7639^0.82 = 21000 × 0.293071 × 7.0178
       = 21000 × 2.05655 = 43187.6 ≈ 43192 ✓
    """
    inp = Api2000ReliefInput(
        tank_volume_m3=100.0,
        wetted_area_m2=50.0,
        design_pressure_kpa=20.0,
        vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None,
        environment_factor=1.0,
        scenario="FIRE",
    )
    result = calc_api2000_relief_capacity(inp)
    expected_q = 43192.0 * 1.0 * (50.0 ** 0.82)
    assert math.isclose(result.required_relief_rate_w, expected_q, rel_tol=1e-2)
    assert result.scenario_used == "FIRE"


# ============================================================================
# Step 5: EMERGENCY + vessel_geometry 覆盖 wetted_area + VACUUM 工况
# ============================================================================


def test_api2000_emergency_vessel_geometry_overrides_wetted_area():
    """EMERGENCY：vessel_geometry 非 None → 调 C-12 calc_wetted_area 覆盖 inp.wetted_area_m2。

    Z-1 v5 BLOCKER：actual_a_wetted 必须从 C-12 calc_wetted_area 读取，禁止硬编码 13.5。
    """
    vessel_geom = WettedAreaInput(
        D_m=2.0, L_m=3.0, head_type="2:1_ELLIPTICAL", H_m=1.0,
    )
    # Z-1 v5：实际调 C-12 calc_wetted_area 拿精确值（不可硬编码 13.5）
    actual_a_wetted = calc_wetted_area(vessel_geom).wetted_area_m2

    inp_with_geom = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=999.0,  # 故意错的值
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="EMERGENCY", vessel_geometry=vessel_geom,
    )
    inp_without_geom = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=999.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="EMERGENCY", vessel_geometry=None,
    )
    r_with = calc_api2000_relief_capacity(inp_with_geom)
    r_without = calc_api2000_relief_capacity(inp_without_geom)
    # 有 vessel_geometry 的结果不应等于直接传 999.0 的结果
    assert r_with.required_relief_rate_w != r_without.required_relief_rate_w
    # a_wetted_used = C-12 实际返回值；EMERGENCY Q = 1.5 × FIRE Q
    expected_w_from_geom = 43192.0 * 1.0 * 1.5 * (actual_a_wetted ** 0.82)
    assert math.isclose(r_with.required_relief_rate_w, expected_w_from_geom, rel_tol=1e-6)
    assert r_with.scenario_used == "EMERGENCY"


def test_api2000_vacuum_scenario():
    """VACUUM：Q(m³/h) = 1013·A；A=50 → Q=50650 m³/h。"""
    inp = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=50.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="VACUUM",
    )
    result = calc_api2000_relief_capacity(inp)
    assert math.isclose(result.required_relief_rate_m3_h, 1013 * 50.0, rel_tol=1e-3)
    assert result.scenario_used == "VACUUM"


# ============================================================================
# F2 边界校验 — V/A/P/F 非法值抛 Api2000InputError
# ============================================================================


def test_api2000_zero_volume_raises():
    """F2：tank_volume_m3 ≤ 0 抛 Api2000InputError。"""
    inp = Api2000ReliefInput(
        tank_volume_m3=0.0, wetted_area_m2=50.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="FIRE",
    )
    with pytest.raises(Api2000InputError):
        calc_api2000_relief_capacity(inp)


def test_api2000_negative_wetted_area_raises():
    """F2：wetted_area_m2 < 0 抛 Api2000InputError（允许 0 退化情形）。"""
    inp = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=-1.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="FIRE",
    )
    with pytest.raises(Api2000InputError):
        calc_api2000_relief_capacity(inp)


def test_api2000_environment_factor_out_of_range_raises():
    """environment_factor 越界 [0, 1] 抛 Api2000InputError。"""
    inp = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=50.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.5,
        scenario="FIRE",
    )
    with pytest.raises(Api2000InputError):
        calc_api2000_relief_capacity(inp)


# ============================================================================
# F1 Imperial 双单位输出
# ============================================================================


def test_api2000_imperial_units_output():
    """imperial_units=True 时应输出 btu_hr / gallons_us / ft²。"""
    inp = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=50.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="FIRE", imperial_units=True,
    )
    result = calc_api2000_relief_capacity(inp)
    assert result.imperial_conversion is not None
    assert "required_relief_rate_btu_hr" in result.imperial_conversion
    assert "tank_volume_gallons_us" in result.imperial_conversion
    assert "wetted_area_ft2" in result.imperial_conversion
    expected_btu_hr = result.required_relief_rate_w * 3.41214
    assert math.isclose(
        result.imperial_conversion["required_relief_rate_btu_hr"],
        expected_btu_hr,
        rel_tol=1e-6,
    )
    expected_gal = 100.0 * 264.172
    assert math.isclose(
        result.imperial_conversion["tank_volume_gallons_us"],
        expected_gal,
        rel_tol=1e-6,
    )
    expected_ft2 = 50.0 * 10.7639
    assert math.isclose(
        result.imperial_conversion["wetted_area_ft2"],
        expected_ft2,
        rel_tol=1e-6,
    )


def test_api2000_si_units_no_imperial_conversion():
    """imperial_units=False（默认）时 imperial_conversion 应为 None。"""
    inp = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=50.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="FIRE",
    )
    result = calc_api2000_relief_capacity(inp)
    assert result.imperial_conversion is None


# ============================================================================
# Frozen dataclass + formula_ref + PcsError（批次一致性）
# ============================================================================


def test_api2000_emergency_result_is_frozen():
    """Api2000ReliefResult 必须是 frozen（不可变）。"""
    inp = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=50.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="FIRE",
    )
    result = calc_api2000_relief_capacity(inp)
    with pytest.raises(FrozenInstanceError):
        result.required_relief_rate_w = 0.0  # type: ignore[misc]


def test_api2000_emergency_input_is_frozen():
    """Api2000ReliefInput 必须是 frozen（不可变）。"""
    inp = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=50.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="FIRE",
    )
    with pytest.raises(FrozenInstanceError):
        inp.wetted_area_m2 = 999.0  # type: ignore[misc]


def test_api2000_emergency_formula_ref_present():
    """result.formula_ref 必须含 fire/vacuum/emergency/wetted_area_source 4 公式溯源。"""
    inp = Api2000ReliefInput(
        tank_volume_m3=100.0, wetted_area_m2=50.0,
        design_pressure_kpa=20.0, vacuum_pressure_kpa=0.5,
        fire_heat_input_w=None, environment_factor=1.0,
        scenario="FIRE",
    )
    result = calc_api2000_relief_capacity(inp)
    assert "fire_formula" in result.formula_ref
    assert "vacuum_formula" in result.formula_ref
    assert "emergency_formula" in result.formula_ref
    assert "wetted_area_source" in result.formula_ref
    assert "43192" in result.formula_ref["fire_formula"]
    assert "1013" in result.formula_ref["vacuum_formula"]
    assert "C-12" in result.formula_ref["wetted_area_source"]


def test_api2000_emergency_error_inherits_pcs_error():
    """Api2000InputError 必须继承 PcsError 且含 code/status。"""
    err = Api2000InputError("test")
    assert err.code == "API2000_RELIEF_INPUT_ERROR"
    assert err.status == 422
    assert hasattr(err, "details")


# ============================================================================
# Module surface 完整性
# ============================================================================


def test_api2000_emergency_module_exports():
    """模块 __all__ 必须包含核心 4 个公开符号。"""
    assert "calc_api2000_relief_capacity" in api2000_emergency_service.__all__
    assert "Api2000ReliefInput" in api2000_emergency_service.__all__
    assert "Api2000ReliefResult" in api2000_emergency_service.__all__
    assert "Api2000InputError" in api2000_emergency_service.__all__


# ============================================================================
# Golden fixture 测试
# ============================================================================


def test_golden_api2000_fire_fixture_present():
    """黄金算例 fixture 文件存在且可加载。"""
    if not FIXTURE_PATH.exists():
        pytest.skip("golden_api2000_fire.json fixture 未创建（占位）")
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert "cases" in data
    assert len(data["cases"]) >= 1


def test_golden_fixture_matches_implementation():
    """Future-drift detector: golden fixture FIRE Q values must match
    Q(W) = 43192·F·A^0.82 SI formula."""
    if not FIXTURE_PATH.exists():
        pytest.skip("golden_api2000_fire.json fixture 未创建（占位）")
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        a_m2 = case["input"]["wetted_area_m2"]
        f_env = case["input"]["environment_factor"]
        scenario = case["input"]["scenario"]
        if scenario == "FIRE":
            expected_q = case["expected"]["required_relief_rate_w"]
            actual_q = 43192.0 * f_env * (a_m2 ** 0.82)
            assert math.isclose(actual_q, expected_q, rel_tol=1e-6, abs_tol=1e-6), (
                f"Fixture drift: case={case['id']}, A={a_m2}, F={f_env}, "
                f"expected={expected_q}, actual={actual_q}"
            )
        elif scenario == "VACUUM":
            expected_q = case["expected"]["required_relief_rate_m3_h"]
            actual_q = 1013.0 * a_m2
            assert math.isclose(actual_q, expected_q, rel_tol=1e-6, abs_tol=1e-6), (
                f"Fixture drift: case={case['id']}, A={a_m2}, "
                f"expected={expected_q}, actual={actual_q}"
            )