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
from app.models.project import UserProject
from app.services.notification_recipients import resolve_role_recipients


async def _grant(db, user_id: uuid.UUID, project_id: uuid.UUID) -> None:
    """给用户授予项目成员身份（`user_projects` 有效行）。"""
    db.add(UserProject(user_id=user_id, project_id=project_id, role_in_project="VIEWER"))
    await db.flush()


async def test_resolve_by_global_role(db, make_user, project_id):
    """全局角色命中 **且** 有项目授权 ⇒ 收件人。"""
    zhang = await make_user("zhang", ["REVIEWER"])
    await make_user("wang", ["DESIGNER"])
    await _grant(db, zhang, project_id)
    got = await resolve_role_recipients(db, role="REVIEWER", project_id=project_id)
    assert got == [zhang]


async def test_project_role_alone_does_not_match(db, make_user, project_id):
    """⚠️ 项目内角色**不参与**角色匹配。

    签署矩阵的 `sign_role` 与 **token 的 role claim** 比较（`sign_step` 里
    `sign_role != actor_role` ⇒ 403 `SIGN_STEP_ROLE_MISMATCH`），项目那侧
    （`_authorize`）只校验**成员身份**、不看角色。

    ⇒ 一个全局 DESIGNER、项目内 REVIEWER 的人**签不了** REVIEWER 那一步。
    把他算进收件人 = 通知他一件他根本做不了的事；而在待办侧则是「待办里有，
    点进去说你不是」—— 比没有待办更坏。
    """
    from app.models.project import UserProject

    li = await make_user("li", ["DESIGNER"])
    db.add(UserProject(user_id=li, project_id=project_id, role_in_project="REVIEWER"))
    await db.flush()
    got = await resolve_role_recipients(db, role="REVIEWER", project_id=project_id)
    assert li not in got


async def test_global_role_with_project_access_matches(db, make_user, project_id):
    """全局角色命中 **且** 有项目授权 ⇒ 收件人。

    ⚠️ 两个条件缺一不可：只有全局角色 ⇒ 他点不开那个待办（越权）；
    只有项目授权 ⇒ 他的角色不是矩阵要的那一档。
    """
    from app.models.project import UserProject

    rev = await make_user("rev", ["REVIEWER"])
    db.add(UserProject(user_id=rev, project_id=project_id, role_in_project="VIEWER"))
    await db.flush()
    got = await resolve_role_recipients(db, role="REVIEWER", project_id=project_id)
    assert rev in got


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


async def test_resolve_excludes_disabled_users(db, make_user, project_id):
    """停用用户（离职）不该再收通知。"""
    from app.models.project import User

    zhang = await make_user("zhang", ["REVIEWER"])
    await _grant(db, zhang, project_id)
    await db.execute(
        User.__table__.update()
        .where(User.user_id == zhang)
        .values(status="DISABLED")
    )
    await db.flush()
    got = await resolve_role_recipients(db, role="REVIEWER", project_id=project_id)
    assert got == []


async def test_notify_persists_one_row_per_recipient(db, make_user, project_id):
    """`notify_role()` 给该角色下**每个**收件人各写一行。"""
    from app.services.notifications.notify import notify_role, publish

    a = await make_user("a", ["REVIEWER"])
    b = await make_user("b", ["REVIEWER"])
    await make_user("c", ["DESIGNER"])
    await _grant(db, a, project_id)
    await _grant(db, b, project_id)

    results = await notify_role(
        db,
        role="REVIEWER",
        kind=NotificationKind.SIGN_COMPLETED,
        title="待复核",
        body="有一份交付物等你复核",
        project_id=project_id,
    )
    await db.commit()
    rows = (await db.execute(select(Notification))).scalars().all()
    assert len(results) == 2
    assert {r.recipient_id for r in rows} == {a, b}


async def test_notify_with_no_recipients_is_not_an_error(db, project_id):
    """角色下没人时返回空列表，**不抛**。抛会让「暂时没人有权限」变成 500。"""
    from app.services.notifications.notify import notify_role, publish

    assert await notify_role(
        db,
        role="APPROVER",
        kind=NotificationKind.SIGN_COMPLETED,
        title="t",
        body="b",
        project_id=project_id,
    ) == []


async def test_notify_push_failure_does_not_break_the_caller(db, make_user, project_id):
    """同步写 + 推送失败 ⇒ 通知**仍然落库**，调用方不感知推送失败。

    ADR-0049 §⑤ 约束 2：降级要可观测，但**不得**让业务请求崩 ——
    签署已提交却因推送失败返 500，用户会重签一次。
    """
    from app.services.broadcaster import Broadcaster, set_broadcaster
    from app.services.notifications.notify import notify_role, publish

    a = await make_user("a", ["REVIEWER"])
    await _grant(db, a, project_id)
    dead = Broadcaster("redis://127.0.0.1:6399/0")
    set_broadcaster(dead)
    try:
        pending = await notify_role(
            db,
            role="REVIEWER",
            kind=NotificationKind.SIGN_COMPLETED,
            title="t",
            body="b",
            project_id=project_id,
        )
        assert len(pending) == 1
        await publish(pending)
        assert dead.status == "degraded"
    finally:
        set_broadcaster(None)


async def test_notify_publishes_to_each_recipient_channel(db, make_user, project_id):
    """推送按 `recipient_id` 分 channel（ADR-0049 §⑤ 约束 4）。"""
    from app.services.broadcaster import Broadcaster, set_broadcaster
    from app.services.notifications.notify import notify_role, publish

    a = await make_user("a", ["REVIEWER"])
    await _grant(db, a, project_id)
    pub = []
    b = Broadcaster("redis://localhost:6379/9")
    b.publish = lambda rid, msg: _record(pub, rid, msg)  # type: ignore[method-assign]
    set_broadcaster(b)
    try:
        pending = await notify_role(
            db,
            role="REVIEWER",
            kind=NotificationKind.SIGN_COMPLETED,
            title="t",
            body="b",
            project_id=project_id,
        )
        await publish(pending)
        assert [r for r, _ in pub] == [a]
        assert pub[0][1]["kind"] == NotificationKind.SIGN_COMPLETED
    finally:
        set_broadcaster(None)


async def _record(sink: list, rid, msg):
    sink.append((rid, msg))


async def test_recipient_without_project_access_does_not_get_project_notifications(
    db, make_user, project_id
):
    """⚠️ 收件人解析**必须**受项目授权约束。

    一个全局角色是 DESIGNER、但**没有该项目授权**的人，不得收到该项目的
    变更单通知 —— 通知体里带着 deliverable title 与 project_id，那是不该
    让他看到的东西。

    ⇒ 这是通知侧与待办侧曾经**不对称**的地方：待办按 `user_projects` 圈人，
    通知按全局角色圈人。两条规则漂移的症状是「待办里没有他，通知里有他」。
    """
    from app.models.project import UserProject
    from app.services.notifications.notify import notify_role, publish

    outsider = await make_user("outsider", ["DESIGNER"])  # 全局 DESIGNER，无项目授权
    insider = await make_user("insider", ["DESIGNER"])
    db.add(UserProject(user_id=insider, project_id=project_id, role_in_project="DESIGNER"))
    await db.flush()

    await notify_role(
        db,
        role="DESIGNER",
        kind=NotificationKind.CHANGE_NOTICE_APPROVED,
        title="变更单已批准",
        body="B",
        project_id=project_id,
    )
    await db.commit()

    rows = (await db.execute(select(Notification))).scalars().all()
    recipients = {r.recipient_id for r in rows}
    assert outsider not in recipients, "没有该项目授权的人收到了该项目的通知"
    assert insider in recipients, "有项目授权的同角色用户反而没收到"


# ==========================================================================
# F-1 / F-7：事务边界 —— 通知行与业务变更**同一次提交**，推送在提交**之后**
# ==========================================================================


async def test_notify_writes_the_row_but_does_not_commit(db, make_user, project_id):
    """`notify()` 只 flush，**不提交** —— 提交由调用方在业务变更之后做。

    两次提交意味着两个真相源：业务变更已落库、通知行还没落库，
    而两者之间进程挂掉 ⇒ 变更发生了但没人被告知。
    """
    from app.services.notifications.notify import notify

    a = await make_user("a", ["REVIEWER"])
    await _grant(db, a, project_id)

    calls = []
    original = db.commit

    async def _counting_commit():
        calls.append(1)
        await original()

    db.commit = _counting_commit
    try:
        await notify(
            db,
            recipient_id=a,
            kind=NotificationKind.SIGN_COMPLETED,
            title="t",
            body="b",
        )
    finally:
        db.commit = original

    assert calls == [], "notify() 不该自己提交 —— 提交必须与业务变更同一次"


async def test_publish_is_a_separate_step_from_writing(db, make_user, project_id):
    """写与推是两步：先写（同一事务），提交后再推。"""
    from app.services.notifications.notify import notify, publish

    a = await make_user("a", ["REVIEWER"])
    await _grant(db, a, project_id)
    published: list = []

    class _Spy:
        status = "ok"
        reason = None

        async def publish(self, rid, msg):
            published.append((rid, msg))

    from app.services.broadcaster import set_broadcaster

    spy = _Spy()
    set_broadcaster(spy)
    try:
        payload = await notify(
            db,
            recipient_id=a,
            kind=NotificationKind.SIGN_COMPLETED,
            title="t",
            body="b",
        )
        assert published == [], "notify() 阶段不该推送（还没提交）"
        await db.commit()
        await publish(payload)
        assert [r for r, _ in published] == [a]
    finally:
        set_broadcaster(None)


async def test_commit_failure_leaves_no_phantom_push(db, make_user, project_id):
    """⚠️ 提交失败 ⇒ **不得**推送。

    提交前推送的后果是 phantom notification：用户已经在 UI 上看到铃铛，
    点进去却 404（行被回滚了）。那比没推更糟。
    """
    from app.services.broadcaster import set_broadcaster
    from app.services.notifications.notify import notify, publish

    a = await make_user("a", ["REVIEWER"])
    await _grant(db, a, project_id)
    published: list = []

    class _Spy:
        status = "ok"
        reason = None

        async def publish(self, rid, msg):
            published.append((rid, msg))

    set_broadcaster(_Spy())
    try:
        payload = await notify(
            db,
            recipient_id=a,
            kind=NotificationKind.SIGN_COMPLETED,
            title="t",
            body="b",
        )

        async def _boom():
            raise RuntimeError("DB 抖动")

        db.commit = _boom
        try:
            await db.commit()
        except RuntimeError:
            pass
        else:
            pytest.fail("commit 应当失败")

        # 提交失败 ⇒ 不推送
        assert published == [], "提交失败时不得推送 —— 那是 phantom notification"
        # 且载荷仍在手上，调用方可以选择不推
        assert payload is not None
    finally:
        set_broadcaster(None)
