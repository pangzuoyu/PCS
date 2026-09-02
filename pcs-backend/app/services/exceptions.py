"""PCS service 层统一异常。

PcsError 是所有 service 层异常的基类，便于上层（API/中间件）按 code/status
统一响应。PreconditionViolation 是公式 preconditions 评估时的 REJECT-only 异常。
"""

from __future__ import annotations

from typing import Any


class PcsError(Exception):
    """PCS 统一异常基类。所有 service 层异常应继承此类。"""

    code: str = "PCS_ERROR"
    status: int = 422

    def __init__(
        self,
        message: str,
        *,
        code: str | None = None,
        status: int | None = None,
        details: dict[str, Any] | None = None,
    ):
        super().__init__(message)
        if code is not None:
            self.code = code
        if status is not None:
            self.status = status
        self.details = details or {}


class PreconditionViolation(PcsError):
    """公式前置/后置条件违规。code=PRECONDITION_VIOLATION, status=422, REJECT-only。"""

    code = "PRECONDITION_VIOLATION"
    status = 422


__all__ = ["PcsError", "PreconditionViolation"]
