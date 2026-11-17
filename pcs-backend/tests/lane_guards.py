"""**默认车道**的隔离守卫（P10-F · F2-T5）—— 一处真相源。

## 为什么有这个模块

默认车道（`uv run pytest`）把 `settings.redis_url` 指向**不可路由**端口
（`redis://127.0.0.1:1/0`）⇒ ⇒ 「连了就炸」比「查到了再判」更硬。

⇒ ⇒ 依赖**真 Redis 语义**的用例（编辑锁 TTL/续期 · pub/sub 跨进程推送）
在默认车道**测不了** ⇒ ⇒ 它们要迁到 `scripts/pytest_pg.sh` 车道
（**TODO-165**）⇒ ⇒ 本模块给它们一个统一的「跳过」入口。

⚠️ **判据只读 URL、绝不连接** ⇒ ⇒ 否则**导入期**就���连一次真 Redis
⇒ ⇒ 默认车道**又**连了 6379 ⇒ ⇒ 白隔离了。
"""

from __future__ import annotations

import pytest


def settings_redis_isolated() -> bool:
    """默认车道是否已把 `settings.redis_url` 指向**不可路由**端口。"""
    from app.core.config import get_settings

    url = get_settings().redis_url
    return ":1/0" in url or url.endswith(":1")


def require_real_redis() -> None:
    """默认车道 ⇒ 跳过依赖真 Redis 语义的用例（⇒ 迁到 PG 车道）。

    ⚠️ **运行期**调用（不是导入期）⇒ ⇒ 此时 `settings` 已被会话 fixture
    改成不可路由端口 ⇒ ⇒ 判据才准。
    """
    if settings_redis_isolated():
        pytest.skip(
            "依赖真 Redis 语义 ⇒ 默认车道隔离后连不上"
            " ⇒ 迁到 scripts/pytest_pg.sh 车道（TODO-165）"
        )
