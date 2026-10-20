"""P9A C3：通知 30 天保留清理（ADR-0049 §④ / SPEC P9A-NOT-004）。

TODO-016 显示 **ARQ 失败路径覆盖率为零**。本文件补这条缺口，并补一条
「漏注册」的守卫 —— **ARQ 对未注册的函数名不报错**，job 静静躺在队列里，
症状是「30 天后通知还在，且没人知道」（`worker.py` 里已记为踩坑）。

## 清理不得删未读通知

那条规则写在 ADR §④ 的语义里但没写成测试 —— 而它恰恰是最危险的一条：
清理任务删的是**用户的东西**。未读通知的删除期限没有依据。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.notification import Notification, NotificationKind
from app.services.notifications.payload import NotificationDetail, NotificationPayload
from app.workers.notification_tasks import NOTIFICATION_RETENTION_DAYS, cleanup_old_notifications

pytestmark = pytest.mark.asyncio


async def _seed(db, *, days_old: float, read: bool):
    p = NotificationPayload.from_detail(
        recipient_id=uuid.uuid4(),
        kind=NotificationKind.SIGN_COMPLETED,
        title="旧通知",
        body="B",
        detail=NotificationDetail(),
    )
    db.add(
        Notification(
            notification_id=p.notification_id,
            recipient_id=p.recipient_id,
            kind=p.kind,
            title=p.title,
            body=p.body,
            detail_json=None,
            read_at=datetime.now(UTC) if read else None,
            created_at=datetime.now(UTC) - timedelta(days=days_old),
        )
    )
    await db.commit()
    return p.notification_id


async def test_cleanup_deletes_read_notifications_older_than_retention(db):
    nid = await _seed(db, days_old=NOTIFICATION_RETENTION_DAYS + 1, read=True)

    n = await cleanup_old_notifications({"session_factory": _factory(db)})

    assert n == 1
    assert (await db.execute(select(Notification))).scalars().all() == []


async def test_cleanup_never_deletes_unread_notifications(db):
    """⚠️ **最危险的一条**：清理删的是用户的东西。

    未读通知即便过了 30 天也不删 —— 铃铛上的红点突然空掉，而用户不知道为什么。
    """
    await _seed(db, days_old=NOTIFICATION_RETENTION_DAYS + 365, read=False)

    n = await cleanup_old_notifications({"session_factory": _factory(db)})

    assert n == 0
    assert len((await db.execute(select(Notification))).scalars().all()) == 1


async def test_cleanup_keeps_recent_read_notifications(db):
    await _seed(db, days_old=NOTIFICATION_RETENTION_DAYS - 1, read=True)

    n = await cleanup_old_notifications({"session_factory": _factory(db)})

    assert n == 0


async def test_cleanup_is_idempotent(db):
    """跑两次：第二次删 0 行，不报错。

    cron 会重复触发；第二次抛异常会让 ARQ 重试，把一个成功的清理变成告警。
    """
    await _seed(db, days_old=NOTIFICATION_RETENTION_DAYS + 1, read=True)
    ctx = {"session_factory": _factory(db)}

    assert await cleanup_old_notifications(ctx) == 1
    assert await cleanup_old_notifications(ctx) == 0


async def test_cleanup_on_empty_table_returns_zero(db):
    assert await cleanup_old_notifications({"session_factory": _factory(db)}) == 0


def _factory(db):
    """让任务体里的 `ctx["session_factory"]` 复用测试会话。"""

    class _Factory:
        def __call__(self):
            return self

        async def __aenter__(self):
            return db

        async def __aexit__(self, *exc):
            return False

    return _Factory()


# ============================================================================
# 注册与失败路径（ADR-0049 §④ 的两条硬要求）
# ============================================================================


def _cron(func_name: str):
    from app.workers.worker import WorkerSettings

    for job in WorkerSettings.cron_jobs:
        got = getattr(job, "coroutine", None)
        if getattr(got, "__name__", None) == func_name:
            return job
    raise AssertionError(
        f"WorkerSettings.cron_jobs 里没有 coroutine 为 {func_name} 的 job："
        f"{[getattr(getattr(j, 'coroutine', j), '__name__', j) for j in WorkerSettings.cron_jobs]}"
    )


def test_cleanup_task_is_registered_in_worker():
    """⚠️ **ARQ 对未注册的函数名不报错**，job 静静躺在队列里。

    症状是「30 天后通知还在，且没人知道」—— 与「压根没接 cron」症状完全一样。
    """
    from app.workers.worker import WorkerSettings

    registered = {f.__name__ for f in WorkerSettings.functions}
    assert "cleanup_old_notifications" in registered, (
        "清理任务没注册 —— ARQ 对未注册的函数名不报错，"
        "job 会静静躺在队列里且没有任何告警"
    )
    assert _cron("cleanup_old_notifications") is not None, (
        "清理任务没挂 cron —— 表只增不减"
    )


def test_cleanup_failure_is_retried_not_silently_dropped():
    """TODO-016 的缺口。⚠️ 既有 cron 的 `max_tries=1` 意味着**失败不重试** ——
    通知清理必须显式设 `max_tries >= 2`，否则一次瞬时抖动就让清理永久失效。

    永久失效与漏注册是**同一个失败形状**：「30 天后通知还在，且没人知道」。
    """
    job = _cron("cleanup_old_notifications")
    assert job.max_tries is not None and job.max_tries >= 2, (
        f"max_tries={job.max_tries} —— 一次瞬时连接抖动就会让清理永久失效，"
        "而症状与漏注册一模一样"
    )


def test_cleanup_cron_second_is_zero_not_none():
    """秒位传 `None` 在 ARQ 里等于「这一位不参与匹配」⇒ 匹配的那一分钟里
    **每秒**都命中（`worker.py` 的血泪注释）。每日一次的清理不该变成
    每分钟 59 次的全表 DELETE。"""
    assert _cron("cleanup_old_notifications").second == 0


def test_cleanup_cron_is_a_cronjob_instance_not_a_dict():
    """ARQ 0.28 的 `Worker.__init__` 直接校验类型，dict 会让 worker **构造就抛**
    —— 而它此前从没被真跑起来过，所以没人发现。"""
    from arq.cron import CronJob

    from app.workers.worker import WorkerSettings

    for job in WorkerSettings.cron_jobs:
        assert isinstance(job, CronJob), f"cron_jobs 里混进了非 CronJob：{type(job).__name__}"
