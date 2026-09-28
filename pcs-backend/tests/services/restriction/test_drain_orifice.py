"""P6-5 Task B3: C-19 RESTRICTION 排污孔板（drain orifice）+ Ftp 修正 + 临界流。

按 SPEC §3.6.2 + §3.7.2 V1.1：
- β 直径比 + Ftp = 1 - 0.0245·β^4.4（GB/T 308 排水孔板 Eq.2.2）
- 临界压比 r_c = (2/(γ+1))^(γ/(γ-1))（γ=1.4 默认）
- 阻塞流 v_max = √(2ΔP/ρ) 校验
- CONTINUOUS / INTERMITTENT 两种排污类型
- imperial 双单位（orifice_area_in2 / inlet_pressure_psia）

边界条件：
- β 严格 0 < β < 1
- d/P₁/P₂/ρ 必须 > 0；流量可 0
- Ftp 源 GB/T 308 经验式（Q-11 标 SYNTHETIC_TEST_DATA）
"""

from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.restriction import drain_orifice_service
from app.services.restriction.drain_orifice_service import (
    DrainOrificeInput,
    DrainOrificeInputError,
    calc_drain_orifice,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_drain_orifice.json"


# ============================================================================
# Step 1: 主测试 — 连续排污 β=0.4 + Ftp 修正
# ============================================================================


def test_drain_orifice_continuous_with_ftp_correction():
    """连续排污 β=0.4，Ftp ≈ 1 - 0.0245·β^4.4 ≈ 0.99997（GB 308 Eq.2.2）。

    工况：d=0.02m, β=0.4, P₁=500kPa, P₂=100kPa, ρ=999 kg/m³, m_dot=5 kg/s
        r_c = (2/(1.4+1))^(1.4/(1.4-1)) = (2/2.4)^3.5 ≈ 0.528
        P₂/P₁ = 100/500 = 0.2 ≤ 0.528 → 阻塞流
        Ftp = 1 - 0.0245 * 0.4^4.4 ≈ 1 - 0.0245 * 0.0337 ≈ 0.99917
    """
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
        imperial_units=False,
    )
    result = calc_drain_orifice(inp)
    expected_ftp = 1.0 - 0.0245 * (0.4**4.4)
    assert math.isclose(result.ftp_factor, expected_ftp, rel_tol=1e-3)


# ============================================================================
# Step 5: 间歇排污 + β 越界测试
# ============================================================================


def test_drain_orifice_intermittent_continuous_marker():
    """INTERMITTENT 与 CONTINUOUS 在 formula_ref 区分。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.5,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=400.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="INTERMITTENT",
    )
    result = calc_drain_orifice(inp)
    assert "INTERMITTENT" in result.formula_ref["drain_type"]


def test_drain_orifice_beta_out_of_range_raises():
    """β ≥ 1 应抛 DrainOrificeInputError。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=1.2,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    with pytest.raises(DrainOrificeInputError):
        calc_drain_orifice(inp)


# ============================================================================
# 阻塞流判断（r_c = 0.528 for γ=1.4）
# ============================================================================


def test_drain_orifice_critical_pressure_ratio():
    """γ=1.4 → r_c = (2/2.4)^3.5 ≈ 0.5283。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    result = calc_drain_orifice(inp)
    expected_r_c = (2.0 / 2.4) ** 3.5
    assert math.isclose(result.critical_pressure_ratio, expected_r_c, rel_tol=1e-9)
    # P₂/P₁ = 0.2 < r_c → 阻塞
    assert result.is_choked is True
    assert math.isclose(result.actual_pressure_ratio, 0.2, rel_tol=1e-9)


def test_drain_orifice_not_choked_high_backpressure():
    """P₂/P₁ > r_c → 非阻塞（容量无穷大）。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=400.0,  # P₂/P₁ = 0.8 > 0.528
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    result = calc_drain_orifice(inp)
    assert result.is_choked is False
    assert result.mass_flow_capacity_kg_s == float("inf")
    assert result.is_capacity_ok is True


def test_drain_orifice_choked_flow_capacity():
    """阻塞流时 v_max = √(2ΔP/ρ)；mass_max = A·Ftp·ρ·v_max。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,  # ΔP = 400 kPa = 400000 Pa
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    result = calc_drain_orifice(inp)
    a_orifice = math.pi * 0.02**2 / 4.0
    ftp = 1.0 - 0.0245 * 0.4**4.4
    v_max = math.sqrt(2.0 * 400000.0 / 999.0)
    expected_mass_max = a_orifice * ftp * 999.0 * v_max
    assert math.isclose(result.mass_flow_capacity_kg_s, expected_mass_max, rel_tol=1e-9)


# ============================================================================
# 极值校验（F5：d/P/ρ/m_dot 边界）
# ============================================================================


def test_drain_orifice_zero_diameter_raises():
    """F5：diameter_m ≤ 0 应抛 DrainOrificeInputError。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.0,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    with pytest.raises(DrainOrificeInputError):
        calc_drain_orifice(inp)


def test_drain_orifice_zero_density_raises():
    """F5：density ≤ 0 应抛 DrainOrificeInputError。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=0.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    with pytest.raises(DrainOrificeInputError):
        calc_drain_orifice(inp)


def test_drain_orifice_negative_flow_raises():
    """F5：mass_flow_kg_s < 0 应抛 DrainOrificeInputError。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=-1.0,
        drain_type="CONTINUOUS",
    )
    with pytest.raises(DrainOrificeInputError):
        calc_drain_orifice(inp)


def test_drain_orifice_zero_beta_raises():
    """F2：β ≤ 0 应抛 DrainOrificeInputError。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.0,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    with pytest.raises(DrainOrificeInputError):
        calc_drain_orifice(inp)


# ============================================================================
# Imperial 双单位输出（F1）
# ============================================================================


def test_drain_orifice_imperial_units_output():
    """imperial_units=True 时应输出 orifice_area_in2 / inlet_pressure_psia。

    1 m² = 1550.0031 in²；1 kPa = 0.1450377 psia
    """
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
        imperial_units=True,
    )
    result = calc_drain_orifice(inp)
    assert result.imperial_conversion is not None
    assert "orifice_area_in2" in result.imperial_conversion
    assert "inlet_pressure_psia" in result.imperial_conversion
    a_m2 = math.pi * 0.02**2 / 4.0
    expected_in2 = a_m2 / (0.0254**2)
    assert math.isclose(
        result.imperial_conversion["orifice_area_in2"],
        expected_in2,
        rel_tol=1e-6,
    )
    expected_psia = 500.0 * 0.1450377
    assert math.isclose(
        result.imperial_conversion["inlet_pressure_psia"],
        expected_psia,
        rel_tol=1e-6,
    )


def test_drain_orifice_si_units_no_imperial_conversion():
    """imperial_units=False（默认）时 imperial_conversion 应为 None。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    result = calc_drain_orifice(inp)
    assert result.imperial_conversion is None


# ============================================================================
# Frozen dataclass + formula_ref + PcsError（批次一致性）
# ============================================================================


def test_drain_orifice_result_is_frozen():
    """DrainOrificeResult 必须是 frozen（不可变）。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    result = calc_drain_orifice(inp)
    with pytest.raises(FrozenInstanceError):
        result.ftp_factor = 999.0  # type: ignore[misc]


def test_drain_orifice_input_is_frozen():
    """DrainOrificeInput 必须是 frozen（不可变）。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    with pytest.raises(FrozenInstanceError):
        inp.beta_ratio = 0.99  # type: ignore[misc]


def test_drain_orifice_formula_ref_present():
    """result.formula_ref 必须含 Ftp 修正 + 临界压比 + 排污类型溯源。"""
    inp = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    result = calc_drain_orifice(inp)
    assert "ftp_correction" in result.formula_ref
    assert "SYNTHETIC_TEST_DATA" in result.formula_ref["ftp_correction"]
    assert "critical_pressure_ratio" in result.formula_ref
    assert "drain_type" in result.formula_ref


def test_drain_orifice_error_inherits_pcs_error():
    """DrainOrificeInputError 必须继承 PcsError 且含 code/status。"""
    err = DrainOrificeInputError("test")
    assert err.code == "DRAIN_ORIFICE_INPUT_ERROR"
    assert err.status == 422
    assert hasattr(err, "details")


# ============================================================================
# Module surface 完整性
# ============================================================================


def test_drain_orifice_module_exports():
    """模块 __all__ 必须包含核心 4 个公开符号。"""
    assert "calc_drain_orifice" in drain_orifice_service.__all__
    assert "DrainOrificeInput" in drain_orifice_service.__all__
    assert "DrainOrificeResult" in drain_orifice_service.__all__
    assert "DrainOrificeInputError" in drain_orifice_service.__all__


# ============================================================================
# Golden fixture 测试
# ============================================================================


def test_golden_drain_orifice_fixture_present():
    """黄金算例 fixture 文件存在且可加载。"""
    if not FIXTURE_PATH.exists():
        pytest.skip("golden_drain_orifice.json fixture 未创建（占位）")
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert "cases" in data
    assert len(data["cases"]) >= 1


def test_golden_fixture_matches_implementation():
    """Future-drift detector: golden fixture Ftp values must match Ftp = 1 - 0.0245*beta^4.4."""
    if not FIXTURE_PATH.exists():
        pytest.skip("golden_drain_orifice.json fixture 未创建（占位）")
    cases = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["cases"]
    for case in cases:
        beta = case["input"]["beta_ratio"]
        expected = case["expected"]["ftp_factor"]
        actual = 1.0 - 0.0245 * beta**4.4
        assert math.isclose(actual, expected, rel_tol=1e-6, abs_tol=1e-9), (
            f"Fixture drift: case={case['id']}, beta={beta}, "
            f"expected={expected}, actual={actual}"
        )


# ============================================================================
# P6-6B T13 feature flag 集成（OPEN-P6-6A-4 关闭）
# ============================================================================


@pytest.mark.unit
def test_resolved_cd_y_cr_override_applies_to_mass_flow_capacity():
    """P6-6B T13：`_resolved_cd_y_cr` override 真正生效（NATURAL_GAS XLS convention）。

    当 `_resolved_cd_y_cr=(0.83932, 0.687)` 提供时，m_max 应乘以
    Cd × Y_cr^0.5 = 0.83932 × sqrt(0.687)；back-compat（None）保持 Cd=1.0。
    """
    inp_default = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    inp_resolved = DrainOrificeInput(
        orifice_diameter_m=0.02,
        beta_ratio=0.4,
        inlet_pressure_kpa=500.0,
        outlet_pressure_kpa=100.0,
        fluid_density_kg_m3=999.0,
        mass_flow_kg_s=5.0,
        drain_type="CONTINUOUS",
    )
    result_default = calc_drain_orifice(inp_default)
    result_resolved = calc_drain_orifice(
        inp_resolved, _resolved_cd_y_cr=(0.83932, 0.687),
    )
    expected_factor = 0.83932 * math.sqrt(0.687)
    assert math.isclose(
        result_resolved.mass_flow_capacity_kg_s,
        result_default.mass_flow_capacity_kg_s * expected_factor,
        rel_tol=1e-9,
    )
