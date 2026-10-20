"""通知读 / 标已读（ADR-0049 §① + §⑤ 约束 1）。

## 为什么这里的查询形状不能改

`GET /notifications` 是**断线兜底路径**（§⑤ 约束 1）：pub/sub 不持久化，
重连后靠它拉未读。两条查询都走 ADR-0049 §③ 的部分索引
`ix_notifications_recipient_unread (recipient_id, read_at) WHERE read_at IS NULL`
与 `ix_notifications_recipient_created (recipient_id, created_at)`。

⚠️ **不加 `project_id` 过滤**：通知的归属就是 `recipient_id`，
加一个可能写错的列等于制造第二个鉴权依据（见 `app/models/notification.py`）。

## 越权一律 404

标已读时「这条通知不存在」与「这条通知是别人的」返回**同一个 code** ——
两者可区分就是存在性预言机。
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.notification import Notification
from app.services.notifications.payload import NotificationDetail

logger = logging.getLogger(__name__)


async def list_notifications(
    db: AsyncSession,
    *,
    recipient_id: uuid.UUID,
    after: datetime | None = None,
    limit: int = 50,
) -> tuple[list[Notification], int]:
    """返回（按 created_at 倒序的通知行, 未读总数）。"""
    stmt = select(Notification).where(Notification.recipient_id == recipient_id)
    if after is not None:
        stmt = stmt.where(Notification.created_at > after)
    # notification_id 作 tiebreaker：created_at 秒级粒度，
    # 同一批写入的时间戳必然相同，只按它排序时并列行顺序不确定
    # ⇒ 翻页会漏或重（与 record_comments / deliverable_service 同源问题）。
    stmt = stmt.order_by(Notification.created_at.desc(), Notification.notification_id.desc())
    stmt = stmt.limit(limit)

    unread_stmt = select(func.count()).select_from(Notification).where(
        Notification.recipient_id == recipient_id,
        Notification.read_at.is_(None),
    )
    rows = list((await db.execute(stmt)).scalars().all())
    unread = (await db.execute(unread_stmt)).scalar_one()
    return rows, int(unread)


async def mark_read(
    db: AsyncSession, *, recipient_id: uuid.UUID, notification_id: uuid.UUID
) -> Notification:
    """标已读。幂等 —— 重复调用不改 `read_at`。"""
    row = (
        await db.execute(
            select(Notification).where(
                Notification.notification_id == notification_id,
                Notification.recipient_id == recipient_id,
            )
        )
    ).scalar_one_or_none()
    if row is None:
        # 「不存在」与「是别人的」同一个 code —— 不可区分，否则泄露存在性。
        raise PcsError(
            code="NOTIFICATION_NOT_FOUND", message="通知不存在", status=404
        )
    if row.read_at is None:
        row.read_at = datetime.now(UTC)
        await db.commit()
        await db.refresh(row)
    return row


def to_detail(row: Notification) -> NotificationDetail | None:
    """`detail_json`（落库时是 JSON 形态）→ schema。空则 None。

    ⚠️ **必须兜住 `ValidationError`**（F-5）。`NotificationDetail` 是
    `extra="forbid"` 的 —— 那是它存在的意义（自由 dict 等于没有 schema）。
    但代价是：将来若有人**删/改名**一个字段，已落库的旧通知行里那个键就会
    让 `model_validate` 抛错 ⇒ 整个 `GET /notifications` 返 500
    （一个人的旧数据让所有人看不了通知）。

    ⇒ 坏的那一条降级成 `detail=None` 并记 ERROR，其余照常返回。
    通知的**标题与正文**仍然可读 —— 那才是铃铛上显示的东西。
    """
    if not row.detail_json:
        return None
    try:
        return NotificationDetail.model_validate(row.detail_json)
    except ValidationError:
        logger.error(
            "通知 %s 的 detail_json 与当前 schema 不符，已降级为 detail=None：%r",
            row.notification_id,
            row.detail_json,
        )
        return None
