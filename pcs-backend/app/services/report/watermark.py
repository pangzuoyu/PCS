"""导出水印与格式分发（P8b b8）。

## 水印是**语义声明**，不是装饰

即席导出件不是签署过的交付物（SPEC §3.2.2(8)）。没有水印的即席文件被
当成正式版打印出去，签署矩阵就形同虚设 —— 而签署矩阵是 SUP-007 的核心。
所以水印**每一份**即席导出都必须带，含时间戳：时间戳让「这份是哪一次
临时导出」可追溯，也让「这文件不是签署件」这句话有具体所指。

演示版（SUP-006）在非发布件水印之上**叠加** DEMO 水印，不替换 ——
DEMO 水印说明「这是演示版」，非发布件水印说明「这没签署」，两件事。

## 水印落在哪里

| 格式 | 位置 | 为什么 |
|---|---|---|
| PDF | 首页 + 每页页眉斜排 | 页眉会被后续页覆盖的位置遮住，单页首页水印等于只有第一页有 |
| XLSX | 第 1 行整行横幅 | Excel 里 A1 单元格可见；放最后一行没人会滚到 |
| DOCX | 页眉段落 | 与打印行为一致 |
| CSV | 首行 `#` 注释 | CSV 没有页眉概念；`#` 是 pandas / `csv` 生态的事实注释约定 |

⚠️ CSV 首行注释**会让 Excel 双击打开时报「格式不符」**。这是刻意的取舍：
CSV 的定位是「给脚本再处理」，不是「给人双击看」；要双击看请导 xlsx。
"""
from __future__ import annotations

import csv
import datetime as dt
import io

from app.core.config import get_settings
from app.services.report.blocks import Block, HeadingBlock, TableBlock

NON_ISSUED_PREFIX = "非发布件"
DEMO_MARK = "DEMO"

#: 演示版报表定义数量上限（SPEC §3.2.2(8)，SUP-006）
DEMO_MAX_DEFINITIONS = 3

#: 即席导出的全部格式。CSV 此前不在 `report_service.SUPPORTED_FORMATS`
#: 里（那边注释写「Excel/CSV 走 xlsx 渲染器」），于是用户在输出格式下拉
#: 框里**选不到 CSV** —— SPEC 明确要求三种都可导出。
EXPORT_FORMATS = ("pdf", "xlsx", "docx", "csv")

_EXT = {"pdf": "pdf", "xlsx": "xlsx", "docx": "docx", "csv": "csv"}


def watermark_text(*, timestamp: str | None = None, demo: bool = False) -> str:
    """水印文本。演示版在前面加 DEMO 标记。"""
    ts = timestamp or dt.datetime.now(dt.UTC).strftime("%Y-%m-%d %H:%M:%S")
    prefix = f"{DEMO_MARK} · " if demo else ""
    return f"{prefix}{NON_ISSUED_PREFIX} · {ts}"


def apply(blocks: list[Block], *, timestamp: str | None = None,
          demo: bool | None = None) -> list[Block]:
    """在水印文本后返回新 Block 列表（不改入参）。

    用 `HeadingBlock` 而不是新 Block 类型：三个渲染器都已经会渲染它，
    新造一个类型就得三个渲染器各改一遍 —— 而漏改的那个不报错，只是
    那个格式没有水印。
    """
    is_demo = get_settings().report_demo_mode if demo is None else demo
    return [HeadingBlock(text=watermark_text(timestamp=timestamp, demo=is_demo),
                         level=1), *blocks]


def check_demo_definition_limit(current_count: int) -> None:
    """演示版定义数超限时抛 403。**非演示版不限**。"""
    if not get_settings().report_demo_mode:
        return
    if current_count >= DEMO_MAX_DEFINITIONS:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"演示版最多 {DEMO_MAX_DEFINITIONS} 个报表定义"
            f"（已有 {current_count} 个）。",
            code="REPORT_DEMO_LIMIT", status=403,
        )


def render_to_bytes(blocks: list[Block], *, output_format: str, title: str,
                    style, context: dict | None = None,
                    font_dir=None) -> bytes:
    """按格式渲染并返回字节。CSV 走专门的实现。"""
    if output_format not in EXPORT_FORMATS:
        from app.services.exceptions import PcsError

        raise PcsError(
            f"不支持的输出格式：{output_format!r}。支持 {sorted(EXPORT_FORMATS)}。",
            code="REPORT_FORMAT_UNSUPPORTED", status=400,
        )
    if output_format == "csv":
        return render_csv(title=title, blocks=blocks)
    if output_format == "xlsx":
        from app.services.report.renderer_xlsx import render_xlsx

        return render_xlsx(title=title, blocks=blocks, style=style,
                           context=context or {})
    if output_format == "docx":
        from app.services.report.renderer_docx import render_docx

        return render_docx(title=title, blocks=blocks, style=style,
                           context=context or {})
    from app.services.report.renderer_pdf import render_pdf

    return render_pdf(title=title, blocks=blocks, style=style, qr_payload=None,
                      assumed_fields=[], context=context or {},
                      font_dir=font_dir)


def render_csv(*, title: str, blocks: list[Block]) -> bytes:
    """Block 列表 → CSV 字节（UTF-8 带 BOM，Excel 双击不乱码）。

    ⚠️ 用 `csv` 模块而不是手工 `",".join` —— 字段值里出现逗号、引号、
    换行时手工拼会**列错位**，而列错位的数据表比报错更难发现。
    """
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    for b in blocks:
        if isinstance(b, HeadingBlock):
            w.writerow([f"# {b.text}"])
        elif isinstance(b, TableBlock):
            w.writerow(list(b.headers))
            for row in b.rows:
                w.writerow(["" if c is None else str(c) for c in row])
    # BOM：没有它 Excel 按本地代码页读，中文全是乱码
    return b"\xef\xbb\xbf" + buf.getvalue().encode("utf-8")


def file_extension(output_format: str) -> str:
    return _EXT.get(output_format, "pdf")


__all__ = ["NON_ISSUED_PREFIX", "DEMO_MARK", "DEMO_MAX_DEFINITIONS",
           "EXPORT_FORMATS", "watermark_text", "apply", "render_to_bytes",
           "render_csv", "check_demo_definition_limit", "file_extension"]