"""PDF 渲染器契约。

⚠️ Block 类一律从 `blocks` import，不从 `renderer_pdf` import —— 后者不 re-export
任何东西，从那儿 import 会直接 ImportError。

**字体策略（用户 2026-10-09 裁决）**：字体**不入库**。运行时按
`REPORT_FONT_DIR` → 系统字体候选链的顺序逐个试，全落空才报 `REPORT_FONT_MISSING`。
因此这些测试**依赖本机装有可用中文字体** —— 若 CI 镜像没装会红。这是刻意的：
宁可红，也不要在没有字体的机器上假绿（bug-150 同族：绿灯测的不是出问题的那层）。
"""
import glob
import io
from pathlib import Path

import pytest
from pypdf import PdfReader

from app.services.exceptions import PcsError
from app.services.report import renderer_pdf
from app.services.report.blocks import (
    HeadingBlock,
    KeyValueBlock,
    PageBreakBlock,
    TableBlock,
    _cell_text,
    assumed_header,
)
from app.services.report.renderer_pdf import render_pdf
from app.services.report.style import ReportStyle

HDR = ["位号", "口径", "描述"]


@pytest.fixture(autouse=True)
def _reset_font_registry():
    """**快照-还原**，不是按名字逐个清。

    两个状态都要清，缺一不可（用户 2026-10-09 审查指出）：
      1. `renderer_pdf._REGISTERED` —— 本模块「已注册」缓存
      2. `pdfmetrics._fonts`        —— reportlab 全局的字体注册表

    只清 ① 的话，第二次 `registerFont` 时 ② 里还留着上一次的字体，
    `getFont(name)` 命中缓存**根本不会重新校验字形** —— 测试绿，生产路径没走。

    也不按名字列表清：任何**新加**的字体族名都会漏出去。快照整个注册表，
    天然覆盖将来新增的名字。
    """
    before = set(renderer_pdf.pdfmetrics._fonts)
    renderer_pdf._REGISTERED.clear()
    yield
    for name in set(renderer_pdf.pdfmetrics._fonts) - before:
        renderer_pdf._unregister_font(name)
    renderer_pdf._REGISTERED.clear()


def test_probe_covers_every_text_class(report_font_path):
    """`_PROBE` 是**契约的一部分** —— 每个字符都代表一类必然出现的文本。

    改动探针等于改动验收标准：一个缺下划线的字形本该被守卫拦下，探针里
    没有 `_` 就会混过去，报表里的编号分隔符静默变空白。
    """
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    pdfmetrics.registerFont(TTFont("probecheck", str(report_font_path)))
    try:
        missing = renderer_pdf._missing_glyphs("probecheck")
    finally:
        renderer_pdf._unregister_font("probecheck")
    assert missing == [], f"派生的字体竟然过不了自己的探针：缺 {missing}"

    # 探针必须真的涵盖这几类 —— 少一类就少一道守卫
    for klass, chars in [("位号", "PDN"), ("数字", "0123456789"),
                         ("单位", "ABCabc"), ("比值/温度", "%°"),
                         ("标点", "-_.()/:")]:
        absent = [c for c in chars if c not in renderer_pdf._PROBE]
        assert not absent, f"探针缺「{klass}」类的字符 {absent}"


def test_font_candidates_are_config_driven():
    """候选链必须**配置驱动** —— 换字体是运维动作，不该改代码。

    硬编码在模块里的话，每次换字体都要发版；而发版漏了某个部署环境，
    报表就静默换了字体甚至失败。
    """
    from app.core.config import get_settings

    chain = get_settings().report_font_candidates
    assert chain, "候选链不能为空"
    assert all(isinstance(p, str) and p for p in chain)
    assert renderer_pdf.DEFAULT_FONT_CANDIDATES == tuple(chain), \
        "模块常量与 settings 默认值不一致 —— 改了一处忘了另一处"


def test_unusable_candidate_logs_warning(tmp_path, monkeypatch, caplog):
    """候选被否要记 WARN —— 否则「为什么这台机器用了次优字体」永远查不出来。

    注意用**存在但不可用**的字体（CFF 轮廓），不是不存在的路径：
    不存在的候选是直接跳过的，不构成「否决」，自然也不该有 WARN。
    """
    import logging

    unusable = _any_cff_font()
    if unusable is None:
        pytest.skip("本机没有 CFF/OTF 字体，无法构造「存在但不可用」的候选")
    bad = tmp_path / "NotoSansCJKsc-Regular.otf"
    bad.write_bytes(unusable.read_bytes())
    _use_chain(monkeypatch, [str(bad), *_good_fallbacks()])

    with caplog.at_level(logging.WARNING, logger=renderer_pdf.__name__):
        out = render_pdf(title="x", blocks=[], style=ReportStyle(),
                         qr_payload=None, assumed_fields=[], font_dir=str(tmp_path))
    assert out[:5] == b"%PDF-"
    msgs = [r.getMessage() for r in caplog.records]
    assert any("被否" in m and str(bad) in m for m in msgs), \
        f"应记录被否掉的候选及原因，实得：{msgs}"


def test_missing_font_error_lists_every_reason(tmp_path, monkeypatch):
    """全链落空时，错误信息要说清**每个候选为什么被否**。

    只报「字体缺失」的话，运维得自己逐个试 —— 而这三个坑（TTC 读不了 /
    可变字体是 Thin / 缺 ASCII）都不显眼，正是查不出来的原因。
    """
    droid = Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf")
    if not droid.exists():
        pytest.skip("本机没有 Droid Sans Fallback")
    only_droid = tmp_path / "NotoSansCJKsc-Regular.otf"
    only_droid.write_bytes(droid.read_bytes())
    _use_chain(monkeypatch, [])

    with pytest.raises(PcsError) as e:
        render_pdf(title="x", blocks=[], style=ReportStyle(),
                   qr_payload=None, assumed_fields=[], font_dir=str(tmp_path))
    msg = str(e.value)
    assert "缺字形" in msg and only_droid.name in msg
    for trap in ("ttc", "Thin", "ASCII"):
        assert trap in msg, f"错误信息应提到「{trap}」这个坑，实得：{msg}"


def test_renders_table_and_returns_pdf_bytes():
    out = render_pdf(title="设备一览表",
                     blocks=[TableBlock(headers=HDR,
                                        rows=[["P-101", "DN50", "工艺水"]],
                                        assumed_cols=(2,))],
                     style=ReportStyle(), qr_payload=None, assumed_fields=[])
    assert out[:5] == b"%PDF-", "必须返回真 PDF 字节"
    assert len(out) > 1000


def test_missing_font_raises_instead_of_emitting_blank_pdf(monkeypatch):
    """Review Focus #1：字体缺失必须显式失败，不产出半成品。

    「font_dir 指向不存在的目录」本身**不足以**触发失败 —— 用户裁决要的是
    系统字体兜底。真正的失败条件是**整条候选链全落空**，所以这里连系统候选
    一起清空，测的才是失败分支本身。
    """
    _use_chain(monkeypatch, [])
    s = ReportStyle(font_dir="/nonexistent/fonts")
    with pytest.raises(PcsError) as e:
        render_pdf(title="x", blocks=[], style=s, qr_payload=None, assumed_fields=[])
    assert e.value.code == "REPORT_FONT_MISSING"


def test_null_cell_renders_dash_not_none_literal():
    """Review Focus #2：NULL 单元格渲染为 —，不写 Python None 字面量。"""
    assert _cell_text(None) == "—"
    assert _cell_text("x") == "x"


def test_long_cell_truncated_with_ellipsis():
    """Review Focus #4：超长文本截断，不撑破版式。"""
    assert _cell_text("x" * 500).endswith("…")
    assert len(_cell_text("x" * 500)) == ReportStyle().table.max_cell_chars


def test_assumed_header_gets_triangle_and_others_dont():
    """SPEC §3.2.1(4)：受影响字段表头带 ▲，其余不带。"""
    assert assumed_header("管径", True) == "管径▲"
    assert assumed_header("管径", False) == "管径"


def test_zero_blocks_still_renders_valid_pdf():
    out = render_pdf(title="空报表", blocks=[], style=ReportStyle(),
                     qr_payload=None, assumed_fields=[])
    assert out[:5] == b"%PDF-"


def test_all_four_block_types_render():
    """Heading(两级) / KeyValue / Table / PageBreak 四种块都要真的走到渲染分支。"""
    out = render_pdf(
        title="全块型",
        blocks=[
            HeadingBlock(text="一、概述", level=1),
            HeadingBlock(text="1.1 小节", level=2),
            KeyValueBlock(rows=[("项目号", "PCS-001"), ("空值", None)]),
            TableBlock(headers=HDR, rows=[["P-101", "DN50", "工艺水"]]),
            PageBreakBlock(),
            TableBlock(headers=["第二页"], rows=[["x"]]),
        ],
        style=ReportStyle(), qr_payload=None, assumed_fields=[])
    assert out[:5] == b"%PDF-"
    assert len(PdfReader(io.BytesIO(out)).pages) == 2


def test_table_spanning_pages_still_renders():
    """跨页表格：200 行必须能出，且页数 > 1（repeatRows 路径）。"""
    rows = [[f"P-{i}", "DN50", "工艺水"] for i in range(200)]
    out = render_pdf(title="跨页", blocks=[TableBlock(headers=["位号", "口径", "介质"], rows=rows)],
                     style=ReportStyle(), qr_payload=None, assumed_fields=[])
    assert out[:5] == b"%PDF-"
    assert len(PdfReader(io.BytesIO(out)).pages) > 1


def test_chinese_text_is_extractable_and_font_embedded():
    """**PDF 的全部价值就是「中文字形真的嵌进去了」。**

    只测 `%PDF-` 头是不够的：字体没嵌上时 PDF 结构仍然合法、字节数仍 >1000，
    测试照样绿，用户拿到的是一堆方块。这与 bug-143/145/149/150 同族 ——
    绿灯测的不是出问题的那层。
    """
    out = render_pdf(title="泵数据表", blocks=[TableBlock(
        headers=["位号", "介质"], rows=[["P-101", "天然气"]])],
        style=ReportStyle(), qr_payload=None, assumed_fields=[])
    reader = PdfReader(io.BytesIO(out))
    assert "天然气" in reader.pages[0].extract_text(), "中文抽不出来 = 字形没嵌对"

    # 嵌入检查走 pypdf 读 /FontDescriptor，而不是外部 pdffonts 二进制 ——
    # 测试不该依赖 poppler 装没装在跑测试的机器上。
    embedded = _embedded_font_names(reader.pages[0])
    assert embedded, "PDF 里一个字体资源都没有"
    assert any("/FontFile2" in n or "CIDFont" in n for n in embedded), \
        f"没有任何字体真正嵌入：{embedded}"


def test_font_falls_back_when_first_candidate_is_unusable(tmp_path, monkeypatch):
    """候选链要**逐个试**，不能只看文件存在。

    本机的 `NotoSansCJK-Regular.ttc` 存在，但它是 CFF/PostScript 轮廓，
    reportlab 直接抛 `TTFError: postscript outlines are not supported`。
    天真的实现会在这里炸掉，永远走不到兜底字体。**存在 ≠ 可用。**
    """
    unusable = _any_cff_font()
    if unusable is None:
        pytest.skip("本机没有 CFF/OTF 字体，无法构造「存在但不可用」的候选")
    bad = tmp_path / "NotoSansCJKsc-Regular.otf"
    bad.write_bytes(unusable.read_bytes())

    _use_chain(monkeypatch, [str(bad), *_good_fallbacks()])
    out = render_pdf(title="兜底", blocks=[TableBlock(headers=["位号"], rows=[["P-1"]])],
                     style=ReportStyle(), qr_payload=None, assumed_fields=[])
    assert out[:5] == b"%PDF-"
    assert "P-1" in PdfReader(io.BytesIO(out)).pages[0].extract_text()


def test_font_missing_latin_glyphs_is_rejected(tmp_path, monkeypatch):
    """注册成功 ≠ 能用。Droid Sans Fallback 零 ASCII 字形，数字会全空白。

    它在 `_SYSTEM_FALLBACK_FILES` 里排最后一位**且永远选不到** —— 本测试钉住
    这件事。删掉覆盖校验，报表里每个 P-101 / DN50 都会变成空白，而 PDF 结构
    合法、字节数正常、没有任何自动化会报警。
    """
    droid = Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf")
    if not droid.exists():
        pytest.skip("本机没有 Droid Sans Fallback，无法构造「缺拉丁字形」的候选")
    only_droid = tmp_path / "NotoSansCJKsc-Regular.otf"
    only_droid.write_bytes(droid.read_bytes())
    # 只留这个候选：系统兜底会把它救回来（那正是用户要的行为），
    # 这里要测的是「**整条链**都不可用」时会不会显式失败。
    _use_chain(monkeypatch, [])

    with pytest.raises(PcsError) as e:
        render_pdf(title="x", blocks=[], style=ReportStyle(),
                   qr_payload=None, assumed_fields=[],
                   font_dir=str(tmp_path))
    assert e.value.code == "REPORT_FONT_MISSING"
    assert "缺字形" in str(e.value), f"错误信息应说明是缺字形而非缺文件：{e.value}"
    assert only_droid.name in str(e.value)


def test_droid_fallback_is_never_actually_selected(monkeypatch):
    """兜底链里 Droid 排在最后**且永远选不到** —— 覆盖校验会挡下它。

    与上一个测试互补：那个测「只有 Droid 时会失败」，这个测「有别的候选时
    绝不会误选 Droid」。两者合起来才钉住「Droid 出现在候选链里是安全的」。
    """
    droid = Path("/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf")
    if not droid.exists():
        pytest.skip("本机没有 Droid Sans Fallback")
    _use_chain(monkeypatch, [str(droid), *_good_fallbacks()])
    out = render_pdf(title="P-101", blocks=[TableBlock(headers=["位号"], rows=[["P-101"]])],
                     style=ReportStyle(), qr_payload=None, assumed_fields=[])
    text = PdfReader(io.BytesIO(out)).pages[0].extract_text()
    assert "P-101" in text, "选中了缺拉丁字形的 Droid"


def test_latin_and_digits_survive_rendering():
    """**回归钉子**：报表里必有位号 / 口径 / 数值。

    这条测试的由来：最初的字体探针用的是纯中文文本，于是「Droid 缺全部 ASCII」
    这个事实被漏掉了。探针必须混着拉丁字符和数字。
    """
    out = render_pdf(
        title="P-101 口径 DN50",
        blocks=[TableBlock(headers=["位号", "口径", "温度"],
                           rows=[["P-101", "DN50", 25.5]])],
        style=ReportStyle(), qr_payload=None, assumed_fields=[])
    text = PdfReader(io.BytesIO(out)).pages[0].extract_text()
    for token in ("P-101", "DN50", "25.5"):
        assert token in text, f"{token} 抽不出来 —— 字体缺拉丁字形？实得：{text!r}"


def test_explicit_font_dir_wins_over_system_fallback():
    """REPORT_FONT_DIR 显式指定的字体优先于系统兜底 —— 否则运维配置形同虚设。"""
    style = ReportStyle()
    resolved = renderer_pdf.resolve_font_path(style)
    assert resolved.exists(), "默认配置下必须解析到一个真实存在的字体"
    if Path(style.font_dir).is_dir():
        assert Path(resolved).parent == Path(style.font_dir), \
            f"{style.font_dir} 下有字体时必须优先用它，实际选了 {resolved}"


def test_unknown_placeholder_kept_visible():
    """占位符拼错要**看得见** —— 静默替换成空串会让页脚少一段却没人发现。"""
    assert renderer_pdf._fill_placeholders("{{doc_no}}", {"doc_no": "D-1"}) == "D-1"
    assert renderer_pdf._fill_placeholders("{{typo}}", {}) == "{{typo}}"


def test_footer_page_number_is_rendered():
    """页脚必须真的有页码。

    曾经的实现把 `page` 放进了 `_KNOWN_PLACEHOLDERS`，`_fill_placeholders` 于是
    用 `ctx.get("page", "")` 把它替换成空串；紧接着 `_decorate` 再去找
    `{{page}}` 时已经找不到了 —— 页脚永远显示「第 页」。
    **PDF 仍然完全合法，字节数正常，没有任何结构检查会报警**；
    是把 PDF 转成图片肉眼看出来的（bug-150 同族的第 8 次）。
    """
    out = render_pdf(
        title="分页", style=ReportStyle(), qr_payload=None, assumed_fields=[],
        blocks=[PageBreakBlock(), TableBlock(headers=["x"], rows=[["y"]])])
    reader = PdfReader(io.BytesIO(out))
    p1 = reader.pages[0].extract_text()
    p2 = reader.pages[1].extract_text()
    assert "第 1 页" in p1, f"第 1 页页脚缺页码：{p1!r}"
    assert "第 2 页" in p2, f"第 2 页页脚缺页码：{p2!r}"


def test_qr_payload_actually_drawn():
    """给了 payload 就必须画 —— 二维码是现场校验的入口，漏画等于功能缺失。"""
    kwargs = dict(title="带码", blocks=[], style=ReportStyle(), assumed_fields=[])
    with_qr = render_pdf(qr_payload="https://pcs.example/verify?x=1", **kwargs)
    without = render_pdf(qr_payload=None, **kwargs)
    assert with_qr[:5] == b"%PDF-"
    assert len(with_qr) > len(without), "带二维码的 PDF 必须比不带的大"


# --- 测试辅助 ---------------------------------------------------------------


def _embedded_font_names(page) -> list[str]:
    """返回该页字体资源里**真正带嵌入字体文件**的名字。"""
    names = []
    for ref in page["/Resources"]["/Font"].values():
        f = ref.get_object()
        desc = f.get("/FontDescriptor")
        if desc is None and "/DescendantFonts" in f:
            desc = f["/DescendantFonts"][0].get_object().get("/FontDescriptor")
        if desc is not None:
            desc = desc.get_object()
            names.append(f"{f.get('/BaseFont')}{'/FontFile2' if '/FontFile2' in desc else ''}")
    return names


def _use_chain(monkeypatch, paths: list[str]) -> None:
    """把字体候选链换成给定列表（走 settings，与生产同一条路）。"""
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "report_font_candidates", paths)


def _good_fallbacks() -> tuple[str, ...]:
    """候选链里真正能用的兜底（OFL 静态派生件）。"""
    return tuple(p for p in renderer_pdf.DEFAULT_FONT_CANDIDATES if "droid" not in p)


def _any_cff_font() -> Path | None:
    """找本机任一 reportlab 读不了的 CFF 字体，用来构造「存在但不可用」。"""
    for pat in ("/usr/share/fonts/**/*.otf", "/usr/share/fonts/**/*.ttc"):
        for p in sorted(glob.glob(pat, recursive=True)):
            if Path(p).stat().st_size > 0:
                return Path(p)
    return None