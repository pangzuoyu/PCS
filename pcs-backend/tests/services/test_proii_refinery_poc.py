"""P3.x SIM-37a: PRO/II 8.x 炼油版 PoC（关键字识别 + 1 fixture 验证估时）。

PoC 范围：识别 PRO/II 8.x 炼油版报告中的 7 类关键字
- ASSAY（输入数据声明）
- D86（ASTM D86 蒸馏曲线）
- TBP（实沸点蒸馏曲线）
- LIGHTEND（轻端分析）
- REFSTREAM（参考物流）
- TRAY SIZING（塔盘尺寸计算）
- REFINERY PROCESSOR（炼油处理器属性集）
- 附：STREAM TBP/ASTM CURVES（输出段）

PoC 产物：RefinerySectionDetector.detect(file_path) → RefineryReport dataclass
- 仅关键字识别（不做深度解析；深度解析留待 SIM-37b）
- 1 fixture 验证估时：sample/200FlexiCoking1.out
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_refinery_poc import (
    REFINERY_SECTION_KEYWORDS,
    RefineryReport,
    RefinerySection,
    RefinerySectionDetector,
)

# ============================================================================
# Section 关键字枚举契约（spec V1.1 §3.3.X）
# ============================================================================


def test_refinery_section_enum_has_eight_keywords():
    """8 个关键字（ASSAY/D86/TBP/LIGHTEND/REFSTREAM/TRAY_SIZING/
    REFINERY_PROCESSOR/TBP_ASTM_CURVES）。"""
    assert len(RefinerySection) == 8
    assert RefinerySection.ASSAY.value == "ASSAY"
    assert RefinerySection.D86.value == "D86"
    assert RefinerySection.TBP.value == "TBP"
    assert RefinerySection.LIGHTEND.value == "LIGHTEND"
    assert RefinerySection.REFSTREAM.value == "REFSTREAM"
    assert RefinerySection.TRAY_SIZING.value == "TRAY_SIZING"
    assert RefinerySection.REFINERY_PROCESSOR.value == "REFINERY_PROCESSOR"
    assert RefinerySection.TBP_ASTM_CURVES.value == "TBP_ASTM_CURVES"


def test_refinery_section_keywords_match_enum():
    """REFINERY_SECTION_KEYWORDS 关键字表与枚举一一对应。"""
    assert set(REFINERY_SECTION_KEYWORDS.keys()) == set(RefinerySection)


# ============================================================================
# detect() — 关键字识别
# ============================================================================


@pytest.mark.parametrize(
    "keyword,section",
    [
        ("ASSAY CONVERSION=API94", RefinerySection.ASSAY),
        ("D86 STREAM=1NAPHTHA, DATA=0,50/5", RefinerySection.D86),
        ("TBP STREAM=1SLURRYR, DATA=0,400", RefinerySection.TBP),
        ("LIGHTEND", RefinerySection.LIGHTEND),
        ("REFSTREAM", RefinerySection.REFSTREAM),
        ("TRAY SIZING", RefinerySection.TRAY_SIZING),
        ("REFINERY PROCESSOR PROPERTIES SET", RefinerySection.REFINERY_PROCESSOR),
        ("STREAM TBP/ASTM CURVES", RefinerySection.TBP_ASTM_CURVES),
    ],
)
def test_detect_keyword_recognized(keyword, section):
    """每类关键字单独命中 → section 列表包含对应枚举。"""
    text = f"some header\n  {keyword}\nrest"
    report = RefinerySectionDetector.detect_from_text(text)
    assert section in report.sections
    assert report.counts[section] >= 1


def test_detect_returns_unique_section_set():
    """detect 返回 sections 是 set（同一 section 多行去重）。"""
    text = """
    ASSAY CONVERSION=API94
    D86 STREAM=1NAPHTHA
    D86 STREAM=1LCO
    TBP STREAM=1SLURRYR
    TRAY SIZING
    TRAY SIZING (Cont)
    """
    report = RefinerySectionDetector.detect_from_text(text)
    assert report.sections == {
        RefinerySection.ASSAY,
        RefinerySection.D86,
        RefinerySection.TBP,
        RefinerySection.TRAY_SIZING,
    }


def test_detect_case_insensitive():
    """detect 大小写不敏感（PRO/II 关键字常大写）。"""
    text = "assay conversion=API94\nd86 stream=1naphtha"
    report = RefinerySectionDetector.detect_from_text(text)
    assert RefinerySection.ASSAY in report.sections
    assert RefinerySection.D86 in report.sections


def test_detect_no_refinery_section_returns_empty_report():
    """纯化工报告（无炼油关键字）→ sections 为空。"""
    text = """
    FLASH DRUM SUMMARY
    COLUMN SUMMARY
    UNIT 5, 'T204B'
    """
    report = RefinerySectionDetector.detect_from_text(text)
    assert report.sections == set()
    assert report.has_refinery is False


# ============================================================================
# has_refinery 便捷属性
# ============================================================================


def test_has_refinery_true_when_any_section_present():
    """has_refinery = sections 非空。"""
    text = "ASSAY CONVERSION=API94"
    report = RefinerySectionDetector.detect_from_text(text)
    assert report.has_refinery is True


def test_has_refinery_false_when_no_section():
    text = "no refinery"
    report = RefinerySectionDetector.detect_from_text(text)
    assert report.has_refinery is False


# ============================================================================
# counts — 关键字出现次数（多页 TRAY SIZING 计数）
# ============================================================================


def test_counts_multiple_occurrences():
    """counts 记录每类关键字出现次数（TRAY SIZING 多页）。"""
    text = """
    TRAY SIZING
    TRAY SIZING
    TRAY SIZING (Cont)
    TRAY SIZING (Cont)
    """
    report = RefinerySectionDetector.detect_from_text(text)
    assert report.counts[RefinerySection.TRAY_SIZING] == 4


# ============================================================================
# line_numbers — 关键字首现行号（调试定位用）
# ============================================================================


def test_line_numbers_recorded_for_each_section():
    """line_numbers 记录每类关键字首现行号（1-based）。"""
    text = "\n\nASSAY\n\nD86\n\nTBP\n"
    report = RefinerySectionDetector.detect_from_text(text)
    assert report.line_numbers[RefinerySection.ASSAY] == 3
    assert report.line_numbers[RefinerySection.D86] == 5
    assert report.line_numbers[RefinerySection.TBP] == 7


# ============================================================================
# 真 fixture 验证：sample/200FlexiCoking1.out（PRO/II 8.1.3 FCC 报告）
# ============================================================================


SAMPLE_FILE = Path(__file__).resolve().parents[3] / "sample" / "200FlexiCoking1.out"


def test_real_fixture_200flexicoking_detects_all_sections():
    """真 fixture：200FlexiCoking1.out 含 6 类关键字（除 LIGHTEND/REFSTREAM 外全识别）。"""
    if not SAMPLE_FILE.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FILE}")

    report = RefinerySectionDetector.detect_from_file(SAMPLE_FILE)
    # 200FlexiCoking1.out 关键字识别（FCC 报告）
    expected_present = {
        RefinerySection.ASSAY,
        RefinerySection.D86,
        RefinerySection.TBP,
        RefinerySection.TRAY_SIZING,
        RefinerySection.REFINERY_PROCESSOR,
        RefinerySection.TBP_ASTM_CURVES,
    }
    assert expected_present.issubset(report.sections)
    assert report.has_refinery is True
    # TRAY SIZING 多页（FCC 主分馏/汽提/吸收/解吸等多塔）
    assert report.counts[RefinerySection.TRAY_SIZING] >= 5


def test_real_fixture_tbp_curve_section_present():
    """真 fixture：STREAM TBP/ASTM CURVES 段。"""
    if not SAMPLE_FILE.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FILE}")

    report = RefinerySectionDetector.detect_from_file(SAMPLE_FILE)
    assert RefinerySection.TBP_ASTM_CURVES in report.sections


def test_real_fixture_refinery_processor_section_present():
    """真 fixture：REFINERY PROCESSOR PROPERTIES SET 段。"""
    if not SAMPLE_FILE.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FILE}")

    report = RefinerySectionDetector.detect_from_file(SAMPLE_FILE)
    assert RefinerySection.REFINERY_PROCESSOR in report.sections


# ============================================================================
# RefineryReport dataclass 契约
# ============================================================================


def test_refinery_report_dataclass_fields():
    """RefineryReport 字段：sections/counts/line_numbers/source_file。"""
    rpt = RefineryReport(
        sections={RefinerySection.ASSAY},
        counts={RefinerySection.ASSAY: 1},
        line_numbers={RefinerySection.ASSAY: 10},
        source_file="/tmp/foo.out",
    )
    assert RefinerySection.ASSAY in rpt.sections
    assert rpt.has_refinery is True
    assert rpt.source_file == "/tmp/foo.out"


def test_refinery_report_to_dict():
    """RefineryReport.to_dict() → JSON 序列化友好。"""
    rpt = RefineryReport(
        sections={RefinerySection.ASSAY, RefinerySection.D86},
        counts={RefinerySection.ASSAY: 2, RefinerySection.D86: 3},
        line_numbers={RefinerySection.ASSAY: 1, RefinerySection.D86: 5},
        source_file="x.out",
    )
    d = rpt.to_dict()
    assert d["sections"] == ["ASSAY", "D86"]
    assert d["counts"]["ASSAY"] == 2
    assert d["counts"]["D86"] == 3
    assert d["line_numbers"]["ASSAY"] == 1
    assert d["source_file"] == "x.out"
    assert d["has_refinery"] is True
