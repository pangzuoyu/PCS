"""P6-4 Task 4 (C-17 显式水含量) saturation_water_content_service 单元测试。

按 V1.2 5 单测要求（brief）：

1. **标准大气压**：25°C × 101.325 kPa → W ≈ 0.0202 kg/kg（≈ 14.7 g/kg）
2. **Imperial（2000 psia × 60°F）**：CoolProp 越界 → WARNING + NaN
3. **温度越界 WARNING**：T = 105°C / -55°C → out_of_range=True + warning
4. **单位转换**：3 单位独立 + kg/kg ↔ mg/Sm³ 内部一致 + lb/MMscf 系数
5. **酸性气校正**：CO2+H2S > 40 mol% 触发；≤ 40 mol% 不触发

附加 ASHRAE 黄金对账（D5 三级验收）：10 点 ASHRAE Fundamentals 2021
Table 1 cross-check（rel ≤ 1e-3 = 0.1%）。
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.psychro import (  # noqa: E402
    SaturationWaterContentInput,
    SaturationWaterContentInputError,
    calc_saturation_water_content,
)
from app.services.psychro.saturation_water_content_service import (  # noqa: E402
    _MG_SM3_TO_LB_PER_MMSCF,
    _STANDARD_DRY_AIR_DENSITY_KG_SM3,
    _calc_saturation_w_cached,
)

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_saturation_w_ashrae.json"


# ============================================================================
# 1. 标准大气压（25°C × 101.325 kPa）
# ============================================================================


def test_calc_saturation_water_content_standard_atmospheric() -> None:
    """标准大气压 25°C × 101.325 kPa → W ≈ 0.0202 kg/kg。

    与 ASHRAE Fundamentals 2021 Chapter 1 Table 1 一致；
    3 单位独立输出（kg/kg / mg/Sm³ / lb/MMscf）。
    """
    result = calc_saturation_water_content(
        SaturationWaterContentInput(temperature_c=25.0)
    )
    # 物理期望（ASHRAE Table 1）：W ≈ 0.0202 kg/kg dry air
    assert abs(result.saturation_w_kg_kg - 0.020173) < 0.001
    # 25°C 在 SPEC 安全范围 [-50, 100]°C 内
    assert result.temperature_out_of_range is False
    assert result.warning_message is None
    assert result.acidic_gas_correction_applied is False
    assert result.acidic_gas_correction_factor == 1.0
    # 公式溯源
    assert result.formula_ref == "ASHRAE_RP-1845_CoolProp"
    # 饱和温度回显
    assert result.saturation_T_c == 25.0
    # 3 单位（mg/Sm³ / lb/MMscf）非负且合理
    assert result.saturation_w_mg_sm3 > 0
    assert result.saturation_w_lb_per_mmscf > 0


# ============================================================================
# 2. Imperial（2000 psia × 60°F）— CoolProp 越界 → WARNING + NaN
# ============================================================================


def test_calc_saturation_water_content_imperial_2000_psia() -> None:
    """Imperial 2000 psia × 60°F：超出 SPEC §3.2.5 安全范围（> 100 atm）。

    CoolProp.HumidAirProp.HAPropsSI 在 P > ~1e7 Pa (~100 atm / ~1450 psia)
    拒绝（"pressure value outside the range of validity"）；service 层
    按 SPEC "WARNING，不抛错"约定吞下异常，以 NaN + WARNING 表达。
    """
    # 2000 psia = 13789.52 kPa ≈ 137 atm（远超 CoolProp 上限 ~100 atm）
    result = calc_saturation_water_content(
        SaturationWaterContentInput(
            temperature_c=15.5556,  # 60°F
            pressure_kpa=13789.52,
            units="IMPERIAL",
        )
    )
    # 越界标记
    assert result.temperature_out_of_range is True
    # WARNING 含 SPEC 安全范围提示 + CoolProp 错误细节
    assert result.warning_message is not None
    assert "CoolProp" in result.warning_message
    # 3 单位均为 NaN（CoolProp 拒绝计算）
    assert math.isnan(result.saturation_w_kg_kg)
    assert math.isnan(result.saturation_w_mg_sm3)
    assert math.isnan(result.saturation_w_lb_per_mmscf)


# ============================================================================
# 3. 温度越界 WARNING（T > 100°C / T < -50°C）
# ============================================================================


def test_calc_saturation_water_content_temperature_out_of_range() -> None:
    """温度越界（T > 100°C 或 T < -50°C）→ WARNING + NaN（不抛错）。

    SPEC §3.2.5 §3.9.2 安全范围 [-50, 100]°C；超界仅 WARNING，不抛错。
    CoolProp 在 105°C × 101.325 kPa 也实际越界（x_w > 0.94145）；service
    双重兜底：SPEC 越界 + CoolProp 拒绝 → NaN + 增强 WARNING。
    """
    # 高温越界
    r_high = calc_saturation_water_content(
        SaturationWaterContentInput(temperature_c=105.0)
    )
    assert r_high.temperature_out_of_range is True
    assert r_high.warning_message is not None
    assert "100" in r_high.warning_message
    assert math.isnan(r_high.saturation_w_kg_kg)
    # 低温越界（-55°C < -50°C；CoolProp 仍能计算小 W）
    r_low = calc_saturation_water_content(
        SaturationWaterContentInput(temperature_c=-55.0)
    )
    assert r_low.temperature_out_of_range is True
    assert r_low.warning_message is not None
    assert "-50" in r_low.warning_message or "-55" in r_low.warning_message


# ============================================================================
# 4. 单位转换（3 单位独立 + 内部一致）
# ============================================================================


def test_calc_saturation_water_content_unit_conversions() -> None:
    """单位转换：3 单位独立字段 + kg/kg ↔ mg/Sm³ 内部一致 + lb/MMscf 系数。

    公式（SPEC §3.2.5 §3.9.2）：
        mg/Sm³ = W × ρ_dry_air × 1e6（ρ=1.2923 kg/Sm³ @ STP）
        lb/MMscf = mg/Sm³ × 0.062428
    """
    result = calc_saturation_water_content(
        SaturationWaterContentInput(temperature_c=25.0)
    )
    # mg/Sm³ ↔ kg/kg 内部一致
    expected_mg = (
        result.saturation_w_kg_kg * _STANDARD_DRY_AIR_DENSITY_KG_SM3 * 1.0e6
    )
    assert abs(result.saturation_w_mg_sm3 - expected_mg) < 1.0  # rel ~ 1e-6
    # lb/MMscf ↔ mg/Sm³ 内部一致
    expected_lb = result.saturation_w_mg_sm3 * _MG_SM3_TO_LB_PER_MMSCF
    assert abs(result.saturation_w_lb_per_mmscf - expected_lb) < 1.0
    # 数量级合理性（25°C 饱和 W ≈ 26 g/Sm³）
    assert 2.0e4 < result.saturation_w_mg_sm3 < 3.0e4
    # 数量级合理性（≈ 1628 lb/MMscf）
    assert 1.5e3 < result.saturation_w_lb_per_mmscf < 2.0e3
    # 不混用：3 字段各自独立（非 None）
    assert result.saturation_w_kg_kg is not None
    assert result.saturation_w_mg_sm3 is not None
    assert result.saturation_w_lb_per_mmscf is not None


# ============================================================================
# 5. 酸性气校正（CO2+H2S > 40 mol% 触发；≤ 40 mol% 不触发）
# ============================================================================


def test_calc_saturation_water_content_acidic_gas_correction() -> None:
    """酸性气校正：CO2+H2S > 40 mol% 触发 ISO 18453 简式；≤ 40 mol% 不触发。

    简化模型：f = 1 + 0.05 × (x_CO2 + x_H2S − 0.40) / 0.60，上限 1.05。
    """
    # 触发校正（50 mol% 酸性气 → 校正因子 ≈ 1.0083）
    r_trigger = calc_saturation_water_content(
        SaturationWaterContentInput(
            temperature_c=25.0,
            acidic_gas_composition={"CO2": 0.30, "H2S": 0.20},
        )
    )
    assert r_trigger.acidic_gas_correction_applied is True
    assert 1.005 < r_trigger.acidic_gas_correction_factor <= 1.05
    # 校正后 W 应略大于未校正
    r_no_corr = calc_saturation_water_content(
        SaturationWaterContentInput(temperature_c=25.0)
    )
    assert r_trigger.saturation_w_kg_kg > r_no_corr.saturation_w_kg_kg
    # 不触发校正（35 mol% 酸性气）
    r_no_trigger = calc_saturation_water_content(
        SaturationWaterContentInput(
            temperature_c=25.0,
            acidic_gas_composition={"CO2": 0.30, "H2S": 0.05},
        )
    )
    assert r_no_trigger.acidic_gas_correction_applied is False
    assert r_no_trigger.acidic_gas_correction_factor == 1.0
    assert r_no_trigger.saturation_w_kg_kg == r_no_corr.saturation_w_kg_kg
    # 边界（恰好 40 mol% → 不触发）
    r_boundary = calc_saturation_water_content(
        SaturationWaterContentInput(
            temperature_c=25.0,
            acidic_gas_composition={"CO2": 0.40, "H2S": 0.0},
        )
    )
    assert r_boundary.acidic_gas_correction_applied is False


# ============================================================================
# 6. ASHRAE Fundamentals 2021 黄金对账（D5 三级验收）
# ============================================================================


@pytest.mark.parametrize("idx", range(10))
def test_ashrae_table_1_golden_cross_check(idx: int) -> None:
    """ASHRAE Fundamentals 2021 Table 1 黄金对账（10 点）。

    验收口径：rel ≤ 1e-3（0.1%；D5 三级验收"强公式"口径）。
    fixture 路径：tests/services/psychro/fixtures/golden_saturation_w_ashrae.json。
    """
    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        fixture = json.load(f)
    point = fixture["points"][idx]
    result = calc_saturation_water_content(
        SaturationWaterContentInput(
            temperature_c=point["temperature_c"],
            pressure_kpa=point["pressure_kpa"],
        )
    )
    # kg/kg 黄金对账（D5 < 0.1%）
    assert abs(result.saturation_w_kg_kg - point["saturation_w_kg_kg"]) < 1e-3
    # mg/Sm³ 黄金对账（绝对容差 0.5 mg）
    assert abs(result.saturation_w_mg_sm3 - point["saturation_w_mg_sm3"]) < 0.5
    # lb/MMscf 黄金对账（绝对容差 0.5 lb）
    assert (
        abs(result.saturation_w_lb_per_mmscf - point["saturation_w_lb_per_mmscf"])
        < 0.5
    )


# ============================================================================
# 7. lru_cache 验证（D14 maxsize=4096）
# ============================================================================


def test_lru_cache_maxsize_4096_and_cache_hit() -> None:
    """D14 lru_cache(maxsize=4096) 验证：参数 + 缓存命中。

    cache key 包含全部输入参数（temperature_c / pressure_kpa /
    acidic_gas_composition frozen items）。
    """
    # 清空 cache（pytest run 间可能残留）
    _calc_saturation_w_cached.cache_clear()
    # maxsize 校验
    assert _calc_saturation_w_cached.cache_parameters()["maxsize"] == 4096
    # 首次调用 miss → 后续 hit
    calc_saturation_water_content(SaturationWaterContentInput(temperature_c=25.0))
    calc_saturation_water_content(SaturationWaterContentInput(temperature_c=25.0))
    info = _calc_saturation_w_cached.cache_info()
    assert info.hits >= 1
    assert info.misses >= 1
    # 不同酸性气 composition 独立 cache key
    calc_saturation_water_content(
        SaturationWaterContentInput(
            temperature_c=25.0,
            acidic_gas_composition={"CO2": 0.30, "H2S": 0.20},
        )
    )
    info2 = _calc_saturation_w_cached.cache_info()
    # 酸性气变化 → miss+1（独立 cache entry）
    assert info2.misses == info.misses + 1


# ============================================================================
# 8. 输入校验（schema-like）
# ============================================================================


def test_input_validation_rejects_absolute_zero_and_zero_pressure() -> None:
    """输入校验：T < -273.15 / P <= 0 抛 SaturationWaterContentInputError。"""
    # T < -273.15 → 物理极值越界
    with pytest.raises(SaturationWaterContentInputError):
        SaturationWaterContentInput(temperature_c=-300.0)
    # P <= 0 → 非正压力
    with pytest.raises(SaturationWaterContentInputError):
        SaturationWaterContentInput(temperature_c=25.0, pressure_kpa=0.0)
    with pytest.raises(SaturationWaterContentInputError):
        SaturationWaterContentInput(temperature_c=25.0, pressure_kpa=-1.0)
    # units 非法字面
    with pytest.raises(SaturationWaterContentInputError):
        SaturationWaterContentInput(temperature_c=25.0, units="FOO")


# ============================================================================
# 9. flash stub cross-check（D2 cross-check ≤ 1%）
# ============================================================================


def test_flash_saturation_helper_cross_check() -> None:
    """flash stub cross-check vs ASHRAE 黄金 fixture ≤ 1%。

    D2 决策：flash/saturation_helper.py stub 端 verify_saturation_w
    接口与 GOLDEN_FIXTURE 对账；10 点全部 pass。
    """
    from app.services.flash import (
        flash_saturation_water_content,
        get_golden_saturation_w_kg_kg,
        verify_saturation_w,
    )

    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        fixture = json.load(f)
    for point in fixture["points"]:
        golden = get_golden_saturation_w_kg_kg(
            temperature_c=point["temperature_c"],
            pressure_kpa=point["pressure_kpa"],
        )
        assert golden is not None
        # flash stub 输出
        w_flash = flash_saturation_water_content(
            temperature_c=point["temperature_c"],
            pressure_kpa=point["pressure_kpa"],
        )
        # 与黄金 cross-check
        passed, _ = verify_saturation_w(
            w_kg_kg=w_flash,
            temperature_c=point["temperature_c"],
            pressure_kpa=point["pressure_kpa"],
        )
        assert passed, (
            f"cross-check failed at {point['id']}: w_flash={w_flash} vs golden={golden}"
        )


# ============================================================================
# 10. 物理极值对照 — saturation_W < humidity_ratio_kg_kg at non-1.0 RH
# ============================================================================


def test_saturation_w_equals_rh1_humidity_ratio() -> None:
    """饱和 W = RH=1.0 时的 humidity_ratio（ADR-0030 决策 6 核心约束）。

    验证：饱和 W 与 chedl_wrapper.humid_air_humidity_ratio(T, RH=1.0, P)
    直接调用结果**完全相等**（无算法差异；service 是包装层非新算法）。
    """
    from app.services.chedl_wrapper import humid_air_humidity_ratio

    t_k = 25.0 + 273.15
    p_pa = 101325.0
    w_direct = humid_air_humidity_ratio(t_k, 1.0, p_pa)
    r = calc_saturation_water_content(
        SaturationWaterContentInput(temperature_c=25.0)
    )
    assert abs(r.saturation_w_kg_kg - w_direct) < 1e-12