"""P5-3-2 PSV 其他工况（阀门关闭 + 反应失控 + 热膨胀）测试。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §293-318 + SUP-P5-PSV-001 §4.1：
- 阀门关闭（API 521 §5.15.2.3）— 液体段塞
- 反应失控（API 521 §5.15.2.4）— 反应放热
- 热膨胀（API 521 §5.15.2.5）— 液体等温膨胀

API 路径实施（V1）；GB 路径留 P5-3-6 profile 注入。
"""
from __future__ import annotations

import math

import pytest

from app.services.psv import (
    ClosedValveInput,
    ReactionRunawayInput,
    ThermalExpansionInput,
    calc_closed_valve_case,
    calc_reaction_runaway_case,
    calc_thermal_expansion_case,
)
from app.services.psv.other_cases_service import PsvOtherCaseInputError

# ============================================================================
# 1. 阀门关闭工况（API 521 §5.15.2.3）
# ============================================================================


def test_closed_valve_basic():
    """阀门关闭基本工况：W_mass = V × ρ / t。

    V=0.05 m³, ρ=850 kg/m³, t=60 s
    W_mass = 0.05 × 850 / 60 = 0.7083 kg/s
    Q_v = 0.05 / 60 = 0.000833 m³/s
    """
    inp = ClosedValveInput(V_pipe_m3=0.05, rho_L_kg_m3=850.0, t_isolation_s=60.0)
    r = calc_closed_valve_case(inp)

    expected_W = 0.05 * 850.0 / 60.0  # ≈ 0.7083
    expected_Q_v = 0.05 / 60.0  # ≈ 0.000833

    assert math.isclose(r.relief_mass_flow_kgs, expected_W, rel_tol=1e-6)
    assert math.isclose(r.relief_volume_flow_m3s, expected_Q_v, rel_tol=1e-6)
    # formula_ref
    assert r.formula_ref.standard == "API_521"
    assert r.formula_ref.version == "7th"
    assert r.formula_ref.clause == "§5.15.2.3"


def test_closed_valve_t_isolation_inverse():
    """t_isolation 翻倍 → W_mass 减半（反比例）。"""
    inp_short = ClosedValveInput(V_pipe_m3=0.05, rho_L_kg_m3=850.0, t_isolation_s=30.0)
    inp_long = ClosedValveInput(V_pipe_m3=0.05, rho_L_kg_m3=850.0, t_isolation_s=60.0)
    r_short = calc_closed_valve_case(inp_short)
    r_long = calc_closed_valve_case(inp_long)

    expected_short = r_long.relief_mass_flow_kgs * 2.0
    assert math.isclose(r_short.relief_mass_flow_kgs, expected_short, rel_tol=1e-6)


def test_closed_valve_V_proportional():
    """V_pipe 翻倍 → W_mass 翻倍（正比例）。"""
    inp_small = ClosedValveInput(V_pipe_m3=0.05, rho_L_kg_m3=850.0, t_isolation_s=60.0)
    inp_large = ClosedValveInput(V_pipe_m3=0.10, rho_L_kg_m3=850.0, t_isolation_s=60.0)
    r_small = calc_closed_valve_case(inp_small)
    r_large = calc_closed_valve_case(inp_large)

    expected_large = r_small.relief_mass_flow_kgs * 2.0
    assert math.isclose(r_large.relief_mass_flow_kgs, expected_large, rel_tol=1e-6)


def test_closed_valve_V_zero_raises():
    """V_pipe = 0 → PsvOtherCaseInputError。"""
    inp = ClosedValveInput(V_pipe_m3=0.0, rho_L_kg_m3=850.0, t_isolation_s=60.0)
    with pytest.raises(PsvOtherCaseInputError):
        calc_closed_valve_case(inp)


def test_closed_valve_t_zero_raises():
    """t_isolation = 0 → PsvOtherCaseInputError（除零保护）。"""
    inp = ClosedValveInput(V_pipe_m3=0.05, rho_L_kg_m3=850.0, t_isolation_s=0.0)
    with pytest.raises(PsvOtherCaseInputError):
        calc_closed_valve_case(inp)


def test_closed_valve_rho_zero_raises():
    """ρ_L = 0 → PsvOtherCaseInputError。"""
    inp = ClosedValveInput(V_pipe_m3=0.05, rho_L_kg_m3=0.0, t_isolation_s=60.0)
    with pytest.raises(PsvOtherCaseInputError):
        calc_closed_valve_case(inp)


# ============================================================================
# 2. 反应失控工况（API 521 §5.15.2.4）
# ============================================================================


def test_reaction_runaway_basic():
    """反应失控基本工况：W_mass = Q_rxn × fraction / h_fg。

    Q_rxn=100,000 W, fraction=0.8, h_fg=350,000 J/kg
    Q_valve = 80,000 W
    W_mass = 80,000 / 350,000 = 0.2286 kg/s
    """
    inp = ReactionRunawayInput(Q_rxn_w=100_000.0, fraction_to_valve=0.8)
    r = calc_reaction_runaway_case(inp)

    expected_Q_valve = 100_000.0 * 0.8
    expected_W_mass = expected_Q_valve / 350_000.0

    assert math.isclose(r.heat_input_w, expected_Q_valve, rel_tol=1e-6)
    assert math.isclose(r.relief_mass_flow_kgs, expected_W_mass, rel_tol=1e-6)
    assert r.h_fg_j_per_kg == 350_000.0
    assert r.formula_ref.clause == "§5.15.2.4"


def test_reaction_runaway_fraction_zero():
    """fraction_to_valve = 0 → W_mass = 0（无热进入 PSV）。"""
    inp = ReactionRunawayInput(Q_rxn_w=100_000.0, fraction_to_valve=0.0)
    r = calc_reaction_runaway_case(inp)
    assert r.heat_input_w == 0.0
    assert r.relief_mass_flow_kgs == 0.0


def test_reaction_runaway_fraction_one():
    """fraction_to_valve = 1.0 → 100% 热进入 PSV。"""
    inp = ReactionRunawayInput(Q_rxn_w=100_000.0, fraction_to_valve=1.0)
    r = calc_reaction_runaway_case(inp, h_fg_j_per_kg=350_000.0)
    expected_W = 100_000.0 / 350_000.0
    assert math.isclose(r.relief_mass_flow_kgs, expected_W, rel_tol=1e-6)


def test_reaction_runaway_custom_h_fg():
    """自定义 h_fg_j_per_kg：传参覆盖默认值。"""
    inp = ReactionRunawayInput(Q_rxn_w=100_000.0, fraction_to_valve=0.5)
    r = calc_reaction_runaway_case(inp, h_fg_j_per_kg=200_000.0)
    expected_W = 50_000.0 / 200_000.0  # = 0.25
    assert math.isclose(r.relief_mass_flow_kgs, expected_W, rel_tol=1e-6)
    assert r.h_fg_j_per_kg == 200_000.0


def test_reaction_runaway_fraction_out_of_range_raises():
    """fraction > 1 → PsvOtherCaseInputError。"""
    inp = ReactionRunawayInput(Q_rxn_w=100_000.0, fraction_to_valve=1.5)
    with pytest.raises(PsvOtherCaseInputError):
        calc_reaction_runaway_case(inp)


def test_reaction_runaway_Q_zero_raises():
    """Q_rxn = 0 → PsvOtherCaseInputError。"""
    inp = ReactionRunawayInput(Q_rxn_w=0.0, fraction_to_valve=0.5)
    with pytest.raises(PsvOtherCaseInputError):
        calc_reaction_runaway_case(inp)


def test_reaction_runaway_h_fg_zero_raises():
    """h_fg = 0 → PsvOtherCaseInputError。"""
    inp = ReactionRunawayInput(Q_rxn_w=100_000.0, fraction_to_valve=0.5)
    with pytest.raises(PsvOtherCaseInputError):
        calc_reaction_runaway_case(inp, h_fg_j_per_kg=0.0)


# ============================================================================
# 3. 热膨胀工况（API 521 §5.15.2.5）
# ============================================================================


def test_thermal_expansion_basic():
    """热膨胀基本工况：ΔV = V × β × ΔT；W_mass = ρ × ΔV / t。

    V_L=5.0 m³, ρ=850 kg/m³, β=0.001 1/K, ΔT=50 K, t=600 s
    ΔV = 5.0 × 0.001 × 50 = 0.25 m³
    W_mass = 850 × 0.25 / 600 = 0.3542 kg/s
    """
    inp = ThermalExpansionInput(
        V_L_m3=5.0,
        rho_L_kg_m3=850.0,
        beta_per_k=0.001,
        delta_T_k=50.0,
        t_heat_s=600.0,
    )
    r = calc_thermal_expansion_case(inp)

    expected_dV = 5.0 * 0.001 * 50.0  # = 0.25
    expected_W_mass = 850.0 * expected_dV / 600.0
    expected_Q_v = expected_dV / 600.0

    assert math.isclose(r.expansion_volume_m3, expected_dV, rel_tol=1e-6)
    assert math.isclose(r.relief_mass_flow_kgs, expected_W_mass, rel_tol=1e-6)
    assert math.isclose(r.relief_volume_flow_m3s, expected_Q_v, rel_tol=1e-6)
    assert r.formula_ref.clause == "§5.15.2.5"


def test_thermal_expansion_delta_T_zero():
    """ΔT = 0 → 体积膨胀 0（无热输入）。"""
    inp = ThermalExpansionInput(
        V_L_m3=5.0,
        rho_L_kg_m3=850.0,
        beta_per_k=0.001,
        delta_T_k=0.0,
        t_heat_s=600.0,
    )
    r = calc_thermal_expansion_case(inp)
    assert r.expansion_volume_m3 == 0.0
    assert r.relief_mass_flow_kgs == 0.0


def test_thermal_expansion_beta_linear():
    """β 翻倍 → ΔV 翻倍。"""
    inp_a = ThermalExpansionInput(
        V_L_m3=5.0, rho_L_kg_m3=850.0, beta_per_k=0.001,
        delta_T_k=50.0, t_heat_s=600.0,
    )
    inp_b = ThermalExpansionInput(
        V_L_m3=5.0, rho_L_kg_m3=850.0, beta_per_k=0.002,
        delta_T_k=50.0, t_heat_s=600.0,
    )
    r_a = calc_thermal_expansion_case(inp_a)
    r_b = calc_thermal_expansion_case(inp_b)
    assert math.isclose(r_b.expansion_volume_m3, r_a.expansion_volume_m3 * 2.0, rel_tol=1e-6)


def test_thermal_expansion_V_zero_raises():
    """V_L = 0 → PsvOtherCaseInputError。"""
    inp = ThermalExpansionInput(
        V_L_m3=0.0, rho_L_kg_m3=850.0, beta_per_k=0.001,
        delta_T_k=50.0, t_heat_s=600.0,
    )
    with pytest.raises(PsvOtherCaseInputError):
        calc_thermal_expansion_case(inp)


def test_thermal_expansion_delta_T_negative_raises():
    """ΔT < 0 → PsvOtherCaseInputError（物理不合理）。"""
    inp = ThermalExpansionInput(
        V_L_m3=5.0, rho_L_kg_m3=850.0, beta_per_k=0.001,
        delta_T_k=-10.0, t_heat_s=600.0,
    )
    with pytest.raises(PsvOtherCaseInputError):
        calc_thermal_expansion_case(inp)


def test_thermal_expansion_t_zero_raises():
    """t_heat = 0 → PsvOtherCaseInputError（除零保护）。"""
    inp = ThermalExpansionInput(
        V_L_m3=5.0, rho_L_kg_m3=850.0, beta_per_k=0.001,
        delta_T_k=50.0, t_heat_s=0.0,
    )
    with pytest.raises(PsvOtherCaseInputError):
        calc_thermal_expansion_case(inp)


# ============================================================================
# 4. formula_ref 结构化（三工况一致）
# ============================================================================


@pytest.mark.parametrize("fn, expected_clause", [
    (lambda: calc_closed_valve_case(ClosedValveInput(0.05, 850.0, 60.0)), "§5.15.2.3"),
    (lambda: calc_reaction_runaway_case(ReactionRunawayInput(100_000.0, 0.5)), "§5.15.2.4"),
    (lambda: calc_thermal_expansion_case(
        ThermalExpansionInput(5.0, 850.0, 0.001, 50.0, 600.0)
    ), "§5.15.2.5"),
])
def test_other_case_formula_ref_structured(fn, expected_clause):
    """三工况 formula_ref 三字段（standard + version + clause）均完整。"""
    result = fn()
    assert result.formula_ref.standard == "API_521"
    assert result.formula_ref.version == "7th"
    assert result.formula_ref.clause == expected_clause