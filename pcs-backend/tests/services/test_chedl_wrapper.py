"""P5-0-7 Task 26: ChEDL 包装层测试（ADR-0030 V1.1 决策 6/9 + V1.9 GSTACK P0/P2）。

7 包装函数：5 函数直调 fluids 顶层 + 2 函数 fallback（time_to_empty / tank_level_to_volume
在 fluids 1.3.1 不存在 → 自研几何 + 伯努利 + 孔口出流）。

provenance 接口：get_chedl_provenance() 返回 {func_name: ChEDLProvenance}，7 项齐全；
每项含 chEDL_function / chEDL_version / known_limitations / fallback_available /
fallback_formula_ref。
ChEDL 版本与 Task 25 锁定一致（fluids==1.3.1）。

与已有 chedl 集成的关联：
- Task 5（VESSEL）/ Task 6（SEP_EQUIP）/ Task 11（HEAT）实施时，调 chedl_wrapper.* 而非
  fluids.*（裁决 #8 + V1.8 F-13-2）；本测试是契约门禁。
"""
from __future__ import annotations

import math

import pytest

from app.services import chedl_wrapper
from app.services.chedl_provenance import ChEDLProvenance

# ============================================================================
# 5 直调函数（fluids 1.3.1 顶层）
# ============================================================================


def test_v_Souders_Brown_known_value():
    """v_Souders_Brown 烟雾速度：经典工况 K=0.1 ft/s、rhol=1000、rhog=1.2。

    API 521 / GPSA 数据手册参考：典型 K=0.1 ft/s → 速度量级 ~0.1 m/s 量级。
    函数签名：v_Souders_Brown(K, rhol, rhog) → m/s。
    """
    result = chedl_wrapper.v_Souders_Brown(K=0.1, rhol=1000.0, rhog=1.2)
    # 返回值应 > 0 且量级合理
    assert isinstance(result, float)
    assert result > 0.0
    # 量级校验（K=0.1 时典型结果约 0.05 ~ 0.5 m/s）
    assert 0.01 < result < 5.0


def test_K_separator_Watkins_known_value():
    """K_separator_Watkins：Watkins 法重力分离 K 值。

    典型工况 x=0.1 m、rhol=850、rhog=1.2 → K 量级 0.05 ~ 0.5 m/s。
    """
    result = chedl_wrapper.K_separator_Watkins(x=0.1, rhol=850.0, rhog=1.2)
    assert isinstance(result, float)
    assert result > 0.0
    assert 0.01 < result < 1.0


def test_K_separator_demister_York_known_value():
    """K_separator_demister_York：York 除雾器 K 值（基于压力 P）。

    典型工况 P=101325 Pa（大气压） → K 量级 0.05 ~ 0.2 m/s。
    """
    result = chedl_wrapper.K_separator_demister_York(P=101325.0)
    assert isinstance(result, float)
    assert result > 0.0
    assert 0.01 < result < 1.0


def test_v_terminal_known_value():
    """v_terminal：终端沉降速度（Stokes 定律 / 通用算法）。

    典型工况 D=100e-6 m（100 μm 颗粒）、rhop=2500、rho=1000、mu=0.001 → 量级 1e-3 m/s。
    """
    result = chedl_wrapper.v_terminal(
        D=100e-6, rhop=2500.0, rho=1000.0, mu=0.001
    )
    assert isinstance(result, float)
    assert result > 0.0
    # 量级合理（典型 1e-5 ~ 1e-1 m/s）
    assert 1e-6 < result < 1.0


def test_API520_round_size_known_value():
    """API520_round_size：API 520 阀门口径圆整。

    面积输入 → 返回圆整到标准口径。
    """
    result = chedl_wrapper.API520_round_size(A=0.001)  # 1 cm² 量级
    assert isinstance(result, float)
    assert result >= 0.0
    # 圆整后应不小于原值（向上圆整）或等于
    assert result >= 0.001


# ============================================================================
# 2 Fallback 函数（fluids 1.3.1 不存在 → 自研）
# ============================================================================


def test_time_to_empty_fallback_path():
    """time_to_empty：fluids 1.3.1 不存在 → 触发 fallback（伯努利 + 孔口出流）。

    fallback 实现：圆柱容器 + 圆孔口 + 孔口系数 Cd=0.62。
    公式：Q = Cd · A · √(2·g·h)，积分得 t = (A_tank / (Cd · A_orifice)) · √(2·h₀/g)。

    典型工况：D_tank=2 m, h₀=2 m, d_orifice=0.05 m → 量级 100~1000 s（合理）。
    """
    # 调用包装层（不直接调 fluids），参数语义：直径/初始液位/孔口直径/Cd
    result = chedl_wrapper.time_to_empty(
        D_tank=2.0, h0=2.0, d_orifice=0.05, Cd=0.62
    )
    assert isinstance(result, float)
    assert result > 0.0
    assert math.isfinite(result)
    # 量级合理：~1e2 ~ 1e4 s
    assert 10.0 < result < 100000.0


def test_tank_level_to_volume_fallback_path():
    """tank_level_to_volume：fluids 1.3.1 不存在 → 触发 fallback（圆柱几何 + 椭圆封头）。

    典型工况：D=2 m, h=1 m → V = π · r² · h = π · 1 · 1 ≈ 3.14 m³（无封头）。
    """
    result = chedl_wrapper.tank_level_to_volume(D=2.0, h=1.0, head_type="ellipse")
    assert isinstance(result, float)
    assert result > 0.0
    # 圆柱段 π·r²·h ≈ 3.14 m³（椭圆封头为圆柱段的修正，本测试无封头段 → 近似 3.14）
    assert 2.5 < result < 4.0


# ============================================================================
# provenance 接口
# ============================================================================


def test_get_chedl_provenance_returns_7_entries():
    """get_chedl_provenance() 必须返回 7 项（5 直调 + 2 fallback）。"""
    prov = chedl_wrapper.get_chedl_provenance()
    assert isinstance(prov, dict)
    assert len(prov) == 7, f"provenance 应有 7 项，实际 {len(prov)}: {list(prov.keys())}"


def test_get_chedl_provenance_contains_all_functions():
    """provenance 字典键必须含全部 7 包装函数名。"""
    prov = chedl_wrapper.get_chedl_provenance()
    expected = {
        "v_Souders_Brown",
        "K_separator_Watkins",
        "K_separator_demister_York",
        "v_terminal",
        "API520_round_size",
        "time_to_empty",
        "tank_level_to_volume",
    }
    assert set(prov.keys()) == expected, (
        f"provenance 键不匹配。缺失: {expected - set(prov.keys())}，"
        f"多余: {set(prov.keys()) - expected}"
    )


def test_get_chedl_provenance_version_matches_locked():
    """provenance 中的 ChEDL 版本必须与 Task 25 锁定一致（fluids==1.3.1）。"""
    prov = chedl_wrapper.get_chedl_provenance()
    for name, meta in prov.items():
        assert isinstance(meta, ChEDLProvenance), (
            f"{name} 应为 ChEDLProvenance 实例，实际 {type(meta)}"
        )
        assert meta.chEDL_version == "1.3.1", (
            f"{name} chEDL_version={meta.chEDL_version!r} != 锁定 '1.3.1'"
        )


def test_fallback_provenance_metadata():
    """2 fallback 函数的 provenance 必须显式标注 fallback_available=True + fallback_formula_ref。"""
    prov = chedl_wrapper.get_chedl_provenance()
    for fn_name in ("time_to_empty", "tank_level_to_volume"):
        meta = prov[fn_name]
        assert meta.fallback_available is True, (
            f"{fn_name} fallback_available 应为 True（fluids 1.3.1 缺该函数）"
        )
        assert meta.fallback_formula_ref, (
            f"{fn_name} fallback_formula_ref 必须非空（fallback 实现追溯）"
        )
        assert meta.known_limitations, (
            f"{fn_name} known_limitations 必须列出（用户决策依据）"
        )


def test_direct_provenance_metadata():
    """5 直调函数的 provenance：fallback_available=False + chEDL_function 指向 fluids 函数。"""
    prov = chedl_wrapper.get_chedl_provenance()
    for fn_name in (
        "v_Souders_Brown",
        "K_separator_Watkins",
        "K_separator_demister_York",
        "v_terminal",
        "API520_round_size",
    ):
        meta = prov[fn_name]
        assert meta.fallback_available is False, (
            f"{fn_name} fallback_available 应为 False（直调 fluids）"
        )
        assert meta.fallback_formula_ref is None, (
            f"{fn_name} fallback_formula_ref 应为 None"
        )
        # chEDL_function 应指向 fluids 包
        assert meta.chEDL_function.startswith("fluids."), (
            f"{fn_name} chEDL_function 应指向 fluids，实际 {meta.chEDL_function!r}"
        )


def test_known_limitations_present_all_entries():
    """provenance 中 7 项必须有 known_limitations（空 list 算 None 不可接受 → 测试用 truthy）。"""
    prov = chedl_wrapper.get_chedl_provenance()
    for name, meta in prov.items():
        assert isinstance(meta.known_limitations, list), (
            f"{name} known_limitations 应为 list，实际 {type(meta.known_limitations)}"
        )
        assert len(meta.known_limitations) >= 1, (
            f"{name} known_limitations 应至少 1 项（哪怕 'V1.8 F-13-5' 这种最小声明）"
        )


def test_provenance_runtime_version_matches():
    """provenance 中的 chEDL_version 应与运行时 fluids.__version__ 一致（双证据链）。"""
    import fluids

    prov = chedl_wrapper.get_chedl_provenance()
    for name, meta in prov.items():
        assert meta.chEDL_version == fluids.__version__, (
            f"{name} provenance version {meta.chEDL_version} != 运行时 {fluids.__version__}"
        )


# ============================================================================
# 包装层结构契约
# ============================================================================


def test_chedl_wrapper_module_exports_all_7():
    """chedl_wrapper 模块必须暴露全部 7 包装函数 + get_chedl_provenance。"""
    import app.services.chedl_wrapper as cw

    required_funcs = [
        "v_Souders_Brown",
        "K_separator_Watkins",
        "K_separator_demister_York",
        "v_terminal",
        "API520_round_size",
        "time_to_empty",
        "tank_level_to_volume",
        "get_chedl_provenance",
    ]
    for fn_name in required_funcs:
        assert hasattr(cw, fn_name), f"chedl_wrapper 缺 {fn_name}"
        assert callable(getattr(cw, fn_name)), f"chedl_wrapper.{fn_name} 不可调用"


def test_chedl_provenance_module_exports_dataclass():
    """chedl_provenance 模块必须暴露 ChEDLProvenance 数据类。"""
    from app.services import chedl_provenance

    assert hasattr(chedl_provenance, "ChEDLProvenance")
    assert hasattr(chedl_provenance.ChEDLProvenance, "__dataclass_fields__"), (
        "ChEDLProvenance 必须是 @dataclass"
    )


def test_chedl_provenance_dataclass_fields():
    """ChEDLProvenance 必须含 5 字段（function/version/limitations/available/ref）。"""
    from dataclasses import fields

    field_names = {f.name for f in fields(ChEDLProvenance)}
    expected = {
        "chEDL_function",
        "chEDL_version",
        "known_limitations",
        "fallback_available",
        "fallback_formula_ref",
    }
    assert field_names == expected, (
        f"ChEDLProvenance 字段不匹配。缺失: {expected - field_names}，"
        f"多余: {field_names - expected}"
    )


def test_chedl_provenance_frozen():
    """ChEDLProvenance 必须是 frozen dataclass（不可变，provenance 是历史快照）。"""
    from dataclasses import FrozenInstanceError

    meta = ChEDLProvenance(
        chEDL_function="fluids.separator.v_Souders_Brown",
        chEDL_version="1.3.1",
        known_limitations=["test"],
        fallback_available=False,
        fallback_formula_ref=None,
    )
    with pytest.raises(FrozenInstanceError):
        meta.chEDL_version = "9.9.9"  # type: ignore[misc]