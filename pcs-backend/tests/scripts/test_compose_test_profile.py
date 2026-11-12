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

from pathlib import Path

import pytest
import yaml

#: 仓库根（tests/scripts/ → tests/ → pcs-backend/ → 根）
REPO_ROOT = Path(__file__).resolve().parents[3]
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
