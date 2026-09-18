"""P5-3-7 API 520 9th Ed. **Annex C.2.2 Two-Point Omega Method** 单元测试。

参考算例：API STD 520 Part I 9th Ed.（2014-07）§C.2.2.2-3 worked example
（PDF p.120-121）。SI 主链 + 独立复算与 PDF 一致。

测试覆盖：
- omega_two_point_area 主函数：worked example 完整链路（C.22/C.24/C.26/C.27/C.29）
- omega 推算（Eq C.12）
- η_c 临界压比（Eq C.14 二分法求根）
- 临界/亚临界分支（Eq C.18 vs Eq C.19）
- K 系数缩放
- 输入校验（异常路径）
- 公式溯源 metadata
"""

from __future__ import annotations

import math

import pytest

from app.services.psv import (
    TwoPointOmegaInput,
    TwoPointOmegaInputError,
    omega_two_point_area,
)

# --- API 520 9th Ed. C.2.2.2-3 worked example（SI 主链） ---


# PDF 原始 SI 值
# v_o = 0.01945 m³/kg, v_g (0.9 P_o) = 0.02265 m³/kg
# P_o = 556,379 Pa (0.9 P_o = 500,800 Pa)
# P_a = 204,700 Pa
# W = 216,560 kg/h = 60.1556 kg/s
# K_d = 0.85, K_b = K_c = K_v = 1.0
_WORKED_V_O = 0.01945
_WORKED_V_G = 0.02265
_WORKED_P_O = 556_379.0
_WORKED_P_A = 204_700.0
_WORKED_W_KGS = 216_560.0 / 3600.0
_WORKED_K_D = 0.85


def _worked_input() -> TwoPointOmegaInput:
    return TwoPointOmegaInput(
        mass_flow_kgs=_WORKED_W_KGS,
        P_relieving_pa=_WORKED_P_O,
        P_backpressure_pa=_WORKED_P_A,
        v_inlet_m3_per_kg=_WORKED_V_O,
        v_vapor_0_9Po_m3_per_kg=_WORKED_V_G,
        K_d=_WORKED_K_D,
        K_b=1.0,
        K_c=1.0,
        K_v=1.0,
    )


# --- Eq C.12: omega 推算 ---


def test_eq_c12_omega_matches_pdf_worked_example():
    """Eq C.22 PDF 算例：ω = 9 × (v_g / v_o − 1) = 9 × (0.02265/0.01945 − 1) = 1.482。"""
    r = omega_two_point_area(_worked_input())
    assert math.isclose(r.omega, 1.482, rel_tol=1e-3), f"omega={r.omega} 应≈1.482"


# --- Eq C.14: η_c 二分法求根 ---


def test_eq_c14_eta_critical_close_to_0_66_for_omega_1_482():
    """ω=1.482 时 Eq C.14 根 ≈ 0.6565（PDF 读图 0.66）。"""
    r = omega_two_point_area(_worked_input())
    # PDF 图 C.1 读图 0.66；精确根 0.6565（独立复算）
    assert 0.64 <= r.eta_critical <= 0.68, (
        f"eta_critical={r.eta_critical:.4f} 偏离 0.66 超过 3%"
    )


def test_eq_c14_monotonic_increasing_in_eta():
    """Eq C.14 f(η_c) 在 (0, 1) 严格单调递增（保证二分法唯一根）。

    这是求解算法的物理不变量；测试失败意味着 bisection bracket 选择错误。
    """
    from app.services.psv.two_point_omega import _f_eta_c

    omega = 1.482
    samples = [0.1, 0.3, 0.5, 0.7, 0.9]
    f_values = [_f_eta_c(eta, omega) for eta in samples]
    # 相邻 f 值递增（允许极小浮动容差）
    diffs = [f_values[i + 1] - f_values[i] for i in range(len(f_values) - 1)]
    assert all(d > 0 for d in diffs), f"f(η_c) 不单调：{f_values}"


# --- Eq C.13b: P_c = η_c × P_o ---


def test_eq_c13b_p_critical_matches_pdf():
    """Eq C.25 PDF 算例：P_c = η_c × P_o ≈ 0.66 × 556,379 = 367,210 Pa。

    实际根 0.6565 → P_c ≈ 365,200 Pa（与图读值 367,210 偏差 ~0.5%）。
    """
    r = omega_two_point_area(_worked_input())
    expected_P_c = 367_210.0
    assert math.isclose(r.P_critical_pa, expected_P_c, rel_tol=1e-2), (
        f"P_c={r.P_critical_pa:.0f} Pa 应≈{expected_P_c:.0f} Pa（rel 1%）"
    )


# --- Step 2 critical/subcritical 判定 ---


def test_flow_regime_critical_when_P_c_ge_P_a():
    """worked example: P_c (367 kPa) > P_a (205 kPa) → critical。"""
    r = omega_two_point_area(_worked_input())
    assert r.flow_regime == "critical", (
        f"P_c={r.P_critical_pa:.0f} > P_a={_WORKED_P_A:.0f} 应为 critical"
    )


# --- Step 3 critical: Eq C.18 mass flux ---


def test_eq_c18_mass_flux_matches_pdf():
    """Eq C.27 PDF 算例：G = 0.66 × √(556,379 / (0.01945 × 1.482)) = 2,900 kg/s·m²。

    PDF 用图读 η_c=0.66；精确根 0.6565 → G ≈ 2,885 kg/s·m²（rel ~0.5%）。
    """
    r = omega_two_point_area(_worked_input())
    expected_G = 2_900.0
    assert math.isclose(r.mass_flux_kgs_per_m2, expected_G, rel_tol=1e-2), (
        f"G={r.mass_flux_kgs_per_m2:.1f} 应≈{expected_G:.1f}（rel 1%）"
    )


# --- Step 4: Eq C.21 area ---


def test_eq_c21_area_matches_pdf_si():
    """Eq C.29 PDF 算例：A = 277.8 × 216,560 / (0.85 × 1.0 × 1.0 × 1.0 × 2,900) = 24,400 mm²。"""
    r = omega_two_point_area(_worked_input())
    expected_A_mm2 = 24_400.0
    assert math.isclose(r.area_mm2, expected_A_mm2, rel_tol=1.5e-2), (
        f"A={r.area_mm2:.1f} mm² 应≈{expected_A_mm2:.1f} mm²（rel 1.5%）"
    )


def test_area_m2_equals_mm2_times_1e_minus_6():
    """A_m² = A_mm² × 1e-6。"""
    r = omega_two_point_area(_worked_input())
    assert math.isclose(r.area_m2, r.area_mm2 * 1e-6, rel_tol=1e-12)


# --- Eq C.19 subcritical 分支 ---


def test_subcritical_branch_when_P_a_exceeds_P_c():
    """人为提高背压使 P_c < P_a → subcritical flow regime。

    物理上 ω=1.482 时 η_c ≈ 0.66，所以 P_a > 0.66 × P_o 触发亚临界。
    P_a = 0.7 × P_o = 389,465 Pa 即满足。
    """
    inp = TwoPointOmegaInput(
        mass_flow_kgs=_WORKED_W_KGS,
        P_relieving_pa=_WORKED_P_O,
        P_backpressure_pa=0.7 * _WORKED_P_O,  # 389,465 Pa > P_c 367,210
        v_inlet_m3_per_kg=_WORKED_V_O,
        v_vapor_0_9Po_m3_per_kg=_WORKED_V_G,
        K_d=_WORKED_K_D,
    )
    r = omega_two_point_area(inp)
    assert r.flow_regime == "subcritical", (
        f"P_a={inp.P_backpressure_pa:.0f} > P_c={r.P_critical_pa:.0f} 应为 subcritical"
    )
    # 亚临界 G 通常 < 临界 G（流通阻力更大）
    G_critical = 2_900.0
    assert r.mass_flux_kgs_per_m2 < G_critical, (
        f"subcritical G={r.mass_flux_kgs_per_m2:.1f} 应<critical G={G_critical:.1f}"
    )
    # 亚临界 area 通常 > 临界 area
    assert r.area_mm2 > 24_400.0, (
        f"subcritical A={r.area_mm2:.0f} mm² 应>critical A=24,400 mm²"
    )


# --- K 系数缩放 ---


def test_K_d_scales_area_inversely():
    """K_d 加倍 → 面积减半（Eq C.21 线性反比）。

    同 K_b/K_c/K_v 任一加倍：area 减半（不区分系数类型，验证乘积影响）。
    """
    base = omega_two_point_area(_worked_input())
    high_kd = omega_two_point_area(
        TwoPointOmegaInput(
            mass_flow_kgs=_worked_input().mass_flow_kgs,
            P_relieving_pa=_worked_input().P_relieving_pa,
            P_backpressure_pa=_worked_input().P_backpressure_pa,
            v_inlet_m3_per_kg=_worked_input().v_inlet_m3_per_kg,
            v_vapor_0_9Po_m3_per_kg=_worked_input().v_vapor_0_9Po_m3_per_kg,
            K_d=2 * _WORKED_K_D,  # 加倍
        )
    )
    assert math.isclose(high_kd.area_mm2, base.area_mm2 / 2, rel_tol=1e-9), (
        f"K_d×2 后 area 应减半：base={base.area_mm2:.1f}, high_kd={high_kd.area_mm2:.1f}"
    )


# --- 公式溯源 metadata ---


def test_formula_ref_api520_9th_annex_c_2_2():
    """formula_ref 必须是 API_520 / 9th / Annex C.2.2。"""
    r = omega_two_point_area(_worked_input())
    assert r.formula_ref.standard == "API_520"
    assert r.formula_ref.version == "9th"
    assert r.formula_ref.clause == "Annex C.2.2"


# --- 输入校验 ---


@pytest.mark.parametrize(
    "field,value",
    [
        ("mass_flow_kgs", -1.0),
        ("mass_flow_kgs", 0.0),
        ("P_relieving_pa", -1.0),
        ("P_relieving_pa", 0.0),
        ("P_backpressure_pa", -1.0),
        ("P_backpressure_pa", 0.0),
        ("v_inlet_m3_per_kg", 0.0),
        ("v_inlet_m3_per_kg", -1.0),
        ("v_vapor_0_9Po_m3_per_kg", 0.0),
        ("v_vapor_0_9Po_m3_per_kg", -1.0),
    ],
)
def test_input_validation_rejects_non_positive(field, value):
    """所有物理量必须 > 0。"""
    base_kwargs = dict(
        mass_flow_kgs=_WORKED_W_KGS,
        P_relieving_pa=_WORKED_P_O,
        P_backpressure_pa=_WORKED_P_A,
        v_inlet_m3_per_kg=_WORKED_V_O,
        v_vapor_0_9Po_m3_per_kg=_WORKED_V_G,
    )
    base_kwargs[field] = value
    with pytest.raises(TwoPointOmegaInputError):
        omega_two_point_area(TwoPointOmegaInput(**base_kwargs))


def test_input_validation_rejects_P_a_ge_P_o():
    """P_a ≥ P_o 物理上无效（背压比 η_a ≥ 1，Eq C.19 开方项为负）。"""
    inp = TwoPointOmegaInput(
        mass_flow_kgs=_WORKED_W_KGS,
        P_relieving_pa=_WORKED_P_O,
        P_backpressure_pa=_WORKED_P_O,  # 等于 P_o
        v_inlet_m3_per_kg=_WORKED_V_O,
        v_vapor_0_9Po_m3_per_kg=_WORKED_V_G,
    )
    with pytest.raises(TwoPointOmegaInputError):
        omega_two_point_area(inp)


def test_input_validation_rejects_v_g_lt_v_o():
    """v_g < v_o → ω < 0，无 vapor 释放 → 应改走 subcooled liquid 路径（C.2.3）。"""
    inp = TwoPointOmegaInput(
        mass_flow_kgs=_WORKED_W_KGS,
        P_relieving_pa=_WORKED_P_O,
        P_backpressure_pa=_WORKED_P_A,
        v_inlet_m3_per_kg=_WORKED_V_G,  # 故意让 v_o = 0.02265（蒸汽比容）
        v_vapor_0_9Po_m3_per_kg=_WORKED_V_O,  # 故意让 v_g = 0.01945（更小）
    )
    with pytest.raises(TwoPointOmegaInputError, match="ω=.*< 0"):
        omega_two_point_area(inp)


# --- 退化边界 ---


def test_omega_approaches_zero_for_pure_gas():
    """v_g / v_o → 1 (单相气体极限) → ω → 0。

    注：omega=0 在本函数内 early return η_c=0.5（物理上应改走 §5.6.3），
    但本函数仍正确返回结果用于诊断。
    """
    inp = TwoPointOmegaInput(
        mass_flow_kgs=_WORKED_W_KGS,
        P_relieving_pa=_WORKED_P_O,
        P_backpressure_pa=_WORKED_P_A,
        v_inlet_m3_per_kg=0.02265,
        v_vapor_0_9Po_m3_per_kg=0.02266,  # 极小差异模拟纯气
    )
    r = omega_two_point_area(inp)
    assert r.omega < 0.01, f"omega={r.omega} 应接近 0（单相气体）"


def test_high_omega_liquid_dominated():
    """v_g / v_o >> 1 (蒸汽为主/液体稀薄) → ω → 高值。

    例：v_g = 0.05, v_o = 0.001 → ω = 9 × (50 - 1) = 441（液体高度雾化）。
    """
    inp = TwoPointOmegaInput(
        mass_flow_kgs=_WORKED_W_KGS,
        P_relieving_pa=_WORKED_P_O,
        P_backpressure_pa=_WORKED_P_A,
        v_inlet_m3_per_kg=0.001,  # 液体高度压缩
        v_vapor_0_9Po_m3_per_kg=0.05,  # 蒸汽稀薄
    )
    r = omega_two_point_area(inp)
    # ω = 9 × (50 - 1) = 441（仍能求根，bisection 收敛）
    assert r.omega > 100, f"omega={r.omega} 应>100（v_g/v_o 远大于 1）"
    # 大 ω 时 η_c → 1（接近纯气体极限）
    assert r.eta_critical > 0.85, f"eta_c={r.eta_critical:.3f} 大 ω 应>0.85"
