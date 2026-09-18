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


# --- H-P0-1: JWT decode 必须 exp/iat/sub 三字段必填 ---


@pytest.mark.parametrize("missing_field", ["exp", "iat", "sub"])
def test_decode_token_rejects_missing_required_claim(client, missing_field):
    """H-P0-1 防回归：token 缺少 exp/iat/sub 任一字段 → 401 INVALID_TOKEN。

    攻击场景：伪造 token 跳过 exp 永不过期；跳过 sub 无主体标识；
    跳过 iat 绕过最短有效时长审计。后端必须识别并拒绝。
    """
    settings = get_settings()
    payload: dict = {
        "sub": "alice",
        "type": "refresh",
        "role": "DESIGNER",
        "exp": 9_999_999_999,
        "iat": 1,
    }
    del payload[missing_field]
    bad_token = jwt.encode(payload, settings.secret_key, algorithm="HS256")

    # /refresh 路径：缺 exp/iat/sub → decode_token 抛 MissingRequiredClaimError
    r = client.post("/api/v1/auth/refresh", json={"refresh_token": bad_token})
    assert r.status_code == 401, r.text
    assert r.json()["code"] == "INVALID_REFRESH"


def test_decode_token_rejects_missing_required_claim_on_me(client):
    """H-P0-1 防回归：/me 路径同样必须含 exp/iat/sub。"""
    settings = get_settings()
    payload = {"sub": "alice", "type": "access", "role": "DESIGNER"}  # 缺 exp/iat
    bad_token = jwt.encode(payload, settings.secret_key, algorithm="HS256")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {bad_token}"})
    assert r.status_code == 401, r.text
    assert r.json()["code"] == "INVALID_TOKEN"


def test_decode_token_accepts_all_required_claims(client):
    """正常路径：exp/iat/sub 全部存在时 decode 通过。"""
    token = create_access_token(subject="alice", role="DESIGNER")
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200


# --- H-P0-2: refresh token rotation（一次性使用，旧 refresh 吊销）---


def test_refresh_rotates_to_new_refresh_token(client, patched_ldap):
    """H-P0-2 防回归：refresh 响应必须含新的 refresh_token（轮换）。"""
    login = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "x"}
    ).json()
    old_rt = login["refresh_token"]

    r = client.post("/api/v1/auth/refresh", json={"refresh_token": old_rt})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["access_token"].count(".") == 2
    # 轮换：响应必须含新 refresh_token，且 ≠ 旧 token
    assert "refresh_token" in body
    assert body["refresh_token"] != old_rt
    assert body["refresh_token"].count(".") == 2


def test_refresh_old_token_revoked_after_rotation(client, patched_ldap):
    """H-P0-2 防回归：旧 refresh 一次性使用 → 重放 → 401 INVALID_REFRESH。

    攻击场景：截获 refresh token 后立即重放，本应被吊销集拦截。
    """
    login = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "x"}
    ).json()
    old_rt = login["refresh_token"]

    # 第一次 refresh 成功 + 吊销旧 RT
    first = client.post("/api/v1/auth/refresh", json={"refresh_token": old_rt})
    assert first.status_code == 200

    # 重放旧 RT → 401 INVALID_REFRESH（被 JTI 吊销拦截）
    replay = client.post("/api/v1/auth/refresh", json={"refresh_token": old_rt})
    assert replay.status_code == 401
    assert replay.json()["code"] == "INVALID_REFRESH"
    assert "revoked" in replay.json()["message"].lower()


# --- H-P0-3: logout 真正吊销 refresh token ---


def test_logout_revokes_refresh_token(client, patched_ldap):
    """H-P0-3 防回归：logout 后 refresh 失效 → 401 INVALID_REFRESH。

    旧实现 logout 是 no-op 204；现在 logout 接收 refresh_token 并吊销其 JTI。
    """
    login = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "x"}
    ).json()
    rt = login["refresh_token"]

    # logout 204
    r = client.post("/api/v1/auth/logout", json={"refresh_token": rt})
    assert r.status_code == 204

    # 被吊销的 RT 不能再 refresh
    reuse = client.post("/api/v1/auth/refresh", json={"refresh_token": rt})
    assert reuse.status_code == 401
    assert reuse.json()["code"] == "INVALID_REFRESH"
    assert "revoked" in reuse.json()["message"].lower()


def test_logout_without_body_204(client):
    """H-P0-3 防回归：logout 不传 refresh_token → 幂等 204。

    不强制要求客户端传 token，简化前端集成；不传时仅返回 204。
    """
    r = client.post("/api/v1/auth/logout")
    assert r.status_code == 204


def test_logout_with_invalid_token_204(client):
    """H-P0-3 防回归：logout 传伪造/无效 token → 204（不泄露 token 状态）。

    防侧信道：不应通过响应区分 token 有效/无效/已吊销。
    """
    r = client.post(
        "/api/v1/auth/logout", json={"refresh_token": "not.a.jwt"}
    )
    assert r.status_code == 204


def test_logout_with_access_token_204_no_op(client):
    """H-P0-3 防回归：logout 传 access token（非 refresh）→ 204，不吊销任何 JTI。

    access token 没有 jti claim，logout 不应错误吊销；refresh 仍可用。
    """
    at = create_access_token(subject="alice", role="DESIGNER")
    r = client.post("/api/v1/auth/logout", json={"refresh_token": at})
    assert r.status_code == 204
    # sanity：access token 仍然能访问 /me（无服务端会话，logout 不动 access）
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {at}"})
    assert me.status_code == 200
