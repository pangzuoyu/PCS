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
    COLUMN_MAP,
    TARGET_COVERAGE,
    compute_coverage,
    is_unit,
    main,
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
    assert r["passed"] is False


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


def test_target_is_95_percent():
    """SPEC/计划的验收目标是 ≥95%，写死在工具里而不是散在文档。"""
    assert TARGET_COVERAGE == 0.95


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
    labels: list[str] = []
    for p in (HTRI_XACE, TEMA_SHELL):
        labels += read_labels(p)
    r = compute_coverage(list(dict.fromkeys(labels)), level="DETAIL")
    assert 0 < r["template_coverage"] < 1.0, \
        "覆盖率是 0 或 1 —— 前者是提取全败，后者是映射全中，都得查"
    assert r["unmapped_labels"], "真实模板必然有我们服务不了的标签，清单不该是空的"
    assert r["passed"] == (r["template_coverage"] >= TARGET_COVERAGE
                          and r["registry_coverage"] >= TARGET_COVERAGE)