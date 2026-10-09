"""**像素级**验证：关键模板元素必须真的画在纸上。

用户 2026-10-09 审查定下的元规则：

> 关键模板元素（页脚页码、页眉、二维码、假设声明页）必须通过渲染后目视或
> 像素级验证。文本层断言发现不了布局空白 —— PDF 结构合法、字体嵌入、
> 字节数正常、文本层甚至还有「第」「页」两个字，但**数字没渲染出来**。
> 页脚页码那个 bug 就是这么溜过去的：全部文本断言绿，转成 PNG 一眼看出来了。

## 跑法

- 默认 `-m "not visual"` 跳过（本地跑全量套件时不做 10 秒的位图转换）
- CI 用 `pytest -m visual` 跑 —— 需要 `poppler-utils`（`pdftoppm`）

**绝不 skip 成绿灯**：缺 `pdftoppm` 时 `pytest.fail`，因为「跑不了所以跳过」
正是这套测试要消灭的东西。同 `conftest.report_font_path` 的理由。
"""
from __future__ import annotations

import shutil
import subprocess

import pytest

from app.services.report.blocks import PageBreakBlock, TableBlock
from app.services.report.renderer_pdf import render_pdf
from app.services.report.style import ReportStyle

pytestmark = pytest.mark.visual


@pytest.fixture(scope="module")
def pdftoppm() -> str:
    exe = shutil.which("pdftoppm")
    if not exe:
        pytest.fail(
            "缺 pdftoppm（poppler-utils）。装上：apt install poppler-utils。\n"
            "**不要改成 skip** —— 跳过就等于这些测试不存在，页脚页码那类"
            "「文本层有字、像素上空白」的 bug 会原样溜过去。"
        )
    return exe


@pytest.fixture(scope="module")
def page_pngs(tmp_path_factory, pdftoppm, report_font_path) -> dict[int, bytes]:
    """渲染一份两页报表，把每页转成 1-bit 黑白 PNG。

    返回 {页码: PNG 字节}。**只保留「有没有墨」这一个信息** ——
    目的不是比对公司美术效果，而是回答「这块区域到底画没画东西」。
    """
    out = render_pdf(
        title="视觉验证 P-101",
        blocks=[
            TableBlock(headers=["位号", "口径", "温度"],
                       rows=[["P-101", "DN50", 25.5]]),
            PageBreakBlock(),
            TableBlock(headers=["第二页"], rows=[["x"]]),
        ],
        style=ReportStyle(),
        qr_payload="https://pcs.example/verify?f=abc123",
        assumed_fields=["温度"],
        context={"doc_no": "D-001"},
    )
    pdf = tmp_path_factory.mktemp("visual") / "v.pdf"
    pdf.write_bytes(out)
    subprocess.run(
        [pdftoppm, "-r", "72", "-png", str(pdf), str(pdf.with_suffix(""))],
        check=True, capture_output=True,
    )
    return {i: p.read_bytes() for i, p in enumerate(
        sorted(pdf.parent.glob("v-*.png")), start=1)}


def _ink_ratio(png_bytes: bytes) -> float:
    """墨迹像素占比。>0 说明这块区域**真的画了东西**。"""
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(png_bytes)).convert("L")
    dark = sum(1 for px in img.getdata() if px < 128)
    return dark / (img.width * img.height)


def _crop_bottom_strip(png_bytes: bytes, height_ratio: float = 0.12):
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(png_bytes)).convert("L")
    h = max(1, int(img.height * height_ratio))
    return img.crop((0, img.height - h, img.width, img.height))


def test_both_pages_render(page_pngs):
    assert set(page_pngs) == {1, 2}, f"应产出 2 页，实得 {sorted(page_pngs)}"
    for page, png in page_pngs.items():
        assert _ink_ratio(png) > 0.001, f"第 {page} 页几乎是空白页"


def test_footer_strip_has_ink(page_pngs):
    """页脚区域必须有墨 —— 这是「页码有没有画出来」的**像素级**判据。"""
    for page, png in page_pngs.items():
        strip = _crop_bottom_strip(png)
        dark = sum(1 for px in strip.getdata() if px < 128)
        assert dark > 20, (
            f"第 {page} 页页脚区域几乎没有墨 —— 页码/页眉没画出来？\n"
            f"⚠️ 文本层断言此时仍然是绿的：模板串里的「第」「页」两个字还在，"
            f"只是数字没渲染。别只信 extract_text()。"
        )


def test_page_numbers_differ_between_pages(page_pngs):
    """两页页脚**必须不一样** —— 页码在变。

    判据：第 1 页与第 2 页页脚条带的墨迹**分布**不同。
    若两页页脚像素完全一致，说明页码根本没参与渲染（两页都印了同一个值
    或都没印）。这比「查文本里有几个数字」更难被假绿骗过。
    """
    s1 = _crop_bottom_strip(page_pngs[1])
    s2 = _crop_bottom_strip(page_pngs[2])
    assert list(s1.getdata()) != list(s2.getdata()), \
        "两页页脚像素完全相同 —— 页码没有随页变化"


def test_qr_code_present_on_page(page_pngs):
    """二维码是现场校验的入口 —— 右下角必须有一块**密排黑块**。

    不写死裁剪框：实测二维码占 x 0.80–0.88 / y 0.93–0.98，写死框的话框一挪
    墨迹就被稀释（第一版按 0.75–0.97 / 0.88–0.98 裁，框大了 4 倍，墨迹从
    ~45% 摊到 9.3%，阈值怎么调都别扭）。改成**在右下象限里找最密的一格**：
    二维码是密排模块，必然是全场最密的区域；没画二维码时不存在这样的簇。
    """
    from io import BytesIO

    from PIL import Image

    img = Image.open(BytesIO(page_pngs[1])).convert("L")
    w, h = img.size
    cell = max(8, min(w, h) // 20)
    best = 0.0
    for gy in range(int(h * 0.55), h - cell, cell):
        for gx in range(int(w * 0.55), w - cell, cell):
            box = img.crop((gx, gy, gx + cell, gy + cell))  # 边界由 range 保证不越界
            best = max(best, sum(1 for px in box.getdata() if px < 128) / (cell * cell))
    assert best > 0.30, (
        f"右下象限最密的一格墨迹仅 {best:.1%}，找不到二维码那种密排黑块。"
        f"⚠️ extract_text() 此时仍然是绿的 —— 少画一个码不改变任何文本断言。"
    )