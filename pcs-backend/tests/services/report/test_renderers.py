"""DOCX / XLSX 渲染器契约。

三套渲染器共用 `blocks.Block`，故本文件除各自的格式断言外，还测**跨渲染器
一致性** —— 共用的不只是数据形状，还有它们对同一份配置与同一段文本的读法
（bug-153：PDF 把毫米当点、DOCX 当毫米，两边版式对不上，就是这么暴露的）。

**不嵌字体**：DOCX/XLSX 不嵌入字体文件，中文由打开文档的环境决定。
python-docx 也做不到嵌入。文档里说明「打开需要中文字体环境」即可，
不要试图塞字体 —— 文件体积会爆炸（一个字库 10MB 起步），且毫无作用。
"""
from __future__ import annotations

import io
import zipfile

import pytest
from docx import Document
from openpyxl import load_workbook

from app.services.report.blocks import (
    HeadingBlock,
    KeyValueBlock,
    PageBreakBlock,
    TableBlock,
    _cell_text,
)
from app.services.report.renderer_docx import render_docx
from app.services.report.renderer_xlsx import render_xlsx
from app.services.report.style import ReportStyle

CTX = {"project_no": "PCS-2026-001", "doc_no": "D-001", "rev": "A",
       "report_name": "设备一览表"}

B = [TableBlock(headers=["位号", "口径"], rows=[["P-101", "DN50"], ["P-102", "DN80"]])]


# --- 结构 -------------------------------------------------------------------


def test_docx_is_valid_zip_with_document_xml():
    b = render_docx(title="设备一览表", blocks=B, style=ReportStyle(), context=CTX)
    assert zipfile.ZipFile(io.BytesIO(b)).namelist().__contains__("word/document.xml")


def test_xlsx_is_valid_zip_with_sheet_xml():
    b = render_xlsx(title="设备一览表", blocks=B, style=ReportStyle(), context=CTX)
    # OOXML 是 worksheets/ 子目录，不是 sheets/
    assert "xl/worksheets/sheet1.xml" in zipfile.ZipFile(io.BytesIO(b)).namelist()


def test_xlsx_10000_rows_does_not_explode():
    """10000 行必须能出（SPEC ≤10s / <100MB），验证 constant_memory 路径不炸。

    ⚠️ `constant_memory=True` 与 `in_memory=True` 语义冲突：前者按行流式落临时
    文件、**不能回头改已写的行**，后者把整个工作簿留在内存。故这里只开
    constant_memory，返回值是临时文件路径而非 bytes —— 渲染器需要处理这个差异。
    """
    rows = [[f"P-{i}", "DN50"] for i in range(10000)]
    b = render_xlsx(title="大表", blocks=[TableBlock(headers=["位号", "口径"], rows=rows)],
                    style=ReportStyle(), context=CTX)
    assert len(b) > 100_000
    wb = load_workbook(io.BytesIO(b), read_only=True)
    assert wb["报表"].max_row == 10000 + 3   # 标题 + 空行 + 表头 + 10000 行


def test_freeze_panes_survives_constant_memory():
    """`constant_memory` 下 `freeze_panes` 必须在写完后调，且只能设一次。

    brief 里在每个 TableBlock 末尾都调一次 —— 多表时最后一个生效，且
    在流式模式下回头改 sheet 属性可能覆盖已 flush 的行。
    """
    import xlsxwriter

    from app.services.report import renderer_xlsx

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"constant_memory": True})
    ws = wb.add_worksheet("t")
    ws.write(0, 0, "h")
    for r in range(1, 100):
        ws.write(r, 0, r)
    ws.freeze_panes(1, 0)          # 写完后设置
    wb.close()
    wb2 = load_workbook(io.BytesIO(buf.getvalue()))
    assert wb2["t"].freeze_panes == "A2"
    assert renderer_xlsx.FREEZE_HEADER_ROW is True


def test_freeze_panes_in_rendered_output():
    """渲染器自己的产物要真的带冻结窗格 —— 上一条测试只证了 xlsxwriter 支持，
    没证 renderer_xlsx 用对了。行布局：1=标题 2=空行 3=表头 → 冻结 A4。"""
    b = render_xlsx(title="t", blocks=B, style=ReportStyle(), context=CTX)
    ws = load_workbook(io.BytesIO(b))["报表"]
    assert ws.freeze_panes == "A4", f"表头行未冻结：{ws.freeze_panes}"


# --- 你要求的四类测试（用户 2026-10-09）------------------------------------


@pytest.mark.parametrize("render", [render_docx, render_xlsx],
                         ids=["docx", "xlsx"])
def test_placeholder_substitution(render):
    """① 页眉页脚占位符替换，且**未知占位符原样保留**（拼错要看得见）。"""
    b = render(title="设备一览表", blocks=[], style=ReportStyle(),
               context=CTX)
    text = _all_text(render, b)
    assert "PCS-2026-001" in text, "页眉的 {{project_no}} 没替换"
    assert "D-001" in text, "页脚的 {{doc_no}} 没替换"
    assert "{{" not in text.replace("{{typo}}", ""), \
        f"已知占位符应全部替换，实得：{text!r}"


@pytest.mark.parametrize("render", [render_docx, render_xlsx],
                         ids=["docx", "xlsx"])
def test_unknown_placeholder_stays_visible(render):
    """①的另一半：未知占位符**保留**，不静默变空串。"""
    style = ReportStyle()
    style = style.model_copy(update={"footer": type(style.footer)(
        left="{{typo}}", center="", right="")})
    b = render(title="t", blocks=[], style=style, context=CTX)
    assert "{{typo}}" in _all_text(render, b)


@pytest.mark.parametrize("render", [render_docx, render_xlsx],
                         ids=["docx", "xlsx"])
def test_long_cell_truncated(render):
    """② 超长截断，不撑破版式。"""
    style = ReportStyle()
    mc = style.table.max_cell_chars
    long_v = "x" * (mc + 50)
    blk = [TableBlock(headers=["位号"], rows=[[long_v]])]
    b = render(title="t", blocks=blk, style=style, context=CTX)
    text = _all_text(render, b)
    assert long_v not in text, "超长文本未截断"
    assert "…" in text, "截断应留省略号"
    assert _cell_text(long_v, mc) in text


@pytest.mark.parametrize("render", [render_docx, render_xlsx],
                         ids=["docx", "xlsx"])
def test_null_cell_becomes_dash(render):
    """③ NULL → —，不写 Python None 字面量。"""
    blk = [KeyValueBlock(rows=[("空值", None)]),
           TableBlock(headers=["位号"], rows=[[None]])]
    b = render(title="t", blocks=blk, style=ReportStyle(), context=CTX)
    text = _all_text(render, b)
    assert "None" not in text, f"None 字面量泄漏到报表里：{text!r}"
    assert "—" in text


@pytest.mark.parametrize("render", [render_docx, render_xlsx],
                         ids=["docx", "xlsx"])
def test_assumed_column_marked(render):
    """④ 假设字段：表头带 ▲ 且单元格染成 assumption_color。"""
    style = ReportStyle()
    blk = [TableBlock(headers=["位号", "设计温度"], rows=[["P-101", 25.5]],
                      assumed_cols=(1,))]
    b = render(title="t", blocks=blk, style=style, context=CTX)

    if render is render_docx:
        doc = Document(io.BytesIO(b))
        headers = [c.text for c in doc.tables[0].rows[0].cells]
        assert headers == ["位号", f"设计温度{style.assumption_mark}"]
        cell = doc.tables[0].rows[1].cells[1]
        rgb = cell.paragraphs[0].runs[0].font.color.rgb
        assert str(rgb).upper() == style.assumption_color.lstrip("#").upper()
    else:
        wb = load_workbook(io.BytesIO(b))
        ws = wb["报表"]
        # 行布局：1=标题, 2=空行, 3=表头, 4=首行数据
        assert ws["B3"].value == f"设计温度{style.assumption_mark}"
        # openpyxl 返回 ARGB（前置 FF 是不透明度），只比后 6 位 RGB
        rgb = ws.cell(row=4, column=2).font.color.rgb.upper()
        assert rgb[-6:] == style.assumption_color.lstrip("#").upper()


@pytest.mark.parametrize("render", [render_docx, render_xlsx],
                         ids=["docx", "xlsx"])
def test_no_font_embedded(render):
    """DOCX/XLSX **不嵌字体** —— 中文由打开端的环境决定。

    python-docx / xlsxwriter 都做不到嵌字体，也不该尝试：一个中文字库
    10MB 起步，塞进去只会让文件爆炸，而打开端该装什么字体还是得装。
    """
    b = render(title="设备一览表", blocks=B, style=ReportStyle(), context=CTX)
    names = zipfile.ZipFile(io.BytesIO(b)).namelist()
    assert not [n for n in names if n.lower().endswith((".ttf", ".otf", ".ttc"))]


@pytest.mark.parametrize("render", [render_docx, render_xlsx],
                         ids=["docx", "xlsx"])
def test_all_four_block_types_render(render):
    b = render(title="全块型", style=ReportStyle(), context=CTX, blocks=[
        HeadingBlock(text="一、概述", level=1),
        HeadingBlock(text="1.1 小节", level=2),
        KeyValueBlock(rows=[("项目号", "PCS-001"), ("空值", None)]),
        TableBlock(headers=["位号", "口径"], rows=[["P-101", "DN50"]]),
        PageBreakBlock(),
        TableBlock(headers=["第二页"], rows=[["x"]]),
    ])
    assert len(b) > 5000


def test_docx_landscape_swaps_page_dimensions():
    """landscape 必须真的交换宽高 —— 只设 orientation 属性 Word 不会重排。"""
    portrait = Document(io.BytesIO(render_docx(
        title="t", blocks=[], style=ReportStyle(), context=CTX)))
    landscape = Document(io.BytesIO(render_docx(
        title="t", blocks=[], style=ReportStyle(orientation="landscape"),
        context=CTX)))
    assert landscape.sections[0].page_width > landscape.sections[0].page_height
    assert portrait.sections[0].page_height > portrait.sections[0].page_width


# --- 辅助 -------------------------------------------------------------------


def _all_text(render, blob: bytes) -> str:
    """把渲染结果摊平成一个字符串，便于跨格式做同样的断言。"""
    if render is render_docx:
        doc = Document(io.BytesIO(blob))
        parts = [p.text for p in doc.paragraphs]
        for sec in doc.sections:
            parts += [p.text for p in sec.header.paragraphs]
            parts += [p.text for p in sec.footer.paragraphs]
        for t in doc.tables:
            for row in t.rows:
                parts += [c.text for c in row.cells]
        return "\n".join(parts)

    from openpyxl import load_workbook

    wb = load_workbook(io.BytesIO(blob))
    ws = wb["报表"]
    parts = [str(c.value) for row in ws.iter_rows() for c in row if c.value is not None]
    # XLSX 页眉页脚是「打印页眉」，不在单元格网格里，要单独取
    parts.append(ws.oddHeader.left.text or "")
    parts.append(ws.oddFooter.left.text or "")
    return "\n".join(parts)