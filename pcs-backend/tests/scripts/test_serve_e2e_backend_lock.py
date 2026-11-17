"""真后端通道的**后端**也要进车道锁（P10-F · 整支评审 I3）。

## 为什么要有这个测试

⚠️ 真后端通道的后端（`scripts/serve_e2e_backend.sh`）**写 public schema**
（建项目 / 物流 / 审计行）⇒ ⇒ 而 E2E 车道的守卫断言「public 在车道期间
**一字未改**」⇒ ⇒ 两者**并发** ⇒ ⇒ 守卫**误红** ⇒ ⇒ 而文案把锅甩给
E2E 车道（「隔离失效」）⇒ ⇒ 排查方向被带偏。

⇒ ⇒ 与 PG / E2E 两条车道**同一把锁**（同一路径口径）⇒ ⇒
「别同时跑」是**机制**，不是一句叮嘱（计划 Global Constraints 原话）。

⚠️ **断法**：静态断**可执行部分**（`lane_script_body` ⇒ 一处真相源）
⇒ ⇒ 断**机制**（`flock -n` + `exec 9>`）而不只是「路径字符串」
⇒ ⇒ 加一条**行为**测试（真占锁 ⇒ 脚本必须失败）⇒ ⇒ 只断文本等于没断。
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest

from tests.scripts.lane_script_body import lane_script_body

#: 后端目录（`tests/scripts/` → `tests/` → `pcs-backend/`）。
BACKEND = Path(__file__).resolve().parents[2]
SERVE_SCRIPT = BACKEND / "scripts" / "serve_e2e_backend.sh"


def test_serve_script_takes_the_lane_lock_before_serving() -> None:
    """⚠️ **锁必须在起服之前抢** ⇒ ⇒ 断**顺序**，不是断「有没有锁」。"""
    body = lane_script_body(SERVE_SCRIPT)
    assert "lane.lock" in body, (
        "真后端的后端没抢车道锁 ⇒ 与 E2E 车道并发 ⇒ public 守卫误红"
    )
    assert "flock -n" in body, "车道锁必须是**非阻塞**版（-n）⇒ 否则并发时排队卡住"
    assert "exec 9>" in body, "必须锁住 fd 9 ⇒ 整个脚本生命周期都持锁"
    assert body.index("lane.lock") < body.index("uvicorn"), (
        "锁必须在起服**之前**抢 ⇒ 否则已经写了几轮 public 才发现自己撞了锁"
    )


def test_serve_script_fails_when_the_lane_lock_is_held(tmp_path) -> None:
    """⚠️ **抢不到锁 ⇒ 非零退出**且说清「另一条车道在跑」⇒ ⇒ 只断文本等于没断。

    ⇒ ⇒ 照 `tests/scripts/test_compose_test_profile.py` 的现成做法：
    **假 uv**（万一脚本走到了起服那步，它 exit 0 而不是真的起服）
    + **真占锁进程**。
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "uv").write_text("#!/bin/sh\necho 'fake uv'\nexit 0\n")
    (fake_bin / "uv").chmod(0o755)

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

        r = subprocess.run(
            ["bash", str(SERVE_SCRIPT)],
            env={
                **os.environ,
                "PATH": f"{fake_bin}:{os.environ['PATH']}",
                # ⚠️ **用自己的锁文件** ⇒ 免得与真车道抢同一把锁
                # （`docs/solutions/testing-issues/guard-test-must-use-its-own-lane-lock.md`）
                "PCS_PGTEST_LANE_LOCK": str(lock_file),
            },
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert r.returncode != 0, "锁被占着却跑通了 ⇒ 真后端后端与车道不互斥"
        assert "另一条车道" in (r.stdout + r.stderr), (
            f"失败理由不是「另一条车道正在跑」⇒ 测的不是互斥："
            f"{(r.stdout + r.stderr)[:300]}"
        )
        assert "fake uv" not in (r.stdout + r.stderr), (
            "锁没抢到就已经起服了 ⇒ 锁的顺序错了"
        )
    finally:
        holder.terminate()
        holder.wait(timeout=10)
