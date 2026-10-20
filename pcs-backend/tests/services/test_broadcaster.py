"""P9A C2：Redis pub/sub 推送（ADR-0049 §⑤ 的四条约束）。

## 为什么这些测试用**真 Redis**而不是 fake

ADR-0049 §⑤：进程内 broadcaster 在多 worker 下会让连接到 A 的用户收不到 B
产生的通知，**且不报错** —— 与 TODO-047 同形状（进程内 `hash()` 做锁键）。
而 dev 单 uvicorn 进程会掩盖它。

「同一个 fake 实例的两个连接」测的是「fake 上的 pub/sub 能否工作」，
**不是跨进程**。⇒ 本文件用 `docker compose up redis` 起真 Redis，
worker A = `UserSubscriptionRegistry`，worker B = `Broadcaster`，
两者是**两个独立进程对象**，只共享 Redis。

Redis 不可用时整文件 skip —— 但那会让「本机没起 Redis」看起来像「测试通过」。
所以 `redis_available` fixture 会显式告诉你 skip 原因。
"""
from __future__ import annotations

import asyncio
import json
import uuid

import pytest
import redis.asyncio as aioredis

from app.services.broadcaster import (
    REALTIME_REASONS,
    Broadcaster,
    UserSubscriptionRegistry,
    channel_name,
    get_broadcaster,
    set_broadcaster,
)

REDIS_URL = "redis://localhost:6379/9"


def _redis_up() -> bool:
    try:
        r = aioredis.Redis.from_url(REDIS_URL, socket_connect_timeout=1)
        r.ping()
    except Exception:  # noqa: BLE001
        return False
    return True


@pytest.fixture
def real_redis():
    if not _redis_up():
        pytest.skip("真 Redis 未运行（docker compose up redis）—— 跨进程推送无法用 fake 证明")
    yield REDIS_URL


async def _subscribe_one(registry: UserSubscriptionRegistry, user_id):
    """注册一个 sink，返回 (sink, future)。future 在收到第一条消息时兑现。"""
    fut: asyncio.Future = asyncio.get_running_loop().create_future()

    async def sink(message: dict) -> None:
        if not fut.done():
            fut.set_result(message)

    await registry.add(user_id, sink)
    return sink, fut


# --------------------------------------------------------------------------
# 约束 4 + 「必须跨进程」：B 发布的，A 上连着的该用户收到
# --------------------------------------------------------------------------


async def test_push_crosses_worker_boundary(real_redis):
    """约束：跨进程。

    ⚠️ **不是「同一个 fake 实例的两个连接」**（2026-10-19 委员会建议 3）——
    同一个 fake 共享同一份存储，测的是「fake 上的 pub/sub 能否工作」，
    不是跨进程。这正是 TODO-047 的失败形状：单进程全绿，多 worker 静默失效。

    本测试用的是**真 Redis**（方案 b，唯一能证明跨进程的方式）。
    """
    user_id = uuid.uuid4()
    registry_a = UserSubscriptionRegistry(real_redis)  # worker A
    broadcaster_b = Broadcaster(real_redis)  # worker B
    try:
        sink, fut = await _subscribe_one(registry_a, user_id)
        await broadcaster_b.publish(user_id, {"notification_id": str(uuid.uuid4())})
        msg = await asyncio.wait_for(fut, timeout=5)
        assert msg["notification_id"] is not None
    finally:
        await registry_a.aclose()
        await broadcaster_b.aclose()


async def test_multiple_sinks_for_same_user_all_receive(real_redis):
    """约束 4：单用户多设备 → 同 channel 多订阅者都收到。"""
    user_id = uuid.uuid4()
    registry_a = UserSubscriptionRegistry(real_redis)
    broadcaster_b = Broadcaster(real_redis)
    try:
        got: list[uuid.UUID] = []
        events = [asyncio.Event() for _ in range(3)]

        def make_sink(i: int):
            async def sink(_message: dict) -> None:
                got.append(i)
                events[i].set()

            return sink

        for i in range(3):
            await registry_a.add(user_id, make_sink(i))
        await broadcaster_b.publish(user_id, {"n": 1})
        await asyncio.wait_for(asyncio.gather(*(e.wait() for e in events)), timeout=5)
        assert sorted(got) == [0, 1, 2]
    finally:
        await registry_a.aclose()
        await broadcaster_b.aclose()


async def test_other_users_connection_does_not_receive(real_redis):
    """channel 按 `recipient_id` 分（约束 4）—— 别人的通知不串台。
    串台在这里不是「多收一条」，是**泄露**。"""
    mine, theirs = uuid.uuid4(), uuid.uuid4()
    registry_a = UserSubscriptionRegistry(real_redis)
    broadcaster_b = Broadcaster(real_redis)
    try:
        _, their_fut = await _subscribe_one(registry_a, theirs)
        received: list[dict] = []
        events = asyncio.Event()

        async def sink(m):
            received.append(m)
            events.set()

        await registry_a.add(mine, sink)
        await broadcaster_b.publish(theirs, {"secret": "not-yours"})
        await asyncio.wait_for(their_fut, timeout=5)
        await asyncio.sleep(0.2)  # 给「不该收到」留出到达时间
        assert received == [], "A 用户收到了 B 用户的通知"
    finally:
        await registry_a.aclose()
        await broadcaster_b.aclose()


# --------------------------------------------------------------------------
# 约束 1：pub/sub 不持久化（这是定义，不是缺陷）
# --------------------------------------------------------------------------


async def test_messages_published_with_no_subscriber_are_not_buffered(real_redis):
    """**不得**把「WS 推送成功」当作「通知已送达」的判据（ADR-0049 §⑤ 约束 1）。

    没有订阅者时消息直接消失 —— 兜底是 `notifications` 表 + `GET /notifications`。
    这条测试把「不持久化」钉成契约，将来若有人偷偷加缓冲，这条会红。
    """
    user_id = uuid.uuid4()
    broadcaster = Broadcaster(real_redis)
    try:
        await broadcaster.publish(user_id, {"before": "no subscriber"})
        registry = UserSubscriptionRegistry(real_redis)
        try:
            _, fut = await _subscribe_one(registry, user_id)
            with pytest.raises(asyncio.TimeoutError):
                await asyncio.wait_for(fut, timeout=1)
        finally:
            await registry.aclose()
    finally:
        await broadcaster.aclose()


# --------------------------------------------------------------------------
# 约束 3：订阅端必须独立连接
# --------------------------------------------------------------------------


async def test_subscription_uses_separate_connection_from_publisher(real_redis):
    """订阅会阻塞，不能与 ARQ 的 BLPOP 共用同一连接（ADR-0049 §⑤ 约束 3）。

    断言「订阅连接不是发布用的那个 client 对象」—— 不是「有没有连上」。
    """
    broadcaster = Broadcaster(real_redis)
    registry = UserSubscriptionRegistry(real_redis)
    try:
        await registry.add(uuid.uuid4(), lambda _m: asyncio.sleep(0))
        sub_conn = await registry._sub_client()
        assert sub_conn is not broadcaster._client
        assert sub_conn is not None
    finally:
        await registry.aclose()
        await broadcaster.aclose()


# --------------------------------------------------------------------------
# 约束 2 + §⑥：降级可观测
# --------------------------------------------------------------------------


async def test_broadcaster_records_degraded_state_when_redis_unreachable():
    """发布失败要留下可读标志（ADR-0049 §⑤ 约束 2 + §⑥）。
    ⚠️ 不得静默降级 —— 用户不知道自己在轮询，会以为推送坏了。"""
    broadcaster = Broadcaster("redis://127.0.0.1:6399/0")  # 无人监听
    try:
        await broadcaster.publish(uuid.uuid4(), {"n": 1})
        assert broadcaster.status == "degraded"
        assert broadcaster.reason == "redis_unavailable"
        assert broadcaster.reason in REALTIME_REASONS
    finally:
        await broadcaster.aclose()


async def test_realtime_reason_is_enum_not_free_string():
    """§⑥ 约束 3：`"Redis is down"` / `"redis_down"` / `"unavailable"`
    都是自由发挥，前端无法可靠判断。枚举才是契约。"""
    assert set(REALTIME_REASONS) == {
        "redis_unavailable",
        "redis_timeout",
        "pubsub_error",
    }, "realtime_reason 的枚举值集被改动 —— 前端按值判断，改了要同步"


async def test_publish_failure_does_not_raise():
    """降级不得把业务请求带崩：写侧已经落库，推送失败只该让用户改轮询。"""
    broadcaster = Broadcaster("redis://127.0.0.1:6399/0")
    try:
        await broadcaster.publish(uuid.uuid4(), {"n": 1})  # 不抛
        assert broadcaster.status == "degraded"
    finally:
        await broadcaster.aclose()


async def test_broadcaster_recovers_to_ok_after_success(real_redis):
    """降级状态必须能自愈，否则一次抖动就永久 degraded。"""
    broadcaster = Broadcaster("redis://127.0.0.1:6399/0")
    broadcaster._client = aioredis.Redis.from_url(real_redis)
    try:
        await broadcaster.publish(uuid.uuid4(), {"n": 1})
        assert broadcaster.status == "ok"
        assert broadcaster.reason is None
    finally:
        await broadcaster.aclose()


def test_status_defaults_to_ok_and_reason_to_none(real_redis):
    """还没发过任何消息时不能自称 degraded —— 否则 /health 一启动就报故障。"""
    b = Broadcaster(real_redis)
    assert b.status == "ok"
    assert b.reason is None


# --------------------------------------------------------------------------
# channel 命名（约束 4）
# --------------------------------------------------------------------------


def test_channel_is_namespaced_by_recipient_id():
    """`ws:notify:{user_id}`（ADR-0049 §⑤ 约束 4）。"""
    u = uuid.uuid4()
    assert channel_name(u) == f"ws:notify:{u}"


async def test_publish_sends_json_serialisable_body(real_redis):
    """消息体是 JSON 字符串 —— 非 JSON 可序列化的载荷会在推送时炸，
    而通知**已经落库**了：用户看得到铃铛，推送却静默失败。"""
    user_id = uuid.uuid4()
    registry = UserSubscriptionRegistry(real_redis)
    broadcaster = Broadcaster(real_redis)
    try:
        _, fut = await _subscribe_one(registry, user_id)
        await broadcaster.publish(user_id, {"a": 1, "b": None})
        msg = await asyncio.wait_for(fut, timeout=5)
        assert isinstance(msg, dict)
        json.dumps(msg)  # 可再序列化
    finally:
        await registry.aclose()
        await broadcaster.aclose()


# --------------------------------------------------------------------------
# 进程级单例：/health 读的就是它
# --------------------------------------------------------------------------


def test_broadcaster_singleton_is_process_local_and_replaceable():
    """`/health` 零额外探测 —— 它读的就是这个单例的标志位。"""
    b = Broadcaster("redis://localhost:6379/9")
    try:
        set_broadcaster(b)
        assert get_broadcaster() is b
    finally:
        set_broadcaster(None)
