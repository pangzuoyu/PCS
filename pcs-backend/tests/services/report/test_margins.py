"""**页边距单位契约** —— 三个渲染器共用。

`ReportStyle.margins` 的默认值 top/bottom/left/right = 20/25/20/20 是**毫米**
（教科书级 A4 页边距值）。PDF 渲染器早期把它**当点**传给了 ReportLab，
25pt = 8.8mm —— 边距窄到不成样子，而 PDF 结构合法、字节数正常，
**没有任何结构断言会红**。

DOCX/XLSX 同样读 `style.margins`。若一个当点、一个当毫米，同一份样式在不同
格式下版式完全不同 —— 而三者共用同一个 `blocks.Block`，本该长得一样。
故换算收敛到 `ReportStyle.margins_pt` 一处，由本文件钉死。
"""
import pytest
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm

from app.services.report.style import ReportStyle


def test_margins_are_millimetres_not_points():
    """25 若是点 = 8.8mm，明显不是设计意图。"""
    got = ReportStyle().margins_pt
    assert got["left"] == pytest.approx(25 * mm), \
        f"左边距 {got['left']}pt，应为 {25 * mm}pt（25mm）"
    assert got["left"] / mm == pytest.approx(25)


def test_margins_scale_with_style():
    s = ReportStyle(margins={"top": 30, "bottom": 30, "left": 40, "right": 40})
    assert s.margins_pt == pytest.approx(
        {"top": 30 * mm, "bottom": 30 * mm, "left": 40 * mm, "right": 40 * mm})


def test_content_width_is_a4_minus_margins():
    """A4 210mm − 左 25 − 右 20 = 165mm 正文宽。

    边距误当点时正文宽是 194mm —— 表格撑得更满，看着「挺好」，
    所以这个 bug 靠肉眼也不容易发现，必须用断言钉住。
    """
    got = ReportStyle().margins_pt
    assert A4[0] - got["left"] - got["right"] == pytest.approx((210 - 25 - 20) * mm)