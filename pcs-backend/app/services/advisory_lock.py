"""Postgres advisory lock（事务级）防止并发状态转移。

pg_advisory_xact_lock(classid, objid) — 事务结束释放；同 classid+objid 串行化。
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


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