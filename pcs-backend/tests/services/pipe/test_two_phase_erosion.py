"""P6-5+C-03 TwoPhaseErosionService 单元测试。

覆盖：
1. 单相退化：ρ=999 kg/m³，C=100 → Ve = 100/√999 ≈ 3.16 m/s（Step 1 RED→GREEN）
2. 两相加权退化：ρ_mix = 0.5·ρ_L + 0.5·ρ_V = 525 kg/m³，Ve = 122/√525
3. Imperial 双单位对账：imperial_units=True 时 v_e_ft_s = v_e_m_s / 0.3048

Golden 溯源：
- V_e = C / √ρ_mix（API 14E 5th Ed §4.3.2 Eq.4）
- C 因子（SPEC §3.2.1 V1.8 表 3.2.1）：CONTINUOUS=122 / INTERMITTENT=152.5
  / CORROSIVE_CONTINUOUS=200 / CORROSIVE_INTERMITTENT=305
- Imperial：v_e_ft_s = v_e_m_s / 0.3048

X-1 v5 BLOCKER（must follow）：service_type 是必填字段（无默认值），
显式传 "CONTINUOUS" 等。
"""
from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.pipe.two_phase_erosion import (
    Api14eErosionInput,
    Api14eErosionInputError,
    calc_api14e_erosion_velocity,
)

# ---------------------------------------------------------------------------
# Golden fixture 加载（参考数据；非测试断言硬依赖）
# ---------------------------------------------------------------------------


_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_api14e_erosion.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1) 单相退化（Step 1 RED→GREEN：必填 service_type 显式传值）
# ---------------------------------------------------------------------------


def test_api14e_erosion_single_phase_water():
    """单相水 ρ=999 kg/m³，C=100 → Ve = 100/√999 ≈ 3.164 m/s。

    X-1 v5：service_type 必填显式传值（覆盖 C 默认 122）。
    """
    inp = Api14eErosionInput(
        rho_mix_kg_m3=999.0,
        service_type="CONTINUOUS",  # X-1 v5：必填字段显式传值（c_factor 100 覆盖默认 122）
        c_factor=100.0,
        mass_flow_kg_s=10.0,
        pipe_diameter_m=0.1,
        imperial_units=False,
    )
    result = calc_api14e_erosion_velocity(inp)
    assert math.isclose(result.v_e_m_s, 3.164, rel_tol=1e-2)


# ---------------------------------------------------------------------------
# 2) 两相加权退化（Step 5）
# ---------------------------------------------------------------------------


def test_api14e_erosion_two_phase_mix():
    """两相 ρ_mix = 0.5·ρ_L + 0.5·ρ_V = 0.5·1000 + 0.5·50 = 525，
    Ve = 122/√525（C 默认 CONTINUOUS=122）。

    仅传必填字段；其余走默认。
    """
    inp = Api14eErosionInput(
        rho_mix_kg_m3=525.0,
        service_type="CONTINUOUS",
        mass_flow_kg_s=10.0,
        pipe_diameter_m=0.1,
    )
    result = calc_api14e_erosion_velocity(inp)
    assert math.isclose(result.v_e_m_s, 122.0 / math.sqrt(525), rel_tol=1e-3)


# ---------------------------------------------------------------------------
# 3) Imperial 双单位对账（Step 5 + Review Fix 3/4：golden 数值 + actual_v_ft_s）
# ---------------------------------------------------------------------------


def test_api14e_erosion_imperial_units():
    """imperial_units=True 时 v_e_ft_s + actual_v_ft_s 必须命中 golden 数值。

    ρ=999, C=122（C 默认 CONTINUOUS）：
    - V_e = 122/√999 ≈ 3.8604 m/s
    - actual_v = 10 / (999 · π·0.1²/4) ≈ 1.2732 m/s
    - V_e_ft_s = 3.8604 / 0.3048 ≈ 12.6647 ft/s
    - actual_v_ft_s = 1.2732 / 0.3048 ≈ 4.1765 ft/s
    """
    inp = Api14eErosionInput(
        rho_mix_kg_m3=999.0,
        service_type="CONTINUOUS",
        mass_flow_kg_s=10.0,
        pipe_diameter_m=0.1,
        imperial_units=True,
    )
    result = calc_api14e_erosion_velocity(inp)
    assert result.imperial_conversion is not None
    # golden numeric values（pin literal 1/0.3048 + V_e + actual_v）
    expected_v_e_m_s = 122.0 / math.sqrt(999.0)
    expected_v_actual_m_s = 10.0 / (999.0 * math.pi * 0.1**2 / 4.0)
    assert math.isclose(result.v_e_m_s, expected_v_e_m_s, rel_tol=1e-9)
    assert math.isclose(result.actual_v_m_s, expected_v_actual_m_s, rel_tol=1e-9)
    assert math.isclose(
        result.imperial_conversion["v_e_ft_s"],
        expected_v_e_m_s / 0.3048,
        rel_tol=1e-9,
    )
    assert math.isclose(
        result.imperial_conversion["actual_v_ft_s"],
        expected_v_actual_m_s / 0.3048,
        rel_tol=1e-9,
    )


# ---------------------------------------------------------------------------
# 4) 输入校验（F5：极端值 ρ_mix ≤ 0）
# ---------------------------------------------------------------------------


def test_api14e_erosion_rho_mix_zero_raises():
    """ρ_mix=0 必须 raise Api14eErosionInputError（F5 极端值）。"""
    inp = Api14eErosionInput(
        rho_mix_kg_m3=0.0,
        service_type="CONTINUOUS",
    )
    with pytest.raises(Api14eErosionInputError) as exc:
        calc_api14e_erosion_velocity(inp)
    assert exc.value.code == "API14E_EROSION_INPUT_ERROR"
    assert exc.value.status == 422


# ---------------------------------------------------------------------------
# 5) 不可变结果（frozen dataclass）
# ---------------------------------------------------------------------------


def test_api14e_erosion_result_is_frozen():
    """Api14eErosionResult 必须 frozen（frozen=True）；不允许修改。"""
    inp = Api14eErosionInput(
        rho_mix_kg_m3=999.0,
        service_type="CONTINUOUS",
    )
    result = calc_api14e_erosion_velocity(inp)
    with pytest.raises(FrozenInstanceError):
        result.v_e_m_s = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 6) is_erosion_safe True 判定（actual_v < V_e）
# ---------------------------------------------------------------------------


def test_api14e_erosion_is_safe_when_actual_below_limit():
    """actual_v < V_e 时 is_erosion_safe=True。

    用单相水 ρ=999 + C=122（默认 CONTINUOUS）：
    - V_e = 122/√999 ≈ 3.86 m/s
    - actual_v = 10 / (999 · π·0.1²/4) ≈ 1.27 m/s（远低于 V_e → safe）
    """
    inp = Api14eErosionInput(
        rho_mix_kg_m3=999.0,
        service_type="CONTINUOUS",
        mass_flow_kg_s=10.0,
        pipe_diameter_m=0.1,
    )
    result = calc_api14e_erosion_velocity(inp)
    assert result.is_erosion_safe is True


# ---------------------------------------------------------------------------
# 7) is_erosion_safe False 判定（Review Fix 1：实际流速超过 V_e）
# ---------------------------------------------------------------------------


def test_api14e_erosion_is_unsafe_when_actual_above_limit():
    """actual_v > V_e 时 is_erosion_safe=False（Review Fix 1）。

    ρ=999, C=122, D=0.1 m, mass_flow=200 kg/s：
    - V_e = 122/√999 ≈ 3.86 m/s
    - actual_v = 200 / (999 · π·0.1²/4) ≈ 25.49 m/s（远超 V_e → unsafe）
    - actual_v_ft_s = 25.49 / 0.3048 ≈ 83.63 ft/s（imperial 对账）
    """
    inp = Api14eErosionInput(
        rho_mix_kg_m3=999.0,
        service_type="CONTINUOUS",
        mass_flow_kg_s=200.0,
        pipe_diameter_m=0.1,
        imperial_units=True,
    )
    result = calc_api14e_erosion_velocity(inp)
    assert result.is_erosion_safe is False
    # actual_v_ft_s symmetry 验证（与 v_e_ft_s 对账同口径）
    assert result.imperial_conversion is not None
    expected_actual_v_m_s = 200.0 / (999.0 * math.pi * 0.1**2 / 4.0)
    assert math.isclose(
        result.imperial_conversion["actual_v_ft_s"],
        expected_actual_v_m_s / 0.3048,
        rel_tol=1e-9,
    )


# ---------------------------------------------------------------------------
# 8) C 因子范围校验（Review Fix 2：c_factor 越界 → raise）
# ---------------------------------------------------------------------------


def test_api14e_erosion_c_factor_out_of_range_raises():
    """c_factor=999.0 越界（API 14E 范围 50~400）必须 raise Api14eErosionInputError。"""
    inp = Api14eErosionInput(
        rho_mix_kg_m3=999.0,
        service_type="CONTINUOUS",
        c_factor=999.0,
    )
    with pytest.raises(Api14eErosionInputError) as exc:
        calc_api14e_erosion_velocity(inp)
    assert exc.value.code == "API14E_EROSION_INPUT_ERROR"
    assert exc.value.status == 422


# ---------------------------------------------------------------------------
# 9) formula_ref 存在 + 非空（review focus：spec 溯源）
# ---------------------------------------------------------------------------


def test_api14e_erosion_formula_ref_keys():
    """formula_ref 必须含 erosion_velocity + c_factor_by_service 两个键。"""
    inp = Api14eErosionInput(
        rho_mix_kg_m3=999.0,
        service_type="CONTINUOUS",
    )
    result = calc_api14e_erosion_velocity(inp)
    assert "erosion_velocity" in result.formula_ref
    assert "c_factor_by_service" in result.formula_ref
    assert "API 14E" in result.formula_ref["erosion_velocity"]
