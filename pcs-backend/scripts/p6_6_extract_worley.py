"""P6-6A Task 0：Worley 24 XLS（OLE2 .xls）全量提取 → JSON dump。

背景（P6-6A 对账批计划 Task 0）：

- 源目录：``sample/Process caculation from Worley/16.3 Standard Calculation/``
  下 24 个 ``WS-CA-PR-*.xls``（gitignored，只读）。OLE2 旧格式，openpyxl
  不支持，用 ``xlrd>=2.0``（2.x 专读 .xls）。
- 文件名容错：两个文件含尾随空格（``WS-CA-PR-010 .xls`` /
  ``WS-CA-PR-014 .xls``），输出前统一规范化为无空格同名 ``.json``。
- dump JSON 结构（供后续人工审阅定位输入/输出区）：

  - ``source_file`` / ``normalized_name``：原始与规范化文件名；
  - ``sheet_names``：sheet 名列表；
  - ``sheets[]``：每 sheet 的 ``name`` / ``nrows`` / ``ncols`` / ``cells[]``；
  - ``cells[]``：非空 cell，``ref``（A1 坐标）+ ``type`` + ``value``。

- 值语义：xlrd 给的 cell value 即公式缓存计算结果值（xlrd 2.x 不解析
  公式文本）；``cell_type`` 区分 number/text/date/boolean/error/blank，
  date 为 Excel 序数 float（未做时区/日历换算）。

用法：

    cd pcs-backend
    uv run python scripts/p6_6_extract_worley.py [--src DIR] [--out DIR]

单测：``tests/services/test_worley_extract.py``（纯函数：文件名规范化 /
A1 坐标 / cell 结构 / dump 统计；真 XLS 端到端以本脚本统计输出为准）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import xlrd

# 允许 ``uv run python scripts/xxx.py`` 直接调用。
_BACKEND_ROOT = Path(__file__).resolve().parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))

# 源目录默认指向主仓库 sample/（gitignored 只读；worktree 内无副本）。
DEFAULT_SRC = Path(
    "/home/pangzy/code_project/PCS/sample/"
    "Process caculation from Worley/16.3 Standard Calculation"
)
# 输出默认落 worktree 的 .superpowers/sdd 工作区（gitignored）。
DEFAULT_OUT = (
    _BACKEND_ROOT.parent
    / ".superpowers/sdd/2026-09-27-p6-6a-worley-reconciliation/worley_dump"
)

# xlrd cell type → dump 内可读类型名（EMPTY 不入 dump，无映射）。
_CELL_TYPE_NAMES: dict[int, str] = {
    xlrd.XL_CELL_TEXT: "text",
    xlrd.XL_CELL_NUMBER: "number",
    xlrd.XL_CELL_DATE: "date",
    xlrd.XL_CELL_BOOLEAN: "boolean",
    xlrd.XL_CELL_ERROR: "error",
    xlrd.XL_CELL_BLANK: "blank",  # 有格式的空 cell（值恒为 ""），保留供审阅
}


def normalize_xls_filename(name: str) -> str:
    """规范化 XLS 文件名：去外层空白 + 扩展名前尾随空格。

    尾随空格容错（Worley 源目录实况）：

    >>> normalize_xls_filename("WS-CA-PR-010 .xls")
    'WS-CA-PR-010.xls'

    非 .xls 文件名原样返回（仅 strip 外层空白）。
    """
    name = name.strip()
    stem, dot, ext = name.rpartition(".")
    if dot and ext.lower() == "xls":
        return f"{stem.rstrip()}.{ext}"
    return name


def excel_ref(row: int, col: int) -> str:
    """0-based (row, col) → Excel A1 坐标（excel_ref(0, 0) == "A1"）。"""
    letters = ""
    c = col
    while True:
        letters = chr(ord("A") + c % 26) + letters
        c = c // 26 - 1
        if c < 0:
            break
    return f"{letters}{row + 1}"


def cell_entry(row: int, col: int, cell_type: int, value: object) -> dict | None:
    """非空 cell → dump entry；``XL_CELL_EMPTY`` → None（不入 dump）。"""
    if cell_type == xlrd.XL_CELL_EMPTY:
        return None
    return {
        "ref": excel_ref(row, col),
        "type": _CELL_TYPE_NAMES.get(cell_type, f"unknown_{cell_type}"),
        "value": value,
    }


def sheet_to_dict(sheet: xlrd.sheet.Sheet) -> dict:
    """一个 sheet → dump dict（行列数 + 非空 cell 列表，行/列序自然有序）。"""
    cells: list[dict] = []
    for row in range(sheet.nrows):
        for col in range(sheet.ncols):
            cell = sheet.cell(row, col)
            entry = cell_entry(row, col, cell.ctype, cell.value)
            if entry is not None:
                cells.append(entry)
    return {"name": sheet.name, "nrows": sheet.nrows, "ncols": sheet.ncols, "cells": cells}


def extract_xls(path: Path) -> dict:
    """单个 .xls → 全 sheet dump dict。"""
    book = xlrd.open_workbook(str(path))
    return {
        "source_file": path.name,
        "normalized_name": normalize_xls_filename(path.name),
        "sheet_names": book.sheet_names(),
        "sheets": [sheet_to_dict(s) for s in book.sheets()],
    }


def dump_json_name(path: Path) -> str:
    """输出 JSON 文件名：规范化后的文件名换 .json 扩展。"""
    return normalize_xls_filename(path.name).removesuffix(".xls") + ".json"


def summarize(dump: dict) -> dict:
    """dump dict → 统计（sheet 数 / 数字 cell 数 / 非空 cell 数 / 是否空）。"""
    sheets = dump["sheets"]
    nonempty_cells = sum(len(s["cells"]) for s in sheets)
    return {
        "file": dump["source_file"],
        "sheet_count": len(sheets),
        "number_cells": sum(
            1 for s in sheets for c in s["cells"] if c["type"] == "number"
        ),
        "nonempty_cells": nonempty_cells,
        "is_empty": nonempty_cells == 0,
    }


def main() -> int:
    """CLI：dump 全部 .xls → --out，打印每文件统计 + 总计。"""
    parser = argparse.ArgumentParser(description="Worley 24 XLS → JSON dump")
    parser.add_argument("--src", type=Path, default=DEFAULT_SRC, help="XLS 源目录")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="JSON dump 输出目录")
    args = parser.parse_args()

    xls_paths = sorted(
        p for p in args.src.iterdir() if p.suffix.lower() == ".xls" and p.is_file()
    )
    if not xls_paths:
        print(f"[ERROR] 源目录无 .xls：{args.src}")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)

    total_sheets = total_numbers = total_nonempty = 0
    print(f"{'file':<24} {'sheets':>6} {'num_cells':>9} {'cells':>7}  empty")
    for path in xls_paths:
        dump = extract_xls(path)
        out_path = args.out / dump_json_name(path)
        out_path.write_text(
            json.dumps(dump, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        stats = summarize(dump)
        total_sheets += stats["sheet_count"]
        total_numbers += stats["number_cells"]
        total_nonempty += stats["nonempty_cells"]
        print(
            f"{stats['file']:<24} {stats['sheet_count']:>6} "
            f"{stats['number_cells']:>9} {stats['nonempty_cells']:>7}  "
            f"{'YES' if stats['is_empty'] else 'no'}"
        )
    print(
        f"\nTOTAL: {len(xls_paths)} XLS → {total_sheets} sheets, "
        f"{total_numbers} number cells, {total_nonempty} non-empty cells"
    )
    print(f"dump 目录：{args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
