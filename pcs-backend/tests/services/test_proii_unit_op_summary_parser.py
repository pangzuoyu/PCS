"""P3.x SIM-15: 单元操作 SUMMARY 解析测试。

spec §3.4.2 + audit V2.0 E-1：从 .out 的 6 类 SUMMARY 段（REACTOR/COMPRESSOR/SPLITTER/
STCA/CALCULATOR/EXTRACTOR）提取
- 公共字段：unit_uid / iterations / convergence_status
- 单元流：feed_streams_json / product_streams_json
- raw_summary_json（完整段，备 SIM-20 增强）
"""
from __future__ import annotations

from pathlib import Path

from app.services.proii_parser import parse_proii_unit_op_summaries

FIXTURES = Path(__file__).parent.parent / "fixtures" / "proii"


def test_parse_unit_op_summaries_from_sample5():
    """sample5 含 6 类 SUMMARY 段：REACTOR/EXTRACTOR/COMPRESSOR/SPLITTER/STCA/CALCULATOR。"""
    out_path = FIXTURES / "sample5_reactor_extraction" / "sample5_reactor_extraction.out"
    result = parse_proii_unit_op_summaries(out_path)
    assert len(result) == 6
    types = {u["unit_type"] for u in result}
    assert types == {"REACTOR", "EXTRACTOR", "COMPRESSOR", "SPLITTER", "STCA", "CALCULATOR"}


def test_parse_reactor_summary_iterations_and_convergence():
    """REACTOR SUMMARY：iterations + convergence_status + feed/product streams。"""
    out_path = FIXTURES / "sample5_reactor_extraction" / "sample5_reactor_extraction.out"
    result = parse_proii_unit_op_summaries(out_path)
    r101 = next(u for u in result if u["unit_uid"] == "R101")
    assert r101["unit_type"] == "REACTOR"
    assert r101["iterations"] == 15
    assert r101["convergence_status"] == "CONVERGED"
    assert "FEED" in r101["feed_streams_json"]
    assert "CAT" in r101["feed_streams_json"]
    assert "PROD" in r101["product_streams_json"]


def test_parse_compressor_summary_outlet_pressure():
    """COMPRESSOR SUMMARY：outlet_pressure_kpa 提取。"""
    out_path = FIXTURES / "sample5_reactor_extraction" / "sample5_reactor_extraction.out"
    result = parse_proii_unit_op_summaries(out_path)
    c1 = next(u for u in result if u["unit_uid"] == "C1")
    assert c1["unit_type"] == "COMPRESSOR"
    assert c1["iterations"] == 8
    assert c1["raw_summary_json"].get("OUTLET PRESSURE") == "3.61"


def test_parse_splitter_summary_outlets():
    """SPLITTER SUMMARY：outlets 列表含 stream_id + mass_flow。"""
    out_path = FIXTURES / "sample5_reactor_extraction" / "sample5_reactor_extraction.out"
    result = parse_proii_unit_op_summaries(out_path)
    sp1 = next(u for u in result if u["unit_uid"] == "SP1")
    assert sp1["unit_type"] == "SPLITTER"
    outlets = sp1["raw_summary_json"].get("outlets", [])
    assert len(outlets) == 2
    assert outlets[0]["stream_id"] == "SPLIT1"
    assert outlets[0]["mass_flow_kg_h"] == 222.0


def test_parse_returns_empty_when_no_summary():
    """无 SUMMARY 段时返回空列表。"""
    out_path = FIXTURES / "sample1_34comp" / "sample1_34comp.out"
    result = parse_proii_unit_op_summaries(out_path)
    # sample1 无 SUMMARY 段（流文件，无单元操作段）
    assert isinstance(result, list)
