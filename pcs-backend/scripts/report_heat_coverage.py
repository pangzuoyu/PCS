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
import os
import sys
from pathlib import Path

#: HTRI/TEMA 列名 → `datasource_registry` 登记名。
#: 只收**确定**的对应；不确定的宁可不映射，进 UNMAPPED。
COLUMN_MAP: dict[str, list[str]] = {
    '%Cut (Diam)   25.0': ['baffle_cut_percent'],
    'Actual U': ['u_overall'],
    'Area': ['effective_area'],
    'Average Film Coefficient': ['shell_params.film_coef', 'tube_params.film_coef'],
    'Bare area': ['total_area_gross'],
    'Bundle width': ['total_area_gross'],
    'Clean coef': ['u_clean'],
    'Critical Pressure': ['shell_params.pressure', 'tube_params.pressure'],
    'Cross Baffle Type   PERPEND.  SINGLE-SEG.': ['baffle_type'],
    'Density': ['shell_params.density', 'tube_params.density'],
    'Design Pressure': ['shell_design_pressure'],
    'Design Temperature': ['shell_design_temp'],
    'Driver power': ['ache_params.fan_power_kw'],
    'Duty': ['duty'],
    'EMTD': ['emtd'],
    'Effective mean temperature difference': ['emtd'],
    'Extended area': ['total_area_gross'],
    'Film coefficient, Bare/Extended': ['shell_params.film_coef', 'tube_params.film_coef'],
    'Fin type': ['ache_params.fin_type'],
    'Fluid Quantity, Total': ['shell_params.mass_flow', 'tube_params.mass_flow'],
    'Fouling Resistance (min)': ['shell_params.fouling_res', 'tube_params.fouling_res'],
    'Fouling resistance': ['shell_params.fouling_res', 'tube_params.fouling_res'],
    'Heat Exchanged': ['duty'],
    'Heat duty, Calculated/Specified': ['duty'],
    'Impingement Plate': ['impingement_plate'],
    'Inlet Pressure': ['shell_params.pressure'],
    'Kettle ID': ['shell_id'],
    'LMTD': ['lmtd'],
    'Length': ['tube_length'],
    'Long pitch': ['tube_pitch'],
    'MTD (Corrected)': ['mtd_corrected'],
    'Material   321 STAINLESS STEEL (18 CR,10 NI)': ['tube_material'],
    'Midpoint velocity': ['shell_params.velocity', 'tube_params.velocity'],
    'Motor power/fan-design air temperature': ['ache_params.fan_power_kw'],
    'No Passes per Shell': ['tube_passes'],
    'Number': ['tube_count'],
    'Number of fans per bay': ['ache_params.fan_count'],
    'Number of nozzles': ['ache_params.tube_nozzle_count'],
    'Number of passes': ['tube_passes'],
    'Number of tubes/bundle': ['tube_count'],
    'Orientation  Horizontal': ['orientation'],
    'Outside film coef': ['shell_params.film_coef'],
    'Overall coef, Design/Clean/Actual': ['u_overall', 'u_service', 'u_calculated', 'u_clean'],
    'Overdesign': ['overdesign_percent'],
    'Pairs seal strips': ['seal_strip_count'],
    'Passlane Seal Rod No.': ['passlane_seal_rod_count'],
    'Pressure Drop, Allow/Calc': ['shell_params.pd', 'tube_params.pd'],
    'Pressure drop, Total/Allow': ['shell_params.pd'],
    'Pressure drop, Total/Allowed': ['shell_params.pd'],
    'Pressure, In/Out': ['shell_params.pressure', 'tube_params.pressure'],
    'Pressure, Inlet/Outlet': ['shell_params.pressure', 'tube_params.pressure'],
    'Required U': ['u_overall'],
    'Shell ID': ['shell_id'],
    'Spacing(c/c)   450.000': ['baffle_spacing'],
    'Specific Heat': ['shell_params.cp', 'tube_params.cp'],
    'Temperature (In/Out)': ['shell_params.temp_in', 'shell_params.temp_out',
               'tube_params.temp_in', 'tube_params.temp_out'],
    'Temperature, In/Out': ['shell_params.temp_in', 'shell_params.temp_out',
               'tube_params.temp_in', 'tube_params.temp_out'],
    'Thermal Conductivity': ['shell_params.k', 'tube_params.k'],
    'Total flow rate': ['shell_params.mass_flow', 'tube_params.mass_flow'],
    'Trans pitch': ['tube_pitch'],
    'Transverse pitch': ['tube_pitch'],
    'Tube ID': ['tube_id'],
    'Tube OD': ['tube_od'],
    'Tube Type': ['tube_layout'],
    'Tube form': ['tube_layout'],
    'Tube pressure drop, Total/Allowed': ['tube_params.pd'],
    'Tube type': ['tube_layout'],
    'Tubecount': ['tube_count'],
    'Tubepasses/Tuberows': ['tube_passes'],
    'Tubeside film coef': ['tube_params.film_coef'],
    'Type': ['exchanger_type'],
    'Velocity': ['shell_params.velocity', 'tube_params.velocity'],
    'Viscosity': ['shell_params.viscosity', 'tube_params.viscosity'],
}

#: 第二轮补映射：第一版手写表遗漏、但**确实对应已登记字段**的标签。
#: 每条都能在 `heat_results` 上找到落点（列或 JSONB 键），不是凑数。
#: 补这些是修正遗漏，不是往目标数字上靠 —— 补完后的数字仍然远低于 95%。
COLUMN_MAP.update({
    # 用户 2026-12-12 裁决落地的新增字段
    "Skin temperature, Min/Max": ["skin_temp_min", "skin_temp_max"],
    "Number of rows": ["tube_rows"],
    "Vapor (In/Out)": ["shell_params.vapor_wt_frac_in",
                       "shell_params.vapor_wt_frac_out",
                       "tube_params.vapor_wt_frac_in",
                       "tube_params.vapor_wt_frac_out"],
    "Liquid": ["shell_params.liquid_wt_frac_in",
               "shell_params.liquid_wt_frac_out",
               "tube_params.liquid_wt_frac_in",
               "tube_params.liquid_wt_frac_out"],
    "Tip clearance": ["ache_params.tip_clearance_mm"],
    # 主表剩余 4 条缺口（用户 2026-12-12「补齐」）
    "Area ratio (fin/bare)": ["extended_area_m2", "bare_area_m2"],
    "Area ratio(out/in)": ["extended_area_m2", "bare_area_m2"],
    "Ratio, Fan/bundle face area": ["fan_face_area_ratio"],
    "Heat transfer safety factor": ["heat_transfer_safety_factor"],
    "Fin height": ["ache_params.fin_height_mm"],
    "Fin thickness at base": ["ache_params.fin_thickness_mm"],
    "Fin root": ["ache_params.fin_root_diameter_mm"],
    "Over fin": ["ache_params.over_fin_diameter_mm"],
    # TODO-056 第二批：解析器 + AcheParams + 注册表 + 写入方都已补齐，
    # 因此从 KNOWN_ACHE_GEOMETRY_GAPS 转正。⚠️ `Air humidity` 在
    # `A-101.xls` 里只有标签与单位、没有值 —— 映射仍然正确
    # （HTRI 在别的工况下会给值），但真实跑它时会是空列。
    "Air humidity": ["ache_params.air_humidity_percent"],
    "Fins per unit length": ["ache_params.fin_density_per_m"],
    "Fin efficiency": ["ache_params.fin_efficiency_percent"],
    "Unfinned length": ["ache_params.unfinned_length_mm"],
    "Unheated length": ["ache_params.unheated_length_mm"],
    # 管束几何（TEMA 的 "Tube No. | 2716 | OD 19.000 mm | ..." 一行多标签）
    "Tubecount Odd/Even": ["tube_count"],
    "Tubecount, Odd rows/Even rows": ["tube_count"],
    "Outside diameter": ["tube_od"],
    "Inside diameter": ["tube_id"],
    "Base thickness": ["tube_wall_thickness"],
    "Layout": ["tube_layout"],
    "Tube form": ["tube_layout"],
    # 并联台数
    "Bays in parallel per unit": ["units_parallel"],
    # 速度（shell/tube 物性里的 velocity）
    "Velocity - Midpoint": ["shell_params.velocity", "tube_params.velocity"],
    "Velocity pressure": ["shell_params.velocity", "tube_params.velocity"],
    "Face velocity": ["shell_params.velocity"],
    "Maximum velocity": ["shell_params.velocity", "tube_params.velocity"],
    "Input maximum velocity": ["shell_params.velocity", "tube_params.velocity"],
    "Input minimum velocity": ["shell_params.velocity", "tube_params.velocity"],
    # 压降
    "Pressure drop": ["shell_params.pd", "tube_params.pd"],
    "Bundle pressure drop": ["shell_params.pd"],
    "Bundle pressure drop/ Velocity pressure": ["shell_params.pd"],
    # 面积
    "Bare area/unit": ["total_area_gross"],
    "Bare area/bundle": ["total_area_gross"],
    "Extended area per unit": ["total_area_gross"],
    "Extended area per bundle": ["total_area_gross"],
    # 风机 / 空冷
    "Motor power/fan-min air temperature": ["ache_params.fan_power_kw"],
    "No/bay": ["ache_params.fan_count"],
    "Nozzle R-V-SQ": ["ache_params.tube_nozzle_count"],
    "R-V-SQ": ["ache_params.tube_nozzle_count"],
    # 密封
    "Edge seals": ["seal_strip_count"],
    # 布置
    "Orientation (from horiz.)": ["orientation"],
})

#: ⚠️ 原 `KNOWN_ACHE_GEOMETRY_GAPS` 已于 TODO-056 第二批删除：它列的 5 个
#: 标签（Air humidity / Fins per unit length / Fin efficiency /
#: Unfinned length / Unheated length）现已解析、登记并写入，转正进
#: `COLUMN_MAP`。
#:
#: 顺带记一笔它原本的毛病：那个常量**定义了却零引用** —— 看上去在守护
#: 「刻意不映射」，实际没有任何代码读它，这些标签会照常落进
#: `unmapped_labels`。「一个零引用的白名单不是白名单」：它让读代码的人
#: 以为这些标签被特殊处理了，而真去查一遍会发现并没有。
#: 将来若再有刻意不映射的字段，要么**接到 `unmapped_labels` 的分类里**
#: （像 `EXTRACTION_NOISE` 那样），要么别写。

#: **提取噪声**：被误当成字段标签的列头/小标题 —— 本身不是字段，
#: 只是恰好后面跟了一个单位（如 `Outlet | Deg C | 54.99` 里的 Outlet 是
#: 「出口温度」这一列的列头，字段标签是 `Temperature, In/Out`）。
#: 单独列出来是为了让读覆盖率的人知道分母里有噪声，而不是把它们藏起来。
EXTRACTION_NOISE = frozenset({
    "In", "Out", "Inlet", "Outlet", "Midpoint", "Face", "Flow",
    "Liq. Out", "Shell Exit", "Bundle Exit", "Maximum", "Fouling",
    "Number", "Height", "Diameter", "Clearance", "Efficiency",
    "Spacing(c/c)   450.000", "Inlet   800.000",
    "Shell ID   1600.00  mm", "Layout   4",
})

#: **基线**，不是目标。
#:
#: 计划/ADR-0028 写的「DETAIL 字段覆盖率 ≥ 95%」已由用户 2026-12-12 裁决放弃：
#: 实测主表口径 64.9%，补完全部已知缺口也只到 73% —— 95% 是在一个更窄的
#: 定义下达成的，那个定义没有被记录下来，无法复现。
#:
#: ⚠️ **所以这里不能用「目标 0」代替**：那会让工具**恒绿**，
#: 而覆盖率工具恒绿比没有工具更坏（它让人以为还在守着）。
#: 改为**基线 + 回归容差**：
#:   - 涨（补字段、修映射）随便涨，永远不报失败
#:   - 跌超过 `REGRESSION_TOLERANCE` 才报 —— 抓的是「有人改坏了」
#:
#: 基线 = `sample/A-101.xls` + `sample/131-E-102-EOR.xls` 在
#: `--scope main` 下的实测值（2026-12-13：用户要求补齐剩余缺口之后）。
#: **先测后填** —— 把基线写成「当前值」再回头测，等于用结果定义起点，
#: 那一刻工具就成了「记录我刚做的事」的镜子。**每个口径一个基线** —— 模板口径 64.9%、
#: 注册口径 53.0%，两者量纲不同，把一个的基线套到另一个上会**误报回归**
#: （第一版就是这么写的：注册口径 53% < 模板下限 62.9% → 报「已回归」，
#: 而实际一个数都没变）。换参考文件后基线要重测。
BASELINE_TEMPLATE_COVERAGE = 0.797   # 59/74 条标签（2026-12-13 实测）
# ⚠️ 2026-12-13 第二次重测：62/**108** 个字段。**分子没动、分母 +5**，
# 所以这个数**因为补了字段而下降** —— 看着像倒退，其实是量纲问题：
# 分母是**全部已登记字段**，分子是**主表口径标签够得着的字段**。
# TODO-056 第二批那 5 个 ACHE 字段的标签都在 `2 - Final Results`，
# 而主表口径只读 `2 - Output Summary`，于是它们进了分母、进不了分子。
# 想看这 5 个字段的覆盖情况：`--sheet "2 - Final Results"`（那里是 49/108）。
BASELINE_REGISTRY_COVERAGE = 0.574   # 62/108 个字段（2026-12-13 实测）
REGRESSION_TOLERANCE = 0.02          # 2 个百分点

#: 判定下限 = 基线 − 容差。**不是**「目标」：只防跌，不追涨。
TEMPLATE_FLOOR = BASELINE_TEMPLATE_COVERAGE - REGRESSION_TOLERANCE
REGISTRY_FLOOR = BASELINE_REGISTRY_COVERAGE - REGRESSION_TOLERANCE


#: 单位词表。HTRI/TEMA 的单位写法不统一 —— Xace 带括号 `(kg/s)`，
#: TEMA 不带（`kg/s`）。两者都要认，否则一份文件能提取到、另一份提不出，
#: 而两者的差异看起来像「TEMA 字段少」。
UNITS = frozenset({
    "C", "Deg C", "K", "kPa", "kPaG", "Pa", "bar", "psi",
    "mm", "cm", "m", "m2", "m3", "kg", "kg/s", "kg/h", "kg/m3",
    "wt%", "%", "m/s", "W/m2-K", "W/m-K", "m2-K/W", "m2-K/W-sec",
    "kJ/kg-C", "kW", "MW", "W", "J/kg-K", "mN-s/m2", "N-s/m2",
    "kg/m-s2", "mm2", "g", "N", "--", "-", "m/s2", "kJ/h",
    "1/s", "ppm", "mg/Nm3", "m3/h", "L/s", "1", "lb/hr", "m3/s", "kcal/h",
})


def is_unit(v) -> bool:
    s = str(v).strip()
    return bool(s) and ((s.startswith("(") and s.endswith(")")) or s in UNITS)


def read_labels_by_sheet(path: Path) -> list[tuple[str, list[str]]]:
    """逐 sheet 返回 `(sheet 名, 该 sheet 的标签)`。"""
    out: list[tuple[str, list[str]]] = []
    for name, rows in _iter_rows(path):
        found: list[str] = []
        for row in rows:
            cells = [str(v).strip() for v in row
                     if v is not None and str(v).strip()]
            for k, a in enumerate(cells):
                if not a[0].isalpha() or is_unit(a):
                    continue
                nxt = cells[k + 1] if k + 1 < len(cells) else None
                if nxt and is_unit(nxt):
                    found.append(a)
        out.append((name, list(dict.fromkeys(found))))
    return out


def main_labels(path: Path) -> tuple[str, list[str]]:
    """**主输出表**的标签 + 表名。

    ## 选哪个 sheet —— 这不是能靠猜决定的

    `A-101.xls` 有 4 个 sheet：`Output Summary`(50 标签)、
    `Final Results`(95)，另两个提不到标签。而计划里的「33 列」落在
    50 与 95 之间 —— 说明**原始取数范围比这两个 sheet 都窄**，计划没写清。

    裁决（用户 2026-10-12）：分母取主表口径。但「主表」仍有歧义：

    | 规则 | 选中的 sheet | A-101 标签数 |
    |---|---|---|
    | 第一个提取到标签的 sheet | `2 - Output Summary` | 50 |
    | 标签最多的 sheet | `2 - Final Results` | 95 |

    本实现取**第一个提取到标签的 sheet**：HTRI/TEMA 输出的惯例是摘要表
    排在最前，而「标签最多」会把明细诊断表选成主表 —— 那不是「主」。

    ⚠️ 这仍是**代理规则**，不是业务事实。故：
    1. 返回表名，调用方必须显示（`main()` 会打印）；
    2. `main()` 同时打印**每个 sheet 的标签数**，让口径的敏感度可见；
    3. `--sheet` 可显式指定，绕开代理规则。
    """
    sheets = read_labels_by_sheet(path)
    productive = [(n, ls) for n, ls in sheets if ls]
    if not productive:
        return "", []
    return productive[0]


def read_labels(path: Path) -> list[str]:
    """提取一份 HTRI/TEMA 输出里的**字段标签**（跨全部工作表）。

    ## 为什么不能读「表头行」

    第一版读第 0 行当表头 —— 那是**报表标题**（`Final Results` / `Page 2`），
    不是字段名。而这两份文件的字段是**标签 + 单位 + 数值**的竖排结构，
    一个标签后面隔着 4 个空单元格才到单位（合并单元格布局）。
    读表头行得到的是 0 个字段、覆盖率 100% —— 又一次「测的不是出问题那层」。

    ## 判定规则

    「字符串单元格 + 本行**下一个非空**单元格是单位」→ 该字符串是字段标签。
    「下一个非空」而不是「紧邻」：Xace 的标签与单位之间隔着合并单元格。
    同一行可以有**两组**标签（空气侧 / 管程侧），规则对两者都成立。

    **漏提取是安全方向**：无单位的字段（`Fluid name`）提不到，
    覆盖率被低估 —— 低估不会让「≥95%」假通过，多提才会。
    """
    out: list[str] = []
    for _name, labels in read_labels_by_sheet(path):
        out += labels
    return list(dict.fromkeys(out))


def _iter_rows(path: Path):
    """逐工作表产出 `(sheet 名, 行列表)`。**.xls 读不动时经 LibreOffice 兜底。"""
    import openpyxl
    import xlrd

    if path.suffix.lower() in (".xls", ".xlt"):
        try:
            # ⚠️ 必须给 `logfile` 一个丢弃句柄：xlrd 的 OLE2 一致性警告
            # 默认写 **stdout**，会把 `--json` 的输出污染成非法 JSON，
            # 任何 `tool --json | jq` 的调用方当场炸。实测 131-E-102-EOR.xls
            # 就会打这一行。
            book = xlrd.open_workbook(str(path), logfile=open(os.devnull, "w"))
            for sheet in book.sheets():
                yield sheet.name, [sheet.row_values(i) for i in range(sheet.nrows)]
            return
        except Exception as e:  # noqa: BLE001 —— xlrd 对损坏定义名抛多种异常
            print(f"[warn] xlrd 读 {path.name} 失败（{type(e).__name__}: {e}），"
                  "改用 LibreOffice 转换", file=sys.stderr)
            yield from _iter_rows(_lo_convert(path))
            return

    book = openpyxl.load_workbook(path, read_only=True, data_only=True)
    try:
        for sheet in book.worksheets:
            yield sheet.title, [list(r) for r in sheet.iter_rows(values_only=True)]
    finally:
        book.close()


def _lo_convert(path: Path) -> Path:
    """LibreOffice headless 转 xlsx，返回产物路径。

    临时目录，**不入库**。131-E-102-EOR.xls 里有一条损坏的定义名公式
    （`Token 0x2d (AreaN) found in NAME formula`），xlrd 解析 globals 时就抛，
    `ignore_workbook_corruption=True` 也拦不住（它只在别的损坏类型上生效）。
    """
    import subprocess
    import tempfile

    out = Path(tempfile.mkdtemp(prefix="htri_conv_"))
    subprocess.run(
        ["soffice", "--headless", "--convert-to", "xlsx", "--outdir", str(out), str(path)],
        check=True, capture_output=True, timeout=300,
    )
    return out / (path.stem + ".xlsx")


def compute_coverage(labels: list[str], *,
                     level: str = "DETAIL") -> dict:
    """覆盖率。**两个口径都算**，因为「覆盖率」本身有两种读法。

    | 口径 | 公式 | 回答的问题 |
    |---|---|---|
    | `template_coverage` | 服务得了的标签 / 标签总数 | 客户拿 HTRI 报告，
                                                  我们**认得几项** |
    | `registry_coverage` | 被模板覆盖的已登记字段 / 已登记字段数 | 我们宣称的
                                                  DETAIL 字段里，**有几项
                                                  真有数据源** |

    两者的分母不同，数值可以差很远。计划只写「≥95%」没写哪个口径 ——
    所以工具**两个都给**，不替人挑。

    一条 HTRI 标签常常对应**两个**注册字段（`Temperature, In/Out` →
    `shell_params.temp_in` / `shell_params.temp_out` / `tube_params.*`），
    所以映射值是列表而非单个字段名。
    """
    from app.services.report.datasource_registry import DATASOURCES

    fields = DATASOURCES["HEAT_RESULTS"].fields
    scoped = {n for n, s in fields.items()
              if level == "DETAIL" or s.level in (None, "BASIC")}

    covered: set[str] = set()
    unmapped: list[str] = []
    noise: list[str] = []
    served_labels = 0          # ⚠️ 数**标签**，不是字段 —— 见下面的量纲说明
    for label in labels:
        if label in EXTRACTION_NOISE:
            noise.append(label)
            continue
        targets = COLUMN_MAP.get(label)
        if not targets:
            unmapped.append(label)
            continue
        covered.update(targets)
        if any(t in fields for t in targets):
            served_labels += 1

    unknown_targets = sorted(t for t in covered if t not in fields)
    served = covered & scoped

    def pct(num: int, den: int) -> float:
        return 0.0 if den == 0 else num / den

    # ⚠️ 分母**含**提取噪声。剔除噪声会让数字好看一点，但那是改分母去凑
    # 目标 —— 噪声是提取规则的已知偏差，该显示出来而不是藏起来。
    return {
        "level": level,
        # ⚠️ 分子分母**量纲必须一致**：分子数「服务得起的**标签**数」，
        # 不是「服务得起的**字段**数」。一条标签会映射到多个字段
        # （`Temperature, In/Out` → shell/tube × in/out 共 4 个），
        # 用字段数当分子会算出 **112% 的覆盖率** —— 一个不可能的值，
        # 而它一路显示得很正常。
        "template_coverage": pct(served_labels, len(labels)),
        "served_labels": served_labels,
        "registry_coverage": pct(len(served), len(scoped)),
        # ⚠️ 判定的是**回归**，不是「达标」：两个口径都没跌过容差即未回归。
        "baselines": {"template": BASELINE_TEMPLATE_COVERAGE,
                      "registry": BASELINE_REGISTRY_COVERAGE},
        "floors": {"template": TEMPLATE_FLOOR, "registry": REGISTRY_FLOOR},
        # ⚠️ 每个口径对**自己**的基线。两个口径量纲不同，混用会误报。
        "regressed": (pct(served_labels, len(labels)) < TEMPLATE_FLOOR
                      or pct(len(served), len(scoped)) < REGISTRY_FLOOR),
        # 保留 `target` 键名（前端/脚本可能已依赖）但语义改为「判定下限」，
        # 且明确不再有 95% 的目标 —— 避免下游读到一个看似仍存在的验收线。
        "target": None,
        "template_labels": len(labels),
        "real_labels": len(labels) - len(noise),
        "mapped_labels": len(labels) - len(unmapped) - len(noise),
        "registry_fields": len(scoped),
        "covered_fields": sorted(served),
        "unmapped_labels": sorted(unmapped),
        "extraction_noise": sorted(noise),
        "mapped_to_unknown_fields": unknown_targets,
        "registry_fields_without_template_source": sorted(scoped - served),
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="HEAT DETAIL 字段覆盖率")
    ap.add_argument("references", nargs="*", help="HTRI/TEMA 参考文件（.xls/.xlsx）")
    ap.add_argument("--level", default="DETAIL", choices=["BASIC", "DETAIL"])
    ap.add_argument("--scope", default="main", choices=["main", "all"],
                    help="main=每个文件的主输出表（**默认**，用户 2026-10-12 "
                         "裁决的分母）；all=全部工作表的所有标签")
    ap.add_argument("--sheet", action="append", default=None,
                    help="显式指定参考文件的 sheet 名（可多次，对应多个文件）；"
                         "不给则用主表代理规则")
    ap.add_argument("--json", action="store_true", help="只输出 JSON")
    args = ap.parse_args(argv)

    if not args.references:
        print("未提供参考文件。覆盖率无从计算 —— "
              "**这不是「0% 通过」**。", file=sys.stderr)
        return 2
    paths = [Path(p) for p in args.references]
    missing = [p for p in paths if not p.exists()]
    if missing:
        print(f"参考文件不存在：{[str(p) for p in missing]}", file=sys.stderr)
        return 2

    labels: list[str] = []
    sheets: dict[str, str] = {}
    per_sheet_detail: dict[str, list] = {}
    for p in paths:
        if args.scope == "all":
            labels += read_labels(p)
            sheets[str(p)] = "(全部工作表)"
        elif args.sheet:
            by_name = dict(read_labels_by_sheet(p))
            want = args.sheet[paths.index(p)] if paths.index(p) < len(args.sheet) else None
            if want not in by_name:
                print(f"{p.name} 没有 sheet [{want}]；实有：{list(by_name)}",
                      file=sys.stderr)
                return 2
            sheets[str(p)] = want
            labels += by_name[want]
        else:
            # ⚠️ **只读一次**。先前的写法先 `main_labels(p)` 再
            # `read_labels_by_sheet(p)` —— 同一个文件被解两次，.xls 的
            # LibreOffice 转换也因此跑两遍（warning 打两行、慢一倍）。
            detail = read_labels_by_sheet(p)
            per_sheet_detail[p.name] = detail
            productive = [(n, x) for n, x in detail if x]
            sheet, ls = productive[0] if productive else ("", [])
            sheets[str(p)] = sheet
            labels += ls
    labels = list(dict.fromkeys(labels))
    r = compute_coverage(labels, level=args.level)
    r["references"] = [str(p) for p in paths]
    r["scope"] = args.scope
    r["sheets_used"] = sheets
    r["sheet_label_counts"] = {
        fname: {n: len(ls) for n, ls in det}
        for fname, det in per_sheet_detail.items()}

    if args.json:
        print(json.dumps(r, ensure_ascii=False, indent=2))
    else:
        print(f"level={r['level']}  scope={args.scope}")
        for f, sh in sheets.items():
            print(f"  {Path(f).name} → 取自 [{sh}]")
        if per_sheet_detail:
            print("  各 sheet 标签数（口径敏感度 —— 换个 sheet 分母就变）：")
            for fname, sheets_ in per_sheet_detail.items():
                detail = "、".join(f"{n}:{len(ls)}" for n, ls in sheets_)
                print(f"    {fname}  {detail}")
        print(f"  标签 {r['template_labels']}"
              f"（提取噪声 {len(r['extraction_noise'])}），"
              f"已登记字段 {r['registry_fields']}")
        tc = r["template_coverage"] * 100
        rc = r["registry_coverage"] * 100
        print(f"  模板口径（认得几项）: {tc:5.1f}%  "
              f"{r['served_labels']}/{r['template_labels']}")
        print(f"  注册口径（覆盖几项）: {rc:5.1f}%  "
              f"{len(r['covered_fields'])}/{r['registry_fields']}")
        print(f"  基线 模板 {r['baselines']['template'] * 100:.1f}% / "
              f"注册 {r['baselines']['registry'] * 100:.1f}%"
              f"（各扣 {REGRESSION_TOLERANCE * 100:.0f}pp 容差）"
              f" → {'未回归' if not r['regressed'] else '**已回归**'}")
        print("  注：95% 目标已由用户 2026-12-12 裁决放弃；此处只防回归，不追覆盖率")
        if r["extraction_noise"]:
            sample = "、".join(r["extraction_noise"][:8])
            print(f"\n  · 提取噪声（{len(r['extraction_noise'])}）—— 规则偏差，"
                  f"不是字段缺口：{sample} …")
        if r["unmapped_labels"]:
            print(f"\n  ⚠ 服务不了的标签（{len(r['unmapped_labels'])}）：")
            for x in r["unmapped_labels"]:
                print(f"    ? {x}")
        if r["mapped_to_unknown_fields"]:
            print(f"\n  ⚠ COLUMN_MAP 指向未登记字段：{r['mapped_to_unknown_fields']}")
    return 1 if r["regressed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
