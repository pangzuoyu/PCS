"""P3.x SIM-38b/2: 塔盘数据全量 — TRAY RATING RESULTS（双版本格式）。

Part 2/3（SIM-38b 拆 3 commit）：
- commit 2: TRAY RATING RESULTS

两版本格式：
- PRO/II 4.17（proii .out）：TRAY RATING RESULTS，9 列
  TRAY VAPOR LIQUID VLOAD DIAM FF PRES_DROP GPM/LWI BACKUP_PCT
    1   25.63  15.9  .956  900.0 57.8  .005   1.0    26.08
- PRO/II 8.x（200FlexiCoking1.out）：TRAY RATING AT SELECTED DESIGN TRAY，10 列（多 NP）
  TRAY VAPOR LIQUID VLOAD DIAM FF NP PRES_DROP RATE BACKUP_PCT
    1   0.342 0.08638 0.091 2743. 41.7 2 0.000 18.027 39.51

单位不同（CFS/HOTGPM vs M3/S）不区分，仅取数值。
"""
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_tray_rating_parser import (
    TrayRatingRow,
    UnitTrayRating,
    parse_tray_rating,
)

SAMPLE_FCC = Path(__file__).resolve().parents[3] / "sample" / "200FlexiCoking1.out"
SAMPLE_OLD = Path(__file__).resolve().parents[3] / "sample" / "proii .out"


RATING_9COL = """
                      UNIT 8, 'T01'  (CONT)

 TRAY RATING RESULTS

                                             PRES              DOWNCOMER
  TRAY  VAPOR  LIQUID  VLOAD   DIAM    FF    DROP  GPM/LWI    BACKUP, PCT
         CFS   HOTGPM   CFS     MM          KG/CM2 GPM/IN     TRAY SPACING
  ----  -----  ------  -----  ------  ----  ------ --------   ------------
    1   25.63    15.9   .956   900.0  57.8    .005     1.0        26.08
    2   31.26   112.8  1.105   900.0  98.2    .009     4.1        40.96
"""

RATING_10COL = """
                      UNIT 5, 'T204B', 'STRIPPER'  (Cont)

 TRAY RATING AT SELECTED DESIGN TRAY

                                               PRES     WEIR     DOWNCOMER
  TRAY  VAPOR  LIQUID  VLOAD   DIAM   FF  NP   DROP     RATE    BACKUP, PCT
         M3/S   M3/S    M3/S    MM             MPA    CM3/S/MM  TRAY SPACING
  ----  ----- -------  -----   ----  ---- --  ------  --------  ------------
    1   0.342 0.08638  0.091  2743.  41.7  2   0.000   18.027       39.51
    2   0.407 0.09498  0.114  2743.  49.5  2   0.001   19.822       42.78
"""


# ============================================================================
# 9 列格式（4.17）
# ============================================================================


def test_rating_9col_parse():
    """4.17 格式：9 列行解析，np=None。"""
    units = parse_tray_rating(RATING_9COL)
    assert len(units) == 1
    u = units[0]
    assert u.unit_no == "8"
    assert u.unit_name == "T01"
    assert len(u.rows) == 2
    r = u.rows[0]
    assert r.tray == 1
    assert r.vapor_rate == pytest.approx(25.63)
    assert r.liquid_rate == pytest.approx(15.9)
    assert r.vload == pytest.approx(0.956)
    assert r.diameter_mm == pytest.approx(900.0)
    assert r.ff == pytest.approx(57.8)
    assert r.pres_drop == pytest.approx(0.005)
    assert r.weir_rate == pytest.approx(1.0)
    assert r.backup_pct == pytest.approx(26.08)
    assert r.np is None


# ============================================================================
# 10 列格式（8.x）
# ============================================================================


def test_rating_10col_parse():
    """8.x 格式：10 列行解析（NP 在 FF 后）。"""
    units = parse_tray_rating(RATING_10COL)
    assert len(units) == 1
    u = units[0]
    assert u.unit_name == "T204B"
    assert u.unit_desc == "STRIPPER"
    assert len(u.rows) == 2
    r = u.rows[0]
    assert r.tray == 1
    assert r.vapor_rate == pytest.approx(0.342)
    assert r.liquid_rate == pytest.approx(0.08638)
    assert r.vload == pytest.approx(0.091)
    assert r.diameter_mm == pytest.approx(2743.0)
    assert r.ff == pytest.approx(41.7)
    assert r.np == 2
    assert r.pres_drop == pytest.approx(0.000)
    assert r.weir_rate == pytest.approx(18.027)
    assert r.backup_pct == pytest.approx(39.51)


def test_rating_no_section_returns_empty():
    """无 RATING 段 → 空 list；SIZING RESULTS 不误吃。"""
    assert parse_tray_rating("") == []
    assert parse_tray_rating("TRAY SIZING RESULTS\nnothing") == []


def test_rating_sizing_results_not_swallowed():
    """TRAY SIZING RESULTS 行（11 列）不被 RATING 解析器误收。"""
    text = """
 UNIT 1, 'X'
 TRAY SIZING RESULTS
    1   0.342 0.08638  0.091   1993.1  78.0   1981.   78.8   2134.   69.5    2
"""
    assert parse_tray_rating(text) == []


# ============================================================================
# 真 fixture 验证
# ============================================================================


def test_real_fixture_old_t01_rating():
    """真 fixture proii .out：T01 RATING 12 行（tray 1-12）。"""
    if not SAMPLE_OLD.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_OLD}")

    text = SAMPLE_OLD.read_text(encoding="utf-8", errors="replace")
    units = parse_tray_rating(text)
    t01 = next(u for u in units if u.unit_name == "T01")
    assert len(t01.rows) == 12
    assert t01.rows[0].tray == 1
    assert t01.rows[-1].tray == 12
    assert t01.rows[0].vapor_rate == pytest.approx(25.63)
    assert t01.rows[-1].backup_pct == pytest.approx(40.38)


def test_real_fixture_fcc_stripper_rating():
    """真 fixture FCC：T204B RATING 9 行 + NP=2。"""
    if not SAMPLE_FCC.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_FCC}")

    text = SAMPLE_FCC.read_text(encoding="utf-8", errors="replace")
    units = parse_tray_rating(text)
    stripper = next(
        u for u in units if u.unit_name == "T204B" and u.rows
    )
    assert len(stripper.rows) == 9
    assert stripper.rows[0].np == 2
    assert stripper.rows[0].backup_pct == pytest.approx(39.51)


# ============================================================================
# 数据类契约
# ============================================================================


def test_rating_dataclass_fields():
    """TrayRatingRow / UnitTrayRating 字段契约。"""
    r = TrayRatingRow(
        tray=1, vapor_rate=25.63, liquid_rate=15.9, vload=0.956,
        diameter_mm=900.0, ff=57.8, pres_drop=0.005,
        weir_rate=1.0, backup_pct=26.08, np=None,
    )
    u = UnitTrayRating(unit_no="8", unit_name="T01", rows=[r])
    assert u.rows[0].ff == pytest.approx(57.8)
    assert u.rows[0].np is None
