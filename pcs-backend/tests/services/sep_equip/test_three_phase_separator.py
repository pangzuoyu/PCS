"""P6-5 Task B2: C-10 VESSEL 三相分离器（油水气 + 堰板 + 油水界面 + 停留时间）。

按 SPEC §3.4.3 V1.5 + GPSA §4.4：
- 三相体积流量（油/水/气各自 m³/d）
- 堰板高度 H_w（控制油水界面）
- 油水界面位置 H_ow = H·(ρ_w - ρ_oil)/(ρ_w - ρ_g)（SPEC §3.4.3 Eq.1 反推 H_total）
- 停留时间：液 ≥ 5 min, 气 ≥ 10 s
- 调用 C-12 calc_partial_volume（D7 接口冻结）

边界条件：
- weir_height 严格 0 < H_w < D
- 极值校验：diameter/length/flow > 0；密度 > 0
- 体积/停留时间计算经由 C-12 calc_partial_volume
"""
from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.sep_equip import three_phase_separator_service
from app.services.sep_equip.three_phase_separator_service import (
    ThreePhaseSeparatorError,
    ThreePhaseSeparatorInput,
    calc_three_phase_separator,
)

FIXTURE_PATH = (
    Path(__file__).parent / "fixtures" / "golden_three_phase.json"
)


# ============================================================================
# 油水界面 + 堰板高度 主测试（SPEC §3.4.3 Eq.1）
# ============================================================================


def test_three_phase_separator_oil_water_interface():
    """油水界面位置：H_total = H_ow · (ρ_w - ρ_g) / (ρ_w - ρ_oil)。

    工况：HORIZONTAL D=2.0m, L=6.0m, 2:1_ELLIPTICAL
        oil=5000 kg/d @ 800 kg/m³ → 6.25 m³/d
        water=2000 kg/d @ 1000 kg/m³ → 2.0 m³/d
        gas=10000 kg/d @ 50 kg/m³ → 200 m³/d
        weir=0.5m, target H_ow=0.4m
        H_total = 0.4 * (1000 - 50) / (1000 - 800) = 0.4 * 950/200 = 1.9 m
        应可算（< 容器总高 h_max=D=2m for HORIZONTAL）
    """
    inp = ThreePhaseSeparatorInput(
        vessel_shape="HORIZONTAL",
        diameter_m=2.0,
        length_m=6.0,
        head_type="2:1_ELLIPTICAL",
        oil_mass_rate_kg_d=5000.0,
        water_mass_rate_kg_d=2000.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.4,
    )
    result = calc_three_phase_separator(inp)
    assert abs(result.oil_water_interface_m - 0.4) < 0.1
    assert result.weir_height_required_m == pytest.approx(0.5, rel=1e-9)
    assert result.total_volume_m3 > 0.0


# ============================================================================
# 停留时间不达标（极端高流量）→ is_residence_time_ok=False
# ============================================================================


def test_three_phase_separator_residence_time_violation():
    """极端高流量 → 停留时间 < 5 min → is_residence_time_ok=False。

    工况：HORIZONTAL D=1.0m, L=1.0m, FLAT 封头
        h_max = D = 1.0m
        target H_ow=0.1m → H_total = 0.1*(1000-50)/(1000-800) = 0.475m < 1.0m ok
        V_partial (HORIZONTAL D=1, L=1, H=0.475) ≈ 0.366 m³
        Q_liquid = 100000/800 + 50000/1000 = 175 m³/d
        t_r_liq = 0.366/175·1440 ≈ 3.0 min < 5 min → 触发越界
    """
    inp = ThreePhaseSeparatorInput(
        vessel_shape="HORIZONTAL",
        diameter_m=1.0,
        length_m=1.0,
        head_type="FLAT",
        oil_mass_rate_kg_d=100000.0,
        water_mass_rate_kg_d=50000.0,
        gas_mass_rate_kg_d=200000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.3,
        oil_water_interface_target_m=0.1,
    )
    result = calc_three_phase_separator(inp)
    assert result.is_residence_time_ok is False
    assert result.liquid_residence_time_min < 5.0


def test_three_phase_separator_residence_time_ok_low_flow():
    """低流量 → 停留时间 ≥ 5 min → is_residence_time_ok=True。

    工况：HORIZONTAL D=3.0m, L=10.0m, 2:1_ELLIPTICAL
        V_total = π·3²/4·10 + 2·(π/12·0.75²·3) ≈ 70.69 + 1.77 ≈ 72.46 m³
        oil=100, water=50, gas=200 kg/d
        Q_liquid = 100/800 + 50/1000 = 0.175 m³/d → t_r_liq = 72.46/0.175·1440 ≈ huge
    """
    inp = ThreePhaseSeparatorInput(
        vessel_shape="HORIZONTAL",
        diameter_m=3.0,
        length_m=10.0,
        head_type="2:1_ELLIPTICAL",
        oil_mass_rate_kg_d=100.0,
        water_mass_rate_kg_d=50.0,
        gas_mass_rate_kg_d=200.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.4,
    )
    result = calc_three_phase_separator(inp)
    assert result.is_residence_time_ok is True
    assert result.liquid_residence_time_min >= 5.0
    assert result.gas_residence_time_s >= 10.0


# ============================================================================
# weir_height 越界 + 极值校验（F2 + F5）
# ============================================================================


def test_three_phase_separator_weir_height_out_of_range_raises():
    """weir_height ≥ D 应抛 ThreePhaseSeparatorError（0 < H_w < D 严格）。"""
    inp = ThreePhaseSeparatorInput(
        vessel_shape="VERTICAL",
        diameter_m=1.0,
        length_m=2.0,
        head_type="FLAT",
        oil_mass_rate_kg_d=100.0,
        water_mass_rate_kg_d=50.0,
        gas_mass_rate_kg_d=200.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=1.5,  # > D=1.0 越界
        oil_water_interface_target_m=0.5,
    )
    with pytest.raises(ThreePhaseSeparatorError):
        calc_three_phase_separator(inp)


def test_three_phase_separator_weir_height_zero_raises():
    """weir_height = 0 应抛 ThreePhaseSeparatorError（严格 > 0）。"""
    inp = ThreePhaseSeparatorInput(
        vessel_shape="VERTICAL",
        diameter_m=1.0,
        length_m=2.0,
        head_type="FLAT",
        oil_mass_rate_kg_d=100.0,
        water_mass_rate_kg_d=50.0,
        gas_mass_rate_kg_d=200.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.0,  # 不允许 0
        oil_water_interface_target_m=0.5,
    )
    with pytest.raises(ThreePhaseSeparatorError):
        calc_three_phase_separator(inp)


def test_three_phase_separator_negative_diameter_raises():
    """F5：diameter_m ≤ 0 应抛 ThreePhaseSeparatorError。"""
    inp = ThreePhaseSeparatorInput(
        vessel_shape="VERTICAL",
        diameter_m=-1.0,  # 越界
        length_m=2.0,
        head_type="FLAT",
        oil_mass_rate_kg_d=100.0,
        water_mass_rate_kg_d=50.0,
        gas_mass_rate_kg_d=200.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.3,
    )
    with pytest.raises(ThreePhaseSeparatorError):
        calc_three_phase_separator(inp)


def test_three_phase_separator_negative_density_raises():
    """F5：oil/water/gas 密度 ≤ 0 应抛 ThreePhaseSeparatorError。"""
    inp = ThreePhaseSeparatorInput(
        vessel_shape="VERTICAL",
        diameter_m=1.0,
        length_m=2.0,
        head_type="FLAT",
        oil_mass_rate_kg_d=100.0,
        water_mass_rate_kg_d=50.0,
        gas_mass_rate_kg_d=200.0,
        oil_density_kg_m3=0.0,  # 越界
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.3,
    )
    with pytest.raises(ThreePhaseSeparatorError):
        calc_three_phase_separator(inp)


# ============================================================================
# 体积流量计算（油/水/气 m³/d）
# ============================================================================


def test_three_phase_separator_volumetric_flows():
    """体积流量 = 质量流量 / 密度（油/水/气 各 m³/d）。

    工况：oil=5000@800 → 6.25 m³/d；water=2000@1000 → 2.0 m³/d；gas=10000@50 → 200 m³/d。
    """
    inp = ThreePhaseSeparatorInput(
        vessel_shape="HORIZONTAL",
        diameter_m=2.0,
        length_m=6.0,
        head_type="2:1_ELLIPTICAL",
        oil_mass_rate_kg_d=5000.0,
        water_mass_rate_kg_d=2000.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.4,
    )
    result = calc_three_phase_separator(inp)
    assert math.isclose(result.oil_vol_rate_m3_d, 6.25, rel_tol=1e-9)
    assert math.isclose(result.water_vol_rate_m3_d, 2.0, rel_tol=1e-9)
    assert math.isclose(result.gas_vol_rate_m3_d, 200.0, rel_tol=1e-9)


# ============================================================================
# Imperial 双单位输出（F1）
# ============================================================================


def test_three_phase_separator_imperial_units_output():
    """imperial_units=True 时应输出 ft³/d 双单位（油/水/气）。

    1 m³ = 35.3147 ft³
    """
    inp = ThreePhaseSeparatorInput(
        vessel_shape="HORIZONTAL",
        diameter_m=2.0,
        length_m=6.0,
        head_type="2:1_ELLIPTICAL",
        oil_mass_rate_kg_d=5000.0,
        water_mass_rate_kg_d=2000.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.4,
        imperial_units=True,
    )
    result = calc_three_phase_separator(inp)
    assert result.imperial_conversion is not None
    assert "oil_vol_rate_ft3_d" in result.imperial_conversion
    assert "water_vol_rate_ft3_d" in result.imperial_conversion
    assert "gas_vol_rate_ft3_d" in result.imperial_conversion
    _M3_TO_FT3 = 35.3147
    assert math.isclose(
        result.imperial_conversion["oil_vol_rate_ft3_d"],
        result.oil_vol_rate_m3_d * _M3_TO_FT3,
        rel_tol=1e-6,
    )


def test_three_phase_separator_si_units_no_imperial_conversion():
    """imperial_units=False（默认）时 imperial_conversion 应为 None。"""
    inp = ThreePhaseSeparatorInput(
        vessel_shape="HORIZONTAL",
        diameter_m=2.0,
        length_m=6.0,
        head_type="2:1_ELLIPTICAL",
        oil_mass_rate_kg_d=5000.0,
        water_mass_rate_kg_d=2000.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.4,
    )
    result = calc_three_phase_separator(inp)
    assert result.imperial_conversion is None


# ============================================================================
# Frozen dataclass + formula_ref + PcsError（批次一致性）
# ============================================================================


def test_three_phase_separator_result_is_frozen():
    """ThreePhaseSeparatorResult 必须是 frozen（不可变）。"""
    inp = ThreePhaseSeparatorInput(
        vessel_shape="HORIZONTAL",
        diameter_m=2.0,
        length_m=6.0,
        head_type="2:1_ELLIPTICAL",
        oil_mass_rate_kg_d=5000.0,
        water_mass_rate_kg_d=2000.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.4,
    )
    result = calc_three_phase_separator(inp)
    with pytest.raises(FrozenInstanceError):
        result.oil_water_interface_m = 999.0  # type: ignore[misc]


def test_three_phase_separator_input_is_frozen():
    """ThreePhaseSeparatorInput 必须是 frozen（不可变）。"""
    inp = ThreePhaseSeparatorInput(
        vessel_shape="HORIZONTAL",
        diameter_m=2.0,
        length_m=6.0,
        head_type="2:1_ELLIPTICAL",
        oil_mass_rate_kg_d=5000.0,
        water_mass_rate_kg_d=2000.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.4,
    )
    with pytest.raises(FrozenInstanceError):
        inp.diameter_m = 10.0  # type: ignore[misc]


def test_three_phase_separator_formula_ref_present():
    """result.formula_ref 必须含公式溯源键。"""
    inp = ThreePhaseSeparatorInput(
        vessel_shape="HORIZONTAL",
        diameter_m=2.0,
        length_m=6.0,
        head_type="2:1_ELLIPTICAL",
        oil_mass_rate_kg_d=5000.0,
        water_mass_rate_kg_d=2000.0,
        gas_mass_rate_kg_d=10000.0,
        oil_density_kg_m3=800.0,
        water_density_kg_m3=1000.0,
        gas_density_kg_m3=50.0,
        weir_height_m=0.5,
        oil_water_interface_target_m=0.4,
    )
    result = calc_three_phase_separator(inp)
    assert "oil_water_interface" in result.formula_ref
    assert "residence_time" in result.formula_ref
    assert "vessel_partial_volume" in result.formula_ref


def test_three_phase_separator_error_inherits_pcs_error():
    """ThreePhaseSeparatorError 必须继承 PcsError 且含 code/status。"""
    err = ThreePhaseSeparatorError("test")
    assert err.code == "THREE_PHASE_SEPARATOR_INPUT_ERROR"
    assert err.status == 422
    assert hasattr(err, "details")


# ============================================================================
# Module surface 完整性
# ============================================================================


def test_three_phase_separator_module_exports():
    """模块 __all__ 必须包含核心 4 个公开符号。"""
    assert "calc_three_phase_separator" in three_phase_separator_service.__all__
    assert "ThreePhaseSeparatorInput" in three_phase_separator_service.__all__
    assert "ThreePhaseSeparatorResult" in three_phase_separator_service.__all__
    assert "ThreePhaseSeparatorError" in three_phase_separator_service.__all__


# ============================================================================
# Golden fixture 测试（如有）
# ============================================================================


def test_golden_three_phase_fixture_present():
    """黄金算例 fixture 文件存在且可加载。"""
    if not FIXTURE_PATH.exists():
        pytest.skip("golden_three_phase.json fixture 未创建（占位）")
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert "cases" in data
    assert len(data["cases"]) >= 1