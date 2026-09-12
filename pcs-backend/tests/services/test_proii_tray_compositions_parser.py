"""P3.x SIM-38b/3: 塔盘数据全量 — TRAY COMPOSITIONS 全量集成。

Part 3/3（SIM-38b 拆 3 commit，闭环）：
- commit 3: per-UNIT 归属 + MOLAR/WEIGHT 基准 + 翻页（PoC → 全量）

在 SIM-38a PoC（块解析）之上的增量：
- UnitTrayCompositions：UNIT 头归属 + basis（MOLAR/WEIGHT）
- 全文解析：翻页（页内 (CONT) UNIT 头不切断 section）；
  非 (CONT) UNIT 头 / 基准切换 / 其他 TRAY 段标题 → 结束当前 section
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_tray_compositions_parser import (
    UnitTrayCompositions,
    parse_tray_compositions,
)

SAMPLE_DMC = Path(__file__).resolve().parents[3] / "sample" / "dmc.out"
SAMPLE_OLD = Path(__file__).resolve().parents[3] / "sample" / "proii .out"


FULL_TEXT = """
                      UNIT 19, 'T102'  (CONT)

 TRAY MOLAR COMPOSITIONS

                               TRAY 1                      TRAY 2
     COMPONENT              X          Y                X          Y
                       ----------  ----------      ----------  ----------
    1 H2O                 0.00000     0.00000         0.00000     0.00000
    2 PO               7.6544E-04     0.02855      4.7646E-06     0.00135

  RATE, KG-MOL/HR           12.04    2.59E-01           15.81       12.30


 SIMULATION SCIENCES INC.               R                             PAGE P-39
 PROJECT  DMC                     PRO/II  VERSION 5.01                   386/EM
 PROBLEM  Reactor Dist                   OUTPUT                    TIANXIAOLING
                                     COLUMN SUMMARY                    02/18/99
 ==============================================================================

                            UNIT 19, 'T102'  (CONT)

                               TRAY 3                      TRAY 4
     COMPONENT              X          Y                X          Y
                       ----------  ----------      ----------  ----------
    1 H2O                 0.00000     0.00000         0.00000     0.00000
    2 PO               1.6211E-06  4.6525E-04      1.6183E-06  4.5948E-04

  RATE, KG-MOL/HR           15.90       16.07           15.92       16.16


 TRAY WEIGHT COMPOSITIONS

                               TRAY 1                      TRAY 2
     COMPONENT              X          Y                X          Y
                       ----------  ----------      ----------  ----------
    1 H2O                 0.00000     0.00000         0.00000     0.00000

  RATE, KG/HR            2096.146   8.026E-21        1923.013    2096.146
"""


# ============================================================================
# 全量集成契约
# ============================================================================


def test_full_parse_unit_and_basis():
    """单 UNIT：MOLAR + WEIGHT 两个 section（unit 元数据 + basis）。"""
    entries = parse_tray_compositions(FULL_TEXT)
    assert len(entries) == 2
    molar = entries[0]
    assert molar.unit_no == "19"
    assert molar.unit_name == "T102"
    assert molar.basis == "MOLAR"
    weight = entries[1]
    assert weight.basis == "WEIGHT"


def test_full_parse_pagination_continues_blocks():
    """翻页：页内 (CONT) UNIT 头不切断 section，块跨页累计。"""
    entries = parse_tray_compositions(FULL_TEXT)
    molar = entries[0]
    # TRAY 1-2（页内）+ TRAY 3-4（翻页后）= 2 块
    assert len(molar.blocks) == 2
    assert molar.blocks[0].tray_numbers == [1, 2]
    assert molar.blocks[1].tray_numbers == [3, 4]


def test_full_parse_new_unit_ends_section():
    """非 (CONT) UNIT 头 → 结束当前 section（新 unit 的段开始）。"""
    text = FULL_TEXT + "\n UNIT 20, 'T103'\n\n TRAY MOLAR COMPOSITIONS\n"
    entries = parse_tray_compositions(text)
    assert len(entries) == 3
    assert entries[2].unit_no == "20"
    assert entries[2].unit_name == "T103"


def test_full_parse_no_compositions_returns_empty():
    """无 COMPOSITIONS → 空 list。"""
    assert parse_tray_compositions("") == []
    assert parse_tray_compositions("COLUMN SUMMARY\nTRAY SIZING RESULTS") == []


# ============================================================================
# 真 fixture 验证
# ============================================================================


def test_real_fixture_dmc_t102_both_bases():
    """真 fixture dmc.out：T102 MOLAR + WEIGHT 双 section。"""
    if not SAMPLE_DMC.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_DMC}")

    text = SAMPLE_DMC.read_text(encoding="utf-8", errors="replace")
    entries = parse_tray_compositions(text)
    t102 = [e for e in entries if e.unit_name == "T102"]
    bases = {e.basis for e in t102}
    assert bases == {"MOLAR", "WEIGHT"}
    molar = next(e for e in t102 if e.basis == "MOLAR")
    # 首块 14 组件（与 PoC fixture 一致）
    assert molar.blocks[0].tray_numbers == [1, 2]
    assert len(molar.blocks[0].rows) == 14


def test_real_fixture_old_t1_repeated():
    """真 fixture proii .out：T1 双基准（MOLAR+WEIGHT）重复报告 ×2 = 4 section。"""
    if not SAMPLE_OLD.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_OLD}")

    text = SAMPLE_OLD.read_text(encoding="utf-8", errors="replace")
    entries = parse_tray_compositions(text)
    # 实际输出：T1 MOLAR/WEIGHT 对出现 2 次（重复报告），无 T2/T3 section
    assert len(entries) == 4
    assert all(e.unit_name == "T1" for e in entries)
    bases = [e.basis for e in entries]
    assert bases == ["MOLAR", "WEIGHT", "MOLAR", "WEIGHT"]
    # 首块与 PoC fixture 一致（2 组件）
    assert entries[0].blocks[0].tray_numbers == [1, 2]
    assert len(entries[0].blocks[0].rows) == 2


# ============================================================================
# 数据类契约
# ============================================================================


def test_unit_tray_compositions_dataclass_fields():
    """UnitTrayCompositions 字段：unit_no/unit_name/unit_desc/basis/blocks。"""
    e = UnitTrayCompositions(
        unit_no="19", unit_name="T102", basis="MOLAR", blocks=[],
    )
    assert e.basis == "MOLAR"
    assert e.blocks == []
