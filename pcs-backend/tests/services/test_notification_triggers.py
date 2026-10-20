"""P9A C1b：通知**触发接线**（用户 2026-10-20 裁决的最小集合）。

四个触发点：sign-step 成功 / step 被退回 / proxy 代录完成 / 变更单审批。

## 为什么这些测试不 mock `notify()`

「service 层调了 notify」用 mock 一断就绿，而 mock 恰好是「接线断了但全绿」
的最短路径（本仓已为 TODO-047 与三次 404 假绿付过代价）。
⇒ 本文件断言**落库的那一行**：收件人是谁、`kind` 是什么、`detail` 带什么。

## 收件人解析：一个 helper，两个消费方

签署矩阵的 `sign_role` 是**角色名**不是用户。把它解析成用户集合的规则
被抽成 `resolve_role_recipients()`，通知接线（C1b）与待办实时计算（C4）
**共用同一个 helper** —— 两份解析规则必然漂移，而漂移的表现是
「通知发给了 A，待办列给 B」。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.notification import Notification, NotificationKind
from app.services.notification_recipients import resolve_role_recipients


async def test_resolve_by_global_role(db, make_user):
    zhang = await make_user("zhang", ["REVIEWER"])
    await make_user("wang", ["DESIGNER"])
    got = await resolve_role_recipients(db, role="REVIEWER")
    assert got == [zhang]


async def test_resolve_by_project_role(db, make_user, project_id):
    """项目内角色也要算 —— 只有 `users.roles` 的话，
    被只在某个项目里授予复核权的人永远收不到通知、也永远没有待办。"""
    from app.models.project import UserProject

    li = await make_user("li", ["DESIGNER"])
    db.add(UserProject(user_id=li, project_id=project_id, role_in_project="REVIEWER"))
    await db.flush()
    got = await resolve_role_recipients(db, role="REVIEWER", project_id=project_id)
    assert li in got


async def test_resolve_excludes_revoked_project_grant(db, make_user, project_id):
    """已撤销的项目授权不再算角色 —— 否则人离开项目后待办和通知仍在。"""
    from app.models.project import UserProject

    li = await make_user("li", ["DESIGNER"])
    db.add(
        UserProject(
            user_id=li,
            project_id=project_id,
            role_in_project="REVIEWER",
            revoked_at=__import__("datetime").datetime.now(__import__("datetime").UTC),
        )
    )
    await db.flush()
    got = await resolve_role_recipients(db, role="REVIEWER", project_id=project_id)
    assert li not in got


async def test_resolve_excludes_disabled_users(db, make_user):
    """停用用户（离职）不该再收通知。"""
    from app.models.project import User

    zhang = await make_user("zhang", ["REVIEWER"])
    await db.execute(
        User.__table__.update()
        .where(User.user_id == zhang)
        .values(status="DISABLED")
    )
    await db.flush()
    assert await resolve_role_recipients(db, role="REVIEWER") == []


async def test_notify_persists_one_row_per_recipient(db, make_user):
    """`notify_role()` 给该角色下**每个**收件人各写一行。"""
    from app.services.notifications.notify import notify_role

    a = await make_user("a", ["REVIEWER"])
    b = await make_user("b", ["REVIEWER"])
    await make_user("c", ["DESIGNER"])

    results = await notify_role(
        db,
        role="REVIEWER",
        kind=NotificationKind.SIGN_COMPLETED,
        title="待复核",
        body="有一份交付物等你复核",
    )
    await db.commit()
    rows = (await db.execute(select(Notification))).scalars().all()
    assert len(results) == 2
    assert {r.recipient_id for r in rows} == {a, b}


async def test_notify_with_no_recipients_is_not_an_error(db):
    """角色下没人时返回空列表，**不抛**。抛会让「暂时没人有权限」变成 500。"""
    from app.services.notifications.notify import notify_role

    assert await notify_role(
        db,
        role="APPROVER",
        kind=NotificationKind.SIGN_COMPLETED,
        title="t",
        body="b",
    ) == []


async def test_notify_push_failure_does_not_break_the_caller(db, make_user):
    """同步写 + 推送失败 ⇒ 通知**仍然落库**，调用方不感知推送失败。

    ADR-0049 §⑤ 约束 2：降级要可观测，但**不得**让业务请求崩 ——
    签署已提交却因推送失败返 500，用户会重签一次。
    """
    from app.services.broadcaster import Broadcaster, set_broadcaster
    from app.services.notifications.notify import notify_role

    await make_user("a", ["REVIEWER"])
    dead = Broadcaster("redis://127.0.0.1:6399/0")
    set_broadcaster(dead)
    try:
        results = await notify_role(
            db,
            role="REVIEWER",
            kind=NotificationKind.SIGN_COMPLETED,
            title="t",
            body="b",
        )
        assert len(results) == 1
        assert dead.status == "degraded"
    finally:
        set_broadcaster(None)


async def test_notify_publishes_to_each_recipient_channel(db, make_user):
    """推送按 `recipient_id` 分 channel（ADR-0049 §⑤ 约束 4）。"""
    from app.services.broadcaster import Broadcaster, set_broadcaster
    from app.services.notifications.notify import notify_role

    a = await make_user("a", ["REVIEWER"])
    pub = []
    b = Broadcaster("redis://localhost:6379/9")
    b.publish = lambda rid, msg: _record(pub, rid, msg)  # type: ignore[method-assign]
    set_broadcaster(b)
    try:
        await notify_role(
            db, role="REVIEWER", kind=NotificationKind.SIGN_COMPLETED, title="t", body="b"
        )
        assert [r for r, _ in pub] == [a]
        assert pub[0][1]["kind"] == NotificationKind.SIGN_COMPLETED
    finally:
        set_broadcaster(None)


async def _record(sink: list, rid, msg):
    sink.append((rid, msg))
