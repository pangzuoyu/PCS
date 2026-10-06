"""双引擎 / lifespan 测试。"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.asyncio


async def test_async_engine_url_conversion():
    from app.db.session import _build_async_url

    assert _build_async_url("postgresql+psycopg://u:p@h/db").startswith(
        "postgresql+asyncpg://"
    )
    assert _build_async_url("postgresql://u:p@h/db").startswith(
        "postgresql+asyncpg://"
    )


async def test_lifespan_warms_async_engine(client):
    """client fixture 内部走 lifespan，验证 dispose_engines_async 可调用。"""
    from app.db.session import dispose_engines_async

    await dispose_engines_async()
    # 不抛即通过（引擎已在 lifespan 中初始化）


def test_cors_allow_origins_parsed():
    from app.core.config import get_settings

    s = get_settings()
    origins = [o.strip() for o in s.cors_allow_origins.split(",") if o.strip()]
    assert "http://localhost:5173" in origins


def test_redis_url_default_present():
    from app.core.config import get_settings

    s = get_settings()
    assert s.redis_url.startswith("redis://")

# ---------------------------------------------------------------------------
# CORS middleware（TODO-004 / TODO-019）
#
# 背景：`cors_allow_origins` 配置项一直存在，但 `add_middleware` 在全仓 0 命中
# —— CORSMiddleware 从未挂载。dev 靠 Vite proxy 掩盖，前后端一旦分域部署，
# preflight 直接 403。
# ---------------------------------------------------------------------------

_ORIGIN = "http://localhost:5173"


def test_app_mounts_cors_middleware():
    """create_app() 必须真的挂上 CORSMiddleware（不只是读配置）。"""
    from starlette.middleware.cors import CORSMiddleware

    from app.main import create_app

    app = create_app()
    assert any(m.cls is CORSMiddleware for m in app.user_middleware), (
        f"未挂载 CORSMiddleware，当前中间件: {[m.cls for m in app.user_middleware]}"
    )


def _cors_client() -> AsyncClient:
    """自建 app 做 CORS 测试。

    不能用 conftest 的 `client` fixture —— 它挂的是自己的最小
    `FastAPI(title="PCS Test")`（不走 `create_app()`），没有 CORS 中间件。
    ASGITransport 不跑 lifespan，故不会触发真实 DB probe。
    """
    from httpx import ASGITransport

    from app.main import create_app

    return AsyncClient(
        transport=ASGITransport(app=create_app()), base_url="http://test"
    )


async def test_cors_preflight_from_allowed_origin():
    """允许的 Origin 发 preflight → 200 且回 Access-Control-Allow-Origin."""
    async with _cors_client() as c:
        resp = await c.options(
            "/api/v1/health",
            headers={
                "Origin": _ORIGIN,
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == _ORIGIN


async def test_cors_preflight_from_unknown_origin_has_no_allow_header():
    """未授权的 Origin → 不回 ACAO 头（浏览器据此阻断）。"""
    async with _cors_client() as c:
        resp = await c.options(
            "/api/v1/health",
            headers={
                "Origin": "https://evil.example.com",
                "Access-Control-Request-Method": "GET",
            },
        )
    assert resp.headers.get("access-control-allow-origin") is None


def test_cors_prod_rejects_wildcard():
    """生产环境 origins 为 `*` → 启动期 fail-fast。

    理由：`*` 允许任意站点读取本系统响应。配 `allow_credentials` 时浏览器会
    直接拒绝该组合，故不能用「`*` + credentials」这种"安全"折中。
    """
    from app.core.config import Settings, validate_cors_for_production

    with pytest.raises(RuntimeError, match="CORS"):
        validate_cors_for_production(Settings(env="production", cors_allow_origins="*"))


def test_cors_prod_rejects_empty():
    """生产环境未配 origins（空串）→ 启动期 fail-fast。

    空 = 分域部署下所有浏览器请求都会被拒，且症状是"所有接口 403"，
    极难自查，必须在启动期炸。
    """
    from app.core.config import Settings, validate_cors_for_production

    with pytest.raises(RuntimeError, match="CORS"):
        validate_cors_for_production(Settings(env="production", cors_allow_origins=""))


def test_cors_prod_accepts_explicit_origin():
    """生产环境显式配了域名 → 放行。"""
    from app.core.config import Settings, validate_cors_for_production

    validate_cors_for_production(
        Settings(env="production", cors_allow_origins="https://pcs.example.com")
    )


def test_cors_dev_allows_wildcard():
    """非生产环境不限制 —— 开发便利优先于安全。"""
    from app.core.config import Settings, validate_cors_for_production

    validate_cors_for_production(Settings(env="development", cors_allow_origins="*"))


def test_cors_origins_parsed_strips_whitespace():
    """多 origin 逗号分隔解析应去空白、丢空项。"""
    from app.core.config import parse_cors_origins

    assert parse_cors_origins(" http://a.com , http://b.com ,, ") == [
        "http://a.com",
        "http://b.com",
    ]
    assert parse_cors_origins("") == []
