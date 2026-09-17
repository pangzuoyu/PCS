"""P5-2-3 重力沉降器测试。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md 行 232-245：
- Stokes 沉降手算（d=10μm, Re_p≈0.0022 → Stokes 区）
- ChEDL 优先（V1.8 F-13-2 包装层）—— 调 chedl_wrapper.v_terminal
- ChEDL 内置 Stokes/Intermediate/Newton 三区迭代收敛（V1.8 F-13-4 修正：
  函数名 v_terminal 而非 v_sphere；模块 fluids.* 而非 fluids.particle_size.*）
- 叶片/纤维经验法（spec §3.2.2）
- 测试：3 区域各 1 例 + Re≈0.1 边界 + Re≈1000 边界
"""
from __future__ import annotations

import math

import pytest

from app.services.sep_equip.gravity_separator_service import (
    GravitySeparatorInput,
    GravitySeparatorResult,
    Region,
    SeparatorType,
    calc_gravity_separator,
)


def _stokes_input() -> GravitySeparatorInput:
    """Stokes 区：d=10μm, ρ_p=1100, ρ_f=1.2 → Re_p≈0.0022 < 0.1。"""
    return GravitySeparatorInput(
        d_particle_m=10e-6,
        rho_particle_kg_m3=1100.0,
        rho_fluid_kg_m3=1.2,
        mu_fluid_pa_s=1.8e-5,
        height_setting_m=1.0,
        horizontal_velocity_ms=0.1,
        separator_type="PLAIN",
    )


def _intermediate_input() -> GravitySeparatorInput:
    """Intermediate 区：d=100μm → Re_p≈1.86 (0.1 < Re < 1000)。"""
    return GravitySeparatorInput(
        d_particle_m=100e-6,
        rho_particle_kg_m3=1100.0,
        rho_fluid_kg_m3=1.2,
        mu_fluid_pa_s=1.8e-5,
        height_setting_m=1.0,
        horizontal_velocity_ms=0.1,
        separator_type="PLAIN",
    )


def _newton_input() -> GravitySeparatorInput:
    """Newton 区：d=10mm → Re_p≈11310 > 1000。"""
    return GravitySeparatorInput(
        d_particle_m=10e-3,
        rho_particle_kg_m3=1100.0,
        rho_fluid_kg_m3=1.2,
        mu_fluid_pa_s=1.8e-5,
        height_setting_m=1.0,
        horizontal_velocity_ms=0.1,
        separator_type="PLAIN",
    )


# ============================================================================
# 1. 三区各 1 例（Re_p 自动收敛）
# ============================================================================


def test_stokes_region_small_particle():
    """d=10μm → Re_p≈0.0022 → STOKES 区（ChEDL 收敛）。"""
    result = calc_gravity_separator(_stokes_input())
    assert result.region == "STOKES"
    assert result.re_particle < 0.1
    # ChEDL 收敛 v_t ≈ 0.003326 m/s（d=10μm）
    assert math.isclose(result.settling_velocity_ms, 0.003326, rel_tol=0.01)
    # 沉降长度：H × V_h / V_t = 1.0 × 0.1 / 0.003326 ≈ 30 m
    assert result.chamber_length_m > 20.0
    assert result.chamber_width_m > 0


def test_intermediate_region_medium_particle():
    """d=100μm → Re_p≈1.86 → INTERMEDIATE 区。"""
    result = calc_gravity_separator(_intermediate_input())
    assert result.region == "INTERMEDIATE"
    assert 0.1 < result.re_particle < 1000
    # ChEDL v_t ≈ 0.278501 m/s（d=100μm）
    assert math.isclose(result.settling_velocity_ms, 0.278501, rel_tol=0.01)


def test_newton_region_large_particle():
    """d=10mm → Re_p≈11310 → NEWTON 区。"""
    result = calc_gravity_separator(_newton_input())
    assert result.region == "NEWTON"
    assert result.re_particle > 1000
    # ChEDL v_t ≈ 16.97 m/s（d=10mm）
    assert math.isclose(result.settling_velocity_ms, 16.97, rel_tol=0.05)


# ============================================================================
# 2. Stokes 公式精确验证（小颗粒 Re<0.1 → Stokes 解 = ChEDL 收敛解）
# ============================================================================


def test_stokes_formula_exact_match():
    """Stokes 公式手算 vs ChEDL 收敛解偏差 ≤1%（Stokes 区严格适用）。"""
    inp = GravitySeparatorInput(
        d_particle_m=5e-6,  # 5μm → Re_p < 0.01（极小颗粒 Stokes 严格）
        rho_particle_kg_m3=1100.0,
        rho_fluid_kg_m3=1.2,
        mu_fluid_pa_s=1.8e-5,
        height_setting_m=1.0,
        horizontal_velocity_ms=0.1,
        separator_type="PLAIN",
    )
    result = calc_gravity_separator(inp)
    # 手算 Stokes: v_t = g·Δρ·d² / (18μ)
    g = 9.80665
    v_stokes = g * (1100.0 - 1.2) * (5e-6) ** 2 / (18.0 * 1.8e-5)
    assert math.isclose(result.settling_velocity_ms, v_stokes, rel_tol=0.01)
    assert result.region == "STOKES"


# ============================================================================
# 3. 叶片/纤维效率系数
# ============================================================================


def test_vane_separator_shortens_chamber():
    """VANE 类型在 PLAIN 基础上缩短 chamber_length（spec §3.2.2 经验效率 0.5）。"""
    plain = calc_gravity_separator(_intermediate_input())
    vane_input = GravitySeparatorInput(
        d_particle_m=100e-6,
        rho_particle_kg_m3=1100.0,
        rho_fluid_kg_m3=1.2,
        mu_fluid_pa_s=1.8e-5,
        height_setting_m=1.0,
        horizontal_velocity_ms=0.1,
        separator_type="VANE",
    )
    vane = calc_gravity_separator(vane_input)
    # VANE 沉降距离 = PLAIN × 0.5（叶片效率）
    assert vane.chamber_length_m < plain.chamber_length_m
    assert math.isclose(
        vane.chamber_length_m, plain.chamber_length_m * 0.5, rel_tol=0.01
    )


def test_fiber_separator_factor():
    """FIBER 类型效率系数 0.3（spec §3.2.2）。"""
    plain = calc_gravity_separator(_intermediate_input())
    fiber_input = GravitySeparatorInput(
        d_particle_m=100e-6,
        rho_particle_kg_m3=1100.0,
        rho_fluid_kg_m3=1.2,
        mu_fluid_pa_s=1.8e-5,
        height_setting_m=1.0,
        horizontal_velocity_ms=0.1,
        separator_type="FIBER",
    )
    fiber = calc_gravity_separator(fiber_input)
    assert math.isclose(
        fiber.chamber_length_m, plain.chamber_length_m * 0.3, rel_tol=0.01
    )


# ============================================================================
# 4. 边界异常
# ============================================================================


def test_zero_diameter_raises():
    """d_particle_m=0 无物理意义 → 422。"""
    from app.services.exceptions import PcsError

    with pytest.raises(PcsError) as exc_info:
        calc_gravity_separator(GravitySeparatorInput(
            d_particle_m=0.0,
            rho_particle_kg_m3=1100.0,
            rho_fluid_kg_m3=1.2,
            mu_fluid_pa_s=1.8e-5,
            height_setting_m=1.0,
            horizontal_velocity_ms=0.1,
            separator_type="PLAIN",
        ))
    assert exc_info.value.status == 422


def test_particle_less_dense_than_fluid_raises():
    """ρ_p < ρ_f 颗粒浮力（不上浮 = 不沉降）→ 422。"""
    from app.services.exceptions import PcsError

    with pytest.raises(PcsError) as exc_info:
        calc_gravity_separator(GravitySeparatorInput(
            d_particle_m=100e-6,
            rho_particle_kg_m3=0.5,  # 比流体轻
            rho_fluid_kg_m3=1.2,
            mu_fluid_pa_s=1.8e-5,
            height_setting_m=1.0,
            horizontal_velocity_ms=0.1,
            separator_type="PLAIN",
        ))
    assert exc_info.value.status == 422


# ============================================================================
# 5. 不可变性 + 类型契约
# ============================================================================


def test_gravity_separator_result_is_frozen():
    """GravitySeparatorResult frozen dataclass。"""
    from dataclasses import FrozenInstanceError

    result = calc_gravity_separator(_stokes_input())
    assert isinstance(result, GravitySeparatorResult)
    with pytest.raises(FrozenInstanceError):
        result.settling_velocity_ms = 999.0  # type: ignore[misc]


def test_region_literal_values():
    """Region Literal 仅 3 类（防回归）。"""
    assert set(Region.__args__) == {"STOKES", "INTERMEDIATE", "NEWTON"}


def test_separator_type_literal_values():
    """SeparatorType Literal 3 类（PLAIN / VANE / FIBER）。"""
    assert set(SeparatorType.__args__) == {"PLAIN", "VANE", "FIBER"}