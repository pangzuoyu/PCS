"""脚本「可执行部分」的**一处真相源**（P10-F · 评审 #27）。

## 为什么要有这个模块

⚠️ **同一个文件里两套口径 ⇒ 至少要一致**
（`docs/solutions/testing-issues/guard-test-must-use-its-own-lane-lock.md` §4）：

- `test_pytest_e2e_gate.py` 有一份 `_body()`（剥注释）⇒ 断薄封装时用它；
- 同一文件里的 flock 守卫却读**原文** ⇒ ⇒ 两套口径 ⇒ ⇒ **注释足以让守卫通过**。

⇒ ⇒ 抽成**一个**函数 ⇒ 两个测试文件都 import 它 ⇒ ⇒ 只有一处真相源。

⇒ ⇒ **新的守卫/新的脚本**一律用它 ⇒ ⇒ 别再各写一份 `_body()`。
"""
from __future__ import annotations

from pathlib import Path


def lane_script_body(script: Path) -> str:
    """脚本的**可执行部分**（去掉注释）—— 断「脚本有没有做这件事」必须断这里。

    ⚠️ **按 shell 的词边界规则剥**：`#` 只有在**词首**（行首或前面是空白）才是注释
    ⇒ ⇒ `echo "a # b"` 里的 `#` 是**字面量** ⇒ ⇒ `echo a#b` 里的 `#` 也是字面量
    ⇒ ⇒ ⇒ 早先的 `line.split("#", 1)[0]` 会把这两类**一起剥掉**
    ⇒ ⇒ ⇒ 守卫会在「脚本里只剩注释」时**误判为可执行**（⇒ ⇒ 假绿）。

    ⚠️ **不支持**：反引号（`` `…` ``）与 heredoc（`<<EOF`）⇒ ⇒ 这两种写法里的 `#`
    会被误剥 ⇒ ⇒ **守卫脚本自己不应使用这两种写法** ⇒ ⇒ 若将来要用 ⇒ ⇒ 换 `shlex` 解析。
    """
    out: list[str] = []
    for line in script.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#"):
            continue
        cut = len(line)
        quote = ""
        for i, ch in enumerate(line):
            if quote:
                if ch == quote:
                    quote = ""
                continue
            if ch in "'\"":
                quote = ch
                continue
            if ch == "#" and (i == 0 or line[i - 1].isspace()):
                cut = i
                break
        out.append(line[:cut])
    return "\n".join(out)
