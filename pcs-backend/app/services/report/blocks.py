"""三个渲染器共用的中间表示（Block）。

⚠️ **刻意不放 renderer_pdf.py**（2026-10-08 审查决策）：PDF / XLSX / DOCX 三者
在架构上对等，不该有谁 import 谁。改 PDF 渲染器不应波及 XLSX。

本模块只做**表示层**：把「一段标题 / 一组键值 / 一张表 / 一次分页」描述清楚，
不碰任何渲染技术。各渲染器只负责把 Block 画到自己的画布上。
"""
from __future__ import annotations

from dataclasses import dataclass

# NULL 的显示占位。SPEC 不要求与 NULL 字面量区分，但**必须**与空字符串区分：
# 空字符串是「填了但是空的」，NULL 是「没填」，报告里两者含义不同。
_NULL = "—"


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