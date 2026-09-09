"""P3.x SIM-19: PRO/II composition 提取 + 17 项 LIBID→CAS 别名映射 测试。

spec §3.3.3 + §5.2：
- 从 .inp PROPERTY STREAM 段的 COMPOSITION(M)=N,f/N,f/... 提取组成
- 17 项 LIBID→CAS 别名映射（H2O→WATER, CO2→CARBON_DIOXIDE 等）
- 输出：stream_tag → {component_name_or_alias: mole_fraction}
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_parser import (
    PROII_COMPONENT_ALIASES,
    map_libid_to_alias,
    parse_compositions,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "proii"


def test_proii_component_aliases_has_17_items():
    """spec §5.2 契约：PROII_COMPONENT_ALIASES 必含 17 项 LIBID→CAS。"""
    assert len(PROII_COMPONENT_ALIASES) == 17
    # 关键别名覆盖（H2O/CO2/H2S/NH3/CH4/C2H6/C3H8 等）
    must_have = {"H2O", "CO2", "H2S", "N2", "O2", "H2", "NH3", "C1",
                 "C2", "C3", "CO", "SO2", "HCL", "CL2", "NC4", "IC4", "NC5"}
    missing = must_have - PROII_COMPONENT_ALIASES.keys()
    assert not missing, f"missing aliases: {missing}"


def test_map_libid_to_alias_h2o():
    """H2O → WATER 别名映射（spec §5.2 头部）。"""
    assert map_libid_to_alias("H2O") == "WATER"


def test_map_libid_to_alias_unknown_returns_unchanged():
    """未知 LIBID（如 C38 长链烃）→ 原名返回。"""
    assert map_libid_to_alias("C38") == "C38"


def test_map_libid_to_alias_case_insensitive():
    """别名匹配大小写不敏感（PRO/II 输出常大写）。"""
    assert map_libid_to_alias("h2o") == "WATER"
    assert map_libid_to_alias("H2o") == "WATER"


def test_parse_compositions_from_sample1():
    """sample1_34comp 多个 PROPERTY STREAM 含 COMPOSITION(M)=N,f/...。"""
    inp_path = FIXTURES / "sample1_34comp" / "sample1_34comp.inp"
    result = parse_compositions(inp_path)
    assert isinstance(result, dict)
    # FEED 流有 21 项组成（C1~C38 多个）
    assert "FEED" in result
    assert len(result["FEED"]) >= 1
    # 关键组分：LIBID=4 (C1) → METHANE，LIBID=11 (C6) → C6 (未在别名表)
    assert "METHANE" in result["FEED"]  # C1 LIBID=4
    assert "C6" in result["FEED"]  # C6 LIBID=11 (无别名)
    # 摩尔分率抽取
    assert result["FEED"]["METHANE"] == pytest.approx(5.0, rel=1e-6)
    assert result["FEED"]["C6"] == pytest.approx(3.0, rel=1e-6)


def test_parse_compositions_with_alias_resolution():
    """验证 H2O 等常见组分通过 libid→name→alias 链解析。"""
    # 构造最小 .inp 文本（含 H2O）
    text = """\
TITLE PROJECT=Test
 COMPONENT DATA
   LIBID 1,H2O/2,CO2/3,C1
 STREAM DATA
   PROPERTY STREAM=S1, TEMPERATURE=80, PRESSURE=200, PHASE=L, &
          RATE(W)=1000, COMPOSITION(M)=1,0.95/2,0.03/3,0.02, NORMALIZE
"""
    inp_path = FIXTURES.parent.parent / "_tmp_sim19.inp"
    inp_path.write_text(text)
    try:
        result = parse_compositions(inp_path)
        assert "S1" in result
        # 通过 libid → 名称 → 别名映射：1=H2O=WATER
        # 输出 keys 应为别名后的名称（uppercase 兜底）
        keys = set(result["S1"].keys())
        assert "WATER" in keys
        assert "CARBON_DIOXIDE" in keys
        assert "METHANE" in keys  # C1 → METHANE
    finally:
        inp_path.unlink(missing_ok=True)


def test_parse_compositions_empty_when_no_composition():
    """无 COMPOSITION 段时返回空 dict。"""
    text = """\
TITLE PROJECT=Test
 STREAM DATA
   PROPERTY STREAM=S1, TEMPERATURE=80, PRESSURE=200, PHASE=L, RATE(W)=1000
"""
    inp_path = FIXTURES.parent.parent / "_tmp_sim19_empty.inp"
    inp_path.write_text(text)
    try:
        result = parse_compositions(inp_path)
        assert result == {}
    finally:
        inp_path.unlink(missing_ok=True)