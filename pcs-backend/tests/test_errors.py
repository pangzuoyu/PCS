"""全局异常信封测试：404 / 405 / 422 均走 ErrorResponse 信封（code/trace_id 字段断言）。

覆盖 app/core/errors.py install_exception_handlers 注册的 StarletteHTTPException handler。
"""
from fastapi.testclient import TestClient

from app.main import create_app


def test_404_uses_envelope() -> None:
    resp = TestClient(create_app()).get("/api/v1/nope")
    assert resp.status_code == 404
    body = resp.json()
    assert body["code"] == "HTTP_404" and body["trace_id"]


def test_405_uses_envelope() -> None:
    resp = TestClient(create_app()).post("/api/v1/health")
    assert resp.status_code == 405
    assert resp.json()["code"] == "HTTP_405"


def test_pcserror_detail_reaches_envelope() -> None:
    """PcsError 的 detail 必须透传进响应信封 —— 客户端靠它读结构化信息.

    锁 `app/core/errors.py` 的 `detail=exc.detail` 这一行。既有测试只覆盖
    404/405 走 StarletteHTTPException 的分支，**PcsError 分支的 detail 透传
    此前零覆盖**：该行若被改成 `detail=None`（或误抄上面 429 限流分支的写法），
    全套测试无一会红，而客户端已经依赖它分流 —— 例如 `EVENT_ID_CONFLICT` 的
    `detail.retryable` 区分「上游 bug, 重试无用」与「行暂不可见, 可重试」，
    静默退化成「一律不可重试」会把可恢复的并发直接判成失败。
    """
    from fastapi import FastAPI

    from app.core.errors import PcsError, install_exception_handlers

    app = FastAPI()
    install_exception_handlers(app)

    @app.get("/boom")
    async def _boom():  # pragma: no cover - 由 TestClient 触发
        raise PcsError(
            code="EVENT_ID_CONFLICT",
            message="event_id 已被并发事务 claim 但尚未可见，请重试",
            status=409,
            detail={"retryable": True, "event_id": "0" * 8},
        )

    resp = TestClient(app, raise_server_exceptions=False).get("/boom")
    assert resp.status_code == 409
    body = resp.json()
    assert body["code"] == "EVENT_ID_CONFLICT"
    assert body["detail"]["retryable"] is True
    assert body["detail"]["event_id"] == "0" * 8
