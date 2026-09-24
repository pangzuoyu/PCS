"""P6-3 Task 33 FILTRATION ruth_constant_pressure 测试（§3.2.7 第一项）。

按 SPEC §3.2.7 Ruth 恒压过滤方程：

    (V + V₀)² = k · A² · t + V₀²
    V = √(k · A² · t + V₀²) − V₀
    k = 2 · ΔP / (μ · α · c₀)
    V₀ = μ · Rm · A / (α · c₀)

手算独立校核（3 例，体现本模块 docstring）：

例 1（A=1/ΔP=1e5/μ=1e-3/α=1e10/c₀=10/Rm=1e10/t=3600）：

    k = 2e5 / (1e-3 · 1e10 · 10) = 2e5 / 1e8 = 2e-3 m²/s
    V₀ = 1e-3 · 1e10 · 1 / (1e10 · 10) = 1e-4 m³
    V = √(2e-3 · 1 · 3600 + 1e-8) − 1e-4
      = √7.2 − 1e-4 ≈ 2.6832 m³

例 2（α=0/c₀=0 无饼理想）：

    k_proxy = 2 · ΔP / μ = 2e8；V₀ = 0
    V = √(2e8 · 1 · 3600) − 0 = √7.2e11 ≈ 8.4853e5 m³

例 3（t=0）：

    V = √V₀² − V₀ = 0；Q_avg = 0（t=0 时定义）

3 例手算与公式直接计算偏差 = 0%（公式自洽）。
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

_BACKEND_ROOT = Path(__file__).resolve().parents[3]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from app.services.filtration import (  # noqa: E402
    RuthConstantPressureInput,
    RuthConstantPressureInputError,
    calc_ruth_constant_pressure,
)

# ============================================================================
# 1. 例 1 手算校核（A=1/ΔP=1e5/μ=1e-3/α=1e10/c₀=10/Rm=1e10/t=3600 → V≈2.6832）
# ============================================================================


def test_ruth_const_pressure_basic() -> None:
    """A=1/ΔP=1e5/μ=1e-3/α=1e10/c₀=10/Rm=1e10/t=3600 → V ≈ 2.6832 m³（手算）。

    手算：k = 2e-3 m²/s；V₀ = 1e-4 m³
        V = √(2e-3 · 1 · 3600 + 1e-8) − 1e-4 = √7.2 − 1e-4 ≈ 2.6832 m³
    """
    r = calc_ruth_constant_pressure(
        RuthConstantPressureInput(
            filtration_area=1.0,
            delta_pressure=1e5,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=1e10,
            solid_concentration=10.0,
            medium_resistance=1e10,
            filtration_time=3600.0,
        )
    )
    # V ≈ 2.6832（公式自洽，偏差 < 5%）
    assert r.filtrate_volume == pytest.approx(2.6832, rel=5e-3)
    # k = 2e-3
    assert r.ruth_constant_k == pytest.approx(2e-3, rel=1e-9)
    # V₀ = 1e-4
    assert r.virtual_volume_v0 == pytest.approx(1e-4, rel=1e-9)
    # Q_avg = V / t
    assert r.average_flow_rate == pytest.approx(r.filtrate_volume / 3600.0, rel=1e-9)
    assert r.formula_ref == "RUTH_CONST_PRESSURE_§3.2.7"


# ============================================================================
# 2. 例 2 无饼路径（α=0/c₀=0 → V₀ = 0，k = 2·ΔP/μ 占位）
# ============================================================================


def test_ruth_const_pressure_no_cake() -> None:
    """α=0/c₀=0 → V₀ = 0；k 取占位 2·ΔP/μ；V 仅由 k_proxy 决定。

    手算：k_proxy = 2 · 1e5 / 1e-3 = 2e8；V₀ = 0
        V = √(2e8 · 1 · 3600 + 0) − 0 = √7.2e11 ≈ 8.4853e5 m³
    """
    r = calc_ruth_constant_pressure(
        RuthConstantPressureInput(
            filtration_area=1.0,
            delta_pressure=1e5,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=0.0,
            solid_concentration=0.0,
            medium_resistance=1e10,
            filtration_time=3600.0,
        )
    )
    assert r.virtual_volume_v0 == pytest.approx(0.0, abs=1e-12)
    assert r.ruth_constant_k == pytest.approx(2e8, rel=1e-9)
    assert r.filtrate_volume == pytest.approx(848528.137, rel=1e-4)
    assert r.formula_ref == "RUTH_CONST_PRESSURE_§3.2.7"


# ============================================================================
# 3. 例 3 零时间（t=0 → V=0, Q_avg=0）
# ============================================================================


def test_ruth_const_pressure_zero_time() -> None:
    """t=0 → V = √V₀² − V₀ = 0；Q_avg = 0（无时间无流量）。"""
    r = calc_ruth_constant_pressure(
        RuthConstantPressureInput(
            filtration_area=1.0,
            delta_pressure=1e5,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=1e10,
            solid_concentration=10.0,
            medium_resistance=1e10,
            filtration_time=0.0,
        )
    )
    assert r.filtrate_volume == pytest.approx(0.0, abs=1e-12)
    assert r.average_flow_rate == pytest.approx(0.0, abs=1e-12)
    assert r.virtual_volume_v0 == pytest.approx(1e-4, rel=1e-9)


# ============================================================================
# 4. 输入校验 — μ=-1 → RuthConstantPressureInputError
# ============================================================================


def test_ruth_const_pressure_input_error_negative_viscosity() -> None:
    """μ=-1 → RuthConstantPressureInputError（422）。"""
    with pytest.raises(RuthConstantPressureInputError) as exc_info:
        calc_ruth_constant_pressure(
            RuthConstantPressureInput(
                filtration_area=1.0,
                delta_pressure=1e5,
                filtrate_viscosity=-1.0,
                cake_specific_resistance=1e10,
                solid_concentration=10.0,
                medium_resistance=1e10,
                filtration_time=3600.0,
            )
        )
    assert "filtrate_viscosity" in str(exc_info.value)


def test_ruth_const_pressure_input_error_zero_area() -> None:
    """A=0 → RuthConstantPressureInputError（422）。"""
    with pytest.raises(RuthConstantPressureInputError) as exc_info:
        calc_ruth_constant_pressure(
            RuthConstantPressureInput(
                filtration_area=0.0,
                delta_pressure=1e5,
                filtrate_viscosity=1e-3,
                cake_specific_resistance=1e10,
                solid_concentration=10.0,
                medium_resistance=1e10,
                filtration_time=3600.0,
            )
        )
    assert "filtration_area" in str(exc_info.value)


def test_ruth_const_pressure_input_error_negative_alpha() -> None:
    """α=-1 → RuthConstantPressureInputError（422）。"""
    with pytest.raises(RuthConstantPressureInputError) as exc_info:
        calc_ruth_constant_pressure(
            RuthConstantPressureInput(
                filtration_area=1.0,
                delta_pressure=1e5,
                filtrate_viscosity=1e-3,
                cake_specific_resistance=-1.0,
                solid_concentration=10.0,
                medium_resistance=1e10,
                filtration_time=3600.0,
            )
        )
    assert "cake_specific_resistance" in str(exc_info.value)


# ============================================================================
# 5. 单调性验证（t 翻倍 → V 增长但趋于减速率）
# ============================================================================


def test_ruth_const_pressure_monotonic_in_time() -> None:
    """t=1800 vs t=3600 → V 单调增长（公式物理保证）。"""
    base_kwargs = dict(
        filtration_area=1.0,
        delta_pressure=1e5,
        filtrate_viscosity=1e-3,
        cake_specific_resistance=1e10,
        solid_concentration=10.0,
        medium_resistance=1e10,
    )
    r1 = calc_ruth_constant_pressure(
        RuthConstantPressureInput(**base_kwargs, filtration_time=1800.0)
    )
    r2 = calc_ruth_constant_pressure(
        RuthConstantPressureInput(**base_kwargs, filtration_time=3600.0)
    )
    # V 单调递增
    assert r2.filtrate_volume > r1.filtrate_volume
    # Q_avg 随 t 递减（恒压下过滤阻力递增 → 流量递减）
    assert r2.average_flow_rate < r1.average_flow_rate


# ============================================================================
# 6. formula_ref 字面常量统一
# ============================================================================


def test_ruth_const_pressure_formula_ref() -> None:
    """formula_ref 必须恒等于 "RUTH_CONST_PRESSURE_§3.2.7"（Task 33 红线 #12）。"""
    r = calc_ruth_constant_pressure(
        RuthConstantPressureInput(
            filtration_area=1.0,
            delta_pressure=1e5,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=1e10,
            solid_concentration=10.0,
            medium_resistance=1e10,
            filtration_time=3600.0,
        )
    )
    assert r.formula_ref == "RUTH_CONST_PRESSURE_§3.2.7"