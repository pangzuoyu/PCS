"""FastAPI 应用入口（lifespan + 路由挂载 + 异常处理器注册）。

含 lifespan async context manager（DB 引擎 + Redis 探测）+ create_app() 工厂
（中间件链 + CORS + trace_id + 异常处理器 + api_router 挂载）。
"""

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api import api_router
from app.api.v1.mock_auth import router as mock_auth_router
from app.core.config import (
    assert_secret_key_configured,
    get_settings,
    parse_cors_origins,
    validate_cors_for_production,
)
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
    """FastAPI 应用生命周期（启动/关闭 hook）。

    启动阶段：
    1. 校验 `SECRET_KEY` 在生产环境已配置（fail-fast 防 default token 风险）
    2. 拒绝生产挂载 mock-login 路由（防 P0 误用）
    3. seed CATEGORY_3 默认 6 张系数表（幂等，V1.4 P2-OPEN-005）

    关闭阶段：
    释放 sync + async 引擎连接池（P0-MED-002 fix）。否则重启时连接
    可能 TIME_WAIT 累积 + 文件描述符泄漏。
    """
    settings = get_settings()
    assert_secret_key_configured()
    # TODO-019: CORS 配置自检必须在 startup 做（而非 middleware 阶段）——
    # middleware 跑在每个请求上，配错时的症状是"所有接口 403"，极难自查。
    validate_cors_for_production(settings)
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
    """PCS 后端 FastAPI 应用工厂。

    装配顺序：
    1. `setup_logging()` 装载 TraceIdFilter + JsonFormatter
    2. 挂载 `CORSMiddleware`（读 `cors_allow_origins`）
    3. 注册 `add_trace_id` 中间件（每次请求生成 trace_id 写入 contextvar + state）
    4. 注册全局异常处理器（`install_exception_handlers`）
    5. 挂载 `api_router`（v1 路由）
    6. 非生产环境追加 `mock_auth_router`（开发态 mock 登录）
    """
    settings = get_settings()
    setup_logging()
    app = FastAPI(title="PCS Backend", version="0.5.1", lifespan=lifespan)

    # TODO-004: CORSMiddleware 一直缺失 —— `cors_allow_origins` 配置项在，
    # 但中间件从未挂载。dev 靠 Vite proxy 掩盖，前后端一但分域部署
    # preflight 直接 403。
    #
    # allow_credentials=False：本系统是 Bearer token（Authorization 头）模式，
    # 全栈无 cookie（已核 app/ 与 pcs-frontend/src 均无 set_cookie /
    # withCredentials），故不需要也不应开 —— 且开了会与 `*` 组合冲突。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=parse_cors_origins(settings.cors_allow_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def add_trace_id(request: Request, call_next):
        """trace_id 中间件：每次 HTTP 请求生成 UUID hex 写入 contextvar + request.state。

        contextvar 让 `app.core.logging.TraceIdFilter` 在任意代码路径读取 trace_id，
        无需显式透传；request.state 提供给响应日志 / 业务代码层访问。
        """
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
