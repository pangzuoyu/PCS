"""通知读 / 标已读 API（SPEC P9A-NOT-001/005 / ADR-0049 §① + §⑤ 约束 1）。

`GET /api/v1/notifications` 是**断线兜底路径**：WebSocket 的 pub/sub 不持久化，
断线期间的消息只存在于 `notifications` 表里，前端重连后靠这里拉。

鉴权身份就是 `recipient_id` 本身（见 `app/models/notification.py`），
所以这里**没有** `_check_project_access_or_404` —— 加一层项目校验反而会
造出「通知属于某项目但用户不在这项目里 ⇒ 看不到自己的通知」这种错误。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor
from app.db.session import get_db
from app.schemas.notification import NotificationItemResponse, NotificationListResponse
from app.services import notification_query_service as svc

router = APIRouter(tags=["notifications"])

# 200 是通知列表的合理上限；`limit=10000` 会把整个表拉出来。
_MAX_LIMIT = 200


def _to_item(row) -> NotificationItemResponse:
    return NotificationItemResponse(
        notification_id=row.notification_id,
        kind=row.kind,
        title=row.title,
        body=row.body,
        detail=svc.to_detail(row),
        created_at=row.created_at,
        read_at=row.read_at,
    )


@router.get(
    "/notifications",
    response_model=NotificationListResponse,
    summary="我的通知（断线兜底路径）",
)
async def list_my_notifications(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
    after: Annotated[datetime | None, Query(description="断线前最后见到的时刻")] = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_LIMIT)] = 50,
) -> NotificationListResponse:
    rows, unread = await svc.list_notifications(
        db, recipient_id=actor.user_id, after=after, limit=limit
    )
    return NotificationListResponse(
        items=[_to_item(r) for r in rows], unread_count=unread
    )


@router.put(
    "/notifications/{notification_id}/read",
    response_model=NotificationItemResponse,
    summary="标记已读（幂等）",
)
async def mark_notification_read(
    notification_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> NotificationItemResponse:
    row = await svc.mark_read(
        db, recipient_id=actor.user_id, notification_id=notification_id
    )
    return _to_item(row)
