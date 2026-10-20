"""通知载荷与 `detail_json` 的字段级 schema（ADR-0049 §① / P9A-DLV-010）。

## 为什么有 `NotificationDetail` 这一层

ADR §① 的 `NotificationPayload.meta` 是 `dict[str, Any]`（通道无关的附加上下文）。
若它一路裸存进 DB，`detail_json` 在 OpenAPI 里就是一个**无属性 object** ——
即 P9A-DLV-010 的裸字段，前端无法据此生成类型。

⇒ 两道防线：
1. `NotificationPayload.from_detail()` 是**构造入口**，要求传 `NotificationDetail`
   而不是 dict —— 类型错误在触发点就报，不在写入点。
2. `InAppChannel.deliver()` 写入前**再验一次** —— 谁要是绕过 1 直接构造
   `NotificationPayload(meta={...})`，写入侧仍会挡住。

不静默丢弃未知键：丢弃会让「字段名拼错了」看起来像成功，
而拼错的字段名恰好是最容易犯、也最难发现的错误。
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from app.models.notification import NotificationKind


class NotificationDetail(BaseModel):
    """`notifications.detail_json` 的字段级 schema（P9A-DLV-010）。

    `extra="forbid"` 是这个模型存在的意义：不 forbid 的模型等于没有 schema。
    """

    model_config = ConfigDict(extra="forbid")

    project_id: uuid.UUID | None = None
    deliverable_id: uuid.UUID | None = None
    deliverable_version_id: uuid.UUID | None = None
    workflow_type: str | None = None
    step_order: int | None = None
    actor_id: uuid.UUID | None = None
    actor_name: str | None = None
    reason: str | None = None


@dataclass(frozen=True)
class NotificationPayload:
    """通道无关的通知载荷（ADR-0049 §①）。

    **不是 ORM 对象，也不携带 `recipient: User`** —— 收件人只在
    `recipient_id` 里。否则将来的邮件通道要在 ORM 会话里取用户，
    多一个失败面。
    """

    notification_id: uuid.UUID
    recipient_id: uuid.UUID
    kind: str
    title: str
    body: str
    created_at: datetime
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_detail(
        cls,
        *,
        recipient_id: uuid.UUID,
        kind: NotificationKind,
        title: str,
        body: str,
        detail: NotificationDetail | None = None,
        notification_id: uuid.UUID | None = None,
        created_at: datetime | None = None,
    ) -> NotificationPayload:
        """从 `NotificationDetail` 构造 —— 本包的推荐构造入口。

        `notification_id` 必须在落库前就定下来：读 API 与推送都按它做
        tiebreaker（同一批写入的时间戳可能相同）。
        """
        return cls(
            notification_id=notification_id or uuid.uuid4(),
            recipient_id=recipient_id,
            kind=str(kind),
            title=title,
            body=body,
            created_at=created_at or datetime.now(UTC),
            meta=(detail.model_dump(exclude_none=True) if detail else {}),
        )
