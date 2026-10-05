"""偏差报告组装 + 确认门禁 + 导出 (P7 Sprint 4 Task S4-2).

SPEC §3.2.4(3) 报告含「对比项、设计值、实际值、偏差、结论」，可导出 PDF/Excel。
SPEC §3.2.4(4) + 风险 #4：**存在不合格项 → 禁止标记「已确认」**。

⚠️ 已知缺口 (2026-10-05 用户裁决「设计值留空」): `design_parameters_json`
无写入方，故生产路径上报告恒为「缺设计值（不可判）」。本测试直接构造
design_parameters_json 以验证引擎本身正确 —— 来源问题另记，不在本 Task。
"""

from __future__ import annotations

import pytest

from app.services.supplier.deviation_report import (
    build_report,
    can_confirm,
    export_excel,
    export_pdf,
)

DESIGN = {"扬程": {"value": 32.0, "unit": "m"}, "电机额定功率": {"value": 55.0, "unit": "kW"}}
ACTUAL_ALL_OK = {"扬程": {"value": 33.0, "unit": "m"}, "电机额定功率": {"value": 56.0, "unit": "kW"}}
ACTUAL_HAS_BAD = {"扬程": {"value": 33.0, "unit": "m"}, "电机额定功率": {"value": 48.0, "unit": "kW"}}


class _Eq:
    """最小设备替身 —— 引擎只读这 4 个属性。"""

    def __init__(self, design, actual, status="PENDING_CONFIRM"):
        self.equipment_id = "eq-1"
        self.tag_number = "P-101A"
        self.actual_data_status = status
        self.design_parameters_json = design
        self.actual_data_json = actual


# ---------------------------------------------------------------------------
# 组装
# ---------------------------------------------------------------------------


def test_report_rows_cover_every_actual_parameter():
    r = build_report(_Eq(DESIGN, ACTUAL_ALL_OK))
    assert {row.parameter for row in r.rows} == {"扬程", "电机额定功率"}


def test_report_row_carries_design_actual_deviation_verdict():
    r = build_report(_Eq(DESIGN, ACTUAL_ALL_OK))
    row = next(x for x in r.rows if x.parameter == "扬程")
    assert row.design_value == 32.0
    assert row.actual_value == 33.0
    assert row.deviation_pct == pytest.approx(3.125, abs=1e-3)
    assert row.verdict == "QUALIFIED"
    assert row.color == "绿色"
    assert row.spec_ref  # 报告须能回溯到 SPEC 哪一条


def test_report_equipment_identity():
    r = build_report(_Eq(DESIGN, ACTUAL_ALL_OK))
    assert r.tag_number == "P-101A"
    assert r.actual_data_status == "PENDING_CONFIRM"


def test_unruled_parameter_is_unverdictable():
    """非泵设备参数（SPEC 表「以泵为例」外的）落不到规则 → 不可判，不标合格."""
    r = build_report(_Eq({}, {"容器设计温度": {"value": 55.0, "unit": "℃"}}))
    row = r.rows[0]
    assert row.verdict == "UNVERDICTABLE"
    assert "无判定规则" in row.note


def test_missing_design_value_row_is_unverdictable():
    r = build_report(_Eq(None, ACTUAL_ALL_OK))
    assert all(row.verdict == "UNVERDICTABLE" for row in r.rows)
    assert "缺设计值" in r.rows[0].note


def test_not_entered_actual_data_yields_empty_report():
    r = build_report(_Eq(DESIGN, None))
    assert r.rows == ()
    assert can_confirm(r) is False  # 没录数据不能确认


# ---------------------------------------------------------------------------
# 确认门禁（SPEC §3.2.4(4) + 风险 #4）
# ---------------------------------------------------------------------------


def test_can_confirm_when_all_qualified_or_warning():
    r = build_report(_Eq(DESIGN, ACTUAL_ALL_OK))
    assert can_confirm(r) is True


def test_cannot_confirm_when_any_unqualified():
    """存在不合格项 → 禁止确认。SPEC §3.2.4(4) 的核心风险 #4."""
    r = build_report(_Eq(DESIGN, ACTUAL_HAS_BAD))
    assert can_confirm(r) is False
    assert "不合格" in (r.blocking_reason or "")


def test_cannot_confirm_when_any_unverdictable():
    """不可判也拦确认 —— fail-closed：判不了不等于合格."""
    r = build_report(_Eq(DESIGN, {**ACTUAL_ALL_OK, "容器设计温度": {"value": 55.0, "unit": "℃"}}))
    assert can_confirm(r) is False
    assert "不可判" in (r.blocking_reason or "")


def test_cannot_confirm_when_design_missing():
    r = build_report(_Eq(None, ACTUAL_ALL_OK))
    assert can_confirm(r) is False


# ---------------------------------------------------------------------------
# 导出（SPEC §3.2.4(3)「可导出PDF/Excel」）
# ---------------------------------------------------------------------------


def test_export_excel_returns_xlsx_bytes_with_header():
    content = export_excel(build_report(_Eq(DESIGN, ACTUAL_ALL_OK)))
    assert content[:2] == b"PK"  # zip 容器

    from io import BytesIO

    from openpyxl import load_workbook

    ws = load_workbook(BytesIO(content)).active
    header = [c.value for c in ws[1]]
    # SPEC §3.2.4(3) 规定的 5 列
    for col in ("对比项", "设计值", "实际值", "偏差", "结论"):
        assert col in header
    assert ws.max_row >= 3  # 表头 + 2 参数行


def test_export_excel_colors_the_verdict_cell():
    """不合格红色 —— SPEC §3.2.4(3) 的颜色标识."""
    from io import BytesIO

    from openpyxl import load_workbook

    content = export_excel(build_report(_Eq(DESIGN, ACTUAL_HAS_BAD)))
    ws = load_workbook(BytesIO(content)).active
    header = [c.value for c in ws[1]]
    verdict_col = header.index("结论") + 1
    fills = [
        ws.cell(row=r, column=verdict_col).fill.start_color.rgb
        for r in range(2, ws.max_row + 1)
    ]
    # 至少一格带红底 —— 具体色值随 openpyxl 版本变，只断言"有颜色"
    assert any(f not in (None, "00000000") for f in fills)


def test_export_pdf_returns_pdf_bytes():
    content = export_pdf(build_report(_Eq(DESIGN, ACTUAL_ALL_OK)))
    assert content[:5] == b"%PDF-"


def test_export_pdf_renders_chinese_without_crashing():
    """中文字体走 reportlab 内置 STSong-Light —— 不引外部 ttf。"""
    content = export_pdf(build_report(_Eq(DESIGN, ACTUAL_ALL_OK)))
    assert len(content) > 1000
