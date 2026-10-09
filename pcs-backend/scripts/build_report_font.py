#!/usr/bin/env python
"""从 OFL 可变字体派生 reportlab 能用的静态 CJK 字体。

## 为什么需要这个脚本

PDF 渲染器（`app/services/report/renderer_pdf.py`）需要一份**同时**满足三条的
中文字体：

1. **TrueType 轮廓** —— reportlab 不支持 CFF/PostScript 轮廓。
   Debian/Ubuntu 的 `fonts-noto-cjk` 装出来是 `.ttc` + CFF，reportlab 直接抛
   `TTFError: postscript outlines are not supported`。
2. **非极细字重** —— reportlab 取可变字体的**默认实例**。Noto Sans SC 可变
   字体的 `wght` 默认值是 **100（Thin）**，于是整份报表是发丝字。
   实测：把默认实例直接注册进 PDF，`pdffonts` 显示
   `AAAAAA+NotoSansSC-Thin`。
3. **含拉丁字形** —— Droid Sans Fallback 零 ASCII 字形，`P-101` / `DN50` /
   所有数字会渲染成空白。

本脚本用 fontTools 把 `wght=400` 的静态实例从可变字体里切出来，三条全满足，
产物约 10.6 MB（可变原文件 17.7 MB）。

## 许可

输入源字体必须是 **SIL OFL 1.1**（Noto Sans SC / Source Han Sans 同源，
两者是同一套字形，Noto 是 Google 的构建）。产物继承 OFL，可自由再分发与嵌入。

⚠️ **不要把 HP Simplified Hans 当输入**：它字形齐全但 name 表写着
「This typeface is the property of Dalton Maag Ltd / Modification requires
prior written permission」—— 专有许可，产物不能自由再分发。
（它仍留在 settings 的候选链末尾，仅作本机开发兜底。）

## 用法

    uv run python scripts/build_report_font.py                 # 自动找源，写到 REPORT_FONT_DIR
    uv run python scripts/build_report_font.py --src A.ttf --out ./fonts/NotoSansSC-Regular.ttf

设计取舍：**不入库**（用户 2026-10-09 裁决）。产物落在 `REPORT_FONT_DIR`
（默认 `./fonts`，已 gitignore），部署/CI 镜像构建时跑一次即可。
`tests/conftest.py` 会在字体缺失时自动调用本脚本，所以测试永不 skip ——
skip 就是这个项目最熟悉的假绿。
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

# 优先找的源字体（OFL）。顺序即优先级。
DEFAULT_SOURCES = (
    "/usr/share/fonts/windows/NotoSansSC-VF.ttf",
    "/usr/share/fonts/opentype/noto/NotoSansSC-VF.ttf",
    "/usr/share/fonts/windows/NotoSerifSC-VF.ttf",
)
DEFAULT_OUT = "./fonts/NotoSansSC-Regular.ttf"
WEIGHT = 400

# 与 renderer_pdf._PROBE 同款 —— 产物必须能画全这些，否则守卫会拒收它
PROBE = "ABCabc0123%°-_.()/: "


def _is_glyph_complete(path: Path) -> tuple[bool, int, list[str]]:
    """返回 (字形是否齐, 汉字数, 缺失的探针字符)。"""
    codes = set(TTFont(str(path), lazy=True).getBestCmap().keys())
    missing = [c for c in PROBE if ord(c) not in codes]
    hanzi = sum(1 for cp in codes if 0x4E00 <= cp <= 0x9FFF)
    return not missing, hanzi, missing


def derive(src: Path, out: Path) -> None:
    font = TTFont(str(src))
    axes = [a.axisTag for a in font["fvar"].axes] if "fvar" in font else []
    if "wght" in axes:
        font = instancer.instantiateVariableFont(font, {"wght": WEIGHT})
    out.parent.mkdir(parents=True, exist_ok=True)
    font.save(str(out))

    if "glyf" not in TTFont(str(out), lazy=True):
        sys.exit(f"❌ 派生产物仍是 CFF 轮廓，reportlab 读不了：{out}")
    ok, hanzi, missing = _is_glyph_complete(out)
    if not ok:
        sys.exit(f"❌ 派生产物缺字形 {missing!r}，会被 renderer_pdf 的守卫拒收：{out}")
    print(f"✅ {src} --wght={WEIGHT}--> {out} "
          f"({out.stat().st_size / 1e6:.1f} MB, 汉字 {hanzi:,}, 探针全过)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--src", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=Path(DEFAULT_OUT))
    args = ap.parse_args()

    src = args.src
    if src is None:
        src = next((Path(p) for p in DEFAULT_SOURCES if Path(p).exists()), None)
    if src is None or not src.exists():
        sys.exit(
            "❌ 找不到 OFL 可变中文字体。装一个：\n"
            "   apt install fonts-noto-cjk     # 或从 Google Fonts 取 Noto Sans SC 可变版\n"
            "也可以用 --src 显式指定路径。"
        )
    derive(src, args.out)


if __name__ == "__main__":
    main()