"""P6-3 Task 33 FILTRATION ruth_constant_rate 测试（§3.2.7 第二项）。

按 SPEC §3.2.7 Ruth 恒速过滤方程：

    V = Q · t
    R_total = α · c₀ · V / A + Rm
    ΔP = μ · Q · R_total / A²

手算独立校核（3 例，体现本模块 docstring）：

例 1（Q=1e-3/A=1/μ=1e-3/α=1e10/c₀=10/Rm=1e10/t=3600）：

    V = 1e-3 · 3600 = 3.6 m³
    R_total = 1e10 · 10 · 3.6 / 1 + 1e10 = 3.6e11 + 1e10 = 3.7e11 1/m
    ΔP = 1e-3 · 1e-3 · 3.7e11 / 1 = 3.7e5 Pa

例 2（α=0/c₀=0 无饼）：

    R_total = 0 + Rm = Rm = 1e10 1/m
    ΔP = 1e-3 · 1e-3 · 1e10 / 1 = 1e4 Pa（仅介质阻力）

例 3（t=1800 → t=3600）：

    V 翻倍 → R_total 翻倍（α · c₀ · V / A 项主导） → ΔP 近似翻倍

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
    RuthConstantRateInput,
    RuthConstantRateInputError,
    calc_ruth_constant_rate,
)

# ============================================================================
# 1. 例 1 手算校核（Q=1e-3/A=1/μ=1e-3/α=1e10/c₀=10/Rm=1e10/t=3600 → V=3.6, ΔP=3.7e5）
# ============================================================================


def test_ruth_const_rate_basic() -> None:
    """Q=1e-3/A=1/μ=1e-3/α=1e10/c₀=10/Rm=1e10/t=3600 → V=3.6, ΔP=3.7e5（手算）。

    手算：V = 3.6 m³
        R_total = 3.6e11 + 1e10 = 3.7e11 1/m
        ΔP = 1e-3 · 1e-3 · 3.7e11 = 3.7e5 Pa
    """
    r = calc_ruth_constant_rate(
        RuthConstantRateInput(
            constant_flow_rate=1e-3,
            filtration_area=1.0,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=1e10,
            solid_concentration=10.0,
            medium_resistance=1e10,
            filtration_time=3600.0,
        )
    )
    # V = 3.6
    assert r.cumulative_volume == pytest.approx(3.6, rel=1e-9)
    # R_total = 3.7e11
    assert r.resistance_total == pytest.approx(3.7e11, rel=1e-9)
    # ΔP = 3.7e5
    assert r.instantaneous_pressure_drop == pytest.approx(3.7e5, rel=1e-9)
    assert r.formula_ref == "RUTH_CONST_RATE_§3.2.7"


# ============================================================================
# 2. 例 2 无饼路径（α=0/c₀=0 → R_total = Rm）
# ============================================================================


def test_ruth_const_rate_no_cake() -> None:
    """α=0/c₀=0 → R_total = Rm；ΔP 仅由介质阻力贡献。

    手算：R_total = 0 + 1e10 = 1e10 1/m
        ΔP = 1e-3 · 1e-3 · 1e10 / 1 = 1e4 Pa
    """
    r = calc_ruth_constant_rate(
        RuthConstantRateInput(
            constant_flow_rate=1e-3,
            filtration_area=1.0,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=0.0,
            solid_concentration=0.0,
            medium_resistance=1e10,
            filtration_time=3600.0,
        )
    )
    assert r.resistance_total == pytest.approx(1e10, rel=1e-9)
    assert r.instantaneous_pressure_drop == pytest.approx(1e4, rel=1e-9)
    # 无饼路径下 R_total 严格等于 Rm
    assert r.resistance_total == pytest.approx(1e10, abs=1e-3)


# ============================================================================
# 3. 例 3 单调性（t 翻倍 → ΔP 近似翻倍，因 V 与 R_total 线性）
# ============================================================================


def test_ruth_const_rate_pressure_growth() -> None:
    """t=1800 → t=3600：ΔP 近似翻倍（验证单调性 + 线性）。

    手算：t=1800 时 V=1.8；R_total = 1.8e11 + 1e10 = 1.9e11
        ΔP_1800 = 1e-3 · 1e-3 · 1.9e11 = 1.9e5 Pa
        ΔP_3600 = 3.7e5 Pa
        比值 ≈ 3.7/1.9 ≈ 1.947（接近 2，偏差由 Rm 项导致）
    """
    base_kwargs = dict(
        constant_flow_rate=1e-3,
        filtration_area=1.0,
        filtrate_viscosity=1e-3,
        cake_specific_resistance=1e10,
        solid_concentration=10.0,
        medium_resistance=1e10,
    )
    r1 = calc_ruth_constant_rate(
        RuthConstantRateInput(**base_kwargs, filtration_time=1800.0)
    )
    r2 = calc_ruth_constant_rate(
        RuthConstantRateInput(**base_kwargs, filtration_time=3600.0)
    )
    # ΔP 单调递增
    assert r2.instantaneous_pressure_drop > r1.instantaneous_pressure_drop
    # R_total 单调递增
    assert r2.resistance_total > r1.resistance_total
    # Rm 项主导下 V 翻倍 → R_total 近似翻倍（cake 项 vs medium 项）
    # t=1800: R_total = 1.8e11 + 1e10 = 1.9e11
    # t=3600: R_total = 3.6e11 + 1e10 = 3.7e11
    assert r1.resistance_total == pytest.approx(1.9e11, rel=1e-9)
    assert r2.resistance_total == pytest.approx(3.7e11, rel=1e-9)
    # ΔP 比值 ≈ 1.947
    ratio = r2.instantaneous_pressure_drop / r1.instantaneous_pressure_drop
    assert ratio == pytest.approx(3.7e5 / 1.9e5, rel=1e-3)


# ============================================================================
# 4. 输入校验 — Q=0 → RuthConstantRateInputError
# ============================================================================


def test_ruth_const_rate_input_error_zero_flow() -> None:
    """Q=0 → RuthConstantRateInputError（422）。"""
    with pytest.raises(RuthConstantRateInputError) as exc_info:
        calc_ruth_constant_rate(
            RuthConstantRateInput(
                constant_flow_rate=0.0,
                filtration_area=1.0,
                filtrate_viscosity=1e-3,
                cake_specific_resistance=1e10,
                solid_concentration=10.0,
                medium_resistance=1e10,
                filtration_time=3600.0,
            )
        )
    assert "constant_flow_rate" in str(exc_info.value)


def test_ruth_const_rate_input_error_negative_time() -> None:
    """t=-1 → RuthConstantRateInputError（422）。"""
    with pytest.raises(RuthConstantRateInputError) as exc_info:
        calc_ruth_constant_rate(
            RuthConstantRateInput(
                constant_flow_rate=1e-3,
                filtration_area=1.0,
                filtrate_viscosity=1e-3,
                cake_specific_resistance=1e10,
                solid_concentration=10.0,
                medium_resistance=1e10,
                filtration_time=-1.0,
            )
        )
    assert "filtration_time" in str(exc_info.value)


def test_ruth_const_rate_input_error_zero_area() -> None:
    """A=0 → RuthConstantRateInputError（422）。"""
    with pytest.raises(RuthConstantRateInputError) as exc_info:
        calc_ruth_constant_rate(
            RuthConstantRateInput(
                constant_flow_rate=1e-3,
                filtration_area=0.0,
                filtrate_viscosity=1e-3,
                cake_specific_resistance=1e10,
                solid_concentration=10.0,
                medium_resistance=1e10,
                filtration_time=3600.0,
            )
        )
    assert "filtration_area" in str(exc_info.value)


# ============================================================================
# 5. t=0 边界 — V=0, ΔP 仅由 Rm 贡献（无滤饼）
# ============================================================================


def test_ruth_const_rate_zero_time() -> None:
    """t=0 → V=0；R_total = Rm；ΔP = μ · Q · Rm / A²。"""
    r = calc_ruth_constant_rate(
        RuthConstantRateInput(
            constant_flow_rate=1e-3,
            filtration_area=1.0,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=1e10,
            solid_concentration=10.0,
            medium_resistance=1e10,
            filtration_time=0.0,
        )
    )
    assert r.cumulative_volume == pytest.approx(0.0, abs=1e-12)
    # t=0 时 cake 项 = 0，仅 Rm 贡献
    assert r.resistance_total == pytest.approx(1e10, rel=1e-9)
    assert r.instantaneous_pressure_drop == pytest.approx(1e4, rel=1e-9)


# ============================================================================
# 6. formula_ref 字面常量统一
# ============================================================================


def test_ruth_const_rate_formula_ref() -> None:
    """formula_ref 必须恒等于 "RUTH_CONST_RATE_§3.2.7"（Task 33 红线 #12）。"""
    r = calc_ruth_constant_rate(
        RuthConstantRateInput(
            constant_flow_rate=1e-3,
            filtration_area=1.0,
            filtrate_viscosity=1e-3,
            cake_specific_resistance=1e10,
            solid_concentration=10.0,
            medium_resistance=1e10,
            filtration_time=3600.0,
        )
    )
    assert r.formula_ref == "RUTH_CONST_RATE_§3.2.7"