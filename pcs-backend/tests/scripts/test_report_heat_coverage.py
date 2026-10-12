"""c4/c5：HEAT DETAIL 覆盖率工具的测试。

## 为什么工具本身也要测

这个工具的唯一产出是「一个百分比」。而百分比工具最常见的失败模式是
**恒返回好看的数字**：

- 提取不到任何字段 → 分母 0 → 报「全覆盖」（第一版就犯过：读表头行，
  而这两份文件的第 0 行是报表标题不是字段名）
- 分母定成「已映射列数」 → 分子 = 分母 → **恒 100%**（第二版犯过）
- COLUMN_MAP 拼错一个字母 → 所有列进 UNMAPPED → 分母 0 → 又恒真

三种都「通过」，且都一列没比对。**一个恒真的指标比没有指标更坏**，
因为它让人以为已经验过了。所以下面每条测试都盯住一个「恒真」入口。

## 真实参考文件

`sample/A-101.xls`（HTRI Xace，空冷器）与 `sample/131-E-102-EOR.xls`
（TEMA Xist，管壳式）**不入 git**，所以这部分是「有文件才跑」——
不用 skip-strict：文件到位时测试要能自己跑起来。

⚠️ `A-101.xls` 有 **4 个工作表**，字段散在 `Output Summary`(50) 与
`Final Results`(95) 两处。只读第一个会漏掉近 2/3 的字段 —— 而漏读让分母
变小、覆盖率**虚高**，正好是「测的不是出问题那一层」。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.report_heat_coverage import (
    BASELINE_REGISTRY_COVERAGE,
    BASELINE_TEMPLATE_COVERAGE,
    COLUMN_MAP,
    REGRESSION_TOLERANCE,
    compute_coverage,
    is_unit,
    main,
    main_labels,
    read_labels,
)

#: `parents[3]` = 仓库根（PCS/），sample/ 在它下面。
#: ⚠️ 写成 `parents[3].parent / "sample"` 会指到 code_project/sample ——
#: 路径错一级，而后果是**静默 skip**：测试绿着、真实文件一条没比对。
SAMPLE_DIR = Path(__file__).resolve().parents[3] / "sample"
HTRI_XACE = SAMPLE_DIR / "A-101.xls"
TEMA_SHELL = SAMPLE_DIR / "131-E-102-EOR.xls"
_PRESENT = [p for p in (HTRI_XACE, TEMA_SHELL) if p.exists()]


def _need_samples() -> None:
    if not _PRESENT:
        pytest.skip("sample/ 下没有 HTRI/TEMA 参考文件（见 TODOS.md TODO-055）")


@pytest.fixture
def partial_xlsx(tmp_path):
    """合成一份参考文件：**3 个已映射标签 + 1 个未映射标签**。

    用的是 COLUMN_MAP 里**真实存在**的标签名 —— 合成文件也得走真实代码路径，
    否则测的是「我造的名字碰巧能映射」。
    """
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.append(["Total flow rate", "(kg/s)", "17.8",
                      "Temperature, In/Out", "(Deg C)", "32.0",
                      "Area", "(m2)", "120.0",
                      "某个 HTRI 专有列", "(m2)", "1"])
    p = tmp_path / "partial.xlsx"
    wb.save(p)
    return p


# --- 退出码 -------------------------------------------------------------------


def test_missing_reference_exits_2_not_0(tmp_path):
    """没有参考文件 → 退出码 **2**。

    **不是 0**。「没找到参考文件」若返回 0，CI 会把它读成「覆盖率达标」——
    而实际一行都没比对。这是「绿灯测的不是出问题那层」的又一个变种。
    """
    assert main([]) == 2
    assert main([str(tmp_path / "nope.xls")]) == 2


def test_partial_coverage_exits_1(partial_xlsx):
    """合成 fixture 覆盖率远低于基线 → 判回归 → 退出码 1。"""
    assert main([str(partial_xlsx)]) == 1


# --- 提取规则 -----------------------------------------------------------------


def test_unit_recognises_both_xace_and_tema_notations():
    """Xace 单位带括号 `(kg/s)`，TEMA 不带 `kg/s`。两种都要认。

    只认一种的后果是一份文件能提取、另一份提不出，而那看起来像
    「TEMA 字段少」——一个会被当成数据结论的提取缺陷。
    """
    assert is_unit("(kg/s)")
    assert is_unit("kg/s")
    assert is_unit("m2-K/W")
    assert not is_unit("Total flow rate")
    assert not is_unit("17.797")


def test_labels_are_found_despite_gaps_between_label_and_unit(tmp_path):
    """标签与单位之间隔着**空单元格**（合并单元格布局）。

    第一版按「紧邻」判定 → 一条都提取不到 → 分母 0 → 报 100% 通过。
    这是本工具最隐蔽的一个恒真入口。
    """
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.append(["Total flow rate", None, None, None, None, "(kg/s)", "17.8"])
    p = tmp_path / "gapped.xlsx"
    wb.save(p)

    labels = read_labels(p)
    assert "Total flow rate" in labels, \
        "标签与单位之间的空单元格必须被跳过 —— 紧邻判定会漏掉全部字段"


def test_extraction_reads_every_sheet_not_just_the_first(tmp_path):
    """⚠️ 用户提示：**多个工作表**。

    `A-101.xls` 有 4 个 sheet，字段散在 `Output Summary`(50) 与
    `Final Results`(95)。只读第一个会漏掉近 2/3 的字段 ——
    而漏读让分母变小、覆盖率**虚高**。
    """
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.title = "Summary"
    wb.active.append(["Area", "(m2)", "120"])
    second = wb.create_sheet("Details")
    second.append(["Tube OD", "(mm)", "19"])
    p = tmp_path / "multi.xlsx"
    wb.save(p)

    labels = read_labels(p)
    assert {"Area", "Tube OD"} <= set(labels), \
        f"第二个 sheet 的字段没被提取：{labels}"


def test_extraction_noise_is_separated_from_real_gaps(partial_xlsx):
    """被误当成标签的列头（`Inlet` / `Outlet` / `Midpoint`）单列一份。

    它们不是字段缺口，是提取规则的已知偏差。混进缺口清单里会让人
    去补根本不存在的字段。
    """
    r = compute_coverage(read_labels(partial_xlsx))
    assert "extraction_noise" in r
    assert set(r["unmapped_labels"]) & set(r["extraction_noise"]) == set(), \
        "噪声与缺口必须是不相交的两份清单"


# --- 指标不能恒真 -------------------------------------------------------------


def test_coverage_is_not_structurally_always_full():
    """⚠️ 反回归：分母若定成「已映射列数」，覆盖率恒等于 1.0。

    第二版就是这么写的：分母 = 已映射，分子 = 已映射 ∩ 已登记，
    而「映射目标必须已登记」又保证了已映射 ⊆ 已登记 —— 分子 = 分母。
    """
    r = compute_coverage(["Total flow rate", "Area",
                          "某个没见过的列", "又一个没见过的"])
    assert r["template_coverage"] < 1.0, \
        "分母必须含未映射的模板标签；恒等于 1.0 说明分母又定义错了"


def test_nothing_extracted_is_zero_not_full():
    """一条都提不出来 → 0%，不是 100%。"""
    r = compute_coverage(["完全没见过的列 A", "完全没见过的列 B"])
    assert r["template_coverage"] == 0.0
    assert r["regressed"] is True, "一条都提不出来必须是回归，不是「未回归」"


def test_map_targets_must_exist_in_registry():
    """COLUMN_MAP 的每个目标都必须在注册表里 —— 否则映射指向一个查不出的
    字段，覆盖率会替一个不存在的字段记功。"""
    from app.services.report.datasource_registry import DATASOURCES

    registered = set(DATASOURCES["HEAT_RESULTS"].fields)
    unknown = sorted({t for v in COLUMN_MAP.values() for t in v
                      if t not in registered})
    assert not unknown, f"COLUMN_MAP 指向未登记的字段：{unknown}"


def test_coverage_can_never_exceed_one():
    """⚠️ 反回归：一条标签映射到**多个**字段时，用字段数当分子会算出
    **112% 的覆盖率** —— 一个不可能的值，而它一路显示得很正常。

    `Temperature (In/Out)` 一条标签就对应 shell/tube × in/out 共 4 个
    注册字段。分子分母必须都是**标签**。
    """
    r = compute_coverage(["Temperature (In/Out)", "Temperature, In/Out"])
    assert 0 <= r["template_coverage"] <= 1.0, \
        f"覆盖率 {r['template_coverage']:.1%} 越界 —— 分子分母量纲不一致"
    assert r["served_labels"] == 2
    assert len(r["covered_fields"]) > 2, \
        "这两条标签应当映射到 4 个以上字段（正是量纲错配的来源）"


def test_two_denominators_disagree():
    """两个口径的数值必须不同 —— 相同说明其中一个算错了。"""
    r = compute_coverage(["Total flow rate", "Area", "某个没见过的列"])
    assert r["template_coverage"] != r["registry_coverage"]


def test_no_95_percent_target_remains():
    """95% 目标已由用户 2026-12-12 裁决放弃，工具里不得残留。

    ⚠️ 关键不是「删掉 0.95」，而是**不能把它换成 0** —— 那会让工具恒绿，
    而覆盖率工具恒绿比没有工具更坏。现在是**基线 + 回归容差**：
    涨随便涨，跌超容差才报。
    """
    from scripts import report_heat_coverage as tool

    assert not hasattr(tool, "TARGET_COVERAGE"), \
        "95% 目标仍在工具里 —— 裁决已放弃它"
    # 基线是**实测值**（2026-12-13：用户要求补齐剩余缺口之后重测）。
    # ⚠️ 不要在补字段之后忘了改这里 —— 那会让基线仍停在旧值，
    # 补字段反被报成「无变化」，或者反过来把基线写成当前值而失去意义。
    assert BASELINE_TEMPLATE_COVERAGE == pytest.approx(0.797, abs=0.005)
    assert BASELINE_REGISTRY_COVERAGE == pytest.approx(0.602, abs=0.005)
    assert 0 < REGRESSION_TOLERANCE < 0.1


def test_each_metric_is_judged_against_its_own_baseline():
    """⚠️ 量纲：模板口径与注册口径的基线不同（64.9% / 53.0%）。

    把模板基线套到注册口径上 → 注册口径 53% < 模板下限 62.9% → 误报
    「已回归」，而实际一个数都没变。第一版就是这么写的。
    """
    from scripts import report_heat_coverage as tool

    assert tool.TEMPLATE_FLOOR != tool.REGISTRY_FLOOR, \
        "两个口径的下限相同 —— 基线被跨口径套用了"
    assert (tool.TEMPLATE_FLOOR - tool.REGISTRY_FLOOR) == pytest.approx(
        BASELINE_TEMPLATE_COVERAGE - BASELINE_REGISTRY_COVERAGE)


def test_real_files_are_not_regressed():
    """真实文件跑出来必须是「未回归」。"""
    if not (HTRI_XACE.exists() and TEMA_SHELL.exists()):
        pytest.skip("sample/ 下缺参考文件")
    out = _run_json([str(HTRI_XACE), str(TEMA_SHELL)])
    assert out["regressed"] is False, \
        f"覆盖率回归了：模板 {out['template_coverage']:.1%} "\
        f"注册 {out['registry_coverage']:.1%}"
    assert out["target"] is None, "输出里不应再有 95% 目标"


def test_json_mode_emits_parseable_json(partial_xlsx, capsys):
    """⚠️ xlrd 的 OLE2 一致性警告默认写 **stdout**，会把 `--json` 污染成
    非法 JSON，`tool --json | jq` 当场炸。实测 131-E-102-EOR.xls 会打这一行。"""
    main([str(partial_xlsx), "--json"])
    json.loads(capsys.readouterr().out)


# --- 真实参考文件 -------------------------------------------------------------


@pytest.mark.parametrize("path", [HTRI_XACE, TEMA_SHELL])
def test_real_reference_files_yield_labels(path):
    """真实文件必须能提取出标签 —— 提取规则对真实布局有效。"""
    if not path.exists():
        pytest.skip(f"{path.name} 不在 sample/")
    assert len(read_labels(path)) > 10, \
        f"{path.name} 提取到的标签太少 —— 提取规则多半错了"


def test_real_xace_reads_both_content_sheets():
    """Xace 的字段横跨 `Output Summary` 与 `Final Results` 两个 sheet。"""
    if not HTRI_XACE.exists():
        pytest.skip("A-101.xls 不在 sample/")
    import xlrd

    book = xlrd.open_workbook(str(HTRI_XACE), logfile=open(os.devnull, "w"))
    per_sheet = []
    for sheet in book.sheets():
        found = set()
        for i in range(sheet.nrows):
            cells = [str(v).strip() for v in sheet.row_values(i)
                     if v is not None and str(v).strip()]
            for k, a in enumerate(cells):
                if not a[0].isalpha() or is_unit(a):
                    continue
                nxt = cells[k + 1] if k + 1 < len(cells) else None
                if nxt and is_unit(nxt):
                    found.add(a)
        per_sheet.append((sheet.name, len(found)))

    productive = [n for n, c in per_sheet if c > 5]
    assert len(productive) >= 2, \
        f"只有 {len(productive)} 个 sheet 提取到字段：{per_sheet} —— 只读了部分工作表"


def test_real_coverage_is_measured_and_honest():
    """真实文件跑出来的覆盖率必须**是一个具体的数**，未达标就说未达标。

    ⚠️ 不钉死具体数值：映射表会随缺口补齐而变（那是好事）。这里钉的是
    「工具跑得动、数不是恒 100%、未达标的清单非空」。
    """
    _need_samples()
    # ⚠️ 必须走**主表**提取，与量基线时用的是同一条路径。
    # 用 `read_labels`（全部工作表）会得到 52.8%，而基线 64.9% 是主表口径量的
    # —— 拿全表去比主表基线，会报一个「回归」而实际什么都没变。
    labels: list[str] = []
    for p in (HTRI_XACE, TEMA_SHELL):
        labels += main_labels(p)[1]
    r = compute_coverage(list(dict.fromkeys(labels)), level="DETAIL")
    assert 0 < r["template_coverage"] < 1.0, \
        "覆盖率是 0 或 1 —— 前者是提取全败，后者是映射全中，都得查"
    # 2026-12-13：用户要求补齐剩余缺口后，真实模板已**零缺口**。
    # 这条断言原来是「清单不该是空的」—— 那是在缺口存在时的期望。
    # 现在反过来了：清单为空是**期望状态**，而「工具会不会报缺口」
    # 由合成 fixture 的 `test_unmapped_columns_lower_coverage_and_are_listed`
    # 保证 —— 真实模板全被覆盖时，拿它来证明「工具能报缺口」是做不到的。
    assert r["unmapped_labels"] == [], \
        f"真实模板应零缺口，实得 {r['unmapped_labels']}"
    assert r["regressed"] is False, \
        f"真实文件回归了：{r['template_coverage']:.1%} / {r['registry_coverage']:.1%}"

# --- 主表口径（用户 2026-12-12 裁决）-------------------------------------------


def test_main_scope_picks_first_productive_sheet_not_the_biggest(tmp_path):
    """主表 = **第一个**提取到标签的 sheet，不是标签最多的。

    `A-101.xls` 有 `2 - Output Summary`(50) 与 `2 - Final Results`(95)。
    选「标签最多」会把明细诊断表选成主表 —— 那不是「主」，而 HTRI/TEMA
    输出的惯例是摘要表排在最前。
    """
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.title = "Summary"
    wb.active.append(["Area", "(m2)", "120"])
    detail = wb.create_sheet("Details")
    for row in (["Tube OD", "(mm)", "19"], ["Tube Pitch", "(mm)", "25"],
                ["Diameter", "(mm)", "894"]):
        detail.append(row)
    p = tmp_path / "x.xlsx"
    wb.save(p)

    name, labels = main_labels(p)
    assert name == "Summary", f"选中了 {name}，应选第一个有标签的 sheet"
    assert labels == ["Area"], "主表标签不该包含 Details 的字段"


def test_main_scope_reports_which_sheet_it_used():
    """⚠️ 静默换分母是这类指标最容易被忽略的作弊 —— 表名必须进输出。"""
    if not HTRI_XACE.exists():
        pytest.skip("A-101.xls 不在 sample/")
    out = _run_json([str(HTRI_XACE)])
    assert out["scope"] == "main"
    assert "Output Summary" in out["sheets_used"][str(HTRI_XACE)]
    # 每个 sheet 的标签数也必须给出来，让口径的敏感度可见
    assert out["sheet_label_counts"][HTRI_XACE.name]


def test_sheet_option_overrides_the_proxy_rule():
    """显式 `--sheet` 能绕开代理规则。"""
    if not HTRI_XACE.exists():
        pytest.skip("A-101.xls 不在 sample/")
    default = _run_json([str(HTRI_XACE)])
    explicit = _run_json([str(HTRI_XACE), "--sheet", "2 - Final Results"])
    assert explicit["sheets_used"][str(HTRI_XACE)] == "2 - Final Results"
    assert explicit["template_labels"] > default["template_labels"], \
        "Final Results 标签更多 —— 换个 sheet 分母确实会变（所以要显式）"


def _run_json(argv) -> dict:
    """跑 CLI 的 --json 模式并解析结果。"""
    import contextlib
    import io

    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        main([*argv, "--json"])
    return json.loads(buf.getvalue())
