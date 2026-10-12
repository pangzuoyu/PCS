"""三个渲染器共用的中间表示（Block）。

⚠️ **刻意不放 renderer_pdf.py**（2026-10-08 审查决策）：PDF / XLSX / DOCX 三者
在架构上对等，不该有谁 import 谁。改 PDF 渲染器不应波及 XLSX。

本模块只做**表示层**：把「一段标题 / 一组键值 / 一张表 / 一次分页」描述清楚，
不碰任何渲染技术。各渲染器只负责把 Block 画到自己的画布上。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# NULL 的显示占位。SPEC 不要求与 NULL 字面量区分，但**必须**与空字符串区分：
# 空字符串是「填了但是空的」，NULL 是「没填」，报告里两者含义不同。
_NULL = "—"

# 页眉页脚可用的占位符。**刻意不含 `page`** —— 它是渲染期才知道的值
# （PDF 的 `doc.page`、DOCX 的 PAGE 域、XLSX 的 `&P`），不是 context 里的值。
# 放进来会被 `fill_placeholders` 用 `ctx.get("page", "")` 吃掉成空串，
# 页脚就永远显示「第 页」—— 那个 bug 找出来过一次，别再犯。
KNOWN_PLACEHOLDERS = {"project_no", "project_name", "doc_no", "rev", "report_name"}
# 2026-10-08 裁决已从 SPEC §4.1 移除 `pages`（ReportLab 两遍渲染代价 ×2）。


@dataclass(frozen=True)
class HeadingBlock:
    text: str
    level: int = 1


@dataclass(frozen=True)
class KeyValueBlock:
    rows: list[tuple[str, object]]


@dataclass(frozen=True)
class TableBlock:
    headers: list[str]
    rows: list[list[object]]
    # 受假设数据影响的列下标。SPEC §3.2.1(4)：这些列的表头要带 ▲、数据要变色。
    assumed_cols: tuple[int, ...] = ()


@dataclass(frozen=True)
class PageBreakBlock:
    pass


Block = HeadingBlock | KeyValueBlock | TableBlock | PageBreakBlock


def _cell_text(value: object, max_chars: int = 200) -> str:
    """NULL → —，超长截断加省略号。三个渲染器共用（DRY）。"""
    if value is None:
        return _NULL
    s = str(value)
    return s if len(s) <= max_chars else s[: max_chars - 1] + "…"


def assumed_header(header: str, assumed: bool, mark: str = "▲") -> str:
    """SPEC §3.2.1(4)：受影响字段在表头带三角。

    三个渲染器的表头语法不同（ReportLab Paragraph / XlsxWriter write /
    python-docx run），但「加三角」这个逻辑只在这里写一次。
    """
    return f"{header}{mark}" if assumed else header


def fill_placeholders(text: str, ctx: dict) -> str:
    """替换页眉页脚占位符。**未知占位符原样保留** —— 拼错时看得见，
    静默替换成空串反而更糟（页脚会少一段文字却没人发现）。

    三个渲染器共用（各写一份就是 bug-153 的温床：同一语义三处实现，
    迟早有一处漏）。
    """
    def repl(m: re.Match) -> str:
        key = m.group(1)
        return str(ctx.get(key, "")) if key in KNOWN_PLACEHOLDERS else m.group(0)
    return re.sub(r"\{\{(\w+)\}\}", repl, text)
