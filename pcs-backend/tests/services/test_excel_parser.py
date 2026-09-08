"""P3.2 SIM-5：Excel 批量导入解析器契约测试（spec 第二部分）。

按 spec：双 Sheet（物流列表 + 组分组成）+ 名称别名解析
（H₂O→WATER 等，见附录 A）+ Mole Fraction 与 Mass Flow 至少填一列。

注：组分组分键用名称（非 CAS），CAS 转换在 SIM-10 commit 阶段
  chemicals vendor 库完成。
"""
from __future__ import annotations

from pathlib import Path

import pytest
from openpyxl import Workbook

from app.services.excel_parser import (
    parse_excel_file,
)

FIXTURES = Path(__file__).parent.parent / "fixtures" / "excel"
SAMPLE = FIXTURES / "streams_sample.xlsx"


def _build_xlsx(
    path: Path,
    *,
    sheet1: list[list] | None = None,
    sheet2: list[list] | None = None,
    sheet1_name: str = "物流列表",
    sheet2_name: str = "组分组成",
) -> None:
    """临时构造 xlsx（错误用例测试用）。"""
    wb = Workbook()
    ws1 = wb.active
    ws1.title = sheet1_name
    if sheet1 is not None:
        for row in sheet1:
            ws1.append(row)
    if sheet2 is not None:
        ws2 = wb.create_sheet(sheet2_name)
        for row in sheet2:
            ws2.append(row)
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)


# ---------------------------------------------------------------------------
# 主路径：2 stream + composition 合并
# ---------------------------------------------------------------------------


def test_parse_sample_streams_count_2():
    r = parse_excel_file(SAMPLE)
    assert len(r.streams) == 2


def test_parse_sample_stream_names():
    r = parse_excel_file(SAMPLE)
    names = {s.tag for s in r.streams}
    assert names == {"FEED", "RECYCLE"}


def test_parse_sample_stream_basic_fields():
    """spec §2.2 Sheet 1：temp/press/phase/flow 全转 SI。"""
    r = parse_excel_file(SAMPLE)
    feed = next(s for s in r.streams if s.tag == "FEED")
    assert feed.temperature_k == pytest.approx(25 + 273.15, abs=0.01)
    assert feed.pressure_pa == pytest.approx(101.325 * 1000, abs=0.1)
    assert feed.phase == "LIQUID"
    assert feed.mass_flow_kg_h == 10000.0


def test_parse_sample_composition_merged():
    """spec §2.2 Sheet 2 → composition dict。"""
    r = parse_excel_file(SAMPLE)
    feed = next(s for s in r.streams if s.tag == "FEED")
    assert feed.composition is not None
    # H₂O 别名 → WATER（spec §2.2 附录 A）
    assert "WATER" in feed.composition
    assert feed.composition["WATER"] == pytest.approx(0.25, abs=0.001)
    assert feed.composition["METHANOL"] == pytest.approx(0.75, abs=0.001)


def test_parse_sample_recycle_composition():
    r = parse_excel_file(SAMPLE)
    rec = next(s for s in r.streams if s.tag == "RECYCLE")
    assert rec.composition["WATER"] == pytest.approx(0.90, abs=0.001)
    assert rec.composition["AMMONIA"] == pytest.approx(0.10, abs=0.001)


# ---------------------------------------------------------------------------
# 错误兜底
# ---------------------------------------------------------------------------


def test_missing_required_column_raises(tmp_path):
    xlsx = tmp_path / "bad.xlsx"
    _build_xlsx(
        xlsx,
        sheet1=[
            ["Stream Name", "Temp (°C)"],  # 缺 Pressure / Phase / Flow
            ["X", 25.0],
        ],
        sheet2=[["Stream Name", "Component Name", "Mole Fraction"]],
    )
    with pytest.raises(ValueError, match="missing required column"):
        parse_excel_file(xlsx)


def test_composition_row_missing_both_fraction_and_mass_raises(tmp_path):
    """spec §2.2 规则：Mole Fraction 与 Mass Flow 至少填一列。"""
    xlsx = tmp_path / "bad.xlsx"
    _build_xlsx(
        xlsx,
        sheet1=[
            [
                "Stream Name", "Stream No", "Temp (°C)", "Pressure (kPa)",
                "Phase", "Total Mass Flow (kg/h)", "Total Molar Flow (kmol/h)",
                "Description",
            ],
            ["X", "P-1", 25.0, 100.0, "L", 100.0, None, ""],
        ],
        sheet2=[
            ["Stream Name", "Component Name", "Mole Fraction", "Mass Flow (kg/h)"],
            ["X", "WATER", None, None],  # 两列均空 → 错
        ],
    )
    r = parse_excel_file(xlsx)
    assert any("row 2" in e and "fraction" in e.lower() for e in r.errors)


def test_stream_without_composition_kept_with_warn(tmp_path):
    """Sheet 2 存在但无该 stream 的组分行 → 流保留 + WARN（用于手工二次补全）。"""
    xlsx = tmp_path / "warn.xlsx"
    _build_xlsx(
        xlsx,
        sheet1=[
            [
                "Stream Name", "Stream No", "Temp (°C)", "Pressure (kPa)",
                "Phase", "Total Mass Flow (kg/h)", "Total Molar Flow (kmol/h)",
                "Description",
            ],
            ["PURE", "P-1", 25.0, 100.0, "L", 100.0, None, "纯组分"],
        ],
        sheet2=[
            ["Stream Name", "Component Name", "Mole Fraction", "Mass Flow (kg/h)"],
            # Sheet 2 存在但只有表头 → PURE 无组分
        ],
    )
    r = parse_excel_file(xlsx)
    assert len(r.streams) == 1
    assert r.streams[0].composition is None
    assert any("PURE" in w and "无组分" in w for w in r.warnings)


def test_garbage_xlsx_raises(tmp_path):
    """非 .xlsx 或破损文件 → ValueError。"""
    xlsx = tmp_path / "garbage.xlsx"
    xlsx.write_bytes(b"not a real xlsx")
    with pytest.raises(ValueError):
        parse_excel_file(xlsx)


def test_missing_sheet_raises(tmp_path):
    """只有 Sheet 1 无 Sheet 2 → ValueError（必须双 Sheet）。"""
    xlsx = tmp_path / "half.xlsx"
    _build_xlsx(
        xlsx,
        sheet1=[
            ["Stream Name", "Stream No", "Temp (°C)", "Pressure (kPa)", "Phase",
             "Total Mass Flow (kg/h)", "Total Molar Flow (kmol/h)", "Description"],
            ["X", "P-1", 25.0, 100.0, "L", 100.0, None, ""],
        ],
        sheet2=None,
    )
    with pytest.raises(ValueError, match="sheet"):
        parse_excel_file(xlsx)
