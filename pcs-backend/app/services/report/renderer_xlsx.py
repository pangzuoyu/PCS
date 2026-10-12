"""XLSX 渲染器 —— XlsxWriter 流式写入。

ADR-P8-001：**不用 openpyxl 做模板填充**，直接流式构建。

## 为什么 `constant_memory=True`

SPEC 性能预算：100 万行约 80MB。XlsxWriter 默认模式把整个工作簿攒在内存里，
行数一多就爆；`constant_memory=True` 改成**按行 flush 到临时文件**，内存恒定。

代价是**必须按行顺序写、不能回头改已写的行**。所以：
- 所有 `write()` 严格从上往下，列可以乱序但行不能回退
- `freeze_panes()` 只能在**写完之后**设一次（设早了会 flush 掉已写数据）

## 页眉页脚

XLSX 的页眉页脚是「打印页眉页脚」，不在单元格网格里。XlsxWriter 用
`&L/&C/&R` 分左右中，`&P` 是页码 —— 页码在这里有原生支持，不需要像
PDF 那样手工塞。`{{page}}` 被换成 `&P`。
"""
from __future__ import annotations

import io

import xlsxwriter

from app.services.report.blocks import (
    Block,
    HeadingBlock,
    KeyValueBlock,
    PageBreakBlock,
    TableBlock,
    _cell_text,
    assumed_header,
    fill_placeholders,
)
from app.services.report.style import ReportStyle

# 表头行是否冻结。测试钉住这个常量：`constant_memory` 下 freeze_panes 的
# 时机很敏感，改动它必须同步改测试。
FREEZE_HEADER_ROW = True


def _hf_to_xlsx(part: str) -> str:
    """把 `{{page}}` 换成 XlsxWriter 的页码码 `&P`。

    其余占位符交给 `fill_placeholders`；未知占位符原样保留。XlsxWriter 把
    `&` 当转义前缀，故占位符里的 `&` 需转义 —— 本项目的占位符都是
    `{{name}}` 形式，不含 `&`，但真填进去的值可能含，故一并处理。
    """
    return fill_placeholders(part, {}).replace("{{page}}", "&P")


def render_xlsx(*, title: str, blocks: list[Block], style: ReportStyle,
                context: dict) -> bytes:
    """渲染 XLSX 并返回字节。

    ⚠️ 返回 bytes 而不是 `constant_memory` 惯用的临时文件路径：报表生成走
    「内容哈希命名落盘」，调用方要的是可写文件的字节。且这里读回来的
    BytesIO 立刻被 zip 打包，内存占用由最终文件大小决定（XLSX 是 zip，
    10000 行约 200KB 量级，远小于 uncompressed 数据）。
    """
    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"constant_memory": True})
    ws = wb.add_worksheet("报表")

    hdr = wb.add_format({"bold": style.table.header_bold,
                         "bg_color": style.table.header_bg, "border": 1,
                         "valign": "top", "text_wrap": True})
    cell = wb.add_format({"border": 1, "valign": "top", "text_wrap": True})
    assumed = wb.add_format({"border": 1, "valign": "top", "text_wrap": True,
                             "font_color": style.assumption_color})
    head = wb.add_format({"bold": True, "font_size": style.font_size_heading,
                          "font_name": style.font_family_en})
    # XLSX 不嵌字体，中文由打开端环境决定（python-docx/xlsxwriter 都做不到）
    mc = style.table.max_cell_chars

    ws.set_header(f"&L{fill_placeholders(style.header.left, context)}"
                  f"&C{fill_placeholders(style.header.center, context)}"
                  f"&R{fill_placeholders(style.header.right, context)}")
    ws.set_footer(f"&L{fill_placeholders(style.footer.left, context)}"
                  f"&C{_hf_to_xlsx(style.footer.center)}"
                  f"&R{_hf_to_xlsx(style.footer.right)}")

    ws.write(0, 0, title, head)
    r = 2
    header_row: int | None = None
    for b in blocks:
        if isinstance(b, HeadingBlock):
            ws.write(r, 0, b.text, head)
            r += 1
        elif isinstance(b, PageBreakBlock):
            r += 1          # XLSX 无分页概念；留空行保持与 PDF/DOCX 的视觉分隔
        elif isinstance(b, KeyValueBlock):
            for k, v in b.rows:
                ws.write(r, 0, str(k), hdr)
                ws.write(r, 1, _cell_text(v, mc), cell)
                r += 1
        elif isinstance(b, TableBlock):
            if header_row is None:
                header_row = r
            for ci, h in enumerate(b.headers):
                ws.write(r, ci, assumed_header(h, ci in b.assumed_cols,
                                               style.assumption_mark), hdr)
            r += 1
            for row in b.rows:
                for ci, v in enumerate(row):
                    fmt = assumed if ci in b.assumed_cols else cell
                    ws.write(r, ci, _cell_text(v, mc), fmt)
                r += 1

    if FREEZE_HEADER_ROW and header_row is not None:
        # ⚠️ 必须在所有 write() 之后：constant_memory 模式下已 flush 的行改不得
        ws.freeze_panes(header_row + 1, 0)

    wb.close()
    return buf.getvalue()