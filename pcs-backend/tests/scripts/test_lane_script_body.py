"""`lane_script_body` 的**剥注释口径**（P10-F · 评审 #27）。

## 为什么这个文件存在

守门测试要断的是「**脚本有没有做这件事**」⇒ ⇒ 断的必须是脚本的**可执行部分**
⇒ ⇒ 注释里写一句 `flock -n` 不足以让守卫通过。

⚠️ **朴素的剥法会误判**：`line.split("#", 1)[0]` 把
`echo "a # b"`（引号里的 `#` 是**字面量**）与 `echo a#b`（`#` 前不是空白）
**一起剥掉** ⇒ ⇒ 脚本里只剩注释时，守卫会**误判为可执行** ⇒ ⇒ **假绿**。

⇒ ⇒ 本文件把口径钉死（**按 shell 的词边界规则**：`#` 只有在**词首**
才���注释）。
"""
from __future__ import annotations

from pathlib import Path

from tests.scripts.lane_script_body import lane_script_body


def _write(tmp_path: Path, text: str) -> Path:
    script = tmp_path / "lane.sh"
    script.write_text(text, encoding="utf-8")
    return script


def test_a_whole_line_comment_is_removed(tmp_path: Path) -> None:
    script = _write(tmp_path, "# flock -n 9\necho hi\n")
    body = lane_script_body(script)
    assert "flock" not in body
    assert "echo hi" in body


def test_an_indented_whole_line_comment_is_removed(tmp_path: Path) -> None:
    script = _write(tmp_path, "    # flock -n 9\n    echo hi\n")
    body = lane_script_body(script)
    assert "flock" not in body
    assert "echo hi" in body


def test_an_inline_comment_after_whitespace_is_removed(tmp_path: Path) -> None:
    script = _write(tmp_path, "exec 9>\"$LOCK\"  # 锁住 fd 9\n")
    body = lane_script_body(script)
    assert "#" not in body
    assert 'exec 9>"$LOCK"' in body


def test_a_hash_inside_double_quotes_is_not_a_comment(tmp_path: Path) -> None:
    script = _write(tmp_path, 'echo "a # b"\n')
    assert "a # b" in lane_script_body(script)


def test_a_hash_inside_single_quotes_is_not_a_comment(tmp_path: Path) -> None:
    script = _write(tmp_path, "echo 'a # b'\n")
    assert "a # b" in lane_script_body(script)


def test_a_hash_without_preceding_whitespace_is_not_a_comment(tmp_path: Path) -> None:
    script = _write(tmp_path, "echo a#b\n")
    assert "a#b" in lane_script_body(script)
