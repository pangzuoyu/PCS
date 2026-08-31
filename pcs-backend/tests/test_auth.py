"""auth API 单元测试。Mock LDAP 通过 monkey-patching app.services.ldap_client.authenticate。"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import app.services.ldap_client as ldap_mod
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
    import app.api.v1.auth as auth_mod

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
    rt = create_refresh_token(subject="alice")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {rt}"})
    assert r.status_code == 401
    assert r.json()["code"] == "WRONG_TOKEN_TYPE"


def test_refresh_returns_new_access_token(client):
    rt = create_refresh_token(subject="alice")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert r.status_code == 200
    assert r.json()["access_token"].count(".") == 2


def test_refresh_with_access_token_rejected(client):
    at = create_access_token(subject="alice", role="DESIGNER")
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": at})
    assert r.status_code == 401
    assert r.json()["code"] == "WRONG_TOKEN_TYPE"


def test_logout_204(client):
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204
