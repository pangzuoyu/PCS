"""P6-3 Task 33 FILTRATION ergun 测试（§3.2.7 第三项 — 深层过滤）。

按 SPEC §3.2.7 Ergun 方程：

    ΔP/L = 150 · μ · (1−ε)² / ε³ · v_s / dp² + 1.75 · ρ · (1−ε) / ε³ · v_s² / dp

手算独立校核（3 例，体现本模块 docstring）：

例 1（水+砂 v_s=1e-3/ε=0.4/dp=0.5e-3/μ=1e-3/ρ=1000/L=1）：

    laminar = 150 · 1e-3 · 0.36 / 0.064 · 1e-3 / 2.5e-7
            = 0.84375 · 1e-3 / 2.5e-7
            = 3375 Pa/m
    turbulent = 1.75 · 1000 · 0.6 / 0.064 · 1e-6 / 5e-4
              = 16406.25 · 1e-6 / 5e-4
              ≈ 32.8125 Pa/m
    ΔP_total ≈ 3407.8125 Pa（L=1）
    Re_p = 1000 · 1e-3 · 5e-4 / 1e-3 / 0.6 ≈ 0.8333

例 2（高流速 v_s=1.0，其余同例 1）：

    laminar ≈ 3.375e7 Pa/m
    turbulent ≈ 3.28125e7 Pa/m（v_s² 项主导）
    Re_p ≈ 833.3（接近上限 1000）

例 3（ε=0 或 ε=1）→ ErgunInputError

3 例手算与公式直接计算偏差 = 0%（公式自洽）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.filtration import (  # noqa: E402
    ErgunInput,
    ErgunInputError,
    calc_ergun_pressure_drop,
)

# ============================================================================
# 1. 例 1 手算校核（水+砂 → ΔP ≈ 3407.81 Pa，Re_p ≈ 0.8333）
# ============================================================================


def test_ergun_basic_water_sand() -> None:
    """v_s=1e-3/ε=0.4/dp=0.5e-3/μ=1e-3/ρ=1000/L=1 → ΔP ≈ 3407.81 Pa（手算）。

    手算：laminar = 3375 Pa/m；turbulent = 32.8125 Pa/m
        ΔP = (3375 + 32.8125) · 1 ≈ 3407.8125 Pa
    """
    r = calc_ergun_pressure_drop(
        ErgunInput(
            superficial_velocity=1e-3,
            bed_porosity=0.4,
            particle_diameter=0.5e-3,
            fluid_viscosity=1e-3,
            fluid_density=1000.0,
            bed_length=1.0,
        )
    )
    # ΔP / L ≈ 3407.8125 Pa/m
    assert r.pressure_drop_per_length == pytest.approx(3407.8125, rel=1e-3)
    # ΔP = ΔP / L · L = 3407.8125 Pa
    assert r.pressure_drop == pytest.approx(3407.8125, rel=1e-3)
    # laminar = 3375
    assert r.laminar_term == pytest.approx(3375.0, rel=1e-3)
    # turbulent = 32.8125
    assert r.turbulent_term == pytest.approx(32.8125, rel=1e-3)
    # Re_p = 1000 · 1e-3 · 5e-4 / 1e-3 / 0.6 ≈ 0.8333
    assert r.reynolds_particle == pytest.approx(0.8333, rel=1e-3)
    assert r.formula_ref == "ERGUN_§3.2.7"


# ============================================================================
# 2. 例 2 高流速 — 紊流主导（v_s=1.0）
# ============================================================================


def test_ergun_high_velocity_turbulent_dominant() -> None:
    """v_s=1.0（高流速）→ 紊流主导（v_s² 项）；Re_p ≈ 833.3 接近上限。

    手算：laminar ≈ 3.375e6；turbulent ≈ 3.28125e7（turbulent ≈ 9.72 × laminar）
        turbulent 主导（v_s² 项主导）✓
    """
    r = calc_ergun_pressure_drop(
        ErgunInput(
            superficial_velocity=1.0,
            bed_porosity=0.4,
            particle_diameter=0.5e-3,
            fluid_viscosity=1e-3,
            fluid_density=1000.0,
            bed_length=1.0,
        )
    )
    # turbulent 主导（v_s² 项主导）
    assert r.turbulent_term > r.laminar_term
    assert r.turbulent_term == pytest.approx(3.28125e7, rel=1e-3)
    # laminar
    assert r.laminar_term == pytest.approx(3.375e6, rel=1e-3)
    # Re_p ≈ 833.3
    assert r.reynolds_particle == pytest.approx(833.333, rel=1e-3)


# ============================================================================
# 3. 例 3 输入校验 — ε 边界（0 或 1）→ ErgunInputError
# ============================================================================


def test_ergun_porosity_edge_zero() -> None:
    """ε=0 → ErgunInputError（422）。"""
    with pytest.raises(ErgunInputError) as exc_info:
        calc_ergun_pressure_drop(
            ErgunInput(
                superficial_velocity=1e-3,
                bed_porosity=0.0,
                particle_diameter=0.5e-3,
                fluid_viscosity=1e-3,
                fluid_density=1000.0,
                bed_length=1.0,
            )
        )
    assert "bed_porosity" in str(exc_info.value)


def test_ergun_porosity_edge_one() -> None:
    """ε=1 → ErgunInputError（422）。"""
    with pytest.raises(ErgunInputError) as exc_info:
        calc_ergun_pressure_drop(
            ErgunInput(
                superficial_velocity=1e-3,
                bed_porosity=1.0,
                particle_diameter=0.5e-3,
                fluid_viscosity=1e-3,
                fluid_density=1000.0,
                bed_length=1.0,
            )
        )
    assert "bed_porosity" in str(exc_info.value)


# ============================================================================
# 4. 颗粒雷诺数范围验证（3 例：低/中/高 Re_p 均 ∈ [0.001, 1000]）
# ============================================================================


def test_ergun_reynolds_range_low() -> None:
    """低 Re_p（v_s=1e-5）→ Re_p ≈ 0.00833 ∈ [0.001, 1000]。"""
    r = calc_ergun_pressure_drop(
        ErgunInput(
            superficial_velocity=1e-5,
            bed_porosity=0.4,
            particle_diameter=0.5e-3,
            fluid_viscosity=1e-3,
            fluid_density=1000.0,
            bed_length=1.0,
        )
    )
    assert 0.001 <= r.reynolds_particle <= 1000.0
    assert r.reynolds_particle == pytest.approx(8.333e-3, rel=1e-2)


def test_ergun_reynolds_range_mid() -> None:
    """中 Re_p（v_s=1e-3）→ Re_p ≈ 0.8333 ∈ [0.001, 1000]。"""
    r = calc_ergun_pressure_drop(
        ErgunInput(
            superficial_velocity=1e-3,
            bed_porosity=0.4,
            particle_diameter=0.5e-3,
            fluid_viscosity=1e-3,
            fluid_density=1000.0,
            bed_length=1.0,
        )
    )
    assert 0.001 <= r.reynolds_particle <= 1000.0


def test_ergun_reynolds_range_high() -> None:
    """高 Re_p（v_s=1.0）→ Re_p ≈ 833.3 ∈ [0.001, 1000]（接近上限）。"""
    r = calc_ergun_pressure_drop(
        ErgunInput(
            superficial_velocity=1.0,
            bed_porosity=0.4,
            particle_diameter=0.5e-3,
            fluid_viscosity=1e-3,
            fluid_density=1000.0,
            bed_length=1.0,
        )
    )
    assert 0.001 <= r.reynolds_particle <= 1000.0
    assert r.reynolds_particle == pytest.approx(833.333, rel=1e-3)


# ============================================================================
# 5. ΔP / L dimensional check（Pa/m）— 用 laminar + turbulent 之和验证
# ============================================================================


def test_ergun_dimensional_check_pa_per_m() -> None:
    """dimensional check：pressure_drop_per_length = laminar + turbulent（Pa/m 单位）。"""
    r = calc_ergun_pressure_drop(
        ErgunInput(
            superficial_velocity=1e-3,
            bed_porosity=0.4,
            particle_diameter=0.5e-3,
            fluid_viscosity=1e-3,
            fluid_density=1000.0,
            bed_length=1.0,
        )
    )
    # ΔP / L = laminar + turbulent（algebraic identity）
    assert r.pressure_drop_per_length == pytest.approx(
        r.laminar_term + r.turbulent_term, rel=1e-12
    )
    # ΔP = (ΔP / L) · L
    assert r.pressure_drop == pytest.approx(
        r.pressure_drop_per_length * 1.0, rel=1e-12
    )


def test_ergun_dimensional_check_longer_bed() -> None:
    """dimensional check：L=2 → ΔP 翻倍（线性缩放）。"""
    base_kwargs = dict(
        superficial_velocity=1e-3,
        bed_porosity=0.4,
        particle_diameter=0.5e-3,
        fluid_viscosity=1e-3,
        fluid_density=1000.0,
    )
    r1 = calc_ergun_pressure_drop(ErgunInput(**base_kwargs, bed_length=1.0))
    r2 = calc_ergun_pressure_drop(ErgunInput(**base_kwargs, bed_length=2.0))
    # ΔP 线性于 L
    assert r2.pressure_drop == pytest.approx(2.0 * r1.pressure_drop, rel=1e-12)
    # ΔP / L 不随 L 变
    assert r2.pressure_drop_per_length == pytest.approx(
        r1.pressure_drop_per_length, rel=1e-12
    )


# ============================================================================
# 6. 输入校验 — 其他负值
# ============================================================================


def test_ergun_input_error_negative_dp() -> None:
    """dp=-1 → ErgunInputError（422）。"""
    with pytest.raises(ErgunInputError) as exc_info:
        calc_ergun_pressure_drop(
            ErgunInput(
                superficial_velocity=1e-3,
                bed_porosity=0.4,
                particle_diameter=-1.0,
                fluid_viscosity=1e-3,
                fluid_density=1000.0,
                bed_length=1.0,
            )
        )
    assert "particle_diameter" in str(exc_info.value)


def test_ergun_input_error_negative_velocity() -> None:
    """v_s=-1 → ErgunInputError（422）。"""
    with pytest.raises(ErgunInputError) as exc_info:
        calc_ergun_pressure_drop(
            ErgunInput(
                superficial_velocity=-1.0,
                bed_porosity=0.4,
                particle_diameter=0.5e-3,
                fluid_viscosity=1e-3,
                fluid_density=1000.0,
                bed_length=1.0,
            )
        )
    assert "superficial_velocity" in str(exc_info.value)


# ============================================================================
# 7. formula_ref 字面常量统一
# ============================================================================


def test_ergun_formula_ref() -> None:
    """formula_ref 必须恒等于 "ERGUN_§3.2.7"（Task 33 红线 #12）。"""
    r = calc_ergun_pressure_drop(
        ErgunInput(
            superficial_velocity=1e-3,
            bed_porosity=0.4,
            particle_diameter=0.5e-3,
            fluid_viscosity=1e-3,
            fluid_density=1000.0,
            bed_length=1.0,
        )
    )
    assert r.formula_ref == "ERGUN_§3.2.7"