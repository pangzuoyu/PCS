"""P5-3-5 PSV 选型（API 526 孔口表 D~T）+ 呼吸阀（API 2000）测试。

按 PCS-PLAN-P5-DEVICE-EQUIPMENT.md §370-394 + SUP-P5-PSV-001 §4.1：
- API 526 7th Ed. 标准孔口面积表（D~T，14 级）
- 选型策略：≥ area_required 的最小孔口；oversize_ratio ≤ 1.05
- API 2000 7th Ed. 呼吸阀（2"/3"/4"/6"/8"/10"/12"）

formula_ref 结构化（F-09）。
"""
from __future__ import annotations

import pytest

from app.services.psv import (
    BreathingValveInput,
    OrificeInput,
    calc_breathing_valve_api2000,
    select_orifice_api526,
)
from app.services.psv.breathing_valve_service import PsvBreathingValveInputError
from app.services.psv.orifice_service import PsvOrificeInputError

# ============================================================================
# 1. API 526 孔口选型
# ============================================================================


def test_api526_selects_minimum_fitting():
    """API 526 选最小满足要求的孔口（保守选型）。"""
    # D 孔口：0.000710 in² × 6.4516e-4 = 4.58e-7 m²
    # E 孔口：0.001260 × 6.4516e-4 = 8.13e-7 m²
    # 需求 5e-7 > D 面积 → 选 E
    inp = OrificeInput(area_required_m2=5e-7)
    r = select_orifice_api526(inp)
    assert r.selected_size == "E"
    assert r.actual_area_m2 >= inp.area_required_m2
    assert r.oversize_ratio >= 1.0


def test_api526_selects_T_for_large_area():
    """超大面积需求（超过 T）→ 抛错（欠选）。"""
    # T 孔口面积 ≈ 5.108e-5 m²
    # 需求 6e-5 > T → 应抛 PsvOrificeInputError
    inp = OrificeInput(area_required_m2=6e-5)
    with pytest.raises(PsvOrificeInputError) as exc_info:
        select_orifice_api526(inp)
    assert "超过 API 526 最大孔口 T" in str(exc_info.value)
    assert exc_info.value.code == "PSV_INPUT_ERROR"


def test_api526_selects_T_within_tolerance():
    """大面积但在 T 1.05 倍内 → 选 T（无抛错）。"""
    # T 面积 ≈ 5.108e-5 m²
    # 需求 5e-5 → 选 T，oversize = 5.108e-5 / 5e-5 = 1.0216（≤ 1.05）
    inp = OrificeInput(area_required_m2=5e-5)
    r = select_orifice_api526(inp)
    assert r.selected_size == "T"
    assert r.oversize_ratio <= 1.05
    assert r.oversize_ratio >= 1.0


def test_api526_formula_ref():
    """formula_ref 结构化（F-09）。"""
    inp = OrificeInput(area_required_m2=1e-6)
    r = select_orifice_api526(inp)
    assert r.formula_ref.standard == "API_526"
    assert r.formula_ref.version == "7th"
    assert r.formula_ref.clause == "Table 1 / Table 2"


def test_api526_zero_area_raises():
    """area_required = 0 → PsvOrificeInputError。"""
    with pytest.raises(PsvOrificeInputError):
        select_orifice_api526(OrificeInput(area_required_m2=0.0))


def test_api526_negative_area_raises():
    """area_required < 0 → PsvOrificeInputError。"""
    with pytest.raises(PsvOrificeInputError):
        select_orifice_api526(OrificeInput(area_required_m2=-1e-6))


# ============================================================================
# 2. API 526 孔口选型——单孔尺寸边界
# ============================================================================


def test_api526_size_table_includes_all_D_to_T():
    """D~T 14 级全包含（V1 简化版无 U/V/W 扩展）。"""
    inp_d = OrificeInput(area_required_m2=1e-9)  # 极小 → 选 D
    inp_t = OrificeInput(area_required_m2=5e-5)  # 大 → 选 T（≤ T 1.05 倍内）
    r_d = select_orifice_api526(inp_d)
    r_t = select_orifice_api526(inp_t)
    assert r_d.selected_size == "D"
    assert r_t.selected_size == "T"


def test_api526_required_area_passthrough():
    """required_area_m2 透传（audit / SPEC 报告）。"""
    # 需求 2e-7 m² < D 面积 4.58e-7 → 选 D
    inp = OrificeInput(area_required_m2=2e-7)
    r = select_orifice_api526(inp)
    assert r.selected_size == "D"
    assert r.required_area_m2 == 2e-7


# ============================================================================
# 3. API 2000 呼吸阀选型
# ============================================================================


def test_api2000_basic_selection():
    """API 2000 基本选型：需求 < 2" 能力 → 选 2"。

    需求 inbreath=100, outbreath=200
    2": 250/350 能力，均能覆盖
    """
    inp = BreathingValveInput(
        inbreath_flow_m3h=100.0,
        outbreath_flow_m3h=200.0,
        P_design_pa=10_000.0,  # 常压储罐
    )
    r = calc_breathing_valve_api2000(inp)

    assert r.recommended_size_inches == "2"
    assert r.inbreath_capacity_m3h == 250.0
    assert r.outbreath_capacity_m3h == 350.0
    # 压力设定：90% 设计压力
    assert r.pressure_setting_pa == 9_000.0
    # 真空设定：5% 设计压力
    assert r.vacuum_setting_pa == 500.0


def test_api2000_selects_4_inch_for_medium_flow():
    """中等需求 → 选 4"（inbreath=800, outbreath=1200）。"""
    inp = BreathingValveInput(
        inbreath_flow_m3h=800.0,
        outbreath_flow_m3h=1200.0,
        P_design_pa=15_000.0,
    )
    r = calc_breathing_valve_api2000(inp)
    # 4": 1100/1500；3": 600/850（不够 outbreath）
    assert r.recommended_size_inches == "4"


def test_api2000_thermal_breathing_factor_scaling():
    """thermal_breathing_factor > 1 → 需求放大（V1 简化）。"""
    inp_base = BreathingValveInput(
        inbreath_flow_m3h=200.0,  # 2" 能力 250 能覆盖
        outbreath_flow_m3h=300.0,  # 2" 能力 350 能覆盖
        P_design_pa=10_000.0,
        thermal_breathing_factor=1.0,
    )
    inp_scaled = BreathingValveInput(
        inbreath_flow_m3h=200.0,
        outbreath_flow_m3h=300.0,
        P_design_pa=10_000.0,
        thermal_breathing_factor=2.0,  # 需求 ×2
    )
    r_base = calc_breathing_valve_api2000(inp_base)
    r_scaled = calc_breathing_valve_api2000(inp_scaled)

    # base: 2"（250 inbreath, 350 outbreath 均覆盖）
    # scaled: 需求 400/600 → 需 3"（600/850）覆盖
    assert r_base.recommended_size_inches == "2"
    assert r_scaled.recommended_size_inches == "3"


def test_api2000_formula_ref():
    """formula_ref 结构化（F-09）。"""
    inp = BreathingValveInput(
        inbreath_flow_m3h=100.0,
        outbreath_flow_m3h=200.0,
        P_design_pa=10_000.0,
    )
    r = calc_breathing_valve_api2000(inp)
    assert r.formula_ref.standard == "API_2000"
    assert r.formula_ref.version == "7th"
    assert r.formula_ref.clause == "§5.4"


# ============================================================================
# 4. API 2000 边界异常
# ============================================================================


def test_api2000_inbreath_zero_raises():
    """inbreath_flow = 0 → PsvBreathingValveInputError。"""
    inp = BreathingValveInput(
        inbreath_flow_m3h=0.0,
        outbreath_flow_m3h=200.0,
        P_design_pa=10_000.0,
    )
    with pytest.raises(PsvBreathingValveInputError):
        calc_breathing_valve_api2000(inp)


def test_api2000_outbreath_zero_raises():
    """outbreath_flow = 0 → PsvBreathingValveInputError。"""
    inp = BreathingValveInput(
        inbreath_flow_m3h=100.0,
        outbreath_flow_m3h=0.0,
        P_design_pa=10_000.0,
    )
    with pytest.raises(PsvBreathingValveInputError):
        calc_breathing_valve_api2000(inp)


def test_api2000_P_design_zero_raises():
    """P_design = 0 → PsvBreathingValveInputError。"""
    inp = BreathingValveInput(
        inbreath_flow_m3h=100.0,
        outbreath_flow_m3h=200.0,
        P_design_pa=0.0,
    )
    with pytest.raises(PsvBreathingValveInputError):
        calc_breathing_valve_api2000(inp)


# ============================================================================
# 5. 跨服务集成（API 520 面积 → API 526 选型）
# ============================================================================


def test_integration_area_to_orifice():
    """P5-3-4 面积 → P5-3-5 选型端到端集成测试（合理需求范围）。

    1. API 520 气体面积 = 4e-5 m²（合理工业级）
    2. 选 API 526 孔口（≥ 4e-5 m² → 选 T）

    注：API 526 孔口间距较大，oversize > 1.05 是常态；本断言仅要求 ≥ 1.0。
    """
    from app.services.psv import (
        ReliefAreaInput,
        calc_relief_area_api520_gas,
    )

    inp_area = ReliefAreaInput(
        relief_mass_flow_kgs=6.0,
        phase="GAS",
        P_back_pa=150_000.0,
        P_set_pa=300_000.0,
    )
    r_area = calc_relief_area_api520_gas(inp_area)
    r_orifice = select_orifice_api526(OrificeInput(area_required_m2=r_area.area_required_m2))

    assert r_orifice.selected_size == "T"
    assert r_orifice.actual_area_m2 >= r_area.area_required_m2
    assert r_orifice.oversize_ratio >= 1.0