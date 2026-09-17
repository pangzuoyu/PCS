"""SUP-P5-PSV-002 V1.14 §4.2 validate_valve_params 测试（G7-G25 全拦截/警告）。

按 SPEC V1.14 §4.2：

覆盖：
- G7/G8：阀型拦截（PILOT/RUPTURE）
- G10：背压超限（SPRING_LOADED + BUILT_UP）
- G11：blowdown 越界 + 派生
- G14：inlet < 1"
- G12：入/出口 ∉ API 526 + orifice_override ∉ candidates
- G17：BALANCED_BELLOWS 缺 bellows_material
- G21：波纹管材料-介质不兼容
- 介质默认 blowdown 派生（验证 §3.5 联动规则）
- happy path：SPRING_LOADED 默认 → kb=1.0 / source='none'
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
    PsvPilotOperatedNotSupported,
    PsvRuptureDiscNotSupported,
)
from app.services.psv.valve_selection_types import ValidatedParams
from app.services.psv.valve_validation import validate_valve_params


# ============================================================================
# 请求模板：默认 SPRING_LOADED + BUILT_UP + BP=0
# ============================================================================


def _base_req(**overrides) -> dict:
    """最小可用 SPRING_LOADED 请求；overrides 覆盖任意字段。"""
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


def test_g10_balanced_bellows_total_50pct_passes():
    """BALANCED_BELLOWS + total BP=30% → pass（上限 50%）。"""
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        back_pressure_type="BUILT_UP",
        back_pressure_pct=30.0,
    )
    result = validate_valve_params(req)
    assert isinstance(result, ValidatedParams)


def test_g10_superimposed_no_limit_for_spring():
    """SPRING_LOADED + SUPERIMPOSED BP=30% → pass（无硬限；走 CDTP 修正）。"""
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


def test_g11_blowdown_default_derived_from_medium():
    """blowdown 未填 → 默认按 medium 派生（GAS=5%）。"""
    req = _base_req(blowdown_fraction=None, medium="GAS")
    result = validate_valve_params(req)
    # 默认值通过派生填充；本函数不返回 blowdown 字段，但应通过校验
    assert isinstance(result, ValidatedParams)


def test_g11_blowdown_default_liquid_10pct():
    """LIQUID 默认 blowdown 派生 = 10%。"""
    req = _base_req(blowdown_fraction=None, medium="LIQUID")
    # LIQUID 范围 [10%, 20%]；派生 10% 落在边界下端 → pass
    result = validate_valve_params(req)
    assert isinstance(result, ValidatedParams)


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
# Happy path + 派生字段
# ============================================================================


def test_happy_path_spring_loaded_zero_bp_returns_validated_params():
    """SPRING_LOADED + BP=0 → ValidatedParams {kb=1.0, source='none', cdtp_applied=False}。"""
    req = _base_req()
    result = validate_valve_params(req)
    assert isinstance(result, ValidatedParams)
    assert result.valve_type == "SPRING_LOADED"
    assert result.medium == "GAS"
    assert result.cdtp_applied is False
    assert result.kb_factor == 1.0
    assert result.kb_source == "none"
    assert result.candidates == ["H"]  # 2 inch × 3 inch + 300# → H only（G 高压档排除）
    assert result.rupture_disc_kc is None  # NONE


def test_happy_path_balanced_bellows_with_brand_kb():
    """BALANCED_BELLOWS + LESER + BP=20% → kb=LESER 曲线 @ 16% = 0.95。"""
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        back_pressure_type="BUILT_UP",
        back_pressure_pct=20.0,
        overpressure_pct=16.0,
        valve_brand="LESER",
    )
    result = validate_valve_params(req)
    assert result.kb_factor == 0.95
    assert result.kb_source == "manufacturer:LESER"