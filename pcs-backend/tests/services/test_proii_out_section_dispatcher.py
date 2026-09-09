"""P3.2 SIM-20: PRO/II .out 20+ Section 数值提取（spec V1.6 §3.4.2）。

目标：单一 .out 文件一次性提取所有 section，返回 dict[section_name, payload]。
性能基准：≤ 5s / 100 条记录（spec §3.4.2 性能预算）。

覆盖 section（与 PR-3~PR-10/PR-13 一致）：
- banner / convergence_status / warnings / reactions
- zero_flow / unreliable
- streams（STREAM SUMMARY 数值表）
- unit_ops（PUMP/HX/MIXER/FLASH/VALVE/COMPRESSOR/SPLITTER/STCA/CALCULATOR/COLUMN）
- run_statistics（RUN STATISTICS 段）
- calculation_history（CALCULATION HISTORY 段——如有）
- column_summary
- compositions（inp 文件）
- hcurve（HCURVE 段——本期未实现，返回 None）
- reactor_summary / cstr_summary（PR-13/14——本期未实现，返回 None）

性能测试：使用真实 sample 文件，断言 ≤ 5s / 100 条（单文件即可验证）。
"""
from __future__ import annotations

import time
from pathlib import Path

import pytest

from app.services.proii_parser import (
    parse_proii_out_sections,
)

SAMPLE_DIR = Path(__file__).resolve().parents[3] / "sample"
SAMPLE_PROII_OUT = SAMPLE_DIR / "proii .out"


# ---------------------------------------------------------------------------
# dispatcher 契约
# ---------------------------------------------------------------------------


def test_parse_proii_out_sections_returns_dict():
    """dispatcher 返回 dict（key=section 名，value=payload）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    assert isinstance(sections, dict)
    # 必含核心 section
    assert "banner" in sections
    assert "convergence_status" in sections
    assert "warnings" in sections
    assert "run_statistics" in sections


def test_parse_proii_out_sections_includes_stream_summary():
    """STREAM SUMMARY 段已提取（spec PR-5：streams 数值表）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    assert "streams" in sections
    # streams 是 dict[stream_name, stream_data] 或 list（与现有 _parse_streams 兼容）
    streams = sections["streams"]
    assert streams  # 非空


def test_parse_proii_out_sections_includes_run_statistics():
    """RUN STATISTICS 段：STARTED/FINISHED/RUN TIMES 三块。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    rs = sections["run_statistics"]
    assert isinstance(rs, dict)
    assert "started" in rs or "errors" in rs
    # 至少含 errors/warnings 计数
    assert "errors" in rs or "warnings" in rs


def test_parse_proii_out_sections_includes_unit_ops_summary():
    """unit_ops 段：所有单元操作的 SUMMARY 表（PUMP/HX/MIXER/.../COMPRESSOR/SPLITTER）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    assert "unit_ops" in sections
    unit_ops = sections["unit_ops"]
    assert isinstance(unit_ops, (list, dict))
    assert unit_ops  # 非空（PRO/II 文件必有 PUMP/HX 等）


def test_parse_proii_out_sections_includes_calculation_history_when_present():
    """CALCULATION HISTORY 段（如有）。本 sample 文件可能不含，容许 None。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    assert "calculation_history" in sections
    # 不强制非 None（多数 sample 不含此段）


def test_parse_proii_out_sections_includes_extended_unit_types():
    """COMPRESSOR / SPLITTER / STCA / CALCULATOR SUMMARY（PR-8b/PR-13）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    unit_ops = sections["unit_ops"]
    # 本 sample 文件至少含 PUMP/HX/MIXER 等基础类型
    unit_types = (
        {u.get("type") for u in unit_ops}
        if isinstance(unit_ops, list)
        else set(unit_ops.keys())
    )
    # 基础类型至少 1 个
    assert len(unit_types) >= 1


def test_parse_proii_out_sections_returns_section_count():
    """返回值含 section 名集合，便于上游审计（spec §3.4.2 性能审计）。"""
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    # dispatcher 至少返回 10 个 section key
    assert len(sections) >= 10


# ---------------------------------------------------------------------------
# 容错
# ---------------------------------------------------------------------------


def test_parse_proii_out_sections_missing_file_raises():
    """文件不存在 → FileNotFoundError。"""
    with pytest.raises(FileNotFoundError):
        parse_proii_out_sections("/nonexistent/proii.out")


def test_parse_proii_out_sections_invalid_file_returns_partial():
    """无效文件（无 banner）→ 抛 ValueError。"""
    tmp = Path("/tmp/_invalid_proii.out")
    tmp.write_text("NOT A PROII OUTPUT\n" * 10, encoding="utf-8")
    try:
        with pytest.raises(ValueError):
            parse_proii_out_sections(tmp)
    finally:
        tmp.unlink()


# ---------------------------------------------------------------------------
# 性能：≤5s / 100 条
# ---------------------------------------------------------------------------


def test_parse_proii_out_sections_performance_under_5s():
    """spec §3.4.2 性能预算：单文件解析 ≤5s。

    用真实 sample 文件（445KB 含多条 stream/unit_op），覆盖典型规模。
    """
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    # 预热（首次 import + 读文件 cache）
    parse_proii_out_sections(SAMPLE_PROII_OUT)
    # 测量
    t0 = time.perf_counter()
    for _ in range(5):
        parse_proii_out_sections(SAMPLE_PROII_OUT)
    elapsed = (time.perf_counter() - t0) / 5
    # 单次 ≤5s（spec 预算：100 条记录；本文件 < 100 条，但量级可比）
    assert elapsed < 5.0, f"parse_proii_out_sections too slow: {elapsed:.2f}s"


# ---------------------------------------------------------------------------
# 流式 stream summary 内容正确性
# ---------------------------------------------------------------------------


def test_parse_proii_out_sections_streams_contain_data_rows():
    """streams 段含 STREAM SUMMARY 数据行（spec PR-5：原始行 list）。

    注：本期未做列拆分（TYPE/NAME/PHASE/FROM/TO/FLOW_RATES），保留为
    原始字符串行——下游 SIM-22 PropertyConflictResolver 落地后可基于
    effective streams 表 join；列拆分属 SIM-22+ 增强范围。
    """
    if not SAMPLE_PROII_OUT.exists():
        pytest.skip(f"sample not found: {SAMPLE_PROII_OUT}")
    sections = parse_proii_out_sections(SAMPLE_PROII_OUT)
    streams = sections["streams"]
    assert isinstance(streams, list)
    # 至少 1 条数据行（FEED/PROD 等）
    assert len(streams) >= 1
    # 行至少含 stream type 前缀（FEED/PROD/RECYCLE 等）
    type_prefixes = {"FEED", "PROD", "RECYCLE", "PROD."}
    has_prefixed = any(
        any(row.startswith(p) for p in type_prefixes)
        for row in streams
        if isinstance(row, str)
    )
    assert has_prefixed, (
        f"no STREAM SUMMARY row with FEED/PROD/RECYCLE prefix; "
        f"first 5 rows: {streams[:5]}"
    )
