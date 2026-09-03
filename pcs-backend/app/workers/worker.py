"""ARQ WorkerSettings（Sprint 1 + Sprint 3）。

含四个异步任务：
- cleanup_workspaces：扫描并删除过期 PERSONAL/TEMPORARY workspace
- touch_workspace：把指定 workspace last_active_at 推到 now（活跃心跳）
- scan_stale_incremental：1 分钟增量 CIA 扫描
- scan_stale_full：5 分钟全量 CIA 扫描
"""

from __future__ import annotations

from arq.connections import RedisSettings
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import dispose_engines_async, get_async_session_factory
from app.workers.cia_tasks import scan_stale_full, scan_stale_incremental
from app.workers.workspace_tasks import (
    cleanup_expired_workspaces,
    touch_workspace,
)


async def _on_startup(ctx: dict) -> None:
    settings = get_settings()
    ctx["redis_settings"] = RedisSettings.from_dsn(settings.redis_url)
    ctx["session_factory"] = get_async_session_factory()


async def _on_shutdown(ctx: dict) -> None:
    await dispose_engines_async()


async def _make_session(ctx: dict) -> AsyncSession:
    factory = ctx["session_factory"]
    return factory()


class WorkerSettings:
    redis_settings: RedisSettings = RedisSettings()  # overridden in startup
    on_startup = _on_startup
    on_shutdown = _on_shutdown
    functions = [
        cleanup_expired_workspaces,
        touch_workspace,
        scan_stale_incremental,
        scan_stale_full,
    ]
    cron_jobs = [
        # ARQ cron 语法：(minute, hour, day, month, dow, function)
        # Sprint 3.9：每 5 分钟全量；每 1 分钟增量
        {
            "minute": {0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55},
            "function": scan_stale_full,
        },
        {
            "second": 0,
            "minute": {1, 6, 11, 16, 21, 26, 31, 36, 41, 46, 51, 56},
            "function": scan_stale_incremental,
        },
    ]
    max_jobs = 4
    job_timeout = 300