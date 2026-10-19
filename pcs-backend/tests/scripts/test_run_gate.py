"""`scripts/run_gate.py` 的测试 —— 它唯一的产出是「一个退出码」。

## 为什么这么小的工具也要测

TODO-050 的失效模式是**沉默的假绿**：`cmd | tail; echo $?` 读到的是
`tail` 的码。于是「裸字段 71 → 73」的回归被报告成「闸门通过」。

本工具就是为了消灭那一类。测它要证明的是：**非零码被如实报出来**，
以及它**不会**像管道那样把码吃掉。
"""
from __future__ import annotations

import sys

import pytest

from scripts.run_gate import main, run, run_capture


def test_reports_the_commands_own_nonzero_exit_code(capsys):
    """⚠️ 根断言：命令 exit 1 → 本脚本也 exit 1。

    这正是管道吃掉的那一类：`sh -c 'exit 1' | tail` 整体返回 0。
    """
    code = run([sys.executable, "-c", "import sys; print('boom'); sys.exit(1)"],
               tail=5)
    assert code == 1
    out = capsys.readouterr().out
    assert "EXIT=1" in out
    assert "boom" in out


def test_reports_zero_for_a_passing_command(capsys):
    code = run([sys.executable, "-c", "print('ok')"], tail=5)
    assert code == 0
    assert "EXIT=0" in capsys.readouterr().out


def test_streams_stderr_too(capsys):
    """闸门的失败信息常走 stderr —— 只收 stdout 会让报错凭空消失。"""
    code = run([sys.executable, "-c",
                "import sys; sys.stderr.write('警告在这\\n'); sys.exit(2)"],
               tail=5)
    assert code == 2
    assert "警告在这" in capsys.readouterr().out


def test_tail_keeps_the_last_lines_and_says_it_truncated(capsys):
    code = run([sys.executable, "-c", "print('\\n'.join(str(i) for i in range(50)))"],
               tail=5)
    assert code == 0
    out = capsys.readouterr().out
    assert "略去前 45 行" in out
    assert "49" in out
    assert "\n10\n" not in out, "被截掉的行不该出现在输出里"


def test_missing_command_is_127_not_a_traceback(capsys):
    assert run(["这个命令不存在-xyz"], tail=3) == 127
    assert "命令不存在" in capsys.readouterr().err


def test_cli_strips_the_separator(capsys):
    """`-- command` 的 `--` 要被去掉，否则 `--` 会被当成命令名。"""
    code = main(["--tail", "3", "--", sys.executable, "-c", "print(1)"])
    assert code == 0


def test_cli_without_command_is_an_error(capsys):
    with pytest.raises(SystemExit):
        main(["--tail", "3"])


# ---- run_capture()（P9-Prep PP-5 新增）----
# 既有 7 个测试覆盖的是 run()；run_capture() 是新函数，三条分支一条都不能少 ——
# 其中 127 / 124 是 run() 改调后**透传**出来的，改错了 run() 的既有测试抓不到。


def test_run_capture_returns_code_and_merged_output():
    rc, out = run_capture([sys.executable, "-c",
                           "import sys; print('o'); sys.stderr.write('e'); sys.exit(3)"])
    assert rc == 3
    assert "o" in out and "e" in out


def test_run_capture_missing_command_is_127():
    rc, out = run_capture(["这个命令不存在-abc"])
    assert rc == 127
    assert "命令不存在" in out


def test_run_capture_timeout_is_124():
    rc, out = run_capture(
        [sys.executable, "-c", "import time; time.sleep(5)"], timeout=0.1
    )
    assert rc == 124
    assert "超时" in out


def test_run_still_forwards_127_after_refactor():
    """回归：run() 改成转调 run_capture 后，127 必须仍然透传。"""
    assert run(["这个命令不存在-def"], tail=3) == 127
