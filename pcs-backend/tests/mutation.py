"""变异测试的元断言工具（用户 2026-10-09 审查引入；2026-10-13 扩充）。

## 为什么需要它

变异测试自己也会**假绿**，而且是最阴的一种：变异**根本没应用上**，
于是测试套件原样通过，看起来像「测试抓住了这个变异」，其实什么都没发生。

实际踩过一次：把

    rejected.append(f"{path}（无法解析：{type(e).__name__}）")
    continue

改成 `raise`，因为手写的 `old` 字符串和文件里的实际内容差了一个字符，
`str.replace` 静默返回原串 —— 变异是**空操作**，测试全绿。
若当时没多问一句「变异到底应用上没有」，就会把一条假绿的验证写进提交信息。

## **三种**失败必须能区分（TODO-048 补齐了后两种）

| 失败 | 谁负责拦 | 工具 |
|---|---|---|
| 变异没应用 | `mutate` 的 `assert old in source` | ✅ 已有 |
| 变异应用了但**测试没抓到** | `expect_killed` | ✅ 本轮补 |
| 测试**本来就红**（基线不绿） | `expect_killed` 的基线检查 | ✅ 本轮补 |

第三条最容易被忽略：一个**恒红**的测试能「杀掉」任何变异 ——
变异测试报告「100% 变异被杀死」，而真相是那个测试压根不绿。
所以 `expect_killed` 在施加变异**之前**先跑一次基线，基线不绿就报错。

## 用法

    from tests.mutation import mutate, expect_killed

    # 只想改字符串：
    src = mutate(Path("app/x.py").read_text(), "OLD", "NEW")

    # 想证明「某个测试确实能抓住这个变异」（会真的写文件、跑 pytest、还原）：
    expect_killed(
        rel_path="app/x.py",
        old="raise REPORT_QUEUE_UNAVAILABLE",
        new="return None",
        test_ids=["tests/api/v1/test_x.py::test_enqueue_failure_is_503"],
    )

⚠️ `expect_killed` **会真的改磁盘上的文件**。它保证还原（`finally`），
但如果进程被 kill -9，文件会留在变异态 —— 所以它不适合在 CI 里跑。

⚠️ `mutate` 只保证 old 存在且至少替换一处。若 old 在文件里出现多次，
`str.replace` 会全换 —— 想只换一处就把上下文一起传进 old，
或用 `mutate_count`。
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def mutate(source: str, old: str, new: str) -> str:
    """替换并**断言目标确实存在**。

    Raises:
        AssertionError: `old` 不在 `source` 里 —— 变异是空操作，后续的绿灯无意义。
    """
    assert old in source, (
        f"变异目标未找到，变异是空操作：{old!r}\n"
        f"文件实际内容可能已变（格式化 / 重构 / 上一轮已改过）。"
        f"不要把「测试仍然全绿」当成「测试抓住了变异」。"
    )
    return source.replace(old, new)


def mutate_count(source: str, old: str, new: str, expected: int = 1) -> str:
    """同 `mutate`，但额外校验替换次数 —— 多处命中时用这个。"""
    assert old in source, f"变异目标未找到：{old!r}"
    actual = source.count(old)
    assert actual == expected, f"目标出现 {actual} 次，期望 {expected} 次：{old!r}"
    return source.replace(old, new)


def _run_pytest(test_ids: list[str], cwd: Path) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "pytest", *test_ids, "-q", "--no-header", "-x"],
        cwd=cwd, capture_output=True, text=True, timeout=600,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    )


def expect_killed(*, rel_path: str, old: str, new: str, test_ids: list[str],
                  root: Path | None = None) -> None:
    """证明 `test_ids` **确实能抓住**某个变异。

    三步，缺一不可：

    1. **基线必须绿**（不施加变异跑一次）。基线红 → 报错。
       否则一个恒红的测试能「杀掉」任何变异，报告全是假的。
    2. **施加变异并确认落盘**。落盘后再读一次比对 ——
       `mutate` 只保证字符串层替换成功，磁盘层仍可能没写对。
    3. **重跑测试，必须红**。还绿 = 测试没抓到，登记 TODOS.md。

    文件在 `finally` 里还原；还原后再校验一次磁盘内容与备份一致。

    Raises:
        AssertionError: 基线不绿 / 变异没落盘 / 测试仍然全绿 / 还原失败。
    """
    repo = Path(root) if root else REPO_ROOT
    target = repo / rel_path
    assert target.exists(), f"待变异文件不存在：{target}"
    assert test_ids, "test_ids 不能为空 —— 那样任何变异都会被「杀掉」"

    original = target.read_text()
    backup = original

    # --- 1. 基线必须绿 -------------------------------------------------------
    baseline = _run_pytest(test_ids, repo)
    assert baseline.returncode == 0, (
        f"基线不绿，无法证明变异被抓住。\n"
        f"指定测试在**未变异**时就失败 —— 那么它会「杀掉」任何变异，"
        f"报告全绿是假的。\n{baseline.stdout[-2000:]}\n"
        f"先修好基线，或换一个真正覆盖该行为的测试。"
    )

    try:
        # --- 2. 施加变异并确认落盘 -------------------------------------------
        mutated = mutate(original, old, new)
        target.write_text(mutated)
        on_disk = target.read_text()
        assert on_disk != original, "变异写回了但内容与原始相同 —— 变异是空操作"
        assert old not in on_disk or old == new, (
            f"变异目标 {old!r} 施加后仍在文件里 —— 替换没有真正生效")

        # --- 3. 必须红 --------------------------------------------------------
        killed = _run_pytest(test_ids, repo)
        assert killed.returncode != 0, (
            f"变异已施加，但指定测试**仍然全绿** —— 测试没抓到它。\n"
            f"测试：{test_ids}\n"
            f"变异：{old!r} → {new!r}\n"
            f"这是真实缺口：要么测试没覆盖这条行为（补测试），"
            f"要么变异选错了目标（换一个真正会改变行为的地方）。"
        )
    finally:
        target.write_text(backup)
        restored = target.read_text()
        assert restored == original, (
            f"⚠️ 还原失败：{rel_path} 仍处于变异态。"
            f"用 git diff 检查并手动恢复。")


def snapshot(rel_path: str, root: Path | None = None) -> str:
    """取文件当前内容 —— 作为「变异前」的基线快照。

    ⚠️ **不要拿 `git diff` 当基线**。变异测试是在**有正常工作改动**的
    工作区里做的（这正是你要边写边验的场景），那些改动本身就在 diff 里。
    用 HEAD 当基线会把「我今天改的代码」误判成「变异没还原干净」——
    这个误报实测踩过：文件明明已正确还原，`assert_restored` 却红了。

    所以基线是**进入时读到的内容**，不是 git 历史。
    """
    repo = Path(root) if root else REPO_ROOT
    return (repo / rel_path).read_text()


def assert_restored(rel_path: str, before: str, root: Path | None = None) -> None:
    """确认文件已回到 `snapshot()` 取到的内容。"""
    repo = Path(root) if root else REPO_ROOT
    target = repo / rel_path
    after = target.read_text()
    assert after == before, (
        f"⚠️ {rel_path} 仍处于变异态（与变异前的内容不一致）。"
        f"用 git diff 查看残留。")


def copy_and_restore(rel_path: str, root: Path | None = None):
    """上下文管理器：进入时备份、退出时还原并校验。手工跑变异时用。

    比 `expect_killed` 轻量：只管还原，不跑测试、不查基线绿不绿。
    """
    from contextlib import contextmanager

    @contextmanager
    def _cm():
        repo = Path(root) if root else REPO_ROOT
        target = repo / rel_path
        before = target.read_text()
        try:
            yield target
        finally:
            target.write_text(before)
            assert target.read_text() == before, (
                f"⚠️ {rel_path} 还原失败")

    return _cm()
