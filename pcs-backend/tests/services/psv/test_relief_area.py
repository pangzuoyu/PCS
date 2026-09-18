"""P5-3-4 PSV 泄放面积（API 520 + GB/T 12241 + ω 法两相流）测试。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §344-369 + SUP-P5-PSV-001 §4.1：
- API 520 9th Ed. §5.6.3 气体（V2 严格公式：含 M/Z/T/k 等熵项；bug-089 修复）
- API 520 9th Ed. §5.6.4 液体
- API 520 9th Ed. Annex C.2.2 两相流 ω 法（V1 简化：Leung 1996 形式）
- GB/T 12241 降级路径（orifice_table_status = "incomplete_fallback"）

API/GB 完全隔离（独立函数 + 公用入口分发）。
formula_ref 结构化（F-09）。
"""
from __future__ import annotations

import math

import pytest

from app.services.psv import (
    ReliefAreaInput,
    calc_relief_area,
    calc_relief_area_api520_gas,
    calc_relief_area_api520_liquid,
    calc_relief_area_api520_two_phase,
    calc_relief_area_gb12241,
)
from app.services.psv.relief_area_service import PsvReliefAreaInputError

# 通用输入：W = 5.0 kg/s, P_back = 100 kPa, P_set = 200 kPa
_BASE_GAS_INPUT = ReliefAreaInput(
    relief_mass_flow_kgs=5.0,
    phase="GAS",
    P_back_pa=100_000.0,
    P_set_pa=200_000.0,
    T_k=350.0,
    M_kg_per_mol=0.029,  # 空气
    Z=1.0,
    k_cp_ratio=1.4,
)

_BASE_LIQUID_INPUT = ReliefAreaInput(
    relief_mass_flow_kgs=10.0,
    phase="LIQUID",
    P_back_pa=100_000.0,
    P_set_pa=300_000.0,
    rho_L_kg_m3=850.0,
)


# ============================================================================
# 1. API 520 气体（V1 简化）
# ============================================================================


def test_api520_gas_basic():
    """API 520 9th Ed. §5.6.3 气体（严格公式，bug-089 修复）：含 M/Z/k 等熵项。

    W=5.0, P_back=100000, M=0.029, T=350, Z=1.0, k=1.4
    isentropic = √(1.4 × (2/2.4)^6) = √0.4689 ≈ 0.6847
                  （bug-089 fix: 移除 (k/(k-1)) 因子，
                   见 API 520 9th Ed. §5.6.3 Eq (9)）
    G_c = 0.975 × 100000 × √(0.029/(8.314×350)) × 0.6847
        = 0.975 × 100000 × 3.157e-3 × 0.6847
        ≈ 210.7 kg/(s·m²)
    A = 5.0 / 210.7 ≈ 0.02373 m²
    """
    r = calc_relief_area_api520_gas(_BASE_GAS_INPUT)

    R = 8.314462618  # bug-089 fix: J/(mol·K) 配 M kg/mol
    isentropic = math.sqrt(1.4 * ((2.0 / 2.4) ** 6))  # bug-089 fix: √[k×...] 而非 √[(k/(k-1))×...]
    G_c = 0.975 * 100_000.0 * math.sqrt(0.029 / (1.0 * R * 350.0)) * isentropic
    expected = 5.0 / G_c
    assert math.isclose(r.area_required_m2, expected, rel_tol=1e-6)
    expected_d = math.sqrt(4.0 * expected / math.pi)
    assert math.isclose(r.orifice_diameter_m, expected_d, rel_tol=1e-6)
    assert r.orifice_table_status == "exact"
    assert r.formula_ref.standard == "API_520"
    assert r.formula_ref.version == "9th"
    assert r.formula_ref.clause == "§5.6.3"


def test_api520_gas_W_proportional():
    """W 翻倍 → A 翻倍（正比例；同 T/M/Z/k 严格公式下）。"""
    inp_double = ReliefAreaInput(
        relief_mass_flow_kgs=10.0,
        phase="GAS",
        P_back_pa=100_000.0,
        P_set_pa=200_000.0,
        T_k=350.0, M_kg_per_mol=0.029, Z=1.0, k_cp_ratio=1.4,
    )
    r_base = calc_relief_area_api520_gas(_BASE_GAS_INPUT)
    r_double = calc_relief_area_api520_gas(inp_double)
    assert math.isclose(r_double.area_required_m2, r_base.area_required_m2 * 2.0, rel_tol=1e-6)


def test_api520_gas_P_back_inverse():
    """P_back 翻倍 → A 减半（反比例；同 T/M/Z/k 严格公式下）。"""
    inp_double = ReliefAreaInput(
        relief_mass_flow_kgs=5.0,
        phase="GAS",
        P_back_pa=200_000.0,
        P_set_pa=400_000.0,
        T_k=350.0, M_kg_per_mol=0.029, Z=1.0, k_cp_ratio=1.4,
    )
    r_base = calc_relief_area_api520_gas(_BASE_GAS_INPUT)
    r_double = calc_relief_area_api520_gas(inp_double)
    assert math.isclose(r_double.area_required_m2, r_base.area_required_m2 / 2.0, rel_tol=1e-6)


def test_api520_gas_wrong_phase_raises():
    """phase=LIQUID 调 gas 函数 → PsvReliefAreaInputError。"""
    with pytest.raises(PsvReliefAreaInputError):
        calc_relief_area_api520_gas(_BASE_LIQUID_INPUT)


def test_api520_gas_T_zero_raises():
    """T_k = 0 → PsvReliefAreaInputError。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        T_k=0.0,
    )
    with pytest.raises(PsvReliefAreaInputError):
        calc_relief_area_api520_gas(inp)


def test_api520_gas_k_le_one_raises():
    """k_cp_ratio <= 1 → PsvReliefAreaInputError（理想气体比热比下限）。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        k_cp_ratio=1.0,
    )
    with pytest.raises(PsvReliefAreaInputError):
        calc_relief_area_api520_gas(inp)


# ============================================================================
# 2. API 520 液体
# ============================================================================


def test_api520_liquid_basic():
    """API 520 液体：A = W / (K_v × √(2·ρ·ΔP))。

    W=10, K_v=0.975, ρ=850, ΔP = 300,000 - 100,000 = 200,000
    A = 10 / (0.975 × √(2 × 850 × 200,000))
      = 10 / (0.975 × √340,000,000)
      = 10 / (0.975 × 18,439)
      ≈ 5.566e-4 m²
    """
    r = calc_relief_area_api520_liquid(_BASE_LIQUID_INPUT)

    delta_P = 200_000.0
    expected = 10.0 / (0.975 * math.sqrt(2.0 * 850.0 * delta_P))
    assert math.isclose(r.area_required_m2, expected, rel_tol=1e-6)
    assert r.formula_ref.clause == "§5.6.4"
    assert r.orifice_table_status == "exact"


def test_api520_liquid_P_set_le_P_back_raises():
    """P_set ≤ P_back → PsvReliefAreaInputError（驱动压差为 0）。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=10.0, phase="LIQUID",
        P_back_pa=200_000.0, P_set_pa=200_000.0,  # 等于
        rho_L_kg_m3=850.0,
    )
    with pytest.raises(PsvReliefAreaInputError):
        calc_relief_area_api520_liquid(inp)


def test_api520_liquid_rho_zero_raises():
    """ρ_L = 0 → PsvReliefAreaInputError。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=10.0, phase="LIQUID",
        P_back_pa=100_000.0, P_set_pa=300_000.0,
        rho_L_kg_m3=0.0,
    )
    with pytest.raises(PsvReliefAreaInputError):
        calc_relief_area_api520_liquid(inp)


# ============================================================================
# 3. API 520 两相流 ω 法
# ============================================================================


def test_api520_two_phase_omega_zero():
    """ω = 0：两相流退化为纯气（Leung：denom=1.0 → A_TP = A_gas）。

    同 T/M 让 base_area 一致；C6 fix 后 gas 公式含严格等熵项。
    """
    inp_tp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="TWO_PHASE",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        omega=0.0, rho_L_kg_m3=1000.0, rho_g_kg_m3=0.6,
        T_k=350.0, M_kg_per_mol=0.029,
    )
    inp_gas = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        T_k=350.0, M_kg_per_mol=0.029,
    )
    r_two_phase = calc_relief_area_api520_two_phase(inp_tp)
    r_gas = calc_relief_area_api520_gas(inp_gas)

    assert math.isclose(r_two_phase.area_required_m2, r_gas.area_required_m2, rel_tol=1e-6)


def test_api520_two_phase_omega_one():
    """ω = 1：Leung 公式 A_TP = A_gas × √(ρ_l/ρ_g)（密度比主导；远超 6× V1 简化）。"""
    inp_tp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="TWO_PHASE",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        omega=1.0, rho_L_kg_m3=1000.0, rho_g_kg_m3=0.6,
        T_k=350.0, M_kg_per_mol=0.029,
    )
    inp_gas = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        T_k=350.0, M_kg_per_mol=0.029,
    )
    r_two_phase = calc_relief_area_api520_two_phase(inp_tp)
    r_gas = calc_relief_area_api520_gas(inp_gas)

    expected = r_gas.area_required_m2 / math.sqrt(0.6 / 1000.0)
    assert math.isclose(r_two_phase.area_required_m2, expected, rel_tol=1e-6)


def test_api520_two_phase_omega_half():
    """ω = 0.5：Leung 公式 A_TP = A_gas / √((1-0.5) + 0.5×ρ_g/ρ_l)。"""
    inp_tp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="TWO_PHASE",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        omega=0.5, rho_L_kg_m3=1000.0, rho_g_kg_m3=0.6,
        T_k=350.0, M_kg_per_mol=0.029,
    )
    inp_gas = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        T_k=350.0, M_kg_per_mol=0.029,
    )
    r_two_phase = calc_relief_area_api520_two_phase(inp_tp)
    r_gas = calc_relief_area_api520_gas(inp_gas)

    density_ratio = 0.6 / 1000.0
    expected = r_gas.area_required_m2 / math.sqrt((1.0 - 0.5) + 0.5 * density_ratio)
    assert math.isclose(r_two_phase.area_required_m2, expected, rel_tol=1e-6)


def test_api520_two_phase_omega_out_of_range_raises():
    """omega > 1 → PsvReliefAreaInputError。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="TWO_PHASE",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        omega=1.5, rho_L_kg_m3=1000.0, rho_g_kg_m3=0.6,
    )
    with pytest.raises(PsvReliefAreaInputError):
        calc_relief_area_api520_two_phase(inp)


def test_api520_two_phase_leung_ideal_gas_fallback_rho_g():
    """未传 rho_g_kg_m3 → 理想气体推导 ρ_g = P_back × M / (Z × R × T)（bug-089 fix R=8.314）。"""
    # 蒸汽 M=0.018 kg/mol, P_back=101325, T=400 K, Z=1.0
    # ρ_g = 101325 × 0.018 / (1 × 8.314 × 400) ≈ 0.5484 kg/m³
    rho_g_expected = 101_325.0 * 0.018 / (1.0 * 8.314462618 * 400.0)
    inp_explicit = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="TWO_PHASE",
        P_back_pa=101_325.0, P_set_pa=200_000.0,
        omega=0.3, rho_L_kg_m3=1000.0, T_k=400.0, M_kg_per_mol=0.018,
        rho_g_kg_m3=rho_g_expected,
    )
    inp_fallback = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="TWO_PHASE",
        P_back_pa=101_325.0, P_set_pa=200_000.0,
        omega=0.3, rho_L_kg_m3=1000.0, T_k=400.0, M_kg_per_mol=0.018,
        # rho_g_kg_m3 不传 → 理想气体推导
    )
    r_explicit = calc_relief_area_api520_two_phase(inp_explicit)
    r_fallback = calc_relief_area_api520_two_phase(inp_fallback)
    assert math.isclose(
        r_explicit.area_required_m2, r_fallback.area_required_m2, rel_tol=1e-6
    )


def test_api520_two_phase_leung_water_steam_conservative():
    """水-蒸汽工况（ρ_l=1000, ρ_g=0.6, ω=0.4）→ Leung 公式保守放大 ~1.29×。

    用同一热力学参数（T_k, M）跑 gas 基准，确保 ratio 严格等于 1/√denom。
    """
    inp_tp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="TWO_PHASE",
        P_back_pa=101_325.0, P_set_pa=200_000.0,
        omega=0.4, rho_L_kg_m3=1000.0, rho_g_kg_m3=0.6,
        T_k=400.0, M_kg_per_mol=0.018,
    )
    inp_gas = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=101_325.0, P_set_pa=200_000.0,
        T_k=400.0, M_kg_per_mol=0.018,
    )
    r_tp = calc_relief_area_api520_two_phase(inp_tp)
    r_gas = calc_relief_area_api520_gas(inp_gas)
    # Leung：denom = (1-0.4) + 0.4 × 0.0006 = 0.60024 → √0.60024 ≈ 0.7748
    expected = r_gas.area_required_m2 / math.sqrt(0.60024)
    assert math.isclose(r_tp.area_required_m2, expected, rel_tol=1e-6)


# ============================================================================
# 4. GB/T 12241 降级路径（orifice_table_status = "incomplete_fallback"）
# ============================================================================


def test_gb12241_fallback_marker():
    """GB 路径 orifice_table_status 必须 = "incomplete_fallback"。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
    )
    r = calc_relief_area_gb12241(inp)

    assert r.orifice_table_status == "incomplete_fallback"
    assert r.formula_ref.standard == "GB_T_12241"
    assert r.formula_ref.version == "2021"
    assert r.formula_ref.clause == "§4.3.1"


def test_gb12241_more_conservative_than_api():
    """GB 略保守：相同输入面积 ≥ API 面积（C_d_Gb=0.95 < C_d_Api=0.975）。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
    )
    r_gb = calc_relief_area_gb12241(inp)
    r_api = calc_relief_area_api520_gas(inp)

    # GB Cd 更小 → 面积更大（保守）
    assert r_gb.area_required_m2 > r_api.area_required_m2


def test_gb12241_P_back_zero_raises():
    """P_back = 0 → PsvReliefAreaInputError。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=0.0, P_set_pa=200_000.0,
    )
    with pytest.raises(PsvReliefAreaInputError):
        calc_relief_area_gb12241(inp)


# ============================================================================
# 5. 公用入口分发（按 standard + phase 路由）
# ============================================================================


def test_dispatch_api_gas():
    """calc_relief_area(standard='API') + GAS → API 520 气体。"""
    r = calc_relief_area(_BASE_GAS_INPUT, standard="API")
    assert r.formula_ref.standard == "API_520"
    assert r.formula_ref.clause == "§5.6.3"


def test_dispatch_api_liquid():
    """calc_relief_area(standard='API') + LIQUID → API 520 液体。"""
    r = calc_relief_area(_BASE_LIQUID_INPUT, standard="API")
    assert r.formula_ref.clause == "§5.6.4"


def test_dispatch_api_two_phase():
    """calc_relief_area(standard='API') + TWO_PHASE → API 520 Leung 1996 ω 法。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="TWO_PHASE",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        omega=0.3, rho_L_kg_m3=1000.0, rho_g_kg_m3=0.6,
    )
    r = calc_relief_area(inp, standard="API")
    assert r.formula_ref.clause == "Annex C.2.2"


def test_dispatch_gb_unified():
    """calc_relief_area(standard='GB') → GB 降级路径（无论 phase）。"""
    r = calc_relief_area(_BASE_GAS_INPUT, standard="GB")
    assert r.formula_ref.standard == "GB_T_12241"
    assert r.orifice_table_status == "incomplete_fallback"


def test_dispatch_W_zero_raises():
    """W = 0 → PsvReliefAreaInputError（公用入口校验）。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=0.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
    )
    with pytest.raises(PsvReliefAreaInputError):
        calc_relief_area(inp, standard="API")


# ============================================================================
# 6. API/GB 完全隔离（SUP-P5-PSV-001 §4.1 断言）
# ============================================================================


def test_gb12241_bug089_regression():
    """bug-089 GB/T 12241 修复回归：R 单位 + k/(k-1) 因子双修。

    修复前：GB 面积 ≈ API 面积 × 20.5x（k=1.4 空气），严重失真
    修复后：GB 面积 ≈ API 面积 × (0.975/0.95) = 1.0263（仅 C_d 差异）

    锁定：
      - R = 8.314462618 J/(mol·K)（不是 8314）
      - 等熵因子 = √[k × (2/(k+1))^((k+1)/(k-1))]（不含 k/(k-1)）
    """
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        T_k=350.0, M_kg_per_mol=0.02897,  # 空气
        Z=1.0, k_cp_ratio=1.4,
    )
    r_api = calc_relief_area_api520_gas(inp)
    r_gb = calc_relief_area_gb12241(inp)

    # 仅 C_d 差异 (0.975 vs 0.95 → GB 面积更大 1/0.95 / 1/0.975 = 1.0263 倍)
    expected_ratio = 0.975 / 0.95
    actual_ratio = r_gb.area_required_m2 / r_api.area_required_m2
    assert math.isclose(actual_ratio, expected_ratio, rel_tol=1e-3), (
        f"bug-089 修复回归：GB/API 面积比 {actual_ratio:.4f} 偏离预期 "
        f"{expected_ratio:.4f}（rel > 0.1%）"
    )


def test_api_gb_calculation_independence():
    """API 与 GB 公式常数不同，相同输入产出必须不同（证明隔离）。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
    )
    r_api = calc_relief_area_api520_gas(inp)
    r_gb = calc_relief_area_gb12241(inp)

    assert r_api.formula_ref.standard != r_gb.formula_ref.standard
    assert r_api.area_required_m2 != r_gb.area_required_m2
    assert r_api.orifice_table_status != r_gb.orifice_table_status


# ============================================================================
# 7. formula_ref 三参数化
# ============================================================================


@pytest.mark.parametrize("fn, expected_standard, expected_clause", [
    (calc_relief_area_api520_gas, "API_520", "§5.6.3"),
    (calc_relief_area_api520_liquid, "API_520", "§5.6.4"),
    (calc_relief_area_api520_two_phase, "API_520", "Annex C.2.2"),
])
def test_api_formula_ref_structured(fn, expected_standard, expected_clause):
    """API 520 三相态 formula_ref 三字段均完整。"""
    inp = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        rho_L_kg_m3=850.0,
    )
    if "liquid" in fn.__name__:
        inp = ReliefAreaInput(
            relief_mass_flow_kgs=10.0, phase="LIQUID",
            P_back_pa=100_000.0, P_set_pa=300_000.0,
            rho_L_kg_m3=850.0,
        )
    elif "two_phase" in fn.__name__:
        inp = ReliefAreaInput(
            relief_mass_flow_kgs=5.0, phase="TWO_PHASE",
            P_back_pa=100_000.0, P_set_pa=200_000.0,
            omega=0.5, rho_L_kg_m3=1000.0, rho_g_kg_m3=0.6,
        )

    r = fn(inp)
    assert r.formula_ref.standard == expected_standard
    assert r.formula_ref.version == "9th"
    assert r.formula_ref.clause == expected_clause

# ============================================================================
# C6: API 520 气体公式严格化（ce-code-review P0..P5 C6）—— M/Z/k 等熵项
# ============================================================================


def test_api520_gas_strict_M_dependence():
    """气体面积随 M 严格变化（V1 简化忽略 M → 现在纳入公式）。

    M=0.002 (H₂): k=1.41, M=0.029 (air): k=1.4（同温同压）
    比值 ≈ √(M_air/M_H₂) = √(0.029/0.002) ≈ 3.81
    """
    inp_h2 = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        T_k=350.0, M_kg_per_mol=0.002, k_cp_ratio=1.41,
    )
    inp_air = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        T_k=350.0, M_kg_per_mol=0.029, k_cp_ratio=1.4,
    )
    r_h2 = calc_relief_area_api520_gas(inp_h2)
    r_air = calc_relief_area_api520_gas(inp_air)
    # H₂ 分子量小 → 单位质量体积大 → 临界质量通量小 → 面积大
    assert r_h2.area_required_m2 > r_air.area_required_m2
    # 比值 ≈ √(M_H₂/M_air)^(-1) = √(M_air/M_H₂) × √(isentropic_h2/isentropic_air) ≈ 3.81
    # （k_H₂ 略大 → isentropic 略大 → 比值稍大于纯 √(M_air/M_H₂)）
    ratio = r_h2.area_required_m2 / r_air.area_required_m2
    assert 3.5 < ratio < 4.0


def test_api520_gas_strict_T_dependence():
    """气体面积随 T 严格变化（V1 简化忽略 T → 现在纳入公式）。

    T↑ → √(M/T)↓ → G_c↓ → A↑
    """
    inp_cold = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        T_k=200.0, M_kg_per_mol=0.029, k_cp_ratio=1.4,
    )
    inp_hot = ReliefAreaInput(
        relief_mass_flow_kgs=5.0, phase="GAS",
        P_back_pa=100_000.0, P_set_pa=200_000.0,
        T_k=800.0, M_kg_per_mol=0.029, k_cp_ratio=1.4,
    )
    r_cold = calc_relief_area_api520_gas(inp_cold)
    r_hot = calc_relief_area_api520_gas(inp_hot)
    # 高温 → 大面积
    assert r_hot.area_required_m2 > r_cold.area_required_m2
    # T 比 4× → √T 比 2× → 面积比 2×（同其他条件）
    ratio = r_hot.area_required_m2 / r_cold.area_required_m2
    assert math.isclose(ratio, math.sqrt(800.0 / 200.0), rel_tol=1e-6)
