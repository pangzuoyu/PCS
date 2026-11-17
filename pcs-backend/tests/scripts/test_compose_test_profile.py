"""`docker-compose.yml` 的 **test profile** 守卫（P10-A · Task T1）。

为什么要有这个测试：compose 的 profile 语义是**静默**的 ——
给一个服务加了 `profiles:` ⇒ `docker compose up` **不再起它** ⇒
症状是「开发机连不上 Redis / LDAP」，而 compose 本身不报错。
⇒ 这里把「哪些服务能进 profile、哪些绝对不能」钉成断言。

⚠️ **日常开发服务绝不加 profile**（worker / openldap / postgres / redis）
   —— 它们是 `docker compose up` 的默认启动集合，加了 profile 等于
   悄悄改了既有开发流程。
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml

from tests.scripts.lane_script_body import lane_script_body

#: 仓库根（tests/scripts/ → tests/ → pcs-backend/ → 根）
REPO_ROOT = Path(__file__).resolve().parents[3]
#: 后端目录（`scripts/` 与 `tests/` 的父目录）。
BACKEND = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"

#: 日常开发必用的服务 —— **不得**进任何 profile。
DAILY_DEV_SERVICES = ("postgres", "redis", "worker", "openldap", "openldap-seed")


@pytest.fixture(scope="module")
def compose() -> dict:
    """解析 compose 文件（module 级 ⇒ 只解析一次）。"""
    if not COMPOSE_FILE.exists():  # pragma: no cover — 仓库结构变了
        pytest.fail(f"找不到 {COMPOSE_FILE}")
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


def _services(compose: dict) -> dict:
    return compose.get("services") or {}


def test_seed_service_is_in_the_test_profile(compose: dict) -> None:
    """`seed` 在 `profiles: ["test"]` 下 ⇒ 默认 `docker compose up` **不**起它。

    ⚠️ 它是**一次性任务**（灌 E2E 种子数据）⇒ 默认启动只会白等一次。
    """
    services = _services(compose)
    assert "seed" in services, "compose 里没有 `seed` 服务"
    assert "test" in (services["seed"].get("profiles") or [])


def test_seed_service_mounts_the_backend_source(compose: dict) -> None:
    """⚠️ **seed 必须挂源码卷**（`./pcs-backend:/app`）
    —— 否则容器里没有 `scripts/seed_e2e_data.py` ⇒ 立刻 FileNotFoundError。
    """
    volumes = _services(compose)["seed"].get("volumes") or []
    mounts = [v if isinstance(v, str) else v.get("source", "") for v in volumes]
    assert any("pcs-backend" in m for m in mounts), f"seed 没挂源码：{volumes}"


def test_seed_uses_the_frozen_uv_entrypoint(compose: dict) -> None:
    """⚠️ 与 `worker` 同款：`uv run --frozen`（不是裸 `python`）
    ⇒ 依赖由 uv 装好，且版本与本地一致。

    ⚠️ 裸 `python` 在 uv 官方镜像里**没有**项目依赖 ⇒ 立刻 ModuleNotFoundError。
    """
    command = _services(compose)["seed"].get("command") or []
    joined = " ".join(command) if isinstance(command, list) else str(command)
    assert "uv" in joined and "run" in joined and "--frozen" in joined, joined
    assert "scripts/seed_e2e_data.py" in joined, joined


def test_seed_depends_only_on_services_reachable_with_the_test_profile(
    compose: dict,
) -> None:
    """⚠️ **depends_on 的每个依赖都要在 `--profile test` 下可达**
    ⇒ `postgres-pgtest` 的 profiles 必须含 "test"
    （否则 `--profile test` 起不出 seed —— compose 不会隐式启动
    不在启用 profile 内的服务）。

    没有 `profiles` 的服务 = **默认启动集合** ⇒ 永远可达。
    """
    services = _services(compose)
    for dep in (services["seed"].get("depends_on") or {}):
        assert dep in services, f"seed 依赖了不存在的服务 {dep}"
        profiles = services[dep].get("profiles") or []
        assert (not profiles) or ("test" in profiles), (
            f"seed 依赖 {dep}，但它的 profiles={profiles} 不含 'test'"
            f" ⇒ `--profile test` 起不出 seed"
        )


def test_seed_points_at_the_pgtest_database(compose: dict) -> None:
    """⚠️ seed 连的是 `postgres-pgtest` 的库 **`pcs_pgtest`**（不是 `pcs_test`）。

    连错库的后果：种子数据灌进**开发库** ⇒ 污染开发数据。
    """
    env = _services(compose)["seed"].get("environment") or {}
    url = env.get("DATABASE_URL", "")
    assert "postgres-pgtest" in url, url
    assert "pcs_pgtest" in url, url


def test_daily_dev_services_are_not_moved_into_a_profile(compose: dict) -> None:
    """⚠️ **worker / openldap / postgres / redis 必须留在默认启动集合**
    ⇒ 加了 profile 会让 `docker compose up` 不再起它们 ⇒ 破坏日常开发。
    """
    services = _services(compose)
    for name in DAILY_DEV_SERVICES:
        assert name in services, f"compose 里没有 {name} 服务"
        assert not services[name].get("profiles"), (
            f"{name} 被移进 profile {services[name]['profiles']}"
            f" ⇒ `docker compose up` 不再起它 ⇒ 破坏日常开发"
        )


def test_migrate_service_is_in_the_test_profile(compose: dict) -> None:
    """⚠️ **迁移**也得在 test profile 里（评审 H-2）。

    ⇒ 测试库（`pcs_pgtest`）的 schema 由它升到 head ⇒
    `seed` 才有表可写（否则 `relation "workspaces" does not exist`）。
    """
    services = _services(compose)
    assert "migrate" in services, "compose 里没有 `migrate` 服务"
    assert "test" in (services["migrate"].get("profiles") or [])


def test_seed_runs_after_migrate(compose: dict) -> None:
    """⚠️ `seed` 必须**等迁移完成** ⇒ 空 schema 上灌种子必然炸。"""
    services = _services(compose)
    depends = services["seed"].get("depends_on") or {}
    assert "migrate" in depends, depends
    assert depends["migrate"].get("condition") == "service_completed_successfully", depends


def test_migrate_points_at_the_pgtest_database(compose: dict) -> None:
    """⚠️ 迁移连的必须是**测试库** `pcs_pgtest`（不是开发库 `pcs`）。

    连错 ⇒ **污染开发库**。
    """
    env = _services(compose)["migrate"].get("environment") or {}
    url = env.get("DATABASE_URL", "")
    assert "postgres-pgtest" in url, url
    assert "pcs_pgtest" in url, url


# ---------------------------------------------------------------------------
# 车道互斥锁（P10-F · F2-T3 · 评审 #15 第 ① 步）
# ---------------------------------------------------------------------------


def test_compose_test_stack_takes_the_lane_lock_before_invoking_compose() -> None:
    """⚠️ **测试栈也要进车道锁** —— 它建 schema / 跑迁移 / 灌种子 ⇒ ⇒ 与
    PG 车道 / E2E 车道**写同一个库** ⇒ ⇒ 并发 ⇒ ⇒ DDL 互相等锁 ⇒ ⇒
    表现是「**偶发卡住**」（不是报错 ⇒ 极难定位）。

    ⇒ ⇒ 锁必须在**调 compose 之前**抢 ⇒ ⇒ 断**顺序**，不是断「有没有锁」。
    """
    body = lane_script_body(BACKEND / "scripts" / "compose_test_stack.sh")
    assert "lane.lock" in body, "起测试栈的脚本没抢车道锁 ⇒ 与车道并发 ⇒ DDL 等锁"
    # ⚠️ **断「锁机制」而不只是「路径字符串」** —— 只断 `lane.lock` ⇒ ⇒
    # ⇒ 把 `flock -n` / `exec 9>` 删掉（**留下路径变量**）也照样绿
    # ⇒ ⇒ 那正是「声明了但没做」的病（同 `guard-test-fooled-by-lying-comment`）。
    assert "flock -n" in body, "车道锁必须是**非阻塞**版（-n）⇒ 否则并发时排队卡住"
    assert "exec 9>" in body, "必须锁住 fd 9 ⇒ 整个脚本生命周期都持锁"
    assert body.index("lane.lock") < body.index("docker compose"), (
        "锁必须在调 compose **之前**抢 ⇒ 否则已经建了 schema 才发现自己撞了锁"
    )


def test_compose_test_stack_fails_when_the_lane_lock_is_held(tmp_path) -> None:
    """⚠️ **抢不到锁 ⇒ 非零退出**且说清「另一条车道在跑」⇒ ⇒ 只断文本等于没断。

    ⇒ ⇒ 照 `tests/scripts/test_pytest_pg_gate.py` 的现成做法：**假 docker**
    （让第 ① 步不会因为「PG 起不来」而失败）+ **真占锁进程**。
    """
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    (fake_bin / "docker").write_text("#!/bin/sh\necho 'fake'\nexit 0\n")
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

        r = subprocess.run(
            ["bash", str(BACKEND / "scripts" / "compose_test_stack.sh")],
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
        assert r.returncode != 0, "锁被占着却跑通了 ⇒ 两条车道不互斥"
        assert "另一条车道" in (r.stdout + r.stderr), (
            f"失败理由不是「另一条车道正在跑」⇒ 测的不是互斥："
            f"{(r.stdout + r.stderr)[:300]}"
        )
    finally:
        holder.terminate()
        holder.wait(timeout=10)
