"""Mock auth + 生产环境禁用契约。"""

from __future__ import annotations

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


def test_mock_login_alice_designer():
    client = _client_with_mock()
    r = client.post("/auth/mock-login", json={"username": "alice"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["username"] == "alice"
    assert d["role"] == "DESIGNER"
    assert d["access_token"].count(".") == 2


def test_mock_login_bob_checker():
    r = _client_with_mock().post("/auth/mock-login", json={"username": "bob"})
    assert r.json()["role"] == "CHECKER"


def test_mock_login_unknown_user_404():
    r = _client_with_mock().post("/auth/mock-login", json={"username": "ghost"})
    assert r.status_code == 404
    assert r.json()["code"] == "UNKNOWN_MOCK_USER"


def test_mock_login_production_403(monkeypatch):
    """即使 mock 路由被强制挂载，生产环境内 endpoint 必须 self-disable。"""
    import app.api.v1.mock_auth as mock_mod

    s = cfg.Settings(env="production", secret_key="x" * 40)
    monkeypatch.setattr(mock_mod, "get_settings", lambda: s)
    r = _client_with_mock().post("/auth/mock-login", json={"username": "alice"})
    assert r.status_code == 403
    assert r.json()["code"] == "MOCK_DISABLED"


def test_main_create_app_skips_mock_in_production(monkeypatch):
    """main.create_app 不会在 env=production 挂载 /auth/mock-login。"""
    from fastapi.testclient import TestClient

    from app.main import create_app

    fake_settings = cfg.Settings(env="production", secret_key="x" * 40)
    monkeypatch.setattr("app.main.get_settings", lambda: fake_settings)
    app = create_app()
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
