"""通知保留期清理（ADR-0049 §④ / SPEC P9A-NOT-004，ARQ cron）。

## 只删**已读**且过期的通知

ADR §④ 说的是「30 天过期删除」，但**未读通知不删**。
理由：清理任务删的是用户的东西 —— 铃铛上的红点突然空掉、用户不知道为什么，
比多占几行数据坏得多。未读通知的删除期限没有依据，所以没有期限。

## 失败必须重试（不是静默丢弃）

既有三个 cron 都是 `max_tries=1`（`worker.py` 的 `MAX_TRIES`）。清理任务
**显式设 `max_tries=2`** —— 一次瞬时的连接抖动不该让清理永久失效，
而永久失效的症状是「30 天后通知还在，且没人知道」（同 §④ 漏注册的坑）。
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete

from app.models.notification import Notification

#: 保留天数（ADR-0049 §④）。
NOTIFICATION_RETENTION_DAYS = 30


async def cleanup_old_notifications(ctx: dict) -> int:
    """删除「已读且创建时间早于保留期」的通知。返回删除行数。

    幂等：第二次跑删 0 行。无人可删时返回 0 而不抛 ——
    「没有过期通知」是一种状态，不是一次失败。
    """
    factory = ctx["session_factory"]
    async with factory() as session:
        cutoff = datetime.now(UTC) - timedelta(days=NOTIFICATION_RETENTION_DAYS)
        result = await session.execute(
            delete(Notification).where(
                Notification.read_at.is_not(None),
                Notification.created_at < cutoff,
            )
        )
        await session.commit()
        return int(result.rowcount or 0)
