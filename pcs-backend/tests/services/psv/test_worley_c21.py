"""P6-6A Task 13: C-21 PSV AS 1210 火灾/管破裂/控制阀失效工况 vs Worley 真实算例
WS-CA-PR-025 对账测试。

数据源: sample/Process caculation from Worley/…/WS-CA-PR-025.xls (gitignored 只读);
提取 dump: .superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-025.json
fixture: tests/services/psv/fixtures/worley_c21_as1210.json
(含 Worley 原始输入 cell 坐标、单位换算链、Ruling 9 formula family mismatch 登记、
容差分级与放宽理由)

⚠️ **MAJOR FORMULA FAMILY MISMATCH — Ruling 9 (2nd surface, C-17 was 1st surface)**

XLS-PR-025 Calculation Sheet: **AS 1210 §4.4 + AS 1797 + API 520 combined relief sizing**
(Natural Gas liquefied vessel, Sheet 'SI' 293 rows × 47 cols).
PCS service `calc_as1210_relief_sizing`:
**AS 1210 §4.3.1 + §4.3.2 + §4.4 fire case (subset)** per SPEC §3.7.2 V1.4.

XLS uses TWO paths (Natural Gas liquefied + non-liquefied):
  - API 520 path (G26=C_API=323.66, G33=14.666 m², G34=390.72 kW, G35=6766 kg/hr)
  - AS 1210 path (G27=C_AS1210=2.457, G53=14.628 m², G54=649.81 kW, G55=11253 kg/hr)

PCS service hardcodes API 521 coefficient 43192 (corresponds to XLS API 520 path C_API=323.66
SI strict conversion) + ΔH_vap=2260 kJ/kg (typical light hydrocarbon/water simplification).

**Direct overlap** (经验 1% 容差 per SPEC §5):
  - Input chain (vessel geometry → A_wetted via C-12 calc_wetted_area —
    XLS G33 EXACT match with H_m=1.867m)
  - q_fire_w = 43192·F·A^0.82 SI matches XLS API 520 path G34 within 经验 1%
    (0.0185% diff)
  - set_p formula (TUBE_RUPTURE + CONTROL_VALVE_FAILURE — algebraic EXACT)
  - formula_ref sanity

**OUT_OF_SCOPE** (per Ruling 9 + 14 sub-features):
  - FIRE_CASE q_fire_w vs XLS AS 1210 path G54 (Ruling 9: C_AS1210=2.457
    different basis → 1.66× magnitude diff)
  - FIRE_CASE capacity vs XLS G55/G57 (Ruling 9: ΔH_vap≈208 kJ/kg vs PCS 2260
    → 18× magnitude diff)
  - Tube rupture XLS F78-F88 (AS 1797 derivation)
  - Flashing liquid relief F73-F93 (WL+WV simultaneous equations)
  - Vapour/liquid split V83-Z93
  - LNG/non-LNG differentiation (XLS row 30 vs row 50)
  - Pressure factor selection (1.10/1.20)
  - Critical flow pressure G80
  - MAWP derivation XLS row 42-49
  - Fire env factor F differentiation
  - Liquid level above grade F23
  - Wetted area Kd + relief valve area G36/G56/G63
  - Exposed vessel surface area G44
  - Gas density / mass in vessel G65/G66

SPEC §5 分级: C-21 经验 1% (rel≤0.01); 本批因 Ruling 9 MAJOR formula family
mismatch (2nd surface) — PCS API 521 path matches XLS API 520 path (G34 within
经验 1%, actual 0.0185%) but NOT XLS AS 1210 path (G54 magnitude diff 39%,
G55 18× diff). 经验 1% 容差 used for input chain + q_fire_w vs XLS API 520
path G34 only; XLS AS 1210 path G54/G55 完全 OUT_OF_SCOPE per Ruling 9. set_p
algebraic EXACT; formula_ref EXACT non-empty string; scenario_used /
as_standard / pressure_factor EXACT.

处置结论: 全部通过 (input chain EXACT + q_fire_w within 经验 1% vs XLS API 520
path + set_p algebraic EXACT + formula_ref EXACT + Ruling 9 登记); 无
Ruling 1(a) 代码修复; root_cause_notes 登记 13 项 (Ruling 9 + 12 子项: tube
rupture F78-F88 / flashing liquid F73-F93 / vapour-liquid split V83-Z93 /
LNG-non-LNG / pressure factor / critical flow / MAWP / env factor F / liquid
level F23 / Kd relief valve area / exposed surface area / gas density mass)
+ out_of_scope 14 项 (q_fire_w G54 + capacity G55 + tube rupture + flashing
liquid + vapour-liquid split + LNG-non-LNG + pressure factor + critical
flow + MAWP + env factor F + liquid level F23 + Kd relief valve area +
exposed surface area + gas density mass).
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

from app.services.psv.as1210_overpressure_service import (  # noqa: E402
    As1210ReliefInput,
    calc_as1210_relief_sizing,
)
from app.services.vessel.vessel_service import (  # noqa: E402
    WettedAreaInput,
    calc_wetted_area,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "worley_c21_as1210.json"
)
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _build_input_fire_case(
    case: dict, delta_h_vap_kj_kg: float | None = None
) -> As1210ReliefInput:
    """Build As1210ReliefInput for FIRE_CASE scenario from case.service_inputs.

    Args:
        case: fixture case dict (worley_c21_as1210.json).
        delta_h_vap_kj_kg: optional fluid-specific ΔH_vap override (kJ/kg).
            If None: don't pass field (use service default 2260 kJ/kg — backward
            compat with T0 era). If float: pass delta_h_vap_kj_kg= explicitly
            to match XLS PR-025 implied ΔH_vap=208 kJ/kg (Ruling 14).
    """
    si = case["service_inputs"]
    vg = si["vessel_geometry"]
    geom = WettedAreaInput(
        D_m=vg["D_m"],
        L_m=vg["L_m"],
        head_type=vg["head_type"],
        H_m=vg["H_m"],
        n_vessels=vg["n_vessels"],
        vessel_shape=vg["vessel_shape"],
    )
    kwargs = dict(
        mawp_kpa=si["mawp_kpa"],
        tube_rupture_mass_kg_s=si["tube_rupture_mass_kg_s"],
        control_valve_failure_mode=si["control_valve_failure_mode"],
        fire_case_wetted_area_m2=si["fire_case_wetted_area_m2"],
        as1210_pressure_factor=si["as1210_pressure_factor"],
        scenario="FIRE_CASE",
        vessel_geometry=geom,
        environment_factor=si["environment_factor"],
        imperial_units=si["imperial_units"],
    )
    if delta_h_vap_kj_kg is not None:
        kwargs["delta_h_vap_kj_kg"] = delta_h_vap_kj_kg
    return As1210ReliefInput(**kwargs)


def _build_input_tube_rupture(case: dict) -> As1210ReliefInput:
    """Build As1210ReliefInput for TUBE_RUPTURE scenario from case.service_inputs."""
    si = case["service_inputs"]
    return As1210ReliefInput(
        mawp_kpa=si["mawp_kpa"],
        tube_rupture_mass_kg_s=si["tube_rupture_mass_kg_s"],
        control_valve_failure_mode=si["control_valve_failure_mode"],
        fire_case_wetted_area_m2=si["fire_case_wetted_area_m2"],
        as1210_pressure_factor=si["as1210_pressure_factor"],
        scenario="TUBE_RUPTURE",
        vessel_geometry=None,
        environment_factor=si["environment_factor"],
        imperial_units=si["imperial_units"],
    )


def _build_input_cv_failure(case: dict, cv_mode: str) -> As1210ReliefInput:
    """Build As1210ReliefInput for CONTROL_VALVE_FAILURE scenario from case.service_inputs."""
    si = case["service_inputs"]
    return As1210ReliefInput(
        mawp_kpa=si["mawp_kpa"],
        tube_rupture_mass_kg_s=si["tube_rupture_mass_kg_s"],
        control_valve_failure_mode=cv_mode,
        fire_case_wetted_area_m2=si["fire_case_wetted_area_m2"],
        as1210_pressure_factor=si["as1210_pressure_factor"],
        scenario="CONTROL_VALVE_FAILURE",
        vessel_geometry=None,
        environment_factor=si["environment_factor"],
        imperial_units=si["imperial_units"],
    )


# ============================================================================
# 1) Input chain — A_wetted via C-12 calc_wetted_area matches XLS G33 EXACTLY
# ============================================================================


def test_input_chain_via_C12_calc_wetted_area_matches_xls_G33() -> None:
    """Input chain (vessel geometry → A_wetted via C-12 calc_wetted_area) matches XLS G33 EXACT.

    XLS G33 = 14.666481633974485 m² (API 520 path wetted area).
    PCS C-12 calc_wetted_area with WettedAreaInput(D_m=2.5, L_m=10.0, head_type='FLAT',
    H_m=1.8673944398508298, vessel_shape='VERTICAL') produces wetted_area_m2 =
    14.666481633974485 m² (matches XLS G33 EXACTLY via π·D·H).

    This is the **direct overlap** field per Ruling 9 — input chain via D7 接口冻结
    (calc_wetted_area, ADR-0041 v7).

    H_liquid = 1.867m implied by XLS G33 = π·D·H_liquid → H_liquid = 14.666/(π·2.5) = 1.867m.
    PCS service then uses this A_wetted for q_fire_w calculation (FIRE_CASE).
    """
    case = WORLEY["cases"][0]
    si = case["service_inputs"]
    vg = si["vessel_geometry"]
    exp = case["expected"]

    # Hand-compute PCS A_wetted from C-12 calc_wetted_area
    geom = WettedAreaInput(
        D_m=vg["D_m"],
        L_m=vg["L_m"],
        head_type=vg["head_type"],
        H_m=vg["H_m"],
        n_vessels=vg["n_vessels"],
        vessel_shape=vg["vessel_shape"],
    )
    wa_result = calc_wetted_area(geom)

    # 1) A_wet matches XLS G33 EXACTLY (rel=1e-12 to absorb JSON-stored double precision)
    assert wa_result.wetted_area_m2 == pytest.approx(exp["xls_Awet_API_G33"], rel=1e-12), (
        f"PCS C-12 A_wet={wa_result.wetted_area_m2!r} ≠ XLS G33={exp['xls_Awet_API_G33']!r}"
    )

    # 2) PCS service uses this A_wet in FIRE_CASE formula_ref (D7 接口冻结)
    inp = _build_input_fire_case(case)
    result = calc_as1210_relief_sizing(inp)

    # PCS service q_fire_w = 43192 × 1.0 × A_wet^0.82 — should use the C-12-computed A_wet
    expected_q_fire_w_pcs = 43192.0 * si["environment_factor"] * (
        wa_result.wetted_area_m2 ** 0.82
    )
    assert result.required_relief_capacity_kg_s == pytest.approx(
        expected_q_fire_w_pcs / (2260.0 * 1000.0), rel=1e-10
    ), (
        f"PCS capacity={result.required_relief_capacity_kg_s!r} 应基于 C-12 A_wet"
        f"={wa_result.wetted_area_m2!r} (Ruling 9 input chain)"
    )

    # 3) A_wet ≈ 14.67 m² — physical sanity (small vessel, ~2.5m × 1.867m cylinder area)
    assert 10.0 < wa_result.wetted_area_m2 < 20.0, (
        f"A_wet={wa_result.wetted_area_m2!r} 应 ∈ (10, 20) m² 物理范围"
    )


# ============================================================================
# 2) FIRE_CASE q_fire_w — direct overlap within 经验 1% vs XLS API 520 path G34
# ============================================================================


def test_fire_case_q_fire_w_within_experience_1pct_vs_xls_API_520_path_G34() -> None:
    """FIRE_CASE q_fire_w = 43192·F·A^0.82 SI matches XLS API 520 path G34 within 经验 1%.

    XLS G34 = 390724.83806486497 W (API 520 path total heat absorption Q).
    PCS q_fire_w = 43192 × 1.0 × 14.666481633974485^0.82 = 390652.4816133714 W.
    Diff = 0.0185% — within 经验 1% 容差 per SPEC §5.

    This is the **direct overlap** field per Ruling 9 (PCS API 521 path ↔ XLS API 520 path).

    Note: XLS AS 1210 path G54 = 649808.14 W is OUT_OF_SCOPE per Ruling 9
    (C_AS1210=2.457 different formula basis, magnitude diff 1.66×).
    """
    case = WORLEY["cases"][0]
    si = case["service_inputs"]
    exp = case["expected"]

    # Hand-compute PCS q_fire_w from C-12 A_wet and F input
    vg = si["vessel_geometry"]
    geom = WettedAreaInput(
        D_m=vg["D_m"],
        L_m=vg["L_m"],
        head_type=vg["head_type"],
        H_m=vg["H_m"],
        n_vessels=vg["n_vessels"],
        vessel_shape=vg["vessel_shape"],
    )
    wa_result = calc_wetted_area(geom)
    A = wa_result.wetted_area_m2
    F = si["environment_factor"]
    expected_q_fire_w_pcs_W = 43192.0 * F * (A ** 0.82)

    # PCS service call (FIRE_CASE scenario)
    inp = _build_input_fire_case(case)
    result = calc_as1210_relief_sizing(inp)

    # 1) PCS q_fire_w matches algebraic identity EXACT (rel=1e-10 to absorb JSON precision)
    # capacity = q_fire_w / (ΔH_vap × 1000) → q_fire_w = capacity × ΔH_vap × 1000
    implied_q_fire_w_pcs = result.required_relief_capacity_kg_s * 2260.0 * 1000.0
    assert implied_q_fire_w_pcs == pytest.approx(expected_q_fire_w_pcs_W, rel=1e-10), (
        f"PCS q_fire_w (implied from capacity)={implied_q_fire_w_pcs!r} ≠ "
        f"algebraic 43192·F·A^0.82={expected_q_fire_w_pcs_W!r}"
    )

    # 2) PCS q_fire_w matches XLS API 520 path G34 within 经验 1% (actual 0.0185% diff)
    rel_diff = abs(expected_q_fire_w_pcs_W - exp["xls_Q_API_G34_W"]) / exp["xls_Q_API_G34_W"]
    assert rel_diff <= 0.01, (
        f"PCS q_fire_w={expected_q_fire_w_pcs_W!r} vs XLS API G34={exp['xls_Q_API_G34_W']!r}"
        f" rel_diff={rel_diff:.4%} > 经验 1% 容差 per SPEC §5"
    )

    # 3) Ruling 9 OUT_OF_SCOPE: PCS q_fire_w ≠ XLS AS 1210 path G54 (different basis)
    magnitude_diff = exp["xls_Q_AS1210_G54_W_OUT_OF_SCOPE"] / expected_q_fire_w_pcs_W
    assert magnitude_diff > 1.5, (
        f"PCS/XLS AS1210 magnitude diff={magnitude_diff:.3f} 应 >> 1"
        f" (Ruling 9: C_AS1210 vs C_API521)"
        f" PCS q_fire_w={expected_q_fire_w_pcs_W!r}"
        f" vs XLS AS1210 G54={exp['xls_Q_AS1210_G54_W_OUT_OF_SCOPE']!r}"
    )

    # 4) PCS capacity ≈ 622 kg/hr — physical sanity
    capacity_kg_hr = result.required_relief_capacity_kg_s * 3600.0
    assert 600 < capacity_kg_hr < 650, (
        f"PCS capacity={capacity_kg_hr!r} kg/hr 应 ∈ (600, 650) 物理范围"
    )


# ============================================================================
# 3) set_p TUBE_RUPTURE — algebraic EXACT
# ============================================================================


def test_set_p_tube_rupture_algebraic_exact() -> None:
    """TUBE_RUPTURE set_p = as1210_pressure_factor × MAWP (algebraic EXACT).

    AS 1210 §4.3.1 default: pressure_factor=1.10. With MAWP=1000 kPa, set_p=1100 kPa.
    """
    case = WORLEY["cases"][0]
    si = case["service_inputs"]
    exp = case["expected"]

    inp = _build_input_tube_rupture(case)
    result = calc_as1210_relief_sizing(inp)

    # 1) set_p matches algebraic identity factor × MAWP EXACT (rel=1e-12)
    expected_set_p = si["as1210_pressure_factor"] * si["mawp_kpa"]
    assert result.required_set_pressure_kpa == pytest.approx(
        exp["pcs_set_p_TUBE_RUPTURE_kpa"], rel=1e-12
    ), (
        f"TUBE_RUPTURE set_p={result.required_set_pressure_kpa!r} ≠ algebraic"
        f" {si['as1210_pressure_factor']}×{si['mawp_kpa']}={expected_set_p!r}"
    )

    # 2) capacity = tube_rupture_mass_kg_s (direct)
    assert result.required_relief_capacity_kg_s == pytest.approx(
        si["tube_rupture_mass_kg_s"], rel=1e-12
    ), (
        f"TUBE_RUPTURE capacity={result.required_relief_capacity_kg_s!r} ≠ "
        f"tube_rupture_mass_kg_s={si['tube_rupture_mass_kg_s']!r}"
    )

    # 3) as_standard = 'AS 1210 §4.3.1'
    assert result.as_standard == "AS 1210 §4.3.1", (
        f"as_standard={result.as_standard!r} 应 'AS 1210 §4.3.1'"
    )

    # 4) pressure_factor = input as1210_pressure_factor (1.10)
    assert result.pressure_factor == pytest.approx(si["as1210_pressure_factor"], rel=1e-12), (
        f"pressure_factor={result.pressure_factor!r} ≠ input {si['as1210_pressure_factor']!r}"
    )

    # 5) formula_ref.tube_rupture contains 'AS 1210 §4.3.1' + 'set_p'
    assert "AS 1210 §4.3.1" in result.formula_ref["tube_rupture"], (
        f"formula_ref.tube_rupture={result.formula_ref['tube_rupture']!r}"
        f" 应包含 'AS 1210 §4.3.1'"
    )
    assert "set_p" in result.formula_ref["tube_rupture"].lower(), (
        f"formula_ref.tube_rupture={result.formula_ref['tube_rupture']!r} 应包含 'set_p'"
    )


# ============================================================================
# 4) set_p CONTROL_VALVE_FAILURE — 3 modes algebraic EXACT
# ============================================================================


def test_set_p_control_valve_failure_factors_three_modes() -> None:
    """CONTROL_VALVE_FAILURE set_p = CV factor × MAWP for all 3 modes (algebraic EXACT).

    AS 1210 §4.3.2: AIR_FAIL=1.10 / SIGNAL_FAIL=1.20 (L-2 BLOCKER, most severe) /
    POWER_FAIL=1.15. With MAWP=1000 kPa, set_p = 1100/1200/1150 kPa respectively.
    capacity = tube_rupture_mass_kg_s × _CV_FAIL_CAPACITY_FRACTION (0.5).
    """
    case = WORLEY["cases"][0]
    exp = case["expected"]

    # Test all 3 CV failure modes
    cv_modes = {
        "AIR_FAIL": exp["pcs_set_p_CV_AIR_FAIL_kpa"],
        "SIGNAL_FAIL": exp["pcs_set_p_CV_SIGNAL_FAIL_kpa"],
        "POWER_FAIL": exp["pcs_set_p_CV_POWER_FAIL_kpa"],
    }
    for cv_mode, expected_set_p in cv_modes.items():
        inp = _build_input_cv_failure(case, cv_mode)
        result = calc_as1210_relief_sizing(inp)

        # 1) set_p algebraic EXACT
        assert result.required_set_pressure_kpa == pytest.approx(
            expected_set_p, rel=1e-12
        ), (
            f"CV {cv_mode} set_p={result.required_set_pressure_kpa!r} ≠ "
            f"expected {expected_set_p!r}"
        )

        # 2) capacity = tube_rupture_mass_kg_s × 0.5 (algebraic EXACT)
        assert result.required_relief_capacity_kg_s == pytest.approx(
            exp["pcs_capacity_CV_FAILURE_kg_s"], rel=1e-12
        ), (
            f"CV {cv_mode} capacity={result.required_relief_capacity_kg_s!r} ≠ "
            f"{exp['pcs_capacity_CV_FAILURE_kg_s']!r}"
        )

        # 3) as_standard contains 'AS 1210 §4.3.2' + cv_mode
        assert "AS 1210 §4.3.2" in result.as_standard, (
            f"CV {cv_mode} as_standard={result.as_standard!r} 应包含 'AS 1210 §4.3.2'"
        )
        assert cv_mode in result.as_standard, (
            f"CV {cv_mode} as_standard={result.as_standard!r} 应包含 '{cv_mode}'"
        )

        # 4) pressure_factor = CV mode factor
        if cv_mode == "AIR_FAIL":
            assert result.pressure_factor == pytest.approx(1.10, rel=1e-12)
        elif cv_mode == "SIGNAL_FAIL":
            assert result.pressure_factor == pytest.approx(1.20, rel=1e-12), (
                f"SIGNAL_FAIL pressure_factor={result.pressure_factor!r} 应 1.20 (L-2 BLOCKER)"
            )
        elif cv_mode == "POWER_FAIL":
            assert result.pressure_factor == pytest.approx(1.15, rel=1e-12)

    # 5) SIGNAL_FAIL is most severe (L-2 BLOCKER — factor 1.20 > 1.15 > 1.10)
    assert cv_modes["SIGNAL_FAIL"] > cv_modes["POWER_FAIL"] > cv_modes["AIR_FAIL"], (
        f"SIGNAL_FAIL 应最严重: AIR={cv_modes['AIR_FAIL']}, POWER={cv_modes['POWER_FAIL']},"
        f" SIGNAL={cv_modes['SIGNAL_FAIL']}"
    )

    # 6) formula_ref.control_valve_failure 包含 'AIR_FAIL' + 'SIGNAL_FAIL' + 'POWER_FAIL' + '1.20'
    inp_signal = _build_input_cv_failure(case, "SIGNAL_FAIL")
    result_signal = calc_as1210_relief_sizing(inp_signal)
    cv_ref = result_signal.formula_ref["control_valve_failure"]
    assert "AIR_FAIL" in cv_ref
    assert "SIGNAL_FAIL" in cv_ref
    assert "POWER_FAIL" in cv_ref
    assert "1.2" in cv_ref or "1.20" in cv_ref, (
        f"formula_ref.control_valve_failure={cv_ref!r} 应包含 '1.20' (SIGNAL_FAIL factor)"
    )


# ============================================================================
# 5) FIRE_CASE formula_ref + service structure sanity + Ruling 9 registration
# ============================================================================


def test_fire_case_formula_ref_and_service_structure_with_ruling_9() -> None:
    """FIRE_CASE formula_ref sanity + Ruling 9 OUT_OF_SCOPE registration.

    PCS service formula_ref.fire_formula contains '43192' + 'AS 1210' + '2260' + '0.82'.
    PCS as_standard = 'AS 1210 §4.4 + API 521 §3.4' (Ruling 9: PCS uses API 521 not AS 1210 path).
    PCS capacity differs from XLS AS 1210 path G55 by 18× magnitude (Ruling 9: ΔH_vap mismatch).
    """
    case = WORLEY["cases"][0]
    si = case["service_inputs"]
    exp = case["expected"]

    inp = _build_input_fire_case(case)
    result = calc_as1210_relief_sizing(inp)

    # 1) formula_ref.fire_formula contains '43192' + 'AS 1210' + '0.82'
    fire_formula = result.formula_ref["fire_case"]
    assert "43192" in fire_formula, (
        f"formula_ref.fire_case={fire_formula!r} 应包含 '43192' (SI coefficient)"
    )
    assert "AS 1210" in fire_formula, (
        f"formula_ref.fire_case={fire_formula!r} 应包含 'AS 1210'"
    )
    assert "0.82" in fire_formula, (
        f"formula_ref.fire_case={fire_formula!r} 应包含 '0.82' (FIRE exponent)"
    )
    assert "2260" in fire_formula or "ΔH_vap" in fire_formula, (
        f"formula_ref.fire_case={fire_formula!r} 应包含 '2260' 或 'ΔH_vap' (Ruling 9 hardcode)"
    )

    # 2) as_standard = 'AS 1210 §4.4 + API 521 §3.4' (Ruling 9: PCS uses API 521 not AS 1210 path)
    assert result.as_standard == "AS 1210 §4.4 + API 521 §3.4", (
        f"as_standard={result.as_standard!r} 应 'AS 1210 §4.4 + API 521 §3.4' (Ruling 9)"
    )

    # 3) Ruling 9: PCS capacity << XLS AS 1210 path G55 (magnitude diff 18×)
    capacity_kg_hr = result.required_relief_capacity_kg_s * 3600.0
    magnitude_diff = exp["xls_relief_AS1210_G55_kg_hr_OUT_OF_SCOPE"] / capacity_kg_hr
    assert magnitude_diff > 10, (
        f"Ruling 9: PCS/XLS capacity magnitude diff={magnitude_diff:.1f}"
        f" 应 > 10 (ΔH_vap mismatch)"
        f" PCS={capacity_kg_hr!r} kg/hr vs XLS G55="
        f"{exp['xls_relief_AS1210_G55_kg_hr_OUT_OF_SCOPE']!r}"
    )

    # 4) imperial_conversion = None (imperial_units=False)
    assert result.imperial_conversion is None, (
        f"imperial_conversion={result.imperial_conversion!r} (imperial_units=False 应 None)"
    )

    # 5) formula_ref 4 keys: tube_rupture / control_valve_failure / fire_case / wetted_area_source
    for key in (
        "tube_rupture",
        "control_valve_failure",
        "fire_case",
        "wetted_area_source",
    ):
        assert key in result.formula_ref, f"formula_ref 缺键 {key!r}"

    # 6) formula_ref.wetted_area_source mentions C-12 calc_wetted_area + vessel_geometry
    wa_source = result.formula_ref["wetted_area_source"]
    assert "calc_wetted_area" in wa_source or "C-12" in wa_source, (
        f"formula_ref.wetted_area_source={wa_source!r} 应提到 C-12 calc_wetted_area"
    )
    assert "vessel_geometry" in wa_source, (
        f"formula_ref.wetted_area_source={wa_source!r} 应提到 vessel_geometry"
    )

    # 7) Ruling 9 implied ΔH_vap from XLS AS 1210 path (sanity check on magnitude diff root cause)
    # XLS Q_G54 × 3600 / relief_G55 = 649808.14 × 3600 / (11253.17 × 1000) = 207.88 kJ/kg
    assert exp["implied_dh_vap_xls_kj_kg"] == pytest.approx(207.88, rel=1e-3), (
        f"XLS implied ΔH_vap={exp['implied_dh_vap_xls_kj_kg']!r} 应 ≈ 207.88 kJ/kg (Ruling 9)"
    )

    # 8) Pressure factor = input as1210_pressure_factor (1.10)
    assert result.pressure_factor == pytest.approx(si["as1210_pressure_factor"], rel=1e-12)

    # 9) capacity > 0 and finite
    assert result.required_relief_capacity_kg_s > 0.0
    assert math.isfinite(result.required_relief_capacity_kg_s)
    assert result.required_set_pressure_kpa > 0.0
    assert math.isfinite(result.required_set_pressure_kpa)


# ============================================================================
# 6) Ruling 9 registration: mapping_defect + root_cause_notes + out_of_scope 必齐
# ============================================================================


def test_worley_c21_root_cause_notes_registered() -> None:
    """fixture.root_cause_notes 必须登记 13 项 (Ruling 9 + 12 子项)."""
    registered = {n["id"] for n in WORLEY["root_cause_notes"]}
    expected_ids = {
        "Ruling_9_formula_family_mismatch_xls_as1210_path_vs_pcs_api521_hardcode",
        "xls_tube_rupture_F78_F88_AS1797_derivation",
        "xls_flashing_liquid_relief_F73_F93_WL_WV_simultaneous",
        "xls_vapour_liquid_relief_split_V83_Z93",
        "xls_LNG_non_LNG_differentiation_row_30_vs_row_50",
        "xls_pressure_factor_selection_G78_10pct",
        "xls_critical_flow_pressure_G80_2982",
        "xls_MAWP_derivation_row_42_49",
        "xls_fire_exposure_env_factor_F_API521_vs_AS1210",
        "xls_liquid_level_above_grade_F23",
        "xls_wetted_area_table_Kd_relief_valve_area_G63_G36_G56",
        "xls_exposed_vessel_surface_area_G44_92",
        "xls_gas_density_mass_in_vessel_G65_G66",
    }
    assert registered == expected_ids, (
        f"root_cause_notes 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )


def test_worley_c21_out_of_scope_ledger_complete() -> None:
    """fixture.out_of_scope 必须登记 14 项 (Ruling 9 + 13 子项)."""
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    expected_ids = {
        "xls_fire_case_q_fire_w_bit_for_bit_vs_G54_AS1210_path",
        "xls_fire_case_capacity_bit_for_bit_vs_G55_G57_AS1210_path",
        "xls_tube_rupture_F78_F88_AS1797_derivation",
        "xls_flashing_liquid_relief_F73_F93_WL_WV",
        "xls_vapour_liquid_relief_split_V83_Z93",
        "xls_LNG_non_LNG_differentiation_row_30_vs_row_50",
        "xls_pressure_factor_selection_G78_1p10",
        "xls_critical_flow_pressure_G80_2982",
        "xls_MAWP_derivation_row_42_49",
        "xls_fire_exposure_env_factor_F_API521_vs_AS1210",
        "xls_liquid_level_above_grade_F23",
        "xls_wetted_area_table_Kd_relief_valve_area_G36_G56_G63",
        "xls_exposed_vessel_surface_area_G44_92",
        "xls_gas_density_mass_in_vessel_G65_G66",
    }
    assert registered == expected_ids, (
        f"out_of_scope 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )


def test_worley_c21_ruling_9_registration_complete() -> None:
    """Ruling 9 MAJOR formula family mismatch 三层注册一致性检查:

    1. fixture.mapping_defect.ruling_id == "Ruling_9_formula_family_mismatch_xls_as1210_path_..."
    2. root_cause_notes[0].id == "Ruling_9_..." + finding 提及 'formula family mismatch'
       + 'C_AS1210' + 'ΔH_vap' + '2260'
    3. out_of_scope 包含 'xls_fire_case_q_fire_w_bit_for_bit_vs_G54_AS1210_path' (核心 OOS)
    4. mapping_defect.implication 显式声明 'MAJOR FORMULA FAMILY MISMATCH' + 'C_AS1210'
       + 'ΔH_vap' + '经验 1%'
    """
    # Layer 1: mapping_defect.ruling_id
    _ruling_id = (
        "Ruling_9_formula_family_mismatch_xls_as1210_path_vs_pcs_api521_hardcode"
    )
    assert WORLEY["mapping_defect"]["ruling_id"] == _ruling_id, (
        f"mapping_defect.ruling_id={WORLEY['mapping_defect']['ruling_id']!r} "
        f"(应为 {_ruling_id})"
    )

    # Layer 2: root_cause_notes 必含 formula family mismatch + C_AS1210 + ΔH_vap + 2260
    primary_note = next(
        n for n in WORLEY["root_cause_notes"]
        if n["id"] == _ruling_id
    )
    finding_lower = primary_note["finding"].lower()
    assert "major formula family mismatch" in finding_lower or (
        "formula family mismatch" in finding_lower
    ), (
        "Ruling_9 root_cause finding 必须提及 'MAJOR FORMULA FAMILY MISMATCH' 或 "
        "'formula family mismatch'"
    )
    assert "c_as1210" in finding_lower, (
        "Ruling_9 root_cause finding 必须提及 'C_AS1210' (XLS AS 1210 coefficient)"
    )
    assert "δh_vap" in finding_lower or "dh_vap" in finding_lower or "δhvap" in finding_lower, (
        "Ruling_9 root_cause finding 必须提及 'ΔH_vap' 或 'dh_vap'"
    )
    assert "2260" in primary_note["finding"], (
        "Ruling_9 root_cause finding 必须提及 '2260' (PCS hardcoded ΔH_vap)"
    )

    # Layer 3: out_of_scope 必含 FIRE_CASE q_fire_w vs G54 + capacity vs G55 (Ruling 9 核心 OOS)
    oos_ids = {o["id"] for o in WORLEY["out_of_scope"]}
    assert "xls_fire_case_q_fire_w_bit_for_bit_vs_G54_AS1210_path" in oos_ids, (
        "out_of_scope 必须包含 xls_fire_case_q_fire_w_bit_for_bit_vs_G54_AS1210_path "
        "(Ruling 9 核心 OOS #1 — q_fire_w G54 magnitude diff)"
    )
    assert "xls_fire_case_capacity_bit_for_bit_vs_G55_G57_AS1210_path" in oos_ids, (
        "out_of_scope 必须包含 xls_fire_case_capacity_bit_for_bit_vs_G55_G57_AS1210_path "
        "(Ruling 9 核心 OOS #2 — capacity G55 magnitude diff 18×)"
    )

    # Layer 4: mapping_defect.implication 显式声明 MAJOR FORMULA FAMILY MISMATCH +
    # C_AS1210 + 经验 1%
    impl = WORLEY["mapping_defect"]["implication"]
    assert "MAJOR FORMULA FAMILY MISMATCH" in impl or (
        "major formula family mismatch" in impl.lower()
    ), (
        "mapping_defect.implication 必须显式声明 'MAJOR FORMULA FAMILY MISMATCH'"
    )
    assert "C_AS1210" in impl, (
        "mapping_defect.implication 必须显式声明 'C_AS1210'"
    )
    assert "经验 1%" in impl or "经验" in impl, (
        "mapping_defect.implication 必须显式声明 '经验 1%' (容差 per SPEC §5)"
    )


def test_worley_c21_fixture_structure_basics() -> None:
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
        "Ruling_9_formula_family_mismatch_xls_as1210_path_vs_pcs_api521_hardcode"
    )
    assert WORLEY["mapping_defect"]["ruling_id"] == _ruling_id_ck
    assert len(WORLEY["cases"]) == 1, (
        f"cases={len(WORLEY['cases'])} (XLS PR-025 SI sheet 是 single case)"
    )

    # unit_conversion_factors 必含 3 项 + xls_unit_check_* 多项
    ucf = WORLEY["unit_conversion_factors"]
    for k in (
        "mm_to_m",
        "kw_to_w",
        "kg_per_hr_to_kg_per_s",
        "xls_unit_check_G20",
        "xls_unit_check_G21",
        "xls_unit_check_G22",
        "xls_unit_check_G23",
        "xls_unit_check_G24",
        "xls_unit_check_G25",
        "xls_unit_check_G26",
        "xls_unit_check_G27",
        "xls_unit_check_G28",
        "xls_unit_check_G33",
        "xls_unit_check_G34",
        "xls_unit_check_G35",
        "xls_unit_check_G53",
        "xls_unit_check_G54",
        "xls_unit_check_G55",
        "xls_unit_check_G63",
        "xls_unit_check_G64",
        "xls_unit_check_G78",
        "xls_unit_check_G79",
        "xls_unit_check_G80",
        "h_liquid_implied_m",
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

    # service_inputs 必含 vessel_geometry dict (D7 接口冻结)
    vg = case["service_inputs"]["vessel_geometry"]
    assert vg is not None, "vessel_geometry 应非 None (FIRE_CASE input chain via C-12)"
    for k in (
        "D_m",
        "L_m",
        "head_type",
        "H_m",
        "n_vessels",
        "vessel_shape",
    ):
        assert k in vg, f"vessel_geometry 缺键 {k!r}"


# ============================================================================
# 7) OPEN-P6-6A-5 T2 — FIRE_CASE ΔH_vap=208 matches XLS PR-025 G35 within 经验 1%
# ============================================================================


def test_worley_c21_fire_case_xls_dhvap_208_matches_g35_within_1pct() -> None:
    """OPEN-P6-6A-5 Ruling 14: ΔH_vap fluid-specific field → XLS PR-025 API 520
    path G35 对账（经验 1% 容差 per SPEC §5）。

    XLS API 520 path G35=6766.45 kg/hr (Natural Gas liquefied, ΔH_vap≈208 kJ/kg
    implied per `xls_implied_dh_vap_xls_kj_kg`=207.88 in fixture)。
    PCS 用 _build_input_fire_case(delta_h_vap_kj_kg=208.0) 调 service →
    capacity × 3600 ≈ 6761 kg/hr, diff -0.076%（within 经验 1%）。

    NOTE: XLS AS 1210 path G55=11253.17 kg/hr 是 OUT_OF_SCOPE per Ruling 9
    （formula family mismatch, ΔH_vap 解释不同 — 不是 PCS ΔH_vap=208 对账目标）。
    """
    case = WORLEY["cases"][0]
    exp = case["expected"]

    # XLS PR-025 API 520 path G35=6766.45 kg/hr (target — 对账 PCS ΔH_vap=208)
    _XLS_G35_API520_PATH_KG_HR = 6766.45

    # 显式传 ΔH_vap=208 → PCS FIRE_CASE capacity 对账 XLS API 520 path G35
    inp = _build_input_fire_case(case, delta_h_vap_kj_kg=208.0)
    result = calc_as1210_relief_sizing(inp)

    capacity_kg_hr = result.required_relief_capacity_kg_s * 3600.0
    # PCS 6761 vs XLS G35 6766.45 ≈ 0.076% diff（within 经验 1%）
    assert capacity_kg_hr == pytest.approx(
        _XLS_G35_API520_PATH_KG_HR, rel=1e-2
    ), (
        f"PCS ΔH_vap=208 capacity={capacity_kg_hr!r} kg/hr"
        f" vs XLS G35={_XLS_G35_API520_PATH_KG_HR} diff > 1%"
        f" (Ruling 14 XLS PR-025 对账失败)"
    )
    # Ruling 9 OUT_OF_SCOPE sanity: PCS ΔH_vap=208 应与 XLS AS 1210 path G55
    # magnitude 不同（C_AS1210 不同 basis），不应误判 PASS
    assert capacity_kg_hr < exp["xls_relief_AS1210_G55_kg_hr_OUT_OF_SCOPE"], (
        f"Ruling 9: PCS ΔH_vap=208={capacity_kg_hr!r} kg/hr 应 < "
        f"XLS AS 1210 G55={exp['xls_relief_AS1210_G55_kg_hr_OUT_OF_SCOPE']!r}"
        f" (AS 1210 path magnitude larger)"
    )
    # 物理 sanity：ΔH_vap=208 应比默认 2260 容量大 ~10.9×
    capacity_2260_kg_hr_default = (
        (43192.0 * exp["xls_Awet_API_G33"] ** 0.82) / (2260.0 * 1000.0) * 3600.0
    )
    assert capacity_kg_hr > capacity_2260_kg_hr_default * 10.0, (
        f"ΔH_vap=208 应比默认 2260 容量大 ~10.9×, 实际 ratio="
        f"{capacity_kg_hr / capacity_2260_kg_hr_default:.2f}"
    )

    # formula_ref 透出 ΔH_vap=208
    assert "208" in result.formula_ref["fire_case"], (
        f"formula_ref.fire_case={result.formula_ref['fire_case']!r}"
        f" 应包含 '208' (实际 ΔH_vap)"
    )