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
from app.db.session import get_async_session_factory
from app.services.broadcaster import UserSubscriptionRegistry
from app.services.user_status_service import is_account_disabled

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


async def _authenticate(token: str | None, authorization: str | None) -> uuid.UUID:
    """复用 REST 侧的 JWT 解析，返回 user_id。失败抛 PcsError。

    ⚠️ **P9B-4 T0-B（TODO-132）**：这里**直接调用** `current_actor`（**不走
    `Depends`**）⇒ `current_actor` 改 async / 改签名后**不会自动适配**
    ⇒ 必须一并改，否则握手直接断（拿到的是 coroutine 不是 actor）。

    ⇒ `current_actor` 需要一个 `AsyncSession`（判 `users.status`）⇒ 这里
    **自己开一个短命 session**（握手是一次性动作，不值得为它挂一个依赖）。
    """
    if token:
        authorization = f"Bearer {token}"
    if not authorization:
        raise PcsError(code="MISSING_TOKEN", message="?token= 或 Authorization: Bearer", status=401)
    factory = get_async_session_factory()
    async with factory() as session:
        actor = await current_actor(session, authorization)
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

    ## ⚠️ 拒绝原因**只对日志可见**（P9B-4 评审 #24）

    ASGI 规定：**accept 之前**的 close 会被服务端当成 **HTTP 403 握手拒绝**
    ⇒ close code（1008）与 reason（`USER_DISABLED` / `MISSING_TOKEN` /
    `INVALID_TOKEN`）**到不了客户端** ⇒ 每一种拒绝在客户端看来**完全一样**。

    ⚠️ Starlette 的 `TestClient` 会把 accept 前的 close 还原成
    `WebSocketDisconnect(1008)` ⇒ **测试观察到的是一个部署里不存在的拒绝语义**
    ⇒ 「绿灯的测试，nobody 能观测的通道」。

    ⇒ 两条纪律：
    ① **原因写进日志**（运维可查「谁在什么时候因为什么被拒」）；
    ② 文档**不再**承诺「客户端能区分拒绝原因」。

    （要让原因**真正**到达客户端 ⇒ 必须**先 accept 再 close** ⇒ 那是**传输层
    变更**（客户端会看到「连上了又断」）⇒ 属于设计裁决，不在本批顺手做。）
    """
    try:
        user_id = await _authenticate(token, authorization)
    except PcsError as e:
        logger.warning("通知 WS 握手被拒（原因=%s）", e.code)
        await websocket.close(code=_WS_POLICY_VIOLATION, reason=e.code)
        return
    except Exception:  # noqa: BLE001 — 握手期的**任何**后端故障都不得裸穿成 500
        # ⚠️ **评审 #7**：鉴权要**查库**（判 `users.status`）⇒ 连接错误 /
        #    连接池超时 / 语句超时都**不是** `PcsError` ⇒ 原先的
        #    `except PcsError` 捕不到 ⇒ 异常逃出 ASGI 处理器 ⇒
        #    握手变成 **HTTP 500**（且**无日志**）⇒ 观测不到。
        #    ⇒ 与 `PcsError` 分支**同形**地关连接（1008）+ 记日志。
        logger.exception("通知 WS 握手失败（后端故障）")
        await websocket.close(code=_WS_POLICY_VIOLATION, reason="HANDSHAKE_FAILED")
        return

    await websocket.accept()
    registry = get_registry()

    sink = _make_sink(websocket, user_id)

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


async def _account_disabled_now(user_id: uuid.UUID) -> bool:
    """这个账号**此刻**是否被停用（WS 投递路径复检 · 评审 #6）。

    ⚠️ **无行 ⇒ False（放行）**（与 HTTP 侧同口径 · mock 登录不落库）。
    """
    factory = get_async_session_factory()
    async with factory() as session:
        return await is_account_disabled(session, user_id=user_id)


def _make_sink(
    websocket: WebSocket, user_id: uuid.UUID
) -> Callable[[dict], Awaitable[None]]:
    """造这条连接的 sink —— **投递前复检账号状态**（评审 #6）。

    ## 为什么要有这次复检

    握手只查**一次**账号状态 ⇒ 握手之后才被停用的用户**继续收到推送**
    （没有任何东西会替他关连接）⇒ HTTP 侧「停用立即生效」与长连接侧的
    实际行为**不一致**。

    ⇒ 用户 2026-11-12 裁决「停用覆盖面 = **全部补齐**」⇒ 投递前复检。

    ## 复检**失败**（DB 挂了）怎么办

    ⇒ **不投递**（fail-closed），但**不关连接** ⇒ 下次投递再试。
    ⚠️ 理由：HTTP 侧此时也是坏的（每请求都 500）⇒ 少一条通知不影响大局；
    反过来「检查失败就放行」会把「停用立即生效」这条承诺在**最需要**的时候
    破掉。
    """

    async def sink(message: dict) -> None:
        try:
            disabled = await _account_disabled_now(user_id)
        except Exception:  # noqa: BLE001 — 复检失败 ⇒ 不投递（见上文）
            logger.exception("通知 WS 投递前复检失败（user=%s）", user_id)
            return
        if disabled:
            logger.warning("通知 WS：账号已停用 ⇒ 关连接（user=%s）", user_id)
            await websocket.close(code=_WS_POLICY_VIOLATION, reason="USER_DISABLED")
            return
        await websocket.send_json(message)

    return sink


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
