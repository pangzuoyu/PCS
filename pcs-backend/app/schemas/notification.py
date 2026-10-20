"""通知读 / 标已读 API 的响应 schema（SPEC P9A-NOT-001/005）。

`detail_json` 走 `NotificationDetail` 而不是 `dict` —— 自由 dict 在 OpenAPI 里
是**无属性 object**，即 P9A-DLV-010 的裸字段，前端据此生成不了类型
（基线 71，只拦倒退）。
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.services.notifications.payload import NotificationDetail


class NotificationItemResponse(BaseModel):
    """单条通知。"""

    model_config = ConfigDict(from_attributes=True)

    notification_id: uuid.UUID
    kind: str = Field(description="NotificationKind 四值之一")
    title: str
    body: str
    detail: NotificationDetail | None = None
    created_at: datetime
    read_at: datetime | None = Field(default=None, description="NULL = 未读")


class NotificationListResponse(BaseModel):
    """通知列表。

    `unread_count` 与 `items` 都走 ADR-0049 §③ 的部分索引
    `ix_notifications_recipient_unread (recipient_id, read_at) WHERE read_at IS NULL`
    —— 铃铛上的红点数字正是这个索引的用途。
    """

    items: list[NotificationItemResponse]
    unread_count: int = Field(description="未读总数（铃铛红点）")
