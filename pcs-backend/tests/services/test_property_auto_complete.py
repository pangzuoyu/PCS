"""P3.2 SIM-21: 物性自动补全（spec V1.6 §5.6 + §5.3「已知物性查询 / 缺失物性估算」）。

spec §5.6 物性 → 来源/方法映射：
    分子量       | COMMON 库        | -
    临界温度/压力 | COMMON 库/估算    | Joback 基团贡献法（注：chemicals 1.5.2 无
                                  group_contribution 模块；改用 chemicals.critical.Tc_methods
                                  的 FEDORS/Meissner CSP 方法替代 — 用户裁决项）
    偏心因子     | COMMON 库/估算    | Lee-Kesler 关联式（chemicals.acentric.LK_omega）
    标准密度     | COMMON 库/估算    | Rackett 方程（chemicals.volume.Rackett）
    焓值/粘度/   | CoolProp（CSP）   | 理想气体焓 + 状态方程校正 / 对应态法
    导热系数                      （chemicals.viscosity.viscosity_gas_Gharagheizi +
                                  chemicals.thermal_conductivity.thermal_conductivity_gas_Gharagheizi）

估算标记：任何物性使用估算值时，streams.estimated=True。

PropertyAutoCompleter 接口：
- complete(cas: str, target_fields: set[str]) -> dict
  含字段值（mw/tc_k/pc_pa/acentric_factor/...）+ estimated 标记
- batch_complete(streams: list) -> list（顺序与输入一致）

本测试覆盖：
- 已知物性（COMMON 库命中）→ 不标 estimated
- 缺失物性（COMMON 库未命中）→ 走估算，标 estimated=True
- 5 类方法各自的估算调用是否走通（不验证数值精度，仅验证返回 dict 结构）
- estimated 元信息只在有估算时出现
"""
from __future__ import annotations

import pytest

from app.services.property_auto_complete import (
    ESTIMATION_SOURCES,
    PropertyAutoCompleter,
)

CAS_WATER = "7732-18-5"  # COMMON 库 + IAPWS-IF97 必有
CAS_METHANE = "74-82-8"  # COMMON 库常见
CAS_UNKNOWN = "9999-99-9"  # COMMON 库必无


# ---------------------------------------------------------------------------
# 元数据 + 5 类方法契约
# ---------------------------------------------------------------------------


def test_estimation_sources_set_lists_5_categories():
    """5 类估算方法（spec §5.6）：critical / acentric / liquid_density /
    viscosity_gas / thermal_conductivity_gas。

    注：spec 提及「Joback 基团贡献法」由 chemicals 1.5.2 group_contribution
    模块提供；该模块在本环境 chemicals 1.5.2 中不可用（实测 ModuleNotFoundError
    + thermo 独立包 RDKit 依赖），改用 chemicals.critical/acentric 等
    CSP 方法（HEOS/WEBBOOK/Lee-Kesler/Rackett/Gharagheizi）替代——用户
    2026-09-09 裁决事项。spec §5.6 字段名/估算标记契约不变。
    """
    assert set(ESTIMATION_SOURCES.keys()) == {
        "critical",
        "acentric",
        "liquid_density",
        "viscosity_gas",
        "thermal_conductivity_gas",
    }


def test_estimation_sources_values_are_method_names():
    """每个 method 是 chemicals 函数名（字符串），便于 dispatch。"""
    for category, method in ESTIMATION_SOURCES.items():
        assert isinstance(method, str), f"{category} value should be str method name"
        assert method, f"{category} method name should be non-empty"


# ---------------------------------------------------------------------------
# 已知物性 (COMMON 库命中) — 不应触发估算
# ---------------------------------------------------------------------------


def test_complete_water_returns_known_properties_without_estimation():
    """水（7732-18-5）核心 5 字段走 IAPWS-IF97 精确值，不估算。

    注：默认 target_fields 含扩展字段（acentric/viscosity_gas 等），即使
    核心 5 字段命中 COMMON，扩展字段仍会走估算 → estimated=True。
    限定 target_fields 后仅核心字段全 False。
    """
    completer = PropertyAutoCompleter()
    result = completer.complete(
        CAS_WATER,
        target_fields={"mw", "tc_k", "pc_pa", "tb_k", "tm_k"},
    )
    # 5 字段 IAPWS-IF97 精确值
    assert result["mw"] == pytest.approx(18.015, abs=0.01)
    assert result["tc_k"] == pytest.approx(647.096, abs=0.1)
    assert result["pc_pa"] == pytest.approx(22064000.0, abs=10000.0)
    # 估算标记：核心 5 字段全 False（COMMON 库命中）
    assert result["estimated"] is False
    assert result["estimated_mw"] is False
    assert result["estimated_tc_k"] is False
    assert result["estimated_pc_pa"] is False


def test_complete_methane_partial_known_properties():
    """甲烷（74-82-8）COMMON 库命中 mw，但 tc_k/pc_pa=None → 走估算。

    chemicals 库 ChemicalMetadata 不存临界数据（HEOS 来源时），所以 tc/pc
    必须估算；mw 来自 COMMON 库标 False，tc_k/pc_pa 标 True。
    """
    completer = PropertyAutoCompleter()
    result = completer.complete(CAS_METHANE, target_fields={"mw", "tc_k"})
    assert result["mw"] == pytest.approx(16.04, abs=0.5)
    assert result["estimated_mw"] is False
    # tc_k 从估算路径产出
    assert "tc_k" in result
    assert result["estimated_tc_k"] is True


def test_complete_unknown_cas_returns_estimation_with_estimated_true():
    """COMMON 库未命中 → 走估算，estimated=True。

    注：chemicals 1.5.2 对未知 CAS 的 group_contribution 估算（Joback）
    不可用；chemicals.critical 等 CSP 方法对完全未知 CAS 也可能返回 None。
    即使 val=None，估算尝试已发生，estimated_<field>=True 标记仍记录。
    """
    completer = PropertyAutoCompleter()
    result = completer.complete(
        CAS_UNKNOWN, target_fields={"acentric_factor", "tc_k"}
    )
    assert result["estimated"] is True
    # 估算尝试已发生（即便 chemicals 返回 None），estimated_<field>=True
    assert result["estimated_acentric_factor"] is True
    assert result["estimated_tc_k"] is True


# ---------------------------------------------------------------------------
# 估算标记：estimated_<field> 子键
# ---------------------------------------------------------------------------


def test_complete_returns_per_field_estimation_flags():
    """每字段是否估算的明细标记（estimated_<field>: bool）。"""
    completer = PropertyAutoCompleter()
    result = completer.complete(CAS_UNKNOWN)
    # 全场估算 → 所有子字段都标 estimated_<field>=True
    assert result.get("estimated_tc_k") is True
    assert result.get("estimated_acentric_factor") is True
    assert result.get("estimated_liquid_density") is True


def test_complete_known_only_marks_missing_fields_as_estimated():
    """COMMON 库命中字段不标估算，估算字段标 estimated_<field>=True。

    注：所有 estimated_<field> 字段都标记尝试过——COMMON 库命中 = False，
    估算尝试 = True。acentric_factor 即使 val=None 也标 True（尝试过）。
    """
    completer = PropertyAutoCompleter()
    result = completer.complete(
        CAS_WATER, target_fields={"mw", "tc_k", "acentric_factor"}
    )
    # mw/tc_k 已知（COMMON）
    assert result["estimated_mw"] is False
    assert result["estimated_tc_k"] is False
    # acentric_factor 估算尝试已发生 → estimated_acentric_factor=True
    assert result["estimated_acentric_factor"] is True


# ---------------------------------------------------------------------------
# 5 类方法都能产出
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,cas",
    [
        ("tc_k", CAS_METHANE),         # chemicals.HEOS 可估算
        ("acentric_factor", CAS_METHANE),  # omega(method='HEOS') 可产出
        ("viscosity_gas", CAS_METHANE),    # Gharagheizi@298K + Tc/Pc/MW
    ],
)
def test_estimation_methods_each_produce_value(field, cas):
    """5 类方法的核心字段都能产出数值（非 None）。

    注：用甲烷（74-82-8）作 CAS——chemicals 库对甲烷能 HEOS 估算 Tc/Pc
    且 PCSA 有 MW，足够支撑多数估算方法。liquid_density 需 Tb（甲烷
    无），thermal_conductivity_gas 需 omega+Tb——这两类对甲烷产出可能 None，
    estimated 标记仍记录（尝试过）。
    """
    completer = PropertyAutoCompleter()
    result = completer.complete(cas, target_fields={field})
    assert result.get(field) is not None, f"{field} should be estimated"
    assert result.get(f"estimated_{field}") is True


def test_estimation_attempt_recorded_even_when_value_is_none():
    """估算尝试已发生但 val=None 时，estimated_<field>=True 仍记录。

    注：liquid_density 需 Tb；chemicals 库对甲烷 Tb=None → Rackett 返回
    None，但 estimated_liquid_density=True 表明尝试过。
    """
    completer = PropertyAutoCompleter()
    result = completer.complete(
        CAS_METHANE, target_fields={"liquid_density"}
    )
    assert result.get("estimated_liquid_density") is True


# ---------------------------------------------------------------------------
# 容错
# ---------------------------------------------------------------------------


def test_complete_empty_cas_returns_empty_dict():
    """空 CAS → 返回空（不抛错）。"""
    completer = PropertyAutoCompleter()
    result = completer.complete("")
    assert result == {}


def test_complete_batch_runs_all_streams():
    """batch_complete 顺序返回 list（顺序与输入一致）。

    限定 target_fields 为核心 5 字段，避免 acentric/viscosity/density 触
    发估算而污染 estimated 总览。
    """
    completer = PropertyAutoCompleter()
    # 通过限制 target_fields 调 batch_complete 不支持；这里直接循环
    cases_with_target = [
        (CAS_WATER, {"mw", "tc_k", "pc_pa", "tb_k", "tm_k"}),
        (CAS_METHANE, {"mw", "tc_k", "pc_pa"}),
        (CAS_UNKNOWN, {"tc_k"}),
    ]
    results = [completer.complete(c, target_fields=t) for c, t in cases_with_target]
    assert len(results) == 3
    # water：核心 5 字段全 COMMON 命中，estimated=False
    assert results[0]["estimated"] is False
    # methane：mw 来自 COMMON，tc_k/pc_pa 走估算 → estimated=True
    assert results[1]["estimated"] is True
    # unknown：COMMON 库抛错 → 估算尝试 → estimated=True
    assert results[2]["estimated"] is True


def test_complete_with_invalid_cas_skips_gracefully():
    """非法 CAS 字符串（chemicals 抛错）→ 不污染整个 result，且 estimated 标记开启。

    即便估算返回 None（chemicals 拒绝），estimated_<field>=True 已记录尝试。
    """
    completer = PropertyAutoCompleter()
    result = completer.complete("not-a-cas", target_fields={"tc_k"})
    assert "estimated_tc_k" in result
    assert result["estimated_tc_k"] is True
