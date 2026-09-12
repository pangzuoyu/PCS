"""P3.x SIM-38a: 塔盘数据 PoC — TRAY COMPOSITIONS 单 Section。

PoC 范围（0.5d）：解析 TRAY MOLAR/WEIGHT COMPOSITIONS 段内
单 section 的块结构（每块 1-2 塔板）：

                              TRAY 1                      TRAY 2
     COMPONENT              X          Y                X          Y
                       ----------  ----------      ----------  ----------
    1 H2O                 0.00000     0.00000         0.00000     0.00000
    2 PO               7.6544E-04     0.02855      4.7646E-06     0.00135
    ...

  RATE, KG-MOL/HR           12.04    2.59E-01           15.81       12.30

- X = 液相分率，Y = 汽相分率（MOLAR 摩尔 / WEIGHT 质量）
- 列对齐：dashes 段起点 = 值列起点（1 塔板 2 列 / 2 塔板 4 列）
- RATE 行 = 各塔板液/汽相流率

深度解析（LOADING/RATING + 全 unit 翻页）留待 SIM-38b（2.5d）。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_tray_compositions_poc import (
    TrayCompositionRow,
    TrayCompositions,
    parse_tray_composition_blocks,
)

SAMPLE_DMC = Path(__file__).resolve().parents[3] / "sample" / "dmc.out"
SAMPLE_OLD = Path(__file__).resolve().parents[3] / "sample" / "proii .out"


TWO_TRAY_BLOCK = """
                               TRAY 1                      TRAY 2
     COMPONENT              X          Y                X          Y
                       ----------  ----------      ----------  ----------
    1 H2O                 0.00000     0.00000         0.00000     0.00000
    2 PO               7.6544E-04     0.02855      4.7646E-06     0.00135
    3 PROPCARB            0.94781     0.00956         0.99715     0.92804

  RATE, KG-MOL/HR           12.04    2.59E-01           15.81       12.30
"""

ONE_TRAY_BLOCK = """
                               TRAY 3
     COMPONENT              X          Y
                       ----------  ----------
    1 H2O                 0.00000     0.00000
    2 PO               1.6211E-06  4.6525E-04

  RATE, KG-MOL/HR           15.90       16.07
"""


# ============================================================================
# 块结构解析
# ============================================================================


def test_parse_two_tray_block():
    """2 塔板块：tray_numbers [1,2] + 3 组件 + 每组件 x/y 各 2 值。"""
    blocks = parse_tray_composition_blocks(TWO_TRAY_BLOCK)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.tray_numbers == [1, 2]
    assert len(b.rows) == 3
    r2 = b.rows[1]
    assert r2.comp_no == 2
    assert r2.comp_name == "PO"
    assert r2.x == pytest.approx([7.6544e-04, 4.7646e-06])
    assert r2.y == pytest.approx([0.02855, 0.00135])


def test_parse_one_tray_block():
    """1 塔板块：tray_numbers [3] + x/y 各 1 值。"""
    blocks = parse_tray_composition_blocks(ONE_TRAY_BLOCK)
    assert len(blocks) == 1
    b = blocks[0]
    assert b.tray_numbers == [3]
    r2 = b.rows[1]
    assert r2.x == pytest.approx([1.6211e-06])
    assert r2.y == pytest.approx([4.6525e-04])


def test_parse_rate_row():
    """RATE 行 → liquid_rates/vapor_rates（按塔板一一对应）。"""
    blocks = parse_tray_composition_blocks(TWO_TRAY_BLOCK)
    b = blocks[0]
    assert b.liquid_rates == pytest.approx([12.04, 15.81])
    assert b.vapor_rates == pytest.approx([0.259, 12.30])


def test_parse_multiple_blocks():
    """多块连续解析（TRAY 头行重新开块）。"""
    blocks = parse_tray_composition_blocks(TWO_TRAY_BLOCK + ONE_TRAY_BLOCK)
    assert len(blocks) == 2
    assert blocks[0].tray_numbers == [1, 2]
    assert blocks[1].tray_numbers == [3]


def test_parse_scientific_notation_values():
    """科学计数法值解析（4.6525E-04 / 4.46E-22）。"""
    text = """
                               TRAY 1                      TRAY 2
     COMPONENT              X          Y                X          Y
                       ----------  ----------      ----------  ----------
    1 NH3              9.2290E-04  3.0409E-04      1.2496E-04  3.5166E-04

  RATE, KG-MOL/HR          116.36    4.46E-22          106.75      116.36
"""
    blocks = parse_tray_composition_blocks(text)
    r = blocks[0].rows[0]
    assert r.comp_name == "NH3"
    assert r.x == pytest.approx([9.2290e-04, 1.2496e-04])
    assert r.y == pytest.approx([3.0409e-04, 3.5166e-04])
    assert blocks[0].vapor_rates == pytest.approx([4.46e-22, 116.36])


def test_parse_no_blocks_returns_empty():
    """无块结构 → 空 list。"""
    assert parse_tray_composition_blocks("") == []
    assert parse_tray_composition_blocks("COLUMN SUMMARY\nnothing here") == []


# ============================================================================
# 真 fixture 验证（单 Section 切片）
# ============================================================================


def _slice_section(text: str, start_marker: str, end_marker: str) -> str:
    """取 start_marker 之后到 end_marker 之前的片段（测试辅助）。"""
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.strip() == start_marker)
    end = next(
        i for i, ln in enumerate(lines[start + 1:], start=start + 1)
        if ln.strip() == end_marker
    )
    return "\n".join(lines[start + 1:end])


def test_real_fixture_dmc_t102_section():
    """真 fixture dmc.out：T102 MOLAR section 首块 14 组件 + RATE。"""
    if not SAMPLE_DMC.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_DMC}")

    text = SAMPLE_DMC.read_text(encoding="utf-8", errors="replace")
    section = _slice_section(text, "TRAY MOLAR COMPOSITIONS", "TRAY WEIGHT COMPOSITIONS")
    blocks = parse_tray_composition_blocks(section)
    assert len(blocks) >= 2
    b = blocks[0]
    assert b.tray_numbers == [1, 2]
    assert len(b.rows) == 14
    assert b.rows[0].comp_name == "H2O"
    assert b.rows[2].comp_name == "PROPCARB"
    assert b.rows[2].x[0] == pytest.approx(0.94781)
    assert b.liquid_rates == pytest.approx([12.04, 15.81])
    assert b.vapor_rates == pytest.approx([0.259, 12.30])


def test_real_fixture_old_t1_section():
    """真 fixture proii .out（4.17）：T1 MOLAR section 首块 2 组件。"""
    if not SAMPLE_OLD.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_OLD}")

    text = SAMPLE_OLD.read_text(encoding="utf-8", errors="replace")
    section = _slice_section(text, "TRAY MOLAR COMPOSITIONS", "TRAY WEIGHT COMPOSITIONS")
    blocks = parse_tray_composition_blocks(section)
    assert len(blocks) >= 2
    b = blocks[0]
    assert b.tray_numbers == [1, 2]
    assert len(b.rows) == 2
    assert b.rows[0].comp_name == "NH3"
    assert b.rows[1].comp_name == "H2O"
    assert b.rows[1].x == pytest.approx([0.99908, 0.99988])
    assert b.liquid_rates == pytest.approx([116.36, 106.75])


# ============================================================================
# 数据类契约
# ============================================================================


def test_tray_composition_dataclass_fields():
    """TrayCompositionRow / TrayCompositions 字段契约。"""
    r = TrayCompositionRow(comp_no=1, comp_name="H2O", x=[0.5], y=[0.6])
    b = TrayCompositions(
        tray_numbers=[1],
        rows=[r],
        liquid_rates=[12.0],
        vapor_rates=[4.0],
    )
    assert b.tray_numbers == [1]
    assert b.rows[0].comp_name == "H2O"
    assert b.liquid_rates == [12.0]
    assert b.vapor_rates == [4.0]
