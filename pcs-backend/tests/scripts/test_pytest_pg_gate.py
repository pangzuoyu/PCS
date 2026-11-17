"""scripts/pytest_pg.sh 的 fail-closed 行为（T0 · TODO-099 · 裁决 4 约束 1）。

## 为什么这个文件存在

「一键脚本」如果没有**强制力**，等于没有 —— 没人跑就等于没做。
委员会的三条硬约束里第一条就是「**fail-closed**」：
PG 没起 ⇒ FAIL；收集到 0 个 PG 测试 ⇒ FAIL；测试被全 skip ⇒ FAIL。
⇒ 这三条必须**有测试**，否则「脚本写了但没人跑」与「脚本不存在」不可区分
（同 `docs/solutions/testing-issues/guard-test-fooled-by-lying-comment.md`）。
"""
from __future__ import annotations

import os
import subprocess
import tempfile
import time
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pytest_pg.sh"


def _run(env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    # ⚠️ **车道锁用独立文件**（P10-B · T7 · bug-2170）：
    # `pytest_pg.sh` 有「车道互斥锁」（PG 车道与 E2E 车道共用同一个库）
    # ⇒ ⇒ **真车道在跑时**，这些守门测试会被锁挡住 ⇒ 报的是
    # 「另一条车道正在跑」⇒ ⇒ **测的根本不是它们声称的那条闸门**
    # ⇒ ⇒ 守门测试必须用**自己的**锁文件（脚本支持 `PCS_PGTEST_LANE_LOCK` 覆盖）。
    lock_file = env_extra.get(
        "PCS_PGTEST_LANE_LOCK",
        str(Path(tempfile.gettempdir()) / f"pcs-pgtest-gate-{os.getpid()}.lock"),
    )
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env={**os.environ, "PCS_PGTEST_LANE_LOCK": lock_file, **env_extra},
        capture_output=True,
        text=True,
        timeout=120,
    )


def test_script_exists_and_is_executable():
    assert SCRIPT.exists(), "PG 车道入口脚本不存在"
    assert os.access(SCRIPT, os.X_OK), "脚本不可执行"


def test_fails_when_pg_instance_is_not_running():
    """PG 实例没起 ⇒ 非零退出 + 明确提示（不是「跳过」）。"""
    r = _run({"PG_COMPOSE_PROJECT": "pcs_pg_absent_project"})
    assert r.returncode != 0, "PG 没起却退出 0 ⇒ 假绿"
    assert "docker compose --profile pg up -d" in (r.stdout + r.stderr)


def test_fails_when_zero_pg_tests_are_collected(tmp_path):
    """收集到 0 个 PG 测试 ⇒ 非零退出（「收集到 0 个」不是「通过」）。

    ⚠️ **必须让 PG 检查通过**才能测到这条分支 —— 否则脚本在「PG 没起」那步就
    退出，这条测试实际测的是「PG 没起」而不是「收集到 0 个」
    （`guard-test-fooled-by-lying-comment` 同形：守卫测的不是它声称的东西）。

    ⇒ 用**假的 docker**（PATH 前置一个 shim，输出 `postgres-pgtest running`）
    让第 ① 步通过。
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_docker = fake_bin / "docker"
    fake_docker.write_text("#!/bin/sh\necho 'postgres-pgtest running'\nexit 0\n")
    fake_docker.chmod(0o755)

    r = _run({
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "PG_PYTEST_MARK": "no_such_marker_xyz",
    })
    assert r.returncode != 0
    assert "收集到 0 个 PG 测试" in (r.stdout + r.stderr)


def test_fails_when_all_pg_tests_are_skipped(tmp_path):
    """⚠️ 收集到了但**全部 skip** ⇒ 非零退出（第三条 fail-closed 闸）。

    ⚠️ 这条与「收集到 0 个」**不是同一件事**：前者说明 marker 选中了用例、
    但它们没真跑（PG 起了但环境不满足 ⇒ `pytest.skip`）⇒ 与「PG 没起」
    **无法区分** ⇒ 必须单独非零退出（委员会裁决 4 约束 1 的第三条）。

    ⇒ 用**假的 docker**（让第 ① 步通过）+ **假的 uv**（收集报 3 个、
    正式跑报 3 skipped）走到第 ③ 条闸。
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "docker").write_text("#!/bin/sh\necho 'postgres-pgtest running'\nexit 0\n")
    (fake_bin / "uv").write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        "  *--collect-only*) echo '3 tests collected in 0.01s' ;;\n"
        "  *) echo '3 skipped in 0.02s' ;;\n"
        "esac\n"
        "exit 0\n"
    )
    for name in ("docker", "uv"):
        (fake_bin / name).chmod(0o755)

    r = _run({"PATH": f"{fake_bin}:{os.environ['PATH']}"})
    assert r.returncode != 0, "全部 skip 却退出 0 ⇒ 假绿"
    assert "没有实际执行任何测试" in (r.stdout + r.stderr)


def test_fails_when_some_pg_tests_are_skipped(tmp_path):
    """⚠️ **部分** skip ⇒ 也必须非零退出（P10-B 评审 #16 · P1）。

    ⚠️ 原先第 ③ 条闸只要求「**≥1 passed**」⇒ ⇒ 「30 条里跑 1 条、29 条被
    skip」也算**绿** ⇒ ⇒ 车道绿灯**不携带信息**（这正是「验证机制的失败模式
    是假绿」）。

    ⇒ ⇒ 用**假的 docker**（第 ① 步通过）+ **假的 uv**（收集报 3 个、
    正式跑报「2 passed, 1 skipped」）走到第 ③ 条闸。
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "docker").write_text("#!/bin/sh\necho 'postgres-pgtest running'\nexit 0\n")
    (fake_bin / "uv").write_text(
        "#!/bin/sh\n"
        'case "$*" in\n'
        "  *--collect-only*) echo '3 tests collected in 0.01s' ;;\n"
        "  *) echo '2 passed, 1 skipped in 0.02s' ;;\n"
        "esac\n"
        "exit 0\n"
    )
    for name in ("docker", "uv"):
        (fake_bin / name).chmod(0o755)

    r = _run({"PATH": f"{fake_bin}:{os.environ['PATH']}"})
    assert r.returncode != 0, "有测试被 skip 却退出 0 ⇒ 假绿"
    assert "skip" in (r.stdout + r.stderr)


def test_script_does_not_teach_a_second_entry_point():
    """⚠️ 唯一入口：脚本里不得出现「直接 DATABASE_URL=... pytest」的第二条路。"""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "pytest -m pg" in body
    # 不得在脚本里另起一条不经脚本的 pytest 调用路径（注释里说明允许）
    assert body.count("uv run pytest") == 2, (
        "脚本里应只有「收集计数」与「正式执行」两次 pytest 调用；"
        "多出来的说明有人加了第二条路径"
    )


def test_default_lock_path_is_inside_the_project_not_tmp():
    """⚠️ **默认锁路径在项目内**（P10-B 评审 #15 第 ② 步）。

    ⇒ `/tmp` 会被**清理**（tmpfs / 重启）⇒ ⇒ 锁文件 inode 换新 ⇒ ⇒
    ⇒ 正在跑的车道的锁对新车道**不可见** ⇒ ⇒ 互斥**静默失效** ⇒ ⇒
    ⇒ 默认路径必须是项目内的 `.tmp/lane.lock`。
    """
    body = SCRIPT.read_text(encoding="utf-8")
    assert "/tmp/pcs-pgtest-lane.lock" not in body, (
        "默认锁路径还在 /tmp ⇒ 清理后 inode 换新 ⇒ 互斥静默失效（评审 #15）"
    )
    assert ".tmp/lane.lock" in body, (
        "默认锁路径应是项目内的 .tmp/lane.lock（评审 #15）"
    )


def test_two_lanes_are_mutually_exclusive_on_the_default_path(tmp_path):
    """⚠️ **默认路径**下两条车道**真的互斥**（P10-B 评审 #15 第 ③ 步）。

    ⇒ 之前只测过「覆盖过的锁文件」（守门测试自己那份）⇒ ⇒ **默认路径
    ⇒ 从没被测过** ⇒ ⇒ 「默认路径也有效」只能靠读代码 ⇒ ⇒ 这里**实测**。

    ⇒ 做法：起一个**占着锁**的进程（`flock -n` 同一路径 + sleep）⇒ ⇒
    ⇒ 再跑车道脚本 ⇒ ⇒ 它必须因为「另一条车道正在跑」而失败。

    ⚠️ **第 ① 步（PG 实例起着）要用假 docker 顶掉** ⇒ ⇒ 否则失败理由会是
    「PG 实例未起」⇒ ⇒ 测的不是互斥（与本文件其它守卫测试同款做法）。
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "docker").write_text("#!/bin/sh\necho 'postgres-pgtest running'\nexit 0\n")
    (fake_bin / "docker").chmod(0o755)

    lock_file = tmp_path / "lane.lock"
    holder = subprocess.Popen(
        ["flock", "-n", str(lock_file), "sleep", "30"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # 等 holder 真的拿到锁（否则测的是「锁没人占」）
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            probe = subprocess.run(
                ["flock", "-n", str(lock_file), "true"],
                capture_output=True,
                text=True,
            )
            if probe.returncode != 0:
                break
            time.sleep(0.1)
        else:  # pragma: no cover — 环境异常
            pytest.fail("占锁进程没拿到锁 ⇒ 测不了互斥")

        result = _run(
            {
                "PCS_PGTEST_LANE_LOCK": str(lock_file),
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
            }
        )
        assert result.returncode != 0, (
            "锁被占着却跑通了 ⇒ 两条车道**不互斥** ⇒ 并发建 schema ⇒ DDL 互相等锁"
        )
        assert "另一条车道" in (result.stdout + result.stderr), (
            f"失败理由不是「另一条车道正在跑」⇒ 测的不是互斥："
            f"{(result.stdout + result.stderr)[:300]}"
        )
    finally:
        holder.terminate()
        holder.wait(timeout=10)
