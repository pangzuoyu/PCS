"""`tests/mutation.py` 自身的测试。

## 为什么一个元工具也要测

它唯一的产出是「这个变异确实被抓住了」这个**声明**。而这个工具失败时
的表现全是**沉默的假绿** —— 所以它自己的失败模式必须被钉住。

要证明它有用，先得证明**它会失败**。
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tests.mutation import (
    assert_restored,
    copy_and_restore,
    expect_killed,
    mutate,
    mutate_count,
    snapshot,
)

#: 一个被测文件的真身（临时目录里造，不碰仓库源码）
TARGET = "pkg_sample.py"


@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    """一个够 `expect_killed` 跑起来的微型项目。"""
    (tmp_path / "tests").mkdir()
    src = tmp_path / "pkg_sample.py"
    src.write_text(
        "def is_valid(n):\n"
        "    return n > 0\n"
        "\n"
        "def label(n):\n"
        "    if n > 0:\n"
        "        return 'pos'\n"
        "    return 'non'\n"
    )
    test = tmp_path / "tests" / "test_sample.py"
    test.write_text(
        "from pkg_sample import is_valid, label\n"
        "\n"
        "def test_positive():\n"
        "    assert is_valid(1) is True\n"
        "\n"
        "def test_label():\n"
        "    assert label(1) == 'pos'\n"
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    return tmp_path


def _ids(*names: str) -> list[str]:
    return [f"tests/test_sample.py::{n}" for n in names]


# --- mutate / mutate_count：老行为不许退化 ---------------------------------------


def test_mutate_rejects_a_no_op_mutation():
    with pytest.raises(AssertionError, match="空操作"):
        mutate("abc", "不存在的目标", "x")


def test_mutate_count_rejects_wrong_occurrence_count():
    with pytest.raises(AssertionError, match="出现 2 次"):
        mutate_count("aXbX", "X", "Y", expected=1)


# --- expect_killed：三步缺一不可 -----------------------------------------------


def test_baseline_must_be_green(sandbox):
    """⚠️ **恒红的测试能「杀掉」任何变异** —— 基线不绿必须先报错。

    这是最容易漏的一条：没有基线检查，报告「变异 100% 被杀死」可能
    只是因为那个测试本来就红。
    """
    broken = sandbox / "tests" / "test_broken.py"
    broken.write_text("def test_always_red():\n    assert False\n")
    with pytest.raises(AssertionError, match="基线不绿"):
        expect_killed(rel_path=TARGET, old="return n > 0", new="return False",
                      test_ids=_ids("test_broken.py::test_always_red"),
                      root=sandbox)


def test_a_test_that_does_not_catch_the_mutation_is_rejected(sandbox):
    """变异应用了但测试仍然全绿 → 必须报错。

    这是 TODO-048 点名的第二类失败。第一版工具只拦「没应用」，
    对这一类完全沉默。
    """
    with pytest.raises(AssertionError, match="仍然全绿"):
        # label(1) 的行为与 is_valid 无关 → 换掉 is_valid 只有 test_positive 抓得到
        expect_killed(rel_path=TARGET, old="return n > 0", new="return True",
                      test_ids=_ids("test_label"), root=sandbox)


def test_a_real_mutation_is_accepted(sandbox):
    """正例：测试确实抓得住 → 不报错，且文件被还原。"""
    before = (sandbox / TARGET).read_text()
    expect_killed(rel_path=TARGET, old="return n > 0", new="return False",
                  test_ids=_ids("test_positive"), root=sandbox)
    assert (sandbox / TARGET).read_text() == before, "文件没被还原"


def test_no_op_mutation_is_rejected_before_running_tests(sandbox):
    """变异目标是空操作 → 在跑测试**之前**就炸。

    顺序很重要：先跑一遍基线再炸，等于白跑一次。
    """
    with pytest.raises(AssertionError, match="空操作"):
        expect_killed(rel_path=TARGET, old="不存在的行", new="x",
                      test_ids=_ids("test_positive"), root=sandbox)


def test_file_is_restored_even_when_the_mutation_is_rejected(sandbox):
    """⚠️ **失败也必须还原**。否则一次失败的变异会把源码留在变异态，
    而 git 里看不出来（工作区是脏的，但没人知道是哪次变异留下的）。"""
    before = (sandbox / TARGET).read_text()
    with pytest.raises(AssertionError):
        expect_killed(rel_path=TARGET, old="return n > 0", new="return True",
                      test_ids=_ids("test_label"), root=sandbox)
    assert (sandbox / TARGET).read_text() == before


def test_empty_test_ids_are_rejected(sandbox):
    """空 test_ids 会让「任何变异都被杀掉」恒成立。"""
    with pytest.raises(AssertionError, match="不能为空"):
        expect_killed(rel_path=TARGET, old="return n > 0", new="return False",
                      test_ids=[], root=sandbox)


def test_missing_target_file_is_rejected(sandbox):
    with pytest.raises(AssertionError, match="不存在"):
        expect_killed(rel_path="根本没有这个文件.py", old="a", new="b",
                      test_ids=_ids("test_positive"), root=sandbox)


# --- snapshot / assert_restored --------------------------------------------------


def test_assert_restored_passes_once_the_content_is_back(sandbox):
    before = snapshot(TARGET, root=sandbox)
    mutated = (sandbox / TARGET).read_text().replace("return n > 0", "return False")
    (sandbox / TARGET).write_text(mutated)
    with pytest.raises(AssertionError):        # 还没还原：应当红
        assert_restored(TARGET, before, root=sandbox)
    (sandbox / TARGET).write_text(before)      # 还原后
    assert_restored(TARGET, before, root=sandbox)


def test_assert_restored_catches_a_left_behind_mutation(sandbox):
    before = snapshot(TARGET, root=sandbox)
    (sandbox / TARGET).write_text(
        (sandbox / TARGET).read_text().replace("return n > 0", "return False"))
    with pytest.raises(AssertionError, match="仍处于变异态"):
        assert_restored(TARGET, before, root=sandbox)


def test_snapshot_ignores_legitimate_uncommitted_work(sandbox):
    """⚠️ **不能拿 `git diff` 当基线。**

    变异测试是在有正常工作改动的工作区里做的，那些改动本身就在 diff 里。
    用 HEAD 当基线会把「我今天写的代码」误判成「变异没还原干净」——
    实测踩过：文件已正确还原，检查却红了。
    """
    subprocess.run(["git", "init", "-q"], cwd=sandbox, check=True)
    subprocess.run(["git", "add", "-A"], cwd=sandbox, check=True)
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t",
                    "commit", "-qm", "init"], cwd=sandbox, check=True)
    # 一次**正常**的工作改动（不是变异）
    (sandbox / TARGET).write_text(
        (sandbox / TARGET).read_text() + "\n\ndef extra():\n    return 1\n")
    before = snapshot(TARGET, root=sandbox)
    assert_restored(TARGET, before, root=sandbox)   # 不该误报


def test_copy_and_restore_context_manager_reverts_on_error(sandbox):
    before = snapshot(TARGET, root=sandbox)
    with pytest.raises(RuntimeError):
        with copy_and_restore(TARGET, root=sandbox) as f:
            f.write_text("全乱了")
            raise RuntimeError("中途炸了")
    assert_restored(TARGET, before, root=sandbox)
