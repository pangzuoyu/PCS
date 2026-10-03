"""FastAPI 全局异常处理器 + 统一 PcsError 信封。

含 PcsError envelope 结构（code/status/message/detail）+ install_exception_handlers
注册 5 类 handler（PcsError / HTTPException / RequestValidationError / 未捕获 / 404）。

F-P3-001 checklist #5 (Sprint 3b): RBAC 401/403 拒绝事件 audit + per-IP 滑动窗口限流
（复用 F-P2-006 _sliding_window_rate_limit; >5 次/min 同 IP → 429 RBAC_RATE_LIMITED）。
"""

import logging
import os
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.services.exceptions import PcsError as ServicePcsError

logger = logging.getLogger(__name__)

# F-P3-001 #5: RBAC 拒绝限流参数（checklist 锁定 >5/min; 生产按需改 cfg）
_RBAC_DENIED_LIMIT = 5
_RBAC_DENIED_WINDOW_S = 60.0


async def _write_rbac_audit_row(
    user_id: uuid.UUID | None, detail: dict[str, Any]
) -> None:
    """写一条 RBAC_DENIED audit_logs 行（独立 session, best-effort）.

    - 懒导入避免 core → services/models 循环依赖
    - pytest 环境默认跳过（防测试写真实 DB; 单测 monkeypatch 本函数或
      清 PYTEST_CURRENT_TEST + 注入测试 factory 走真路径）
    - 失败仅 log warning, 不影响错误响应本身
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return
    try:
        from app.db.session import get_async_session_factory
        from app.services.audit_service import AuditService

        factory = get_async_session_factory()
        async with factory() as session:
            await AuditService(session).write(
                # str 而非 AuditAction 枚举: core 层禁止 import models
                # (architecture test); AuditService.write 接受 AuditAction | str
                action="RBAC_DENIED",
                resource_type="AUTHZ",
                resource_id=None,
                user_id=user_id,
                detail=detail,
            )
            await session.commit()
    except Exception:  # noqa: BLE001 — audit 失败不阻断错误响应
        logger.warning("RBAC_DENIED audit write failed", exc_info=True)


def _best_effort_user_id(request: Request) -> uuid.UUID | None:
    """从 Authorization Bearer best-effort 解 user_id（无/坏 token → None）."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    try:
        from app.core.security import decode_token

        payload = decode_token(auth[len("Bearer "):])
        sub = payload.get("sub", "")
        raw = payload.get("user_id")
        return uuid.UUID(str(raw)) if raw else uuid.uuid5(uuid.NAMESPACE_DNS, sub)
    except Exception:  # noqa: BLE001 — 坏 token 视为匿名
        return None


async def _record_rbac_denial(request: Request, *, status: int, code: str) -> bool:
    """F-P3-001 #5: 记 RBAC 拒绝事件 + per-IP 滑动窗口限流.

    Returns:
        True → 已超限, 调用方应回 429; False → 正常回原 401/403.
    """
    from app.services._sliding_window_rate_limit import check_rate_limit

    # ASGITransport 下 request.client 可能为 None; 反代部署建议信任
    # X-Forwarded-For (当前直连部署用 client.host)
    ip = request.client.host if request.client else "unknown"
    allowed = await check_rate_limit(
        f"rbac_denied:{ip}", _RBAC_DENIED_LIMIT, _RBAC_DENIED_WINDOW_S
    )
    detail = {
        "path": request.url.path,
        "method": request.method,
        "ip": ip,
        "status": status,
        "code": code,
        "rate_limited": not allowed,
    }
    await _write_rbac_audit_row(_best_effort_user_id(request), detail)
    return not allowed


class PcsError(Exception):
    """FastAPI 全局异常信封基类（code/status/message/detail 四元组）。

    业务：service 层抛出 PcsError，install_exception_handlers 兜底转 4xx/5xx JSON；
    code 大写蛇形命名 + status HTTP code + detail 可选 dict（结构化错误数据）。
    """

    def __init__(
        self, code: str, message: str, status: int = 400, detail: Any = None
    ):
        """构造 FastAPI 全局异常信封基类（code 大写蛇形 + status HTTP code + detail 可选 dict）。"""
        self.code = code
        self.message = message
        self.status = status
        self.detail = detail


class ErrorResponse(BaseModel):
    """统一错误响应外壳（FastAPI exception handler 序列化输出）。

    业务：code 业务错误码 + message 中文消息 + detail 可选详情 +
    trace_id 链路追踪 ID（X-Trace-ID header 同值，跨服务日志关联）。
    """

    code: str
    message: str
    detail: Any = None
    trace_id: str


def install_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器，统一错误响应信封（ErrorResponse）。

    注册 5 类 handler（按优先级匹配）：
    1. `PcsError` / `ServicePcsError`：业务异常（status 取 exc.status/code）
    2. `StarletteHTTPException`：HTTP 异常（status 取 exc.status_code）
    3. `RequestValidationError`：Pydantic 422 校验失败（VALIDATION_ERROR 信封）
    4. `Exception`：兜底 500（INTERNAL_ERROR 信封，不泄漏内部细节）

    所有响应均经 `ErrorResponse` 信封序列化（code/message/detail/trace_id）。
    """
    @app.exception_handler(PcsError)
    async def _pcs(request: Request, exc: PcsError) -> JSONResponse:
        # F-P3-001 #5: 认证/授权类 401/403 → audit + per-IP 限流 (>5/min → 429)
        if exc.status in (401, 403):
            if await _record_rbac_denial(request, status=exc.status, code=exc.code):
                return JSONResponse(
                    status_code=429,
                    content=ErrorResponse(
                        code="RBAC_RATE_LIMITED",
                        message="too many denied requests, retry later",
                        detail=None,
                        trace_id=getattr(request.state, "trace_id", ""),
                    ).model_dump(),
                )
        return JSONResponse(
            status_code=exc.status,
            content=ErrorResponse(
                code=exc.code,
                message=exc.message,
                detail=exc.detail,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(ServicePcsError)
    async def _service_pcs(request: Request, exc: ServicePcsError) -> JSONResponse:
        # app/services/exceptions.PcsError 与 core.PcsError 是两个类；
        # message 走 str(exc)、details(dict) 映射到信封的 detail 字段。
        return JSONResponse(
            status_code=getattr(exc, "status", 422),
            content=ErrorResponse(
                code=getattr(exc, "code", "PCS_ERROR"),
                message=str(exc),
                detail=getattr(exc, "details", None) or None,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        # F-P3-001 #5: require_roles 403 等 HTTP 拒绝 → audit + per-IP 限流
        if exc.status_code in (401, 403):
            if await _record_rbac_denial(
                request, status=exc.status_code, code=f"HTTP_{exc.status_code}"
            ):
                return JSONResponse(
                    status_code=429,
                    content=ErrorResponse(
                        code="RBAC_RATE_LIMITED",
                        message="too many denied requests, retry later",
                        detail=None,
                        trace_id=getattr(request.state, "trace_id", ""),
                    ).model_dump(),
                )
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
                detail=None,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code="VALIDATION_ERROR",
                message="request validation failed",
                detail=jsonable_encoder(exc.errors()),
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code="INTERNAL_ERROR",
                message="internal server error",
                detail=None,
                trace_id=getattr(request.state, "trace_id", ""),
            ).model_dump(),
        )
