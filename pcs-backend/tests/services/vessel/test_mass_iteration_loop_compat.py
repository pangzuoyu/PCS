"""P6-x Phase 1：vessel_shape 透传 + HORIZONTAL/SPHERICAL/p12 兼容性测试（ADR-0041 v7 §7 §F8）。

覆盖：
  1. _mass_at_variable vessel_shape 透传（HORIZONTAL/SPHERICAL 经 calc_partial_volume）
  2. calc_partial_volume vessel_shape 3 路径独立返回 + vessel_shape_used 字段
  3. calc_wetted_area 同上
  4. p12 拒绝：FLAT × SPHERICAL → VesselInputError（ADR-0041 v7 F8）
  5. 默认 vessel_shape='VERTICAL' 向后兼容 5 调用方（现有 fixture 全过）
"""
from __future__ import annotations

import math

import pytest

from app.services.vessel.vessel_service import (
    MassIterationInput,
    PartialVolumeInput,
    VesselInputError,
    WettedAreaInput,
    calc_partial_volume,
    calc_wetted_area,
    mass_iteration_loop,
)

# ============================================================================
# 1. vessel_shape 3 路径独立返回（默认 VERTICAL 行为不变）
# ============================================================================


def test_default_vessel_shape_is_VERTICAL_backward_compat():
    """默认 vessel_shape='VERTICAL'（向后兼容 5 调用方）。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=1.0,
    )
    result = calc_partial_volume(inp)
    assert result.vessel_shape_used == "VERTICAL"


def test_partial_volume_VERTICAL_branch():
    """VERTICAL 分支：vessel_shape_used='VERTICAL'。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=1.0,
        vessel_shape="VERTICAL",
    )
    result = calc_partial_volume(inp)
    assert result.vessel_shape_used == "VERTICAL"
    assert result.partial_volume_m3 > 0.0
    assert result.total_volume_m3 > result.partial_volume_m3
    assert result.cylinder_volume_m3 > 0.0


def test_partial_volume_HORIZONTAL_branch():
    """HORIZONTAL 分支：cylinder 横截面 + 封头两端数值积分。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=0.9,  # 50% fill
        vessel_shape="HORIZONTAL",
    )
    result = calc_partial_volume(inp)
    assert result.vessel_shape_used == "HORIZONTAL"
    # 50% fill cylinder：A_seg = π·D²/8 = π·3.24/8 ≈ 1.2723
    # V_cyl ≈ 1.2723 × 4.5 ≈ 5.7255（与 WS-CA-PR-013 Horiz-Vol&Area-SI 一致）
    assert math.isclose(result.cylinder_volume_m3, 5.7255, rel_tol=1e-3)
    # V_head 数值积分：D=1.8, H=0.9=R, 2:1 ELLIPSE 闭式 V_two = 2·R²·π·b/3
    # R=0.9, b=R/2=0.45 → V_two ≈ 0.7634 m³
    R = 0.9
    b = R / 2
    V_head_expected = 2 * R**2 * math.pi * b / 3
    assert math.isclose(result.head_volume_m3, V_head_expected, rel_tol=1e-3)


def test_partial_volume_SPHERICAL_branch():
    """SPHERICAL 分支：球缺公式 π·H²·(3R − H)/3。

    D=1.8, H=0.9 (= R): V = π·R²·(3R − R)/3 = π·R²·2R/3 = 2π·R³/3 = 2π·(0.9)³/3
    注意：head_type 必须非 FLAT（FLAT × SPHERICAL 是 p12 N/A → 拒绝）；
    SPHERICAL 分支不调用 head 公式，head_type 实际忽略但需合法值。
    """
    inp = PartialVolumeInput(
        D_m=1.8, L_m=0.0, head_type="2:1_ELLIPTICAL", H_m=0.9,
        vessel_shape="SPHERICAL",
    )
    result = calc_partial_volume(inp)
    assert result.vessel_shape_used == "SPHERICAL"
    assert result.cylinder_volume_m3 == 0.0  # 球罐无 cylinder
    R = 0.9
    V_expected = 2 * math.pi * R**3 / 3
    assert math.isclose(result.partial_volume_m3, V_expected, rel_tol=1e-12)


def test_partial_volume_SPHERICAL_full_sphere():
    """SPHERICAL H=D 满 fill = 全球 = π·D³/6。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=0.0, head_type="2:1_ELLIPTICAL", H_m=1.8,
        vessel_shape="SPHERICAL",
    )
    result = calc_partial_volume(inp)
    assert math.isclose(result.partial_volume_m3, math.pi * 1.8**3 / 6, rel_tol=1e-12)
    assert math.isclose(result.total_volume_m3, math.pi * 1.8**3 / 6, rel_tol=1e-12)


def test_wetted_area_VERTICAL_branch_default():
    """VERTICAL 分支：vessel_shape_used='VERTICAL'（向后兼容）。"""
    inp = WettedAreaInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=1.0,
    )
    result = calc_wetted_area(inp)
    assert result.vessel_shape_used == "VERTICAL"


def test_wetted_area_HORIZONTAL_branch():
    """HORIZONTAL 分支：cylinder 润湿弧长 × L + 封头润湿面积。"""
    inp = WettedAreaInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=0.9,  # 50% fill
        vessel_shape="HORIZONTAL",
    )
    result = calc_wetted_area(inp)
    assert result.vessel_shape_used == "HORIZONTAL"
    # 50% fill cylinder：润湿弧长 = D·arccos((R-h)/R) = D·arccos(0) = D·π/2
    # A_cyl = π/2·D·L = π/2·1.8·4.5 ≈ 12.73
    A_cyl_expected = math.pi / 2 * 1.8 * 4.5
    assert math.isclose(result.cylinder_area_m2, A_cyl_expected, rel_tol=1e-6)


def test_wetted_area_SPHERICAL_branch():
    """SPHERICAL 分支：球冠侧面积 2πR·H。

    注意：head_type 必须非 FLAT（FLAT × SPHERICAL 是 p12 N/A → 拒绝）；
    SPHERICAL 分支不调用 head 公式，head_type 实际忽略但需合法值。
    """
    inp = WettedAreaInput(
        D_m=1.8, L_m=0.0, head_type="2:1_ELLIPTICAL", H_m=0.9,
        vessel_shape="SPHERICAL",
    )
    result = calc_wetted_area(inp)
    assert result.vessel_shape_used == "SPHERICAL"
    # A_partial = 2πR·H = 2π·0.9·0.9
    A_expected = 2 * math.pi * 0.9 * 0.9
    assert math.isclose(result.wetted_area_m2, A_expected, rel_tol=1e-12)


# ============================================================================
# 2. p12 拒绝（FLAT × SPHERICAL 几何退化）
# ============================================================================


def test_partial_volume_p12_FLAT_SPERICAL_raises():
    """p12（FLAT × SPHERICAL）→ VesselInputError（ADR-0041 v7 F8）。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=0.0, head_type="FLAT", H_m=0.5,
        vessel_shape="SPHERICAL",
    )
    with pytest.raises(VesselInputError) as exc_info:
        calc_partial_volume(inp)
    # 错误信息匹配 ADR-0041 v7 F8 + spec §6
    assert "FLAT" in str(exc_info.value)
    assert "SPHERICAL" in str(exc_info.value)
    assert "几何退化" in str(exc_info.value)


def test_wetted_area_p12_FLAT_SPERICAL_raises():
    """p12（FLAT × SPHERICAL）calc_wetted_area 同样拒绝。"""
    inp = WettedAreaInput(
        D_m=1.8, L_m=0.0, head_type="FLAT", H_m=0.5,
        vessel_shape="SPHERICAL",
    )
    with pytest.raises(VesselInputError) as exc_info:
        calc_wetted_area(inp)
    assert "FLAT × SPHERICAL" in str(exc_info.value)


def test_partial_volume_FLAT_VERTICAL_accepted():
    """FLAT × VERTICAL 合法（p11 路径，不拒绝）。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="FLAT", H_m=1.0,
        vessel_shape="VERTICAL",
    )
    result = calc_partial_volume(inp)
    assert result.vessel_shape_used == "VERTICAL"
    assert result.head_volume_m3 == 0.0  # FLAT 封头无体积贡献


def test_partial_volume_2to1_SPHERICAL_accepted():
    """2:1 ELLIPTICAL × SPHERICAL 合法（虽工程上不常见，但非 p12 退化）。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=0.0, head_type="2:1_ELLIPTICAL", H_m=0.5,
        vessel_shape="SPHERICAL",
    )
    # 球罐走 _sphere_partial_volume_h_m 路径，不调用 head 公式
    result = calc_partial_volume(inp)
    assert result.vessel_shape_used == "SPHERICAL"


# ============================================================================
# 3. mass_iteration_loop vessel_shape 透传（ADR-0041 v7 §7）
# ============================================================================


def test_mass_iteration_VERTICAL_D_vessel_shape_passed_through():
    """VERTICAL mass_iteration 透传 vessel_shape='VERTICAL'（默认路径）。"""
    inp = MassIterationInput(
        target_mass_kg=5774.0,
        rho_L_kg_m3=1000.0,
        rho_V_kg_m3=1.2,
        vessel_shape="VERTICAL",
        head_type="2:1_ELLIPTICAL",
        initial_D_m=1.5,
        initial_L_m=5.0,
        variable="D",
        mass_model="OPERATING",
    )
    result = mass_iteration_loop(inp)
    assert result.converged
    assert result.formula_ref["vessel_shape"] == "VERTICAL"


def test_mass_iteration_HORIZONTAL_L_uses_new_formula():
    """HORIZONTAL + variable='L'：透传 vessel_shape=HORIZONTAL 给 calc_partial_volume。

    ADR-0041 v7 §7：mass_iteration_loop 内部 _mass_at_variable 必须把 vessel_shape 透传，
    否则会把 HORIZONTAL 误走 VERTICAL 公式（旧 v6 bug）。
    """
    inp = MassIterationInput(
        target_mass_kg=2387.0,
        rho_L_kg_m3=900.0,
        rho_V_kg_m3=2.0,
        vessel_shape="HORIZONTAL",
        head_type="2:1_ELLIPTICAL",
        initial_D_m=2.0,
        initial_L_m=4.0,
        variable="L",
        mass_model="OPERATING",
    )
    result = mass_iteration_loop(inp)
    assert result.converged
    assert result.formula_ref["vessel_shape"] == "HORIZONTAL"
    # v7 公式正确解 L ≈ 1.02 m（旧 v6 bug → 5.07 m 错解）
    assert math.isclose(result.final_variable_m, 1.02, rel_tol=1e-2)


def test_mass_iteration_SPHERICAL_D():
    """SPHERICAL + variable='D'：球缺公式直走（不调 calc_partial_volume）。"""
    inp = MassIterationInput(
        target_mass_kg=4000.0,
        rho_L_kg_m3=850.0,
        rho_V_kg_m3=1.5,
        vessel_shape="SPHERICAL",
        head_type="FLAT",
        initial_D_m=1.5,
        initial_L_m=0.0,
        variable="D",
        mass_model="OPERATING",
    )
    result = mass_iteration_loop(inp)
    assert result.converged
    assert result.formula_ref["vessel_shape"] == "SPHERICAL"
    # 与 test_mass_iteration_spherical_D_converges 一致
    assert math.isclose(result.final_variable_m, 2.0791, rel_tol=1e-3)


# ============================================================================
# 4. 边界 case（H=0, H=D, H>L+2b 等）
# ============================================================================


def test_partial_volume_HOR_D_zero_horizontal():
    """HORIZONTAL H=0 → partial=0（无液相）。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=0.0,
        vessel_shape="HORIZONTAL",
    )
    result = calc_partial_volume(inp)
    assert result.partial_volume_m3 == 0.0


def test_partial_volume_HOR_D_full_horizontal():
    """HORIZONTAL H=D → partial = V_total（满液位）。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=4.5, head_type="2:1_ELLIPTICAL", H_m=1.8,
        vessel_shape="HORIZONTAL",
    )
    result = calc_partial_volume(inp)
    # partial == total（满 fill）
    assert math.isclose(
        result.partial_volume_m3, result.total_volume_m3, rel_tol=1e-9
    )


def test_partial_volume_SPHERICAL_H_zero():
    """SPHERICAL H=0 → partial=0。"""
    inp = PartialVolumeInput(
        D_m=1.8, L_m=0.0, head_type="2:1_ELLIPTICAL", H_m=0.0,
        vessel_shape="SPHERICAL",
    )
    result = calc_partial_volume(inp)
    assert result.partial_volume_m3 == 0.0