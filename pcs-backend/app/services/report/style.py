"""报表样式配置 —— ADR-P8-001：样式驱动生成，替代 .dotx/.xltx 模板。

**优先级顺序是 默认 → 报表类型 → 项目 → 运行时**（用户 2026-10-08 裁决）。
ADR-P8-001 原文写的「默认 → 项目 → 报表类型 → 运行时」作废：报表类型级是公司
标准（默认值），项目级是更具体的上下文，应当覆盖它。反过来会让「项目级样式」
这一层失去存在意义。
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import get_settings


class Margins(BaseModel):
    """页边距，**单位毫米**。

    ⚠️ 单位是契约，不是实现细节。PDF 渲染器曾把这些值**当点**传给 ReportLab：
    25 当点 = 8.8mm，边距窄到不成样子，而 PDF 结构合法、字节数正常，
    没有一个结构断言会红。DOCX/XLSX 读同一份配置，一个当点一个当毫米的话，
    同一份样式在不同格式下版式完全不同。故换算收敛到
    `ReportStyle.margins_pt`，三个渲染器都用它。
    """

    top: float = 20.0
    bottom: float = 20.0
    left: float = 25.0
    right: float = 20.0


class HeaderFooterConfig(BaseModel):
    left: str = ""
    center: str = ""
    right: str = ""


class TableStyle(BaseModel):
    header_bg: str = "#D9E1F2"
    header_bold: bool = True
    border_width: float = 0.5
    border_color: str = "#000000"
    cell_padding: int = 4
    zebra_stripe: bool = True
    # Review Focus #4：超长单元格截断，不撑破版式
    max_cell_chars: int = 200


class ReportStyle(BaseModel):
    page_size: Literal["A4", "A3", "Letter"] = "A4"
    orientation: Literal["portrait", "landscape"] = "portrait"
    margins: Margins = Margins()
    font_family_cn: str = "Noto Sans CJK SC"
    font_family_en: str = "Arial"
    font_size_body: int = 10
    font_size_heading: int = 14
    line_spacing: float = 1.5
    header: HeaderFooterConfig = HeaderFooterConfig(
        left="{{project_no}}", center="{{report_name}}", right="Rev {{rev}}"
    )
    # ⚠️ 页脚**没有** `{{pages}}`（总页数）。ReportLab 需两遍渲染才能知道总页数，
    # 代价是生成时间 ×2，而总页数在 PDF 阅读器里本就可见。2026-10-08 裁决从
    # SPEC §4.1 移除该占位符。留在这里会被 `_fill_placeholders` 原样保留，
    # 印出一串永远替换不掉的 `{{pages}}`。
    footer: HeaderFooterConfig = HeaderFooterConfig(
        left="{{doc_no}}", center="", right="第 {{page}} 页"
    )
    table: TableStyle = TableStyle()
    assumption_mark: str = "▲"
    assumption_color: str = "#FF8C00"
    qr_position: Literal["footer", "header"] = "footer"
    qr_size_mm: int = 20
    # 字体目录（PDF 渲染器据此定位 TTF）。缺字体抛 REPORT_FONT_MISSING
    # （Review Focus #1）。**不要改成相对路径** —— 字体路径解析相对工作目录，
    # 而工作目录随启动方式变化。
    font_dir: str = Field(default_factory=lambda: get_settings().report_font_dir)

    # 公司强制标准字段：合并时**任何层**都改不了（用户 2026-10-08 裁决的架构
    # 预留位）。P8 先只锁这两项 —— 改了版式 A4/A3 就不再是标准计算书了；
    # 「页脚必含 doc_no」之类的业务强制项待工艺确认后再加。
    locked_fields: frozenset[str] = frozenset({"page_size", "orientation"})

    @property
    def margins_pt(self) -> dict[str, float]:
        """页边距换算成**点**（1pt = 1/72 inch，1mm = 72/25.4 pt）。

        PDF/ReportLab 与 DOCX 都用点或 EMU，但**只有这里知道源单位是毫米** ——
        换算散到各渲染器里各写一遍，就是「一个当点一个当毫米」的来源。
        """
        from reportlab.lib.units import mm

        return {"top": self.margins.top * mm,
                "bottom": self.margins.bottom * mm,
                "left": self.margins.left * mm,
                "right": self.margins.right * mm}


def resolve(*, defaults: ReportStyle, by_type: ReportStyle | None = None,
            project: ReportStyle | None = None,
            runtime: ReportStyle | None = None) -> ReportStyle:
    """四级优先级合并：**默认 → 报表类型 → 项目 → 运行时**。

    三个层都是**可选**的 —— 调用方常常只有一两层，给了默认值比逼着传
    `project=None` 更不容易漏。

    只用**显式设置过**的字段覆盖（exclude_unset）—— 否则上层一个空
    `ReportStyle()` 会把下层全部字段清成默认值（Review Focus #2）。
    pydantic v2 的 `ReportStyle()` 不会把「取了默认值」算作已设置，
    所以 `exclude_unset` 对空层是安全的。

    `defaults.locked_fields` 里的字段任何层都改不了。
    """
    merged = defaults.model_dump()
    for layer in (by_type, project, runtime):
        if layer is None:
            continue
        for k, v in layer.model_dump(exclude_unset=True).items():
            if v is not None and k not in defaults.locked_fields:
                merged[k] = v
    # ⚠️ 上一行是**必需**的，不是重复：locked_fields 本身也是一个可被
    # exclude_unset 命中的**键名**。循环里的 `k not in defaults.locked_fields`
    # 检查的是「值」不是「键名」，拦不住对 locked_fields 自身的覆盖 ——
    # 上层传 locked_fields={"font_size_body"} 就能给自己解锁。合并后必须还原。
    merged["locked_fields"] = defaults.locked_fields
    return ReportStyle.model_validate(merged)
