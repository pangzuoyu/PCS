"""通知的**唯一写侧入口**（ADR-0049 §① + 用户 2026-10-20 裁决）。

## 同步写（本轮裁决）

`deliver()` 在请求内直接写 `notifications` 行，成功后通知 broadcaster 推送。

**为什么不是异步**：ADR §① 的原论证「异步以免阻塞外部通道的延迟」已随邮件移除
而失效 —— 本版没有外部投递。剩下的理由只剩「不阻塞写库」，而事件源全是用户低频
动作（签署 / 审批），写压力不构成阻塞理由。异步会额外引入「已入队未送达」的窗口
（ADR §后果 已预告），换不来任何东西。

## 推送失败**不得**影响业务请求

`Broadcaster.publish()` 吞掉异常并只把 `status` 置 degraded。推��失败时
通知**仍然落库**，用户下次轮询能看到；调用方（签署/审批端点）不感知。

反过来做 —— 推送失败就抛 —— 后果是签署已提交却返 500，用户以为没签上，
于是重签一次。**真正的事故是这么造出来的。**

## 模块边界的验证

本模块 import `broadcaster` 是**允许**的 —— 「通道不该知道 WebSocket 存在」
说的是 `in_app.py`，不是「写侧不许推送」。ADR §① 明写「推送的接线义务在本版」，
接线点就在这里。
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import NotificationKind
from app.services.notifications.channel import DeliveryResult
from app.services.notifications.in_app import InAppChannel
from app.services.notifications.payload import NotificationDetail, NotificationPayload
from app.services.notification_recipients import resolve_role_recipients


async def notify(
    db: AsyncSession,
    *,
    recipient_id: uuid.UUID,
    kind: NotificationKind,
    title: str,
    body: str,
    detail: NotificationDetail | None = None,
) -> DeliveryResult:
    """写一条通知并尝试推送。返回 `DeliveryResult`。"""
    payload = NotificationPayload.from_detail(
        recipient_id=recipient_id, kind=kind, title=title, body=body, detail=detail
    )
    result = await InAppChannel(db).deliver(payload)
    if result.delivered:
        await _push(payload)
    return result


async def notify_role(
    db: AsyncSession,
    *,
    role: str,
    kind: NotificationKind,
    title: str,
    body: str,
    detail: NotificationDetail | None = None,
    project_id: uuid.UUID | None = None,
    exclude_user_ids: tuple[uuid.UUID, ...] = (),
) -> list[DeliveryResult]:
    """给持有 `role` 的每个用户各发一条。没人时返回空列表，**不抛**。

    抛会把「暂时没人有这个角色」变成 500 —— 那不是错误，是一种状态。
    """
    recipients = await resolve_role_recipients(
        db, role=role, project_id=project_id, exclude_user_ids=exclude_user_ids
    )
    out: list[DeliveryResult] = []
    for uid in recipients:
        out.append(
            await notify(
                db,
                recipient_id=uid,
                kind=kind,
                title=title,
                body=body,
                detail=detail,
            )
        )
    return out


async def _push(payload: NotificationPayload) -> None:
    """推给该用户当前打开的连接。失败已被 `publish` 吞掉并置 degraded。"""
    from app.services.broadcaster import get_broadcaster

    message: dict[str, Any] = {
        "notification_id": str(payload.notification_id),
        "recipient_id": str(payload.recipient_id),
        "kind": payload.kind,
        "title": payload.title,
        "body": payload.body,
        "created_at": payload.created_at.isoformat(),
        "detail": payload.meta or None,
    }
    await get_broadcaster().publish(payload.recipient_id, message)
