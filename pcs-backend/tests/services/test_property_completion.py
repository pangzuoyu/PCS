"""P3.2 SIM-3：物性补全服务契约测试（spec V1.6 §3.3.1）。

锁定 property_completion.complete_properties / complete_batch 接口：
- 输入：含 .cas 字段的 stream 对象（dict / dataclass / 命名属性皆可）
- 输出：effective 物性 dict（mw/tc_k/pc_pa/tb_k/tm_k/source/warning）
- 水（7732-18-5）走 IAPWS-IF97 精确值（CommonService 已实现）
- 未知 CAS 抛 PcsError → 补全返回 None + warning
- 100 条并行 ≤ 5s（spec 性能预算）
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

import pytest

from app.services.property_completion import (
    ParsedStream,
    complete_batch,
    complete_properties,
)


@dataclass
class _FakeStream:
    """测试用 stream：含 .cas + .temperature_k 属性。"""

    tag: str
    cas: str | None = None
    temperature_k: float | None = None
    composition: dict[str, float] = field(default_factory=dict)


def test_complete_properties_water_uses_iapws_if97():
    s = ParsedStream(tag="W1", cas="7732-18-5", temperature_k=373.15)
    eff = complete_properties(s)
    assert eff["cas"] == "7732-18-5"
    assert eff["mw"] == pytest.approx(18.015, rel=1e-3)
    assert eff["source"] == "IAPWS-IF97"
    assert "warning" not in eff


def test_complete_properties_known_cas_uses_chemicals_library():
    """甲烷 74-82-8 在 chemicals 库中存在。"""
    s = ParsedStream(tag="C1", cas="74-82-8")
    eff = complete_properties(s)
    assert eff["cas"] == "74-82-8"
    assert eff["mw"] is not None
    assert eff["mw"] > 0
    assert eff["source"] in {"EXPERIMENTAL", "ESTIMATED"}


def test_complete_properties_unknown_cas_returns_none_with_warning():
    """未知 CAS 不抛错，返回 None + warning（供上游 conflict_resolver 标记）。"""
    s = ParsedStream(tag="X1", cas="0000-00-0")
    eff = complete_properties(s)
    assert eff["cas"] == "0000-00-0"
    assert eff["mw"] is None
    assert eff["source"] == "NOT_FOUND"
    assert "warning" in eff


def test_complete_properties_missing_cas_returns_warning():
    s = ParsedStream(tag="X2", cas=None)
    eff = complete_properties(s)
    assert eff["mw"] is None
    assert eff["source"] == "MISSING_CAS"
    assert eff["warning"] == "MISSING_CAS"


def test_complete_properties_uses_fake_stream_with_cas_attr():
    """兼容 _FakeStream 类型（命名 .cas 属性即可）。"""
    s = _FakeStream(tag="W1", cas="7732-18-5", temperature_k=373.15)
    eff = complete_properties(s)
    assert eff["mw"] == pytest.approx(18.015, rel=1e-3)
    assert eff["source"] == "IAPWS-IF97"


def test_complete_batch_returns_one_per_input():
    streams = [
        ParsedStream(tag=f"S{i}", cas="7732-18-5", temperature_k=373.15 + i)
        for i in range(10)
    ]
    results = complete_batch(streams)
    assert len(results) == 10
    for r in results:
        assert r["source"] == "IAPWS-IF97"
        assert r["mw"] == pytest.approx(18.015, rel=1e-3)


def test_complete_batch_100_streams_under_5_seconds():
    """spec §3.3.1 性能预算：100 条 ≤ 5s。"""
    streams = [
        ParsedStream(tag=f"S{i}", cas="7732-18-5", temperature_k=373.15)
        for i in range(100)
    ]
    t0 = time.monotonic()
    results = complete_batch(streams)
    elapsed = time.monotonic() - t0
    assert len(results) == 100
    assert elapsed < 5.0, f"批 100 条耗时 {elapsed:.2f}s 超 spec 预算 5s"


def test_complete_batch_mixed_cas_handles_partial_failures():
    """混合 CAS 批次：3 个有效 + 2 个无效，全返回，不抛错。"""
    streams = [
        ParsedStream(tag="S1", cas="7732-18-5"),  # water, valid
        ParsedStream(tag="S2", cas="74-82-8"),  # methane, valid
        ParsedStream(tag="S3", cas="67-56-1"),  # methanol, valid
        ParsedStream(tag="S4", cas="0000-00-0"),  # unknown
        ParsedStream(tag="S5", cas=None),  # missing
    ]
    results = complete_batch(streams)
    assert len(results) == 5
    assert results[0]["source"] == "IAPWS-IF97"
    assert results[1]["source"] in {"EXPERIMENTAL", "ESTIMATED"}
    assert results[2]["source"] in {"EXPERIMENTAL", "ESTIMATED"}
    assert results[3]["source"] == "NOT_FOUND"
    assert results[4]["source"] == "MISSING_CAS"


def test_complete_properties_preserves_input_cas():
    """output 必须含 cas 字段（即使缺失）。"""
    s = ParsedStream(tag="S1", cas=None)
    eff = complete_properties(s)
    assert "cas" in eff
    assert eff["cas"] is None
