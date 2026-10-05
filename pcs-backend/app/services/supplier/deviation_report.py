"""偏差报告组装 + 确认门禁 + 导出 (P7 Sprint 4 S4-2 / SPEC V1.4 §3.2.4).

- `build_report`: 把 `actual_data_json` 逐项按 `deviation_service` 判定, 组装报告
- `can_confirm`: 确认门禁 —— 存在**不合格或不可判**项一律拒绝 (SPEC §3.2.4(4))
- `export_excel` / `export_pdf`: SPEC §3.2.4(3)「可导出PDF/Excel」

⚠️ **已知缺口** (2026-10-05 用户裁决「设计值留空」): `design_parameters_json`
无写入方，生产路径上所有行都会落到「缺设计值（不可判）」，因而 `can_confirm` 恒
False。引擎本身已按 SPEC 逐条实现并由单测覆盖；设计值来源是另一个决定。
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from app.services.supplier.deviation_service import (
    UNQUALIFIED,
    UNVERDICTABLE,
    find_rule,
    evaluate,
    verdict_color,
    verdict_label,
)


@dataclass(frozen=True)
class DeviationRow:
    parameter: str
    design_value: object
    actual_value: object
    unit: str
    deviation_pct: float | None
    verdict: str
    note: str
    spec_ref: str
    requires_recheck: bool = False
    requires_manual_check: bool = False

    @property
    def label(self) -> str:
        return verdict_label(self.verdict)

    @property
    def color(self) -> str:
        return verdict_color(self.verdict)


@dataclass(frozen=True)
class DeviationReport:
    equipment_id: str
    tag_number: str
    actual_data_status: str
    rows: tuple[DeviationRow, ...]
    blocking_reason: str = ""

    @property
    def can_confirm(self) -> bool:
        return can_confirm(self)


def _extract(container: dict | None, name: str) -> tuple[object, str, bool]:
    """从 `{name: {value, unit}}` 容器取一项 → (value, unit, 是否存在)."""
    if not container:
        return None, "", False
    entry = container.get(name)
    if entry is None:
        return None, "", False
    if isinstance(entry, dict):
        return entry.get("value"), (entry.get("unit") or ""), True
    return entry, "", True


def build_report(equipment) -> DeviationReport:
    """逐项比对并组装报告。

    行集合 = 实际值里已录入的参数 —— 没录入的项无法比对，不占行（但
    `can_confirm` 因空报告恒 False，见下）。
    """
    actual = equipment.actual_data_json or {}
    design = equipment.design_parameters_json
    rows: list[DeviationRow] = []

    for name in actual:
        actual_value, unit, _ = _extract(actual, name)
        design_value, _, _ = _extract(design, name)
        rule = find_rule(name)

        if rule is None:
            rows.append(
                DeviationRow(
                    parameter=name, design_value=design_value,
                    actual_value=actual_value, unit=unit, deviation_pct=None,
                    verdict=UNVERDICTABLE, note="无判定规则（SPEC §3.2.4(2) 以泵为例）",
                    spec_ref="",
                )
            )
            continue

        if design_value is None:
            rows.append(
                DeviationRow(
                    parameter=name, design_value=None, actual_value=actual_value,
                    unit=unit, deviation_pct=None, verdict=UNVERDICTABLE,
                    note="缺设计值，无法判定", spec_ref=rule.spec_ref,
                )
            )
            continue

        result = evaluate(rule, design=design_value, actual=actual_value)
        rows.append(
            DeviationRow(
                parameter=name, design_value=design_value, actual_value=actual_value,
                unit=unit, deviation_pct=result.deviation_pct, verdict=result.verdict,
                note=result.note, spec_ref=rule.spec_ref,
                requires_recheck=result.requires_recheck,
                requires_manual_check=result.requires_manual_check,
            )
        )

    report = DeviationReport(
        equipment_id=str(equipment.equipment_id),
        tag_number=equipment.tag_number,
        actual_data_status=equipment.actual_data_status,
        rows=tuple(rows),
    )
    return DeviationReport(
        equipment_id=report.equipment_id,
        tag_number=report.tag_number,
        actual_data_status=report.actual_data_status,
        rows=report.rows,
        blocking_reason=_blocking_reason(report.rows),
    )


def _blocking_reason(rows: tuple[DeviationRow, ...]) -> str:
    bad = [r for r in rows if r.verdict == UNQUALIFIED]
    unknown = [r for r in rows if r.verdict == UNVERDICTABLE]
    if not rows:
        return "未录入实际数据"
    parts = []
    if bad:
        parts.append(f"不合格 {len(bad)} 项: {'、'.join(r.parameter for r in bad)}")
    if unknown:
        parts.append(f"不可判 {len(unknown)} 项: {'、'.join(r.parameter for r in unknown)}")
    return "；".join(parts)


def can_confirm(report: DeviationReport) -> bool:
    """确认门禁 (SPEC §3.2.4(4) + 风险 #4)。

    全部合格或仅警告 → 可确认。存在**不合格或不可判** → 拒绝。
    「不可判」也拦 —— 把判不了的当合格会让这道门禁形同虚设。
    """
    if not report.rows:
        return False
    return not any(
        r.verdict in (UNQUALIFIED, UNVERDICTABLE) for r in report.rows
    )


# ---------------------------------------------------------------------------
# 导出（SPEC §3.2.4(3)）
# ---------------------------------------------------------------------------

# 结论 → 填充色（openpyxl 用 ARGB hex）
_FILL = {
    "合格": "FFC6EFCE",
    "警告": "FFFFEB9C",
    "不合格": "FFFFC7CE",
    "不可判": "FFD9D9D9",
}
_FONT_COLOR = {
    "合格": "FF006100",
    "警告": "FF9C5700",
    "不合格": "FF9C0006",
    "不可判": "FF3F3F3F",
}

# SPEC §3.2.4(3) 原文列名：对比项、设计值、实际值、偏差、结论。不得改写成
# 「偏差%」—— 工艺室按 SPEC 认列名。
_HEADERS = ("设备位号", "对比项", "设计值", "实际值", "单位", "偏差", "结论", "颜色", "说明", "SPEC 依据")


def _cell(container, row) -> dict:
    from dataclasses import asdict

    return asdict(row)


def export_excel(report: DeviationReport) -> bytes:
    """导出 xlsx（openpyxl 已在依赖内）。结论列按 SPEC 颜色标识。"""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill

    wb = Workbook()
    ws = wb.active
    ws.title = "偏差报告"
    ws.append(list(_HEADERS))

    for row in report.rows:
        ws.append(
            [
                report.tag_number,
                row.parameter,
                row.design_value,
                row.actual_value,
                row.unit,
                None if row.deviation_pct is None else round(row.deviation_pct, 4),
                row.label,
                row.color,
                row.note,
                row.spec_ref,
            ]
        )
        r = ws.max_row
        ws.cell(row=r, column=7).fill = PatternFill(
            "solid", start_color=_FILL.get(row.label, "FFD9D9D9")
        )
        ws.cell(row=r, column=7).font = Font(
            color=_FONT_COLOR.get(row.label, "FF3F3F3F"), bold=True
        )
        ws.cell(row=r, column=7).alignment = Alignment(horizontal="center")

    for idx, width in enumerate((14, 16, 12, 12, 8, 10, 10, 8, 34, 46), start=1):
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = width
    ws.freeze_panes = "A2"

    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()


def export_pdf(report: DeviationReport) -> bytes:
    """导出 PDF（reportlab）。中文字体用内置 STSong-Light，不引外部 ttf。"""
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Table, TableStyle

    pdfmetrics.registerFont(UnicodeCIDFont("STSong-Light"))
    _FONT = "STSong-Light"

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "cnTitle", parent=styles["Title"], fontName=_FONT, fontSize=15
    )
    cell_style = ParagraphStyle("cnCell", parent=styles["Normal"], fontName=_FONT, fontSize=8)
    head_style = ParagraphStyle(
        "cnHead", parent=styles["Normal"], fontName=_FONT, fontSize=8,
        textColor=colors.white,
    )

    buf = BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=landscape(A4), title=f"偏差报告 {report.tag_number}"
    )
    story = [
        Paragraph(f"偏差报告 — {report.tag_number}", title_style),
        Paragraph(f"录入状态: {report.actual_data_status}", cell_style),
    ]
    if report.blocking_reason:
        story.append(Paragraph(f"确认门禁: {report.blocking_reason}", cell_style))

    data = [[Paragraph(h, head_style) for h in _HEADERS[:9]]]
    for row in report.rows:
        data.append(
            [
                Paragraph(report.tag_number, cell_style),
                Paragraph(row.parameter, cell_style),
                Paragraph(str(row.design_value), cell_style),
                Paragraph(str(row.actual_value), cell_style),
                Paragraph(row.unit, cell_style),
                Paragraph("—" if row.deviation_pct is None else f"{row.deviation_pct:.3f}%", cell_style),
                Paragraph(row.label, cell_style),
                Paragraph(row.color, cell_style),
                Paragraph(row.note, cell_style),
            ]
        )

    table = Table(data, repeatRows=1)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4A5568")),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#A0AEC0")),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    for i, row in enumerate(report.rows, start=1):
        # _FILL 是 openpyxl 用的 ARGB ('FFC6EFCE')；reportlab 的 HexColor 只吃
        # '#RRGGBB' —— 直接传 ARGB 会炸在 int('FFC6EFCE', 16)。
        argb = _FILL.get(row.label, "FFD9D9D9")
        style.append(("BACKGROUND", (6, i), (7, i), colors.HexColor("#" + argb[2:])))
    table.setStyle(TableStyle(style))
    story.append(table)

    doc.build(story)
    return buf.getvalue()


__all__ = [
    "DeviationReport",
    "DeviationRow",
    "build_report",
    "can_confirm",
    "export_excel",
    "export_pdf",
]
