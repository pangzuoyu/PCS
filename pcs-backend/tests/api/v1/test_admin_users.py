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
