"""compose **容器侧**车道锁的守卫（P10-C · T0-3 · TODO-163）。

## 缺陷是什么

`scripts/pytest_pg.sh`（PG 车道）与 `scripts/compose_test_stack.sh`（测试栈）
都在**宿主侧**抢 `pcs-backend/.tmp/lane.lock` ⇒ ⇒ 同一个库不能并发建 schema。
⇒ ⇒ 但**直接** `docker compose run --rm seed` **绕过**宿主脚本
⇒ ⇒ ⇒ 那就能与跑着的车道**并发** ⇒ ⇒ DDL 互相等锁
⇒ ⇒ ⇒ 表现是「**偶发卡住**」（不是报错 ⇒ 极难定位）。

⇒ ⇒ 修法：容器**自己也抢**同一把锁（同一路径 ⇒ ⇒ 同一 inode
⇒ ⇒ bind mount 进去 ⇒ ⇒ 宿主与容器**互斥**）。

## 本文件断什么

① **静态**（compose yaml）：`migrate` / `seed` 都走锁脚本 ·
   锁目录挂载**可写**（`:ro` ⇒ ⇒ 容器开不了锁 ⇒ ⇒ 互斥失效）·
   镜像**自建**（uv 官方镜像里**没有** `flock`）
② **脚本行为**（真跑 `sh`）：锁空闲 ⇒ ⇒ 正常执行 ·
   **锁被占** ⇒ ⇒ 非零退出 · `PCS_LANE_LOCK_HELD=1` ⇒ ⇒ 放行（宿主自持锁）
③ **Dockerfile**：装 `util-linux`（`flock` 的来源）
④ **容器实测**（`docker` 标记 · 默认 deselect）：镜像里有 `flock` ·
   容器在锁被占时**拒绝**执行
"""
from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path

import pytest
import yaml

#: 仓库根（tests/scripts/ → tests/ → pcs-backend/ → 根）
REPO_ROOT = Path(__file__).resolve().parents[3]
#: 后端目录（`scripts/` 与 `tests/` 的父目录）。
BACKEND = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "docker-compose.yml"
LOCK_SCRIPT = BACKEND / "scripts" / "compose_lane_lock.sh"
DOCKERFILE = BACKEND / "Dockerfile"
IMAGE_NAME = "pcs-backend:local"

#: 要抢锁的一次性写者。
WRITE_SERVICES = ("migrate", "seed")


@pytest.fixture(scope="module")
def compose() -> dict:
    if not COMPOSE_FILE.exists():  # pragma: no cover — 仓库结构变了
        pytest.fail(f"找不到 {COMPOSE_FILE}")
    return yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# ① 静态：compose 层
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("service", WRITE_SERVICES)
def test_write_services_go_through_the_lane_lock_script(compose, service: str) -> None:
    """⚠️ 一次性写者**必须**经锁脚本 ⇒ ⇒ 否则容器侧抢不到锁。"""
    svc = compose["services"][service]
    command = " ".join(str(part) for part in svc.get("command", []))
    assert "compose_lane_lock.sh" in command, (
        f"{service} 的 command 没走锁脚本：{command!r}"
        f" ⇒ ⇒ 容器侧**抢不到锁** ⇒ ⇒ 直接 `docker compose run --rm {service}`"
        f" 仍能绕过宿主锁 ⇒ ⇒ 洞没闭上"
    )


@pytest.mark.parametrize("service", WRITE_SERVICES)
def test_lock_directory_is_mounted_writable(compose, service: str) -> None:
    """⚠️ **锁目录必须可写** ⇒ ⇒ `:ro` ⇒ ⇒ 容器开不了锁 ⇒ ⇒ 互斥失效。"""
    svc = compose["services"][service]
    volumes = [str(v) for v in svc.get("volumes", [])]
    lock_mounts = [v for v in volumes if ".tmp" in v]
    assert lock_mounts, (
        f"{service} 没有挂 `.tmp` 目录 ⇒ ⇒ 容器用的锁文件"
        f"**不是**宿主那一个 ⇒ ⇒ 两边各锁各的 ⇒ ⇒ 互斥失效"
    )
    for mount in lock_mounts:
        assert ":ro" not in mount, (
            f"{service} 的锁目录挂载是**只读**的：{mount!r}"
            f" ⇒ ⇒ 容器开不了锁 ⇒ ⇒ 互斥失效"
        )


@pytest.mark.parametrize("service", WRITE_SERVICES)
def test_services_use_the_self_built_image(compose, service: str) -> None:
    """⚠️ 镜像**必须自建** ⇒ ⇒ uv 官方镜像里**没有** `flock`。"""
    svc = compose["services"][service]
    assert svc.get("image") == IMAGE_NAME, (
        f"{service} 的 image 是 {svc.get('image')!r} ⇒ ⇒ 不是自建镜像"
        f" ⇒ ⇒ 容器里**没有 flock** ⇒ ⇒ 抢不到锁"
    )
    assert svc.get("build"), f"{service} 没有 build 段 ⇒ ⇒ 镜像不会自动构建"


# ---------------------------------------------------------------------------
# ② 脚本行为（真跑 `sh`）
# ---------------------------------------------------------------------------


def _run_locked(cmd: list[str], lock_file: Path, **env_extra: str) -> subprocess.CompletedProcess:
    env = {**os.environ, "PCS_LANE_LOCK": str(lock_file), **env_extra}
    return subprocess.run(
        ["sh", str(LOCK_SCRIPT), *cmd],
        capture_output=True,
        text=True,
        timeout=30,
        env=env,
    )


def test_lock_script_runs_the_command_when_the_lock_is_free(tmp_path) -> None:
    """⚠️ 锁空闲 ⇒ ⇒ **正常执行**（不能把正常流程锁死）。"""
    result = _run_locked(["sh", "-c", "echo RAN-OK"], tmp_path / "lane.lock")
    assert result.returncode == 0, result.stderr
    assert "RAN-OK" in result.stdout


def test_lock_script_refuses_when_the_lock_is_held(tmp_path) -> None:
    """⚠️ **锁被占 ⇒ ⇒ 非零退出** ⇒ ⇒ 这就是「直接 docker compose run 被拒」。"""
    lock_file = tmp_path / "lane.lock"
    # 后台持锁 5 秒
    holder = subprocess.Popen(
        ["flock", "-x", str(lock_file), "sh", "-c", "sleep 5"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        # 等它真的拿到锁
        for _ in range(50):
            time.sleep(0.1)
            probe = subprocess.run(
                ["flock", "-n", str(lock_file), "true"],
                capture_output=True,
            )
            if probe.returncode != 0:
                break
        result = _run_locked(["sh", "-c", "echo SHOULD-NOT-RUN"], lock_file)
        assert result.returncode != 0, (
            "锁被占时脚本**仍然执行了命令** ⇒ ⇒ 互斥失效"
            f"（stdout={result.stdout!r}）"
        )
        assert "SHOULD-NOT-RUN" not in result.stdout
        assert "另一条车道" in result.stderr
    finally:
        holder.terminate()
        holder.wait(timeout=10)


def test_lock_script_yields_when_the_host_already_holds_the_lock(tmp_path) -> None:
    """⚠️ `PCS_LANE_LOCK_HELD=1` ⇒ ⇒ **放行**（宿主脚本已持锁 ⇒ ⇒ 否则自锁）。"""
    lock_file = tmp_path / "lane.lock"
    holder = subprocess.Popen(
        ["flock", "-x", str(lock_file), "sh", "-c", "sleep 5"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        time.sleep(1)
        result = _run_locked(
            ["sh", "-c", "echo RAN-OK"], lock_file, PCS_LANE_LOCK_HELD="1"
        )
        assert result.returncode == 0, result.stderr
        assert "RAN-OK" in result.stdout
    finally:
        holder.terminate()
        holder.wait(timeout=10)


# ---------------------------------------------------------------------------
# ③ Dockerfile
# ---------------------------------------------------------------------------


def test_dockerfile_installs_util_linux_for_flock() -> None:
    """⚠️ `flock` 来自 `util-linux` ⇒ ⇒ 镜像必须装它。"""
    text = DOCKERFILE.read_text(encoding="utf-8")
    assert "util-linux" in text, "Dockerfile 没装 util-linux ⇒ ⇒ 镜像里没有 flock"


# ---------------------------------------------------------------------------
# ④ 容器实测（`docker` 标记 · 默认 deselect）
# ---------------------------------------------------------------------------


@pytest.mark.docker
def test_the_built_image_actually_has_flock() -> None:
    """⚠️ **实测镜像里真的有 `flock`** ⇒ ⇒ 静态断言骗不了人。"""
    subprocess.run(
        ["docker", "image", "inspect", IMAGE_NAME],
        capture_output=True,
        check=True,
        timeout=60,
    )
    result = subprocess.run(
        ["docker", "run", "--rm", IMAGE_NAME, "sh", "-c", "command -v flock"],
        capture_output=True,
        text=True,
        timeout=120,
    )
    assert result.returncode == 0, result.stderr
    assert "flock" in result.stdout
