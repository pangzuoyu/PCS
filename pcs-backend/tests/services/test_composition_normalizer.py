"""P3.x SIM-31：composition_mass → composition_mole 归一化 + 液相字段。

设计：
- 输入归一化层：`normalize_composition_mass_to_mole(composition_mass, mw_by_component)`
  - 纯数学：mass fraction → mole fraction（mass_i / MW_i → mole_i，sum 归一化）
  - MW 缺失 → 抛 `SIM_COMP_MW_MISSING` 异常
- PropertyAutoCompleter（SIM-26）不变：只接 composition_mole
- 液相字段（SIM-31）：
  - ORM 列：liquid_fraction / specific_gravity（与 vapor_fraction / api_gravity 对称）
  - JSONB：std_liq_density / liquid_mass_rate / liq_actual_m3hr（入 stream_properties_json）
"""
from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# 受测目标
# ---------------------------------------------------------------------------


def _import_normalizer():
    from app.services.composition_normalizer import (
        normalize_composition_mass_to_mole,
        CompositionMassToMoleError,
    )

    return normalize_composition_mass_to_mole, CompositionMassToMoleError


# ---------------------------------------------------------------------------
# 基本换算
# ---------------------------------------------------------------------------


def test_mass_to_mole_simple_benzene_water():
    """苯+水 50:50 质量 → mole ≈ 0.728:0.272（MW 78/18）。"""
    normalize, _ = _import_normalizer()
    # 50 g 苯 (MW=78) + 50 g 水 (MW=18)
    # mole 苯 = 50/78 = 0.641; mole 水 = 50/18 = 2.778
    # sum = 3.419; mole_frac 苯 = 0.1875, 水 = 0.8125
    result = normalize(
        {"71-43-2": 0.5, "7732-18-5": 0.5},
        {"71-43-2": 78.0, "7732-18-5": 18.0},
    )
    assert pytest.approx(result["71-43-2"], abs=1e-3) == 0.1875
    assert pytest.approx(result["7732-18-5"], abs=1e-3) == 0.8125


def test_mass_to_mole_pure_component():
    """纯组分（mass_frac=1.0）→ mole_frac=1.0。"""
    normalize, _ = _import_normalizer()
    result = normalize({"71-43-2": 1.0}, {"71-43-2": 78.0})
    assert result == {"71-43-2": 1.0}


def test_mass_to_mole_sum_to_one():
    """归一化：mole 摩尔分率之和 = 1.0（±1e-9）。"""
    normalize, _ = _import_normalizer()
    result = normalize(
        {"71-43-2": 0.6, "7732-18-5": 0.4},
        {"71-43-2": 78.0, "7732-18-5": 18.0},
    )
    assert pytest.approx(sum(result.values()), abs=1e-9) == 1.0


# ---------------------------------------------------------------------------
# 错误边界
# ---------------------------------------------------------------------------


def test_mass_to_mole_missing_mw_raises():
    """MW 缺失 → 抛 SIM_COMP_MW_MISSING（带 CAS 与缺失 keys 信息）。"""
    normalize, Err = _import_normalizer()
    with pytest.raises(Err) as exc_info:
        normalize(
            {"71-43-2": 0.5, "9999-99-9": 0.5},
            {"71-43-2": 78.0},  # 9999-99-9 缺失
        )
    # 异常信息含缺失 CAS
    msg = str(exc_info.value)
    assert "9999-99-9" in msg
    assert "MW" in msg or "molecular_weight" in msg.lower()


def test_mass_to_mole_negative_fraction_raises():
    """负 mass fraction → 抛 ValueError。"""
    normalize, _ = _import_normalizer()
    with pytest.raises(ValueError):
        normalize(
            {"71-43-2": -0.1, "7732-18-5": 1.1},
            {"71-43-2": 78.0, "7732-18-5": 18.0},
        )


def test_mass_to_mole_zero_mw_raises():
    """MW=0 → 抛 ZeroDivisionError 或 ValueError（避免除零）。"""
    normalize, _ = _import_normalizer()
    with pytest.raises((ValueError, ZeroDivisionError)):
        normalize(
            {"71-43-2": 0.5},
            {"71-43-2": 0.0},
        )


def test_mass_to_mole_empty_input_returns_empty():
    """空输入 → 空 dict（不抛）。"""
    normalize, _ = _import_normalizer()
    assert normalize({}, {}) == {}


# ---------------------------------------------------------------------------
# 液相 ORM 字段：SIM-31 + SIM-33 共 5 个 ORM 字段
# ---------------------------------------------------------------------------


def test_liquid_fraction_in_orm_stream():
    """liquid_fraction 写入 ORM Stream 后可读出（SIM-31 migration 已加列）。"""
    from app.models.project import Stream

    s = Stream()
    s.liquid_fraction = 0.3
    assert s.liquid_fraction == 0.3


def test_specific_gravity_in_orm_stream():
    """specific_gravity 写入 ORM Stream 后可读出（SIM-31 migration）。"""
    from app.models.project import Stream

    s = Stream()
    s.specific_gravity = 0.85
    assert s.specific_gravity == 0.85


# ---------------------------------------------------------------------------
# SIM-33：JSONB → ORM 迁移后的 3 字段
# ---------------------------------------------------------------------------


def test_liquid_std_density_in_orm_stream():
    """liquid_std_density（SIM-31 std_liq_density）迁 ORM 后直接读写。"""
    from app.models.project import Stream

    s = Stream()
    s.liquid_std_density = 850.0
    assert s.liquid_std_density == 850.0


def test_liquid_mass_rate_in_orm_stream():
    """liquid_mass_rate（SIM-31 JSONB）迁 ORM 后直接读写。"""
    from app.models.project import Stream

    s = Stream()
    s.liquid_mass_rate = 1200.0
    assert s.liquid_mass_rate == 1200.0


def test_liquid_actual_m3hr_in_orm_stream():
    """liquid_actual_m3hr（SIM-31 liq_actual_m3hr）迁 ORM 后直接读写。"""
    from app.models.project import Stream

    s = Stream()
    s.liquid_actual_m3hr = 1.5
    assert s.liquid_actual_m3hr == 1.5


# ---------------------------------------------------------------------------
# PropertyAutoCompleter 不变性回归（SIM-26 契约）
# ---------------------------------------------------------------------------


def test_property_auto_complete_signature_unchanged():
    """SIM-31 不修改 PropertyAutoCompleter 签名：complete(cas, target_fields)。"""
    import inspect

    from app.services.property_auto_complete import PropertyAutoCompleter

    sig = inspect.signature(PropertyAutoCompleter.complete)
    params = list(sig.parameters.keys())
    # 签名第一参数为 cas（单 CAS 查询，无 composition/mass 概念）
    assert params[0] == "self"
    assert "cas" in params
    # 不应有 composition_mass / composition 形参（物性估算与组成解耦）
    assert "composition_mass" not in params
    assert "composition" not in params
