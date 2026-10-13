"""部署侧报表字体自检（TODO-045）。

## 它防什么

`REPORT_FONT_CANDIDATES` 全链落空时 `render_pdf` 抛 `REPORT_FONT_MISSING`
（500）。本地永远看不出来：`tests/conftest.py` 缺字体时会**自动派生**
—— 那是刻意的（skip 就是假绿），但代价是部署侧没有任何自动兜底，
于是「P8 上线当天所有 PDF 500、且只在生产暴露」成为一个真实风险。

**上线前跑一次本脚本**（或在部署镜像构建里跑），那个 500 就提前到上线前：

    uv run python scripts/check_report_font.py

- 退出 0：字体就绪，stdout 报出实际选中的路径
- 退出 1：全链落空 / 全链被否，stdout 给出**每个候选被否的原因**与修法

## 为什么复用 `renderer_pdf._register_font` 而不是自己再写一遍检查

自检的价值取决于它测的是**不是生产真正走的那条路**。抄一份「检查逻辑」
会在某次 renderer 改动后悄悄漂移 —— 自检绿着、生产照样 500。
这里直接调 `_register_font`（与 `render_pdf` 同一条路径），漂移不可能。

三道关全在 `_register_font` 里（文件在 / reportlab 读得动 /
`_PROBE` 字形覆盖），被否的候选会逐个记 WARN。

## ⚠️ 已知的错误修法（别再走）

`apt install fonts-noto-cjk` **不能**解决此问题 —— 它装出 `.ttc` + CFF
轮廓，reportlab 直接抛 `TTFError: postscript outlines are not supported`。
装了它本脚本照样红。正确做法二选一：

1. 镜像构建步骤里跑 `uv run python scripts/build_report_font.py`
   （需要镜像里有 OFL 的 Noto Sans SC **可变**字体作为源）；
2. 或把 `build_report_font.py` 的产物（静态 Regular，约 10.6 MB）直接
   投放到 `REPORT_FONT_DIR`。
"""
from __future__ import annotations

import logging
import sys

# 让 _register_font 里每个被否候选的 WARN 都打到 stderr ——
# 部署排障时「哪个文件、为什么被否」就是全部信息量。
logging.basicConfig(level=logging.WARNING, stream=sys.stderr,
                    format="%(levelname)s %(message)s")


def main() -> int:
    from app.services.exceptions import PcsError
    from app.services.report.renderer_pdf import _register_font
    from app.services.report.style import ReportStyle

    try:
        # 复用生产路径：与 render_pdf 同一个函数、同一份配置。
        # 传裸 ReportStyle() 即用当前 settings 的 font_dir / 候选链。
        _register_font(ReportStyle())
    except PcsError as e:
        if e.code != "REPORT_FONT_MISSING":
            raise          # 意外错误不该被吞成本脚本的「字体缺失」
        # PcsError 的文本在 str(e)（构造参数 message 走 super().__init__），
        # 没有 .message 属性 —— 第一版写 e.message 得到 AttributeError，
        # 把真正的「字体缺失」盖成了「脚本自己崩了」。
        print(f"FAIL {e.code}: {e}", file=sys.stderr)
        print(
            "\n修法（二选一）：\n"
            "  1) uv run python scripts/build_report_font.py   "
            "# 从 OFL 可变字体派生静态 Regular\n"
            "  2) 把派生产物投放到 REPORT_FONT_DIR（默认 ./fonts）\n"
            "⚠️ apt install fonts-noto-cjk 没用 —— .ttc + CFF 轮廓 "
            "reportlab 读不了。",
            file=sys.stderr,
        )
        return 1

    from app.core.config import get_settings
    from app.services.report.renderer_pdf import resolve_font_path
    # 报出实际选中的路径 —— 部署排障要能回答「这台机器用的是哪份字体」。
    print(f"OK 报表中文字体就绪：{resolve_font_path(ReportStyle())}")
    print(f"   REPORT_FONT_DIR = {get_settings().report_font_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
