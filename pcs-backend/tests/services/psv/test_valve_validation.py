"""SUP-P5-PSV-002 V1.14 §4.2 validate_valve_params 拦截类测试（G7-G21 raise）。

按 SPEC V1.14 §4.2：

覆盖：
- G7/G8：阀型拦截（PILOT/RUPTURE）
- G10：背压超限（SPRING_LOADED + BUILT_UP）
- G11：blowdown 越界
- G14：inlet < 1"
- G12：入/出口 ∉ API 526 + orifice_override ∉ candidates
- G17：BALANCED_BELLOWS 缺 bellows_material
- G21：波纹管材料-介质不兼容
- G9：orifice_override 面积 < 计算面积

警告/派生类测试（G13/G15/G24/G25 + CDTP + happy path + blowdown 派生）
已迁出至 test_valve_validation_warnings.py（2026-09-18 LOW backlog 收口，735 → 2 文件）。
"""
from __future__ import annotations

import pytest

from app.services.exceptions import (
    PsvBackPressureExceeded,
    PsvBellowsIncompatible,
    PsvBellowsMaterialRequired,
    PsvBlowdownOutOfRange,
    PsvInletOutletMismatch,
    PsvInletTooSmall,
    PsvOrificeOverrideTooSmall,
    PsvOrificeTemperatureLimit,
    PsvPilotOperatedNotSupported,
    PsvRuptureDiscNotSupported,
)
from app.services.psv.valve_validation import validate_valve_params


def _base_req(**overrides) -> dict:
    """最小可用 SPRING_LOADED 请求；overrides 覆盖任意字段。

    与 test_valve_validation_warnings.py 同源定义；保持双文件副本避免隐式跨文件 fixture。
    """
    return {
        "valve_type": "SPRING_LOADED",
        "body_material": "SS316",
        "bellows_material": None,
        "medium": "GAS",
        "flange_class": "300#",
        "back_pressure_type": "BUILT_UP",
        "back_pressure_pct": 0.0,
        "superimposed_pressure_pa": 0.0,
        "set_pressure_pa": 200_000.0,
        "overpressure_pct": 10.0,
        "blowdown_fraction": None,
        "orifice_override": None,
        "inlet_size": "2 inch",
        "outlet_size": "3 inch",
        "rupture_disc_position": "NONE",
        "valve_brand": None,
        "service_note": None,
        "fluid_temperature_c": None,
        "molecular_weight": None,
        "calculated_area_m2": None,
        "relief_scenario": "FIRE",
        **overrides,
    }


# ============================================================================
# G7 / G8：阀型拦截
# ============================================================================


def test_g7_pilot_operated_blocked():
    """PILOT_OPERATED → 422 PSV_PILOT_OPERATED_NOT_SUPPORTED。"""
    req = _base_req(valve_type="PILOT_OPERATED")
    with pytest.raises(PsvPilotOperatedNotSupported) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_PILOT_OPERATED_NOT_SUPPORTED"


def test_g8_rupture_disc_blocked():
    """RUPTURE_DISC → 422 PSV_RUPTURE_DISC_NOT_SUPPORTED。"""
    req = _base_req(valve_type="RUPTURE_DISC")
    with pytest.raises(PsvRuptureDiscNotSupported) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_RUPTURE_DISC_NOT_SUPPORTED"


# ============================================================================
# G10：背压超阀型范围
# ============================================================================


def test_g10_built_up_backpressure_exceeds_spring_limit():
    """SPRING_LOADED + BUILT_UP BP=15% → 422（弹簧式 BUILT_UP 上限 10%）。"""
    req = _base_req(back_pressure_type="BUILT_UP", back_pressure_pct=15.0)
    with pytest.raises(PsvBackPressureExceeded) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_BACK_PRESSURE_EXCEEDED"
    assert exc_info.value.details["max_pct"] == 10.0


def test_g10_superimposed_no_limit_for_spring():
    """SPRING_LOADED + SUPERIMPOSED BP=30% → pass（无硬限；走 CDTP 修正）。

    注：本测试名为 ..._no_limit_for_spring 但预期 raise 路径不同——
    SUPERIMPOSED 不会触发 G10 拦截（应 pass 而不 raise），CDTP 派生字段验证。
    由 SPEC §4.3 保证 CDTP 与 G10 互不干扰，故放在 blocks 文件统一验证。
    """
    req = _base_req(
        back_pressure_type="SUPERIMPOSED",
        back_pressure_pct=30.0,
        superimposed_pressure_pa=50_000.0,
    )
    result = validate_valve_params(req)
    assert result.cdtp_applied is True
    assert result.cdtp_set_pressure_pa == 150_000.0


# ============================================================================
# G11：blowdown 范围
# ============================================================================


def test_g11_blowdown_out_of_range():
    """SPRING_LOADED + GAS + blowdown=20% → 422（GAS 范围 [5%, 10%]）。"""
    req = _base_req(blowdown_fraction=0.20)
    with pytest.raises(PsvBlowdownOutOfRange) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_BLOWDOWN_OUT_OF_RANGE"
    assert exc_info.value.details["min"] == 0.05
    assert exc_info.value.details["max"] == 0.10


# ============================================================================
# G14：入口 < 1 inch
# ============================================================================


def test_g14_inlet_too_small():
    """inlet=0.5 inch → 422 PSV_INLET_TOO_SMALL。"""
    req = _base_req(inlet_size="0.5 inch", outlet_size="1 inch", flange_class="150#")
    with pytest.raises(PsvInletTooSmall) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_INLET_TOO_SMALL"
    assert exc_info.value.details["min_inlet"] == "1 inch"


# ============================================================================
# G12：入/出口 ∉ API 526 / orifice_override ∉ candidates
# ============================================================================


def test_g12_inlet_outlet_not_in_api526():
    """入/出口 5×7 不在 API 526 反向映射 → 422 PSV_INLET_OUTLET_MISMATCH。"""
    req = _base_req(inlet_size="5 inch", outlet_size="7 inch", flange_class="300#")
    with pytest.raises(PsvInletOutletMismatch) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_INLET_OUTLET_MISMATCH"


def test_g12_orifice_override_not_in_candidates():
    """2×3 inlet/orifice_override='D'（不在 2×3 候选 H/G）→ 422。"""
    req = _base_req(
        inlet_size="2 inch",
        outlet_size="3 inch",
        flange_class="300#",
        orifice_override="D",
    )
    with pytest.raises(PsvInletOutletMismatch) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_INLET_OUTLET_MISMATCH"
    assert exc_info.value.details["orifice_override"] == "D"


# ============================================================================
# G17：BALANCED_BELLOWS 缺 bellows_material
# ============================================================================


def test_g17_balanced_bellows_missing_material():
    """BALANCED_BELLOWS + bellows_material=None → 422 PSV_BELLOWS_MATERIAL_REQUIRED。"""
    req = _base_req(valve_type="BALANCED_BELLOWS", bellows_material=None)
    with pytest.raises(PsvBellowsMaterialRequired) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_BELLOWS_MATERIAL_REQUIRED"


# ============================================================================
# G21：波纹管材料-介质不兼容
# ============================================================================


def test_g21_bellows_material_medium_incompatible():
    """BALANCED_BELLOWS + HASTELLOY_C276 + service_note 含强氧化性 → 422。"""
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="HASTELLOY_C276",
        service_note="本工段为热浓硝酸介质，强氧化性介质工况",
    )
    with pytest.raises(PsvBellowsIncompatible) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_BELLOWS_INCOMPATIBLE"


# ============================================================================
# G15: Q/R/T 高温低分子量（raise 部分）
# ============================================================================


def test_g15_q_high_temp_light_gas_raises():
    """Q 孔口 + T=200°C + MW=5 → 422 PSV_ORIFICE_TEMPERATURE_LIMIT。"""
    req = _base_req(
        inlet_size="6 inch",
        outlet_size="8 inch",
        flange_class="300#",
        orifice_override="Q",
        fluid_temperature_c=200.0,
        molecular_weight=5.0,
    )
    with pytest.raises(PsvOrificeTemperatureLimit) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_ORIFICE_TEMPERATURE_LIMIT"
    assert exc_info.value.details["orifice"] == "Q"


def test_g15_t_high_temp_light_gas_raises():
    """T 孔口 + T=200°C + MW=5 → 422。"""
    req = _base_req(
        inlet_size="8 inch",
        outlet_size="10 inch",
        flange_class="300#",
        orifice_override="T",
        fluid_temperature_c=200.0,
        molecular_weight=5.0,
    )
    with pytest.raises(PsvOrificeTemperatureLimit):
        validate_valve_params(req)


def test_g15_raises_when_temp_above_and_mw_below():
    """G15：Q/R/T + T>=177 + MW<10 → raise PsvOrificeTemperatureLimit。"""
    req = _base_req(
        inlet_size="6 inch",
        outlet_size="8 inch",
        flange_class="300#",
        orifice_override="Q",
        fluid_temperature_c=300.0,
        molecular_weight=5.0,
    )
    with pytest.raises(PsvOrificeTemperatureLimit) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_ORIFICE_TEMPERATURE_LIMIT"
    assert exc_info.value.details["orifice"] == "Q"


# ============================================================================
# G9: orifice_override 面积 < 计算面积（SUP-P5-PSV-002 V1.14 §4.2 G9）
# ============================================================================


def test_g9_orifice_override_area_lt_calculated_area_raises():
    """orifice_override 面积 < 计算面积 → 422 PSV_ORIFICE_OVERRIDE_TOO_SMALL。

    2×3 / 300# candidates=['H']；H = 2.93e-06 m²；计算面积 5.0e-06 m² → H 远小，raise
    """
    req = _base_req(
        orifice_override="H",
        calculated_area_m2=5.0e-06,
    )
    with pytest.raises(PsvOrificeOverrideTooSmall) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_ORIFICE_OVERRIDE_TOO_SMALL"
    details = exc_info.value.details
    assert details["orifice_override"] == "H"
    assert details["override_area_m2"] < details["calculated_area_m2"]


# ============================================================================
# OPEN-10-4 余项：blowdown 越界补充（raise 部分）
# ============================================================================


def test_blowdown_explicit_liquid_25pct_out_of_range():
    """blowdown_fraction=0.25 + LIQUID (上限 20%) → raise G11。"""
    req = _base_req(medium="LIQUID", blowdown_fraction=0.25)
    with pytest.raises(PsvBlowdownOutOfRange) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_BLOWDOWN_OUT_OF_RANGE"
    assert exc_info.value.details["valve_type"] == "SPRING_LOADED"
    assert exc_info.value.details["max"] == 0.20
