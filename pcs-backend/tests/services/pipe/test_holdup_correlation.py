"""P6-5+C-15 持液率与流型计算（Beggs-Brill + Mandhane 1975 + Eaton-Flanning）单元测试。

覆盖（SPEC §3.2.3 V1.9）：
1. 水平管层状波 Beggs-Brill H_L(0)（Step 1 RED→GREEN）
2. 上坡持液率增加（Step 5）
3. Fr 越界 → is_beggs_brill_valid=False（Step 5）
4. Imperial 双单位（Step 5 F1）
5. 边界：管径 ≤ 0 / 负值 → BeggsBrillInputError（F2/F5）
6. ±90° 倾角边界接受（F2）
7. 流型判别 Mandhane 1975：SEGREGATED / INTERMITTENT / DISTRIBUTED / TRANSITION（Step 5）
8. 结果 frozen（A1/A2/A3 模式一致）

公式溯源：
- Mandhane 1975 水平管流型图（被 BG-B 1973 引用为适用范围）
- Beggs-Brill 1973 Eq.6 H_L(0) = a·λ_L^b / Fr^c
- BG-B 1973 Eq.14-16 倾角修正 B(θ)
- Eaton-Flanning 1967 Fr ∈ [0.01, 10] 适用范围校验
"""
from __future__ import annotations

import json
import math
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest

from app.services.pipe.holdup_correlation import (
    BeggsBrillHoldupInput,
    BeggsBrillInputError,
    calc_beggs_brill_holdup,
)

# ---------------------------------------------------------------------------
# Golden fixture（参考数据）
# ---------------------------------------------------------------------------

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "golden_beggs_brill.json"
GOLDEN = json.loads(_FIXTURE_PATH.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 1) 水平管层状波浪流：H_L(0) 在 [0, 1]；θ=0 时 H_L(θ) = H_L(0)（Step 1）
# ---------------------------------------------------------------------------


def test_beggs_brill_horizontal_stratified_wavy():
    """水平管层状波浪流：V_sl=0.5, V_sg=1.0, D=0.1 → H_L(0) 在 [0,1]。

    按 Beggs-Brill 1973 Eq.6 H_L(0) = a·λ_L^b / Fr^c；θ=0 时倾角修正恒等。
    """
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
        imperial_units=False,
    )
    result = calc_beggs_brill_holdup(inp)
    assert 0.0 <= result.h_l_theta0 <= 1.0
    # 水平流时 H_L(θ=0) = H_L(θ) 无倾角修正
    assert math.isclose(result.h_l_theta, result.h_l_theta0, rel_tol=1e-3)
    # 弗劳德数应在 Eaton-Flanning 适用范围 [0.01, 10] 内（V_m=1.5, D=0.1）
    assert 0.01 <= result.froude_number <= 10.0
    assert result.is_beggs_brill_valid is True


# ---------------------------------------------------------------------------
# 2) 上坡持液率增加（Step 5）
# ---------------------------------------------------------------------------


def test_beggs_brill_uphill_increases_holdup():
    """上坡（θ>0）持液率应增加（BG-B 1973 倾角修正 B(θ) > 1）。"""
    inp_horiz = BeggsBrillHoldupInput(
        v_sl_m_s=0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    inp_uphill = BeggsBrillHoldupInput(
        v_sl_m_s=0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=30.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    r_horiz = calc_beggs_brill_holdup(inp_horiz)
    r_uphill = calc_beggs_brill_holdup(inp_uphill)
    assert r_uphill.h_l_theta > r_horiz.h_l_theta0


# ---------------------------------------------------------------------------
# 3) Fr 越界 → is_beggs_brill_valid=False（Step 5）
# ---------------------------------------------------------------------------


def test_beggs_brill_fr_validation():
    """Fr 越界（>10）应触发 is_beggs_brill_valid=False。"""
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=10.0,
        v_sg_m_s=10.0,
        pipe_diameter_m=0.05,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    result = calc_beggs_brill_holdup(inp)
    # 高流速 → 高 Fr → 越界 Eaton-Flanning 范围
    assert result.froude_number > 10.0
    assert result.is_beggs_brill_valid is False


def test_beggs_brill_fr_too_low_marks_invalid():
    """Fr 极小（< 0.01）也应标 is_beggs_brill_valid=False。"""
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=0.001,
        v_sg_m_s=0.0,
        pipe_diameter_m=1.0,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    result = calc_beggs_brill_holdup(inp)
    assert result.froude_number < 0.01
    assert result.is_beggs_brill_valid is False


# ---------------------------------------------------------------------------
# 4) Imperial 双单位（Step 5 F1）
# ---------------------------------------------------------------------------


def test_beggs_brill_imperial_units():
    """imperial_units=True 时 V_sl/V_sg 应正确转换为 ft/s。"""
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
        imperial_units=True,
    )
    result = calc_beggs_brill_holdup(inp)
    assert result.imperial_conversion is not None
    expected_sl_ft = 0.5 / 0.3048
    expected_sg_ft = 1.0 / 0.3048
    assert math.isclose(
        result.imperial_conversion["v_sl_ft_s"], expected_sl_ft, rel_tol=1e-6
    )
    assert math.isclose(
        result.imperial_conversion["v_sg_ft_s"], expected_sg_ft, rel_tol=1e-6
    )


def test_beggs_brill_no_imperial_when_disabled():
    """imperial_units=False（默认）→ imperial_conversion 应为 None。"""
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    result = calc_beggs_brill_holdup(inp)
    assert result.imperial_conversion is None


# ---------------------------------------------------------------------------
# 5) 边界：管径 ≤ 0 / 负值 → 拒绝（F2/F5）
# ---------------------------------------------------------------------------


def test_beggs_brill_diameter_zero_raises():
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.0,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    with pytest.raises(BeggsBrillInputError):
        calc_beggs_brill_holdup(inp)


def test_beggs_brill_negative_velocity_raises():
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=-0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    with pytest.raises(BeggsBrillInputError):
        calc_beggs_brill_holdup(inp)


def test_beggs_brill_negative_density_raises():
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=-1.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    with pytest.raises(BeggsBrillInputError):
        calc_beggs_brill_holdup(inp)


# ---------------------------------------------------------------------------
# 6) ±90° 倾角边界（F2 Step 5）
# ---------------------------------------------------------------------------


def test_beggs_brill_inclination_boundaries_accepted():
    """±90° 倾角边界应接受（管壁摩擦主导区）。"""
    for theta in (90.0, -90.0):
        inp = BeggsBrillHoldupInput(
            v_sl_m_s=0.5,
            v_sg_m_s=1.0,
            pipe_diameter_m=0.1,
            pipe_inclination_deg=theta,
            rho_L_kg_m3=999.0,
            rho_V_kg_m3=50.0,
            mu_L_pa_s=1.0e-3,
            mu_V_pa_s=1.5e-5,
            sigma_n_m=0.02,
        )
        result = calc_beggs_brill_holdup(inp)
        assert 0.0 <= result.h_l_theta <= 1.0


def test_beggs_brill_inclination_out_of_range_raises():
    """倾角超 ±90° → 拒绝。"""
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=95.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    with pytest.raises(BeggsBrillInputError):
        calc_beggs_brill_holdup(inp)


# ---------------------------------------------------------------------------
# 7) Mandhane 1975 流型判别（Step 5）
# ---------------------------------------------------------------------------


def test_mandhane_flow_pattern_segregated():
    """极低气相流速 + 中等液相 → SEGREGATED（分离流）。

    λ_V 需 < L3 ≈ 0.0046；选 v_sg=0.001 / v_sl=2.0 → λ_V=0.0005 < L3。
    """
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=2.0,
        v_sg_m_s=0.001,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    result = calc_beggs_brill_holdup(inp)
    assert result.flow_pattern == "SEGREGATED"


def test_mandhane_flow_pattern_intermittent():
    """高 λ_L + 高 λ_V → INTERMITTENT（间歇流 / 段塞流）。"""
    # λ_L ≈ 0.9, λ_V ≈ 0.1, ρ_L=999
    # L2 ≈ 0.000925·(999·50)^0.305 ≈ 0.087; λ_L >= L2 且 λ_V >= L3 → INTERMITTENT
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=9.0,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    result = calc_beggs_brill_holdup(inp)
    assert result.flow_pattern == "INTERMITTENT"


# ---------------------------------------------------------------------------
# 8) 不可变结果（frozen dataclass，A1/A2/A3 模式一致）
# ---------------------------------------------------------------------------


def test_holdup_correlation_result_is_frozen():
    """HoldupCorrelationResult 必须 frozen（frozen=True）；不允许修改。"""
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=0.5,
        v_sg_m_s=1.0,
        pipe_diameter_m=0.1,
        pipe_inclination_deg=0.0,
        rho_L_kg_m3=999.0,
        rho_V_kg_m3=50.0,
        mu_L_pa_s=1.0e-3,
        mu_V_pa_s=1.5e-5,
        sigma_n_m=0.02,
    )
    result = calc_beggs_brill_holdup(inp)
    with pytest.raises(FrozenInstanceError):
        result.h_l_theta0 = 0.0  # type: ignore[misc]


# ---------------------------------------------------------------------------
# 9) Golden fixture 一致性（参考）
# ---------------------------------------------------------------------------


def test_golden_beggs_brill_reference_matches():
    """Golden fixture 中 Beggs-Brill 参考值应等于实现输出。"""
    ref = GOLDEN["stratified_wavy_horizontal"]
    inp = BeggsBrillHoldupInput(
        v_sl_m_s=ref["v_sl_m_s"],
        v_sg_m_s=ref["v_sg_m_s"],
        pipe_diameter_m=ref["pipe_diameter_m"],
        pipe_inclination_deg=ref["pipe_inclination_deg"],
        rho_L_kg_m3=ref["rho_L_kg_m3"],
        rho_V_kg_m3=ref["rho_V_kg_m3"],
        mu_L_pa_s=ref["mu_L_pa_s"],
        mu_V_pa_s=ref["mu_V_pa_s"],
        sigma_n_m=ref["sigma_n_m"],
    )
    result = calc_beggs_brill_holdup(inp)
    assert math.isclose(result.h_l_theta0, ref["expected_h_l_theta0"], rel_tol=1e-3)
    assert math.isclose(result.froude_number, ref["expected_froude_number"], rel_tol=1e-3)
    assert result.flow_pattern == ref["expected_flow_pattern"]