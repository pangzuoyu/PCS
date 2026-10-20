"""Redis pub/sub 实时推送（ADR-0049 §⑤）。

## 为什么必须是 Redis pub/sub 而不是进程内

进程内 broadcaster 在多 worker 下会让**连接到 A 的用户收不到 B 产生的通知，
且不报错**。这与 TODO-047 同形状（进程内 `hash()` 做锁键：单进程全绿、
多进程静默失效），而 dev 单 uvicorn 进程（`README.md` 无 `--workers`）会
掩盖它 —— P10 容量规格已按 4 workers 设计。

**禁止用「文档限制单进程部署」替代跨进程正确性**：那等于制造一个新缺陷
并复制 TODO-047 的教训。Redis pub/sub 单 worker 与多 worker 行为一致。

## 三条硬约束的落点

1. **pub/sub 不持久化** —— 这是**定义不是缺陷**。兜底是 `notifications` 表
   + `GET /notifications?after=<last_seen>`。⇒ **不得**把「WS 推送成功」
   当作「通知已送达」的判据。
2. **降级必须可观测** —— `status` / `reason` 是 `/health` 的
   `realtime` / `realtime_reason` 的**唯一数据源**，且 `/health` 零额外探测。
3. **订阅端独立连接** —— 发布端可复用 ARQ 的连接池（普通命令）；
   **订阅会阻塞，不能与 ARQ 的 `BLPOP` 共用同一连接**。

## channel 命名与分片决策点

`ws:notify:{user_id}`（ADR-0049 §⑤ 约束 4）。每个 worker 只订阅
「本 worker 上有连接的用户」的 channel，避免 N 倍无效消息转发。

📌 **分片决策点**：连接数超过约 5000 时再考虑按 hash 分片。现在不做 ——
提前分片是 YAGNI，但**阈值与触发条件写在这里**，免得将来无人记得。
"""
from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
import redis.exceptions as redis_exc

logger = logging.getLogger(__name__)

CHANNEL_PREFIX = "ws:notify:"

#: §⑥ 约束 3：`realtime_reason` 是**枚举**，不是自由字符串。
#: 自由字符串（"Redis is down" / "redis_down" / "unavailable"）会让前端
#: 无法可靠判断。`realtime == "ok"` ⇒ `realtime_reason is None`。
REALTIME_REASONS = ("redis_unavailable", "redis_timeout", "pubsub_error")

_Sink = Callable[[dict[str, Any]], Awaitable[None]]


def channel_name(recipient_id: uuid.UUID) -> str:
    """channel 按 `recipient_id` 分（ADR-0049 §⑤ 约束 4）。"""
    return f"{CHANNEL_PREFIX}{recipient_id}"


def _classify(exc: Exception) -> str:
    """把 Redis 异常映射到 `REALTIME_REASONS` 里的一个值。"""
    if isinstance(exc, (asyncio.TimeoutError, redis_exc.TimeoutError)):
        return "redis_timeout"
    if isinstance(exc, redis_exc.ConnectionError):
        return "redis_unavailable"
    return "pubsub_error"


class Broadcaster:
    """发布端 + 降级标志位。

    `status` / `reason` 由本对象维护，`/health` **只读它们**——
    不做任何探测（§⑥ 约束 1：检测不得阻塞 `/health` 主路径，
    `/health` 已经在同步 `check_database_async()`，不能再叠第二个阻塞依赖）。
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._client: aioredis.Redis | None = aioredis.Redis.from_url(redis_url)
        self.status: str = "ok"
        self.reason: str | None = None

    async def publish(self, recipient_id: uuid.UUID, message: dict[str, Any]) -> None:
        """发布一条通知。**失败不抛** —— 写侧已落库，推送失败只该让用户改轮询。

        抛出去会把业务请求带崩：签署已经提交，却因为推送失败而回 500，
        用户看到的是「签署失败」，于是重签一次 —— 真正的事故是这么造出来的。
        """
        try:
            body = json.dumps(message, default=str)
            await self._client.publish(channel_name(recipient_id), body)
        except Exception as e:  # noqa: BLE001 — Redis 各种连接/序列化异常
            self.status = "degraded"
            self.reason = _classify(e)
            logger.error(
                "通知推送失败，降级到轮询（channel=%s, %s: %s）",
                channel_name(recipient_id),
                type(e).__name__,
                e,
            )
            return
        self.status, self.reason = "ok", None

    async def aclose(self) -> None:
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.aclose()


class UserSubscriptionRegistry:
    """订阅端 —— **每个 worker 一份**。

    懒订阅：只有当本 worker 上真的有连接的用户才建订阅。断开且该用户在本
    worker 上再无连接时，关闭订阅连接。
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        # ⚠️ 独立连接（约束 3）。**不能**复用 Broadcaster 的 client ——
        # 订阅会阻塞，与普通命令共用连接会把发布端一起卡死。
        self._sub: aioredis.Redis | None = None
        # ⚠️ **每个用户一个 PubSub**，不是一个 PubSub 订阅所有 channel。
        # 单个 PubSub 上的并发 `get_message()` 不是安全的：两个 pump 任务会
        # 互相抢同一条消息，其中一个还可能被对方的 cancel 波及
        # （实测：第二个用户上线后，第一个用户的 pump 抛 CancelledError，
        #   该用户的推送**静默停止** —— 正是 ADR-0049 §⑤ 要防的那类失败）。
        self._pub_subs: dict[uuid.UUID, aioredis.client.PubSub] = {}
        self._sinks: dict[uuid.UUID, list[_Sink]] = {}
        self._tasks: dict[uuid.UUID, asyncio.Task] = {}

    async def _sub_client(self) -> aioredis.Redis:
        if self._sub is None:
            self._sub = aioredis.Redis.from_url(self._redis_url)
        return self._sub

    async def add(self, user_id: uuid.UUID, sink: _Sink) -> None:
        self._sinks.setdefault(user_id, []).append(sink)
        if user_id not in self._tasks:
            # redis-py 的 asyncio 版 `pubsub()` 返回 PubSub 对象本身，不是协程。
            pubsub = (await self._sub_client()).pubsub()
            await pubsub.subscribe(channel_name(user_id))
            self._pub_subs[user_id] = pubsub
            self._tasks[user_id] = asyncio.create_task(self._pump(user_id))

    async def remove(self, user_id: uuid.UUID, sink: _Sink) -> None:
        sinks = self._sinks.get(user_id)
        if not sinks:
            return
        with contextlib.suppress(ValueError):
            sinks.remove(sink)
        if sinks:
            return
        self._sinks.pop(user_id, None)
        task = self._tasks.pop(user_id, None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        pubsub = self._pub_subs.pop(user_id, None)
        if pubsub is not None:
            with contextlib.suppress(Exception):
                await pubsub.aclose()

    async def _pump(self, user_id: uuid.UUID) -> None:
        """把该 channel 上的消息扇出给本 worker 上的所有 sink。"""
        pubsub = self._pub_subs[user_id]
        while True:
            try:
                msg = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=1.0
                )
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001
                logger.error(
                    "订阅通道 %s 中断：%s: %s", channel_name(user_id), type(e).__name__, e
                )
                return
            if msg is None or msg.get("type") != "message":
                continue
            try:
                data = json.loads(msg["data"])
            except (TypeError, ValueError):
                logger.error("通知消息不是合法 JSON，已丢弃：%r", msg.get("data"))
                continue
            for sink in list(self._sinks.get(user_id, [])):
                try:
                    await sink(data)
                except Exception:  # noqa: BLE001 — 一个坏 sink 不能带走其他人
                    logger.exception("推送 sink 失败（user=%s）", user_id)

    async def aclose(self) -> None:
        for user_id in list(self._tasks):
            for sink in list(self._sinks.get(user_id, [])):
                await self.remove(user_id, sink)
        if self._sub is not None:
            with contextlib.suppress(Exception):
                await self._sub.aclose()
            self._sub = None


# --------------------------------------------------------------------------
# 进程级单例 —— `/health` 读的就是它（零额外探测）
# --------------------------------------------------------------------------

_broadcaster: Broadcaster | None = None


def get_broadcaster() -> Broadcaster:
    global _broadcaster
    if _broadcaster is None:
        from app.core.config import get_settings

        _broadcaster = Broadcaster(get_settings().redis_url)
    return _broadcaster


def set_broadcaster(b: Broadcaster | None) -> None:
    """测试与 lifespan 用的注入口。传 None 复位。"""
    global _broadcaster
    _broadcaster = b
