"""AI 请求的**审计中间件**（P10-A · Task T11）—— 纯 ASGI。

## 为什么是**纯 ASGI**（不是 `BaseHTTPMiddleware`）

`BaseHTTPMiddleware` 会把 request/response 包成新的对象流 ⇒ body 的
「读—再给下游」这件事变得别扭（它自己也要处理 `receive` 的一次性语义）。
纯 ASGI 直接操作 `scope` / `receive` / `send` ⇒ body 的缓存与重放是
**显式**的、可测的。

## 五件事

1. **只作用于 `/api/v1/ai/` 前缀**（其它路径零开销、零副作用）。
2. **生成 `request_id`**（标准 UUID 串）写 `scope["state"]["request_id"]`
   ⇒ 路由与 501 handler 都从这儿取（`request.state.request_id`）。
   ⚠️ **与 `trace_id` 不是一回事**：`trace_id` 走日志（32 位 hex），
   `request_id` 走 AI 审计（36 位 UUID）（偏离登记 D8）。
3. **读 `X-Request-ID`** ⇒ `client_request_id`（**不生成、不信任** ——
   只原样留痕，不拿它当幂等键）。
4. **缓存并重放 body** ⇒ 下游 Pydantic 仍能收到（Review Focus #2）。
5. **入队审计**（`enqueue_ai_audit_log`）⇒ 失败降级（不抛）。

## 两条最容易漏的

- **认证失败也要留痕**（`user_id=None`）—— 否则无效 token 的探测行为
  在审计表里**完全看不见**（Review Focus #1）。
- **下游异常未产生响应时** ⇒ `status_code` 记 **500**（不是 None、不是 0）。
"""
from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.datastructures import Headers, MutableHeaders

from app.core.ai_sanitizer import hash_sanitized
from app.services.ai.arq_queue import enqueue_ai_audit_log

logger = logging.getLogger(__name__)

#: 只审计这个前缀（= `api_router` 的 `/api/v1` + AI 路由的 `/ai`）。
AI_PATH_PREFIX = "/api/v1/ai"

#: 超过这个大小就**不哈希**（大 body 不进审计表的哈希列）。
MAX_HASH_BYTES = 1024 * 1024

#: **请求体的读取上限**（评审 M-5）—— 超过就截断 ⇒ 下游 422，
#: 而不是把整个 body 读进内存（未认证路径也能触发 ⇒ 内存放大风险）。
#: 取 10 MB（与本仓 `MAX_UPLOAD_BYTES` 同量级）。
_MAX_BODY_BYTES = 10 * 1024 * 1024

#: ASGI 作用域类型（http / websocket）。
Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


def _extract_user_id(authorization: str | None) -> uuid.UUID | None:
    """从 `Authorization: Bearer <token>` 解出 `user_id`（**失败 ⇒ None**）。

    ⚠️ **不抛** —— 认证失败正是**最该留痕**的场景（Review Focus #1）。
    ⚠️ 派生用 `derive_user_id`（`app/services/token_issuer.py`）——
    那是 user_id 的**唯一**派生点（与登录路径同口径）⇒ 不另写一套。
    """
    if not authorization or not authorization.lower().startswith("bearer "):
        return None
    from app.core.security import decode_token
    from app.services.token_issuer import derive_user_id

    try:
        payload = decode_token(authorization.split(" ", 1)[1].strip())
    except Exception:  # noqa: BLE001 — 坏 token 视为匿名
        return None
    raw = payload.get("user_id")
    if raw:
        try:
            return uuid.UUID(str(raw))
        except (ValueError, TypeError):
            pass
    return derive_user_id(str(payload.get("sub", "")))


async def _read_body(receive: Receive) -> bytes:
    """把请求体读出来（**下游要靠重放才能收到**）。

    ⚠️ **有上限**（2026-11-12 评审 M-5）：本中间件在**认证之前**就读 body
    ⇒ 未认证的客户端 POST 一个超大 body ⇒ 服务端先把它**完整**读进内存
    （峰值 ≈ 2× body：list 一份 + join 后一份）⇒ 内存放大 / OOM 风险。
    ⇒ **超过 `_MAX_BODY_BYTES` 就停止累积** ⇒ 下游收到**被截断**的 body
    ⇒ JSON 解析失败 ⇒ **422**（而不是把服务撑爆）。
    ⇒ 真实业务 body（AI 请求是 JSON 小对象）远小于这个上限 ⇒ 行为不变。
    """
    chunks: list[bytes] = []
    total = 0
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        chunk = message.get("body", b"")
        if chunk:
            if total + len(chunk) > _MAX_BODY_BYTES:
                # ⚠️ **截断**（见 docstring）—— 不再累积，也不继续读。
                chunks.append(chunk[: _MAX_BODY_BYTES - total])
                break
            chunks.append(chunk)
            total += len(chunk)
        if not message.get("more_body", False):
            break
    return b"".join(chunks)


def _replay_receive(body: bytes) -> Receive:
    """造一个「把已读 body 再放回去」的 `receive`。

    ⚠️ **必须重放** —— 否则下游 Pydantic 收不到 body ⇒ 报 **422**
    （而不是 501）⇒ **症状与「参数错」无法区分**（Review Focus #2）。
    """
    sent = False

    async def receive() -> dict[str, Any]:
        nonlocal sent
        if not sent:
            sent = True
            return {"type": "http.request", "body": body, "more_body": False}
        return {"type": "http.disconnect"}

    return receive


def _response_summary(status_code: int) -> str:
    """结果摘要（**不记录响应体** —— 响应体可能含敏感内容）。"""
    if status_code == 501:
        return "AI_NOT_IMPLEMENTED"
    return f"HTTP_{status_code}"


class AIAuditMiddleware:
    """纯 ASGI 的 AI 审计中间件。"""

    def __init__(self, app: Callable[..., Awaitable[None]], *, prefix: str = AI_PATH_PREFIX):
        self.app = app
        self.prefix = prefix

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope.get("type") != "http" or not str(scope.get("path", "")).startswith(
            self.prefix
        ):
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        scope.setdefault("state", {})["request_id"] = request_id

        headers = Headers(scope=scope)
        client_request_id = headers.get("x-request-id")
        user_id = _extract_user_id(headers.get("authorization"))
        # ⚠️ `started` 必须在**读 body 之前**（评审 L-5）—— 否则
        #    `duration_ms` 不含读 body 的时间（≈ 一个「假」的耗时）。
        started = time.monotonic()
        body = await _read_body(receive)

        status_code: int | None = None

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers.append("X-Request-ID", request_id)
            await send(message)

        try:
            await self.app(scope, _replay_receive(body), send_wrapper)
        finally:
            # ⚠️ 下游异常**未产生响应** ⇒ status_code 仍是 None ⇒ 记 500
            #    （不是 None、不是 0 —— 「没有状态码」不是一种状态）。
            effective_status = status_code if status_code is not None else 500
            await self._record_audit(
                scope=scope,
                request_id=request_id,
                client_request_id=client_request_id,
                user_id=user_id,
                body=body,
                status_code=effective_status,
                duration_ms=int((time.monotonic() - started) * 1000),
            )

    async def _record_audit(
        self,
        *,
        scope: Scope,
        request_id: str,
        client_request_id: str | None,
        user_id: uuid.UUID | None,
        body: bytes,
        status_code: int,
        duration_ms: int,
    ) -> None:
        """把审计**入队**（失败降级，不抛）。"""
        digest = hash_sanitized(body) if len(body) <= MAX_HASH_BYTES else None
        try:
            await enqueue_ai_audit_log(
                request_id=request_id,
                client_request_id=client_request_id,
                endpoint=str(scope.get("path", "")),
                status_code=status_code,
                duration_ms=duration_ms,
                sanitized_request_hash=digest,
                response_summary=_response_summary(status_code),
                model_version=None,
                user_id=user_id,
                operation="AI_REQUEST",
            )
        except Exception:  # noqa: BLE001 — 审计失败不该影响请求
            logger.warning("AI 审计入队失败（已降级）", exc_info=True)


__all__ = ["AI_PATH_PREFIX", "AIAuditMiddleware", "MAX_HASH_BYTES"]
