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

import asyncio
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

from app.core.ai_sanitizer import hash_sanitized
from app.core.config import get_settings
from app.core.logging import get_current_trace_id
from app.services.ai.arq_queue import enqueue_ai_audit_log

logger = logging.getLogger(__name__)

#: 只审计这个前缀（= `api_router` 的 `/api/v1` + AI 路由的 `/ai`）。
AI_PATH_PREFIX = "/api/v1/ai"

#: 超过这个大小就**不哈希**（大 body 不进审计表的哈希列）。
MAX_HASH_BYTES = 1024 * 1024

#: 超限请求的错误码（评审 #3）。
BODY_TOO_LARGE_CODE = "REQUEST_BODY_TOO_LARGE"

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


async def _read_body(receive: Receive, max_bytes: int) -> tuple[bytes, bool]:
    """把请求体读出来（**下游要靠重放才能收到**）。

    返回 `(body, too_large)`。

    ⚠️ **有上限**（评审 #3 · 2026-11-12）：本中间件在**认证之前**就读 body
    ⇒ 未认证的客户端 POST 一个超大 body ⇒ 服务端先把它**完整**读进内存
    ⇒ 内存放大 / OOM 风险。
    ⇒ **超过 `max_bytes` 就停止累积**并把 `too_large` 置 True ⇒
    调用方回 **413**（不再截断成 422 ⇒ 语义不再与「参数错」混淆）。
    ⇒ 用**单个 `bytearray`** 累积 ⇒ 不再出现「chunks 一份 + join 后一份」
    的 **2× 峰值**。
    """
    buffer = bytearray()
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            break
        chunk = message.get("body", b"")
        if chunk:
            if len(buffer) + len(chunk) > max_bytes:
                # ⚠️ **超限** —— 不再累积，也不继续读（见 docstring）。
                return bytes(buffer), True
            buffer.extend(chunk)
        if not message.get("more_body", False):
            break
    return bytes(buffer), False


def _is_ai_path(path: str, prefix: str) -> bool:
    """路径**是否属于** AI 前缀（**有边界**）。

    ⚠️ **评审 #29**：旧判定是 `path.startswith("/api/v1/ai")` ⇒
    `/api/v1/ai-anything` 这类**邻居路径**也会被审计（body 被读、被哈希、
    被入队）⇒ 未认证请求可以把它当**任意的哈希停顿入口**（见评审 #4）。
    ⇒ 改成「**等于**前缀」或「前缀 + `/` 开头」。
    """
    return path == prefix or path.startswith(prefix + "/")


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
        path = str(scope.get("path", ""))
        if scope.get("type") != "http" or not _is_ai_path(path, self.prefix):
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

        # ⚠️ **上限来自 settings**（评审 #3）—— AI 请求体是小 JSON 对象。
        max_bytes = get_settings().ai_max_request_body_bytes

        # ⚠️ **先看 content-length**（评审 #3）—— 超限就**根本不读 body**
        #    ⇒ 未认证客户端无法让服务端把大 body 收进内存。
        declared = headers.get("content-length")
        too_large = bool(declared and declared.isdigit() and int(declared) > max_bytes)
        body = b""
        if not too_large:
            body, too_large = await _read_body(receive, max_bytes)

        status_code: int | None = None

        async def send_wrapper(message: dict[str, Any]) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers.append("X-Request-ID", request_id)
            await send(message)

        try:
            if too_large:
                # ⚠️ **413**（评审 #3）—— 不再截断成 422（那与「参数错」混同）。
                await self._send_too_large(scope, receive, send_wrapper, max_bytes)
            else:
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
                skip_hash=too_large,
            )

    async def _send_too_large(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
        max_bytes: int,
    ) -> None:
        """回 **413**（评审 #3）—— 信封与全局 `ErrorResponse` 同形。"""
        response = JSONResponse(
            status_code=413,
            content={
                "code": BODY_TOO_LARGE_CODE,
                "message": "请求体过大",
                "detail": {"max_bytes": max_bytes},
                "trace_id": get_current_trace_id() or "",
            },
        )
        await response(scope, receive, send)

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
        skip_hash: bool = False,
    ) -> None:
        """把审计**入队**（失败降级，不抛）。"""
        digest: str | None = None
        if not skip_hash and len(body) <= MAX_HASH_BYTES:
            try:
                # ⚠️⚠️ **离开事件循环**（评审 #18）：`hash_sanitized` 是**同步 CPU**
                #    （解析 → 递归脱敏 → 再序列化 → sha256）⇒ 直接在 async 里调
                #    ⇒ **整个事件循环被占住**（未认证请求即可触发）。
                # ⚠️ **哈希失败不得顶掉审计行**（评审 #17）：算不出哈希 ⇒ hash 留空，
                #    **行照写**（契约 R2：失败也要留痕）。
                digest = await asyncio.to_thread(hash_sanitized, body)
            except Exception:  # noqa: BLE001 — 哈希失败不该丢审计行
                logger.warning("AI 审计哈希失败（已降级，行照写）", exc_info=True)
                digest = None
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
