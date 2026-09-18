"""双引擎：sync（P0 auth/health/migration）+ async（P1 端点/ARQ）。

lifespan 顺序（TODO-021）：startup 先 async probe → 再 sync init；
shutdown 反向。ARQ 任务独立创建 async session，不依赖 FastAPI 依赖注入。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

_sync_engine: Engine | None = None
_async_engine: AsyncEngine | None = None
_async_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> Engine:
    """P0 同步引擎（auth/health/migration 路径）。"""
    global _sync_engine
    if _sync_engine is None:
        _sync_engine = create_engine(
            get_settings().database_url,
            pool_size=5,
            max_overflow=45,
            pool_pre_ping=True,
            pool_timeout=30,
            pool_recycle=1800,
        )
    return _sync_engine


def check_database() -> bool:
    """P0 健康检查（同步）。"""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


def _build_async_url(sync_url: str) -> str:
    """postgresql+psycopg:// → postgresql+asyncpg://"""
    if sync_url.startswith("postgresql+psycopg://"):
        return sync_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
    if sync_url.startswith("postgresql://"):
        return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return sync_url


def get_async_engine() -> AsyncEngine:
    """P1 异步引擎（端点 + ARQ 任务）。"""
    global _async_engine
    if _async_engine is None:
        _async_engine = create_async_engine(
            _build_async_url(get_settings().database_url),
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            pool_timeout=30,
            pool_recycle=1800,
        )
    return _async_engine


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """ARQ 任务用：独立创建 session，不依赖 FastAPI 依赖注入。"""
    global _async_session_factory
    if _async_session_factory is None:
        _async_session_factory = async_sessionmaker(
            get_async_engine(),
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _async_session_factory


async def check_database_async() -> bool:
    """P1 健康检查（异步）。"""
    try:
        async with get_async_engine().connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def get_db() -> AsyncIterator[AsyncSession]:
    """FastAPI 依赖：每个请求一个 AsyncSession。"""
    factory = get_async_session_factory()
    async with factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def dispose_engines_async() -> None:
    """lifespan shutdown：释放 async engine 连接池。"""
    global _async_engine, _async_session_factory
    if _async_engine is not None:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None


def dispose_sync_engine() -> None:
    """lifespan shutdown：释放 sync engine 连接池（P0-MED-002 修复）。"""
    global _sync_engine
    if _sync_engine is not None:
        _sync_engine.dispose()
        _sync_engine = None