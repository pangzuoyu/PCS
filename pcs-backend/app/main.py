import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from app.api import api_router
from app.core.config import get_settings
from app.core.errors import install_exception_handlers
from app.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Task 10 注入: assert_mock_not_enabled(app) + assert_secret_key_configured()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    setup_logging()
    app = FastAPI(title="PCS Backend", version="0.1.0", lifespan=lifespan)

    @app.middleware("http")
    async def add_trace_id(request: Request, call_next):
        request.state.trace_id = uuid.uuid4().hex
        return await call_next(request)

    install_exception_handlers(app)
    app.include_router(api_router)
    if not settings.is_production:
        # Task 10 注入 mock 路由
        pass
    return app


app = create_app()
