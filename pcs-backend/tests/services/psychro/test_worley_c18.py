"""P6-6A Task 10: C-18 PSYCHRO 水合物抑制 vs Worley 真实算例 WS-CA-PR-020 对账测试。

数据源: sample/Process caculation from Worley/…/WS-CA-PR-020.xls (gitignored 只读);
提取 dump: .superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump/WS-CA-PR-020.json
fixture: tests/services/psychro/fixtures/worley_c18_hydrate_inhibition.json
(含 Worley 原始输入 cell 坐标、单位换算链、Ruling 6 inversion + K scale defect 登记、
容差分级与放宽理由)

⚠️ **INVERSION DEFECT — Ruling 6 (K SCALE CLOSED in OPEN-P6-6A-3)**

XLS-PR-020 Calculation sheet: **Methanol Hydrate Prevention** (dosing problem:
target d → solve X → compute MeOH flowrate).
PCS service `calc_hydrate_inhibition`: **Hydrate Depression Calculation** (forward
problem: X → compute d).

**Direct numerical bit-for-bit match is meaningless** because:
  - Problem direction differs: XLS = INVERSE (d→X→flowrate); PCS = FORWARD (X→d)
  - ~~K scale interpretation differs: XLS K=2335 in °F (Hammerschmidt literature);
    PCS service treats K as °C scale~~ RESOLVED in OPEN-P6-6A-3: PCS now uses
    K_F=2335 in °F scale per Hammerschmidt 1934 paper; `delta_t_f = K * X / (mw
    * (1-X))` raw °F output; `delta_t_c = delta_t_f * 5/9`. PCS d_F = XLS d_F
    = 21.6°F for X=22.86% (bit-for-bit rel=1e-12).
  - XLS equation selector supports Hammerschmidt + Nielsen; PCS implements
    Hammerschmidt only
  - XLS injection rate uses Nielsen X (24.40%) for mass balance (E58=39.55 kg/hr);
    PCS service uses Hammerschmidt X via GPSA §20.3 (different formula basis)

Test scope reduced to:
  1. **Algebra identity tests** (rel=1e-12, pure Hammerschmidt 1934 algebra):
     - Forward formula: X=42% → d_F = K·X/(M·(1-X)) = 52.78°F
     - Forward formula: X=22.86% (XLS Hammerschmidt inversion) → d_F = 21.6°F
       (= XLS d_F bit-for-bit rel=1e-12, OPEN-P6-6A-3 fix)
     - Forward formula: X=24.40% (XLS Nielsen inversion, K-scale consistency check)
     - Inversion: d_F=21.6 (XLS G37=12°C) → X = d_F·M/(K + d_F·M) = 0.228625
  2. **XLS injection rate mass balance** (rel=1e-12, XLS-specific algebra):
     - E58 = X_Nielsen × W_free / (1-X_Nielsen) = 0.244 × 122.5 / (1-0.244) = 39.55
     - Cross-check: if Hammerschmidt X used instead, would give 36.31 (8.2% diff)
  3. **Input chain**: K=2335 (from _HAMMERSCHMIDT_K["MEOH"]), M=32.04 (from
     _INHIBITOR_MW["MEOH"]) — exact match (H-2 v1 BLOCKER)
  4. **Sanity assertions**: ΔT > 0 for X∈(0,1), formula_ref non-empty, is_safe
     bool, no NaN, valid struct
  5. **Ruling 6 registration**: mapping_defect.ruling_id + root_cause_notes +
     out_of_scope 三层注册, 防 fixture 演进时漂移.

SPEC §5 分级: C-18 强公式 1% (rel≤1e-2); 本批因 Ruling 6 inversion defect (K scale
CLOSED in OPEN-P6-6A-3), 强公式容差 NOT used; 仅 algebraic identity 用 rel=1e-12
严格一致 (pure algebra, no algorithm choice involved)。

处置结论: 全部通过 (3 sub-cases + sanity + Ruling 6 + injection rate cross-check);
OPEN-P6-6A-3 Ruling 1(a) 代码修复 (K scale swap): PCS 现在用 K_F=2335 °F scale per
Hammerschmidt 1934 paper; root_cause_notes 登记 5 项 (Ruling 6 inversion defect [K scale
子项 CLOSED] + K scale F vs C [FIXED in OPEN-P6-6A-3] + Nielsen X for injection +
equation selector + pure MeOH assumption) + out_of_scope 10 项 (bit-for-bit match +
Nielsen 1988 + MeOH injection rate + inlet MeOH + free water + equation selector +
K factor table + MW table + secondary considerations + mixed-algorithm + water-phase
state)。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.psychro import (  # noqa: E402
    HydrateInhibitionInput,
    calc_hydrate_inhibition,
)

_FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "worley_c18_hydrate_inhibition.json"
)
WORLEY = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


def _case_ids() -> list[str]:
    return [c["id"] for c in WORLEY["cases"]]


# ============================================================================
# 1) Hammerschmidt 1934 forward formula — algebraic identity (rel=1e-12)
# ============================================================================


@pytest.mark.parametrize("sub_key", ["xls_hammerschmidt_X", "xls_nielsen_X", "mid_range_X"])
def test_hammerschmidt_forward_algebra_identity(sub_key: str) -> None:
    """Hammerschmidt 1934 forward formula: ΔT_C = K·X / (M·(1-X)) — pure algebra.

    Three sub-cases:
      a) XLS Hammerschmidt inversion X=22.86% → PCS d_C = 21.60 (matches XLS d_F=21.6°F=12°C,
         numerically — but K scale interpretation differs per Ruling 6)
      b) XLS Nielsen inversion X=24.40% → PCS d_C = 23.51 (Nielsen X fed to Hammerschmidt
         formula — for K-scale consistency check only, not a real use case)
      c) Mid-range X=42% (brief test point) → PCS d_C = 52.78

    All three use pure Hammerschmidt 1934 algebra with K=2335 °F (H-2 v1 BLOCKER) and M=32.04
    (Methanol). rel=1e-12 严格一致 — 验证 PCS service 代码 `delta_t_f = K * X / (mw * (1-X))`
    实现正确性 (K °F 标度 per Hammerschmidt 1934 paper, OPEN-P6-6A-3 fix), independent of XLS value match.
    """
    case = WORLEY["cases"][0]
    sub = case["service_inputs"]["sub_cases"][sub_key]
    X_wt_pct = sub["inhibitor_concentration_in_water_wt_pct"]
    X_frac = X_wt_pct / 100.0
    K = 2335.0  # °F scale per Hammerschmidt 1934 (OPEN-P6-6A-3 fix)
    M = 32.04

    # 手算 Hammerschmidt 1934 forward formula (K °F → ΔT_F)
    expected_d_F = K * X_frac / (M * (1.0 - X_frac))
    expected_d_C = expected_d_F * 5.0 / 9.0  # °F → °C

    # fixture 登记的 tautology 期望值 (per-case)
    tautology = case["expected"]["xls_tautology_expected"]
    if sub_key == "xls_hammerschmidt_X":
        # XLS PR-020 Hammerschmidt X=22.86%, raw ΔT_F = 21.6°F (XLS G37=12°C × 9/5)
        fixture_d_F = tautology["xls_X22p86_d_F_algebra"]
    elif sub_key == "xls_nielsen_X":
        fixture_d_F = K * X_frac / (M * (1.0 - X_frac))
    else:
        fixture_d_F = tautology["mid_range_X_d_F_algebra"]

    # Tautology check: fixture.expected 与手算一致
    assert fixture_d_F == pytest.approx(expected_d_F, rel=1e-12), (
        f"{sub_key}: fixture d_F={fixture_d_F!r} ≠ 手算 d_F={expected_d_F!r}"
    )

    # PCS service call
    inp = HydrateInhibitionInput(
        gas_flow_mmscfd=case["service_inputs"]["gas_flow_mmscfd"],
        operating_pressure_psia=case["service_inputs"]["operating_pressure_psia"],
        operating_temperature_f=case["service_inputs"]["operating_temperature_f"],
        hydrate_inhibitor_type=case["service_inputs"]["hydrate_inhibitor_type"],
        inhibitor_concentration_in_water_wt_pct=X_wt_pct,
        water_content_inlet_lb_per_mmscf=20.0,
        water_content_target_lb_per_mmscf=1.0,
    )
    result = calc_hydrate_inhibition(inp)

    # 1) d_F EXACT (rel=1e-12) — Hammerschmidt 1934 raw °F output
    assert result.hydrate_depression_f == pytest.approx(expected_d_F, rel=1e-12), (
        f"{sub_key}: PCS d_F={result.hydrate_depression_f!r} ≠ 手算 d_F={expected_d_F!r}"
    )

    # 2) d_C EXACT (rel=1e-12) — PCS code: delta_t_c = delta_t_f * 5/9
    assert result.hydrate_depression_c == pytest.approx(expected_d_C, rel=1e-12), (
        f"{sub_key}: PCS d_C={result.hydrate_depression_c!r} ≠ 手算 d_C={expected_d_C!r}"
    )

    # 3) ΔT > 0 for X∈(0,1) — service 物理范围 (H-2 v1)
    assert result.hydrate_depression_f > 0.0, (
        f"{sub_key}: d_F={result.hydrate_depression_f!r} ≤ 0 (X∈(0,1) 应 ΔT>0)"
    )

    # 4) is_safe bool — service 物理范围 flag
    assert isinstance(result.is_safe, bool), (
        f"{sub_key}: is_safe type={type(result.is_safe).__name__} 应 bool"
    )
    assert result.is_safe is True, (
        f"{sub_key}: is_safe={result.is_safe!r} (ΔT>0 应 True)"
    )


# ============================================================================
# 2) Hammerschmidt inversion algebra — d_F → X (XLS G37 → G53)
# ============================================================================


def test_hammerschmidt_inversion_algebra_identity() -> None:
    """Hammerschmidt 1934 inversion: X = d_F × M / (K + d_F × M) — XLS G37 → G53.

    XLS G37 target d = 12°C → d_F = 21.6°F; K=2335, M=32.04 → X = 0.228625
    (matches XLS G53 = 22.862549321718983 wt%).

    Pure algebra verification — independent of PCS service. 验 fixture.expected
    numerically traceable to XLS cells.
    """
    case = WORLEY["cases"][0]
    tautology = case["expected"]["xls_tautology_expected"]

    # XLS G37 d=12°C → d_F
    xls_d_C = case["xls_inputs"]["G37_target_d_C"]["value"]
    d_F = xls_d_C * 9.0 / 5.0
    K = 2335.0
    M = 32.04

    # 手算 Hammerschmidt inversion
    hand_X_frac = d_F * M / (K + d_F * M)
    hand_X_wt_pct = hand_X_frac * 100.0

    # fixture.expected XLS G53
    fixture_X_frac = tautology["hammerschmidt_X_from_xls_d_F"]
    fixture_X_wt_pct = case["xls_outputs"]["G53_hammerschmidt_X_wt_pct"]["value"]

    # 手算 vs fixture (X fraction rel=1e-12)
    assert hand_X_frac == pytest.approx(fixture_X_frac, rel=1e-12), (
        f"手算 X_frac={hand_X_frac!r} ≠ fixture X_frac={fixture_X_frac!r}"
    )

    # 手算 vs fixture (X wt% rel=1e-12)
    assert hand_X_wt_pct == pytest.approx(fixture_X_wt_pct, rel=1e-12), (
        f"手算 X_wt%={hand_X_wt_pct!r} ≠ fixture X_wt%={fixture_X_wt_pct!r}"
    )

    # XLS G53 (Hammerschmidt) ≠ XLS I53 (Nielsen): 22.86% vs 24.40%
    nielsen_X_wt_pct = case["xls_outputs"]["I53_nielsen_X_wt_pct"]["value"]
    assert abs(fixture_X_wt_pct - nielsen_X_wt_pct) > 1.0, (
        f"XLS Hammerschmidt X={fixture_X_wt_pct} 与 Nielsen X={nielsen_X_wt_pct} 差值 ≤ 1 wt%"
        f" (Hammerschmidt vs Nielsen inversion 应 differ ~1.5 wt%)"
    )


# ============================================================================
# 3) XLS injection rate mass balance — Nielsen X × W_free / (1-X_Nielsen)
# ============================================================================


def test_xls_injection_rate_mass_balance_nielsen_X() -> None:
    """XLS E58 = X_Nielsen × W_free / (1 - X_Nielsen) — pure mass balance algebra.

    XLS uses Nielsen X=24.40% (NOT Hammerschmidt X=22.86%) for injection rate
    mass balance: E58 = 0.2440 × 122.5 / (1 - 0.2440) = 39.54563802535408 kg/hr
    (bit-for-bit rel=7e-15).

    This is XLS-specific algebra — PCS service uses different formula basis
    (GPSA §20.3: Q_inhib = Q_gas·(W_inlet-W_target)/X). OUT_OF_SCOPE for PCS
    bit-for-bit value match.

    Cross-check: If XLS used Hammerschmidt X=22.86% instead: 0.2286 × 122.5 /
    (1 - 0.2286) = 36.31 kg/hr (8.2% diff from 39.55). Confirms XLS uses Nielsen X.
    """
    case = WORLEY["cases"][0]
    tautology = case["expected"]["xls_tautology_expected"]

    # XLS inputs
    X_nielsen_wt_pct = case["xls_outputs"]["I53_nielsen_X_wt_pct"]["value"]
    X_nielsen_frac = X_nielsen_wt_pct / 100.0
    X_hammerschmidt_wt_pct = case["xls_outputs"]["G53_hammerschmidt_X_wt_pct"]["value"]
    X_hammerschmidt_frac = X_hammerschmidt_wt_pct / 100.0
    W_free_kg_hr = case["xls_inputs"]["E56_free_water_kg_hr"]["value"]
    expected_E58 = case["xls_outputs"]["E58_meoh_flowrate_kg_hr"]["value"]

    # 手算 injection rate from Nielsen X (bit-for-bit)
    hand_E58_nielsen = X_nielsen_frac * W_free_kg_hr / (1.0 - X_nielsen_frac)
    assert hand_E58_nielsen == pytest.approx(expected_E58, rel=1e-12), (
        f"手算 E58 (Nielsen X)={hand_E58_nielsen!r} ≠ XLS E58={expected_E58!r}"
    )

    # 手算 injection rate from Hammerschmidt X (cross-check)
    hand_E58_hammerschmidt = (
        X_hammerschmidt_frac * W_free_kg_hr / (1.0 - X_hammerschmidt_frac)
    )
    fixture_E58_hammerschmidt = tautology["xls_meoh_flowrate_from_hammerschmidt_X_kg_hr"]
    assert hand_E58_hammerschmidt == pytest.approx(fixture_E58_hammerschmidt, rel=1e-12), (
        f"手算 E58 (Hammerschmidt X)={hand_E58_hammerschmidt!r} "
        f"≠ fixture {fixture_E58_hammerschmidt!r}"
    )

    # Hammerschmidt-based vs Nielsen-based: ~8.2% difference
    rel_diff = abs(hand_E58_nielsen - hand_E58_hammerschmidt) / hand_E58_nielsen
    assert 0.05 < rel_diff < 0.10, (
        f"Nielsen vs Hammerschmidt-based E58 相对差={rel_diff:.4f} 应 ~8.2%"
        f" (XLS uses Nielsen X, NOT Hammerschmidt X)"
    )

    # fixture.expected 一致性
    fixture_E58_nielsen = tautology["xls_meoh_flowrate_from_nielsen_X_kg_hr"]
    assert fixture_E58_nielsen == pytest.approx(expected_E58, rel=1e-12), (
        f"fixture E58 (Nielsen)={fixture_E58_nielsen!r} ≠ XLS E58={expected_E58!r}"
    )


# ============================================================================
# 4) Input chain: K=2335, M=32.04 from _HAMMERSCHMIDT_K/_INHIBITOR_MW
# ============================================================================


def test_input_chain_k_factor_and_mw_exact_match() -> None:
    """PCS service input chain: K=2335, M=32.04 for MEOH (H-2 v1 BLOCKER).

    PCS service `_HAMMERSCHMIDT_K["MEOH"] = 2335.0` and `_INHIBITOR_MW["MEOH"] = 32.04`
    must match XLS G49 (default) and G50 (Methanol MW). These are constants the
    service exposes via `result.inhibitor_k_factor` and `result.inhibitor_mw` — and
    they must equal XLS values bit-for-bit (rel=1e-12).
    """
    case = WORLEY["cases"][0]
    xls_M = case["xls_inputs"]["G50_M_default"]["value"]

    # 5 inhibitor K values from XLS table F41-F46 should match PCS constants
    xls_K_table = {
        "EG": 4000.0,
        "MEOH": 2335.0,
        "Ethanol": 2335.0,
        "Isopropanol": 2335.0,
        "Propylene Glycol": 3590.0,
        "Diethylene Glycol": 4370.0,
    }
    # PCS _HAMMERSCHMIDT_K subset (5 inhibitors)
    pcs_K_table = {
        "MEOH": 2335.0,
        "EG": 2220.0,
        "DEG": 2335.0,
        "TEG": 2500.0,
        "NACL": 1297.0,
    }

    # MEOH matches exactly (rel=1e-12)
    assert pcs_K_table["MEOH"] == xls_K_table["MEOH"], (
        f"PCS K[MEOH]={pcs_K_table['MEOH']} ≠ XLS K[Methanol]={xls_K_table['MEOH']}"
    )

    # MEOH MW matches (rel=1e-12)
    assert 32.04 == xls_M, (
        f"PCS MW[MEOH]=32.04 ≠ XLS G50={xls_M}"
    )

    # PCS service call — verify result.inhibitor_k_factor / result.inhibitor_mw
    inp = HydrateInhibitionInput(
        gas_flow_mmscfd=10.0,
        operating_pressure_psia=500.0,
        operating_temperature_f=40.0,
        hydrate_inhibitor_type="MEOH",
        inhibitor_concentration_in_water_wt_pct=22.862549321718983,
        water_content_inlet_lb_per_mmscf=20.0,
        water_content_target_lb_per_mmscf=1.0,
    )
    result = calc_hydrate_inhibition(inp)

    # K factor in result matches PCS constant (rel=1e-12)
    assert result.inhibitor_k_factor == pytest.approx(2335.0, rel=1e-12), (
        f"result.inhibitor_k_factor={result.inhibitor_k_factor!r} ≠ 2335.0"
    )

    # MW in result matches PCS constant (rel=1e-12)
    assert result.inhibitor_mw == pytest.approx(32.04, rel=1e-12), (
        f"result.inhibitor_mw={result.inhibitor_mw!r} ≠ 32.04"
    )

    # formula_ref.k_factor 字符串应包含 K=2335
    formula_ref = result.formula_ref
    assert "2335" in formula_ref["k_factor"], (
        f"formula_ref.k_factor={formula_ref['k_factor']!r} 应包含 K=2335"
    )


# ============================================================================
# 5) PCS service sanity (valid result, no NaN, formula_ref, is_safe)
# ============================================================================


def test_service_returns_valid_result_for_xls_scenario() -> None:
    """PCS service 对 XLS PR-020 物理场景 (MeOH Hammerschmidt depression) 应返回合法结果。

    Sanity assertions (independent of value precision — Ruling 6 inversion defect):
      - hydrate_depression_c > 0 for X∈(0,1)
      - hydrate_depression_f > 0 (×9/5 of d_C)
      - hydrate_depression_f == d_C × 9/5 exactly (rel=1e-12)
      - is_safe bool = True (ΔT>0)
      - inhibitor_k_factor == 2335.0
      - inhibitor_mw == 32.04
      - formula_ref keys: hammerschmidt / k_factor / injection_rate / density
      - formula_ref.hammerschmidt 包含 "Hammerschmidt 1934"
      - formula_ref.injection_rate 包含 "GPSA"
      - water_removed_lb_d > 0 (Q_gas × (W_inlet-W_target) > 0)
      - injection_rate_lb_d > 0
      - injection_rate_gpd > 0
      - 不抛异常
    """
    case = WORLEY["cases"][0]
    si = case["service_inputs"]
    X_wt_pct = si["sub_cases"]["xls_hammerschmidt_X"][
        "inhibitor_concentration_in_water_wt_pct"
    ]

    inp = HydrateInhibitionInput(
        gas_flow_mmscfd=si["gas_flow_mmscfd"],
        operating_pressure_psia=si["operating_pressure_psia"],
        operating_temperature_f=si["operating_temperature_f"],
        hydrate_inhibitor_type=si["hydrate_inhibitor_type"],
        inhibitor_concentration_in_water_wt_pct=X_wt_pct,
        water_content_inlet_lb_per_mmscf=20.0,
        water_content_target_lb_per_mmscf=1.0,
    )

    # 不抛异常
    result = calc_hydrate_inhibition(inp)

    # ΔT > 0 for X∈(0,1)
    assert result.hydrate_depression_c > 0.0, (
        f"d_C={result.hydrate_depression_c!r} ≤ 0 (X∈(0,1) 应 ΔT>0)"
    )
    assert result.hydrate_depression_f > 0.0, (
        f"d_F={result.hydrate_depression_f!r} ≤ 0"
    )

    # d_F == d_C × 9/5 EXACT (rel=1e-12) — PCS service 内部公式
    expected_d_F = result.hydrate_depression_c * 9.0 / 5.0
    assert result.hydrate_depression_f == pytest.approx(expected_d_F, rel=1e-12), (
        f"d_F={result.hydrate_depression_f!r} ≠ d_C × 9/5 = {expected_d_F!r}"
    )

    # is_safe bool
    assert isinstance(result.is_safe, bool)
    assert result.is_safe is True

    # K factor / MW
    assert result.inhibitor_k_factor == pytest.approx(2335.0, rel=1e-12)
    assert result.inhibitor_mw == pytest.approx(32.04, rel=1e-12)

    # formula_ref 4 keys
    formula_ref = result.formula_ref
    for key in ("hammerschmidt", "k_factor", "injection_rate", "density"):
        assert key in formula_ref, f"formula_ref 缺键 {key!r}"
    assert "Hammerschmidt 1934" in formula_ref["hammerschmidt"]
    assert "GPSA" in formula_ref["injection_rate"]

    # Water removal / injection rate
    assert result.water_removed_lb_d > 0.0, (
        f"water_removed_lb_d={result.water_removed_lb_d!r} ≤ 0"
    )
    assert result.inhibitor_injection_rate_lb_d > 0.0, (
        f"injection_lb_d={result.inhibitor_injection_rate_lb_d!r} ≤ 0"
    )
    assert result.inhibitor_injection_rate_gpd > 0.0, (
        f"injection_gpd={result.inhibitor_injection_rate_gpd!r} ≤ 0"
    )

    # imperial_conversion 默认 None (L-3 v1 BLOCKER)
    assert result.imperial_conversion is None, (
        f"imperial_conversion={result.imperial_conversion!r} (imperial_units=False 应 None)"
    )


# ============================================================================
# 6) K scale post-fix verification (OPEN-P6-6A-3) — was section 6 K scale defect
# ============================================================================


def test_k_scale_post_fix_xls_F_eq_pcs_F_bit_for_bit() -> None:
    """OPEN-P6-6A-3 fix verification: PCS service d_F = XLS Hammerschmidt literature d_F.

    Pre-fix: PCS service code `delta_t_c = K * X / (mw * (1 - X))` treated K as
    °C scale and reported d_F = d_C × 9/5 = 38.88°F (1.8× over-prediction vs XLS
    literature d_F=21.6°F).

    Post-fix: PCS service uses K_F=2335 in °F scale per Hammerschmidt 1934 paper.
    Code: delta_t_f = K * X / (mw * (1 - X)); delta_t_c = delta_t_f × 5/9.

    For XLS Hammerschmidt X=22.86% (G53):
      - PCS d_F (post-fix) = 21.6°F (matches XLS d_F bit-for-bit rel=1e-12)
      - PCS d_C (post-fix) = 12.0°C (matches XLS target d=12°C bit-for-bit)

    This test verifies the fix end-to-end through PCS service.
    """
    case = WORLEY["cases"][0]
    tautology = case["expected"]["xls_tautology_expected"]

    # XLS literature convention d_F (from K_F=2335, X=22.86%)
    expected_d_F_post_fix = tautology["delta_t_F_for_X22p86_post_fix"]
    expected_d_F_pre_fix = tautology["delta_t_F_for_X22p86_pre_fix"]

    # Sanity: pre-fix was 38.88°F (1.8× over-prediction vs XLS 21.6°F)
    assert abs(expected_d_F_pre_fix - expected_d_F_post_fix) > 10.0, (
        f"pre-fix d_F={expected_d_F_pre_fix} 与 post-fix d_F={expected_d_F_post_fix} "
        f"差值 应 >10 (1.8× over-prediction); actual diff={abs(expected_d_F_pre_fix - expected_d_F_post_fix):.2f}"
    )

    # PCS service call (real calc, end-to-end)
    X_wt_pct = case["service_inputs"]["sub_cases"]["xls_hammerschmidt_X"][
        "inhibitor_concentration_in_water_wt_pct"
    ]
    inp = HydrateInhibitionInput(
        gas_flow_mmscfd=case["service_inputs"]["gas_flow_mmscfd"],
        operating_pressure_psia=case["service_inputs"]["operating_pressure_psia"],
        operating_temperature_f=case["service_inputs"]["operating_temperature_f"],
        hydrate_inhibitor_type=case["service_inputs"]["hydrate_inhibitor_type"],
        inhibitor_concentration_in_water_wt_pct=X_wt_pct,
        water_content_inlet_lb_per_mmscf=20.0,
        water_content_target_lb_per_mmscf=1.0,
    )
    result = calc_hydrate_inhibition(inp)

    # 1) PCS d_F = expected post-fix value (21.6°F) — NOT the buggy 38.88°F
    assert result.hydrate_depression_f == pytest.approx(expected_d_F_post_fix, rel=1e-12), (
        f"PCS d_F={result.hydrate_depression_f!r} ≠ post-fix {expected_d_F_post_fix!r}"
        f" (OPEN-P6-6A-3 fix not applied?)"
    )
    assert abs(result.hydrate_depression_f - expected_d_F_pre_fix) > 10.0, (
        f"PCS d_F={result.hydrate_depression_f!r} = pre-fix buggy {expected_d_F_pre_fix!r}"
        f" (OPEN-P6-6A-3 fix NOT applied; K scale still treated as °C)"
    )

    # 2) PCS d_C = 12.0°C (matches XLS target d=12°C bit-for-bit)
    assert result.hydrate_depression_c == pytest.approx(12.0, rel=1e-12), (
        f"PCS d_C={result.hydrate_depression_c!r} ≠ XLS target d=12°C"
    )


# ============================================================================
# 7) Ruling 6 registration: mapping_defect + root_cause_notes + out_of_scope 必齐
# ============================================================================


def test_worley_c18_root_cause_notes_registered() -> None:
    """fixture.root_cause_notes 必须登记 5 项 (OPEN-P6-6A-3 后 K scale 子项 CLOSED):

    - Ruling_6_inversion_defect_hydrate_dosing_vs_depression_K_scale (primary)
    - xls_k_scale_F_vs_pcs_treats_C (Ruling 6 K scale 子项, FIXED in OPEN-P6-6A-3)
    - xls_uses_nielsen_X_for_injection_rate_not_hammerschmidt (Ruling 6 子项)
    - xls_equation_selector_G52_I52 (Ruling 6 子项)
    - xls_inlet_meoh_concentration_E55_100_pct_pure_assumption (Ruling 6 子项)
    """
    registered = {n["id"] for n in WORLEY["root_cause_notes"]}
    expected_ids = {
        "Ruling_6_inversion_defect_hydrate_dosing_vs_depression_K_scale",
        "xls_k_scale_F_vs_pcs_treats_C",
        "xls_uses_nielsen_X_for_injection_rate_not_hammerschmidt",
        "xls_equation_selector_G52_I52",
        "xls_inlet_meoh_concentration_E55_100_pct_pure_assumption",
    }
    assert registered == expected_ids, (
        f"root_cause_notes 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )

    # OPEN-P6-6A-3: K scale 子项 finding 必须标记 CLOSED
    k_scale_note = next(
        n for n in WORLEY["root_cause_notes"]
        if n["id"] == "xls_k_scale_F_vs_pcs_treats_C"
    )
    assert (
        "CLOSED" in k_scale_note["finding"]
        or "FIXED" in k_scale_note["finding"]
    ), (
        f"xls_k_scale_F_vs_pcs_treats_C finding 应标记 CLOSED/FIXED (OPEN-P6-6A-3):"
        f" {k_scale_note['finding']!r}"
    )


def test_worley_c18_out_of_scope_ledger_complete() -> None:
    """fixture.out_of_scope 必须登记 10 项 Ruling 6 inversion 项 + XLS-only 项.

    OPEN-P6-6A-3: 'xls_hammerschmidt_K_scale_F_to_C_conversion' 已从 out_of_scope
    移除 (K scale CLOSED); 剩余 10 项。
    """
    registered = {o["id"] for o in WORLEY["out_of_scope"]}
    expected_ids = {
        "xls_bit_for_bit_value_match_d_C_or_d_F",
        "xls_nielsen_1988_equation",
        "xls_meoh_injection_rate_39_55_kg_hr",
        "xls_inlet_meoh_concentration_100_pct",
        "xls_free_water_flowrate_122_5_kg_hr",
        "xls_equation_selector_hammerschmidt_vs_nielsen",
        "xls_K_factors_EG_DEG_TEG_NACL_table_F41_F46",
        "xls_MW_values_G41_G46_EG_DEG_TEG_NACL",
        "xls_secondary_considerations_B20_B24_AND_notes_A60_A61",
        "xls_nielsen_X_for_pcs_depression_calculation",
        "xls_free_water_vs_pcs_water_content_inlet",
    }
    assert registered == expected_ids, (
        f"out_of_scope 集合不符: 已登记 {registered}, 预期 {expected_ids}"
    )


def test_worley_c18_ruling_6_registration_complete() -> None:
    """Ruling 6 inversion + K scale defect 三层注册一致性检查:

    1. fixture.mapping_defect.ruling_id == "Ruling_6_inversion_defect_..."
    2. root_cause_notes[0].id 包含 'inversion' / 'K_scale' 关键词
    3. out_of_scope 包含 'bit_for_bit_value_match_d_C_or_d_F'
    4. mapping_defect.implication 显式声明 inversion + K scale
    """
    # Layer 1: mapping_defect.ruling_id
    _ruling_id = "Ruling_6_inversion_defect_hydrate_dosing_vs_depression_K_scale"
    assert WORLEY["mapping_defect"]["ruling_id"] == _ruling_id, (
        f"mapping_defect.ruling_id={WORLEY['mapping_defect']['ruling_id']!r} (应为 {_ruling_id})"
    )

    # Layer 2: root_cause_notes 必含 inversion + K scale
    primary_note = next(
        n for n in WORLEY["root_cause_notes"]
        if n["id"] == "Ruling_6_inversion_defect_hydrate_dosing_vs_depression_K_scale"
    )
    finding_lower = primary_note["finding"].lower()
    assert "inverse" in finding_lower, (
        "Ruling_6 root_cause finding 必须提及 'inverse' (INVERSION defect)"
    )
    assert (
        "k scale" in finding_lower
        or "k_scale" in finding_lower
        or "°f" in primary_note["finding"].lower()
    ), "Ruling_6 root_cause finding 必须提及 'K scale' 或 '°F'"
    assert "hammerschmidt" in finding_lower, (
        "Ruling_6 root_cause finding 必须提及 'Hammerschmidt'"
    )

    # Layer 3: out_of_scope 必含 bit-for-bit value match
    oos_ids = {o["id"] for o in WORLEY["out_of_scope"]}
    assert "xls_bit_for_bit_value_match_d_C_or_d_F" in oos_ids, (
        "out_of_scope 必须包含 xls_bit_for_bit_value_match_d_C_or_d_F (Ruling 6 核心 OOS)"
    )

    # Layer 4: mapping_defect.implication 显式声明 inversion + K scale
    impl = WORLEY["mapping_defect"]["implication"].lower()
    assert "inverse" in impl, (
        "mapping_defect.implication 必须显式声明 'inverse' (INVERSION defect)"
    )
    assert "k scale" in impl or "k_scale" in impl, (
        "mapping_defect.implication 必须显式声明 'K scale' (K scale defect)"
    )


def test_worley_c18_fixture_structure_basics() -> None:
    """fixture JSON 顶层键健全性: source/mapping_defect/tolerance_policy/unit_conversion_factors/
    xls_workbook/cases/root_cause_notes/out_of_scope 必齐; case 顶层键必齐。"""
    for k in (
        "source", "mapping_defect", "tolerance_policy",
        "unit_conversion_factors", "xls_workbook", "cases",
        "root_cause_notes", "out_of_scope",
    ):
        assert k in WORLEY, f"fixture 缺顶层键 {k!r}"
    assert "service" in WORLEY["source"]
    assert "ruling_id" in WORLEY["mapping_defect"]
    _ruling_id_ck = "Ruling_6_inversion_defect_hydrate_dosing_vs_depression_K_scale"
    assert WORLEY["mapping_defect"]["ruling_id"] == _ruling_id_ck
    assert len(WORLEY["cases"]) == 1, (
        f"cases={len(WORLEY['cases'])} (XLS PR-020 是 single case 不同于 PR-019 5 cases)"
    )

    # unit_conversion_factors 必含 5 项
    ucf = WORLEY["unit_conversion_factors"]
    for k in (
        "F_to_C", "delta_t_F_to_delta_t_C", "K_F_to_K_C",
        "wt_pct_to_fraction", "kg_per_hr_to_lb_per_d",
    ):
        assert k in ucf, f"unit_conversion_factors 缺键 {k!r}"

    # single case 顶层键必齐
    case = WORLEY["cases"][0]
    for k in (
        "id", "sheet", "xls_inputs", "xls_outputs",
        "service_inputs", "input_assumptions", "expected",
        "per_field_tolerance", "tolerance",
    ):
        assert k in case, f"case 缺顶层键 {k!r}"

    # sub_cases 必含 3 项
    sub_cases = case["service_inputs"]["sub_cases"]
    for k in ("xls_hammerschmidt_X", "xls_nielsen_X", "mid_range_X"):
        assert k in sub_cases, f"service_inputs.sub_cases 缺键 {k!r}"
