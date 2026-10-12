"""c5 覆盖率工具的测试。

## 为什么工具本身也要测

这个工具的唯一产出是「一个百分比」。而百分比工具最常见的失败模式是
**恒返回好看的数字**：映射表为空时覆盖率是 1.0（分母 0 → 判为全覆盖），
COLUMN_MAP 里的列名拼错时所有列都进 UNMAPPED（分母 0 → 又是 1.0）——
两种情况下它都报「100%，通过」。**没有输入的通过是没有意义的。**

所以本文件用**合成基准文件**（临时造的 xlsx，表头是 HTRI/TEMA 真实列名）
把工具的四个分支都钉住：全覆盖、部分覆盖、映射缺失、不达标。
"""
from __future__ import annotations

import json

import pytest

from scripts.report_heat_coverage import (
    COLUMN_MAP,
    TARGET_COVERAGE,
    compute_coverage,
    main,
    read_headers,
)


@pytest.fixture
def reference_xlsx(tmp_path):
    """合成一份 HTRI 风格输出：全部列名都在 COLUMN_MAP 里有对应。"""
    import openpyxl

    covered = sorted(set(COLUMN_MAP.values()))
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Xace"
    ws.append(["TagNumber", "Area", "Heat Duty", "Overall U", "LMTD",
               "Shell Inlet Temp", "Tube Outlet Temp", "Tube OD",
               "Baffle Spacing", "Fan Power"])
    wb.save(tmp_path / "121-A-101.xlsx")
    return tmp_path / "121-A-101.xlsx", covered


def test_missing_reference_exits_2_not_0(tmp_path):
    """没有参考文件 → 退出码 2。

    **不是 0**。「没找到参考文件」若返回 0，CI 会把它读成「覆盖率达标」——
    而实际上一行都没比对。这是「绿灯测的不是出问题那层」的又一个变种。
    """
    assert main([]) == 2
    assert main([str(tmp_path / "nope.xls")]) == 2


def test_reads_headers_from_every_sheet(tmp_path):
    """HTRI/TEMA 的字段散在多个 sheet，只读第一个会漏掉大半。"""
    import openpyxl

    wb = openpyxl.Workbook()
    wb.active.title = "Geometry"
    wb.active.append(["Tube OD", "Tube Pitch"])
    ws2 = wb.create_sheet("Thermal")
    ws2.append(["Shell Side Resistance", "Fouling Resistance"])
    p = tmp_path / "multi.xlsx"
    wb.save(p)

    headers = read_headers(p)
    assert set(headers) == {"Tube OD", "Tube Pitch",
                            "Shell Side Resistance", "Fouling Resistance"}


def test_full_coverage_is_reported_as_full(reference_xlsx):
    path, covered = reference_xlsx
    r = compute_coverage(read_headers(path))
    assert r["coverage"] == 1.0
    assert r["passed"] is True
    assert r["unmapped_template_columns"] == []


def test_empty_mapping_does_not_report_full_coverage():
    """⚠️ 关键一条：模板列全都不认识时，**绝不能**报 100%。

    分母为 0 时若直接判「全覆盖」，那么 COLUMN_MAP 拼错一个字母
    就会让整个工具报「100% 通过」—— 而它一列都没比对上。
    """
    r = compute_coverage(["完全没见过的列 A", "完全没见过的列 B"])
    assert r["mapped_columns"] == 0
    assert r["unmapped_template_columns"] == ["完全没见过的列 A", "完全没见过的列 B"]
    assert r["coverage"] == 0.0, \
        "一列都服务不了必须是 0%，不是 100%"
    assert r["passed"] is False


def test_partial_coverage_lists_what_is_missing(tmp_path):
    """部分覆盖要报出**具体缺哪些**，不只是个百分比。

    分母是「已映射的模板列数」，所以要制造部分覆盖，得让模板里只出现
    少数几个已知列 —— 那样它们覆盖的注册字段就只占登记总数的一小部分。
    """
    import openpyxl

    wb = openpyxl.Workbook()
    # 必须含**未映射**列才能造成部分覆盖：新定义下「已映射列 / 全部列」，
    # 纯已映射的输入必然 100%（这正是那个恒真指标的由来）。
    wb.active.append(["TagNumber", "Area", "某个 HTRI 专有列"])
    p = tmp_path / "partial.xlsx"
    wb.save(p)
    r = compute_coverage(read_headers(p))
    assert 0 < r["coverage"] < 1.0
    assert "lmtd" not in r["covered"]
    assert "lmtd" in r["registered_fields_not_in_template"], \
        "清单必须点名到具体字段，否则没人知道下一步做什么"
    assert r["passed"] is False


def test_unmapped_columns_lower_coverage_and_are_listed():
    """未识别的模板列**降低**覆盖率，并逐条列出。

    它确实是我们服务不了的列 —— 那就该计入分母。清单指名道姓地说
    「需要补 COLUMN_MAP 或补数据模型列」，方向是明确的。
    """
    r = compute_coverage(["TagNumber", "某个没见过的列"])
    assert r["unmapped_template_columns"] == ["某个没见过的列"]
    assert r["coverage"] == 0.5, "服务不了的一列必须计入分母"
    assert r["passed"] is False


def test_registered_but_unused_is_not_a_gap():
    """注册了但模板用不到的字段**不是缺口** —— 模板不需要 ≠ 我们缺。

    所以它不进 `unmapped_template_columns`（那是真缺口），只单列一份
    供参考。混淆这两者是这类报告最常见的自欺。
    """
    r = compute_coverage(["TagNumber"])
    assert "lmtd" in r["registered_fields_not_in_template"]
    assert "lmtd" not in r["unmapped_template_columns"]
    assert r["coverage"] == 1.0, "模板只有一列且服务得了 → 100%"


def test_coverage_is_not_structurally_always_full():
    """⚠️ 反回归：分母若定成「已映射列数」，覆盖率恒等于 1.0。

    第一版就是这么写的：分母 = 已映射，分子 = 已映射 ∩ 已登记，
    而「COLUMN_MAP 目标必须已登记」又保证了已映射 ⊆ 已登记 ——
    分子 = 分母，工具永远报满分。这是本测试存在的唯一理由。
    """
    headers = ["TagNumber", "Area", "LMTD", "某个没见过的列", "又一个没见过的"]
    r = compute_coverage(headers)
    assert r["coverage"] == pytest.approx(3 / 5), \
        "分母必须是模板源的全部列；恒等于 1.0 说明分母又定义错了"
    assert r["passed"] is False


def test_map_targets_must_exist_in_registry():
    """COLUMN_MAP 的每个目标都必须在注册表里 —— 否则映射指向一个
    查不出的字段，覆盖率会替一个不存在的字段记功。"""
    from app.services.report.datasource_registry import DATASOURCES

    registered = set(DATASOURCES["HEAT_RESULTS"].fields)
    unknown = sorted({t for t in COLUMN_MAP.values() if t not in registered})
    assert not unknown, f"COLUMN_MAP 指向未登记的字段：{unknown}"


def test_cli_exit_codes(reference_xlsx, tmp_path, capsys):
    path, _ = reference_xlsx
    assert main([str(path), "--json"]) == 0          # 全覆盖 → 0
    out = capsys.readouterr().out
    assert json.loads(out)["passed"] is True

    # 含未映射列 → 覆盖率不足 → 退出码 1
    import openpyxl
    wb = openpyxl.Workbook()
    wb.active.append(["TagNumber", "Area", "某个 HTRI 专有列"])
    small = tmp_path / "small.xlsx"
    wb.save(small)
    assert main([str(small)]) == 1


def test_target_is_95_percent():
    """SPEC/计划的验收目标是 ≥95%，写死在工具里而不是散在文档。"""
    assert TARGET_COVERAGE == 0.95
