#!/usr/bin/env python
"""c5：HEAT DETAIL 字段覆盖率（目标 ≥95%）。

比对「HTRI/TEMA 模板源里出现的字段」与「`datasource_registry` 登记的
HEAT_RESULTS 字段」，报出覆盖率与**未覆盖清单**。

## 为什么是「清单」而不是一个百分比

一个 87% 的数字告诉不了任何人下一步做什么。未覆盖清单能：哪个字段缺、
叫什么、去哪补（补 `heat_results` 列还是补 JSONB 键）。
**验收标准是「≥95%」，而达成它靠的是把清单一条条消掉。**

## 映射表：模板源列名 → 注册表字段名

模板源用的是 HTRI/TEMA 的英文列名，注册表用真实 ORM 列名。两侧名字
**对不上**（`Area` vs `effective_area`），所以必须有一张显式映射 ——
靠字符串猜测会把 `Area` 匹配到一堆含 "area" 的字段上，得出一个
看着挺好、其实错位的覆盖率。

## 分母是「模板源的全部列」，不是「已映射的列」

第一版把分母定成「已映射列数」，于是**覆盖率结构上恒等于 100%**：
已映射 = 分母，而分子又是「已映射 ∩ 已登记」；再加上「COLUMN_MAP 的每个
目标都必须已登记」这条测试，分母与分子恒等 —— 工具永远报满分，
而它连覆盖率是干什么的都没验。**一个恒真的指标比没有指标更坏**，
因为它会让人以为已经验过了。

现在的定义：分母 = 模板源的全部列，分子 = 我们能服务的列。
「未识别的模板列」**降低**覆盖率 —— 因为那确实是我们服务不了的列，
且它是**可见的**（清单里逐条列出，补 COLUMN_MAP 即可）。
这个方向的代价：一个模板列名拼错也会拉低覆盖率 —— 但那是对的，
我们本来就服务不了它，而且清单会指名道姓地说「需要补映射」。

## 参考文件缺失时**退出码 2**，不是 0

「没找到参考文件」绝不能是「覆盖率 0% 通过」也不是「不检查」。
缺输入就报缺输入（TODO-055）。
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

#: HTRI/TEMA 列名 → `datasource_registry` 登记名。
#: 只收**确定**的对应；不确定的宁可不映射，进 UNMAPPED。
COLUMN_MAP: dict[str, str] = {
    # --- 标识 ---
    "TagNumber": "tag_number",
    "Tag No": "tag_number",
    "Type": "exchanger_type",
    "Exchanger Type": "exchanger_type",
    # --- 热工（ADR BASIC 9 + DETAIL）---
    "Area": "effective_area",
    "Area Required": "effective_area",
    "Heat Duty": "duty",
    "Overall U": "u_overall",
    "OverallU": "u_overall",
    "LMTD": "lmtd",
    "MTD Correction": "mtd_corrected",
    # --- 温度（JSONB 物性）---
    "Shell Inlet Temp": "shell_params.temp_in",
    "Shell Outlet Temp": "shell_params.temp_out",
    "Tube Inlet Temp": "tube_params.temp_in",
    "Tube Outlet Temp": "tube_params.temp_out",
    # --- 流量 / 压降 ---
    "Shell Flow Rate": "shell_params.mass_flow",
    "Tube Flow Rate": "tube_params.mass_flow",
    "Pressure Drop": "shell_params.pd",
    "Shell Pressure Drop": "shell_params.pd",
    "Tube Pressure Drop": "tube_params.pd",
    # --- 几何（两类）---
    "Tube OD": "tube_od",
    "Tube Wall Thickness": "tube_wall_thickness",
    "Tube Length": "tube_length",
    "Tube Pitch": "tube_pitch",
    "Tube Passes": "tube_passes",
    "Tube Count": "tube_count",
    "Shell ID": "shell_id",
    "Baffle Spacing": "baffle_spacing",
    "Baffle Cut": "baffle_cut_percent",
    "Baffle Type": "baffle_type",
    "TEMA Type": "baffle_type",
    # ⚠️ ADR 的 `Nozzle Sizes` **刻意不映射**：`shell_params.nozzle_sizes`
    # 这个键在数据模型里不存在（见 registry 的 ADR_FIELDS_WITHOUT_COLUMN）。
    # 映射到它会让覆盖率替一个查不出的字段记功，而用户照样拿到空列。
    # 不映射 → 它进 UNMAPPED → 清单里明写着「需要补数据模型」。
    # --- 热阻分布 5 ---
    "Shell Side Resistance": "thermal_resistance_shell",
    "Tube Side Resistance": "thermal_resistance_tube",
    "Wall Resistance": "thermal_resistance_metal",
    "Fouling Resistance": "thermal_resistance_fouling",
    # --- 空冷器 ---
    "Number Of Fans": "ache_params.fan_count",
    "Number of Fans": "ache_params.fan_count",
    "Fan Power": "ache_params.fan_power_kw",
    "Air Inlet Temp": "ache_params.air_inlet_temp_k",
}

TARGET_COVERAGE = 0.95


def read_headers(path: Path) -> list[str]:
    """读一个 Excel 的**全部工作表**的表头并去重。

    HTRI/TEMA 输出的字段散在多个 sheet 里，只读第一个会漏掉大半
    （Xace 的几何在单独的表、Xist 的热阻在单独的表）。
    """
    import openpyxl
    import xlrd

    headers: list[str] = []
    if path.suffix.lower() in (".xls", ".xlt"):
        book = xlrd.open_workbook(str(path))
        for sheet in book.sheets():
            if sheet.nrows:
                headers += [str(v).strip() for v in sheet.row_values(0) if str(v).strip()]
    else:
        book = openpyxl.load_workbook(path, read_only=True, data_only=True)
        try:
            for sheet in book.worksheets:
                first = next(sheet.iter_rows(max_row=1, values_only=True), None)
                if first:
                    headers += [str(v).strip() for v in first if v and str(v).strip()]
        finally:
            book.close()
    seen: dict[str, None] = {}
    for h in headers:
        seen.setdefault(h, None)
    return list(seen)


def compute_coverage(headers: list[str]) -> dict:
    """覆盖率 + 三份清单。分母 = **已映射**的模板源列数。"""
    from app.services.report.datasource_registry import DATASOURCES

    registered = set(DATASOURCES["HEAT_RESULTS"].fields)
    covered: set[str] = set()
    unmapped: list[str] = []
    for h in headers:
        target = COLUMN_MAP.get(h) or COLUMN_MAP.get(h.strip().title())
        if target is None:
            unmapped.append(h)
        else:
            covered.add(target)

    served = {t for t in covered if t in registered}
    unknown_targets = sorted(covered - registered)   # 映射指向已删除/未登记的字段
    denom = len(headers)                            # 模板源的全部列
    coverage = 0.0 if denom == 0 else len(served) / denom
    return {
        "coverage": coverage,
        "target": TARGET_COVERAGE,
        "passed": denom > 0 and coverage >= TARGET_COVERAGE,
        "template_columns": denom,
        "mapped_columns": len(served),
        "covered": sorted(served),
        # ⚠️ 这是**反向**信号：注册了但这份模板用不到的字段。
        # 不是缺口（模板不需要 ≠ 我们缺），所以不参与覆盖率判定。
        "registered_fields_not_in_template": sorted(registered - served),
        # 缺口：模板要、我们服务不了。降低覆盖率，逐条列出以便补映射/补列。
        "unmapped_template_columns": sorted(unmapped),
        "mapped_to_unknown_fields": unknown_targets,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HEAT DETAIL 字段覆盖率")
    ap.add_argument("references", nargs="*", type=Path,
                    help="HTRI/TEMA 参考文件（.xls/.xlsx）")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    args = ap.parse_args(argv)

    if not args.references:
        print("未提供参考文件。覆盖率无从计算 —— "
              "**这不是「0% 通过」**。参考文件见 TODOS.md TODO-055。",
              file=sys.stderr)
        return 2
    missing = [p for p in args.references if not p.exists()]
    if missing:
        print(f"参考文件不存在：{[str(p) for p in missing]}", file=sys.stderr)
        return 2

    headers: list[str] = []
    for p in args.references:
        headers += read_headers(p)
    seen: dict[str, None] = {}
    for h in headers:
        seen.setdefault(h, None)
    result = compute_coverage(list(seen))
    result["references"] = [str(p) for p in args.references]

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        pct = result["coverage"] * 100
        print(f"覆盖率 {pct:.1f}%（目标 ≥{result['target'] * 100:.0f}%）"
              f" —— {'通过' if result['passed'] else '未达标'}")
        print(f"  模板源列 {result['template_columns']}，可服务 {result['mapped_columns']}")
        if result["unmapped_template_columns"]:
            print(f"  ⚠ 服务不了的模板列（{len(result['unmapped_template_columns'])}）—— "
                  "**这些拉低了覆盖率**，需补 COLUMN_MAP 或补数据模型列：")
            for c in result["unmapped_template_columns"][:30]:
                print(f"    ? {c}")
        if result["mapped_to_unknown_fields"]:
            print(f"  ⚠ COLUMN_MAP 指向了未登记的字段：{result['mapped_to_unknown_fields']}")
        unused = result["registered_fields_not_in_template"]
        if unused:
            print(f"  已登记但本模板用不到的字段（{len(unused)}）"
                  "—— 不是缺口，仅供参考：")
            for f in unused[:15]:
                print(f"    · {f}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
