"""`InAppChannel` —— 本版唯一的通知通道（ADR-0049 §①）。

## 职责边界

- **做**：写 `notifications` 一行。这是通知的**真值来源**。
- **不做**：WebSocket 推送。**通道不应该知道 WebSocket 存在** ——
  一个「邮件通道」里出现 WebSocket 调用是荒谬的，而本版的唯一实现是站内信。

⚠️ **但推送不能因此缺席**。ADR §① 明写推送的接线义务在本版：
写侧在 `deliver()` 成功后另行通知 broadcaster（接线在包外的 `notify.py`）。
「登录时轮询能看到」只是降级路径，不能当成推送已实现。

## 写入侧唯一性

本表**只能**经这里写入（ADR-0049 §①）。触发点可以有多个，写入点只有一个 ——
多写入点意味着将来有人绕过通道抽象直接插行，而那正是 §① 禁止的「临时 if」。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification
from app.services.notifications.channel import DeliveryResult
from app.services.notifications.payload import NotificationDetail, NotificationPayload


class InAppChannel:
    """站内信通道：只写 `notifications` 表。

    ⚠️ `db` 走**构造注入**而不是 `deliver(payload, db)` 的第二参数 ——
    ADR §① 把协议签名钉死为 `deliver(self, payload)`，多一个参数就不是
    那个协议了，而协议签名正是「将来接邮件时签名对不对」的判据。
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def deliver(self, payload: NotificationPayload) -> DeliveryResult:
        # 再验一次：绕过 `from_detail` 直接塞自由 dict 时在这里挡住。
        # 不静默丢弃未知键 —— 见 payload.py 模块 docstring。
        detail = NotificationDetail.model_validate(payload.meta)

        row = Notification(
            notification_id=payload.notification_id,
            recipient_id=payload.recipient_id,
            kind=payload.kind,
            title=payload.title,
            body=payload.body,
            # mode="json"：UUID 转字符串后再落库。SQLite 下 JSONB 走 stdlib
            # json.dumps，直接塞 UUID 会抛 "Object of type UUID is not JSON
            # serializable"；PG 的 psycopg 适配器能收 UUID，于是**只有 SQLite
            # 单测炸、真库绿** —— 与 CLAUDE.md 漂移盲区同一形状。
            detail_json=detail.model_dump(exclude_none=True, mode="json") or None,
            created_by=detail.actor_id,
        )
        self._db.add(row)
        await self._db.flush()
        return DeliveryResult(delivered=True)
