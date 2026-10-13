"""HTRI 报表的 **Excel 版**解析。

用户 2026-10-13 澄清：`sample/A-101.xls` 就是 HTRI 文件的 Excel 版 ——
真实样本一直都在，`htri_parser`（纯文本 `Key: value`）读错了格式。

## 布局（两份真实文件实测）

    Xace  A-101.xls            TEMA  131-E-102-EOR.xls
    表头  Process Conditions     表头  Fluid Allocation
          |  Outside | Tubeside        |  Shell Side | Tube Side
    值列  6 / 10 | 14 / 16       值列  6 / 10 | 14 / 18

每行是 `标签(列0) | 单位(列2~5) | 值…`，标签与单位之间隔着合并单元格；
第二组标签在列 10（`Actual U` / `Area` / `Tube OD`…）。

## 三条不能省的规则

1. **侧的分界列从表头行推，不硬编码。** 两份文件的侧名列位不同
   （14/16 vs 14/18）。硬编码 12 的后果**不是报错**，是静默取到另一侧
   的值 —— Xace 管程进口 131.79°C 与空气侧 32.00°C 差 4 倍，
   报表照样出，只是温度全错。
2. **跨全部工作表。** Xace 的字段散在 `Output Summary` 与
   `Final Results`；只读第一个会漏掉近 2/3。
3. **`.xls` 读不动就转 xlsx。** `131-E-102-EOR.xls` 里有一条损坏的
   定义名公式（`Token 0x2d (AreaN) found in NAME formula`），
   xlrd 解析 globals 时就抛，`ignore_workbook_corruption=True` 拦不住。
   兜底走 LibreOffice headless（与 `scripts/report_heat_coverage.py` 同一套）。

## 与 `htri_parser` 的分工

两者产出**同一个 `HtriParsedData`**，落库链路（`map_htri_to_heat_input`）
完全共用 —— 不另起一条写入路径，否则 `heat_results` 会有两个写入方，
而它们对「哪些键存在」的判断可能不一致（bug-160 的教训）。
"""
from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from app.services.exceptions import PcsError
from app.services.heat.htri_parser import HtriParsedData

#: 单位词表 —— 与 `report_heat_coverage.py` 同源（Xace 带括号，TEMA 不带）
UNITS = frozenset({
    "C", "Deg C", "K", "kPa", "kPaG", "Pa", "bar", "psi", "mm", "cm", "m",
    "m2", "m3", "kg", "kg/s", "kg/h", "kg/m3", "wt%", "%", "m/s",
    "W/m2-K", "W/m-K", "m2-K/W", "m2-K/W-sec", "kJ/kg-C", "kW", "MW", "W",
    "J/kg-K", "mN-s/m2", "N-s/m2", "kg/m-s2", "mm2", "g", "N", "--", "-",
    "m/s2", "kJ/h", "1/s", "ppm", "mg/Nm3", "m3/h", "L/s", "1", "lb/hr",
    "m3/s", "kcal/h", "MegaWatts", "(100 m3/min)",
})

#: 表头里的侧名 → 归一化的侧。**两份文件的措辞不同**。
_SIDE_HEADER = {
    "outside": "OUTSIDE", "airside": "OUTSIDE", "air side": "OUTSIDE",
    "shell side": "SHELL", "shellside": "SHELL", "shell": "SHELL",
    "tubeside": "TUBE", "tube side": "TUBE",
}


#: 判定换热器类型的特征标签。**两份文件都可能同时出现其中一类**
#: （Xace 的 Final Results 里也有壳程几何），所以判定看**哪类更多**，
#: 而不是「有没有」—— 后者会让 TEMA 被判成空冷器。
_ACHE_MARKERS = frozenset({
    "Outside film coef", "Fan/Bundle Face Area Ratio", "Number of rows",
    "Ratio, fan area to bay face area", "Ratio, Fan/bundle face area",
    "Tip clearance", "Number of fans per bay", "No/bay", "Driver power",
    "Bundle width", "Bays in parallel per unit", "Bundles parallel per bay",
})
_SHELL_TUBE_MARKERS = frozenset({
    "Baffle Spacing", "Cross Baffle Type", "Shell ID", "%Cut (Diam)",
    "Passlane Seal Rod No.", "Pairs seal strips", "Impingement Plate",
    "No Passes per Shell", "Baffle Cut",
})


class HtriExcelParseError(PcsError):
    """Excel 版 HTRI 报表解析失败。"""


def _is_unit(v: Any) -> bool:
    s = str(v).strip()
    return bool(s) and ((s.startswith("(") and s.endswith(")")) or s in UNITS)


def _num(v: Any) -> float | None:
    """单元格 → float。带千分位逗号与单位后缀也认。"""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "")
    if not s or s in {"-", "--", "/"}:
        return None
    m = re.match(r"^[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", s)
    return float(m.group()) if m else None


def _read_rows(path: Path) -> list[tuple[str, list[list[Any]]]]:
    """逐工作表产出 `(sheet 名, 行列表)`；`.xls` 读不动就转 xlsx。"""
    import openpyxl
    import xlrd

    p = Path(path)
    if p.suffix.lower() in (".xls", ".xlt"):
        try:
            # ⚠️ logfile 必须给丢弃句柄：xlrd 的 OLE2 警告默认写 **stdout**，
            # 会污染任何下游对 stdout 的解析。
            book = xlrd.open_workbook(str(p), logfile=open(os.devnull, "w"))
            return [(s.name, [s.row_values(i) for i in range(s.nrows)])
                    for s in book.sheets()]
        except Exception:  # noqa: BLE001 — xlrd 对损坏定义名抛多种异常
            return _read_rows(_lo_convert(p))

    book = openpyxl.load_workbook(p, read_only=True, data_only=True)
    try:
        return [(ws.title, [list(r) for r in ws.iter_rows(values_only=True)])
                for ws in book.worksheets]
    finally:
        book.close()


def _lo_convert(path: Path) -> Path:
    """LibreOffice headless 转 xlsx（临时目录，不入库）。"""
    out = Path(tempfile.mkdtemp(prefix="htri_excel_"))
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(out),
         str(path)],
        check=True, capture_output=True, timeout=300,
    )
    return out / (path.stem + ".xlsx")


def _find_side_boundary(rows: list[list[Any]]) -> int:
    """从表头行推「第一侧 / 第二侧」的分界列。

    ## 为什么取**两个表头位置的中点**，而不是第二个表头的位置

    实测：Xace 的表头是 `Outside`@7 / `Tubeside`@15，但**值**落在
    6/10 与 14/16 —— 值列并不与表头列对齐（表头是合并单元格的居中位置）。
    用「第二个表头的位置」当分界，会把 col 14 的**管程侧进口值**
    （131.79°C）归进 OUTSIDE，而空气侧进口只有 32.00°C ——
    差 4 倍，报表照样出，只是温度全错，且没有任何一层会报错。

    中点（(7+15)//2 = 11）把 6/10 与 14/16 正确分开。TEMA 同理：
    表头 Shell Side@5 / Tube Side@13 → 中点 9，值在 6/10 与 14/18。

    找不到就抛 —— **不猜一个默认值**：猜错的后果见上。
    """
    for row in rows[:20]:
        hits: list[tuple[int, str]] = []
        for i, v in enumerate(row):
            if v is None:
                continue
            key = str(v).strip().lower()
            if key in _SIDE_HEADER:
                hits.append((i, key))
        # 两个不同的侧名 → 中点即分界
        if len(hits) >= 2 and hits[0][1] != hits[1][1]:
            return (hits[0][0] + hits[1][0]) // 2
    raise HtriExcelParseError(
        "找不到侧分界表头（期望含 Shell Side / Outside / Airside / Tubeside）。"
        "**不猜默认值** —— 猜错会静默取到另一侧的数值（实测差 4 倍）。",
        code="HTRI_EXCEL_NO_SIDE_HEADER", status=422,
    )


def _split_inline_value(text: str) -> tuple[str, list[float], str] | None:
    """`Shell ID 1600.00 mm` → `("Shell ID", [1600.0], "mm")`；不是这个形状给 None。

    TEMA 有三种单元格写法，纯文本 parser 一条都覆盖不到：
      1. `标签 值 单位`         —— `Shell ID 1600.00 mm`
      2. `标签 值1 / 值2 单位`  —— `Surf/Unit (Gross/Eff) 1945.40 / 1862.49 m2`
      3. `标签 | 值 | 单位`     —— 值在**下一格**、单位在再下一格（见 `_collect`）

    判据：末段是单位；单位之前的部分按 `/` 拆出若干数字。
    拆不出任何数字就返回 None（那是普通标签，不是内嵌值）。
    """
    parts = text.rsplit(maxsplit=1)
    if len(parts) < 2:
        return None
    head, unit = parts
    if not _is_unit(unit):
        return None
    # ⚠️ **不能按 `/` 拆** —— 标签自己就带斜杠：
    # `Surf/Unit (Gross/Eff) 1945.40 / 1862.49 m2` 里 `Surf/Unit` 的斜杠
    # 会被当成分隔符，于是 1945.40 被当成标签的一部分丢掉，只剩 1862.49。
    # 正解：在 head 里**找全部数字**，标签 = 第一个数字之前的部分。
    nums = [float(m) for m in re.findall(r"[-+]?\d*\.?\d+", head)]
    if not nums:
        return None
    label = re.split(r"[-+]?\d", head, maxsplit=1)[0].strip(" (/-")
    return label, nums, unit


def _collect(rows: list[list[Any]], boundary: int) -> dict[str, dict[str, list[float | None]]]:
    """扫一张表 → `{标签: {侧: [值...]}}`。

    判定：字符串单元格 + 本行**下一个非空**单元格是单位 → 该字符串是标签。
    「下一个非空」而非「紧邻」：标签与单位之间隔着合并单元格。
    值按列号归到侧（`< boundary` / `>= boundary`）。
    """
    found: dict[str, dict[str, list[float | None]]] = {}
    for row in rows:
        cells = [(i, str(v).strip()) for i, v in enumerate(row)
                 if v is not None and str(v).strip()]
        k = 0
        while k < len(cells):
            i, label = cells[k]
            if not label[0].isalpha() or _is_unit(label):
                k += 1
                continue
            nxt = cells[k + 1][1] if k + 1 < len(cells) else None
            # 写法 4：`Shell ID | 1600.00  mm` —— 值与单位在**下一格**里。
            # 与写法 1（`标签 | 单位 | 值`）的区别：下一格是「值+单位」而不是纯单位。
            if nxt and not _is_unit(nxt) and _split_inline_value(nxt):
                _lbl, vals4, unit4 = _split_inline_value(nxt)
                found.setdefault(label, {"OUTSIDE": [], "TUBE": []})
                side4 = "TUBE" if cells[k + 1][0] >= boundary else "OUTSIDE"
                found[label][side4] += vals4
                found[label]["_unit"] = unit4
                k += 2
                continue
            if nxt is not None and not _is_unit(nxt) and _num(nxt) is not None \
                    and k + 2 < len(cells) and _is_unit(cells[k + 2][1]):
                # TEMA 写法：`Heat Exchanged | 44711. | kW` —— **值在单位之前**。
                # 只认「单位在值之后」的话，这一整类字段一个都取不到。
                found.setdefault(label, {"OUTSIDE": [], "TUBE": []})
                found[label]["TUBE" if cells[k + 1][0] >= boundary
                        else "OUTSIDE"].append(_num(nxt))
                found[label]["_unit"] = cells[k + 2][1]
                k += 2
                continue
            if not (nxt and _is_unit(nxt)):
                # TEMA 常见写法：`Shell ID | 1600.00  mm` —— 值与单位在
                # **同一个单元格**里。不处理它，Shell ID 这类字段一个都取不到。
                inline = _split_inline_value(label)
                if inline is None:
                    k += 1
                    continue
                # ⚠️ 标签**已不含单位**（`_split_inline_value` 把它剥掉了），
                # 所以别再从 label 上二次拆单位 —— 那是 IndexError 的来源。
                label, inline_vals, label_unit = inline
                found.setdefault(label, {"OUTSIDE": [], "TUBE": []})
                found[label]["OUTSIDE"] += inline_vals
                found[label]["_unit"] = label_unit
                k += 1
                continue
            # 单位之后、下一个标签之前的非空单元格 = 本标签的值
            vals: dict[str, list[float | None]] = {"OUTSIDE": [], "TUBE": []}
            hits: list[tuple[int, float]] = []
            for j in range(k + 2, len(cells)):
                ci, txt = cells[j]
                if txt[0].isalpha() and not _is_unit(txt):
                    break        # 下一个标签（可能是第二组）
                n = _num(txt)
                if n is not None:
                    hits.append((ci, n))
            # ⚠️ **四值行不能按列分**。TEMA 的
            # `Vapor (In/Out) | wt% | 6:0.0 | 10:0.0 | 14:0.0 | 18:0.0`
            # 分界列 9 会把它切成 1/3，而真实语义是
            # **两侧 × 进出口**（壳进/壳出/管进/管出）。按列分的结果是
            # 冷侧拿到 3 个值、热侧只有 1 个 —— 而两相含量的进出口对比
            # 恰恰是报表要显示的东西。
            #
            # 规则：值数 ≥ 4 且为偶数 → 按顺序对半分（两侧各进/出）；
            # 否则回退到按列归侧（单值/双值行，如 `Number of rows`）。
            if len(hits) >= 4 and len(hits) % 2 == 0:
                half = len(hits) // 2
                vals["OUTSIDE"] = [n for _c, n in hits[:half]]
                vals["TUBE"] = [n for _c, n in hits[half:]]
            else:
                for ci, n in hits:
                    vals["TUBE" if ci >= boundary else "OUTSIDE"].append(n)
            if any(vals.values()):
                found.setdefault(label, vals)
                found[label]["_unit"] = nxt
            k += 1
    return found


def _first(d: dict | None, side: str, idx: int = 0) -> float | None:
    if not d:
        return None
    vals = d.get(side) or []
    return vals[idx] if idx < len(vals) else None


def _to_w(value: float | None, unit: str | None) -> float | None:
    """功率值 → W。**按单位换，不按数值大小猜**。

    ⚠️ 猜大小会错：TEMA 的 `Heat Exchanged 44711 kW` 与某个 W 单位的
    44711 无法从数字区分，而猜错就是**1000 倍误差** —— 报表照出，
    只是热负荷离谱。
    """
    if value is None:
        return None
    u = (unit or "").strip().strip("()").lower()
    if u in ("mw", "megawatts"):
        return value * 1e6
    if u == "kw":
        return value * 1e3
    return value


def _pair(d: dict | None, side: str) -> tuple[float | None, float | None]:
    return _first(d, side, 0), _first(d, side, 1)


def parse_htri_excel(path: Path) -> HtriParsedData:  # noqa: C901 — 纯字段映射，拆开会更难对账
    """Excel 版 HTRI 报表 → `HtriParsedData`。

    与 `htri_parser.parse_htri` 产出同一个类型，落库链路共用。
    """
    p = Path(path)
    if not p.exists():
        raise HtriExcelParseError(f"报表文件不存在：{p}",
                                  code="HTRI_EXCEL_NOT_FOUND", status=404)

    merged: dict[str, dict[str, list[float | None]]] = {}
    kinds: list[str] = []   # 计数用（判定看哪类**更多**，不是有没有）
    for _name, rows in _read_rows(p):
        if not rows:
            continue
        try:
            boundary = _find_side_boundary(rows)
        except HtriExcelParseError:
            continue                      # 诊断表没有侧表头，跳过
        for label, vals in _collect(rows, boundary).items():
            merged.setdefault(label, vals)
            if label in _ACHE_MARKERS:
                kinds.append("AIR_COOLER")
            if label in _SHELL_TUBE_MARKERS:
                kinds.append("SHELL_TUBE")

    if not merged:
        raise HtriExcelParseError(
            f"{p.name} 里没解析出任何 HTRI 字段 —— 布局可能变了",
            code="HTRI_EXCEL_NO_FIELDS", status=422,
        )

    duty_row = merged.get("Duty") or merged.get("Heat Exchanged")
    duty_w = _to_w(_first(duty_row, "OUTSIDE"),
                   (duty_row or {}).get("_unit"))

    # ⚠️ **热侧 = 管程侧（TUBE），冷侧 = 另一侧（OUTSIDE）**，两份文件
    # 都如此，实测确认：
    #   Xace  TUBE 131.79 → 54.99（降温）· OUTSIDE 32.00 → 49.33（空气被加热）
    #   TEMA  TUBE 400.20 → 279.72（冷凝）· OUTSIDE 186.25 → 326.10（壳程被加热）
    # 取反会让报表把冷热侧的进出口温度整个对调 —— 而温度全都在合理
    # 区间内，**没有任何断言会红**。
    # ⚠️ 不能用 `a or b` 回退：`_pair` 缺字段时返回 `(None, None)`，
    # 而**非空元组是真值** → 第一个永远赢，第二个形同不存在。
    _t_in, _t_out = _first_pair(merged, "TUBE",
                                ("Temperature, In/Out", "Temperature (In/Out)"))
    _c_in, _c_out = _first_pair(merged, "OUTSIDE",
                                ("Temperature, In/Out", "Temperature (In/Out)"))

    return HtriParsedData(
        version="excel",
        case_name=_case_name(p, merged),
        # ⚠️ 看**哪类标记更多**，不是「有没有」。Xace 的 Final Results 里
        # 也有壳程几何（TEMA 特征），「有没有」会让它被判成管壳式。
        exchanger_kind=("SHELL_TUBE"
                        if kinds.count("SHELL_TUBE") > kinds.count("AIR_COOLER")
                        else "AIR_COOLER"),
        heat_duty_w=duty_w or 0.0,
        overall_u_w_m2k=(_first(merged.get("Actual U"), "TUBE")
                         or _first(merged.get("Overall coef, Design/Clean/Actual"), "TUBE")
                         or 0.0),
        # `Surf/Unit (Gross/Eff) 1945.40 / 1862.49 m2` 的**毛**面积是第一个值
        area_required_m2=_coalesce(_first(merged.get("Area"), "TUBE"),
                                  _first(merged.get("Surf/Unit (Gross/Eff)"), "OUTSIDE", 0),
                                  0.0),
        # --- 管壳 ---
        # ⚠️ TEMA 表头是 `Shell Side@5 | Tube Side@13` → 壳程落在 OUTSIDE 带
        shell_id_mm=_coalesce(_first(merged.get("Shell ID"), "OUTSIDE"),
                              _first(merged.get("Shell ID"), "TUBE")),
        tube_length_m=_first(merged.get("Length"), "TUBE"),
        tube_count=_int_or_none(_coalesce(_first(merged.get("Tubecount"), "TUBE"),
                                         _first(merged.get("Tube No."), "TUBE"))),
        baffle_spacing_mm=_first(merged.get("Spacing(c/c)   450.000"), "TUBE"),
        tube_passes=_int_or_none(_coalesce(_first(merged.get("Number of passes"), "TUBE"),
                                          _first(merged.get("No Passes per Shell"), "TUBE"))),
        tube_rows=_int_or_none(_first(merged.get("Number of rows"), "TUBE")),
        # 冷热侧的进出口：热侧 = 管程侧（TUBE），冷侧 = 另一侧（OUTSIDE）。
        # 理由见函数上方 _t_in/_c_in 的推导。
        hot_inlet_t_c=_t_in,
        hot_outlet_t_c=_t_out,
        hot_mass_flow_kgs=(_first(merged.get("Total flow rate"), "TUBE")
                           or _first(merged.get("Fluid Quantity, Total"), "TUBE")),
        cold_inlet_t_c=_c_in,
        cold_outlet_t_c=_c_out,
        cold_mass_flow_kgs=(_first(merged.get("Total flow rate"), "OUTSIDE")
                            or _first(merged.get("Fluid Quantity, Total"), "OUTSIDE")),
        # --- 两相含量（用户 2026-12-12 裁决）---
        # ⚠️ Xace 与 TEMA 的同一项**标签名不同**：
        #   Xace  `Weight fraction vapor, In/Out`
        #   TEMA  `Vapor (In/Out)`
        # 只写一个名字，另一类文件的两相含量全部取不到且不报错。
        vapor_wt_frac_in=_first(_vapor(merged), "TUBE"),
        vapor_wt_frac_out=_first(_vapor(merged), "TUBE", 1),
        liquid_wt_frac_in=_first(merged.get("Liquid"), "TUBE"),
        liquid_wt_frac_out=_first(merged.get("Liquid"), "TUBE", 1),
        cold_vapor_wt_frac_in=_first(_vapor(merged), "OUTSIDE"),
        cold_vapor_wt_frac_out=_first(_vapor(merged), "OUTSIDE", 1),
        cold_liquid_wt_frac_in=_first(merged.get("Liquid"), "OUTSIDE"),
        cold_liquid_wt_frac_out=_first(merged.get("Liquid"), "OUTSIDE", 1),
        # --- 壁温（用户裁决）---
        skin_temp_min_c=_first(merged.get("Skin temperature, Min/Max"), "TUBE"),
        skin_temp_max_c=_first(merged.get("Skin temperature, Min/Max"), "TUBE", 1),
        heat_transfer_safety_factor=_first(merged.get("Heat transfer safety factor"), "OUTSIDE"),
        # --- 空冷器 ---
        air_inlet_t_c=_first(merged.get("Air Inlet Temp"), "OUTSIDE"),
        bundle_area_m2=_coalesce(_first(merged.get("Bundle Area"), "OUTSIDE"),
                                _first(merged.get("Extended area"), "OUTSIDE")),
        fan_count=_int_or_none(_coalesce(_first(merged.get("Number of fans per bay"), "OUTSIDE"),
                                          _first(merged.get("No/bay"), "OUTSIDE"))),
        fan_face_area_ratio=_coalesce(
            _first(merged.get("Ratio, fan area to bay face area"), "OUTSIDE"),
            _first(merged.get("Ratio, Fan/bundle face area"), "OUTSIDE")),
        fan_power_kw=_first(merged.get("Driver power"), "OUTSIDE"),
        fin_height_mm=_first(merged.get("Fin height"), "TUBE"),
        fin_thickness_mm=_first(merged.get("Fin thickness at base"), "TUBE"),
        fin_root_diameter_mm=_first(merged.get("Fin root"), "TUBE"),
        over_fin_diameter_mm=_first(merged.get("Over fin"), "TUBE"),
        # ⚠️ 两侧都读。`Tip clearance` 在 `Output Summary` 的值落在
        # OUTSIDE 侧、在 `Final Results` 落在 TUBE 侧，而 `merged` 用
        # `setdefault` 只保留**先读到的那张表** —— 只读一侧就是 None，
        # 而字段已登记，报表里就是一列空白（登记了不等于有数据）。
        tip_clearance_mm=_coalesce(_first(merged.get("Tip clearance"), "TUBE"),
                                   _first(merged.get("Tip clearance"), "OUTSIDE")),
        # TODO-056 剩余 5 个
        air_humidity_percent=_any_side(merged.get("Air humidity")),
        fin_density_per_m=_any_side(merged.get("Fins per unit length")),
        fin_efficiency_percent=_any_side(merged.get("Fin efficiency")),
        unfinned_length_mm=_any_side(merged.get("Unfinned length")),
        unheated_length_mm=_any_side(merged.get("Unheated length")),
        extended_area_m2=_first(merged.get("Extended area"), "OUTSIDE"),
        bare_area_m2=_first(merged.get("Bare area"), "OUTSIDE"),
        raw_text="",
    )


def _any_side(d: dict | None) -> float | None:
    """两侧里取第一个有值的 —— 不关心它在报告的哪一侧。

    这些是**单值字段**（翅片密度、空气湿度…），HTRI 把它们放在哪一列
    取决于该行怎么排，没有「热侧/冷侧」的语义。两侧都取一遍比猜一侧稳。
    """
    return _coalesce(_first(d, "OUTSIDE"), _first(d, "TUBE"),
                     _first(d, "OUTSIDE", 1), _first(d, "TUBE", 1))


def _int_or_none(v) -> int | None:
    """浮点 → int；None 保持 None。

    ⚠️ 不用 `int(x or 0) or None`：`0 or None` → None，而「风机数 0」
    在某些报表里是合法的（不吹风的设计）。
    """
    return None if v is None else int(v)


def _coalesce(*values):
    """取第一个**非 None** 的值。

    ⚠️ **不能用 `or`**：0.0 是假值，而 `Unfinned length` 的真实值就是
    `0.000`（没有无翅片段）。`a or b` 会把 0 当成「没有值」丢掉，
    而报表里那一列变成空白 —— 与「这个字段取不到」表现完全一样。
    """
    for v in values:
        if v is not None:
            return v
    return None


def _first_pair(merged: dict, side: str, keys: tuple[str, ...]
                ) -> tuple[float | None, float | None]:
    """按 `keys` 顺序取第一组**真正取到值**的键。

    ⚠️ 不用 `or` 回退：`_pair` 缺字段时返回 `(None, None)`，而非空元组
    是真值 —— 第一个永远赢，后面的键形同不存在。
    """
    for key in keys:
        if key not in merged:
            continue
        pair = _pair(merged[key], side)
        if pair[0] is not None or pair[1] is not None:
            return pair
    return (None, None)


def _vapor(merged: dict) -> dict | None:
    """气相含量行 —— Xace 与 TEMA 的标签名不同，取先命中的那个。"""
    for key in ("Weight fraction vapor, In/Out", "Vapor (In/Out)"):
        if key in merged:
            return merged[key]
    return None


def _case_name(p: Path, merged: dict) -> str:
    """案名从文件路径推 —— 报表里没有稳定的案名字段。"""
    return p.stem


__all__ = ["parse_htri_excel", "HtriExcelParseError", "UNITS"]