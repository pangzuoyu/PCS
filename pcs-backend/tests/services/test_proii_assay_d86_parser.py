"""P3.x SIM-37b/1: PRO/II 8.x 炼油版全量解析 — ASSAY + D86。

Part 1/3（6 parser 总任务拆 3 commit）：
- commit 1: ASSAY（输入数据声明）+ D86（ASTM D86 蒸馏曲线输出）

格式参考（spec V1.1 §3.3.X + sample/200FlexiCoking1.out）：
- ASSAY 声明：
    ASSAY CONVERSION=API94, CURVEFIT=IMPROVED, KVRECONCILE=TAILS
    CUTPOINTS TBPCUTS=30,650,23,DEFAULT
  含 CONVERSION/CURVEFIT/KVRECONCILE + 可选 CUTPOINTS TBPCUTS=
- D86 蒸馏曲线：
    D86 STREAM=1NAPHTHA, DATA=0,50/5,57/10,62/20,..., TEMP=C
  - DATA 第一个数为起始 vol%（恒 0），后续「temp/vol」对
  - 跨行 `&` + 下一行缩进续行
  - TEMP=C/F 显式单位（缺省 C）

Parser 产物：
- AssayDeclaration（conversion/curve_fit/kv_reconcile/cut_points_tbp_cuts/cut_points_default）
- D86Curve（stream_id/temp_unit/points 升序）
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_assay_d86_parser import (
    AssayDeclaration,
    D86Curve,
    parse_assay_declarations,
    parse_d86_curves,
)

# ============================================================================
# ASSAY 声明契约（spec V1.1 §3.3.X）
# ============================================================================


def test_assay_parse_minimal_declaration():
    """ASSAY 行仅含 CONVERSION（最简声明）。"""
    text = "  ASSAY CONVERSION=API94\n"
    assays = parse_assay_declarations(text)
    assert len(assays) == 1
    a = assays[0]
    assert a.conversion == "API94"
    assert a.curve_fit is None
    assert a.kv_reconcile is None
    assert a.cut_points_tbp_cuts is None
    assert a.cut_points_default is False


def test_assay_parse_full_declaration():
    """ASSAY 行 + CUTPOINTS TBPCUTS=30,650,23,DEFAULT 完整声明。"""
    text = """
  ASSAY CONVERSION=API94, CURVEFIT=IMPROVED, KVRECONCILE=TAILS
  CUTPOINTS TBPCUTS=30,650,23,DEFAULT
"""
    assays = parse_assay_declarations(text)
    assert len(assays) == 1
    a = assays[0]
    assert a.conversion == "API94"
    assert a.curve_fit == "IMPROVED"
    assert a.kv_reconcile == "TAILS"
    assert a.cut_points_tbp_cuts == [30, 650, 23]
    assert a.cut_points_default is True


def test_assay_parse_no_cutpoints_default_false():
    """CUTPOINTS TBPCUTS= 缺省时 cut_points_default=False。"""
    text = """
  ASSAY CONVERSION=ASTM86, CURVEFIT=NONE
  CUTPOINTS TBPCUTS=10,30,100,200,300
"""
    assays = parse_assay_declarations(text)
    assert len(assays) == 1
    a = assays[0]
    assert a.conversion == "ASTM86"
    assert a.curve_fit == "NONE"
    assert a.cut_points_tbp_cuts == [10, 30, 100, 200, 300]
    assert a.cut_points_default is False


def test_assay_parse_multiple_declarations():
    """多段 ASSAY 声明共存（通常不应出现，但允许）。"""
    text = """
  ASSAY CONVERSION=API94
THERMODYNAMIC DATA
  METHOD SYSTEM=SRK
  ASSAY CONVERSION=ASTM86, CURVEFIT=IMPROVED
"""
    assays = parse_assay_declarations(text)
    assert len(assays) == 2
    assert assays[0].conversion == "API94"
    assert assays[1].conversion == "ASTM86"


def test_assay_parse_empty_text_returns_empty_list():
    """无 ASSAY 段 → 空 list。"""
    assert parse_assay_declarations("nothing here") == []
    assert parse_assay_declarations("") == []


def test_assay_parse_case_insensitive():
    """assay 关键字大小写不敏感。"""
    text = "assay conversion=API94"
    assays = parse_assay_declarations(text)
    assert len(assays) == 1
    assert assays[0].conversion == "API94"


# ============================================================================
# D86 蒸馏曲线契约（spec V1.1 §3.3.X）
# ============================================================================


def test_d86_parse_basic_curve():
    """D86 STREAM=... DATA=vol/temp pairs, TEMP=C 单段。"""
    text = "    D86 STREAM=1NAPHTHA, DATA=0,50/5,57/10,62/20,77/30, TEMP=C"
    curves = parse_d86_curves(text)
    assert len(curves) == 1
    c = curves[0]
    assert c.stream_id == "1NAPHTHA"
    assert c.temp_unit == "C"
    # points: [(50, 5), (57, 10), (62, 20), (77, 30)]
    assert c.points == [(50.0, 5.0), (57.0, 10.0), (62.0, 20.0), (77.0, 30.0)]


def test_d86_parse_with_continuation():
    """D86 行尾 `&` + 下一行缩进续行（PRO/II 长曲线标准格式）。"""
    text = """    D86 STREAM=1NAPHTHA, DATA=0,50/5,57/10,62/20,77/30,89/40,101/ &
        50,112/60,124/70,137/80,151/90,166/95,176/100,190, TEMP=C"""
    curves = parse_d86_curves(text)
    assert len(curves) == 1
    c = curves[0]
    # 跨行拼接 DATA=0,50/5,...,101/50,112/60,...,190, TEMP=C
    # 完整序列：(50,5),(57,10),...,(176,100),(190,100)
    assert len(c.points) == 13
    assert c.points[0] == (50.0, 5.0)
    assert c.points[-1] == (190.0, 100.0) or c.points[-1][0] == 190.0
    # 末尾孤立 vol=100, temp=190 后即 100%
    assert c.points[-1][1] == 100.0


def test_d86_parse_multiple_streams():
    """D86 多物流共存。"""
    text = """
    D86 STREAM=1NAPHTHA, DATA=0,50/5, TEMP=C
    D86 STREAM=1LCO, DATA=0,204/5,220/10, TEMP=C
"""
    curves = parse_d86_curves(text)
    assert len(curves) == 2
    assert curves[0].stream_id == "1NAPHTHA"
    assert curves[1].stream_id == "1LCO"
    assert curves[1].points[0] == (204.0, 5.0)


def test_d86_parse_temp_unit_fahrenheit():
    """TEMP=F 华氏度单位识别。"""
    text = "  D86 STREAM=1FEED, DATA=0,122/5,140/10, TEMP=F"
    curves = parse_d86_curves(text)
    assert len(curves) == 1
    assert curves[0].temp_unit == "F"


def test_d86_parse_temp_unit_default_celsius():
    """TEMP 缺省 → C。"""
    text = "  D86 STREAM=1FEED, DATA=0,50/5,57/10"
    curves = parse_d86_curves(text)
    assert len(curves) == 1
    assert curves[0].temp_unit == "C"


def test_d86_parse_empty_text_returns_empty_list():
    """无 D86 段 → 空 list。"""
    assert parse_d86_curves("nothing") == []
    assert parse_d86_curves("") == []


def test_d86_parse_case_insensitive():
    """d86 关键字大小写不敏感。"""
    text = "  d86 stream=1NAPHTHA, DATA=0,50/5, TEMP=C"
    curves = parse_d86_curves(text)
    assert len(curves) == 1
    assert curves[0].stream_id == "1NAPHTHA"


# ============================================================================
# 真 fixture 验证：sample/200FlexiCoking1.out
# ============================================================================


SAMPLE_FILE = Path(__file__).resolve().parents[3] / "sample" / "200FlexiCoking1.out"


def test_real_fixture_assay_declaration_found():
    """真 fixture：ASSAY CONVERSION=API94 声明。"""
    if not SAMPLE_FILE.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FILE}")

    text = SAMPLE_FILE.read_text(encoding="utf-8", errors="replace")
    assays = parse_assay_declarations(text)
    assert len(assays) >= 1
    a = assays[0]
    assert a.conversion == "API94"
    assert a.curve_fit == "IMPROVED"
    assert a.kv_reconcile == "TAILS"
    assert a.cut_points_tbp_cuts == [30, 650, 23]
    assert a.cut_points_default is True


def test_real_fixture_d86_curves_count():
    """真 fixture：D86 曲线 ≥2 条（NAPHTHA + LCO）。"""
    if not SAMPLE_FILE.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FILE}")

    text = SAMPLE_FILE.read_text(encoding="utf-8", errors="replace")
    curves = parse_d86_curves(text)
    # 200FlexiCoking1.out 含 1NAPHTHA + 1LCO 两条 D86
    assert len(curves) >= 2
    stream_ids = {c.stream_id for c in curves}
    assert "1NAPHTHA" in stream_ids
    assert "1LCO" in stream_ids


def test_real_fixture_d86_naphtha_complete():
    """真 fixture：1NAPHTHA D86 完整曲线（13 个点 IBP~FBP）。"""
    if not SAMPLE_FILE.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FILE}")

    text = SAMPLE_FILE.read_text(encoding="utf-8", errors="replace")
    curves = parse_d86_curves(text)
    naphtha = next(c for c in curves if c.stream_id == "1NAPHTHA")
    # DATA=0,50/5,57/10,...,190（13 个点：5/10/20/30/40/50/60/70/80/90/95/100 + 0 + 100%末端）
    assert len(naphtha.points) >= 12
    assert naphtha.temp_unit == "C"
    # 单调性校验（温度随 vol% 单调递增）
    temps = [t for t, v in naphtha.points]
    assert temps == sorted(temps)
    vols = [v for t, v in naphtha.points]
    assert vols == sorted(vols)


# ============================================================================
# 数据类契约
# ============================================================================


def test_assay_declaration_dataclass_fields():
    """AssayDeclaration 字段：5 个（conversion/curve_fit/kv_reconcile/
    cut_points_tbp_cuts/cut_points_default）。"""
    a = AssayDeclaration(
        conversion="API94",
        curve_fit="IMPROVED",
        kv_reconcile="TAILS",
        cut_points_tbp_cuts=[30, 650, 23],
        cut_points_default=True,
    )
    assert a.conversion == "API94"
    assert a.cut_points_default is True


def test_d86_curve_dataclass_fields():
    """D86Curve 字段：3 个（stream_id/temp_unit/points）。"""
    c = D86Curve(stream_id="1NAPHTHA", temp_unit="C", points=[(50.0, 5.0)])
    assert c.stream_id == "1NAPHTHA"
    assert c.temp_unit == "C"
    assert c.points == [(50.0, 5.0)]