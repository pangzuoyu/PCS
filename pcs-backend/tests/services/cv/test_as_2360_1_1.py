"""P6-5 Task B1: AS 2360.1.1 节流装置 Limit 校核（SPEC §3.6.1 + §3.7.1 V1.1）。

边界条件：
  - d < 1in (25.4mm) 触发 Limit 校核（warning_message）
  - 单相无闪蒸假设
  - 声速理想气体（γ 在 1.2~1.4 范围）
  - SI/Imperial 双单位验收

公式（理想气体）：
  - 声速 a = √(γ·P₁/ρ)
  - 临界压比 r_c = (2/(γ+1))^(γ/(γ-1))
  - 阻塞流判定：P₂/P₁ ≤ r_c → is_choked=True

参考标准：AS 2360.1.1-1993 (R2016) §4.2.3 Limit Factor。
"""
from __future__ import annotations

import math
from dataclasses import FrozenInstanceError

import pytest

from app.services.cv import as_2360_1_1_service
from app.services.cv.as_2360_1_1_service import (
    As2360InputError,
    As2360LimitInput,
    calc_as_2360_1_1_limit,
)

# ============================================================================
# d<1in Limit 触发测试（SPEC §3.7.1 V1.1）
# ============================================================================


def test_as_2360_d_less_than_1in_triggers_limit():
    """d<1in（25.4mm）触发 AS 2360.1.1 Limit 检查 + 警告。

    工况：orifice_d=20mm < 25.4mm（1in），应触发 Limit warning。
    """
    inp = As2360LimitInput(
        orifice_diameter_m=0.02,  # 20mm < 25.4mm
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=999.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
        imperial_units=False,
    )
    result = calc_as_2360_1_1_limit(inp)
    assert result.is_limit_applicable is True, "d<1in 必须触发 Limit"
    assert result.warning_message is not None
    assert "d<1in" in result.warning_message or "Limit" in result.warning_message


def test_as_2360_d_exactly_1in_does_not_trigger_limit():
    """d=1in exactly should NOT trigger limit（strict < 边界）。

    工况：orifice_d=25.4mm（恰好 1in），不触发 Limit warning。
    """
    inp = As2360LimitInput(
        orifice_diameter_m=0.0254,  # exactly 1in
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    result = calc_as_2360_1_1_limit(inp)
    assert result.is_limit_applicable is False, "d=1in 恰好等于阈值，不触发 Limit"
    assert result.warning_message is None
    assert math.isclose(result.orifice_diameter_in, 1.0, rel_tol=1e-9)


def test_as_2360_d_above_1in_does_not_trigger_limit():
    """d>1in 应不触发 Limit（标准管径工况）。

    工况：orifice_d=50mm（≈1.97in），不触发 Limit。
    """
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    result = calc_as_2360_1_1_limit(inp)
    assert result.is_limit_applicable is False
    assert result.warning_message is None
    assert math.isclose(result.orifice_diameter_in, 50.0 / 25.4, rel_tol=1e-9)


# ============================================================================
# 阻塞流 + γ 越界测试（理想气体声速）
# ============================================================================


def test_as_2360_choked_flow_critical_pressure_ratio():
    """γ=1.4 时 r_c ≈ 0.528；P₂/P₁ ≤ 0.528 触发阻塞。

    工况：P₁=1000 kPa, P₂=500 kPa → p_ratio=0.5 < r_c=0.528 → is_choked=True。
    """
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,  # p_ratio = 0.5 < r_c
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    result = calc_as_2360_1_1_limit(inp)
    expected_r_c = (2.0 / 2.4) ** (1.4 / 0.4)
    assert math.isclose(result.critical_pressure_ratio, expected_r_c, rel_tol=1e-3)
    assert result.is_choked is True, "p_ratio=0.5 < r_c=0.528 应判定阻塞"


def test_as_2360_non_choked_flow():
    """p_ratio > r_c 时不应判定阻塞。

    工况：P₁=1000 kPa, P₂=800 kPa → p_ratio=0.8 > r_c=0.528 → is_choked=False。
    """
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=800.0,  # p_ratio = 0.8 > r_c
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    result = calc_as_2360_1_1_limit(inp)
    assert result.is_choked is False, "p_ratio=0.8 > r_c=0.528 不应阻塞"
    assert math.isclose(result.actual_pressure_ratio, 0.8, rel_tol=1e-9)


def test_as_2360_sonic_velocity_ideal_gas():
    """理想气体声速 a = √(γ·P₁/ρ)。

    工况：γ=1.4, P₁=1000 kPa = 1e6 Pa, ρ=10 kg/m³
        a = √(1.4 × 1e6 / 10) = √(1.4e5) ≈ 374.166 m/s
    """
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    result = calc_as_2360_1_1_limit(inp)
    expected_a = math.sqrt(1.4 * 1.0e6 / 10.0)
    assert math.isclose(result.sonic_velocity_m_s, expected_a, rel_tol=1e-6)


# ============================================================================
# γ 越界 + 极值校验（F2 + F5）
# ============================================================================


def test_as_2360_invalid_gamma_low_raises():
    """γ 越界（<1.05）应抛 As2360InputError。

    物理边界：γ=1.0（单原子气体最小值）；γ<1.05 视为非物理输入。
    """
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=0.9,  # < 1.05 越界
        mass_flow_kg_s=10.0,
    )
    with pytest.raises(As2360InputError):
        calc_as_2360_1_1_limit(inp)


def test_as_2360_invalid_gamma_high_raises():
    """γ 越界（>1.67）应抛 As2360InputError。

    物理边界：γ=1.67（单原子气体理论最大值）。
    """
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=2.0,  # > 1.67 越界
        mass_flow_kg_s=10.0,
    )
    with pytest.raises(As2360InputError):
        calc_as_2360_1_1_limit(inp)


def test_as_2360_non_positive_orifice_raises():
    """F5：非正 orifice_diameter_m 应抛 As2360InputError。"""
    inp = As2360LimitInput(
        orifice_diameter_m=0.0,  # 越界
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    with pytest.raises(As2360InputError):
        calc_as_2360_1_1_limit(inp)


def test_as_2360_non_positive_pressure_raises():
    """F5：非正 inlet_pressure_kpa 应抛 As2360InputError。"""
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=0.0,  # 越界
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    with pytest.raises(As2360InputError):
        calc_as_2360_1_1_limit(inp)


def test_as_2360_non_positive_density_raises():
    """F5：非正 fluid_density_kg_m3 应抛 As2360InputError。"""
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=-1.0,  # 越界
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    with pytest.raises(As2360InputError):
        calc_as_2360_1_1_limit(inp)


# ============================================================================
# Imperial 双单位输出（F1）
# ============================================================================


def test_as_2360_imperial_units_output():
    """imperial_units=True 时应输出 ft/s + psia 双单位。

    工况：γ=1.4, P₁=1000 kPa, ρ=10 kg/m³
        sonic_velocity_ft_s = sonic_velocity_m_s / 0.3048
        inlet_pressure_psia = inlet_pressure_kpa * 0.1450377
    """
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
        imperial_units=True,
    )
    result = calc_as_2360_1_1_limit(inp)
    assert result.imperial_conversion is not None
    assert "sonic_velocity_ft_s" in result.imperial_conversion
    assert "inlet_pressure_psia" in result.imperial_conversion
    expected_ft_s = result.sonic_velocity_m_s / 0.3048
    expected_psia = 1000.0 * 0.1450377
    assert math.isclose(
        result.imperial_conversion["sonic_velocity_ft_s"], expected_ft_s, rel_tol=1e-9
    )
    assert math.isclose(
        result.imperial_conversion["inlet_pressure_psia"], expected_psia, rel_tol=1e-9
    )


def test_as_2360_si_units_no_imperial_conversion():
    """imperial_units=False（默认）时 imperial_conversion 应为 None。"""
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    result = calc_as_2360_1_1_limit(inp)
    assert result.imperial_conversion is None


# ============================================================================
# Frozen dataclass + formula_ref（批次一致性）
# ============================================================================


def test_as_2360_result_is_frozen():
    """As2360LimitResult 必须是 frozen（不可变）。"""
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    result = calc_as_2360_1_1_limit(inp)
    with pytest.raises(FrozenInstanceError):
        result.sonic_velocity_m_s = 999.0  # type: ignore[misc]


def test_as_2360_input_is_frozen():
    """As2360LimitInput 必须是 frozen（不可变）。"""
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    with pytest.raises(FrozenInstanceError):
        inp.orifice_diameter_m = 0.10  # type: ignore[misc]


def test_as_2360_formula_ref_present():
    """result.formula_ref 必须含公式溯源键。"""
    inp = As2360LimitInput(
        orifice_diameter_m=0.05,
        inlet_pressure_kpa=1000.0,
        outlet_pressure_kpa=500.0,
        fluid_density_kg_m3=10.0,
        gas_specific_heat_ratio=1.4,
        mass_flow_kg_s=10.0,
    )
    result = calc_as_2360_1_1_limit(inp)
    assert "sonic_velocity" in result.formula_ref
    assert "critical_pressure_ratio" in result.formula_ref
    assert "limit_threshold" in result.formula_ref
    assert "as_standard" in result.formula_ref


# ============================================================================
# Module surface 完整性
# ============================================================================


def test_as_2360_module_exports():
    """模块 __all__ 必须包含核心 4 个公开符号。"""
    assert "calc_as_2360_1_1_limit" in as_2360_1_1_service.__all__
    assert "As2360LimitInput" in as_2360_1_1_service.__all__
    assert "As2360LimitResult" in as_2360_1_1_service.__all__
    assert "As2360InputError" in as_2360_1_1_service.__all__