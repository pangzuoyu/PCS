"""P6-5+C-05 API 14E 两相流管道尺寸单元测试。

覆盖：
1. 连续水相 ρ_L=999, ρ_V=50, x=0.5 → ρ_mix=524.5, C=100 → Ve=C/√ρ,
   D_min = √(4·m/(π·ρ_mix·V_e))。mass_flow=50 kg/s 时 D≈0.187m（Step 1 RED→GREEN）
2. Turner 1966 临界携液（气相主导 ε=0.9）：V_turner 计算正确（Step 5）
3. 液相主导 ε<0.5 时 v_turner=0, is_safe=True（Step 5）

Golden 溯源：
- D_min = √(4·m/(π·ρ_mix·V_e))（连续性方程 + 冲蚀速度边界）
- V_turner = 5.46·(σ·g·(ρ_L-ρ_V)/ρ_V²)^0.25（Turner 1966；气相主导）
- Imperial：d_in = d_min_m / 0.0254；v_ft_s = v_m_s / 0.3048
"""
from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.pipe.two_phase_sizing import (
    Api14ePipeSizingInput,
    Api14ePipeSizingInputError,
    calc_api14e_pipe_size,
)

# ---------------------------------------------------------------------------
# Golden fixture 加载（参考数据；非测试断言硬依赖）
# ---------------------------------------------------------------------------


_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_api14e_sizing.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1) 连续水相（Step 1 RED→GREEN：直径公式 + Du ≈ Ve）
# ---------------------------------------------------------------------------


def test_api14e_sizing_water_continuous_phase():
    """连续水相 ρ_L=999, ρ_V=50, ε=0.5 → ρ_mix=524.5, C=100 → Ve=C/√ρ。

    mass_flow=50 kg/s 时 D_min = √(4·m/(π·ρ_mix·V_e)) ≈ 0.187m（Step 1 RED→GREEN）。
    """
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=50.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.5,
        c_factor=100.0,
        imperial_units=False,
    )
    result = calc_api14e_pipe_size(inp)
    rho_mix = 0.5 * 999 + 0.5 * 50  # = 524.5
    v_e = 100 / math.sqrt(rho_mix)
    d_expected = math.sqrt(4 * 50 / (math.pi * rho_mix * v_e))
    assert math.isclose(result.d_min_m, d_expected, rel_tol=1e-3)


# ---------------------------------------------------------------------------
# 2) Turner 临界携液（Step 5：气相主导 ε=0.9）
# ---------------------------------------------------------------------------


def test_api14e_sizing_turner_critical_velocity_gas_dominant():
    """气相主导 ε=0.9 时 Turner V_turner 计算正确。

    σ=0.02, g=9.81, ρ_L=999, ρ_V=50：
    V_turner = 5.46·(0.02·9.81·949 / 2500)^0.25。
    """
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=5.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.9,
        c_factor=100.0,
    )
    result = calc_api14e_pipe_size(inp)
    expected_v_turner = 5.46 * (
        0.02 * 9.81 * (999 - 50) / 50**2
    ) ** 0.25
    assert math.isclose(result.v_turner_m_s, expected_v_turner, rel_tol=1e-3)


# ---------------------------------------------------------------------------
# 3) 液相主导无 Turner 校核（Step 5：ε<0.5）
# ---------------------------------------------------------------------------


def test_api14e_sizing_liquid_dominant_no_turner_check():
    """液相主导 ε<0.5 时 v_turner=0, is_safe=True（不适用）。"""
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=50.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.3,
        c_factor=100.0,
    )
    result = calc_api14e_pipe_size(inp)
    assert result.v_turner_m_s == 0.0
    assert result.is_liquid_unloading_safe is True


# ---------------------------------------------------------------------------
# 4) Imperial 双单位对账（F1）
# ---------------------------------------------------------------------------


def test_api14e_sizing_imperial_units():
    """imperial_units=True 时 d_in + v_ft_s 必须命中换算。

    ρ_L=999, ρ_V=50, ε=0.5, C=100, m=50：
    - ρ_mix = 524.5
    - V_e = 100/√524.5 ≈ 4.367 m/s
    - D_min = √(4·50/(π·524.5·4.367)) ≈ 0.1865 m
    - d_in = 0.1865 / 0.0254 ≈ 7.343 in
    - v_e_ft_s = 4.367 / 0.3048 ≈ 14.327 ft/s
    """
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=50.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.5,
        c_factor=100.0,
        imperial_units=True,
    )
    result = calc_api14e_pipe_size(inp)
    assert result.imperial_conversion is not None
    rho_mix = 0.5 * 999 + 0.5 * 50
    expected_v_e = 100.0 / math.sqrt(rho_mix)
    expected_d_min = math.sqrt(4 * 50 / (math.pi * rho_mix * expected_v_e))
    assert math.isclose(result.v_e_m_s, expected_v_e, rel_tol=1e-9)
    assert math.isclose(result.d_min_m, expected_d_min, rel_tol=1e-9)
    assert math.isclose(
        result.imperial_conversion["d_min_in"],
        expected_d_min / 0.0254,
        rel_tol=1e-9,
    )
    assert math.isclose(
        result.imperial_conversion["v_e_ft_s"],
        expected_v_e / 0.3048,
        rel_tol=1e-9,
    )


# ---------------------------------------------------------------------------
# 5) void_fraction 边界（F2：0.0 和 1.0 必须接受）
# ---------------------------------------------------------------------------


def test_api14e_sizing_void_fraction_zero_accepts():
    """void_fraction=0.0（全液相）必须接受。"""
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=50.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.0,
        c_factor=100.0,
    )
    result = calc_api14e_pipe_size(inp)
    assert result.d_min_m > 0


def test_api14e_sizing_void_fraction_one_accepts():
    """void_fraction=1.0（全气相）必须接受。"""
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=5.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=1.0,
        c_factor=100.0,
    )
    result = calc_api14e_pipe_size(inp)
    assert result.d_min_m > 0


def test_api14e_sizing_void_fraction_out_of_range_raises():
    """void_fraction=1.5 越界必须 raise Api14ePipeSizingInputError。"""
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=50.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=1.5,
        c_factor=100.0,
    )
    with pytest.raises(Api14ePipeSizingInputError) as exc:
        calc_api14e_pipe_size(inp)
    assert exc.value.code == "API14E_SIZING_INPUT_ERROR"
    assert exc.value.status == 422


# ---------------------------------------------------------------------------
# 6) 极端值校验（F5：mass_flow ≤ 0、ρ ≤ 0）
# ---------------------------------------------------------------------------


def test_api14e_sizing_mass_flow_zero_raises():
    """mass_flow=0 必须 raise（F5 极端值）。"""
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.5,
        c_factor=100.0,
    )
    with pytest.raises(Api14ePipeSizingInputError) as exc:
        calc_api14e_pipe_size(inp)
    assert exc.value.code == "API14E_SIZING_INPUT_ERROR"
    assert exc.value.status == 422


def test_api14e_sizing_rho_L_zero_raises():
    """ρ_L=0 必须 raise（F5 极端值）。"""
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=50.0,
        rho_L_kg_m3=0.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.5,
        c_factor=100.0,
    )
    with pytest.raises(Api14ePipeSizingInputError):
        calc_api14e_pipe_size(inp)


def test_api14e_sizing_c_factor_out_of_range_raises():
    """C 因子越界（<50 或 >250）必须 raise。"""
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=50.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.5,
        c_factor=999.0,
    )
    with pytest.raises(Api14ePipeSizingInputError):
        calc_api14e_pipe_size(inp)


# ---------------------------------------------------------------------------
# 7) 不可变结果（frozen dataclass）
# ---------------------------------------------------------------------------


def test_api14e_sizing_result_is_frozen():
    """Api14ePipeSizingResult 必须 frozen（frozen=True）；不允许修改。"""
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=50.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.5,
        c_factor=100.0,
    )
    result = calc_api14e_pipe_size(inp)
    with pytest.raises(FrozenInstanceError):
        result.d_min_m = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 8) formula_ref 存在 + 非空（review focus：spec 溯源）
# ---------------------------------------------------------------------------


def test_api14e_sizing_formula_ref_keys():
    """formula_ref 必须含 4 个键：rho_mix + erosion_velocity + pipe_diameter + turner。""
    """
    inp = Api14ePipeSizingInput(
        mass_flow_kg_s=50.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        void_fraction=0.5,
        c_factor=100.0,
    )
    result = calc_api14e_pipe_size(inp)
    for key in (
        "rho_mix",
        "erosion_velocity",
        "pipe_diameter",
        "turner_critical_velocity",
    ):
        assert key in result.formula_ref, f"missing key: {key}"
    assert "API 14E" in result.formula_ref["erosion_velocity"]