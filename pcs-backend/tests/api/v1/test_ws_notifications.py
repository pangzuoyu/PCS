"""P9A C2：WebSocket 推送 + 断线兜底 API + `/health` 降级信号
（ADR-0049 §⑤ / §⑥ / SPEC P9A-NOT-006）。

## 三次「假绿」的教训在这个文件里的落法

1. **404 只断言状态码** 会在端点不存在时也绿（FastAPI 对未注册路径返 404）。
   ⇒ 所有 404 断言都**断言 error code**。
2. **`/health` 的 `realtime` 若做实时探测**，测试会因「Redis 恰好可用」而绿，
   生产上 Redis 慢时 `/health` 就跟着慢。⇒ 用一个**黑洞地址**证明零探测。
3. **WS 推送「连上了就算推送通了」** 是假绿。⇒
   `test_ws_delivers_notification_published_by_another_worker` 端到端走真 Redis。
"""
from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

import pytest
import redis.asyncio as aioredis
from fastapi.testclient import TestClient
from sqlalchemy import select, update

from app.core.security import create_access_token
from app.main import create_app
from app.models.notification import Notification, NotificationKind
from app.services.broadcaster import Broadcaster, UserSubscriptionRegistry, set_broadcaster
from app.services.notifications.in_app import InAppChannel
from app.services.notifications.payload import NotificationDetail, NotificationPayload

REDIS_URL = "redis://localhost:6379/9"


def _redis_up() -> bool:
    async def _ping():
        r = aioredis.Redis.from_url(REDIS_URL, socket_connect_timeout=1)
        await r.ping()
        await r.aclose()

    try:
        asyncio.run(_ping())
    except Exception:  # noqa: BLE001
        return False
    return True


def _token(user_id: uuid.UUID) -> str:
    return create_access_token(
        subject=f"u-{user_id}", role="DESIGNER", extra={"user_id": str(user_id)}
    )


# ==========================================================================
# 断线兜底 API（ADR-0049 §⑤ 约束 1）
# ==========================================================================


async def _seed(db, recipient: uuid.UUID, *, count: int, age: timedelta = timedelta(0)):
    rows = []
    for i in range(count):
        p = NotificationPayload.from_detail(
            recipient_id=recipient,
            kind=NotificationKind.SIGN_COMPLETED,
            title=f"通知 {i}",
            body="B",
            detail=NotificationDetail(),
        )
        await InAppChannel(db).deliver(p)
        rows.append(p)
    if age:
        # created_at 由 DB 的 server_default 填，单测里 SQLite 用 Python default，
        # 所以这里用 UPDATE 回填，模拟「这些是 1 小时前的」。
        await db.execute(
            update(Notification)
            .where(Notification.recipient_id == recipient)
            .values(created_at=datetime.now(UTC) - age)
        )
    await db.commit()
    return rows


async def test_messages_during_disconnect_are_recoverable_via_api(client, db, user_id):
    """约束 1：pub/sub 不持久化 ⇒ 断线期间的消息由 `notifications` 表兜底。

    这里**没有任何 WebSocket 连接** —— 正是断线场景本身。
    """
    await _seed(db, user_id, count=3)
    resp = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["items"]) == 3


async def test_after_excludes_older_notifications(client, db, user_id):
    """`after=<last_seen>` 是断线重连的翻页游标 —— 旧消息不该重复推给用户。"""
    now = datetime.now(UTC)
    for i, (title, age) in enumerate([("旧", timedelta(hours=2)), ("新", timedelta(0))]):
        p = NotificationPayload.from_detail(
            recipient_id=user_id,
            kind=NotificationKind.SIGN_COMPLETED,
            title=title,
            body="B",
            detail=NotificationDetail(),
        )
        await InAppChannel(db).deliver(p)
        await db.execute(
            update(Notification)
            .where(Notification.notification_id == p.notification_id)
            .values(created_at=now - age)
        )
    await db.commit()

    # ⚠️ `+` 在 query string 里是空格，必须编码成 %2B —— 否则 Pydantic 收到
    # `2026-10-20T01:03:54.557965 00:00` 并返 422。这是真实调用方会踩的坑。
    after_param = quote((now - timedelta(hours=1)).isoformat())
    resp = await client.get(
        f"/api/v1/notifications?after={after_param}",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    assert resp.status_code == 200, resp.text
    titles = [i["title"] for i in resp.json()["items"]]
    assert titles == ["新"], f"after 游标没起作用，返回了 {titles}"


async def test_get_notifications_returns_only_my_own(client, db, user_id):
    """通知列表按 `recipient_id` 鉴权。返回别人的通知是**泄露**，不是「多几条」。"""
    other = uuid.uuid4()
    await _seed(db, user_id, count=1)
    await _seed(db, other, count=2)
    resp = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["items"]) == 1


async def test_get_notifications_respects_limit(client, db, user_id):
    await _seed(db, user_id, count=5)
    resp = await client.get(
        "/api/v1/notifications?limit=2",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()["items"]) == 2


async def test_get_notifications_rejects_oversized_limit(client, user_id):
    """`limit=10000` 会把整个表拉出来 —— 上界是契约不是建议。"""
    resp = await client.get(
        "/api/v1/notifications?limit=10000",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    assert resp.status_code == 422, resp.text


async def test_get_notifications_requires_auth(client):
    resp = await client.get("/api/v1/notifications")
    assert resp.status_code == 401
    assert resp.json()["code"] == "MISSING_BEARER"


async def test_mark_read_sets_read_at(client, db, user_id):
    await _seed(db, user_id, count=1)
    row = (await db.execute(select(Notification))).scalars().one()
    resp = await client.put(
        f"/api/v1/notifications/{row.notification_id}/read",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["read_at"] is not None


async def test_mark_read_of_other_users_notification_is_404(client, db, user_id):
    """按 `recipient_id` 判归属；别人的通知返 **404**（不泄漏存在性）。

    ⚠️ 断言 **error code** 而不是状态码 —— FastAPI 对未注册路径也返 404，
    只断言状态码会在端点根本没注册时照样绿（本仓已踩过三次这种假绿）。
    """
    other = uuid.uuid4()
    await _seed(db, other, count=1)
    row = (await db.execute(select(Notification))).scalars().one()
    resp = await client.put(
        f"/api/v1/notifications/{row.notification_id}/read",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOTIFICATION_NOT_FOUND", resp.text


async def test_mark_read_of_nonexistent_id_is_404_with_same_code(client, user_id):
    """与「别人的通知」**同一个 code** —— 两者不可区分，否则就是存在性预言机。"""
    resp = await client.put(
        f"/api/v1/notifications/{uuid.uuid4()}/read",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    assert resp.status_code == 404
    assert resp.json()["code"] == "NOTIFICATION_NOT_FOUND", resp.text


async def test_mark_read_is_idempotent(client, db, user_id):
    """重复标已读不改 `read_at` —— 前端连点两次不该改变已读时刻。"""
    await _seed(db, user_id, count=1)
    row = (await db.execute(select(Notification))).scalars().one()
    h = {"Authorization": f"Bearer {_token(user_id)}"}
    first = await client.put(f"/api/v1/notifications/{row.notification_id}/read", headers=h)
    second = await client.put(f"/api/v1/notifications/{row.notification_id}/read", headers=h)
    assert first.status_code == second.status_code == 200
    assert first.json()["read_at"] == second.json()["read_at"]


async def test_mark_read_requires_auth(client, db, user_id):
    await _seed(db, user_id, count=1)
    row = (await db.execute(select(Notification))).scalars().one()
    resp = await client.put(f"/api/v1/notifications/{row.notification_id}/read")
    assert resp.status_code == 401


# ==========================================================================
# WebSocket 端点
# ==========================================================================


def test_ws_accepts_a_valid_token():
    """路由**确实存在**的正向证明。

    ⚠️ 没有这条，下面两条 `pytest.raises(Exception)` 会在**端点没注册**时
    也绿 —— WebSocket 握手对不存在的路径同样抛异常。这正是本仓反复踩到的
    「只断言失败形状就等于断言了功能不存在」（三次假绿之一）。
    """
    from starlette.websockets import WebSocketDisconnect  # noqa: F401  — 仅为文档化

    user_id = uuid.uuid4()
    with TestClient(create_app()) as client:
        with client.websocket_connect(
            f"/api/v1/ws/notifications?token={_token(user_id)}"
        ) as ws:
            ws.send_json({"type": "ping"})
            assert ws.receive_json()["type"] == "pong"


def test_ws_requires_a_token():
    """未鉴权的 WS 连接必须在**握手**就被拒。

    ⚠️ 浏览器 `WebSocket` API **不能设置请求头**，所以 token 走 query；
    但「query 里没 token」必须和「header 里没 token」一样被拒。

    ⚠️ 断言**具体异常 + close code**，不是 `pytest.raises(Exception)`：
    盲断异常在「端点根本没注册」时也绿（握手同样失败）——
    本仓已为这种假绿栽过三次。正向证明见 `test_ws_accepts_a_valid_token`。
    """
    from starlette.websockets import WebSocketDisconnect

    with TestClient(create_app()) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect("/api/v1/ws/notifications") as ws:
                ws.receive_text()
    assert exc.value.code == 1008, "未鉴权必须以 policy violation 关闭"


def test_ws_rejects_invalid_token():
    from starlette.websockets import WebSocketDisconnect

    with TestClient(create_app()) as client:
        with pytest.raises(WebSocketDisconnect) as exc:
            with client.websocket_connect(
                "/api/v1/ws/notifications?token=not-a-jwt"
            ) as ws:
                ws.receive_text()
    assert exc.value.code == 1008


@pytest.mark.skipif(not _redis_up(), reason="真 Redis 未运行（docker compose up redis）")
def test_ws_delivers_notification_published_by_another_worker():
    """端到端跨进程推送：连接在 worker A 上，发布在 worker B 上。

    这是 ADR-0049 §⑤「推送**必须**跨进程」的唯一端到端证明。
    dev 单进程会掩盖它 —— 进程内 broadcaster 在这个测试里根本不会被用到。
    """
    user_id = uuid.uuid4()
    registry = UserSubscriptionRegistry(REDIS_URL)

    async def _boot():
        # 先让 worker A 的订阅就位，再让 worker B 发布。
        ready = asyncio.Event()
        await registry.add(user_id, lambda _m: None)
        asyncio.get_running_loop().call_later(0.1, ready.set)
        await ready.wait()
        return True

    asyncio.run(_boot())

    broadcaster = Broadcaster(REDIS_URL)
    set_broadcaster(broadcaster)
    try:
        with TestClient(create_app()) as client:
            with client.websocket_connect(
                f"/api/v1/ws/notifications?token={_token(user_id)}"
            ) as ws:
                nid = str(uuid.uuid4())

                async def _publish():
                    await broadcaster.publish(
                        user_id,
                        {"notification_id": nid, "kind": "SIGN_COMPLETED"},
                    )

                asyncio.run(_publish())
                assert ws.receive_json()["notification_id"] == nid
    finally:
        set_broadcaster(None)
        asyncio.run(registry.aclose())
        asyncio.run(broadcaster.aclose())


# ==========================================================================
# `/health` 降级信号（ADR-0049 §⑥ / SPEC P9A-NOT-006）
# ==========================================================================


def test_health_realtime_reflects_broadcaster_without_blocking(monkeypatch):
    """§⑥ 约束 1：`/health` **读缓存标志，零额外探测**。

    用一个**黑洞地址**（10.255.255.1 不可路由）做 broadcaster：
    若 `/health` 真的去探活，它会挂在 socket 超时上；
    只读标志则立刻返回。⇒ 断言响应时间。
    """
    import app.api.v1.health as health_mod

    async def _ok() -> bool:
        return True

    monkeypatch.setattr(health_mod, "check_database_async", _ok)
    b = Broadcaster("redis://10.255.255.1:6379/0", )
    b.status, b.reason = "degraded", "redis_timeout"
    set_broadcaster(b)
    try:
        with TestClient(create_app()) as client:
            t0 = __import__("time").perf_counter()
            resp = client.get("/api/v1/health")
            elapsed = __import__("time").perf_counter() - t0
        assert resp.status_code == 200
        assert resp.json()["realtime"] == "degraded"
        assert resp.json()["realtime_reason"] == "redis_timeout"
        assert elapsed < 0.5, f"/health 耗时 {elapsed:.2f}s —— 它在探测而不是读标志"
    finally:
        set_broadcaster(None)


def test_health_returns_200_even_when_realtime_degraded(monkeypatch):
    """§⑥ 约束 2：状态码语义不得改变。

    `realtime` **仅供观测，不得用于 liveness / readiness** ——
    若 K8s 把它纳入 liveness probe，Redis 挂了会触发**服务重启循环**。
    """
    import app.api.v1.health as health_mod

    async def _ok() -> bool:
        return True

    monkeypatch.setattr(health_mod, "check_database_async", _ok)
    b = Broadcaster("redis://localhost:6379/9")
    b.status, b.reason = "degraded", "redis_unavailable"
    set_broadcaster(b)
    try:
        with TestClient(create_app()) as client:
            resp = client.get("/api/v1/health")
        assert resp.status_code == 200, resp.text
        # `status` 只反映 DB，realtime 降级**不得**把它拖成 degraded
        assert resp.json()["status"] == "ok"
        assert resp.json()["database"] == "up"
    finally:
        set_broadcaster(None)


def test_health_realtime_reason_is_null_when_ok(monkeypatch):
    """§⑥ 约束 3：`realtime == "ok"` ⇒ `realtime_reason is None`。
    反过来（有 reason 却 ok）会让前端无法判断该不该切轮询。"""
    import app.api.v1.health as health_mod

    async def _ok() -> bool:
        return True

    monkeypatch.setattr(health_mod, "check_database_async", _ok)
    b = Broadcaster("redis://localhost:6379/9")
    set_broadcaster(b)
    try:
        with TestClient(create_app()) as client:
            resp = client.get("/api/v1/health")
        assert resp.json()["realtime"] == "ok"
        assert resp.json()["realtime_reason"] is None
    finally:
        set_broadcaster(None)


def test_health_still_has_the_pre_existing_fields(monkeypatch):
    """扩字段不是换端点 —— 既有字段一个都不能少。"""
    import app.api.v1.health as health_mod

    async def _ok() -> bool:
        return True

    monkeypatch.setattr(health_mod, "check_database_async", _ok)
    with TestClient(create_app()) as client:
        body = client.get("/api/v1/health").json()
    assert {"status", "database", "realtime", "realtime_reason"} <= set(body)


async def test_old_detail_json_does_not_break_the_whole_list(client, db, user_id):
    """⚠️ F-5：`NotificationDetail` 是 `extra="forbid"` 的。

    将来若有人给该 schema **删/改名**一个字段，已落库的旧通知行里那个键
    就会让 `model_validate` 抛 `ValidationError` ⇒ `_to_item` 抛 ⇒
    **整个 `GET /notifications` 返 500**（一个人的旧数据让所有人看不了通知）。

    ⇒ 读路径必须兜住：坏的那一条降级成 `detail=None`，其余照常返回。
    """
    from app.models.notification import Notification as N

    db.add(
        N(
            notification_id=uuid.uuid4(),
            recipient_id=user_id,
            kind=NotificationKind.SIGN_COMPLETED,
            title="老通知",
            body="B",
            # 模拟「已删字段」的旧行
            detail_json={"some_removed_field": 1, "step_order": 3},
        )
    )
    await db.commit()

    resp = await client.get(
        "/api/v1/notifications",
        headers={"Authorization": f"Bearer {_token(user_id)}"},
    )
    assert resp.status_code == 200, resp.text
    item = resp.json()["items"][0]
    assert item["title"] == "老通知"
    assert item["detail"] is None


def test_lifespan_closes_the_redis_connections(monkeypatch):
    """⚠️ F-6：`/health` 与 WS 各自持有一条 Redis 连接，lifespan 结束时不关 ⇒
    每次优雅重启漏一条（或两条），K8s 滚动升级 N 次后撞 Redis `maxclients`。

    本仓在 `worker.py` 修过同类问题（ARQ cron 的 Redis 必须来自 settings，
    连错实例会静默连错）—— 这次漏的不是配置，是**关闭 hook**。
    """
    from app.api.v1 import ws as ws_mod
    from app.main import create_app
    from app.services.broadcaster import (
        Broadcaster,
        UserSubscriptionRegistry,
        set_broadcaster,
    )

    broadcaster = Broadcaster("redis://localhost:6379/9")
    registry = UserSubscriptionRegistry("redis://localhost:6379/9")
    set_broadcaster(broadcaster)
    ws_mod.set_registry(registry)
    try:
        with TestClient(create_app()):
            pass  # lifespan 跑完即退出
        assert broadcaster.closed is True, "lifespan 结束没关 broadcaster 的 Redis 连接"
        assert registry.closed is True, "lifespan 结束没关 registry 的订阅连接"
    finally:
        set_broadcaster(None)
        ws_mod.set_registry(None)
