import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api import api_router
from app.api.v1.mock_auth import router as mock_auth_router
from app.core.config import assert_secret_key_configured, get_settings
from app.core.errors import install_exception_handlers
from app.core.logging import _trace_id_var, setup_logging
from app.db.session import (
    dispose_engines_async,
    dispose_sync_engine,
    get_async_session_factory,
)
from app.services.coefficient_service import CoefficientService


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    assert_secret_key_configured()
    if settings.is_production:
        for route in app.routes:
            if getattr(route, "path", "").endswith("/mock-login"):
                raise RuntimeError(
                    "mock-login route MUST NOT be mounted in production"
                )
    # V1.4 P2-OPEN-005 / SPEC-P2 §3.2.3：启动时 seed CATEGORY_3 默认 6 张系数表（幂等）
    factory = get_async_session_factory()
    async with factory() as session:
        await CoefficientService.seed_default_tables(session)
    try:
        yield
    finally:
        # P0-MED-002 fix（2026-09-18）：shutdown 释放 sync + async 引擎连接池
        # 否则重启时连接可能 TIME_WAIT 累积 + 文件描述符泄漏
        dispose_sync_engine()
        await dispose_engines_async()


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()
    app = FastAPI(title="PCS Backend", version="0.5.1", lifespan=lifespan)

    @app.middleware("http")
    async def add_trace_id(request: Request, call_next):
        # P0-MED-003 fix（2026-09-18）：trace_id 写入 contextvar + request.state
        # contextvar 让 logging.Filter 能在任意代码路径读取，无需显式透传
        trace_id = uuid.uuid4().hex
        request.state.trace_id = trace_id
        token = _trace_id_var.set(trace_id)
        try:
            return await call_next(request)
        finally:
            _trace_id_var.reset(token)

    install_exception_handlers(app)
    app.include_router(api_router)
    if not settings.is_production:
        app.include_router(mock_auth_router)
    return app


app = create_app()
