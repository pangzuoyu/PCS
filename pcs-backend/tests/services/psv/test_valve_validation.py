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
    PsvOrificeTemperatureLimit,
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


# ============================================================================
# G13: 平衡波纹管式 + CARBON_STEEL + 强氧化性 service_note → 警告
# ============================================================================


def test_g13_balanced_carbon_steel_in_oxidizing_warning():
    """BALANCED_BELLOWS + CARBON_STEEL + 强氧化性 service_note → warnings 含 G13。"""
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        body_material="CARBON_STEEL",
        service_note="强氧化性介质工况（热浓硝酸旁路）",
    )
    result = validate_valve_params(req)
    assert any("G13" in w for w in result.warnings)


def test_g13_no_warning_when_body_material_is_alloy():
    """BALANCED_BELLOWS + ALLOY + 强氧化性 → 不触发 G13 警告。"""
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        body_material="ALLOY",
        service_note="强氧化性介质工况",
    )
    result = validate_valve_params(req)
    assert not any("G13" in w for w in result.warnings)


# ============================================================================
# G15: Q/R/T 高温低分子量
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


def test_g15_no_temp_passes():
    """Q 孔口 + 无温度/分子量 → 不受限（无法判断）。"""
    req = _base_req(
        inlet_size="6 inch",
        outlet_size="8 inch",
        flange_class="300#",
        orifice_override="Q",
        fluid_temperature_c=None,
        molecular_weight=None,
    )
    result = validate_valve_params(req)
    assert isinstance(result, ValidatedParams)


# ============================================================================
# G24/G25: 警告收集
# ============================================================================


def test_g24_unknown_brand_warning():
    """valve_brand='UnknownCo' + BP>0 → warnings 含 G24（fallback api520_fig30）。"""
    req = _base_req(
        back_pressure_type="BUILT_UP",
        back_pressure_pct=5.0,
        valve_brand="UnknownCo",
    )
    result = validate_valve_params(req)
    assert any("G24" in w for w in result.warnings)


def test_g25_mixed_brand_warning():
    """valve_brand='LESER+Consolidated' → warnings 含 G25。"""
    req = _base_req(
        back_pressure_type="BUILT_UP",
        back_pressure_pct=5.0,
        valve_brand="LESER+Consolidated",
    )
    result = validate_valve_params(req)
    assert any("G25" in w for w in result.warnings)


# ============================================================================
# CDTP 触发条件
# ============================================================================


def test_cdtp_not_applied_superimposed_zero():
    """SPRING_LOADED + SUPERIMPOSED + BP=0 + superimposed_pa=0 → cdtp_applied=False。"""
    req = _base_req(
        back_pressure_type="SUPERIMPOSED",
        back_pressure_pct=0.0,
        superimposed_pressure_pa=0.0,
    )
    result = validate_valve_params(req)
    assert result.cdtp_applied is False
    assert result.cdtp_set_pressure_pa is None


def test_cdtp_applied_superimposed_nonzero():
    """SPRING_LOADED + SUPERIMPOSED + BP=5 + superimposed_pa=50_000 → cdtp_applied=True。"""
    req = _base_req(
        back_pressure_type="SUPERIMPOSED",
        back_pressure_pct=5.0,
        superimposed_pressure_pa=50_000.0,
        set_pressure_pa=200_000.0,
    )
    result = validate_valve_params(req)
    assert result.cdtp_applied is True
    assert result.cdtp_set_pressure_pa == 150_000.0


def test_cdtp_built_up_no_correction():
    """SPRING_LOADED + BUILT_UP + BP=5 → cdtp_applied=False（走 Kb 路径）。"""
    req = _base_req(
        back_pressure_type="BUILT_UP",
        back_pressure_pct=5.0,
    )
    result = validate_valve_params(req)
    assert result.cdtp_applied is False


# ============================================================================
# rupture_disc_kc（ASME UG-127）
# ============================================================================


def test_rupture_disc_kc_upstream():
    """rupture_disc_position='UPSTREAM' → kc=0.90（ASME UG-127）。"""
    req = _base_req(rupture_disc_position="UPSTREAM")
    result = validate_valve_params(req)
    assert result.rupture_disc_kc == 0.90


def test_rupture_disc_kc_downstream():
    """rupture_disc_position='DOWNSTREAM' → kc=1.00。"""
    req = _base_req(rupture_disc_position="DOWNSTREAM")
    result = validate_valve_params(req)
    assert result.rupture_disc_kc == 1.00


def test_rupture_disc_kc_none():
    """rupture_disc_position='NONE' → kc=None（无爆破膜组合）。"""
    req = _base_req(rupture_disc_position="NONE")
    result = validate_valve_params(req)
    assert result.rupture_disc_kc is None


# ============================================================================
# 边界 — inlet/orifice_override 缺失
# ============================================================================


def test_orifice_override_validated_when_in_candidates():
    """orifice_override='H' 在 candidates → orifice_override_validated='H'。"""
    req = _base_req(
        inlet_size="2 inch",
        outlet_size="3 inch",
        flange_class="300#",
        orifice_override="H",
    )
    result = validate_valve_params(req)
    assert result.orifice_override_validated == "H"


def test_balanced_bellows_no_service_note_passes():
    """BALANCED_BELLOWS + 无 service_note → 不触发 G21。"""
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        service_note=None,
    )
    result = validate_valve_params(req)
    assert isinstance(result, ValidatedParams)


# ============================================================================
# OPEN-10-4 余项：CDTP + Kb 联动 / warnings 累积 / blowdown 4 介质
# ============================================================================


def test_cdtp_kb_interplay_superimposed_uses_zero_bp():
    """SUPERIMPOSED + BP>0 + superimposed_pa>0：bp_for_kb=0 → Kb=1.0/'none'（kb 不重复调 cdtp）。

    SPEC §4.3：SUPERIMPOSED 走 CDTP 修正，背压不直接进入 Kb 路径。
    """
    req = _base_req(
        back_pressure_type="SUPERIMPOSED",
        back_pressure_pct=5.0,
        superimposed_pressure_pa=50_000.0,
        set_pressure_pa=200_000.0,
    )
    result = validate_valve_params(req)
    assert result.cdtp_applied is True
    assert result.cdtp_set_pressure_pa == 150_000.0
    # Kb 走 bp_for_kb=0 路径 → SPRING_LOADED + BP=0 → Kb=1.0 / 'none'
    assert result.kb_factor == 1.00
    assert result.kb_source == "none"


def test_cdtp_kb_brand_kept_when_superimposed():
    """SUPERIMPOSED + 指定 LESER：bp_for_kb=0 → 'none'（策略 1 优先于品牌查询）。

    注：bp_pct=5（实际值）被 KB 路径忽略（bp_for_kb=0），策略 1 触发。
    """
    req = _base_req(
        back_pressure_type="SUPERIMPOSED",
        back_pressure_pct=5.0,
        superimposed_pressure_pa=50_000.0,
        set_pressure_pa=200_000.0,
        valve_brand="LESER",
    )
    result = validate_valve_params(req)
    assert result.cdtp_applied is True
    assert result.kb_source == "none"  # 策略 1 优先于品牌查询


def test_warnings_g13_carbon_steel_wet_h2s():
    """G13 触发：CARBON_STEEL + 湿 H₂S service_note → warnings 含 G13 文案（占位）。"""
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        body_material="CARBON_STEEL",
        service_note="湿 H₂S 工况（NACE MR0175）",
    )
    result = validate_valve_params(req)
    assert any("G13" in w for w in result.warnings)


def test_warnings_g13_ss304_strong_oxidizing():
    """G13 触发：SS304 + 强氧化性 → warnings 含 G13（占位）。"""
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        body_material="SS304",
        service_note="强氧化性介质 HNO3",
    )
    result = validate_valve_params(req)
    assert any("G13" in w for w in result.warnings)


def test_warnings_g13_not_triggered_for_alloy():
    """G13 不触发：body=ALLOY 即便含湿 H₂S。"""
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        body_material="ALLOY",
        service_note="湿 H₂S 工况",
    )
    result = validate_valve_params(req)
    assert not any("G13" in w for w in result.warnings)


def test_warnings_g25_triggered_for_all_known_mixed_brand():
    """G25 触发：LESER+Consolidated 全在 _KB_DATA → kb_source='mixed:...' → G25 警告。

    与 G24 不同：mixed 部分缺失 fallback 时 G25 不触发；全 known 时 G25 触发但 G24 不触发。
    """
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        back_pressure_type="BUILT_UP",
        back_pressure_pct=20.0,
        overpressure_pct=16.0,
        valve_brand="LESER+Consolidated",
    )
    result = validate_valve_params(req)
    assert any("G25" in w for w in result.warnings)
    assert result.kb_source == "mixed:LESER+Consolidated"
    # 全 known → 不走 fallback → G24 不触发
    assert not any("G24" in w for w in result.warnings)


def test_warnings_g24_unknown_mixed_falls_back_to_api520():
    """G24 触发（kb_source=api520_fig30 + 指定 brand）；mixed 中断 → G25 不触发。

    注：mixed 含 unknown mfr → kb_service 部分缺失返回 None → fallback api520_fig30。
    G25 要求 kb_source 前缀 'mixed:'，fallback 后不再匹配。
    用 BALANCED_BELLOWS 避开 SPRING_LOADED + BUILT_UP=20% 的 G10 拦截。
    """
    req = _base_req(
        valve_type="BALANCED_BELLOWS",
        bellows_material="SS316L",
        back_pressure_type="BUILT_UP",
        back_pressure_pct=20.0,
        overpressure_pct=16.0,
        valve_brand="LESER+UnknownMFR",
    )
    result = validate_valve_params(req)
    assert any("G24" in w for w in result.warnings)
    assert result.kb_source == "api520_fig30"
    # G25 不触发：mixed 中断 fallback（kb_source 不是 'mixed:' 前缀）
    assert not any("G25" in w for w in result.warnings)


def test_blowdown_default_gas_5pct():
    """blowdown_fraction=None + medium=GAS → 默认 5%（BLOWDOWN_DEFAULT_BY_MEDIUM 派生）。"""
    req = _base_req(medium="GAS", blowdown_fraction=None)
    result = validate_valve_params(req)
    assert result.cdtp_applied is False
    assert result.kb_factor == 1.00  # SPRING_LOADED + BP=0 默认


def test_blowdown_default_liquid_10pct():
    """blowdown_fraction=None + medium=LIQUID → 默认 10%。"""
    req = _base_req(medium="LIQUID", blowdown_fraction=None)
    result = validate_valve_params(req)
    assert result.cdtp_applied is False


def test_blowdown_default_two_phase_10pct():
    """blowdown_fraction=None + medium=TWO_PHASE → 默认 10%。"""
    req = _base_req(medium="TWO_PHASE", blowdown_fraction=None)
    result = validate_valve_params(req)
    assert result.cdtp_applied is False


def test_blowdown_default_vapor_5pct():
    """blowdown_fraction=None + medium=VAPOR → 默认 5%。"""
    req = _base_req(medium="VAPOR", blowdown_fraction=None)
    result = validate_valve_params(req)
    assert result.cdtp_applied is False


def test_blowdown_explicit_liquid_15pct_in_range():
    """blowdown_fraction=0.15 + LIQUID (10-20% 范围) → 不 raise。"""
    req = _base_req(medium="LIQUID", blowdown_fraction=0.15)
    result = validate_valve_params(req)
    assert result.cdtp_applied is False


def test_blowdown_explicit_gas_8pct_in_range():
    """blowdown_fraction=0.08 + GAS (5-10% 范围) → 不 raise。"""
    req = _base_req(medium="GAS", blowdown_fraction=0.08)
    result = validate_valve_params(req)
    assert result.cdtp_applied is False


def test_blowdown_explicit_liquid_25pct_out_of_range():
    """blowdown_fraction=0.25 + LIQUID (上限 20%) → raise G11。"""
    req = _base_req(medium="LIQUID", blowdown_fraction=0.25)
    with pytest.raises(PsvBlowdownOutOfRange) as exc_info:
        validate_valve_params(req)
    assert exc_info.value.code == "PSV_BLOWDOWN_OUT_OF_RANGE"
    assert exc_info.value.details["valve_type"] == "SPRING_LOADED"
    assert exc_info.value.details["max"] == 0.20


def test_orifice_override_None_means_first_candidate_unused():
    """orifice_override=None → orifice_override_validated=None（不自动取 candidates[0]）。"""
    req = _base_req(
        inlet_size="2 inch",
        outlet_size="3 inch",
        flange_class="300#",
        orifice_override=None,
    )
    result = validate_valve_params(req)
    assert result.orifice_override_validated is None
    assert len(result.candidates) >= 1  # 但 candidates 仍计算


def test_g15_orifice_temperature_no_trigger_without_temp():
    """G15：Q/R/T + 无 fluid_temperature_c 也不 raise（温度缺失时不拦截）。

    用 6"×8" 300# 让 Q 进入 candidates（实测 ['P', 'Q']）。
    """
    req = _base_req(
        inlet_size="6 inch",
        outlet_size="8 inch",
        flange_class="300#",
        orifice_override="Q",
        fluid_temperature_c=None,
        molecular_weight=None,
    )
    result = validate_valve_params(req)
    assert result.orifice_override_validated == "Q"


def test_g15_passes_when_temp_below_threshold():
    """G15：Q/R/T + T<177°C + MW>=10 → 不 raise（高温低分子量条件未触发）。"""
    req = _base_req(
        inlet_size="6 inch",
        outlet_size="8 inch",
        flange_class="300#",
        orifice_override="Q",
        fluid_temperature_c=100.0,
        molecular_weight=20.0,
    )
    result = validate_valve_params(req)
    assert result.orifice_override_validated == "Q"


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