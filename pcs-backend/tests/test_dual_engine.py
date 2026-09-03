"""双引擎 / lifespan 测试。"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


async def test_async_engine_url_conversion():
    from app.db.session import _build_async_url

    assert _build_async_url("postgresql+psycopg://u:p@h/db").startswith(
        "postgresql+asyncpg://"
    )
    assert _build_async_url("postgresql://u:p@h/db").startswith(
        "postgresql+asyncpg://"
    )


async def test_lifespan_warms_async_engine(client):
    """client fixture 内部走 lifespan，验证 dispose_engines_async 可调用。"""
    from app.db.session import dispose_engines_async

    await dispose_engines_async()
    # 不抛即通过（引擎已在 lifespan 中初始化）


def test_cors_allow_origins_parsed():
    from app.core.config import get_settings

    s = get_settings()
    origins = [o.strip() for o in s.cors_allow_origins.split(",") if o.strip()]
    assert "http://localhost:5173" in origins


def test_redis_url_default_present():
    from app.core.config import get_settings

    s = get_settings()
    assert s.redis_url.startswith("redis://")