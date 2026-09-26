"""P6-6A Task 0：Worley XLS 提取工具（scripts/p6_6_extract_worley.py）单测。

只测纯函数（文件名规范化 / A1 坐标 / cell 结构 / dump 统计 / JSON 序列化
结构），不依赖真 XLS —— xlrd 只读无法用其构造 fixture，真 XLS 端到端
以脚本统计输出为准（见 task-0-report.md dump 统计表）。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import xlrd

_BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

from scripts.p6_6_extract_worley import (  # noqa: E402
    cell_entry,
    dump_json_name,
    excel_ref,
    normalize_xls_filename,
    sheet_to_dict,
    summarize,
)


class TestNormalizeXlsFilename:
    """尾随空格容错（源目录实况：WS-CA-PR-010 .xls / WS-CA-PR-014 .xls）。"""

    def test_trailing_space_before_ext(self) -> None:
        assert normalize_xls_filename("WS-CA-PR-010 .xls") == "WS-CA-PR-010.xls"
        assert normalize_xls_filename("WS-CA-PR-014 .xls") == "WS-CA-PR-014.xls"

    def test_plain_name_unchanged(self) -> None:
        assert normalize_xls_filename("WS-CA-PR-020.xls") == "WS-CA-PR-020.xls"

    def test_outer_whitespace_stripped(self) -> None:
        assert normalize_xls_filename("  WS-CA-PR-001.xls  ") == "WS-CA-PR-001.xls"

    def test_non_xls_untouched(self) -> None:
        # 目录内混有 Standard Calculation.doc，须原样（仅 strip）返回
        assert normalize_xls_filename("Standard Calculation.doc") == (
            "Standard Calculation.doc"
        )

    def test_internal_space_preserved(self) -> None:
        # 扩展名前的"词间"空格不误删，仅去尾部
        assert normalize_xls_filename("My Calc .xls") == "My Calc.xls"


class TestExcelRef:
    """0-based (row, col) → A1 坐标。"""

    def test_origin(self) -> None:
        assert excel_ref(0, 0) == "A1"

    def test_single_letters(self) -> None:
        assert excel_ref(10, 1) == "B11"
        assert excel_ref(0, 25) == "Z1"

    def test_multi_letters(self) -> None:
        assert excel_ref(0, 26) == "AA1"
        assert excel_ref(0, 27) == "AB1"
        assert excel_ref(99, 701) == "ZZ100"  # 26 + 26*26 = 702 列 → ZZ


class TestCellEntry:
    """cell 结构：坐标 + 类型 + 值；EMPTY 不入 dump。"""

    def test_number_cell(self) -> None:
        entry = cell_entry(1, 2, xlrd.XL_CELL_NUMBER, 12.5)
        assert entry == {"ref": "C2", "type": "number", "value": 12.5}

    def test_text_cell(self) -> None:
        assert cell_entry(0, 0, xlrd.XL_CELL_TEXT, "MEOH wt%") == {
            "ref": "A1",
            "type": "text",
            "value": "MEOH wt%",
        }

    def test_date_cell_keeps_serial_float(self) -> None:
        # date 值保留 Excel 序数 float（未做日历换算）
        assert cell_entry(0, 0, xlrd.XL_CELL_DATE, 42005.0) == {
            "ref": "A1",
            "type": "date",
            "value": 42005.0,
        }

    def test_empty_cell_returns_none(self) -> None:
        assert cell_entry(5, 5, xlrd.XL_CELL_EMPTY, "") is None

    def test_blank_cell_kept(self) -> None:
        # 有格式的空 cell（值恒 ""）保留，供人工审阅
        assert cell_entry(0, 0, xlrd.XL_CELL_BLANK, "") == {
            "ref": "A1",
            "type": "blank",
            "value": "",
        }


class _FakeCell:
    """xlrd.cell 平替（只暴露 sheet.cell() 用到的 ctype / value）。"""

    def __init__(self, ctype: int, value: object) -> None:
        self.ctype = ctype
        self.value = value


class _FakeSheet:
    """xlrd.sheet.Sheet 平替（只实现 sheet_to_dict 用到的接口）。"""

    def __init__(self, name: str, grid: list[list[_FakeCell]]) -> None:
        self.name = name
        self._grid = grid
        self.nrows = len(grid)
        self.ncols = len(grid[0]) if grid else 0

    def cell(self, rowx: int, colx: int) -> _FakeCell:
        return self._grid[rowx][colx]


class TestSheetToDictAndSummarize:
    """sheet dump 结构 + 统计（非空 sheet 数 / 数字 cell 数 / 空判定）。"""

    def _dump(self) -> dict:
        sheet1 = sheet_to_dict(
            _FakeSheet(
                "Calc",
                [
                    [
                        _FakeCell(xlrd.XL_CELL_TEXT, "inlet P"),
                        _FakeCell(xlrd.XL_CELL_NUMBER, 40.0),
                        _FakeCell(xlrd.XL_CELL_EMPTY, ""),
                    ],
                    [
                        _FakeCell(xlrd.XL_CELL_NUMBER, 25.0),
                        _FakeCell(xlrd.XL_CELL_EMPTY, ""),
                        _FakeCell(xlrd.XL_CELL_ERROR, 42),
                    ],
                ],
            )
        )
        sheet2 = sheet_to_dict(_FakeSheet("Empty", []))
        return {
            "source_file": "X .xls",
            "normalized_name": "X.xls",
            "sheet_names": ["Calc", "Empty"],
            "sheets": [sheet1, sheet2],
        }

    def test_sheet_dict_structure(self) -> None:
        s = self._dump()["sheets"][0]
        assert s["name"] == "Calc"
        assert s["nrows"] == 2
        assert s["ncols"] == 3
        assert [c["ref"] for c in s["cells"]] == ["A1", "B1", "A2", "C2"]
        assert all(set(c) == {"ref", "type", "value"} for c in s["cells"])

    def test_summarize_counts(self) -> None:
        stats = summarize(self._dump())
        assert stats == {
            "file": "X .xls",
            "sheet_count": 2,
            "number_cells": 2,
            "nonempty_cells": 4,
            "is_empty": False,
        }

    def test_summarize_empty_file(self) -> None:
        dump = {
            "source_file": "E.xls",
            "normalized_name": "E.xls",
            "sheet_names": ["S1"],
            "sheets": [{"name": "S1", "nrows": 0, "ncols": 0, "cells": []}],
        }
        assert summarize(dump)["is_empty"] is True


class TestJsonSerialization:
    """dump JSON 序列化结构（ensure_ascii=False 中文可读 + round-trip 无损）。"""

    def test_round_trip(self) -> None:
        dump = {
            "source_file": "X.xls",
            "normalized_name": "X.xls",
            "sheet_names": ["S"],
            "sheets": [
                {
                    "name": "S",
                    "nrows": 1,
                    "ncols": 2,
                    "cells": [
                        {"ref": "A1", "type": "text", "value": "甲醇 wt%"},
                        {"ref": "B1", "type": "number", "value": 25.5},
                    ],
                }
            ],
        }
        text = json.dumps(dump, ensure_ascii=False, indent=1)
        assert json.loads(text) == dump

    def test_chinese_text_readable(self) -> None:
        text = json.dumps({"v": "甲醇浓度"}, ensure_ascii=False, indent=1)
        assert "甲醇浓度" in text

    def test_dump_json_name(self) -> None:
        # 尾随空格文件名 → 无空格 .json
        assert dump_json_name(Path("WS-CA-PR-010 .xls")) == "WS-CA-PR-010.json"
        assert dump_json_name(Path("WS-CA-PR-020.xls")) == "WS-CA-PR-020.json"
