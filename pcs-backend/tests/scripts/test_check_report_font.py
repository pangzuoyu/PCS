"""`scripts/check_report_font.py` —— 部署侧字体自检（TODO-045）。

## 为什么需要它

`REPORT_FONT_CANDIDATES` 全链落空时 `render_pdf` 抛 `REPORT_FONT_MISSING`
（500）。本地永远看不出来：`tests/conftest.py` 会在字体缺失时**自动派生**
—— 那是刻意的（skip 就是假绿），但代价是**部署侧没有任何自动兜底**，
P8 上线当天所有 PDF 报表 500，且只在生产才暴露。

本脚本给部署一个**能在上线前跑**的闸：复用 `renderer_pdf._register_font`
（生产真正走的那条路，不是抄一份等它漂移），字体过不了三道关
（文件在 / reportlab 读得动 / `_PROBE` 字形覆盖）就退出非零。

## 顺带钉住一个错误建议

TODO-045 原文建议「Dockerfile 里 `apt install fonts-noto-cjk`」——
**那条路走不通**：fonts-noto-cjk 装出来是 `.ttc` + CFF 轮廓，reportlab
直接抛 `TTFError: postscript outlines are not supported`（build_report_font.py
的 docstring 与 config.py 的注释都写了）。装了它，本自检照样红 ——
这正是自检存在的意义：把「装了个没用的字体包」在上线前暴露，而不是
上线后第一份 PDF 上。
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "check_report_font.py"


def _run(env_extra: dict[str, str]) -> subprocess.CompletedProcess:
    env = {**os.environ,
           # JSON 列表：pydantic-settings 对 list 字段的 env 解析格式
           **{k: v if isinstance(v, str) else json.dumps(v)
              for k, v in env_extra.items()}}
    return subprocess.run(
        [sys.executable, str(SCRIPT)], capture_output=True, text=True,
        timeout=120, env=env, cwd=SCRIPT.parents[1],
    )


def test_missing_script_is_not_silent():
    """脚本得先存在 —— 这条红是 RED 阶段本身。"""
    assert SCRIPT.exists(), f"自检脚本不存在：{SCRIPT}"


@pytest.mark.usefixtures("report_font_path")
def test_exits_zero_when_a_font_resolves(report_font_path):
    """有可用字体（conftest 派生那份）→ 退出 0，并报出**具体用的哪个**。

    ⚠️ 候选链刻意只指派生产物一份 —— 不这样写的话，链里排在后面的
    本机兜底字体（hp）也会命中，测试就变成「这台机器碰巧有字体」。
    """
    r = _run({
        "REPORT_FONT_DIR": str(report_font_path.parent),
        "REPORT_FONT_CANDIDATES": [str(report_font_path)],
    })
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert str(report_font_path) in r.stdout, "没报出实际选中的字体路径"


def test_exits_nonzero_with_remediation_when_chain_is_empty(tmp_path):
    """⚠️ 根断言：全链落空 → 非零退出 + 指明修法。

    这正是 TODO-045 的失效模式：本地（自动派生）永远不触发，
    生产第一份 PDF 才 500。部署前跑本脚本，把那个 500 提前到上线前。
    """
    r = _run({
        "REPORT_FONT_DIR": str(tmp_path / "empty"),
        "REPORT_FONT_CANDIDATES": [str(tmp_path / "no-such-font.ttf")],
    })
    assert r.returncode != 0, f"全链落空竟报通过：{r.stdout}"
    out = r.stdout + r.stderr
    assert "REPORT_FONT_MISSING" in out, "没报错误码，运维无从检索"
    assert "build_report_font.py" in out, "没给出修法（跑派生脚本）"


def test_a_present_but_unreadable_font_is_rejected_not_swallowed(tmp_path):
    """存在但 reportlab 读不动的文件（如伪造的 .ttc）必须被否掉。

    ⚠️ 这条钉住「apt install fonts-noto-cjk 是错误修法」：
    装了 CFF 轮廓的 .ttc，自检必须红 —— 否则部署方以为字体就绪了，
    上线后第一份 PDF 才炸。
    """
    bogus = tmp_path / "bogus.ttf"
    bogus.write_bytes(b"not a font at all")
    r = _run({
        "REPORT_FONT_DIR": str(tmp_path),
        "REPORT_FONT_CANDIDATES": [str(bogus)],
    })
    assert r.returncode != 0
    out = r.stdout + r.stderr
    assert "bogus" in out, "被否的候选要出现在输出里 —— 否则查不出是哪个文件"
