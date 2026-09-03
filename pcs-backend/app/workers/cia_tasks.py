"""ARQ CIA 定时任务（Sprint 3）。

两个 cron 任务：
- scan_stale_incremental：每 1 分钟跑一遍增量扫描
- scan_stale_full：每 5 分钟跑全量扫描
"""

from __future__ import annotations

import logging

from app.db.session import check_database_async, get_async_session_factory
from app.services.cia_engine import CIAEngine

logger = logging.getLogger(__name__)


async def scan_stale_incremental(ctx) -> None:
    """1 分钟增量扫描：仅扫最近 1 分钟变更的 record。"""
    if not await check_database_async():
        logger.warning("CIA scan skipped: DB unavailable")
        return
    factory = get_async_session_factory()
    async with factory() as session:
        engine = CIAEngine(session)
        marked = await engine.scan_stale()
        await session.commit()
        logger.info("CIA incremental scan: %d marked STALE", marked)


async def scan_stale_full(ctx) -> None:
    """5 分钟全量扫描：扫所有 CHECKED/CHANGED records。"""
    if not await check_database_async():
        logger.warning("CIA full scan skipped: DB unavailable")
        return
    factory = get_async_session_factory()
    async with factory() as session:
        engine = CIAEngine(session)
        marked = await engine.scan_stale()
        await session.commit()
        logger.info("CIA full scan: %d marked STALE", marked)