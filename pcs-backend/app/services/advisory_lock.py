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

    F-P1-002 fix: dialect-aware. SQLite → no-op (test path OK).
    PostgreSQL → re-raise OperationalError (生产环境必须有锁，不容 silent no-op
    否则 race condition silently un-protected).
    """
    key = f"{project_id}::{tag_number}"
    try:
        await session.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(:key))"),
            {"key": key},
        )
    except OperationalError as e:
        dialect = session.bind.dialect.name if session.bind else "unknown"
        if dialect == "postgresql":
            # 生产 PG 不应该 OperationalError — re-raise fail-fast
            logger.error(
                "acquire_equip_list_lock failed on postgresql: "
                "project_id=%s tag_number=%s err=%s",
                project_id, tag_number, e,
            )
            raise
        # SQLite 测试路径: no-op (M5 logger.warning 已落地)
        logger.warning(
            "acquire_equip_list_lock skipped (SQLite, no pg_advisory_xact_lock): "
            "project_id=%s tag_number=%s",
            project_id, tag_number,
        )
        return