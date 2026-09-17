"""auth API 单元测试。Mock LDAP 通过 monkey-patching app.services.ldap_client.authenticate。"""

from __future__ import annotations

import jwt
import pytest
from fastapi.testclient import TestClient

import app.api.v1.auth as auth_mod
import app.services.ldap_client as ldap_mod
from app.core.config import get_settings
from app.core.security import create_access_token, create_refresh_token
from app.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture
def patched_ldap(monkeypatch):
    """mock LDAP：alice 在 DESIGNER_GROUP，bob 不在群组（默认 DESIGNER）。"""

    def fake_auth(username: str, password: str) -> ldap_mod.LdapUser:
        if password == "":
            raise ldap_mod.LdapAuthError("empty")
        groups = (
            ("cn=DESIGNER_GROUP,ou=Groups,dc=test,dc=local",)
            if username == "alice"
            else ()
        )
        return ldap_mod.LdapUser(
            username=username,
            dn=f"cn={username},CN=Users,DC=test,DC=local",
            groups=groups,
            display_name=username.title(),
        )

    monkeypatch.setattr(ldap_mod, "authenticate", fake_auth)

    monkeypatch.setattr(auth_mod, "authenticate", fake_auth)
    return fake_auth


def test_login_success_returns_tokens(client, patched_ldap):
    r = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "x"}
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["username"] == "alice"
    assert data["role"] == "DESIGNER"
    assert data["token_type"] == "bearer"
    assert data["access_token"].count(".") == 2
    assert data["refresh_token"].count(".") == 2


def test_login_failure_invalid_credentials(client, patched_ldap):
    r = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": ""}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_CREDENTIALS"


def test_login_failure_missing_fields(client):
    r = client.post("/api/v1/auth/login", json={"username": ""})
    assert r.status_code == 422


def test_me_with_valid_bearer(client):
    token = create_access_token(subject="alice", role="CHECKER")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json() == {"username": "alice", "role": "CHECKER"}


def test_me_missing_bearer_401(client):
    r = client.get("/api/v1/auth/me")
    assert r.status_code == 401
    assert r.json()["code"] == "MISSING_BEARER"


def test_me_invalid_token_401(client):
    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": "Bearer not-a-jwt"}
    )
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_TOKEN"


def test_me_with_refresh_token_rejected(client):
    rt = create_refresh_token(subject="alice", role="DESIGNER")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {rt}"})
    assert r.status_code == 401
    assert r.json()["code"] == "WRONG_TOKEN_TYPE"


def test_refresh_returns_new_access_token(client):
    rt = create_refresh_token(subject="alice", role="DESIGNER")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 200
    assert r.json()["access_token"].count(".") == 2


def test_refresh_preserves_roles(client, monkeypatch):
    """防回归（P0-2 审查发现）：refresh 后原角色保留，不降权为 DESIGNER。"""

    def approver_auth(username: str, password: str) -> ldap_mod.LdapUser:
        return ldap_mod.LdapUser(
            username=username,
            dn=f"cn={username},CN=Users,DC=test,DC=local",
            groups=("cn=APPROVER_GROUP,ou=Groups,dc=test,dc=local",),
            display_name=username.title(),
        )

    monkeypatch.setattr(ldap_mod, "authenticate", approver_auth)
    monkeypatch.setattr(auth_mod, "authenticate", approver_auth)

    login = client.post(
        "/api/v1/auth/login",
        json={"username": "approver01", "password": "x"},
    ).json()
    assert login["role"] == "APPROVER", login

    refreshed = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": login["refresh_token"]},
    ).json()
    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {refreshed['access_token']}"},
    ).json()
    assert me["role"] == "APPROVER", me


def test_refresh_with_access_token_rejected(client):
    at = create_access_token(subject="alice", role="DESIGNER")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": at})
    assert r.status_code == 401
    assert r.json()["code"] == "WRONG_TOKEN_TYPE"


def test_logout_204(client):
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204


def test_refresh_missing_role_401_invalid_refresh(client):
    """C1 防回归：refresh token 无 role claim → 401 INVALID_REFRESH（拒绝授权）。

    直接用 jwt.encode 伪造 role-缺失 refresh token（绕过 create_refresh_token 默认填 role）；
    后端必须识别缺 role 并拒绝，**不可**默认降级为 DESIGNER。
    """
    settings = get_settings()
    payload = {
        "sub": "alice",
        "type": "refresh",
        "exp": 9_999_999_999,
        "iat": 1,
        # 注意：无 "role" 字段
    }
    bad_rt = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": bad_rt})
    assert r.status_code == 401
    body = r.json()
    assert body["code"] == "INVALID_REFRESH"
    assert "role" in body["message"].lower()


def test_refresh_empty_role_401_invalid_refresh(client):
    """C1 防回归：refresh token role="" → 401 INVALID_REFRESH（拒绝授权）。"""
    settings = get_settings()
    payload = {
        "sub": "alice",
        "type": "refresh",
        "role": "",
        "exp": 9_999_999_999,
        "iat": 1,
    }
    bad_rt = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": bad_rt})
    assert r.status_code == 401
    assert r.json()["code"] == "INVALID_REFRESH"
