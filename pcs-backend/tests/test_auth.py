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
    """真实 app + in-memory DB override。

    `/login` 自 TODO-006 起写 audit_logs，因此依赖 `get_db`。若不覆盖，
    TestClient 会连 **真实 pcs 开发库** —— 测试污染开发数据。

    引擎与建表都在 app 自己的 event loop 里惰性完成（TestClient 用 anyio
    portal 起独立 loop，与测试侧 loop 不同，跨 loop 复用 async engine 会炸），
    且用 StaticPool 保证 `:memory:` 在多条连接间共享。
    """
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
    from sqlalchemy.pool import StaticPool

    import app.models as _models  # noqa: F401  注册全部表到 metadata（别用 `import app.models` —— 它会把局部名 app 绑到包，遮蔽模块级的 FastAPI 实例）
    from app.db.base import Base
    from app.db.session import get_db

    holder: dict = {}

    async def _get_sessionmaker():
        if "factory" not in holder:
            engine = create_async_engine(
                "sqlite+aiosqlite:///:memory:",
                poolclass=StaticPool,
                connect_args={"check_same_thread": False},
            )
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
            holder["factory"] = async_sessionmaker(engine, expire_on_commit=False)
        return holder["factory"]

    async def _override_get_db():
        factory = await _get_sessionmaker()
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.pop(get_db, None)


@pytest.fixture
def patched_ldap(monkeypatch):
    """mock LDAP：alice 在 DESIGNER_GROUP，bob 不在群组（默认 DESIGNER）。

    password=="wrong-pw" → LdapAuthError（INVALID_CREDENTIALS 测试用）；
    其他非空密码按 username 命中处理。
    """

    def fake_auth(username: str, password: str) -> ldap_mod.LdapUser:
        if password == "wrong-pw":
            raise ldap_mod.LdapAuthError("invalid credentials")
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
    """用户名/密码错误 → 401 INVALID_CREDENTIALS（非空密码）。"""
    r = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "wrong-pw"}
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
    body = r.json()
    # P7-7+ actor 上下文一致: /auth/me 返回 user_id (优先 user_id 声明,
    # 缺省回退 uuid5(NAMESPACE_DNS, sub) 与 Depends(current_actor) 保持一致)
    import uuid as _uuid
    assert body["username"] == "alice"
    assert body["role"] == "CHECKER"
    expected_uid = str(_uuid.uuid5(_uuid.NAMESPACE_DNS, "alice"))
    assert body["user_id"] == expected_uid


def test_me_with_user_id_claim_in_jwt(client):
    """JWT 显式 user_id 声明优先级高于 fallback uuid5 派生 (P7-7+ actor 上下文)."""
    import uuid as _uuid
    fixed_uid = str(_uuid.uuid4())
    token = create_access_token(
        subject="alice", role="CHECKER", extra={"user_id": fixed_uid}
    )
    r = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == fixed_uid  # JWT 声明优先
    assert body["username"] == "alice"


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


def test_login_empty_password_rejected_422(client):
    """P0-MED-006 防回归：password="" → 422（Pydantic min_length=1）。

    旧实现 min_length=0 允许空密码通过校验，攻击者可枚举 username 配合空
    密码爆破。新规则：空密码直接 422，节省 LDAP 查询。
    """
    r = client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": ""},
    )
    assert r.status_code == 422
    body = r.json()
    # 校验错误必有 password 字段定位
    assert any("password" in str(err).lower() for err in body.get("detail", []))


# ---------------------------------------------------------------------------
# JWT 过期 / 无效细分（TODO-007）
#
# 此前两者都映射 INVALID_TOKEN，前端无法区分「token 过期（该刷新或重登）」
# 和「token 伪造 / 签名不符（该拒绝并告警）」。
# ---------------------------------------------------------------------------


def _expired_token(token_type: str = "access") -> str:
    """造一个已过期的 token（exp 远早于当前时间）。"""
    settings = get_settings()
    payload = {
        "sub": "alice",
        "type": token_type,
        "role": "DESIGNER",
        "exp": 1_000_000,      # 2001 年，远早于现在
        "iat": 999_999,
    }
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def test_expired_access_token_returns_EXPIRED_TOKEN_not_INVALID(client):
    """过期 access token → EXPIRED_TOKEN（可与伪造 token 区分开）。"""
    r = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {_expired_token('access')}"},
    )
    assert r.status_code == 401, r.text
    assert r.json()["code"] == "EXPIRED_TOKEN"


def test_tampered_access_token_stays_INVALID_TOKEN(client):
    """签名不符的 token → 仍是 INVALID_TOKEN（不是 EXPIRED_TOKEN）。"""
    settings = get_settings()
    forged = jwt.encode(
        {"sub": "alice", "type": "access", "role": "SYSTEM_ADMIN",
         "exp": 9_999_999_999, "iat": 1},
        "wrong-secret-key",  # 故意用错密钥
        algorithm="HS256",
    )
    del settings
    r = client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {forged}"}
    )
    assert r.status_code == 401, r.text
    assert r.json()["code"] == "INVALID_TOKEN"


def test_expired_refresh_token_returns_EXPIRED_REFRESH(client):
    """过期 refresh token → EXPIRED_REFRESH（与 access 侧码对称）。"""
    r = client.post(
        "/api/v1/auth/refresh", json={"refresh_token": _expired_token("refresh")}
    )
    assert r.status_code == 401, r.text
    assert r.json()["code"] == "EXPIRED_REFRESH"


# ---------------------------------------------------------------------------
# 登录限流 + 审计（TODO-006）
# ---------------------------------------------------------------------------


def test_login_rate_limited_after_10_attempts(client, patched_ldap):
    """同 IP 连续登录超限 → 429（防暴力破解）。"""
    from app.services._sliding_window_rate_limit import clear_all_rate_limits

    clear_all_rate_limits()
    codes = []
    for _ in range(12):
        r = client.post(
            "/api/v1/auth/login", json={"username": "alice", "password": "x"}
        )
        codes.append(r.status_code)
    assert 429 in codes, f"12 次尝试应触发限流, 实际: {codes}"
    assert codes.index(429) >= 9, f"应放行前 10 次, 实际: {codes}"


@pytest.fixture
def audit_spy(monkeypatch):
    """记录 AuditService.write 调用（不真查库）。

    TestClient 自带 event loop，与测试侧 async engine 跨 loop 复用会炸；
    审计的落库本身另有测试覆盖（F-P0-001 backfill 用例）。此处只验端点
    是否在成功/失败两条路径上都调了审计、参数对不对。
    """
    from app.services.audit_service import AuditService

    calls: list[dict] = []

    async def _fake_write(self, **kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(AuditService, "write", _fake_write, raising=True)
    return calls


def test_login_writes_audit_on_success(client, patched_ldap, audit_spy):
    """登录成功 → 调审计 LOGIN_SUCCESS，带 username + ip。"""
    r = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "x"}
    )
    assert r.status_code == 200, r.text
    assert len(audit_spy) == 1, f"应有且仅有一条登录审计, 实际: {audit_spy}"
    call = audit_spy[0]
    assert call["action"] == "LOGIN_SUCCESS"
    assert call["detail"]["username"] == "alice"


def test_login_writes_audit_on_failure(client, patched_ldap, audit_spy):
    """登录失败 → 调审计 LOGIN_FAILED（暴力破解必须留痕）。"""
    r = client.post(
        "/api/v1/auth/login", json={"username": "alice", "password": "wrong-pw"}
    )
    assert r.status_code == 401
    assert len(audit_spy) == 1, f"失败也必须留痕, 实际: {audit_spy}"
    assert audit_spy[0]["action"] == "LOGIN_FAILED"
    assert audit_spy[0]["detail"]["username"] == "alice"
