"""`scripts/gate_alembic_check.py` 的测试 —— 它唯一的产出是「一个退出码」。

沿用 `test_run_gate.py` 的形状（TODO-050）：断言的是**码与文案**，
因为失效模式是沉默的假绿 —— 守门红了却被报成通过。

三条分支各有根断言：正常 / 漂移 / 「守门没跑」/ 连不上。
"""
from __future__ import annotations

import pytest

from scripts.gate_alembic_check import main


def _runner(rc: int, out: str):
    """假 runner：跳过真 alembic，直接返回预设 (退出码, 输出)。"""
    return lambda argv, *, cwd=None: (rc, out)


def test_passing_db_exits_zero():
    assert main(runner=_runner(0, "No new upgrade operations detected")) == 0


def test_real_drift_is_blocked():
    """根断言：漂移（rc 非 0）→ 阻断，且**不**因 rc 是 255 而放过。"""
    out = "Detected removal of column 'pp5_probe_col' on table 'workspaces'"
    assert main(runner=_runner(255, out)) == 1


def test_stale_revision_is_blocked_not_reported_as_pass():
    """守门没跑 ≠ 通过 —— CLAUDE.md 点名的假绿来源。"""
    assert main(runner=_runner(255, "Target database is not up to date")) == 1


def test_unreachable_db_warns_but_allows():
    """DB 不在就拦下所有 commit，会训练出「一律 --no-verify」，那等于没有闸门。"""
    out = "sqlalchemy.exc.OperationalError: connection refused"
    assert main(runner=_runner(1, out)) == 0


@pytest.mark.parametrize("rc", [1, 2, 124, 127, 255])
def test_every_nonzero_code_is_a_failure_not_a_pass(rc):
    """非 0 一律失败：闸门不比较具体码值。"""
    assert main(runner=_runner(rc, "some drift output")) == 1


def test_invokes_alembic_check_from_the_backend_dir():
    seen: dict = {}

    def runner(argv, *, cwd=None):
        seen["argv"], seen["cwd"] = argv, cwd
        return 0, "ok"

    main(runner=runner)
    assert seen["argv"] == ["uv", "run", "alembic", "check"]
    assert seen["cwd"].endswith("pcs-backend")
