"""P3.x SIM-37b/3: PRO/II 8.x 炼油版全量解析 — REFSTREAM + TRAY SIZING。

Part 3/3（6 parser 拆 3 commit）：
- commit 3: REFSTREAM（参考物流声明）+ TRAY SIZING（塔盘尺寸输出）

格式参考（sample/huafeng140_FCC2015.out + 200FlexiCoking1.out）：
- REFSTREAM 输入声明（PROPERTY 行内参数）：
    PROPERTY STREAM=5R, REFSTREAM=5
    PROPERTY STREAM=17R, TEMPERATURE=270, REFSTREAM=17, RATE(M)=1000
    PROPERTY STREAM=46AR, TEMPERATURE=190, REFSTREAM=46A, &
         RATE(M)=1057.65
  - REFSTREAM=<被引用物流>；可选 TEMPERATURE=/RATE(M|WT)= 覆盖
- TRAY SIZING 输出（per UNIT 两表）：
    UNIT 5, 'T204B', 'STRIPPER'  (Cont)
    TRAY SIZING MECHANICAL DATA
     SECTION  TRAY NUMBERS  PASSES  SPACING MM  FACTOR  TYPE  MIN DIA MM
        1     1 - 9         N/A    609.60      1.00    VALVE 381.00
    TRAY SIZING RESULTS
     TRAY VAPOR LIQUID VLOAD  DESIGN DIA FF  NEXT-SMALLER  NEXT-LARGER  NP
      1   0.342 0.08638 0.091  1993.1 78.0  1981. 78.8  2134. 69.5  2
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_refstream_tray_sizing_parser import (
    RefStreamDeclaration,
    TraySizingResult,
    TraySizingSection,
    UnitTraySizing,
    parse_refstream_declarations,
    parse_tray_sizing,
)

SAMPLE_FCC = Path(__file__).resolve().parents[3] / "sample" / "200FlexiCoking1.out"
SAMPLE_HF = Path(__file__).resolve().parents[3] / "sample" / "huafeng140_FCC2015.out"


# ============================================================================
# REFSTREAM 声明契约
# ============================================================================


def test_refstream_parse_minimal():
    """PROPERTY STREAM=5R, REFSTREAM=5 最简引用。"""
    text = "  PROPERTY STREAM=5R, REFSTREAM=5"
    decls = parse_refstream_declarations(text)
    assert len(decls) == 1
    d = decls[0]
    assert d.stream_id == "5R"
    assert d.ref_stream_id == "5"
    assert d.temperature is None
    assert d.rate is None
    assert d.rate_basis is None


def test_refstream_parse_with_overrides():
    """TEMPERATURE= + RATE(M)= 覆盖参数。"""
    text = "  PROPERTY STREAM=17R, TEMPERATURE=270, REFSTREAM=17, RATE(M)=1000"
    decls = parse_refstream_declarations(text)
    assert len(decls) == 1
    d = decls[0]
    assert d.stream_id == "17R"
    assert d.ref_stream_id == "17"
    assert d.temperature == pytest.approx(270.0)
    assert d.rate == pytest.approx(1000.0)
    assert d.rate_basis == "M"


def test_refstream_parse_with_continuation():
    """跨行 `&` 续行（RATE 在第二行）。"""
    text = """  PROPERTY STREAM=46AR, TEMPERATURE=190, REFSTREAM=46A, &
         RATE(M)=1057.65"""
    decls = parse_refstream_declarations(text)
    assert len(decls) == 1
    d = decls[0]
    assert d.ref_stream_id == "46A"
    assert d.rate == pytest.approx(1057.65)
    assert d.rate_basis == "M"


def test_refstream_parse_rate_wt_basis():
    """RATE(WT)= 质量基准。"""
    text = "  PROPERTY STREAM=XR, REFSTREAM=X, RATE(WT)=500"
    decls = parse_refstream_declarations(text)
    assert decls[0].rate_basis == "WT"
    assert decls[0].rate == pytest.approx(500.0)


def test_refstream_parse_multiple():
    """多条 REFSTREAM 声明。"""
    text = """
  PROPERTY STREAM=5R, REFSTREAM=5
  PROPERTY STREAM=11R, REFSTREAM=11
  PROPERTY STREAM=27R, REFSTREAM=27
"""
    decls = parse_refstream_declarations(text)
    assert len(decls) == 3
    assert [d.stream_id for d in decls] == ["5R", "11R", "27R"]


def test_refstream_parse_skips_plain_property_lines():
    """无 REFSTREAM 的 PROPERTY 行不产出。"""
    text = """
  PROPERTY STREAM=1H2O, TEMPERATURE=412, PRESSURE=0.18, PHASE=M, &
         COMPOSITION(WT,KG/H)=1,33015.6
"""
    assert parse_refstream_declarations(text) == []


def test_refstream_parse_empty_text():
    assert parse_refstream_declarations("") == []


def test_refstream_parse_case_insensitive():
    """refstream 关键字大小写不敏感。"""
    text = "  property stream=5R, refstream=5"
    decls = parse_refstream_declarations(text)
    assert len(decls) == 1
    assert decls[0].ref_stream_id == "5"


# ============================================================================
# TRAY SIZING 输出契约
# ============================================================================


TRAY_SIZING_BLOCK = """
                      UNIT 5, 'T204B', 'STRIPPER'  (Cont)

 TRAY SIZING MECHANICAL DATA

  SECTION    TRAY      TRAY   TRAY SPACING  SYSTEM  TRAY   MIN DIAMETER
            NUMBERS   PASSES        MM      FACTOR  TYPE        MM
  -------  ---------  ------  ------------  ------  -----  ------------
      1      1 -   9   N/A        609.60      1.00  VALVE     381.00


 TRAY SIZING RESULTS

  TRAY  VAPOR  LIQUID  VLOAD   -- DESIGN --   NEXT SMALLER   NEXT LARGER    NP
         M3/S   M3/S    M3/S   DIA, MM  FF    DIA, MM  FF    DIA, MM  FF
  ----  ----- -------  -----   ------- ----   ------- ----   ------- ----   --
    1   0.342 0.08638  0.091   1993.1  78.0   1981.   78.8   2134.   69.5    2
    2   0.407 0.09498  0.114   2166.2  78.0   2134.   80.0   2286.   71.2    2
    3   0.448 0.10114  0.129   2283.1  78.0   2134.   87.5   2286.   77.8    2
"""


def test_tray_sizing_parse_single_unit():
    """单 UNIT 块：unit 元数据 + MECHANICAL 1 section + RESULTS 3 tray。"""
    units = parse_tray_sizing(TRAY_SIZING_BLOCK)
    assert len(units) == 1
    u = units[0]
    assert u.unit_no == "5"
    assert u.unit_name == "T204B"
    assert u.unit_desc == "STRIPPER"
    assert len(u.sections) == 1
    assert len(u.results) == 3


def test_tray_sizing_mechanical_section_fields():
    """MECHANICAL DATA section 字段解析。"""
    units = parse_tray_sizing(TRAY_SIZING_BLOCK)
    s = units[0].sections[0]
    assert s.section_no == 1
    assert s.tray_numbers == "1 - 9"
    assert s.tray_passes == "N/A"
    assert s.tray_spacing_mm == pytest.approx(609.60)
    assert s.system_factor == pytest.approx(1.00)
    assert s.tray_type == "VALVE"
    assert s.min_diameter_mm == pytest.approx(381.00)


def test_tray_sizing_results_row_fields():
    """RESULTS 行字段解析（11 列）。"""
    units = parse_tray_sizing(TRAY_SIZING_BLOCK)
    r = units[0].results[0]
    assert r.tray == 1
    assert r.vapor_m3s == pytest.approx(0.342)
    assert r.liquid_m3s == pytest.approx(0.08638)
    assert r.vload_m3s == pytest.approx(0.091)
    assert r.design_dia_mm == pytest.approx(1993.1)
    assert r.design_ff == pytest.approx(78.0)
    assert r.next_smaller_dia_mm == pytest.approx(1981.0)
    assert r.next_smaller_ff == pytest.approx(78.8)
    assert r.next_larger_dia_mm == pytest.approx(2134.0)
    assert r.next_larger_ff == pytest.approx(69.5)
    assert r.np == 2


def test_tray_sizing_no_tray_sizing_returns_empty():
    """无 TRAY SIZING 段 → 空 list。"""
    assert parse_tray_sizing("COLUMN SUMMARY\nnothing") == []
    assert parse_tray_sizing("") == []


def test_tray_sizing_multiple_units():
    """多 UNIT 块各自归属（UNIT 头切换归属）。"""
    text = TRAY_SIZING_BLOCK + TRAY_SIZING_BLOCK.replace("UNIT 5", "UNIT 6")
    units = parse_tray_sizing(text)
    assert len(units) == 2
    assert units[0].unit_no == "5"
    assert units[1].unit_no == "6"


# ============================================================================
# 真 fixture 验证
# ============================================================================


def test_real_fixture_huafeng_refstream_declarations():
    """真 fixture huafeng140：≥10 条 REFSTREAM 声明 + 17R 温度/流量覆盖。"""
    if not SAMPLE_HF.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_HF}")

    text = SAMPLE_HF.read_text(encoding="utf-8", errors="replace")
    decls = parse_refstream_declarations(text)
    assert len(decls) >= 10
    d17 = next(d for d in decls if d.stream_id == "17R")
    assert d17.ref_stream_id == "17"
    assert d17.temperature == pytest.approx(270.0)
    assert d17.rate == pytest.approx(1000.0)
    d46 = next(d for d in decls if d.stream_id == "46AR")
    assert d46.rate == pytest.approx(1057.65)


def test_real_fixture_fcc_tray_sizing_units():
    """真 fixture 200FlexiCoking1：10 个 UNIT TRAY SIZING 块（5 塔 × 2 单位系）。"""
    if not SAMPLE_FCC.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FCC}")

    text = SAMPLE_FCC.read_text(encoding="utf-8", errors="replace")
    units = parse_tray_sizing(text)
    # 5 塔（T204B/T207/T204/T205/T201）× 主/备单位系两遍 = 10 块
    assert len(units) == 10
    names = {u.unit_name for u in units}
    assert {"T204B", "T207", "T204", "T205", "T201"} == names


def test_real_fixture_fcc_tray_sizing_stripper():
    """真 fixture：T204B STRIPPER 9 层塔板（tray 1-9）。"""
    if not SAMPLE_FCC.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FCC}")

    text = SAMPLE_FCC.read_text(encoding="utf-8", errors="replace")
    units = parse_tray_sizing(text)
    stripper = next(u for u in units if u.unit_name == "T204B")
    assert stripper.unit_desc == "STRIPPER"
    assert stripper.sections[0].tray_type == "VALVE"
    assert stripper.sections[0].tray_spacing_mm == pytest.approx(609.60)
    assert len(stripper.results) == 9
    assert stripper.results[0].tray == 1
    assert stripper.results[-1].tray == 9


# ============================================================================
# 数据类契约
# ============================================================================


def test_refstream_dataclass_fields():
    """RefStreamDeclaration 字段：5 个。"""
    d = RefStreamDeclaration(
        stream_id="5R", ref_stream_id="5",
        temperature=270.0, rate=1000.0, rate_basis="M",
    )
    assert d.stream_id == "5R"
    assert d.rate_basis == "M"


def test_tray_sizing_dataclass_fields():
    """三个 dataclass 字段契约。"""
    s = TraySizingSection(
        section_no=1, tray_numbers="1 - 9", tray_passes="N/A",
        tray_spacing_mm=609.6, system_factor=1.0,
        tray_type="VALVE", min_diameter_mm=381.0,
    )
    r = TraySizingResult(
        tray=1, vapor_m3s=0.342, liquid_m3s=0.08638, vload_m3s=0.091,
        design_dia_mm=1993.1, design_ff=78.0,
        next_smaller_dia_mm=1981.0, next_smaller_ff=78.8,
        next_larger_dia_mm=2134.0, next_larger_ff=69.5, np=2,
    )
    u = UnitTraySizing(
        unit_no="5", unit_name="T204B", unit_desc="STRIPPER",
        sections=[s], results=[r],
    )
    assert u.unit_name == "T204B"
    assert u.sections[0].tray_type == "VALVE"
    assert u.results[0].np == 2
