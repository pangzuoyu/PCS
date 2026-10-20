"""WebSocket 实时推送端点（ADR-0049 §⑤ / P9-OPEN-006 关键路径）。

`WS /api/v1/ws/notifications` —— 去邮件后，**实时推送是通知唯一的及时性来源**
（ADR-0049 §⑤），所以这条路径不得缺席。「登录时轮询能看到」只是降级路径。

## 为什么 token 走 query 而不是 header

浏览器的 `WebSocket` API **不能设置请求头**（这是 WebSocket 规范本身的限制，
不是实现偷懒）。⇒ `?token=` 是唯一可行方案；`Authorization` header 同时接受
（给非浏览器客户端与测试用）。

⚠️ 由此产生一条纪律：**token 出现在 URL 里 ⇒ 不能写进日志**。
`access_log` 里的 query string 会被 Nginx / 网关原样记录。

## 与通道的边界

本模块**只**做「鉴权 → 注册 sink → 收 → 转发」。
它不写 `notifications` 表 —— 那是 `InAppChannel` 的活（ADR-0049 §①：
通道不应该知道 WebSocket 存在）。方向是单向的：
写侧 → `InAppChannel.deliver()` → `Broadcaster.publish()` → 本模块的 sink。
"""
from __future__ import annotations

import contextlib
import logging
import uuid
from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Header, Query, WebSocket, WebSocketDisconnect

from app.api.v1.config import current_actor
from app.core.errors import PcsError
from app.services.broadcaster import UserSubscriptionRegistry

logger = logging.getLogger(__name__)

router = APIRouter(tags=["notifications-ws"])

# 关闭码 1008 = policy violation。1000 是正常关闭，会被客户端当成「服务端主动断开」。
_WS_POLICY_VIOLATION = 1008

# 进程级订阅表：**每个 worker 一份**（ADR-0049 §⑤ 约束 4）。
# 一个 worker 只订阅「本 worker 上有连接的用户」的 channel。
_registry: UserSubscriptionRegistry | None = None


def get_registry() -> UserSubscriptionRegistry:
    global _registry
    if _registry is None:
        from app.core.config import get_settings

        _registry = UserSubscriptionRegistry(get_settings().redis_url)
    return _registry


def set_registry(reg: UserSubscriptionRegistry | None) -> None:
    global _registry
    _registry = reg


def _authenticate(token: str | None, authorization: str | None) -> uuid.UUID:
    """复用 REST 侧的 JWT 解析，返回 user_id。失败抛 PcsError。"""
    if token:
        authorization = f"Bearer {token}"
    if not authorization:
        raise PcsError(code="MISSING_TOKEN", message="?token= 或 Authorization: Bearer", status=401)
    actor = current_actor(authorization)
    return actor.user_id


@router.websocket("/ws/notifications")
async def notifications_ws(
    websocket: WebSocket,
    token: str | None = Query(default=None),
    authorization: str | None = Header(default=None),
) -> None:
    """订阅当前用户的通知推送。

    握手阶段鉴权失败 ⇒ 直接关连接（**不接受**再报错）。
    先 accept 再关会让客户端认为连接已建立，随后收到一条空的关闭 ——
    前端会把它记成「连上了但没消息」。
    """
    try:
        user_id = _authenticate(token, authorization)
    except PcsError as e:
        await websocket.close(code=_WS_POLICY_VIOLATION, reason=e.code)
        return

    await websocket.accept()
    registry = get_registry()

    async def sink(message: dict) -> None:
        await websocket.send_json(message)

    await registry.add(user_id, sink)
    try:
        while True:
            raw = await websocket.receive_text()
            await _handle_client_frame(websocket, raw)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001 — 任何异常都必须摘掉 sink，否则泄漏
        logger.exception("通知 WS 异常关闭（user=%s）", user_id)
    finally:
        with contextlib.suppress(Exception):
            await registry.remove(user_id, sink)


async def _handle_client_frame(websocket: WebSocket, raw: str) -> None:
    """客户端帧。目前只认 ping —— 兼作**半开连接**的探活。

    半开连接（NAT / 代理悄悄掐掉对端）在应用层毫无征兆：
    `receive_text()` 永远不返回，sink 永远留着，订阅永不释放。
    ping/pong 让两端都知道连接还活着。
    """
    import json

    try:
        frame = json.loads(raw)
    except ValueError:
        await websocket.send_json({"type": "error", "message": "帧不是合法 JSON"})
        return
    if isinstance(frame, dict) and frame.get("type") == "ping":
        await websocket.send_json({"type": "pong"})


Sink = Callable[[dict], Awaitable[None]]
