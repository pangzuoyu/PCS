"""P4-TASK0 physical_semantics 单测：Quantity / SI base / 单位换算 / 维度算术。

自实现最小集，不引入 chemicals/pint 等新依赖。
"""
from __future__ import annotations

import math

import pytest

from app.services.physical_semantics import (
    Dimension,
    DimensionMismatchError,
    Quantity,
    UnitConversionError,
    convert,
    si_base_dimensions,
)

# ============================================================================
# 1. SI base dimensions
# ============================================================================


def test_si_base_dimensions_completeness() -> None:
    """SI 7 个基本量纲齐备（length/mass/time/temperature/current/mol/luminosity）。"""
    base = si_base_dimensions()
    assert set(base) >= {
        "length",
        "mass",
        "time",
        "temperature",
        "current",
        "amount",
        "luminosity",
    }
    # 单位制：长度米 / 质量千克 / 时间秒
    assert base["length"] == ("m", 1)
    assert base["mass"] == ("kg", 1)
    assert base["time"] == ("s", 1)


def test_dimension_parse_and_str() -> None:
    """Dimension 解析与格式化：维度幂可正可负可零。"""
    d = Dimension.parse("m^2*kg*s^-2")  # 能量量纲
    assert d["m"] == 2
    assert d["kg"] == 1
    assert d["s"] == -2
    s = str(d)
    # 排序：m, kg, s
    assert s == "m^2*kg*s^-2"


# ============================================================================
# 2. 单位换算
# ============================================================================


def test_convert_pressure_pa_to_bar() -> None:
    """Pa ↔ bar 换算：1 bar = 1e5 Pa。"""
    q_pa = Quantity(2e5, Dimension.parse("kg*m^-1*s^-2"))  # Pa
    q_bar = convert(q_pa, "bar")
    assert math.isclose(q_bar.value, 2.0, rel_tol=1e-9)
    assert q_bar.dimension == q_pa.dimension


def test_convert_volume_flow_m3s_to_lmin() -> None:
    """m³/s ↔ L/min 换算：1 m³/s = 60000 L/min。"""
    q = Quantity(1.0, Dimension.parse("m^3*s^-1"))
    q2 = convert(q, "L/min")
    assert math.isclose(q2.value, 60000.0, rel_tol=1e-9)


def test_convert_temperature_k_to_celsius() -> None:
    """K ↔ °C 换算：仿射变换（offset），非纯比例。

    反向（°C → K）需显式 source_unit（量纲 string 不携带单位，逆向时无法
    区分 q.value 是 K 还是 °C；显式声明避免歧义）。
    """
    q_k = Quantity(373.15, Dimension.parse("K"))
    q_c = convert(q_k, "°C")
    assert math.isclose(q_c.value, 100.0, abs_tol=1e-9)
    q_back = convert(q_c, "K", source_unit="°C")
    assert math.isclose(q_back.value, 373.15, abs_tol=1e-9)


def test_convert_unknown_unit_raises() -> None:
    """未知单位 → UnitConversionError。"""
    q = Quantity(1.0, Dimension.parse("m"))
    with pytest.raises(UnitConversionError):
        convert(q, "furlong")


# ============================================================================
# 3. 维度算术
# ============================================================================


def test_add_same_dimension_ok() -> None:
    """同维度加法：数值相加，维度不变。"""
    a = Quantity(1.0, Dimension.parse("m"))
    b = Quantity(2.0, Dimension.parse("m"))
    c = a + b
    assert math.isclose(c.value, 3.0)
    assert c.dimension == a.dimension


def test_add_different_dimension_raises() -> None:
    """异维度相加 → DimensionMismatchError。"""
    a = Quantity(1.0, Dimension.parse("m"))
    b = Quantity(1.0, Dimension.parse("kg"))
    with pytest.raises(DimensionMismatchError):
        _ = a + b


def test_subtract_different_dimension_raises() -> None:
    """异维度相减 → DimensionMismatchError。"""
    a = Quantity(1.0, Dimension.parse("m"))
    b = Quantity(1.0, Dimension.parse("s"))
    with pytest.raises(DimensionMismatchError):
        _ = a - b


def test_multiply_dimension_adds() -> None:
    """乘法维度指数相加：m * m = m^2。"""
    a = Quantity(2.0, Dimension.parse("m"))
    b = Quantity(3.0, Dimension.parse("m"))
    c = a * b
    assert math.isclose(c.value, 6.0)
    assert c.dimension["m"] == 2


def test_divide_dimension_subtracts() -> None:
    """除法维度指数相减：m / s = m*s^-1（速度量纲）。"""
    a = Quantity(10.0, Dimension.parse("m"))
    b = Quantity(2.0, Dimension.parse("s"))
    c = a / b
    assert math.isclose(c.value, 5.0)
    assert c.dimension["m"] == 1
    assert c.dimension["s"] == -1
