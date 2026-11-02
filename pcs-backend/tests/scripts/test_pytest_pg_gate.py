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
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "pytest_pg.sh"


def _run(env_extra: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(SCRIPT)],
        cwd=SCRIPT.parents[1],
        env={**os.environ, **env_extra},
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


def test_script_does_not_teach_a_second_entry_point():
    """⚠️ 唯一入口：脚本里不得出现「直接 DATABASE_URL=... pytest」的第二条路。"""
    body = SCRIPT.read_text(encoding="utf-8")
    assert "pytest -m pg" in body
    # 不得在脚本里另起一条不经脚本的 pytest 调用路径（注释里说明允许）
    assert body.count("uv run pytest") == 2, (
        "脚本里应只有「收集计数」与「正式执行」两次 pytest 调用；"
        "多出来的说明有人加了第二条路径"
    )
