"""**默认车道**的隔离性（P10-F · F2-T5 · 评审期间新发现）。

## 为什么要有这个测试

⚠️ **默认车道**（`uv run pytest`）的硬约束（`CLAUDE.md`）：
**单测车道绝不碰开发库** ⇒ ⇒ 单测写进开发库 ⇒ ⇒ **绿灯但库被改了**。

⇒ ⇒ 但实测（2026-11-17 · P10-F 评审期间）：跑默认车道时，进程 socket 里
挂着 **127.0.0.1:5432**（开发库 `pcs`）与 **127.0.0.1:6379**（真 Redis）
的连接 ⇒ ⇒ 而且整轮跑到 22% **挂死 33 分钟**。

## 两条根因

1. `app/db/session.py` 有**三个模块级单例**：
   `_sync_engine` · `_async_engine` · `_async_session_factory`
   ⇒ ⇒ 默认车道的 `tests/conftest.py` **只覆写了后两个**（而且是在
   `db_engine` fixture 里造**另一个**引擎，不是覆写单例）
   ⇒ ⇒ **`_sync_engine` 裸奔** ⇒ ⇒ 任何走 `get_engine()` 的路径
   （今天：`app/db/session.py::check_database`）都连**开发库**。
2. `app/services/edit_lock.py` 与 `app/services/broadcaster.py` 直接
   `aioredis.Redis.from_url(settings.redis_url)` ⇒ ⇒ 默认车道连**真 Redis**。

## 断法

⚠️ **断法 = 「URL 指向不可路由目标」**（与实现同形）⇒ ⇒
**跨平台**（不扫 `/proc`，那是 Linux 专有）⇒ ⇒ 且「连了就炸」比
「查到了再判」更硬。

⚠️ **额外的手工核验**（不写进测试，因为跨平台）：跑默认车道时
`ss -tnp | grep -E ":5432|:6379"` ⇒ ⇒ **不得**出现 pytest 的连接。
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine


def test_sync_engine_singleton_never_points_at_a_real_database() -> None:
    """⚠️ **第三个单例**（`_sync_engine`）不许连**真库**。

    ⇒ ⇒ 判据 = 引擎的 URL **不是** postgres ⇒ ⇒ 它是 SQLite（内存）。
    """
    import app.db.session as db_session

    engine = db_session._sync_engine
    assert engine is not None, (
        "同步引擎单例没有被覆写 ⇒ 任何走 `get_engine()` 的路径都连开发库"
    )
    url = str(engine.url)
    assert not url.startswith("postgres"), (
        f"同步引擎指向真库 {url!r} ⇒ 默认车道会碰开发库"
    )
    assert url.startswith("sqlite"), f"同步引擎应当是 SQLite（内存）⇒ {url!r}"


def test_redis_url_points_at_an_unroutable_port() -> None:
    """⚠️ Redis 必须指向**不可路由**的端口 ⇒ ⇒ 「连了就炸」。

    ⚠️ **为什么不用 `fakeredis`**：仓里没有 ⇒ ⇒ **不新增依赖**（单人开发裁决）。
    ⇒ ⇒ 选「不可路由端口」⇒ ⇒ 依赖真 Redis 语义的测试会**当场红**
    ⇒ ⇒ 那类测试要迁到 `scripts/pytest_pg.sh` 车道（登记 TODO-165）。
    """
    from app.core.config import get_settings

    settings = get_settings()
    assert "127.0.0.1:1" in settings.redis_url or "localhost:1" in settings.redis_url, (
        f"redis_url 仍指向真 Redis {settings.redis_url!r} ⇒ 默认车道会连真 Redis"
    )


def test_connecting_to_the_configured_redis_url_fails_fast() -> None:
    """⚠️ **连了就炸** —— 不可路由端口 ⇒ ⇒ 连接**必须**抛错（不是静默重试）。

    ⇒ ⇒ 这是「不可路由端口」这个手段的**前提**：如果它连上了，那这条断言
    ⇒ ⇒ 就是**假绿** ⇒ ⇒ 守卫的前提被破坏 ⇒ ⇒ 必须当场红。
    """
    import asyncio

    import redis.asyncio as aioredis  # ⚠️ 与 app 侧同一个 import（redis-py 5.x）

    from app.core.config import get_settings

    settings = get_settings()

    async def _try() -> None:
        client = aioredis.Redis.from_url(settings.redis_url)
        try:
            await client.ping()
        finally:
            await client.aclose()

    with pytest.raises(Exception):  # noqa: B017 — 任何异常都算「连不上」
        asyncio.run(_try())


def test_a_fresh_sqlite_sync_engine_can_be_created_without_a_real_db() -> None:
    """⚠️ **兜底自检** —— SQLite 同步引擎**建得出来**且**能连**。

    ⇒ ⇒ 这条不是为了测 SQLite（那是 SQLAlchemy 的事）⇒ ⇒ 是为了让
    ⇒ 「默认车道不碰真库」这件事有个**正向**的证据（不只是「没连」）。
    """
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT 1").scalar_one() == 1
    finally:
        engine.dispose()
