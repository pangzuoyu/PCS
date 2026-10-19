"""ADMIN 用户端点（SPEC P9A-ADM-001/002，ADR-0046 §⑤）。

两条端点是 `P9A-USR-004`（离职处理）的验收载体，SPEC 明写「不是可选项」。
`test_admin_routes_mounted_unconditionally` 守的是本文件最容易犯的错：
把 `mock_auth` 的「非生产才挂载」形态照抄过来 —— 那个是「生产不该有」，
这个是「生产必须有」，照抄则生产上永远无法停用任何人。
"""
import uuid

import pytest


def _token(username: str, role: str) -> dict[str, str]:
    from app.core.security import create_access_token
    return {"Authorization": f"Bearer {create_access_token(subject=username, role=role)}"}


ADMIN = _token("root", "SYSTEM_ADMIN")
DESIGNER = _token("dev1", "DESIGNER")


async def _mk_user(db_session, *, username="alice", status="ACTIVE", token_version=1):
    from app.models.project import User
    u = User(user_id=uuid.uuid5(uuid.NAMESPACE_DNS, username),
             username=username, display_name=username,
             roles=["DESIGNER"], ad_groups=[], status=status,
             token_version=token_version)
    db_session.add(u)
    await db_session.flush()
    return u


def test_admin_routes_mounted_unconditionally():
    """admin 端点必须挂在 `api_router` 上（main.py 无条件 include）。

    对照断言：mock-login **不在** `api_router` 里 —— 它只在 main.py 非生产
    环境单独挂载。两者形态相反，混用就是把「生产不需要」套到「生产必须有」。
    """
    from fastapi import FastAPI

    from app.api.v1 import api_router

    app = FastAPI()
    app.include_router(api_router)
    paths = app.openapi()["paths"]

    assert "/api/v1/admin/users" in paths, paths.keys()
    assert "/api/v1/admin/users/{user_id}/disable" in paths, paths.keys()
    assert "/api/v1/auth/mock-login" not in paths, \
        "mock-login 若出现在 api_router，说明有人把 admin 端点照抄成了 mock 形态"


@pytest.mark.asyncio
async def test_list_users_requires_system_admin(client):
    r = await client.get("/api/v1/admin/users", headers=DESIGNER)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_disable_requires_system_admin(client, db_session):
    u = await _mk_user(db_session, username="bob")
    r = await client.put(f"/api/v1/admin/users/{u.user_id}/disable", headers=DESIGNER)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_list_users_returns_rows(client, db_session):
    await _mk_user(db_session, username="carol")
    r = await client.get("/api/v1/admin/users", headers=ADMIN)
    assert r.status_code == 200, r.text
    names = [u["username"] for u in r.json()]
    assert "carol" in names


@pytest.mark.asyncio
async def test_disable_increments_token_version(client, db_session):
    """同事务 tv += 1 —— 这是「在手令牌立即失效」的全部机制（ADR-0046 §⑤）。"""
    u = await _mk_user(db_session, username="dan", token_version=1)
    r = await client.put(f"/api/v1/admin/users/{u.user_id}/disable", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["token_version"] == 2
    await db_session.refresh(u)
    assert u.token_version == 2
    assert u.status == "DISABLED"


@pytest.mark.asyncio
async def test_disable_writes_audit(client, db_session):
    from app.models.system import AuditLog
    u = await _mk_user(db_session, username="erin")
    await client.put(f"/api/v1/admin/users/{u.user_id}/disable", headers=ADMIN)
    rows = (await db_session.execute(
        AuditLog.__table__.select().with_only_columns(AuditLog.__table__.c.action)
        .where(AuditLog.__table__.c.action == "USER_DISABLED"))).scalars().all()
    assert rows, "停用必须写审计，否则无法追责「谁停的」"


@pytest.mark.asyncio
async def test_disable_unknown_user_returns_404(client):
    r = await client.put(f"/api/v1/admin/users/{uuid.uuid4()}/disable", headers=ADMIN)
    assert r.status_code == 404, r.text


@pytest.mark.asyncio
async def test_disabled_user_refresh_returns_401(client, db_session):
    """P9A-USR-004 的验收标准：停用后该用户存量 refresh 立即 401。"""
    from app.core.security import create_refresh_token
    u = await _mk_user(db_session, username="frank", token_version=1)
    stale = create_refresh_token(subject="frank", role="DESIGNER", extra={"tv": 1})

    r = await client.put(f"/api/v1/admin/users/{u.user_id}/disable", headers=ADMIN)
    assert r.status_code == 200, r.text

    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": stale})
    assert r.status_code == 401, r.text


# --- SPEC P9A-USR-002：手动触发 AD 同步 ---

@pytest.mark.asyncio
async def test_sync_endpoint_requires_system_admin(client):
    r = await client.post("/api/v1/admin/users/sync", headers=DESIGNER)
    assert r.status_code == 403, r.text


@pytest.mark.asyncio
async def test_sync_endpoint_503_when_service_account_absent(client, monkeypatch):
    """未配置必须**明确 503**，不能返回 200 空结果 —— 那会让运维以为同步过了。"""
    import app.core.config as cfg
    monkeypatch.setattr(cfg.get_settings(), "ldap_bind_dn", "", raising=False)
    r = await client.post("/api/v1/admin/users/sync", headers=ADMIN)
    assert r.status_code == 503, r.text
    assert r.json()["code"] == "LDAP_SYNC_NOT_CONFIGURED"


@pytest.mark.asyncio
async def test_sync_endpoint_returns_counts(client, db_session, monkeypatch):
    import app.core.config as cfg
    from app.services import ad_sync
    from tests.services.test_ad_sync import _AdUser

    monkeypatch.setattr(cfg.get_settings(), "ldap_bind_dn", "cn=svc,DC=test",
                        raising=False)
    monkeypatch.setattr(ad_sync, "enumerate_users", lambda: iter([
        _AdUser("alice", "Alice", "a@c", "P", ("DESIGNER_GROUP",)),
    ]))
    r = await client.post("/api/v1/admin/users/sync", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1


@pytest.mark.asyncio
async def test_p9a_usr_004_acceptance_chain(client, db_session, monkeypatch):
    """SPEC P9A-USR-004 的完整验收链（计划 A3 Step 4 要求的「演示脚本」变成测试）：

        POST /auth/login 建行 → GET /admin/users 可见 → disable
        → 该用户**登录时拿到的那个** refresh 立即 401

    之前的三条测试各自只验一段；这条是唯一把它们串起来、且用真实登录令牌
    （不是手工造的）的断言。手工造令牌会绕过「登录时 tv 是多少」这个环节，
    而那正是要验的东西。
    """
    import app.api.v1.auth as auth_mod
    import app.services.ldap_client as ldap_mod

    monkeypatch.setattr(auth_mod, "authenticate", lambda u, p: ldap_mod.LdapUser(
        username=u, dn=f"cn={u},CN=Users,DC=test,DC=local",
        groups=("cn=DESIGNER_GROUP,ou=Groups,dc=test,dc=local",),
        display_name=u.title(),
    ))
    monkeypatch.setattr(ldap_mod, "authenticate", auth_mod.authenticate)

    # 1) 真实登录 —— 惰性建行 + 签发带 tv 的 refresh
    r = await client.post("/api/v1/auth/login",
                          json={"username": "grace", "password": "pw"})
    assert r.status_code == 200, r.text
    login_refresh = r.json()["refresh_token"]

    # 2) ADMIN 列表里看得到
    r = await client.get("/api/v1/admin/users", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert "grace" in [u["username"] for u in r.json()]

    # 3) 停用
    row = next(u for u in r.json() if u["username"] == "grace")
    assert row["status"] == "ACTIVE" and row["token_version"] == 1
    r = await client.put(f"/api/v1/admin/users/{row['user_id']}/disable", headers=ADMIN)
    assert r.status_code == 200, r.text
    assert r.json()["token_version"] == 2

    # 4) 登录时拿到的那个 refresh 立即失效
    r = await client.post("/api/v1/auth/refresh",
                          json={"refresh_token": login_refresh})
    assert r.status_code == 401, r.text

    # 5) 该用户也不能再登录
    r = await client.post("/api/v1/auth/login",
                          json={"username": "grace", "password": "pw"})
    assert r.status_code == 401, r.text
