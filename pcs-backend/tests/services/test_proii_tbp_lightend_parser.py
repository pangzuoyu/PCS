"""P3.x SIM-37b/2: PRO/II 8.x 炼油版全量解析 — TBP + LIGHTEND。

Part 2/3（6 parser 拆 3 commit）：
- commit 2: TBP（实沸点蒸馏曲线）+ LIGHTEND（轻端分析）

格式参考（sample/200FlexiCoking1.out + huafeng140_FCC2015.out）：
- TBP 输入声明（与 D86 同构）：
    TBP STREAM=1SLURRYR, DATA=0,400/10,430/30,...,95,698, TEMP=C
  - DATA 首 token 起始 vol%（可非 0，如 huafeng FO1 DATA=5,...）
- LIGHTEND 轻端分析：
    LIGHTEND STREAM=1C, COMPOSITION(WT)=19,0.9/20,4.51/.../26,0.41, &
         PERCENT(WT)=17.51, NORMALIZE
  - 组件对 comp_id,value（/ 分隔）
  - 可选 PERCENT(WT)=（轻端总质量百分数）+ NORMALIZE 关键字
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_tbp_lightend_parser import (
    LightendComposition,
    TBPCurve,
    parse_lightend_compositions,
    parse_tbp_curves,
)

SAMPLE_FCC = Path(__file__).resolve().parents[3] / "sample" / "200FlexiCoking1.out"
SAMPLE_HF = Path(__file__).resolve().parents[3] / "sample" / "huafeng140_FCC2015.out"


# ============================================================================
# TBP 蒸馏曲线契约
# ============================================================================


def test_tbp_parse_basic_curve():
    """TBP STREAM=... DATA=temp/vol 对，TEMP=C。"""
    text = "    TBP STREAM=1SLURRYR, DATA=0,400/10,430/30,480/50,550, TEMP=C"
    curves = parse_tbp_curves(text)
    assert len(curves) == 1
    c = curves[0]
    assert c.stream_id == "1SLURRYR"
    assert c.temp_unit == "C"
    assert c.points == [(400.0, 10.0), (430.0, 30.0), (480.0, 50.0), (550.0, 100.0)]


def test_tbp_parse_with_continuation():
    """TBP 行尾 `&` 续行（200FlexiCoking1 1SLURRYR 完整 8 点）。"""
    text = """    TBP STREAM=1SLURRYR, DATA=0,400/10,430/30,480/50,550/70,607/ &
        80,630/90,658/95,698, TEMP=C"""
    curves = parse_tbp_curves(text)
    assert len(curves) == 1
    c = curves[0]
    assert len(c.points) == 8
    assert c.points[0] == (400.0, 10.0)
    assert c.points[-1] == (698.0, 100.0)


def test_tbp_parse_nonzero_initial_vol():
    """DATA 首 token 起始 vol% 可非 0（huafeng FO1 DATA=5,322/...）。"""
    text = """    TBP STREAM=FO1, DATA=5,322/10,352/20,381/30,402/40,428/50,453/ &
        55,506, TEMP=C"""
    curves = parse_tbp_curves(text)
    assert len(curves) == 1
    c = curves[0]
    # 首 token 5（起始 vol%）跳过；points 从 (322,10) 起
    assert c.points[0] == (322.0, 10.0)
    assert c.points[-1] == (506.0, 100.0)
    assert len(c.points) == 7


def test_tbp_parse_temp_unit_fahrenheit():
    """TEMP=F 识别。"""
    text = "  TBP STREAM=1FEED, DATA=0,300/10,400, TEMP=F"
    curves = parse_tbp_curves(text)
    assert curves[0].temp_unit == "F"


def test_tbp_parse_temp_unit_default_celsius():
    """TEMP 缺省 → C。"""
    text = "  TBP STREAM=1FEED, DATA=0,300/10,400"
    curves = parse_tbp_curves(text)
    assert curves[0].temp_unit == "C"


def test_tbp_parse_multiple_streams():
    """多 TBP 共存。"""
    text = """
    TBP STREAM=A, DATA=0,100/10,150, TEMP=C
    TBP STREAM=B, DATA=0,200/10,250, TEMP=C
"""
    curves = parse_tbp_curves(text)
    assert len(curves) == 2
    assert {c.stream_id for c in curves} == {"A", "B"}


def test_tbp_parse_empty_text_returns_empty_list():
    """无 TBP → 空 list；D86 行不误吃。"""
    assert parse_tbp_curves("") == []
    assert parse_tbp_curves("  D86 STREAM=1NAPHTHA, DATA=0,50/5, TEMP=C") == []


def test_tbp_parse_case_insensitive():
    """tbp 关键字大小写不敏感。"""
    text = "  tbp stream=1FEED, DATA=0,300/10,400, TEMP=C"
    curves = parse_tbp_curves(text)
    assert len(curves) == 1
    assert curves[0].stream_id == "1FEED"


# ============================================================================
# LIGHTEND 轻端分析契约
# ============================================================================


def test_lightend_parse_full():
    """LIGHTEND 完整格式：COMPOSITION(WT) 组件对 + PERCENT(WT) + NORMALIZE。"""
    text = """    LIGHTEND STREAM=1C, COMPOSITION(WT)=19,0.9/20,4.51/21,1.19/ &
        22,2.93/23,1.58/24,2.1/25,3.89/26,0.41, &
         PERCENT(WT)=17.51, NORMALIZE"""
    comps = parse_lightend_compositions(text)
    assert len(comps) == 1
    le = comps[0]
    assert le.stream_id == "1C"
    assert le.basis == "WT"
    assert le.components == [
        (19, 0.9), (20, 4.51), (21, 1.19), (22, 2.93),
        (23, 1.58), (24, 2.1), (25, 3.89), (26, 0.41),
    ]
    assert le.percent_wt == pytest.approx(17.51)
    assert le.normalized is True


def test_lightend_parse_minimal():
    """仅 COMPOSITION（无 PERCENT/NORMALIZE）。"""
    text = "  LIGHTEND STREAM=1C, COMPOSITION(WT)=19,0.9/20,4.51"
    comps = parse_lightend_compositions(text)
    assert len(comps) == 1
    le = comps[0]
    assert le.stream_id == "1C"
    assert le.components == [(19, 0.9), (20, 4.51)]
    assert le.percent_wt is None
    assert le.normalized is False


def test_lightend_parse_percent_without_normalize():
    """PERCENT(WT) 有但 NORMALIZE 无。"""
    text = "  LIGHTEND STREAM=1C, COMPOSITION(WT)=19,0.9, PERCENT(WT)=5.0"
    comps = parse_lightend_compositions(text)
    assert comps[0].percent_wt == pytest.approx(5.0)
    assert comps[0].normalized is False


def test_lightend_parse_empty_text_returns_empty_list():
    """无 LIGHTEND → 空 list。"""
    assert parse_lightend_compositions("") == []
    assert parse_lightend_compositions("no lightend here") == []


def test_lightend_parse_case_insensitive():
    """lightend 关键字大小写不敏感。"""
    text = "  lightend stream=1C, COMPOSITION(WT)=19,0.9"
    comps = parse_lightend_compositions(text)
    assert len(comps) == 1
    assert comps[0].stream_id == "1C"


# ============================================================================
# 真 fixture 验证
# ============================================================================


def test_real_fixture_fcc_tbp_slurryr():
    """真 fixture 200FlexiCoking1：1SLURRYR TBP 8 点 + 单调性。"""
    if not SAMPLE_FCC.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FCC}")

    text = SAMPLE_FCC.read_text(encoding="utf-8", errors="replace")
    curves = parse_tbp_curves(text)
    slurry = next(c for c in curves if c.stream_id == "1SLURRYR")
    assert len(slurry.points) == 8
    assert slurry.temp_unit == "C"
    temps = [t for t, v in slurry.points]
    vols = [v for t, v in slurry.points]
    assert temps == sorted(temps)
    assert vols == sorted(vols)


def test_real_fixture_huafeng_lightend():
    """真 fixture huafeng140：LIGHTEND 1C 8 组件 + PERCENT 17.51 + NORMALIZE。"""
    if not SAMPLE_HF.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_HF}")

    text = SAMPLE_HF.read_text(encoding="utf-8", errors="replace")
    comps = parse_lightend_compositions(text)
    assert len(comps) >= 1
    le = next(c for c in comps if c.stream_id == "1C")
    assert len(le.components) == 8
    assert le.percent_wt == pytest.approx(17.51)
    assert le.normalized is True


def test_real_fixture_huafeng_tbp_fo1():
    """真 fixture huafeng140：FO1 TBP 7 点（起始 vol%=5）。"""
    if not SAMPLE_HF.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_HF}")

    text = SAMPLE_HF.read_text(encoding="utf-8", errors="replace")
    curves = parse_tbp_curves(text)
    fo1 = next(c for c in curves if c.stream_id == "FO1")
    assert fo1.points[0] == (322.0, 10.0)
    assert fo1.points[-1] == (506.0, 100.0)


# ============================================================================
# 数据类契约
# ============================================================================


def test_tbp_curve_dataclass_fields():
    """TBPCurve 字段：3 个（stream_id/temp_unit/points）。"""
    c = TBPCurve(stream_id="1SLURRYR", temp_unit="C", points=[(400.0, 10.0)])
    assert c.stream_id == "1SLURRYR"
    assert c.points == [(400.0, 10.0)]


def test_lightend_dataclass_fields():
    """LightendComposition 字段：5 个。"""
    le = LightendComposition(
        stream_id="1C",
        basis="WT",
        components=[(19, 0.9)],
        percent_wt=17.51,
        normalized=True,
    )
    assert le.basis == "WT"
    assert le.normalized is True
