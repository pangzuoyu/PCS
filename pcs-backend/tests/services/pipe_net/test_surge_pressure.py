"""P6-5+C-13 PIPE_NET 浪涌压力（水锤 + 段塞）单元测试。

覆盖：
1. 瞬时关阀 Joukowsky ΔP = ρ·a·ΔV（a = √(K/ρ)，Step 1 RED→GREEN）
2. 缓慢关阀 t_c ≥ 2L/a → is_joukowsky_applicable=False（Step 5）
3. imperial_units=True → surge_pressure_psi 对账（Step 5）
4. 边界：管径 ≤ 0 → SurgePressureInputError
5. 边界：流速 ≤ 0 → SurgePressureInputError
6. 边界：负值 ρ/K/t_c/wall_thickness → SurgePressureInputError
7. 含管壁修正：壁厚 > 0 → a < a_fluid（Wylie & Streeter 1993）

公式溯源：
- 纯流体声速 a_f = √(K/ρ)
- 管壁修正 a = a_f / √(1 + (K·D)/(E·e)·C₁)（Wylie & Streeter 1993）
- Joukowsky 1898：瞬时关阀 ΔP = ρ·a·ΔV
- 临界关阀 t_c_critical = 2L/a
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.services.pipe_net.surge_pressure import (
    SurgePressureInput,
    SurgePressureInputError,
    calc_water_hammer_surge,
)

# ---------------------------------------------------------------------------
# Golden fixture（参考数据）
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_surge_water_hammer.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1) Joukowsky 瞬时关阀（Step 1 RED→GREEN）
# ---------------------------------------------------------------------------


def test_water_hammer_joukowsky_sudden_valve_closure():
    """瞬时关阀水锤 ΔP = ρ·a·ΔV（a = √(K/ρ)）。

    水 ρ=999, K=2.2e9 Pa → a = √(2.2e9/999) ≈ 1483 m/s
    ΔV = 2.0 m/s → ΔP = 999·1483·2.0 ≈ 2.96e6 Pa ≈ 2.96 MPa
    """
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
        imperial_units=False,
    )
    result = calc_water_hammer_surge(inp)
    expected_a = math.sqrt(2.2e9 / 999.0)
    expected_dp = 999.0 * expected_a * 2.0
    assert math.isclose(result.wave_speed_m_s, expected_a, rel_tol=1e-3)
    assert math.isclose(result.surge_pressure_pa, expected_dp, rel_tol=1e-3)


# ---------------------------------------------------------------------------
# 2) 缓慢关阀 MOC 边界（Step 5：t_c > 2L/a）
# ---------------------------------------------------------------------------


def test_water_hammer_slow_closure_no_joukowsky():
    """t_c > 2L/a 时缓慢关阀不触发完整水锤。

    a ≈ 1483 m/s，L=1000m → t_c_critical ≈ 1.348s；t_c=10s > 临界。
    """
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=10.0,
        pipe_length_m=1000.0,
    )
    result = calc_water_hammer_surge(inp)
    assert result.is_joukowsky_applicable is False
    expected_t_c = 2.0 * 1000.0 / math.sqrt(2.2e9 / 999.0)
    assert math.isclose(result.critical_close_time_s, expected_t_c, rel_tol=1e-3)


# ---------------------------------------------------------------------------
# 3) Imperial 双单位对账（Step 5：F1）
# ---------------------------------------------------------------------------


def test_water_hammer_imperial_units():
    """imperial_units=True 时 ΔP 应正确转换为 psi（6894.76 Pa/psi）。"""
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
        imperial_units=True,
    )
    result = calc_water_hammer_surge(inp)
    assert result.imperial_conversion is not None
    expected_psi = result.surge_pressure_pa / 6894.76
    assert math.isclose(
        result.imperial_conversion["surge_pressure_psi"], expected_psi, rel_tol=1e-6
    )
    expected_ft_s = result.wave_speed_m_s / 0.3048
    assert math.isclose(
        result.imperial_conversion["wave_speed_ft_s"], expected_ft_s, rel_tol=1e-6
    )


# ---------------------------------------------------------------------------
# 4) 边界：管径 ≤ 0 → 拒绝（F2）
# ---------------------------------------------------------------------------


def test_surge_pressure_diameter_zero_raises():
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.0,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
    )
    with pytest.raises(SurgePressureInputError):
        calc_water_hammer_surge(inp)


def test_surge_pressure_diameter_negative_raises():
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=-0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
    )
    with pytest.raises(SurgePressureInputError):
        calc_water_hammer_surge(inp)


# ---------------------------------------------------------------------------
# 5) 边界：流速 ≤ 0 → 拒绝（F2）
# ---------------------------------------------------------------------------


def test_surge_pressure_velocity_zero_raises():
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=0.0,
        valve_close_time_s=0.0,
    )
    with pytest.raises(SurgePressureInputError):
        calc_water_hammer_surge(inp)


def test_surge_pressure_velocity_negative_raises():
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=-1.0,
        valve_close_time_s=0.0,
    )
    with pytest.raises(SurgePressureInputError):
        calc_water_hammer_surge(inp)


# ---------------------------------------------------------------------------
# 6) 边界：负值 ρ/K/t_c/wall_thickness → 拒绝（F5）
# ---------------------------------------------------------------------------


def test_surge_pressure_negative_density_raises():
    inp = SurgePressureInput(
        fluid_density_kg_m3=-1.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
    )
    with pytest.raises(SurgePressureInputError):
        calc_water_hammer_surge(inp)


def test_surge_pressure_negative_bulk_modulus_raises():
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=-1.0,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
    )
    with pytest.raises(SurgePressureInputError):
        calc_water_hammer_surge(inp)


def test_surge_pressure_negative_close_time_raises():
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=-1.0,
    )
    with pytest.raises(SurgePressureInputError):
        calc_water_hammer_surge(inp)


def test_surge_pressure_negative_wall_thickness_raises():
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
        wall_thickness_m=-0.005,
    )
    with pytest.raises(SurgePressureInputError):
        calc_water_hammer_surge(inp)


def test_surge_pressure_unknown_material_raises():
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
        wall_thickness_m=0.005,
        pipe_material="UNKNOWN_MATERIAL",
    )
    with pytest.raises(SurgePressureInputError):
        calc_water_hammer_surge(inp)


# ---------------------------------------------------------------------------
# 7) 管壁修正：壁厚 > 0 → a < a_fluid（Wylie & Streeter 1993；H-4 v2 fix）
# ---------------------------------------------------------------------------


def test_wave_speed_wall_correction_reduces_velocity():
    """壁厚 e=5mm + 碳钢 → a < 纯流体声速（管壁弹性修正生效）。

    K=2.2e9, ρ=999, D=0.1m, E=200e9, e=0.005, C₁=0.91
    correction = (K·D)/(E·e)·C₁ ≈ 2.002 → a ≈ a_f / √3.002 ≈ 856 m/s
    """
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
        wall_thickness_m=0.005,
        pipe_material="CARBON_STEEL",
    )
    result = calc_water_hammer_surge(inp)
    a_fluid = math.sqrt(2.2e9 / 999.0)
    # 修正项
    E = 200e9
    c1 = 0.91
    correction = (2.2e9 * 0.1) / (E * 0.005) * c1
    expected_a = a_fluid / math.sqrt(1.0 + correction)
    assert math.isclose(result.wave_speed_m_s, expected_a, rel_tol=1e-3)
    # 修正后声速严格小于纯流体声速
    assert result.wave_speed_m_s < a_fluid


def test_wave_speed_zero_wall_thickness_pure_fluid():
    """wall_thickness_m=0 → a == a_fluid（向后兼容，F3）。"""
    inp = SurgePressureInput(
        fluid_density_kg_m3=999.0,
        fluid_bulk_modulus_pa=2.2e9,
        pipe_diameter_m=0.1,
        flow_velocity_m_s=2.0,
        valve_close_time_s=0.0,
        wall_thickness_m=0.0,
    )
    result = calc_water_hammer_surge(inp)
    a_fluid = math.sqrt(2.2e9 / 999.0)
    assert math.isclose(result.wave_speed_m_s, a_fluid, rel_tol=1e-9)


# ---------------------------------------------------------------------------
# 8) Golden fixture 一致性（参考）
# ---------------------------------------------------------------------------


def test_golden_joukowsky_reference_matches():
    """Golden fixture 中 Joukowsky 参考值应等于实现输出。"""
    ref = GOLDEN["joukowsky_water_quick_closure"]
    inp = SurgePressureInput(
        fluid_density_kg_m3=ref["fluid_density_kg_m3"],
        fluid_bulk_modulus_pa=ref["fluid_bulk_modulus_pa"],
        pipe_diameter_m=ref["pipe_diameter_m"],
        flow_velocity_m_s=ref["flow_velocity_m_s"],
        valve_close_time_s=ref["valve_close_time_s"],
        imperial_units=False,
    )
    result = calc_water_hammer_surge(inp)
    assert math.isclose(
        result.surge_pressure_pa, ref["expected_surge_pressure_pa"], rel_tol=1e-3
    )
    assert math.isclose(result.wave_speed_m_s, ref["expected_wave_speed_m_s"], rel_tol=1e-3)
