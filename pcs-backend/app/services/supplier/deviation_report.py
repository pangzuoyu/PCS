"""偏差报告组装 + 确认门禁 + 导出 (P7 Sprint 4 S4-2 / SPEC V1.4 §3.2.4).

- `build_report`: 把 `actual_data_json` 逐项按 `deviation_service` 判定, 组装报告
- `can_confirm`: 确认门禁 —— 存在**不合格或不可判**项一律拒绝 (SPEC §3.2.4(4))
- `export_excel` / `export_pdf`: SPEC §3.2.4(3)「可导出PDF/Excel」

设计值来源：`app/services/equip_list/pump_design_data.py` 的 `PUMP_DESIGN`
（17 个蜡油加氢泵位号），经 `apply_design_parameters()` /
`scripts/p7_s4_003_seed_pump_design.py` 写入 `design_parameters_json`。

⚠️ **残余缺口**：PUMP_DESIGN 只覆盖那 17 个位号，tag 集之外的设备仍全部落
「缺设计值（不可判）」、`can_confirm` 恒 False。非泵设备的应检参数表与设计值
来源待其数据模型落地时再建（见 #8 的范围限定）。
"""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from app.services.supplier.deviation_service import (
    SPEC_RULES,
    UNQUALIFIED,
    UNVERDICTABLE,
    find_rule,
    evaluate,
    verdict_color,
    verdict_label,
)

# 这些 kind 的判定**不依赖设计值**，故「缺设计值」不该抢在 kind 派发之前
# 短路掉它们（审查 #29）。此前一律短路的后果：
#   - 材质（MANUAL_CHECK）产出一行写着「缺设计值，无法判定」—— 这句是假的，
#     什么都没缺 —— 且 `requires_manual_check=False`，丢掉了下游把该行路由给人
#     而非当成录入缺陷的信号；
#   - 轴功率（REFERENCE_ONLY，本就「不判合格与否」）在设计值未回填的设备上
#     静默降级为 UNVERDICTABLE。
# 若日后希望「转速无设计值时仍阻断」，把 RECHECK_ALWAYS 从此集合去掉即可。
DESIGN_VALUE_OPTIONAL_KINDS = frozenset(
    {"MANUAL_CHECK", "REFERENCE_ONLY", "RECHECK_ALWAYS"}
)


def _required_parameter_names(design: dict | None) -> set[str]:
    """该设备「应检」的参数名集合（审查 #8）.

    推导：SPEC_RULES 中**该设备有对应设计值**的规则，取其 `parameter`（实测侧）。

    两个易错点:
      - 取 `parameter` 而非 `design_key`。`电机额定功率` 规则的 design_key 是「轴功率」
        （设计侧参照量），用 design_key 会放过「电机额定功率」实测值 —— 恰好放过最该
        卡的那一项。
      - 用「设备自身的设计值」求交，而非 import `PUMP_DESIGN`。对泵等价（PUMP_DESIGN
        就是这些设计值的来源），且非泵无设计值 → 空集 → 行集仍等于已录入键集，
        天然不受本轮改动影响，也不在报告层引入对泵选型模块的耦合。
      - **排除 REFERENCE_ONLY**。`轴功率` 是电机裕量规则的设计侧参照量，判定读的是
        `design_parameters_json['轴功率']` 而非实测值 —— 强制录入它既无必要，又因它
        恒产出 UNVERDICTABLE 而让泵永远不可确认。

    为什么需要它：SPEC §3.2.4(2) 的六条允许偏差是**并集**而非「至少一条」。
    修复前行集恰好等于设计人敲进去的键集，`can_confirm` 唯一的空集守卫是「行数为 0」，
    于是只录一个效率（95% 带内）就能确认整台泵 —— 第 4 档 UNVERDICTABLE 防的是
    「进了报告但没判」，对「根本没进报告」无能为力。
    """
    if not design:
        return set()
    return {
        r.parameter
        for r in SPEC_RULES
        if r.design_key in design and r.kind != "REFERENCE_ONLY"
    }


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

    # 设计决策（P7-S4 审查 #8）：应检参数集的 fail-closed **本轮仅对泵生效**。
    # 理由：泵的应检集可从 `PUMP_DESIGN` 的设计键推导（SPEC §3.2.4(2) 六条允许偏差）；
    # 非泵设备无设计值 → 行集为空 → `can_confirm` 恒 False，已是事实上的 fail-closed，
    # 不会误确认。非泵设备的应检参数表机制留到其数据模型落地时再建 —— 那时才谈得上
    # 「哪些参数应检」，在此之前凭空造表反而会拒掉合法录入。
    # 待办（步 3）：#8 落地时泵侧改为「SPEC_RULES 中每条匹配到本设备设计键的规则都补一行，
    # 缺实测值即显式 UNVERDICTABLE」，复用现有 fail-closed 档，不新增门禁逻辑。
    """
    actual = equipment.actual_data_json or {}
    design = equipment.design_parameters_json
    rows: list[DeviationRow] = []

    for name in actual:
        actual_value, unit, _ = _extract(actual, name)
        rule = find_rule(name)
        # 判定依据的设计参数未必与实际参数同名 —— 电机裕量规则看的是「轴功率」。
        # 找不到规则时退回同名查找，好让报错行带上已有的设计值便于排查。
        design_value, _, _ = _extract(
            design, rule.design_key if rule else name
        )

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

        if design_value is None and rule.kind not in DESIGN_VALUE_OPTIONAL_KINDS:
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

    # 补齐未录入的应检参数（审查 #8）。它们必须有行 —— 否则「没录」与「录了且判过」
    # 在报告里长得一模一样，缺值就绕过了确认门禁。
    _existing = {row.parameter for row in rows}
    for key in sorted(_required_parameter_names(design) - _existing):
        rule = find_rule(key)
        d_value, d_unit, _ = _extract(design, key)
        rows.append(
            DeviationRow(
                parameter=key,
                design_value=d_value,
                actual_value=None,
                unit=d_unit,
                deviation_pct=None,
                verdict=UNVERDICTABLE,
                note="应检参数未录入实测值（SPEC §3.2.4(2) 六条允许偏差为并集）",
                spec_ref=rule.spec_ref if rule else "",
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

    ⚠️ **F-P7-S4-01（登记，合并后立即修）**：`UNVERDICTABLE` 被一视同仁地阻断，
    但它有两种来源，语义相反：

    | 类型 | 例子 | 该阻断？ |
    |------|------|---------|
    | 缺值型 | #8 的「应检参数未录入实测值」占位行 | ✅ 该 —— 用户还没补 |
    | 参照型 | `轴功率` 已录入，但它本就不判合格与否 | ❌ 不该 —— 用户已尽责 |

    修法：`can_confirm` 排除 `rule.kind == "REFERENCE_ONLY"` 的 UNVERDICTABLE 行。
    ⚠️ `MANUAL_CHECK`（`requires_manual_check=True`，如材质）的 UNVERDICTABLE
    **是否也该排除，需一并裁决** —— 它同样不是「缺值」，但它代表「机器判不了、
    需人工核对」，阻断与否是产品口径问题，不在本轮 fix pass 范围内。

    实际触发率高：`PUMP_DESIGN` 含 `轴功率` 键，录入方很自然会填它，
    一填就把整台泵的确认门禁堵死。
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


# 公式注入的中和字符集（OWASP CSV/XLS Injection）。openpyxl 不转义前导 `=`，
# 设计人可控的字符串（参数名/单位/位号）会原样落成活公式单元格。
_FORMULA_LEADERS = ("=", "+", "-", "@", "\t", "\r")


def _safe_cell(value: Any) -> Any:
    """写单元格前中和前导公式字符.

    **加前缀而非拒绝** —— 参数名是中文工程术语（「电机额定功率」「轴功率」），
    收紧校验会无收益地打断既有调用方。非字符串（float/None）原样返回。
    """
    if isinstance(value, str) and value.startswith(_FORMULA_LEADERS):
        return "'" + value
    return value


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
                _safe_cell(report.tag_number),
                _safe_cell(row.parameter),
                row.design_value,
                row.actual_value,
                _safe_cell(row.unit),
                None if row.deviation_pct is None else round(row.deviation_pct, 4),
                _safe_cell(row.label),
                _safe_cell(row.color),
                _safe_cell(row.note),
                _safe_cell(row.spec_ref),
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
    from xml.sax.saxutils import escape

    # `Paragraph` 默认把实参当 mini-HTML markup 解析，参数名/单位里的
    # `<img src="...">` 会让服务端去打开攻击者命名的路径（CWE-73 本地文件读取 /
    # SSRF 原语）。所有实参一律 escape，让 markup 按字面渲染。
    # 表头是静态列名，无需处理。
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
        Paragraph(escape(f"偏差报告 — {report.tag_number}"), title_style),
        Paragraph(escape(f"录入状态: {report.actual_data_status}"), cell_style),
    ]
    if report.blocking_reason:
        story.append(
            Paragraph(escape(f"确认门禁: {report.blocking_reason}"), cell_style)
        )

    data = [[Paragraph(h, head_style) for h in _HEADERS[:9]]]
    for row in report.rows:
        data.append(
            [
                Paragraph(escape(report.tag_number), cell_style),
                Paragraph(escape(row.parameter), cell_style),
                Paragraph(escape(str(row.design_value)), cell_style),
                Paragraph(escape(str(row.actual_value)), cell_style),
                Paragraph(escape(row.unit), cell_style),
                Paragraph("—" if row.deviation_pct is None else f"{row.deviation_pct:.3f}%", cell_style),
                Paragraph(escape(row.label), cell_style),
                Paragraph(escape(row.color), cell_style),
                Paragraph(escape(row.note), cell_style),
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
