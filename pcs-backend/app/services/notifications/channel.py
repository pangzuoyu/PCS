"""`NotificationChannel` 协议与 `DeliveryResult`（ADR-0049 §①）。

## 为什么协议**只有**一个方法

ADR §① 约束 2：「预先猜测下一版的需求 = 重蹈空壳覆辙」。`can_deliver` /
`on_failure` / 批量接口都是为还不存在的第二通道预想的，等接邮件时按真实
需求加。测试 `test_protocol_has_exactly_one_method` 钉住这一点。

## `delivered` / `reason` 是本版唯一一处「为下一版预留」

ADR §① 明写理由：邮件的典型失败是 SMTP 拒收。若协议里没有这两个字段，
接邮件的人第一反应就是在 service 里加 `try/except` 记日志 ——
那正是 §① 明令禁止的「临时 if」。有了 `DeliveryResult`，失败是一条
**返回值**，不是一段散在调用点的异常处理。

⚠️ `reason` 是 `str | None` 而**不是枚举**（ADR §① 的 DTO 逐字如此）。
本版不存在未送达路径，此刻就定枚举值集 = 又一次预想未来的需求
（同约束 2）。枚举契约落在 ADR §⑥ 的 `realtime_reason` 上 ——
那是**已存在的**降级路径，不是假设出来的。
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from app.services.notifications.payload import NotificationPayload


@dataclass(frozen=True)
class DeliveryResult:
    """一次投递的结果。失败是一条返回值，不是一段散在调用点的异常处理。"""

    delivered: bool
    reason: str | None = None


@runtime_checkable
class NotificationChannel(Protocol):
    """通知通道。本版只有站内信一个实现（ADR-0049 §①）。"""

    async def deliver(self, payload: NotificationPayload) -> DeliveryResult: ...
