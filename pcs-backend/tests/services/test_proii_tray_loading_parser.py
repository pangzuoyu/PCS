"""P3.x SIM-38b/1: 塔盘数据全量 — TRAY LOADING REPORT。

Part 1/3（SIM-38b 拆 3 commit）：
- commit 1: TRAY LOADING REPORT（双子表 12 列）

格式参考（sample/proii .out 4.17，UNIT 1 'T1'）：

        --------------------  VAPOR TO TRAY  --------------------      --------------------  LIQUID FROM TRAY  -------------------
                                              DENSITY   VISCOSITY                                  DENSITY   VISCOSITY     SURFACE
  TRAY  TEMP   PRESSURE     MW       RATE     AT COND    AT COND       TEMP      MW       RATE     AT COND    AT COND      TENSION
        DEG C   KG/CM2             K*KG/HR    KG/M3        CP          DEG C            K*KG/HR    KG/M3        CP        DYNE/CM
  ----  -----  --------  -------  ---------   -------   ---------      -----  -------  ---------   -------   ---------    --------
    1   164.5    20.000   18.014    2.0961      10.97      .01475       73.2   18.014    2.0961      948.3       .3830      64.180
   20   REBOILER                                                       211.6   18.015     .1963      801.2       .1264      34.905

- 表 A（VAPOR TO TRAY + LIQUID FROM TRAY）/ 表 B（VAPOR FROM TRAY + LIQUID TO TRAY）
  列同构：vapor 6 列（TEMP/PRESSURE/MW/RATE/DENSITY/VISCOSITY）+
  liquid 6 列（TEMP/MW/RATE/DENSITY/VISCOSITY/SURFACE TENSION）
- 特殊行：REBOILER（无 vapor 值）/ CONDENSER（无 liquid 值）
"""
# ruff: noqa: E501 — 文件内嵌 PRO/II 原始表行（130 字符，列对齐不可截断）
from __future__ import annotations

from pathlib import Path

import pytest

from app.services.proii_tray_loading_parser import (
    LiquidLoading,
    TrayLoadingRow,
    UnitTrayLoading,
    VaporLoading,
    parse_tray_loading,
)

SAMPLE_OLD = Path(__file__).resolve().parents[3] / "sample" / "proii .out"


LOADING_SECTION = """
                      UNIT 1, 'T1'  (CONT)

 TRAY LOADING REPORT


        --------------------  VAPOR TO TRAY  --------------------      --------------------  LIQUID FROM TRAY  -------------------
                                              DENSITY   VISCOSITY                                  DENSITY   VISCOSITY     SURFACE
  TRAY  TEMP   PRESSURE     MW       RATE     AT COND    AT COND       TEMP      MW       RATE     AT COND    AT COND      TENSION
        DEG C   KG/CM2             K*KG/HR    KG/M3        CP          DEG C            K*KG/HR    KG/M3        CP        DYNE/CM
  ----  -----  --------  -------  ---------   -------   ---------      -----  -------  ---------   -------   ---------    --------
    1   164.5    20.000   18.014    2.0961      10.97      .01475       73.2   18.014    2.0961      948.3       .3830      64.180
    2   195.8    20.000   18.015    1.9230       9.98      .01604      164.5   18.015    1.9230      858.4       .1642      45.716
   20   REBOILER                                                       211.6   18.015     .1963      801.2       .1264      34.905

        -------------------  VAPOR FROM TRAY  -------------------      ---------------------  LIQUID TO TRAY  --------------------
                                              DENSITY   VISCOSITY                                  DENSITY   VISCOSITY     SURFACE
  TRAY  TEMP   PRESSURE     MW       RATE     AT COND    AT COND       TEMP      MW       RATE     AT COND    AT COND      TENSION
        DEG C   KG/CM2             K*KG/HR    KG/M3        CP          DEG C            K*KG/HR    KG/M3        CP        DYNE/CM
  ----  -----  --------  -------  ---------   -------   ---------      -----  -------  ---------   -------   ---------    --------
    1    73.2    20.000   18.002     .0000      16.50      .01104      CONDENSER
    2   164.5    20.000   18.014    2.0961      10.97      .01475       73.2   18.014    2.0961      948.3       .3830      64.180
"""


# ============================================================================
# 单 UNIT 双子表解析
# ============================================================================


def test_loading_parse_single_unit():
    """单 UNIT：元数据 + 表 A 3 行 + 表 B 2 行。"""
    units = parse_tray_loading(LOADING_SECTION)
    assert len(units) == 1
    u = units[0]
    assert u.unit_no == "1"
    assert u.unit_name == "T1"
    assert len(u.vapor_to_tray) == 3
    assert len(u.vapor_from_tray) == 2


def test_loading_table_a_full_row_fields():
    """表 A 满行：vapor 6 列 + liquid 6 列。"""
    units = parse_tray_loading(LOADING_SECTION)
    r = units[0].vapor_to_tray[0]
    assert r.tray == 1
    assert r.label is None
    assert r.vapor is not None
    assert r.vapor.temp_c == pytest.approx(164.5)
    assert r.vapor.pressure == pytest.approx(20.000)
    assert r.vapor.mw == pytest.approx(18.014)
    assert r.vapor.rate == pytest.approx(2.0961)
    assert r.vapor.density == pytest.approx(10.97)
    assert r.vapor.viscosity == pytest.approx(0.01475)
    assert r.liquid is not None
    assert r.liquid.temp_c == pytest.approx(73.2)
    assert r.liquid.mw == pytest.approx(18.014)
    assert r.liquid.rate == pytest.approx(2.0961)
    assert r.liquid.density == pytest.approx(948.3)
    assert r.liquid.viscosity == pytest.approx(0.3830)
    assert r.liquid.surface_tension == pytest.approx(64.180)


def test_loading_reboiler_row():
    """REBOILER 行：无 vapor 值，liquid 6 列保留。"""
    units = parse_tray_loading(LOADING_SECTION)
    r = units[0].vapor_to_tray[2]
    assert r.tray == 20
    assert r.label == "REBOILER"
    assert r.vapor is None
    assert r.liquid is not None
    assert r.liquid.temp_c == pytest.approx(211.6)
    assert r.liquid.rate == pytest.approx(0.1963)
    assert r.liquid.surface_tension == pytest.approx(34.905)


def test_loading_condenser_row():
    """CONDENSER 行：vapor 6 列保留，无 liquid 值。"""
    units = parse_tray_loading(LOADING_SECTION)
    r = units[0].vapor_from_tray[0]
    assert r.tray == 1
    assert r.label == "CONDENSER"
    assert r.vapor is not None
    assert r.vapor.temp_c == pytest.approx(73.2)
    assert r.vapor.rate == pytest.approx(0.0)
    assert r.liquid is None


def test_loading_no_section_returns_empty():
    """无 TRAY LOADING REPORT → 空 list。"""
    assert parse_tray_loading("COLUMN SUMMARY\nnothing") == []
    assert parse_tray_loading("") == []


def test_loading_table_b_second_row_full():
    """表 B 第 2 行：满行双 6 列。"""
    units = parse_tray_loading(LOADING_SECTION)
    r = units[0].vapor_from_tray[1]
    assert r.tray == 2
    assert r.label is None
    assert r.vapor.temp_c == pytest.approx(164.5)
    assert r.liquid.temp_c == pytest.approx(73.2)


# ============================================================================
# 真 fixture 验证
# ============================================================================


def test_real_fixture_old_t1_loading():
    """真 fixture proii .out：T1 LOADING 表 A 20 行（含 REBOILER）+ 表 B 20 行（含 CONDENSER）。"""
    if not SAMPLE_OLD.exists():
        pytest.skip(f"sample fixture missing: {SAMPLE_OLD}")

    text = SAMPLE_OLD.read_text(encoding="utf-8", errors="replace")
    units = parse_tray_loading(text)
    # 该文件 T1 的 LOADING REPORT 出现 2 次（重复报告），均归属 UNIT 1
    assert len(units) == 2
    assert all(u.unit_name == "T1" for u in units)
    t1 = units[0]
    # 表 A：tray 1-20，第 20 行 REBOILER
    assert len(t1.vapor_to_tray) == 20
    assert t1.vapor_to_tray[-1].label == "REBOILER"
    assert t1.vapor_to_tray[-1].tray == 20
    # 表 B：tray 1-20，第 1 行 CONDENSER
    assert len(t1.vapor_from_tray) == 20
    assert t1.vapor_from_tray[0].label == "CONDENSER"
    assert t1.vapor_from_tray[0].tray == 1
    # 首行数值抽查
    r = t1.vapor_to_tray[0]
    assert r.vapor.temp_c == pytest.approx(164.5)
    assert r.liquid.surface_tension == pytest.approx(64.180)


# ============================================================================
# 数据类契约
# ============================================================================


def test_loading_dataclass_fields():
    """VaporLoading/LiquidLoading/TrayLoadingRow/UnitTrayLoading 字段契约。"""
    v = VaporLoading(
        temp_c=164.5, pressure=20.0, mw=18.014,
        rate=2.0961, density=10.97, viscosity=0.01475,
    )
    lq = LiquidLoading(
        temp_c=73.2, mw=18.014, rate=2.0961,
        density=948.3, viscosity=0.383, surface_tension=64.18,
    )
    row = TrayLoadingRow(tray=1, label=None, vapor=v, liquid=lq)
    u = UnitTrayLoading(
        unit_no="1", unit_name="T1",
        vapor_to_tray=[row], vapor_from_tray=[row],
    )
    assert u.vapor_to_tray[0].liquid.surface_tension == pytest.approx(64.18)
    assert u.vapor_from_tray[0].vapor.mw == pytest.approx(18.014)
