"""PDF 渲染器 —— ReportLab Platypus 直接生成。

ADR-P8-001：**不经 LibreOffice 转换**。二维码直接用
`reportlab.graphics.barcode.qr` 绘制，**不做 pypdf 后处理**。

## 中文字体解析（用户 2026-10-09 裁决）

字体**不入库原始文件**，运行时按 `REPORT_FONT_CANDIDATES` 的顺序**逐个试**。
四条例化下来的硬约束，每条都是实测得来的、不是设想的：

1. **存在 ≠ 可用。** 本机的 `NotoSansCJK-Regular.ttc` 存在，但 reportlab 抛
   `TTFError: postscript outlines are not supported`（CFF 轮廓它读不了）。
   所以候选要**逐个注册试**，不能只判 `path.exists()`。
2. **变体字体会静默变形。** `NotoSansSC-VF.ttf` 能注册，但 reportlab 取可变
   字体的默认实例 —— 那个实例的 `wght` 默认值是 **100（Thin）**，整份报表
   变成发丝字。故候选链里**不列**可变字体；要用就先用
   `scripts/build_report_font.py` 派生静态 Regular。
3. **注册成功 ≠ 能用。** `DroidSansFallbackFull.ttf`（Apache-2.0，3.8 MB）
   能注册、能嵌、能抽出全部汉字 —— 但它**一个 ASCII 字形都没有**：
   `P-101` / `DN50` / 所有数字全部渲染为空白。
   ⚠️ 只用**纯中文**文本探针看不出这个问题（我就是这么被骗过去的）。
4. **许可决定能不能默认用。** HP Simplified Hans 字形齐全，但 name 表写着
   「This typeface is the property of Dalton Maag Ltd / Modification requires
   prior written permission」—— **专有许可**，不能默认嵌进对外发出的 PDF。
   故默认走 **OFL** 的 Noto Sans SC（= Source Han Sans，SIL OFL 1.1）。

守卫对**每一个候选**都跑，不是只在链末尾跑一次 —— 链里任何一环都可能塞进
一个坏字体，逐个拦才是契约。全链落空才抛 `REPORT_FONT_MISSING`：
产出方块 / 空白数字的 PDF 比报错难排查得多。

## 字形探针是契约的一部分

`_PROBE` 里的每个字符都代表一类报表里必然出现的文本：
`P`/`D`/`N` 位号前缀、`0`-`9` 数值与日期、`A`-`Z` 单位（DN50 / M3/h / NPSH）、
`%`/`°` 比值与温度、`-`/`_`/`(`/`)`/`/`/`:`/` ` 编号与标点。
**改动 `_PROBE` 等于改动验收标准** —— 例如删掉 `_`，一个缺下划线字形的
字体就会混过守卫，而报表里的行号分隔符会静默变空白。故有测试钉住它。

"""
from __future__ import annotations

import io
import logging
import re
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A3, A4, LETTER
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.core.config import get_settings
from app.services.exceptions import PcsError
from app.services.report.blocks import (
    Block,
    HeadingBlock,
    KeyValueBlock,
    PageBreakBlock,
    TableBlock,
    _cell_text,
    assumed_header,
)
from app.services.report.style import ReportStyle

_PAGESIZES = {"A4": A4, "A3": A3, "Letter": LETTER}
# getSampleStyleSheet() 每次调用新建一批样式对象；报表循环里调就是纯浪费
_BASE_STYLES = getSampleStyleSheet()

# REPORT_FONT_DIR 下按这些文件名找（用户投放的字体优先于系统兜底）
_FONT_FILES: dict[str, tuple[str, ...]] = {
    "Noto Sans CJK SC": ("NotoSansCJKsc-Regular.otf", "NotoSansCJKsc-Regular.ttf",
                         "NotoSansSC-Regular.otf", "NotoSansSC-Regular.ttf"),
    "Noto Serif CJK SC": ("NotoSerifCJKsc-Regular.otf", "NotoSerifCJKsc-Regular.ttf",
                         "NotoSerifSC-Regular.otf", "NotoSerifSC-Regular.ttf"),
    "Droid Sans Fallback": ("DroidSansFallbackFull.ttf",),
}

# 系统兜底候选**已挪进 settings.report_font_candidates**（配置驱动 —— 换字体是
# 运维动作，不该改代码）。这里只保留「按字体族名取链」的映射，测试也用它。
DEFAULT_FONT_CANDIDATES: tuple[str, ...] = (
    "./fonts/NotoSansSC-Regular.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansSC-Regular.ttf",
    "/usr/share/fonts/windows/hpsimplifiedhans-regular.ttf",
    "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
)

# ⚠️ **`page` 刻意不在这里**。它是渲染期才知道的值（`doc.page`），不是 context
# 里的值。放进来会被 `_fill_placeholders` 用 `ctx.get("page", "")` 吃掉成空串，
# 页脚就永远显示「第 页」。`{{page}}` 由 `_decorate` 在填充 context **之前**替换。
_KNOWN_PLACEHOLDERS = {"project_no", "project_name", "doc_no", "rev",
                       "report_name"}
# 2026-10-08 裁决已从 SPEC §4.1 移除 "pages"（ReportLab 两遍渲染代价 ×2）

# 字体注册进程内只做一次。⚠️ 顺序不能反：先 registerFont 再 registerFontFamily，
# 否则 Paragraph 找不到 family 映射会静默回退 Helvetica —— PDF 结构仍合法、
# 测试仍绿，用户拿到的是方块（与 bug-150 同族的假绿）。
_REGISTERED: set[str] = set()

# 报表里**必须**能渲染的字符。**这段字符串本身就是契约的一部分** ——
# 改动它等于改动验收标准，每个字符都代表一类必然出现的文本：
#   P D N        位号前缀（P-101 / DN50 / NPSH）
#   0-9          数值、日期、版本号
#   A-Z a-z      单位（m3/h / NPSH / kg）
#   % °          比值与温度
#   - _ ( ) / : 空格    编号与标点
# ⚠️ 删掉任一字符，一个缺该字形的字体就会混过守卫，而对应内容会静默变空白
# （页码那类 bug 的同款，只是发生在标点上）。故 `test_probe_covers_every_class`
# 钉住它。
_PROBE = "PDNABCabc0123456789%°-_.()/: "

logger = logging.getLogger(__name__)


def _missing_glyphs(font_name: str) -> list[str]:
    """返回探针里该字体画不出来的字符。

    走 `face.charWidths`（按码位索引）而不是 cmap —— reportlab 注册 TTF 时
    已经把 cmap 摊平进这个字典了，不必自己解析字体二进制。
    """
    char_widths = pdfmetrics.getFont(font_name).face.charWidths
    return [c for c in _PROBE if ord(c) not in char_widths]


def _unregister_font(font_name: str) -> None:
    """把字体从全局注册表摘掉。

    reportlab **没有公开的注销 API**（只有 `registerFont`，没有 `unregisterFont`），
    所以只能动私有的 `_fonts`。选下一个候选前必须摘干净，否则一个残缺字体
    会留在全局表里被别的调用捡到 —— 而 `getFont(name)` 命中缓存时根本不会
    重新校验字形，等于把刚发现的坑又埋回去。
    """
    pdfmetrics._fonts.pop(font_name, None)  # noqa: SLF001 —— 无公开替代


def _candidate_paths(name: str, font_dir: str | Path,
                     configured: list[str] | None = None) -> list[Path]:
    """候选链 = REPORT_FONT_DIR 下的约定文件名（优先）+ settings 里的链。

    「存在的排前面」纯粹是省事：文件不存在时 `TTFont` 会抛 FileNotFoundError，
    让它走 except 分支也算正确，只是错误信息里混进一堆无关的噪声。
    """
    cands = [Path(font_dir) / fn for fn in _FONT_FILES.get(name, ())]
    chain = configured if configured is not None else \
        get_settings().report_font_candidates
    cands += [Path(x) for x in chain]
    present = [p for p in cands if p.exists()]
    return present + [p for p in cands if not p.exists()]


def resolve_font_path(style: ReportStyle, font_dir: str | Path | None = None) -> Path:
    """解析出要用的字体文件 —— **只判存在，不试注册**。

    供配置自检 / 错误信息用；真正注册走 `_register_font`。两者分开是因为
    「文件在」和「reportlab 能读」是两回事（见模块 docstring 约束 1），
    而这里连「字够不够」都不验（约束 3）。
    """
    cands = _candidate_paths(style.font_family_cn, font_dir or style.font_dir)
    for p in cands:
        if p.exists():
            return p
    raise PcsError(
        f"中文字体缺失：{style.font_family_cn}。已尝试：{', '.join(str(p) for p in cands)}。"
        f"请运行 scripts/build_report_font.py 派生静态字体，或把字体投放到 "
        f"REPORT_FONT_DIR。",
        code="REPORT_FONT_MISSING", status=500,
    )


def _register_font(style: ReportStyle, font_dir: str | Path | None = None) -> str:
    """注册中文字体。

    **逐个候选试**，每个候选过三道关才轮不到下一个：
      1. 文件在        —— 少了直接跳过
      2. reportlab 读得动（TrueType 轮廓，CFF/TTC 一律不行）
      3. 字形覆盖够 `_PROBE`（缺 ASCII 的字体会让数字全空白）

    关 3 对**每一个**候选都跑，不是在链末尾跑一次 —— 链里任何一环塞进坏字体
    都得被拦下来。每次否决都记 WARN，否则「为什么这台机器用了次优字体」
    永远查不出来。
    """
    name = style.font_family_cn
    if name in _REGISTERED:
        return name
    cands = _candidate_paths(name, font_dir or style.font_dir)
    rejected: list[str] = []
    for path in cands:
        if not path.exists():
            continue
        try:
            pdfmetrics.registerFont(TTFont(name, str(path)))
        except Exception as e:  # noqa: BLE001 —— reportlab 对各种坏字体抛不同异常类型
            reason = f"{path}（无法解析：{type(e).__name__}）"
            logger.warning("报表字体候选被否：%s", reason)
            rejected.append(reason)
            continue  # 存在但读不动 → 试下一个，绝不因此中断
        missing = _missing_glyphs(name)
        if missing:
            reason = f"{path}（缺字形 {''.join(missing)!r}）"
            logger.warning("报表字体候选被否：%s", reason)
            rejected.append(reason)
            _unregister_font(name)  # 别让残缺字体留在全局注册表里
            continue
        pdfmetrics.registerFontFamily(name, normal=name)
        _REGISTERED.add(name)
        logger.info("报表字体已注册：%s ← %s", name, path)
        return name
    raise PcsError(
        f"中文字体缺失或不可用：{name}。已尝试：{', '.join(str(p) for p in cands)}。"
        + (f"被否掉的原因：{'; '.join(rejected)}。" if rejected else "")
        + "PDF 中文会渲染为方块、数字会渲染为空白，故直接失败。"
        "请运行 scripts/build_report_font.py，或在部署镜像里装中文字体。"
        "⚠️ 三个已知坑：(1) .ttc / CFF 轮廓 reportlab 读不了；"
        "(2) 可变字体的默认实例是 Thin（wght=100），要用得先派生静态 Regular；"
        "(3) DroidSansFallbackFull.ttf 一个 ASCII 字形都没有。",
        code="REPORT_FONT_MISSING", status=500,
    )


def _fill_placeholders(text: str, ctx: dict) -> str:
    """替换页眉页脚占位符。**未知占位符原样保留** —— 拼错时看得见，
    静默替换成空串反而更糟（页脚会少一段文字却没人发现）。"""
    def repl(m):
        key = m.group(1)
        return str(ctx.get(key, "")) if key in _KNOWN_PLACEHOLDERS else m.group(0)
    return re.sub(r"\{\{(\w+)\}\}", repl, text)


def _draw_qr(canvas, payload: str, *, x: float, y: float, size_mm: float) -> None:
    """`QrCodeWidget` 是 `Widget` 不是 `Flowable`，**没有 `.drawOn` 方法**
    （照抄会 AttributeError）。必须包进 `Drawing` 再 `renderPDF.draw`。"""
    q = qr.QrCodeWidget(payload)
    x0, y0, x1, y1 = q.getBounds()
    w, h = (x1 - x0) or 1, (y1 - y0) or 1
    size = size_mm * mm
    d = Drawing(size, size, transform=[size / w, 0, 0, size / h, 0, 0])
    d.add(q)
    renderPDF.draw(d, canvas, x, y)


def _decorate(canvas, doc, *, style: ReportStyle, font: str,
              qr_payload: str | None, context: dict) -> None:
    """页脚绘制回调。模块级而非闭包 —— 签名显式传参，可直接单测。"""
    canvas.saveState()
    canvas.setFont(font, style.font_size_body - 2)
    canvas.drawString(doc.leftMargin, doc.bottomMargin / 2,
                      _fill_placeholders(style.footer.left, context))
    canvas.drawCentredString(
        doc.width / 2, doc.bottomMargin / 2,
        _fill_placeholders(style.footer.right.replace("{{page}}", str(doc.page)), context))
    if qr_payload:
        _draw_qr(canvas, qr_payload,
                 x=doc.width - doc.rightMargin - style.qr_size_mm * mm,
                 y=doc.bottomMargin / 2, size_mm=style.qr_size_mm)
    canvas.restoreState()


def render_pdf(*, title: str, blocks: list[Block], style: ReportStyle,
               qr_payload: str | None, assumed_fields: list[str],
               context: dict | None = None,
               font_dir: str | Path | None = None) -> bytes:
    """渲染 PDF 并返回字节。context 提供页眉页脚占位符的值。"""
    context = context or {}
    font = _register_font(style, font_dir)
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=_PAGESIZES[style.page_size],
        leftMargin=style.margins.left, rightMargin=style.margins.right,
        topMargin=style.margins.top, bottomMargin=style.margins.bottom,
        title=title,
    )
    h1 = ParagraphStyle("h1", parent=_BASE_STYLES["Heading1"], fontName=font,
                        fontSize=style.font_size_heading,
                        leading=style.font_size_heading * 1.4)
    body = ParagraphStyle("body", parent=_BASE_STYLES["BodyText"], fontName=font,
                          fontSize=style.font_size_body,
                          leading=style.font_size_body * style.line_spacing)

    story: list = [Paragraph(title, h1)]
    if assumed_fields:
        note = Paragraph(
            f"本页含假设数据：{style.assumption_mark} " + "、".join(assumed_fields), body)
        story += [note, Spacer(1, 8)]

    for b in blocks:
        if isinstance(b, HeadingBlock):
            story.append(Paragraph(b.text, h1 if b.level == 1 else body))
        elif isinstance(b, PageBreakBlock):
            story.append(PageBreak())
        elif isinstance(b, KeyValueBlock):
            story.append(Table(
                [[Paragraph(str(k), body), Paragraph(_cell_text(v), body)] for k, v in b.rows],
                colWidths=[doc.width * 0.3, doc.width * 0.7],
                style=TableStyle([("GRID", (0, 0), (-1, -1), style.table.border_width,
                                   colors.HexColor(style.table.border_color))]),
            ))
        elif isinstance(b, TableBlock):
            mc = style.table.max_cell_chars
            data = [[Paragraph(assumed_header(h, ci in b.assumed_cols,
                                              style.assumption_mark), body)
                     for ci, h in enumerate(b.headers)]] + [
                [Paragraph(_cell_text(c, mc), body) for c in row] for row in b.rows]
            t = Table(data, repeatRows=1, hAlign="LEFT")
            cmds = [
                ("GRID", (0, 0), (-1, -1), style.table.border_width,
                 colors.HexColor(style.table.border_color)),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(style.table.header_bg)),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
            if style.table.zebra_stripe:
                for i in range(2, len(data), 2):
                    cmds.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#F5F7FB")))
            for ci in b.assumed_cols:
                cmds.append(("TEXTCOLOR", (ci, 1), (ci, -1),
                             colors.HexColor(style.assumption_color)))
            # 表头三角：headers 已在上面渲染，这里用 colspan=0 的空 cell 无法改字，
            # 故三角直接写进 header 文本（见 blocks.assumed_header）
            t.setStyle(TableStyle(cmds))
            story.append(t)

    doc.build(story,
              onFirstPage=lambda c, d: _decorate(c, d, style=style, font=font,
                                                qr_payload=qr_payload, context=context),
              onLaterPages=lambda c, d: _decorate(c, d, style=style, font=font,
                                                 qr_payload=qr_payload, context=context))
    return buf.getvalue()