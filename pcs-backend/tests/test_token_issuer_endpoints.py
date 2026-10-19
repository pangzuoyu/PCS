"""两个签发端点 + refresh 的 tv 比对 —— service 层的断言不够，端点才是真实入口。

覆盖：
- `/auth/mock-login` 端到端**不落库**（§③b 的承诺对调用方成立，而不只是对函数成立）
- `/auth/refresh` 按 `tv` 拒绝被停用用户的存量令牌（ADR-0046 §④）
"""
import uuid

import pytest


async def _mk_user(db_session, *, username, token_version=1, status="ACTIVE"):
    from app.models.project import User
    u = User(user_id=uuid.uuid5(uuid.NAMESPACE_DNS, username),
             username=username, display_name=username,
             roles=["DESIGNER"], ad_groups=[], status=status,
             token_version=token_version)
    db_session.add(u)
    await db_session.commit()
    # ⚠️ 必须 commit，不能只 flush：`client` fixture 的 session 与 `db_session`
    # 共用同一个 SQLite :memory: 连接，跨请求时未提交的行会随上一个请求结束
    # 一起回滚 —— 症状是「第一个请求通过、第二个请求说用户不存在」，
    # 与被测代码无关，纯属 fixture 制造的假故障。


def _refresh_token(username: str, tv: int) -> str:
    from app.core.security import create_refresh_token
    return create_refresh_token(subject=username, role="DESIGNER",
                                extra={"tv": tv})


@pytest.mark.asyncio
async def test_mock_login_endpoint_does_not_create_user_row(db_engine, db_session):
    """mock 端点端到端不落库。

    mock router 不在 `api_router` 里（只在 `main.py` 非生产环境挂载），
    所以这里自建 app —— 与 `tests/test_mock_auth.py` 同一手法。
    """
    import httpx
    from fastapi import FastAPI
    from httpx import ASGITransport
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.api.v1.mock_auth import router as mock_auth_router
    from app.core.errors import install_exception_handlers
    from app.db.session import get_db

    app = FastAPI()
    app.include_router(mock_auth_router)
    install_exception_handlers(app)
    factory = async_sessionmaker(db_engine, expire_on_commit=False)

    async def _override_get_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = _override_get_db
    async with httpx.AsyncClient(transport=ASGITransport(app=app),
                                 base_url="http://test") as mock_client:
        r = await mock_client.post("/auth/mock-login", json={"username": "alice"})
    assert r.status_code == 200, r.text
    from app.models.project import User
    rows = (await db_session.execute(
        User.__table__.select().where(User.username == "alice"))).all()
    assert not rows, "mock 登录建了 users 行"


@pytest.mark.asyncio
async def test_refresh_rejects_stale_tv(client, db_session):
    """用户被停用（tv 1 -> 2）后，存量 refresh 必须 401。"""
    await _mk_user(db_session, username="gina", token_version=2)
    r = await client.post("/api/v1/auth/refresh",
                          json={"refresh_token": _refresh_token("gina", 1)})
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_refresh_accepts_matching_tv(client, db_session):
    await _mk_user(db_session, username="hank", token_version=2)
    r = await client.post("/api/v1/auth/refresh",
                          json={"refresh_token": _refresh_token("hank", 2)})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_refresh_allows_mock_tv_when_no_user_row(client):
    """mock 的 tv=0 且无 users 行 ⇒ 放行。这是 mock 路径的定义，不是漏洞。"""
    r = await client.post("/api/v1/auth/refresh",
                          json={"refresh_token": _refresh_token("ivy", 0)})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_refresh_rejects_mock_tv_once_real_row_exists(client, db_session):
    """同名真实用户一旦建行，旧的 mock 令牌立刻全部作废（§③b 的自动收敛）。"""
    await _mk_user(db_session, username="jack", token_version=1)
    r = await client.post("/api/v1/auth/refresh",
                          json={"refresh_token": _refresh_token("jack", 0)})
    assert r.status_code == 401, r.text


@pytest.mark.asyncio
async def test_refresh_twice_in_a_row_succeeds(client, db_session):
    """⚠️ 回归：refresh 必须能**连续**做两次。

    第一次 refresh 换出的新 refresh 若丢了 `tv` claim，第二次就会拿
    `payload.get("tv", 0)` 去比对行内的 `token_version`（>= 1）⇒ 401。
    症状是「所有真实用户第二次刷新必被登出」，而分段测试全都测不出来 ——
    之前的用例全是手工造带 tv 的令牌，绕过了签发这一环。
    """
    from app.core.security import decode_token
    await _mk_user(db_session, username="kate", token_version=1)
    first = _refresh_token("kate", 1)

    r1 = await client.post("/api/v1/auth/refresh", json={"refresh_token": first})
    assert r1.status_code == 200, r1.text
    second = r1.json()["refresh_token"]
    assert decode_token(second)["tv"] == 1, "换出的 refresh 必须带 tv claim"

    r2 = await client.post("/api/v1/auth/refresh", json={"refresh_token": second})
    assert r2.status_code == 200, r2.text

    r3 = await client.post("/api/v1/auth/refresh",
                           json={"refresh_token": r2.json()["refresh_token"]})
    assert r3.status_code == 200, r3.text


@pytest.mark.asyncio
async def test_access_token_does_not_carry_tv(db_session):
    """ADR-0046 §④：access token **不写** tv（保持无状态，P9A-USR-007 接受该粒度）。

    写成有 tv 不会更安全 —— 没有任何 access 校验路径读它，只会让
    「在手 access 仍可用至过期」这条已知边界的表述与代码对不上。
    """
    from app.core.security import decode_token
    from app.services.token_issuer import issue_tokens
    pair = await issue_tokens(session=db_session, username="liam", role="DESIGNER",
                              persist_user=True)
    assert "tv" not in decode_token(pair.access_token)
    assert decode_token(pair.refresh_token)["tv"] == pair.token_version
