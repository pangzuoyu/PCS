"""P6-x Phase 1：vessel_service 几何 helper 单元测试（ADR-0041 v7 §4 公式重构方案）。

6 helper：_lerp / _trapz / _circular_segment_area_r_h /
          _circular_segment_area_h_m / _sphere_partial_volume_h_m /
          _head_partial_volume_horizontal（数值积分 n_points=200）

依据：ADR-0041 v7 §4 §1-§3 公式推导 + §5 v6 数值积分验证表
（HEMI H=R=1.527、2:1 R=0.7634 等独立推导值）。
"""
from __future__ import annotations

import math

import pytest

from app.services.vessel.vessel_service import (
    VesselInputError,
    _circular_segment_area_h_m,
    _circular_segment_area_r_h,
    _head_partial_volume_horizontal,
    _lerp,
    _sphere_partial_volume_h_m,
    _trapz,
)

# ============================================================================
# 1. _lerp / _trapz（线性插值与梯形积分，数学基元）
# ============================================================================


def test_lerp_endpoints():
    """_lerp 端点：t=0→a；t=1→b。"""
    assert _lerp(0.0, 10.0, 0.0) == 0.0
    assert _lerp(0.0, 10.0, 1.0) == 10.0
    assert _lerp(-1.0, 1.0, 0.5) == 0.0


def test_lerp_midpoint():
    """_lerp 中点：t=0.5。"""
    assert math.isclose(_lerp(2.0, 6.0, 0.5), 4.0)


def test_trapz_linear():
    """_trapz 线性函数精确积分。"""
    # ∫_0^1 x dx = 0.5
    xs = [0.0, 0.25, 0.5, 0.75, 1.0]
    ys = [x for x in xs]
    assert math.isclose(_trapz(ys, xs), 0.5, rel_tol=1e-9)


def test_trapz_constant():
    """_trapz 常数函数 = const × (x_max − x_min)。"""
    xs = [0.0, 1.0, 2.0, 3.0]
    ys = [5.0] * 4
    assert math.isclose(_trapz(ys, xs), 15.0)


def test_trapz_empty_or_single():
    """_trapz 空 / 单元素返回 0（不抛异常）。"""
    assert _trapz([], []) == 0.0
    assert _trapz([1.0], [0.0]) == 0.0
    # 长度不匹配也安全
    assert _trapz([1.0, 2.0], [0.0]) == 0.0


# ============================================================================
# 2. _circular_segment_area_r_h（圆内液面深度 h 部分圆段面积，强公式 <0.1%）
# ============================================================================


def test_circular_segment_r_h_full_circle():
    """h = 2r 整圆填充。"""
    r = 1.0
    A = _circular_segment_area_r_h(r, 2 * r)
    assert math.isclose(A, math.pi * r**2, rel_tol=1e-12)


def test_circular_segment_r_h_half_circle():
    """h = r 半圆填充 = π·r²/2。"""
    r = 1.0
    A = _circular_segment_area_r_h(r, r)
    assert math.isclose(A, math.pi * r**2 / 2, rel_tol=1e-9)


def test_circular_segment_r_h_empty():
    """h ≤ 0 = 0（无液相）。"""
    assert _circular_segment_area_r_h(1.0, 0.0) == 0.0
    assert _circular_segment_area_r_h(1.0, -0.5) == 0.0


def test_circular_segment_r_h_known_value():
    """h = r/2 对账：cos_arg = 0.5，A = r²·(π/3 − 0.5·(√3)/2)。"""
    r = 2.0
    h = r / 2  # cos_arg = (r-h)/r = 0.5
    A_expected = r**2 * math.acos(0.5) - (r - h) * math.sqrt(h * (2 * r - h))
    # 即 r²·(π/3 − (r/2)·√(3r²/4))
    assert math.isclose(_circular_segment_area_r_h(r, h), A_expected, rel_tol=1e-12)


# ============================================================================
# 3. _circular_segment_area_h_m（HORIZONTAL cylinder 横截面液相面积）
# ============================================================================


def test_circular_segment_h_m_D_1_8_H_0_9_50pct():
    """D=1.8, H=0.9 (50% fill) → A_seg=1.5708 m² (= π/2)。

    对账验证：A_seg × L（L=4.5）= 5.7255 m³
    与 WS-CA-PR-013 Horiz-Vol&Area-SI 50% fill V_cyl 一致。
    """
    D = 1.8
    H = 0.9
    A_seg = _circular_segment_area_h_m(D, H)
    # 50% 填充 = 半圆 = π·D²/8
    A_expected = math.pi * D**2 / 8
    assert math.isclose(A_seg, A_expected, rel_tol=1e-6)


def test_circular_segment_h_m_empty_and_full():
    """H ≤ 0 = 0；H ≥ D = 整圆 π·D²/4。"""
    D = 1.8
    assert _circular_segment_area_h_m(D, 0.0) == 0.0
    assert _circular_segment_area_h_m(D, -0.5) == 0.0
    assert math.isclose(
        _circular_segment_area_h_m(D, D), math.pi * D**2 / 4, rel_tol=1e-12
    )


# ============================================================================
# 4. _sphere_partial_volume_h_m（球缺公式；SPHERICAL / HEMI 封头通用）
# ============================================================================


def test_sphere_partial_volume_zero():
    """H = 0 → 0（无液相）。"""
    assert _sphere_partial_volume_h_m(1.8, 0.0) == 0.0


def test_sphere_partial_volume_full_sphere():
    """H = D → 全球 = π·D³/6。"""
    D = 1.8
    assert math.isclose(
        _sphere_partial_volume_h_m(D, D), math.pi * D**3 / 6, rel_tol=1e-12
    )


def test_sphere_partial_volume_H_R_hemisphere():
    """H = R = D/2 → 半球 = π·D³/12。"""
    D = 1.8
    R = D / 2
    assert math.isclose(
        _sphere_partial_volume_h_m(D, R), math.pi * D**3 / 12, rel_tol=1e-12
    )


def test_sphere_partial_volume_H_R_4_3():
    """H = 2R/3 球缺闭式：π·H²·(3R − H)/3。

    H = 2R/3 → V = π·(2R/3)²·(3R − 2R/3)/3 = π·4R²/9·7R/9 = 28π·R³/81
    """
    D = 1.8
    R = D / 2
    H = 2 * R / 3
    expected = math.pi * (2 * R / 3) ** 2 * (3 * R - 2 * R / 3) / 3
    assert math.isclose(_sphere_partial_volume_h_m(D, H), expected, rel_tol=1e-9)


# ============================================================================
# 5. _head_partial_volume_horizontal（HORIZONTAL 封头数值积分，n_points=200）
# ============================================================================


def test_head_partial_volume_horizontal_FLAT_zero():
    """FLAT 封头：0（无几何体）。"""
    assert _head_partial_volume_horizontal("FLAT", 1.8, 0.9) == 0.0


def test_head_partial_volume_horizontal_HEMI_H_R_half_fill():
    """HEMI 卧式 50% fill（H=R=0.9, D=1.8）：两端 V_two_heads = 2·(1/3)πR³ = 1.527 m³。

    v7 关键几何洞察：HEMI 卧式 50% fill 时每 z 截面仅半填充（液面在 cylinder 中心 y=0，
    深度 = r(z) = 半径），不是整圆填充。V_single = (1/3)πR³，V_two_heads = (2/3)πR³。
    """
    D = 1.8
    H = 0.9  # = R
    R = D / 2
    expected = (2.0 / 3.0) * math.pi * R**3  # V_two_heads
    V = _head_partial_volume_horizontal("HEMISPHERICAL", D, H)
    assert math.isclose(V, expected, rel_tol=1e-3), (
        f"HEMI HORIZ 50% fill: V={V:.4f} 期望 {expected:.4f} (相对误差 <1e-3)"
    )


def test_head_partial_volume_horizontal_HEMI_H_D_full():
    """HEMI 卧式满 fill（H=D）：两端 = 球冠侧面积 2·V_full_HEMI = π·D³/6。"""
    D = 1.8
    H = D  # 满 fill
    expected = math.pi * D**3 / 6
    V = _head_partial_volume_horizontal("HEMISPHERICAL", D, H)
    assert math.isclose(V, expected, rel_tol=1e-12)


def test_head_partial_volume_horizontal_2to1_H_R():
    """2:1 ELLIPTICAL 卧式 50% fill（D=1.8, H=0.9, R=0.9, b=R/2=0.45）。

    对账验证（ADR v7 §5 表）：
      - V_single = R²·π·b/3（积分闭式：h(z)=r(z)，A(z)=r²·π/2）
      - V_single = 1·π·0.5/3 = π/6 ≈ 0.5236
      - V_two_heads = 2·π/6 = π/3 ≈ 1.0472
    """
    D = 1.8
    H = 0.9  # = R
    R = D / 2
    b = R / 2
    # 闭式：V_single = R²·π·b/3
    V_single_expected = R**2 * math.pi * b / 3
    V_two_expected = 2 * V_single_expected  # = π/3
    V = _head_partial_volume_horizontal("2:1_ELLIPTICAL", D, H)
    assert math.isclose(V, V_two_expected, rel_tol=1e-3), (
        f"2:1 HORIZ 50% fill: V={V:.4f} 期望 {V_two_expected:.4f}"
    )


def test_head_partial_volume_horizontal_TORI_not_implemented():
    """TORISPHERICAL 仍 NotImplementedError（Q-1 待工艺室 2026-11-30 签发）。"""
    with pytest.raises(NotImplementedError):
        _head_partial_volume_horizontal("TORISPHERICAL", 1.8, 0.9)


def test_head_partial_volume_horizontal_unknown_raises():
    """未知 head_type 抛 VesselInputError。"""
    with pytest.raises(VesselInputError):
        _head_partial_volume_horizontal("UNKNOWN", 1.8, 0.9)  # type: ignore[arg-type]


def test_head_partial_volume_horizontal_H_zero_zero():
    """H = 0 → 0（无液相）。"""
    assert _head_partial_volume_horizontal("HEMISPHERICAL", 1.8, 0.0) == 0.0
    assert _head_partial_volume_horizontal("2:1_ELLIPTICAL", 1.8, 0.0) == 0.0


def test_head_partial_volume_horizontal_HEMI_n_points_precision():
    """HEMI H=R 验证：n_points=50 vs n=200 vs n=1000 偏差 <1e-4（强公式容差）。"""
    D, H = 1.8, 0.9
    V_200 = _head_partial_volume_horizontal("HEMISPHERICAL", D, H, n_points=200)
    V_1000 = _head_partial_volume_horizontal("HEMISPHERICAL", D, H, n_points=1000)
    assert math.isclose(V_200, V_1000, rel_tol=1e-4), (
        f"n=200 vs n=1000 偏差: {abs(V_200 - V_1000) / V_1000:.4e} > 1e-4"
    )