"""P4-1-1 thermo_factory 单元测试。

覆盖：
- 4 体系映射返回正确 stub 类
- 未知体系 → UnknownSystemTypeError
- zs 归一化（0.99 / 1.5 / -0.1）
- 空 CASs 允许；空 zs → CompositionSumError
- ThermoInterface Protocol 运行时检查
- stub 方法调用 → NotImplementedError
"""
from __future__ import annotations

import math

import pytest

from app.services.exceptions import PcsError
from app.services.flash import thermo_factory
from app.services.flash.thermo_factory import (
    THERMO_METHOD_MAP,
    CompositionSumError,
    ThermoInterface,
    UnknownSystemTypeError,
    build_thermo,
)

# ---------------------------------------------------------------------------
# 映射表 + Stub 类构造
# ---------------------------------------------------------------------------


def test_thermo_method_map_has_four_systems():
    """4 体系映射表必须涵盖 LIGHT_HYDROCARBON / GAS_PROCESSING / POLAR / WATER_STEAM。"""
    assert set(THERMO_METHOD_MAP.keys()) == {
        "LIGHT_HYDROCARBON",
        "GAS_PROCESSING",
        "POLAR",
        "WATER_STEAM",
    }


def test_thermo_method_map_values_are_method_names():
    """映射值必须是 thermo 方法名（PRMIX / SRKMIX / NRTL / CoolProp）。"""
    assert THERMO_METHOD_MAP["LIGHT_HYDROCARBON"] == "PRMIX"
    assert THERMO_METHOD_MAP["GAS_PROCESSING"] == "SRKMIX"
    assert THERMO_METHOD_MAP["POLAR"] == "NRTL"
    assert THERMO_METHOD_MAP["WATER_STEAM"] == "CoolProp"


@pytest.mark.parametrize(
    ("system_type", "expected_cls_name"),
    [
        ("LIGHT_HYDROCARBON", "PRMIXThermo"),
        ("GAS_PROCESSING", "SRKMIXThermo"),
        ("POLAR", "NRTLThermo"),
        ("WATER_STEAM", "CoolPropThermo"),
    ],
)
def test_build_thermo_returns_correct_stub(system_type: str, expected_cls_name: str):
    """每体系返回对应 stub 类（实现 ThermoInterface Protocol）。"""
    zs = [0.5, 0.5]
    cass = ["74-82-8", "74-84-0"]
    thermo = build_thermo(system_type, zs, cass)
    assert isinstance(thermo, ThermoInterface)
    assert type(thermo).__name__ == expected_cls_name


# ---------------------------------------------------------------------------
# 未知体系
# ---------------------------------------------------------------------------


def test_unknown_system_type_raises():
    """未知体系 → UnknownSystemTypeError，且继承 PcsError（422 风格）。"""
    with pytest.raises(UnknownSystemTypeError) as exc_info:
        build_thermo("UNKNOWN_X", [1.0], ["74-82-8"])
    assert exc_info.value.status == 422
    assert exc_info.value.code == "UNKNOWN_SYSTEM_TYPE"
    assert isinstance(exc_info.value, PcsError)


# ---------------------------------------------------------------------------
# zs 归一化
# ---------------------------------------------------------------------------


def test_normalize_zs_sum_below_one():
    """sum=0.99 → 自动归一化（不报错），返回 stub。"""
    thermo = build_thermo("LIGHT_HYDROCARBON", [0.5, 0.49], ["74-82-8", "74-84-0"])
    assert isinstance(thermo, ThermoInterface)


def test_normalize_zs_sum_above_one():
    """sum=1.5 → 自动归一化（不报错），返回 stub。"""
    thermo = build_thermo("LIGHT_HYDROCARBON", [0.75, 0.75], ["74-82-8", "74-84-0"])
    assert isinstance(thermo, ThermoInterface)


def test_negative_zs_raises():
    """sum=-0.1（包含负值）→ CompositionSumError。"""
    with pytest.raises(CompositionSumError) as exc_info:
        build_thermo("LIGHT_HYDROCARBON", [-0.05, -0.05], ["74-82-8", "74-84-0"])
    assert exc_info.value.status == 422
    assert exc_info.value.code == "COMPOSITION_SUM_ERROR"
    assert isinstance(exc_info.value, PcsError)


def test_nan_zs_raises():
    """含 NaN → CompositionSumError（非有限值）。"""
    with pytest.raises(CompositionSumError):
        build_thermo("LIGHT_HYDROCARBON", [float("nan"), 0.5], ["74-82-8", "74-84-0"])


def test_inf_zs_raises():
    """含 inf → CompositionSumError。"""
    with pytest.raises(CompositionSumError):
        build_thermo("LIGHT_HYDROCARBON", [float("inf"), 0.5], ["74-82-8", "74-84-0"])


def test_empty_zs_raises():
    """空 zs 列表 → CompositionSumError（与归一化规则一致；sum=0 时无法归一化）。"""
    with pytest.raises(CompositionSumError):
        build_thermo("LIGHT_HYDROCARBON", [], ["74-82-8"])


def test_all_zero_zs_raises():
    """全 0 zs → CompositionSumError（sum=0 无法归一化）。"""
    with pytest.raises(CompositionSumError):
        build_thermo("LIGHT_HYDROCARBON", [0.0, 0.0], ["74-82-8", "74-84-0"])


# ---------------------------------------------------------------------------
# CASs 列表行为
# ---------------------------------------------------------------------------


def test_empty_cass_allowed():
    """空 CASs 列表允许（stub 不依赖 CAS，仅签名占位）。"""
    thermo = build_thermo("LIGHT_HYDROCARBON", [1.0], [])
    assert isinstance(thermo, ThermoInterface)


# ---------------------------------------------------------------------------
# Stub 方法行为
# ---------------------------------------------------------------------------


def test_stub_psat_raises_not_implemented():
    """stub.Psat 必须 raise NotImplementedError（P4-1-2 落地）。"""
    thermo = build_thermo("LIGHT_HYDROCARBON", [1.0], ["74-82-8"])
    with pytest.raises(NotImplementedError) as exc_info:
        thermo.Psat(0)
    assert "P4-1-2" in str(exc_info.value)


@pytest.mark.parametrize("system_type", list(THERMO_METHOD_MAP.keys()))
def test_all_stubs_implement_protocol(system_type: str):
    """每个 stub 类都应满足 ThermoInterface Protocol。"""
    thermo = build_thermo(system_type, [1.0], ["74-82-8"])
    # Protocol 运行时检查（isinstance 需 runtime_checkable）
    assert isinstance(thermo, ThermoInterface)


def test_protocol_is_runtime_checkable():
    """ThermoInterface 必须带 @runtime_checkable，否则 isinstance 抛 TypeError。"""
    thermo = build_thermo("LIGHT_HYDROCARBON", [1.0], ["74-82-8"])
    # 验证不抛 TypeError 即可
    assert isinstance(thermo, ThermoInterface)


# ---------------------------------------------------------------------------
# 数值合理性（非契约性 — 仅冒烟）
# ---------------------------------------------------------------------------


def test_normalize_does_not_mutate_input_visual_check():
    """归一化不修改原列表（仅在实现内做归一化，调用方不变）。"""
    zs = [0.75, 0.75]
    snapshot = list(zs)
    build_thermo("LIGHT_HYDROCARBON", zs, ["74-82-8", "74-84-0"])
    # 容许 sum 数值不变（不原地除）
    assert math.isclose(sum(zs), sum(snapshot), rel_tol=1e-12)


# ---------------------------------------------------------------------------
# 模块导出
# ---------------------------------------------------------------------------


def test_module_exports():
    """thermo_factory 模块必须导出 5 个公开符号。"""
    expected = {
        "THERMO_METHOD_MAP",
        "ThermoInterface",
        "build_thermo",
        "UnknownSystemTypeError",
        "CompositionSumError",
    }
    assert expected.issubset(set(dir(thermo_factory)))
