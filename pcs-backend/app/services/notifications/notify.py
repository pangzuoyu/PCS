"""通知的**唯一写侧入口**（ADR-0049 §① + 用户 2026-10-20 裁决）。

## 同步写 + **同一次提交**（本轮裁决）

写与推是**两步**，分属两个时刻：

```
pending = await notify(db, ...)   # 写行（flush）—— 同一事务，不提交
await db.commit()                  # 一次提交：业务变更 + 通知行
await publish(pending)             # 提交**之后**才推
```

**为什么不是异步**：ADR §① 的原论证「异步以免阻塞外部通道的延迟」已随邮件移除
而失效 —— 本版没有外部投递。剩下的理由只剩「不阻塞写库」，而事件源全是用户低频
动作（签署 / 审批），写压力不构成阻塞理由。异步会额外引入「已入队未送达」的窗口
（ADR §后果 已预告），换不来任何东西。

**为什么推送必须在提交之后**：提交前推送 ⇒ commit 失败时用户**已经**收到一条
会被回滚的通知（phantom notification）—— 铃铛响了，点进去 404。比没推更糟。

**为什么通知行必须与业务变更同一次提交**：两次提交意味着两个真相源 ——
业务变更已落库、通知行还没落库，两者之间进程挂掉 ⇒ 变更发生了但没人被告知。

## 推送失败**不得**影响业务请求

`Broadcaster.publish()` 吞掉异常并只把 `status` 置 degraded。推送失败时
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
from app.services.notification_recipients import resolve_role_recipients
from app.services.notifications.in_app import InAppChannel
from app.services.notifications.payload import NotificationDetail, NotificationPayload


async def notify(
    db: AsyncSession,
    *,
    recipient_id: uuid.UUID,
    kind: NotificationKind,
    title: str,
    body: str,
    detail: NotificationDetail | None = None,
) -> NotificationPayload:
    """写一行通知（**flush，不提交**），返回待推送的载荷。

    ⚠️ **本函数不推送。** 推送必须在**事务提交之后**做 ——
    ADR §① 同步写裁决承诺的是「同一次提交、同一套事务边界」。

    提交前推送的后果是 **phantom notification**：commit 因 DB 抖动失败 ⇒
    通知行回滚，但用户**已经**在 UI 上收到了那条推送，点进去却 404。
    （用户看得见、点不着 —— 比没推更糟。）

    调用方的形状：

    ```
    pending = await notify(db, ...)      # 写行（同一事务）
    await db.commit()                     # 一次提交，业务变更 + 通知行
    await publish(pending)                # 提交之后才推
    ```
    """
    payload = NotificationPayload.from_detail(
        recipient_id=recipient_id, kind=kind, title=title, body=body, detail=detail
    )
    result = await InAppChannel(db).deliver(payload)
    if not result.delivered:
        # 站内信写不进去 = 真值源写不进去 ⇒ 必须响亮。
        # （推送失败不走这里 —— 推送失败在 `publish` 里被吞掉并置 degraded。）
        raise RuntimeError(f"站内信写入失败：{result.reason}")
    return payload


async def notify_role(
    db: AsyncSession,
    *,
    role: str,
    kind: NotificationKind,
    title: str,
    body: str,
    detail: NotificationDetail | None = None,
    project_id: uuid.UUID,
    exclude_user_ids: tuple[uuid.UUID, ...] = (),
) -> list[NotificationPayload]:
    """给持有 `role` 的每个用户各发一条。没人时返回空列表，**不抛**。

    ⚠️ `project_id` **必填**：收件人 = 全局角色命中 **且** 有该项目授权的人。
    不给默认值是为了让「忘了传 ⇒ 越权泄漏」在类型层就不可能发生
    （bug-2030 的教训）。

    抛会把「暂时没人有这个角色」变成 500 —— 那不是错误，是一种状态。
    """
    recipients = await resolve_role_recipients(
        db, role=role, project_id=project_id, exclude_user_ids=exclude_user_ids
    )
    out: list[NotificationPayload] = []
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


async def publish(payloads: list[NotificationPayload] | NotificationPayload) -> None:
    """在**事务提交之后**推送。失败只置 degraded，不抛。

    ⚠️ 忘记调用它的后果是「通知在库里但没推」—— 用户下次轮询能看到。
    这是**可接受**的失败方向（真值源是表，WS 只是及时性通道）。
    反过来（推了但没提交）才是 phantom notification。
    """
    items = [payloads] if isinstance(payloads, NotificationPayload) else list(payloads)
    for payload in items:
        await _push(payload)


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
