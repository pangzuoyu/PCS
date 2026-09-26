"""P6-5 Task C3 FLARE C-22 扩散（API 521 §5.15 + Pasquill-Gifford + 辐射热强度）。

按 SPEC §3.10.2 V1.5 + API 521 7th Ed. §5.15：
- Briggs 1973 Pasquill-Gifford 6 类稳定度（A/B/C/D/E/F）
- 点源高斯中心线浓度 C(x,0,0) = Q/(π·σy·σz·u)·exp(-H²/(2σz²))
  （M-3 v2 含地面反射：源+镜像=2 倍 → π 而非 2π）
- API 521 §5.15 辐射热强度 q = Q_comb/(4π·r²)
- 致死/致伤距离：4.7 / 12.6 kW/m² 二分查找（简化解 r = sqrt(Q/4π·τ)）

测试模式参照 ``tests/services/flare/test_flare_tip.py``（纯计算函数，
无 DB / Mock session）。共 7 测试 = 6 业务 + 1 frozen-pattern（D7 接口冻结）。
"""
from __future__ import annotations

import json
import sys
from dataclasses import FrozenInstanceError, fields
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.exceptions import PcsError  # noqa: E402
from app.services.flare.dispersion_service import (  # noqa: E402
    DispersionInput,
    DispersionInputError,
    DispersionResult,
    calc_dispersion,
)

# ============================================================================
# 1. Pasquill-Gifford A 类（强不稳定）扩散
# ============================================================================


def test_pasquill_gifford_A_extreme_unstable_dispersion():
    """Pasquill-Gifford A 类（强不稳定）+ 10 m/s 风 + 1 kg/s CH4（MW=16）100m 下风向。

    A 类 sigma_y 大（强横向扩散），sigma_z 也大；中心线浓度应 > 0 且 sigma > 20 m。
    """
    inp = DispersionInput(
        gas_release_rate_kg_s=1.0,
        molecular_weight_kg_kmol=16.0,
        release_height_m=10.0,
        wind_speed_m_s=10.0,
        pasquill_stability_class="A",
        ambient_temperature_k=288.15,
        downwind_distance_m=100.0,
    )
    result = calc_dispersion(inp)
    assert result.centerline_conc_mol_m3 > 0
    assert result.sigma_y_m > 20.0
    assert result.sigma_z_m > 18.0
    assert result.pasquill_stability_used == "A"


# ============================================================================
# 2. Pasquill-Gifford D 类（中性）扩散
# ============================================================================


def test_pasquill_gifford_D_neutral_moderate_wind():
    """Pasquill-Gifford D 类（中性）+ 5 m/s 风 + 2 kg/s C3H8（MW=44）500m 下风向。"""
    inp = DispersionInput(
        gas_release_rate_kg_s=2.0,
        molecular_weight_kg_kmol=44.0,
        release_height_m=5.0,
        wind_speed_m_s=5.0,
        pasquill_stability_class="D",
        ambient_temperature_k=298.15,
        downwind_distance_m=500.0,
    )
    result = calc_dispersion(inp)
    assert result.sigma_y_m > 35.0
    assert result.sigma_z_m > 20.0


# ============================================================================
# 3. 辐射热强度传播（API 521 §5.15 q = Q_comb/(4π·r²)）
# ============================================================================


def test_radiation_heat_intensity_propagation():
    """API 521 §5.15 辐射热强度：q = Q_comb/(4π·r²) 衰减。

    Q_comb = 5 kg/s × 50 MJ/kg = 250 MJ/s = 250e6 W；在 200m 处
    q ≈ 250e6 / (4π·200²) ≈ 497 W/m² ≈ 0.497 kW/m²（远场，远 < 100 kW/m²）。
    """
    inp = DispersionInput(
        gas_release_rate_kg_s=5.0,
        molecular_weight_kg_kmol=16.0,
        release_height_m=20.0,
        wind_speed_m_s=3.0,
        pasquill_stability_class="D",
        ambient_temperature_k=300.0,
        downwind_distance_m=200.0,
    )
    result = calc_dispersion(inp)
    assert result.heat_intensity_kw_m2 > 0
    assert result.heat_intensity_kw_m2 < 100.0  # 远场 < 100 kW/m²


# ============================================================================
# 4. 致死/致伤距离（API 521 §5.15 Table 5-15：4.7 / 12.6 kW/m²）
# ============================================================================


def test_lethality_injury_distance_api521():
    """致死/致伤距离：阈值 4.7 kW/m² 致伤 / 12.6 kW/m² 致死。

    Q_comb = 10 kg/s × 50 MJ/kg = 500e6 W
    r_injury = sqrt(Q/(4π·4.7e3)) ≈ sqrt(500e6/(4π·4700)) ≈ 92.0 m
    r_lethality = sqrt(Q/(4π·12.6e3)) ≈ sqrt(500e6/(4π·12600)) ≈ 56.2 m
    显然 r_lethality < r_injury（lethality 阈值更高 → 距离更近）。
    """
    inp = DispersionInput(
        gas_release_rate_kg_s=10.0,
        molecular_weight_kg_kmol=16.0,
        release_height_m=30.0,
        wind_speed_m_s=5.0,
        pasquill_stability_class="D",
        ambient_temperature_k=298.15,
        downwind_distance_m=100.0,
    )
    result = calc_dispersion(inp)
    assert result.r_injury_m > 0
    assert result.r_lethality_m > 0
    assert result.r_lethality_m < result.r_injury_m


# ============================================================================
# 5. 稳定度越界（F2 boundary）
# ============================================================================


def test_invalid_stability_class_raises():
    """pasquill_stability_class 必须是 A/B/C/D/E/F 之一。"""
    inp = DispersionInput(
        gas_release_rate_kg_s=1.0,
        molecular_weight_kg_kmol=16.0,
        release_height_m=10.0,
        wind_speed_m_s=5.0,
        pasquill_stability_class="X",  # type: ignore[arg-type]
        ambient_temperature_k=288.15,
        downwind_distance_m=100.0,
    )
    with pytest.raises(DispersionInputError):
        calc_dispersion(inp)


# ============================================================================
# 6. 风速越界（F5 extreme values）
# ============================================================================


def test_invalid_wind_speed_raises():
    """风速必须 > 0。"""
    inp = DispersionInput(
        gas_release_rate_kg_s=1.0,
        molecular_weight_kg_kmol=16.0,
        release_height_m=10.0,
        wind_speed_m_s=0.0,
        pasquill_stability_class="D",
        ambient_temperature_k=288.15,
        downwind_distance_m=100.0,
    )
    with pytest.raises(DispersionInputError):
        calc_dispersion(inp)


# ============================================================================
# 7. 数据类契约（frozen dataclass，D7 接口冻结 — batch consistency）
# ============================================================================


def test_dispersion_result_is_frozen():
    """DispersionInput / DispersionResult 字段冻结校验 + formula_ref 必填。

    与 P6-5 batch A1-C2 一致的 frozen pattern：D7 接口冻结保证下游
    persistence 层不会因字段重命名/增删而崩溃。
    """
    in_fields = {f.name for f in fields(DispersionInput)}
    expected_in = {
        "gas_release_rate_kg_s",
        "molecular_weight_kg_kmol",
        "release_height_m",
        "wind_speed_m_s",
        "pasquill_stability_class",
        "ambient_temperature_k",
        "downwind_distance_m",
    }
    assert in_fields == expected_in

    out_fields = {f.name for f in fields(DispersionResult)}
    expected_out = {
        "centerline_conc_mol_m3",
        "sigma_y_m",
        "sigma_z_m",
        "heat_intensity_kw_m2",
        "r_injury_m",
        "r_lethality_m",
        "pasquill_stability_used",
        "formula_ref",
    }
    assert out_fields == expected_out

    # formula_ref 必须非空 dict（必填溯源字段）
    inp = DispersionInput(
        gas_release_rate_kg_s=1.0,
        molecular_weight_kg_kmol=16.0,
        release_height_m=10.0,
        wind_speed_m_s=5.0,
        pasquill_stability_class="D",
        ambient_temperature_k=288.15,
        downwind_distance_m=100.0,
    )
    res = calc_dispersion(inp)
    assert isinstance(res.formula_ref, dict)
    assert len(res.formula_ref) >= 5  # concentration / sigma / radiation / 2 thresholds

    # 冻结：修改触发 FrozenInstanceError
    with pytest.raises(FrozenInstanceError):
        inp.wind_speed_m_s = 20.0  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        res.r_lethality_m = 1.0  # type: ignore[misc]


# ============================================================================
# Golden fixture 一致性（数值基准回归）
# ============================================================================


def test_dispersion_matches_golden_fixture():
    """对照 ``golden_dispersion_ch4.json`` 数值基准（rel=1e-6）。

    防 Briggs 常数漂移 / 公式分母写错（2π vs π）/ 常数单位错等 regression。
    """
    fixture_path = Path(__file__).parent / "fixtures" / "golden_dispersion_ch4.json"
    if not fixture_path.exists():
        pytest.skip("golden_dispersion_ch4.json 尚未生成（task C3 创建）")
    with fixture_path.open() as f:
        cases = json.load(f)

    for case in cases:
        inp = DispersionInput(
            gas_release_rate_kg_s=case["gas_release_rate_kg_s"],
            molecular_weight_kg_kmol=case["molecular_weight_kg_kmol"],
            release_height_m=case["release_height_m"],
            wind_speed_m_s=case["wind_speed_m_s"],
            pasquill_stability_class=case["pasquill_stability_class"],
            ambient_temperature_k=case["ambient_temperature_k"],
            downwind_distance_m=case["downwind_distance_m"],
        )
        res = calc_dispersion(inp)
        for k, v_expected in case["expected"].items():
            v_actual = getattr(res, k)
            assert v_actual == pytest.approx(v_expected, rel=1e-6), (
                f"golden mismatch case {case['name']}.{k}: "
                f"actual={v_actual} expected={v_expected}"
            )


# ============================================================================
# PcsError code/status 校验（与 flare_tip / kod_sizing 一致）
# ============================================================================


def test_dispersion_input_error_inherits_pcs_error():
    """DispersionInputError 继承 PcsError，code=DISPERSION_INPUT_ERROR, status=422。"""
    assert issubclass(DispersionInputError, PcsError)
    assert DispersionInputError.code == "DISPERSION_INPUT_ERROR"
    assert DispersionInputError.status == 422