"""P6-6A Task 12: C-20 PSV API 2000 7th atmospheric tank venting vs Worley 真实算例
WS-CA-PR-024 对账测试。

数据源: sample/Process caculation from Worley/…/WS-CA-PR-024.xls (gitignored 只读);
提取 dump: .superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-024.json
fixture: tests/services/psv/fixtures/worley_c20_api2000.json
(含 Worley 原始输入 cell 坐标、单位换算链、Ruling 8 single scenario overlap + air-equivalent
conversion mismatch 登记、容差分级与放宽理由)

⚠️ **SINGLE SCENARIO OVERLAP + AIR-EQUIVALENT CONVERSION MISMATCH — Ruling 8**

XLS-PR-024 Calculation Sheet: **Atmospheric and Low Pressure Tank Venting (API Standard 2000)**
(Combined sheet: Emergency FIRE + Normal + Thermal venting + geometry + project metadata).
PCS service `calc_api2000_relief_capacity`:
**API 2000 7th FIRE/VACUUM/EMERGENCY/NORMAL 4 scenarios** per SPEC §3.5.1 V1.4.

**Single scenario overlap** (Ruling 8 — main finding):
  - **Direct overlap (FIRE scenario only)**: Q_W = 43192·F·A^0.82 SI
    - XLS F19 = 13958413.732670628 W (for A_wet=1148.6448139687682 m², F=1.0)
    - PCS = 13955828.84 W (0.0185% diff, within 经验 1% per SPEC §5)
  - **AIR-EQUIVALENT CONVERSION MISMATCH** (Ruling 8):
    - XLS F24 = 67259.06 Nm³/h of AIR (gas-equivalent basis: Q_W/(L·ρ_air))
    - PCS Q_m3_h = Q_W × 0.86 (simple W → m³/h conversion, no gas basis)
    - Different physical quantities — direct match OUT_OF_SCOPE

**Direct overlap** (verified within 经验 1% per SPEC §5):
  - Q_W (FIRE) = 43192·F·A^0.82 SI matches XLS F19 within 0.0185%
  - scenario_used = "FIRE" (EXACT string)
  - formula_used (non-empty, contains '43192' + 'API 2000 7th §3.4')
  - formula_ref.fire_formula (contains '43192' + 'API 2000')

**OUT_OF_SCOPE** (per Ruling 8 + single scenario overlap):
  - Q_m3_h air-equivalent conversion mismatch (XLS F24=67259 vs PCS Q_m3_h = Q_W × 0.86)
  - NORMAL scenario (F38=639 Nm³/h AIR — delegates to breathing_valve_service)
  - Thermal venting (F34-F37: best-fit curve equations)
  - Max liquid outflow/inflow (F28/F30 — normal venting inputs)
  - Tank capacity (F33=1000 m³ — normal venting input)
  - Flash/boiling point criteria (F31/P42/P43 — normal venting selection)
  - Wetted area computation table (P8-S28 — PCS uses C-12 service or inp.wetted_area_m2)
  - Head type selection table (Q24-S28 — PCS uses C-12 service)
  - Multiple scenarios (VACUUM/EMERGENCY/THERMAL — only FIRE has direct overlap)
  - Elevation/liquid level (F14/F22 — XLS uses in Awet computation)
  - Pcrit critical flow (not applicable to API 2000 scope)

SPEC §5 分级: C-20 经验 1% (rel≤0.01); 本批因 Ruling 8 single scenario overlap,
经验 1% 容差 used for Q_W match (FIRE scenario only); Q_m3_h 完全 OUT_OF_SCOPE per Ruling 8
(air-equivalent conversion mismatch); scenario_used EXACT; formula_used EXACT non-empty string.

处置结论: 全部通过 (Q_W within 经验 1% + scenario_used + formula_used EXACT + Ruling 8 登记);
无 Ruling 1(a) 代码修复; root_cause_notes 登记 11 项 (Ruling 8 single scenario overlap +
air-equivalent mismatch + 10 子项: normal/thermal/max outflow/tank capacity/flash point/
wetted area table/head type table/multiple scenarios/elevation/Pcrit)
+ out_of_scope 11 项 (Q_m3_h + normal + thermal + max outflow + tank capacity +
flash point + wetted area table + head type table + multiple scenarios + elevation + Pcrit).
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.psv.api2000_emergency_service import (  # noqa: E402
    Api2000ReliefInput,
    calc_api2000_relief_capacity,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "worley_c20_api2000.json"
)
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_input(case: dict) -> Api2000ReliefInput:
    """Build Api2000ReliefInput from case.service_inputs."""
    si = case["service_inputs"]
    return Api2000ReliefInput(
        tank_volume_m3=si["tank_volume_m3"],
        wetted_area_m2=si["wetted_area_m2"],
        design_pressure_kpa=si["design_pressure_kpa"],
        vacuum_pressure_kpa=si["vacuum_pressure_kpa"],
        fire_heat_input_w=si["fire_heat_input_w"],
        vessel_geometry=si["vessel_geometry"],
        environment_factor=si["environment_factor"],
        scenario=si["scenario"],
        imperial_units=si["imperial_units"],
    )


# ============================================================================
# 1) Q_W — FIRE scenario direct overlap (经验 1% 容差, actual 0.0185%)
# ============================================================================


def test_fire_Q_W_matches_xls_F19_within_experience_1pct() -> None:
    """FIRE scenario Q_W = 43192·F·A^0.82 SI matches XLS F19 within 经验 1% per SPEC §5.

    XLS F19 = 13958413.732670628 W (XLS computes Q_W from API 2000 7th §3.4 SI formula).
    PCS service: Q_W = 43192 × 1.0 × 1148.6448139687682^0.82 = 13955828.84 W.
    Diff = 0.0185% — within 经验 1% 容差 per SPEC §5.

    This is the **DIRECT OVERLAP** field per Ruling 8 single scenario overlap.
    Q_W formula is identical in PCS ↔ XLS API 2000 7th §3.4 (imperial 21000·F·A_ft2^0.82
    × 0.293071 = 43192 SI strict conversion).
    """
    case = WORLEY["cases"][0]
    si = case["service_inputs"]
    exp = case["expected"]

    # Hand-compute PCS Q_W from A_wet and F input
    A = si["wetted_area_m2"]
    F = si["environment_factor"]
    expected_Q_W_pcs = 43192.0 * F * (A ** 0.82)

    # Fixture expected value
    fixture_Q_W = exp["pcs_Q_W_expected_algebraic"]
    xls_Q_W = exp["xls_Q_W"]

    # Tautology: PCS hand-computation vs fixture expected (algebraic identity)
    # Note: rel=1e-10 (not 1e-12) to absorb JSON-stored value precision
    assert expected_Q_W_pcs == pytest.approx(fixture_Q_W, rel=1e-10), (
        f"手算 Q_W={expected_Q_W_pcs!r} ≠ fixture Q_W={fixture_Q_W!r}"
    )

    # PCS service call
    inp = _build_input(case)
    result = calc_api2000_relief_capacity(inp)

    # 1) Q_W matches PCS algebraic identity EXACT (rel=1e-10 to absorb JSON precision)
    assert result.required_relief_rate_w == pytest.approx(expected_Q_W_pcs, rel=1e-10), (
        f"PCS Q_W={result.required_relief_rate_w!r} ≠ FIRE formula={expected_Q_W_pcs!r}"
    )

    # 2) Q_W matches XLS F19 within 经验 1% (actual 0.0185% diff — Ruling 8 direct overlap)
    rel_diff = abs(result.required_relief_rate_w - xls_Q_W) / xls_Q_W
    assert rel_diff <= 0.01, (
        f"PCS Q_W={result.required_relief_rate_w!r} vs XLS F19={xls_Q_W!r}"
        f" rel_diff={rel_diff:.4%} > 经验 1% 容差 per SPEC §5"
    )

    # 3) Q_W ≈ 1.4e7 W — physical sanity (large tank fire venting requires ~MW heat removal)
    assert 1e7 < result.required_relief_rate_w < 2e7, (
        f"Q_W={result.required_relief_rate_w!r} 不在 (1e7, 2e7) W 物理范围"
    )


# ============================================================================
# 2) Q_m3_h — OUT_OF_SCOPE per Ruling 8 air-equivalent conversion mismatch
# ============================================================================


def test_Q_m3_h_OUT_OF_SCOPE_ruling_8_air_equivalent_conversion_mismatch() -> None:
    """Q_m3_h OUT_OF_SCOPE per Ruling 8: XLS F24=67259 uses air-equivalent basis.

    XLS F24 = 67259.06 Nm³/h of AIR (gas-equivalent volume flow basis Q_W/(L·ρ_air),
    L=334.9 kJ/kg, ρ_air=1.293 kg/Nm³).
    PCS Q_m3_h = Q_W × 0.86 (simple W → m³/h dimensionless conversion, no gas basis).

    Different physical quantities — direct match OUT_OF_SCOPE per Ruling 8.

    This test verifies:
      a) PCS Q_m3_h follows simple W × 0.86 conversion (algebraic identity)
      b) PCS Q_m3_h != XLS F24 (different basis — Ruling 8 OUT_OF_SCOPE)
      c) Magnitude diff is large (PCS/XLS ≈ 178×)
    """
    case = WORLEY["cases"][0]
    si = case["service_inputs"]
    exp = case["expected"]

    # PCS Q_m3_h = Q_W × 0.86 (algebraic identity)
    expected_Q_m3_h_pcs = (
        43192.0 * si["environment_factor"]
        * (si["wetted_area_m2"] ** 0.82) * 0.86
    )

    # Fixture expected value
    fixture_Q_m3_h = exp["pcs_Q_m3_h_expected"]

    # PCS service call
    inp = _build_input(case)
    result = calc_api2000_relief_capacity(inp)

    # 1) PCS Q_m3_h matches algebraic identity EXACT (rel=1e-10 to absorb JSON precision)
    assert result.required_relief_rate_m3_h == pytest.approx(
        expected_Q_m3_h_pcs, rel=1e-10
    ), (
        f"PCS Q_m3_h={result.required_relief_rate_m3_h!r} ≠ Q_W × 0.86={expected_Q_m3_h_pcs!r}"
    )

    # 2) PCS Q_m3_h matches fixture expected (rel=1e-10 to absorb JSON precision)
    assert result.required_relief_rate_m3_h == pytest.approx(fixture_Q_m3_h, rel=1e-10), (
        f"PCS Q_m3_h={result.required_relief_rate_m3_h!r} ≠ fixture Q_m3_h={fixture_Q_m3_h!r}"
    )

    # 3) Ruling 8 OUT_OF_SCOPE: PCS Q_m3_h ≠ XLS F24 (different basis)
    xls_F24_air_equivalent = exp["xls_Q_m3_h_air_OUT_OF_SCOPE"]
    magnitude_ratio = result.required_relief_rate_m3_h / xls_F24_air_equivalent
    assert magnitude_ratio > 100, (
        f"PCS/XLS magnitude ratio={magnitude_ratio:.1f} 应 >> 1 (Ruling 8: 不同 basis)"
        f" PCS={result.required_relief_rate_m3_h!r}"
        f" vs XLS F24={xls_F24_air_equivalent!r}"
    )

    # 4) PCS Q_m3_h magnitude (simple W × 0.86) is much larger than XLS air-equivalent
    #    PCS ≈ 12e6 m³/h vs XLS F24 = 67259 Nm³/h AIR — confirms different basis
    assert result.required_relief_rate_m3_h > 1e7, (
        f"PCS Q_m3_h={result.required_relief_rate_m3_h!r} 应 >> XLS F24=67259"
        f" (Ruling 8 basis mismatch)"
    )


# ============================================================================
# 3) scenario_used — EXACT string 'FIRE'
# ============================================================================


def test_scenario_used_matches_FIRE() -> None:
    """scenario_used = 'FIRE' — EXACT string match (Ruling 8 single scenario overlap).

    PCS service sets scenario_used = inp.scenario; input scenario = 'FIRE'.
    XLS PR-024 'Emergency Venting' block (C10) corresponds to PCS FIRE scenario.
    """
    case = WORLEY["cases"][0]

    inp = _build_input(case)
    result = calc_api2000_relief_capacity(inp)

    # 1) scenario_used EXACT match 'FIRE'
    assert result.scenario_used == "FIRE", (
        f"scenario_used={result.scenario_used!r} 应 'FIRE' (Ruling 8 single scenario overlap)"
    )

    # 2) scenario_used is a string
    assert isinstance(result.scenario_used, str), (
        f"scenario_used type={type(result.scenario_used).__name__} 应 str"
    )


# ============================================================================
# 4) formula_used — EXACT non-empty string containing '43192' + 'API 2000'
# ============================================================================


def test_formula_used_non_empty_and_contains_43192_api2000() -> None:
    """formula_used non-empty string containing '43192' + 'API 2000 7th §3.4 SI'.

    PCS service formula_used for FIRE scenario: 'Q(W) = 43192·F·A^0.82 [API 2000 7th §3.4 SI]'.
    XLS uses identical formula (API 2000 7th §3.4 imperial→SI strict conversion).
    """
    case = WORLEY["cases"][0]

    inp = _build_input(case)
    result = calc_api2000_relief_capacity(inp)

    # 1) formula_used is non-empty string
    assert isinstance(result.formula_used, str), (
        f"formula_used type={type(result.formula_used).__name__} 应 str"
    )
    assert len(result.formula_used) > 0, (
        f"formula_used={result.formula_used!r} 空字符串"
    )

    # 2) formula_used contains '43192' (SI coefficient)
    assert "43192" in result.formula_used, (
        f"formula_used={result.formula_used!r} 应包含 '43192' (SI coefficient)"
    )

    # 3) formula_used contains 'API 2000'
    assert "API 2000" in result.formula_used, (
        f"formula_used={result.formula_used!r} 应包含 'API 2000'"
    )

    # 4) formula_used contains 'A^0.82' (FIRE formula exponent)
    assert "0.82" in result.formula_used, (
        f"formula_used={result.formula_used!r} 应包含 '0.82' (FIRE exponent)"
    )


# ============================================================================
# 5) Service structure sanity + formula_ref + Ruling 8 registration
# ============================================================================


def test_service_returns_valid_result_for_xls_api2000_fire_scenario() -> None:
    """PCS service 对 XLS PR-024 物理场景 (API 2000 FIRE) 应返回合法结果。

    Sanity assertions (independent of value precision — Ruling 8 single scenario overlap):
      - required_relief_rate_w > 0 (FIRE formula)
      - required_relief_rate_m3_h > 0 (FIRE formula × 0.86)
      - scenario_used = 'FIRE'
      - formula_used contains '43192' + 'API 2000'
      - imperial_conversion = None (imperial_units=False)
      - formula_ref keys: fire/vacuum/emergency/wetted_area_source
      - formula_ref.fire_formula 包含 '43192'
      - 不抛异常 (F2 validation passes: V>0, A≥0, P≥0, F∈[0,1])
    """
    case = WORLEY["cases"][0]

    inp = _build_input(case)

    # 不抛异常
    result = calc_api2000_relief_capacity(inp)

    # Q_W > 0 (FIRE formula)
    assert result.required_relief_rate_w > 0.0, (
        f"Q_W={result.required_relief_rate_w!r} 应 > 0 (FIRE formula)"
    )
    assert math.isfinite(result.required_relief_rate_w), (
        f"Q_W={result.required_relief_rate_w!r} 不应 inf"
    )

    # Q_m3_h > 0 (Q_W × 0.86)
    assert result.required_relief_rate_m3_h > 0.0, (
        f"Q_m3_h={result.required_relief_rate_m3_h!r} 应 > 0"
    )
    assert math.isfinite(result.required_relief_rate_m3_h), (
        f"Q_m3_h={result.required_relief_rate_m3_h!r} 不应 inf"
    )

    # scenario_used = 'FIRE'
    assert result.scenario_used == "FIRE"

    # formula_used contains '43192' + 'API 2000'
    assert "43192" in result.formula_used
    assert "API 2000" in result.formula_used

    # imperial_conversion = None (imperial_units=False)
    assert result.imperial_conversion is None, (
        f"imperial_conversion={result.imperial_conversion!r} (imperial_units=False 应 None)"
    )

    # formula_ref keys
    formula_ref = result.formula_ref
    for key in (
        "fire_formula",
        "vacuum_formula",
        "emergency_formula",
        "wetted_area_source",
    ):
        assert key in formula_ref, f"formula_ref 缺键 {key!r}"

    # formula_ref.fire_formula 包含 '43192'
    assert "43192" in formula_ref["fire_formula"], (
        f"formula_ref.fire_formula={formula_ref['fire_formula']!r} 应包含 '43192'"
    )

    # formula_ref.wetted_area_source 提到 inp.wetted_area_m2 (因为 vessel_geometry=None)
    assert "wetted_area_m2" in formula_ref["wetted_area_source"].lower() or (
        "inp.wetted_area_m2" in formula_ref["wetted_area_source"]
    ), (
        f"formula_ref.wetted_area_source={formula_ref['wetted_area_source']!r} "
        f"应提到 inp.wetted_area_m2 (因为 vessel_geometry=None)"
    )


# ============================================================================
# 6) Ruling 8 registration: mapping_defect + root_cause_notes + out_of_scope 必齐
# ============================================================================


def test_worley_c20_root_cause_notes_registered() -> None:
    """fixture.root_cause_notes 必须登记 11 项 (Ruling 8 + 10 子项)."""
    registered = {n["id"] for n in WORLEY["root_cause_notes"]}
    expected_ids = {
        "Ruling_8_single_scenario_overlap_with_air_equivalent_conversion_mismatch",
        "xls_normal_venting_F38_639_Nm3h_air_delegates_to_breathing_valve_service",
        "xls_thermal_venting_F34_F36_best_fit_curve",
        "xls_max_outflow_inflow_F28_F30_normal_venting",
        "xls_tank_capacity_F33_normal_venting_input",
        "xls_flash_or_boiling_point_F31_P42_P43",
        "xls_wetted_area_computation_P8_S28",
        "xls_head_type_table_Q24_S28",
        "xls_multiple_scenarios_fire_vacuum_emergency",
        "xls_elevation_F14_liquid_level_implied_in_wetted_area",
        "xls_pcrit_critical_flow_not_applicable_to_api2000",
    }
    assert registered == expected_ids, (
        f"root_cause_notes 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )


def test_worley_c20_out_of_scope_ledger_complete() -> None:
    """fixture.out_of_scope 必须登记 11 项 (Ruling 8 air-equivalent mismatch + 10 子项)."""
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    expected_ids = {
        "xls_Q_m3_h_air_equivalent_conversion_F24_67259",
        "xls_normal_venting_F38_total_normal_639_Nm3h",
        "xls_thermal_venting_F34_F35_F36_F37",
        "xls_max_liquid_outflow_inflow_F28_F30",
        "xls_tank_capacity_F33_1000_m3",
        "xls_flash_boiling_point_criteria_F31_P42_P43",
        "xls_wetted_area_computation_table_P8_S28",
        "xls_head_type_selection_table_Q24_S28",
        "xls_multiple_scenarios_vacuum_emergency_thermal",
        "xls_elevation_liquid_level_F14_F22",
        "xls_pcrit_critical_flow_not_in_api2000_scope",
    }
    assert registered == expected_ids, (
        f"out_of_scope 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )


def test_worley_c20_ruling_8_registration_complete() -> None:
    """Ruling 8 single scenario overlap + air-equivalent conversion mismatch 三层注册一致性检查:

    1. fixture.mapping_defect.ruling_id == "Ruling_8_single_scenario_overlap_with_..."
    2. root_cause_notes[0].id == "Ruling_8_..." + finding 提及 'single scenario' + 'air-equivalent'
    3. out_of_scope 包含 'xls_Q_m3_h_air_equivalent_conversion_F24_67259'
    4. mapping_defect.implication 显式声明 single scenario overlap + air-equivalent mismatch
    """
    # Layer 1: mapping_defect.ruling_id
    _ruling_id = (
        "Ruling_8_single_scenario_overlap_with_air_equivalent_conversion_mismatch"
    )
    assert WORLEY["mapping_defect"]["ruling_id"] == _ruling_id, (
        f"mapping_defect.ruling_id={WORLEY['mapping_defect']['ruling_id']!r} "
        f"(应为 {_ruling_id})"
    )

    # Layer 2: root_cause_notes 必含 single scenario + air-equivalent
    primary_note = next(
        n for n in WORLEY["root_cause_notes"]
        if n["id"] == _ruling_id
    )
    finding_lower = primary_note["finding"].lower()
    assert "single scenario" in finding_lower or "fire scenario only" in finding_lower, (
        "Ruling_8 root_cause finding 必须提及 'single scenario' 或 'fire scenario only' "
        "(SINGLE SCENARIO OVERLAP)"
    )
    assert "air-equivalent" in finding_lower or "air equivalent" in finding_lower, (
        "Ruling_8 root_cause finding 必须提及 'air-equivalent' (CONVERSION MISMATCH)"
    )
    assert "0.0185%" in finding_lower or "经验 1%" in finding_lower, (
        "Ruling_8 root_cause finding 必须提及容差 '0.0185%' 或 '经验 1%'"
    )

    # Layer 3: out_of_scope 必含 Q_m3_h air-equivalent (Ruling 8 核心 OOS)
    oos_ids = {o["id"] for o in WORLEY["out_of_scope"]}
    assert "xls_Q_m3_h_air_equivalent_conversion_F24_67259" in oos_ids, (
        "out_of_scope 必须包含 xls_Q_m3_h_air_equivalent_conversion_F24_67259 "
        "(Ruling 8 核心 OOS)"
    )

    # Layer 4: mapping_defect.implication 显式声明 single scenario overlap + air-equivalent
    impl = WORLEY["mapping_defect"]["implication"].lower()
    assert "single scenario" in impl or "fire scenario only" in impl or (
        "direct overlap" in impl and "fire" in impl
    ), (
        "mapping_defect.implication 必须显式声明 'single scenario' 或 "
        "'fire scenario only' 或 'direct overlap = fire scenario only' "
        "(SINGLE SCENARIO OVERLAP)"
    )
    assert "air-equivalent" in impl or "air equivalent" in impl, (
        "mapping_defect.implication 必须显式声明 'air-equivalent' "
        "(CONVERSION MISMATCH)"
    )


def test_worley_c20_fixture_structure_basics() -> None:
    """fixture JSON 顶层键健全性: source/mapping_defect/tolerance_policy/unit_conversion_factors/
    xls_workbook/cases/root_cause_notes/out_of_scope 必齐; case 顶层键必齐。"""
    for k in (
        "source",
        "mapping_defect",
        "tolerance_policy",
        "unit_conversion_factors",
        "xls_workbook",
        "cases",
        "root_cause_notes",
        "out_of_scope",
    ):
        assert k in WORLEY, f"fixture 缺顶层键 {k!r}"
    assert "service" in WORLEY["source"]
    assert "ruling_id" in WORLEY["mapping_defect"]
    _ruling_id_ck = (
        "Ruling_8_single_scenario_overlap_with_air_equivalent_conversion_mismatch"
    )
    assert WORLEY["mapping_defect"]["ruling_id"] == _ruling_id_ck
    assert len(WORLEY["cases"]) == 1, (
        f"cases={len(WORLEY['cases'])} (XLS PR-024 是 single case)"
    )

    # unit_conversion_factors 必含 3 项 + xls_unit_check_* 多项
    ucf = WORLEY["unit_conversion_factors"]
    for k in (
        "mm_to_m",
        "bar_to_kpa",
        "kj_per_kg_to_j_per_kg",
        "xls_unit_check_F11",
        "xls_unit_check_F12",
        "xls_unit_check_F17",
        "xls_unit_check_F18",
        "xls_unit_check_F19",
        "xls_unit_check_F24",
        "xls_unit_check_F33",
    ):
        assert k in ucf, f"unit_conversion_factors 缺键 {k!r}"

    # single case 顶层键必齐
    case = WORLEY["cases"][0]
    for k in (
        "id",
        "sheet",
        "xls_inputs",
        "xls_outputs",
        "service_inputs",
        "input_assumptions",
        "expected",
        "per_field_tolerance",
        "tolerance",
    ):
        assert k in case, f"case 缺顶层键 {k!r}"