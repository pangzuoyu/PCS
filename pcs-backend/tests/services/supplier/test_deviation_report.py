"""偏差报告组装 + 确认门禁 + 导出 (P7 Sprint 4 Task S4-2).

SPEC §3.2.4(3) 报告含「对比项、设计值、实际值、偏差、结论」，可导出 PDF/Excel。
SPEC §3.2.4(4) + 风险 #4：**存在不合格项 → 禁止标记「已确认」**。

本测试直接构造 design_parameters_json 以验证引擎本身 —— 真实写入方是
`pump_design_data.PUMP_DESIGN`（17 个位号），残余缺口是 tag 集外的设备
仍全行不可判（见 deviation_report 模块 docstring）。
"""

from __future__ import annotations

import pytest

from app.services.supplier.deviation_report import (
    build_report,
    can_confirm,
    export_excel,
    export_pdf,
)

DESIGN = {"扬程": {"value": 32.0, "unit": "m"}, "轴功率": {"value": 55.0, "unit": "kW"}}
ACTUAL_ALL_OK = {"扬程": {"value": 33.0, "unit": "m"}, "电机额定功率": {"value": 75.0, "unit": "kW"}}
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


def test_can_confirm_when_all_qualified():
    r = build_report(_Eq(DESIGN, ACTUAL_ALL_OK))
    assert can_confirm(r) is True


def test_can_confirm_when_report_really_has_a_warning_row():
    """#21: WARNING **不阻断**确认 —— 但这条断言此前从未真正被执行过。

    原用例名 `test_can_confirm_when_all_qualified_or_warning` 名不副实：它的
    fixture 实测只产出两条 QUALIFIED、**零 WARNING 行**。于是一条把
    `can_confirm` 收紧成连 WARNING 一起拦的改动可以让全套用例全绿。
    `RECHECK_ALWAYS` 规则下转速/叶轮直径只要录入就恒 WARNING，所以「WARNING
    存在时 can_confirm 仍为 True」是必须被锁住的行为。

    先 assert 报告里确有 WARNING 行，防止该用例再次退化成全 QUALIFIED 而测试
    仍绿 —— 这正是原用例的失效方式。
    """
    design = {**DESIGN, "转速": {"value": 2950.0, "unit": "r/min"}}
    actual = {**ACTUAL_ALL_OK, "转速": {"value": 3000.0, "unit": "r/min"}}
    r = build_report(_Eq(design, actual))

    warnings = [row for row in r.rows if row.verdict == "WARNING"]
    assert warnings, "fixture 没产出 WARNING 行 —— 本用例退化成全 QUALIFIED 了"
    assert not r.blocking_reason, "WARNING 不应产生阻断原因"
    assert can_confirm(r) is True, "WARNING 不阻断确认（SPEC §3.2.4(4)）"


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


# ---------------------------------------------------------------------------
# 导出注入（审查 #6 / #7）—— 写入角色与读取收件人不同，是跨角色的投递链
# ---------------------------------------------------------------------------

_FORMULA_PAYLOAD = "=cmd|'/c calc'!A0"
_MARKUP_PAYLOAD = '<img src="/etc/hostname" width="10"/>'


def _eq_with(payload: str, field: str) -> "_Eq":
    """把 payload 塞进指定的设计人可控字段。"""
    eq = _Eq(DESIGN, {"扬程": {"value": 33.0, "unit": "m"}})
    if field == "parameter":
        eq.actual_data_json = {payload: {"value": 1.0, "unit": "m"}}
    elif field == "tag_number":
        eq.tag_number = payload
    elif field == "unit":
        eq.actual_data_json = {"扬程": {"value": 33.0, "unit": payload}}
    else:  # pragma: no cover - 参数写错才会到
        raise AssertionError(field)
    return eq


@pytest.mark.parametrize("field", ["parameter", "tag_number", "unit"])
def test_export_excel_neutralizes_formula_injection(field):
    """#6 A03/CWE-1236：设计人可控的字符串不得落进活公式单元格.

    端到端验证：openpyxl 不转义前导 `=`，导出后回读必须是文本单元格
    （`data_type == "s"`）而非公式类型 `"f"` —— 后者意味着 Excel/WPS 打开时
    会执行该表达式。写入角色（DESIGNER/PROCESS_CONTROLLER）与收件人
    （VIEWER 及下游工艺室）不同，是一条**跨角色的存储型投递链**。
    """
    from io import BytesIO

    from openpyxl import load_workbook

    report = build_report(_eq_with(_FORMULA_PAYLOAD, field))
    ws = load_workbook(BytesIO(export_excel(report))).active

    hit = [c for row in ws.iter_rows() for c in row
           if isinstance(c.value, str) and _FORMULA_PAYLOAD in c.value]
    assert hit, "注入串没出现在导出里 —— 测试没测到东西，改法已失效"
    assert all(c.data_type != "f" for c in hit), (
        f"{field} 字段写进了活公式单元格（data_type='f'）"
    )


@pytest.mark.parametrize("field", ["parameter", "tag_number", "unit"])
def test_export_pdf_survives_markup_in_parameter(field):
    """#7 CWE-73：reportlab `Paragraph` 默认解析 mini-HTML markup.

    修复前参数名里的 `<img src="/etc/hostname">` 会让服务端去打开攻击者命名的
    本地路径（`UnidentifiedImageError`）；`ImageReader` 也接受 `http://`，
    同一原语即对内网的 SSRF。现实上限是「不是图片就 500」，但对可达/不可达
    主机返回不同结果仍是一次内网探测。转义后应按字面渲染且不崩。
    """
    report = build_report(_eq_with(_MARKUP_PAYLOAD, field))
    content = export_pdf(report)
    assert content[:5] == b"%PDF-"


def test_export_pdf_escapes_blocking_reason():
    """`blocking_reason` 同样是 `Paragraph` 实参，同样吃 markup —— 别漏。"""
    from app.services.supplier.deviation_report import DeviationReport, can_confirm

    report = build_report(_Eq(DESIGN, ACTUAL_HAS_BAD))
    assert can_confirm(report) is False  # 前置确认：这份报告确实被门禁拦下
    report = DeviationReport(
        equipment_id="eq-1",
        tag_number="P-101A",
        actual_data_status="PENDING_CONFIRM",
        rows=report.rows,
        blocking_reason=_MARKUP_PAYLOAD,
    )
    assert export_pdf(report)[:5] == b"%PDF-"


# ---------------------------------------------------------------------------
# 取值与规则取值（审查 #24 / #29 / #31）
# ---------------------------------------------------------------------------


def test_value_rejects_non_numeric_coercions():
    """#24 A03/CWE-20: Pydantic v2 松散强制下 `'NaN'` → nan、`True` → 1.0。

    服务层 `_coerce_value` 的布尔/字符串拒绝在 API 路径上因此**不可达**；
    更严重的是 NaN 进入 `evaluate` 后所有比较为 false，`ASYMMETRIC_BAND`
    直接落到 `return Evaluation(QUALIFIED, ...)` —— 一个从未被测量的值能过
    SPEC §3.2.4(4) 确认门。schema 须显式 strict。
    """
    from pydantic import ValidationError

    from app.schemas.supplier import ActualDataEntry

    for bad in ("NaN", "Infinity", "-Infinity", True, False, "100"):
        with pytest.raises(ValidationError):
            ActualDataEntry(name="扬程", value=bad)

    assert ActualDataEntry(name="扬程", value=100.0).value == 100.0
    # 负数是合法实测值（冬季设计温度等），strict 不得误伤
    assert ActualDataEntry(name="扬程", value=-12.5).value == -12.5


def test_manual_check_row_keeps_flag_without_design_value():
    """#29: `design_value is None` 短路抢在 kind 派发之前。

    材质按定义没有数值设计值（SPEC §3.2.4(2) 序数比较），短路的结果是一行
    写着「缺设计值，无法判定」——**这句是假的，什么都没缺** —— 且
    `requires_manual_check=False`。丢掉的 flag 才是真伤害：它是下游把该行
    路由给人而非当成录入缺陷的信号。
    """
    r = build_report(_Eq(DESIGN, {"材质": {"value": "304", "unit": ""}}))
    row = next(x for x in r.rows if x.parameter == "材质")
    assert row.requires_manual_check is True
    assert "缺设计值" not in row.note
    assert row.spec_ref, "人工核对行须带 SPEC 回溯"


def test_impeller_diameter_not_paired_with_design_speed():
    """#31: 叶轮直径此前是转速规则的别名且无 design_parameter。

    `design_key`（`design_parameter or parameter`）于是解析为「转速」，
    报告把 2982 r/min 当作 320 mm 直径的设计值 —— 且 `_extract` 对设计列丢弃
    了单位，导出里显示「2982 r/min」作为毫米级实测项的设计值。
    门禁未被污染（RECHECK_ALWAYS 恒 WARNING），但错配值会写进工艺室收到的
    合规文件。拆成独立规则后自然落入「缺设计值」分支被 fail-closed 拦下。
    """
    r = build_report(
        _Eq(
            {"扬程": {"value": 32.0}, "轴功率": {"value": 55.0}, "转速": {"value": 2982.0, "unit": "r/min"}},
            {"叶轮直径": {"value": 320.0, "unit": "mm"}},
        )
    )
    row = next(x for x in r.rows if x.parameter == "叶轮直径")
    assert row.design_value is None, "叶轮直径被配到了转速的设计值上"
    # ⚠️ 报告预言此处会落「缺设计值，无法判定」并被 can_confirm 阻断 —— 那只在
    # 不做 #29 时成立。#29 把 RECHECK_ALWAYS 列入 DESIGN_VALUE_OPTIONAL_KINDS 后，
    # 它走 evaluate() 拿到固定的 WARNING + requires_recheck。
    # 这更贴 SPEC：「允许差异，需重新校核性能」本就是需复核而非不合格，不应阻断。
    assert row.verdict == "WARNING"
    assert row.requires_recheck is True
