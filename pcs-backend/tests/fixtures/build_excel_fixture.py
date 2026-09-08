"""SIM-5 测试夹具 xlsx 构造脚本（spec 第二部分）。

生成 tests/fixtures/excel/streams_sample.xlsx：
- Sheet 1 (物流列表)：2 条（FEED, RECYCLE）
- Sheet 2 (组分组成)：按 Stream Name 关联的组分
- 含 1 条别名（H₂O → WATER）

运行：cd pcs-backend && uv run python tests/fixtures/build_excel_fixture.py
"""
from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook

OUT = Path(__file__).parent / "excel" / "streams_sample.xlsx"
OUT.parent.mkdir(parents=True, exist_ok=True)


def build() -> None:
    wb = Workbook()

    # Sheet 1: 物流列表
    ws1 = wb.active
    ws1.title = "物流列表"
    ws1.append([
        "Stream Name", "Stream No", "Temp (°C)", "Pressure (kPa)",
        "Phase", "Total Mass Flow (kg/h)", "Total Molar Flow (kmol/h)",
        "Description",
    ])
    ws1.append(["FEED", "P-001-L", 25.0, 101.325, "LIQUID", 10000.0, None, "原料进料"])
    ws1.append(["RECYCLE", "P-002-L", 80.5, 500.0, "LIQUID", 3500.0, None, "循环物流"])

    # Sheet 2: 组分组成（按 Stream Name 关联）
    ws2 = wb.create_sheet("组分组成")
    ws2.append([
        "Stream Name", "Component Name", "Mole Fraction", "Mass Flow (kg/h)",
    ])
    # FEED：H₂O（别名）+ METHANOL
    ws2.append(["FEED", "H₂O", 0.25, None])
    ws2.append(["FEED", "METHANOL", 0.75, None])
    # RECYCLE：WATER + AMMONIA
    ws2.append(["RECYCLE", "WATER", 0.90, None])
    ws2.append(["RECYCLE", "AMMONIA", 0.10, None])

    wb.save(OUT)
    print(f"saved: {OUT}  ({OUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
