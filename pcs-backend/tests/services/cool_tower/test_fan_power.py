"""P6-2 Task 25 COOL_TOWER fan_power 测试（§3.2.4.6）。

按 SPEC §3.2.4.6 CTI 1492 经验值：
    P_fan_kw = Q_air × Δp_total / (η_fan × η_motor × 1000)

设计要点：
- 单元测试用纯函数（无 DB 依赖）；覆盖 basic / scaling / efficiency /
  validation / formula_ref。
- 手算校核（Q=10/Δp=200/η_fan=0.7/η_motor=0.9）→ 3.174603... kW。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.cool_tower import (  # noqa: E402
    FanPowerInput,
    FanPowerInputError,
    calc_fan_power,
)

# ============================================================================
# 1. basic — 手算校核（Q=10/Δp=200/η_fan=0.7/η_motor=0.9）
# ============================================================================


def test_fan_power_basic() -> None:
    """P_fan = 10×200/(0.7×0.9×1000) = 3.1746031746... ≈ 3.1746 kW。

    手算：P_fan_kw = 10 × 200 / (0.7 × 0.9 × 1000)
                  = 2000 / 630
                  = 3.1746031746...
    """
    r = calc_fan_power(
        FanPowerInput(
            q_air_m3_s=10.0,
            delta_p_total_pa=200.0,
            fan_efficiency=0.7,
            motor_efficiency=0.9,
        )
    )
    assert r.p_fan_kw == pytest.approx(3.1746031746, abs=1e-6)
    assert r.formula_ref == "API_521_§3.2.4.6"


# ============================================================================
# 2. scaling — Q 翻倍 → P_fan 翻倍（正比）
# ============================================================================


def test_fan_power_scaling() -> None:
    """Q 翻倍（10 → 20）→ P_fan 翻倍（≈6.349 kW）。"""
    base = calc_fan_power(
        FanPowerInput(
            q_air_m3_s=10.0,
            delta_p_total_pa=200.0,
            fan_efficiency=0.7,
            motor_efficiency=0.9,
        )
    )
    doubled = calc_fan_power(
        FanPowerInput(
            q_air_m3_s=20.0,
            delta_p_total_pa=200.0,
            fan_efficiency=0.7,
            motor_efficiency=0.9,
        )
    )
    assert doubled.p_fan_kw == pytest.approx(base.p_fan_kw * 2.0, abs=1e-6)


# ============================================================================
# 3. efficiency_scaling — η_fan 0.7→0.8 → P_fan 缩 0.875
# ============================================================================


def test_fan_power_efficiency_scaling() -> None:
    """η_fan 0.7 → 0.8 → P_fan 缩 (0.7/0.8) = 0.875。"""
    p_07 = calc_fan_power(
        FanPowerInput(
            q_air_m3_s=10.0,
            delta_p_total_pa=200.0,
            fan_efficiency=0.7,
            motor_efficiency=0.9,
        )
    ).p_fan_kw
    p_08 = calc_fan_power(
        FanPowerInput(
            q_air_m3_s=10.0,
            delta_p_total_pa=200.0,
            fan_efficiency=0.8,
            motor_efficiency=0.9,
        )
    ).p_fan_kw
    assert p_08 == pytest.approx(p_07 * 0.875, abs=1e-6)


# ============================================================================
# 4. input_validation — 4 类非法输入
# ============================================================================


def test_fan_power_input_validation_q_air_zero() -> None:
    """q_air_m3_s = 0 → FanPowerInputError。"""
    with pytest.raises(FanPowerInputError) as exc_info:
        calc_fan_power(
            FanPowerInput(
                q_air_m3_s=0.0,
                delta_p_total_pa=200.0,
                fan_efficiency=0.7,
                motor_efficiency=0.9,
            )
        )
    assert "q_air_m3_s" in str(exc_info.value)


def test_fan_power_input_validation_delta_p_zero() -> None:
    """delta_p_total_pa = 0 → FanPowerInputError。"""
    with pytest.raises(FanPowerInputError) as exc_info:
        calc_fan_power(
            FanPowerInput(
                q_air_m3_s=10.0,
                delta_p_total_pa=0.0,
                fan_efficiency=0.7,
                motor_efficiency=0.9,
            )
        )
    assert "delta_p_total_pa" in str(exc_info.value)


def test_fan_power_input_validation_fan_eff_out_of_range() -> None:
    """fan_efficiency = 1.5 (>1) → FanPowerInputError。"""
    with pytest.raises(FanPowerInputError) as exc_info:
        calc_fan_power(
            FanPowerInput(
                q_air_m3_s=10.0,
                delta_p_total_pa=200.0,
                fan_efficiency=1.5,
                motor_efficiency=0.9,
            )
        )
    assert "fan_efficiency" in str(exc_info.value)


def test_fan_power_input_validation_motor_eff_out_of_range() -> None:
    """motor_efficiency = 0.0 → FanPowerInputError。"""
    with pytest.raises(FanPowerInputError) as exc_info:
        calc_fan_power(
            FanPowerInput(
                q_air_m3_s=10.0,
                delta_p_total_pa=200.0,
                fan_efficiency=0.7,
                motor_efficiency=0.0,
            )
        )
    assert "motor_efficiency" in str(exc_info.value)


# ============================================================================
# 5. formula_ref — 恒等 "API_521_§3.2.4.6"
# ============================================================================


def test_fan_power_formula_ref() -> None:
    """formula_ref 恒等 "API_521_§3.2.4.6"（§3.2.4.6 章节号精确匹配）。"""
    r = calc_fan_power(
        FanPowerInput(
            q_air_m3_s=10.0,
            delta_p_total_pa=200.0,
            fan_efficiency=0.7,
            motor_efficiency=0.9,
        )
    )
    assert r.formula_ref == "API_521_§3.2.4.6"