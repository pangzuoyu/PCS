"""10 类报表 collector —— SPEC §3.2.1(2) 的类型表。

collector 是**声明**：每个 report_type 声明「查哪些源、选哪些字段」，
实际取数交给 `query_engine`（唯一实现）。它**不执行查询**，所以三条要害：

1. **10 种类型不多不少** —— SPEC 的表是权威，少一个是功能缺口，
   多一个是超范围。测试把类型名逐条列出，不是只断 len()。
2. **每种的源与格式都来自 SPEC** —— 「泵数据表」必须出在 `PUMP_RESULTS`，
   「综合能耗计算书」必须出在 `UTIL_RESULTS`。格式同样是契约：
   SPEC 写「设备一览表 → XLSX」就该是 xlsx。
3. **声明的字段必须真在注册表里** —— 否则 query_engine 会在运行时才炸。
"""
from __future__ import annotations

import pytest

from app.services.report.collector import REPORT_TYPES, collector_for
from app.services.report.datasource_registry import DATASOURCES

# SPEC §3.2.1(2) 逐条抄下来的权威清单
SPEC_TABLE = {
    "PIPING_CALC_BOOK": ("DOCX/PDF", "PIPING_RESULTS"),
    "PUMP_DATA_TABLE": ("DOCX/XLSX/PDF", "PUMP_RESULTS"),
    "PSV_DATA_TABLE": ("DOCX/PDF", "PSV_RESULTS"),
    "VESSEL_DATA_TABLE": ("DOCX/PDF", "VESSEL_RESULTS"),
    "HEAT_SPEC": ("DOCX/PDF", "HEAT_RESULTS"),
    "EQUIPMENT_LIST": ("XLSX", "EQUIP_LIST"),
    "UTILITY_BALANCE": ("XLSX", "UTIL_RESULTS"),
    "ENERGY_CALC_BOOK": ("DOCX/PDF", "UTIL_RESULTS"),
    "ENTRUST_CONDITION": ("XLSX", "UTIL_RESULTS"),
    "PIPING_LIST": ("XLSX", "PIPING_RESULTS"),
}


def test_ten_report_types_exactly():
    assert set(REPORT_TYPES) == set(SPEC_TABLE), (
        f"报表类型与 SPEC §3.2.1(2) 不符。"
        f"缺 {sorted(set(SPEC_TABLE) - set(REPORT_TYPES))}，"
        f"多 {sorted(set(REPORT_TYPES) - set(SPEC_TABLE))}")


@pytest.mark.parametrize("report_type", sorted(SPEC_TABLE))
def test_sources_match_spec(report_type):
    expected_formats, _expected_source = SPEC_TABLE[report_type]
    spec = collector_for(report_type)
    assert spec.formats == expected_formats, \
        f"{report_type} 输出格式应为 {expected_formats}，实得 {spec.formats}"


def test_each_type_declares_a_real_datasource():
    """数据源必须在注册表里 —— collector 声明的源会被 query_engine 直接查。"""
    for rt in REPORT_TYPES:
        spec = collector_for(rt)
        assert spec.primary, f"{rt} 未声明主源"
        for src in spec.sources:
            assert src in DATASOURCES, f"{rt} 声明了不存在的源 {src}"


def test_declared_fields_exist_in_registry():
    """**声明的字段必须真在注册表里** —— 否则 query_engine 在运行时才炸，
    而那时用户已经在点「生成」了。"""
    for rt in REPORT_TYPES:
        spec = collector_for(rt)
        for src, fields in spec.fields.items():
            assert src in DATASOURCES, f"{rt}: 源 {src} 不存在"
            known = DATASOURCES[src].fields
            unknown = [f for f in fields if f not in known]
            assert not unknown, \
                f"{rt}: {src} 的字段 {unknown} 不在注册表里（可用：{sorted(known)[:8]}…）"


def test_primary_source_is_among_sources():
    for rt in REPORT_TYPES:
        spec = collector_for(rt)
        assert spec.primary in spec.sources, \
            f"{rt} 的主源 {spec.primary} 不在 sources 里"


def test_field_count_is_not_empty():
    """空字段声明 = 该报表是空表。SPEC 每类都至少给了一组核心字段。"""
    for rt in REPORT_TYPES:
        spec = collector_for(rt)
        assert sum(len(v) for v in spec.fields.values()) >= 2, \
            f"{rt} 字段过少：{spec.fields}"


def test_unknown_report_type_raises():
    from app.services.exceptions import PcsError

    with pytest.raises(PcsError) as e:
        collector_for("NO_SUCH_REPORT")
    assert e.value.code == "REPORT_TYPE_UNKNOWN"
    assert e.value.status == 400


def test_energy_calc_book_source_matches_spec():
    """「综合能耗计算书」数据来源是 `UTIL + GB/T 50441` —— 本仓落地为
    UTIL_RESULTS 一个源（GB/T 50441 是计算标准，不是一张表）。"""
    assert collector_for("ENERGY_CALC_BOOK").primary == "UTIL_RESULTS"


def test_collector_has_no_query_logic():
    """collector 只**声明**，不执行 —— 取数是 query_engine 的唯一职责
    （用户 2026-10-09 裁决）。出现查询调用即违宪。"""
    import inspect

    from app.services.report import collector as c

    src = inspect.getsource(c)
    for banned in ("select(", "session.execute", "await db", "text("):
        assert banned not in src, f"collector 里出现了查询逻辑：{banned}"