"""Postgres advisory lock（事务级）防止并发状态转移。

pg_advisory_xact_lock(classid, objid) — 事务结束释放；同 classid+objid 串行化。
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def acquire_record_lock(
    session: AsyncSession, *, record_table: str, record_id: str
) -> None:
    """事务级 advisory lock：相同 (table, id) 串行执行。"""
    classid = abs(hash(record_table)) % (2**31)
    objid = abs(hash(record_id)) % (2**31)
    await session.execute(
        text("SELECT pg_advisory_xact_lock(:c, :o)"),
        {"c": classid, "o": objid},
    )


async def acquire_equip_list_lock(
    session: AsyncSession, *, project_id: UUID, tag_number: str
) -> None:
    """Per D2 裁决 2A: lock per (project_id, tag_number) for new EquipmentList INSERT serialization.

    Uses PG ``hashtext`` composite key. SQLite raises ``OperationalError`` (no
    ``hashtext``/``pg_advisory_xact_lock``) → silently no-op (single-thread
    happy path OK; concurrent test gates ``pcs_test`` only).
    """
    key = f"{project_id}::{tag_number}"
    try:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": key},
        )
    except OperationalError as e:
        # M5 fix: 加 logger.warning 让 SQLite production 误部署 get visibility
        # (Sentry / log aggregator 可 capture；否则 silent no-op 无察觉)
        logger.warning(
            "acquire_equip_list_lock skipped (SQLite OperationalError, "
            "no pg_advisory_xact_lock): project_id=%s tag_number=%s err=%s",
            project_id,
            tag_number,
            e,
        )
        return