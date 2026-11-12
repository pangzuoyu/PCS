"""Mock auth + 生产环境禁用契约 + **双闸**（T0-F · TODO-135）。"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.core.config as cfg
from app.api.v1.mock_auth import router as mock_auth_router
from app.core.errors import install_exception_handlers


def _client_with_mock() -> TestClient:
    """单挂 mock 路由，不走完整 lifespan（避免生产自检影响）。"""
    app = FastAPI()
    app.include_router(mock_auth_router)
    install_exception_handlers(app)
    return TestClient(app)


def _settings(*, env: str = "development", enable_mock_login: bool = True):
    """造一份确定的 Settings（**不依赖环境里的 .env** ⇒ 测试可重复）。"""
    return cfg.Settings(
        _env_file=None,
        env=env,
        secret_key="x" * 40,
        enable_mock_login=enable_mock_login,
    )


def _patch_settings(monkeypatch, **kwargs):
    """把 mock 路由看到的 settings 换成测试指定的那份。"""
    import app.api.v1.mock_auth as mock_mod

    monkeypatch.setattr(mock_mod, "get_settings", lambda: _settings(**kwargs))


def test_mock_login_alice_designer(monkeypatch):
    _patch_settings(monkeypatch)
    client = _client_with_mock()
    r = client.post("/auth/mock-login", json={"username": "alice"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["username"] == "alice"
    assert d["role"] == "DESIGNER"
    assert d["access_token"].count(".") == 2


def test_mock_login_bob_checker(monkeypatch):
    _patch_settings(monkeypatch)
    r = _client_with_mock().post("/auth/mock-login", json={"username": "bob"})
    assert r.json()["role"] == "CHECKER"


def test_mock_login_unknown_user_404(monkeypatch):
    _patch_settings(monkeypatch)
    r = _client_with_mock().post("/auth/mock-login", json={"username": "ghost"})
    assert r.status_code == 404
    assert r.json()["code"] == "UNKNOWN_MOCK_USER"


def test_mock_login_production_403(monkeypatch):
    """即使 mock 路由被强制挂载，生产环境内 endpoint 必须 self-disable。"""
    _patch_settings(monkeypatch, env="production")
    r = _client_with_mock().post("/auth/mock-login", json={"username": "alice"})
    assert r.status_code == 403
    assert r.json()["code"] == "MOCK_DISABLED"


# === T0-F（TODO-135）：mock 登录的**双闸** ===


@pytest.mark.parametrize(
    ("env", "flag", "expect_status"),
    [
        ("production", True, 403),
        ("production", False, 403),
        ("development", False, 403),
        ("development", True, 200),
    ],
)
def test_mock_login_double_gate(monkeypatch, env, flag, expect_status):
    """⚠️ **两道闸都过**才允许 mock 登录。

    ⚠️ 此前**只有** `is_production` 一道 ⇒ 闸门回归（配置写错 / 挂载代码改动）
    ⇒ mock 签发**任意 role claim** 的 token ⇒ **完整 auth bypass**。
    """
    _patch_settings(monkeypatch, env=env, enable_mock_login=flag)
    r = _client_with_mock().post("/auth/mock-login", json={"username": "alice"})
    assert r.status_code == expect_status, r.text
    if expect_status == 403:
        assert r.json()["code"] == "MOCK_DISABLED"


def test_mock_login_is_disabled_by_default(monkeypatch):
    """⚠️ **默认关** —— 不设任何环境变量 ⇒ mock 登录不可用。

    ⇒ 显式 opt-in（`PCS_ENABLE_MOCK_LOGIN=true`）才开 ⇒ 部署时忘了配 = 安全的。
    """
    import app.api.v1.mock_auth as mock_mod

    default_settings = cfg.Settings(
        _env_file=None, env="development", secret_key="x" * 40
    )
    monkeypatch.setattr(mock_mod, "get_settings", lambda: default_settings)
    r = _client_with_mock().post("/auth/mock-login", json={"username": "alice"})
    assert r.status_code == 403, r.text
    assert r.json()["code"] == "MOCK_DISABLED"


def test_env_var_name_is_pcs_enable_mock_login(monkeypatch):
    """⚠️ 环境变量名必须是 **`PCS_ENABLE_MOCK_LOGIN`**（计划指定的）。

    ⇒ 部署文档 / `.env.example` 写的那个名字**就是**生效的那个。
    """
    import app.core.config as cfg_mod

    monkeypatch.setenv("PCS_ENABLE_MOCK_LOGIN", "true")
    settings = cfg_mod.Settings(
        _env_file=None, env="development", secret_key="x" * 40
    )
    assert settings.enable_mock_login is True

    monkeypatch.setenv("PCS_ENABLE_MOCK_LOGIN", "false")
    settings = cfg_mod.Settings(
        _env_file=None, env="development", secret_key="x" * 40
    )
    assert settings.enable_mock_login is False


def test_production_with_mock_enabled_fails_startup():
    """⚠️ **部署期断言**：生产里开关开着 ⇒ **起不来**（矛盾配置 fail-fast）。"""
    from app.main import assert_mock_auth_not_exposed

    settings = cfg.Settings(
        _env_file=None,
        env="production",
        secret_key="x" * 40,
        enable_mock_login=True,
    )
    with pytest.raises(RuntimeError, match="PCS_ENABLE_MOCK_LOGIN"):
        assert_mock_auth_not_exposed(FastAPI(), settings)


def test_production_with_mock_route_mounted_fails_startup():
    """⚠️ **部署期断言**：生产里挂了 mock 路由 ⇒ **起不来**。"""
    from app.main import assert_mock_auth_not_exposed

    app = FastAPI()
    app.include_router(mock_auth_router)
    settings = cfg.Settings(_env_file=None, env="production", secret_key="x" * 40)
    with pytest.raises(RuntimeError, match="mock-login route"):
        assert_mock_auth_not_exposed(app, settings)


def test_production_with_mock_route_hidden_from_openapi_still_fails_startup():
    """⚠️ **路由挂载但对 OpenAPI 隐身** ⇒ 断言仍必须炸（评审 #8）。

    `include_router(router, include_in_schema=False)` ⇒ 路由**照样挂载**
    （`/auth/mock-login` 照样能打）⇒ 但 `app.openapi()["paths"]` 里**没有它**
    ⇒ 只看 OpenAPI 的断言**报绿** ⇒ 部署期闸门**形同虚设**。

    ⇒ 断言必须**另看路由表**（`app.routes` 递归展开懒挂载包装）。
    """
    from app.main import assert_mock_auth_not_exposed

    app = FastAPI()
    app.include_router(mock_auth_router, include_in_schema=False)

    # ⚠️ **前置条件**：这条路径确实对 OpenAPI 隐身了 ⇒ 旧断言会漏掉它。
    assert "/auth/mock-login" not in app.openapi()["paths"]

    settings = cfg.Settings(_env_file=None, env="production", secret_key="x" * 40)
    with pytest.raises(RuntimeError, match="mock-login route"):
        assert_mock_auth_not_exposed(app, settings)


def test_development_passes_the_startup_assertion():
    """dev ⇒ 断言放行（mock 登录要能用 ⇒ 显式 opt-in 即可）。"""
    from app.main import assert_mock_auth_not_exposed

    app = FastAPI()
    app.include_router(mock_auth_router)
    settings = cfg.Settings(
        _env_file=None,
        env="development",
        secret_key="x" * 40,
        enable_mock_login=True,
    )
    assert_mock_auth_not_exposed(app, settings)  # 不抛 ⇒ 放行


def test_main_create_app_skips_mock_in_production(monkeypatch):
    """main.create_app 不会在 env=production 挂载 /auth/mock-login。"""
    from fastapi.testclient import TestClient

    from app.main import create_app

    fake_settings = cfg.Settings(_env_file=None, env="production", secret_key="x" * 40)
    monkeypatch.setattr("app.main.get_settings", lambda: fake_settings)
    app = create_app()
    # TODO-006 起 /login 会写 audit_logs（依赖 get_db）。不覆盖的话这条用例会
    # 往**真实 pcs 开发库**写审计行 —— 测试污染开发数据。
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    from app.db.base import Base
    from app.db.session import get_db

    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )

    async def _override_get_db():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with async_sessionmaker(engine, expire_on_commit=False)() as s:
            yield s

    app.dependency_overrides[get_db] = _override_get_db
    c = TestClient(app)
    r = c.post(
        "/auth/mock-login",
        json={"username": "alice"},
        headers={"Authorization": "Bearer x"},
    )
    # production 模式：mock-login 不挂载 → 路由不存在 → 404/405
    assert r.status_code in (404, 405), r.text
    # 但真实 auth 路由仍挂载
    r2 = c.post("/api/v1/auth/login", json={"username": "x", "password": "x"})
    # 期望 401（LDAP 不通）而非 404（路由缺失）
    assert r2.status_code == 401, r2.text
