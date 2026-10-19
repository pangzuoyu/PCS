"""`issue_tokens()` 的测试 —— ADR-0046 §③ 的三条断言在两条路径上都要成立。

**mock 不落库**（§③b）：MOCK_USERS 的 alice 与真实 AD 的 alice 同名 + uuid5 以
username 为键 ⇒ 若落库会污染同一行；而 `app/core/acl.py:13` 明写 `User.roles`
是 ACL 的权威输入。
"""
import uuid

import pytest


async def _mk_user(db_session, *, username="alice", roles=None,
                   token_version=1, status="ACTIVE"):
    from app.models.project import User
    u = User(user_id=uuid.uuid5(uuid.NAMESPACE_DNS, username),
             username=username, display_name=username,
             roles=roles or ["DESIGNER"], ad_groups=[], status=status,
             token_version=token_version)
    db_session.add(u)
    await db_session.flush()
    return u


@pytest.mark.asyncio
async def test_real_login_persists_user_row(db_session):
    """真实路径：惰性建行 + tv = 行内 token_version。"""
    from app.services.token_issuer import issue_tokens
    pair = await issue_tokens(session=db_session, username="bob", role="DESIGNER",
                              persist_user=True)
    from app.models.project import User
    row = (await db_session.execute(
        User.__table__.select().where(User.username == "bob"))).first()
    assert row is not None, "真实登录必须惰性建 users 行"
    assert row.token_version >= 1, "真实用户 token_version 永不为 0（CHECK >= 1）"
    assert pair.token_version == row.token_version


@pytest.mark.asyncio
async def test_mock_does_not_persist(db_session):
    """§③b：mock 绝不写 users 表。"""
    from app.models.project import User
    from app.services.token_issuer import issue_tokens
    await issue_tokens(session=db_session, username="alice", role="DESIGNER",
                       persist_user=False)
    row = (await db_session.execute(
        User.__table__.select().where(User.username == "alice"))).first()
    assert row is None, "mock 建了行 ⇒ 会污染同名真实用户的 roles"


@pytest.mark.asyncio
async def test_mock_tv_is_sentinel_zero(db_session):
    """mock 的 tv = 0（保留值）；真实行出现后（tv>=1）mock 存量令牌自动失效。"""
    from app.services.token_issuer import issue_tokens, verify_refresh_tv
    pair = await issue_tokens(session=db_session, username="carol", role="APPROVER",
                              persist_user=False)
    assert pair.token_version == 0
    # 真实 carol 登录建行后，0 != 1 ⇒ 旧 mock refresh 必须被拒
    assert await verify_refresh_tv(db_session, username="carol", tv=0) is True
    await _mk_user(db_session, username="carol", token_version=1)
    assert await verify_refresh_tv(db_session, username="carol", tv=0) is False


@pytest.mark.asyncio
async def test_tv_actually_lands_in_the_refresh_token(db_session):
    """tv 必须真的写进 JWT claim —— 写不进等于没做，吊销永远不会触发。"""
    from app.core.security import decode_token
    from app.services.token_issuer import issue_tokens
    real = await issue_tokens(session=db_session, username="dave", role="DESIGNER",
                              persist_user=True)
    assert decode_token(real.refresh_token)["tv"] == real.token_version
    mock = await issue_tokens(session=db_session, username="dan", role="SYSTEM_ADMIN",
                              persist_user=False)
    assert decode_token(mock.refresh_token)["tv"] == 0


@pytest.mark.asyncio
async def test_disabled_user_rejected(db_session):
    """§③：停用用户拒绝登录 + 写审计 USER_LOGIN_DENIED_DISABLED。"""
    from app.core.errors import PcsError
    from app.services.token_issuer import issue_tokens
    await _mk_user(db_session, username="erin", status="DISABLED")
    with pytest.raises(PcsError) as ei:
        await issue_tokens(session=db_session, username="erin", role="DESIGNER",
                           persist_user=True)
    assert ei.value.status == 401
    from app.models.system import AuditLog
    rows = (await db_session.execute(
        AuditLog.__table__.select().with_only_columns(AuditLog.__table__.c.action)
        .where(AuditLog.__table__.c.action == "USER_LOGIN_DENIED_DISABLED"))).scalars().all()
    assert rows, "停用拒绝必须写审计，否则无法追责"


@pytest.mark.asyncio
async def test_verify_refresh_tv_accepts_matching_tv(db_session):
    """对照组：tv 相等必须放行 —— 否则正常用户刷新全挂。"""
    from app.services.token_issuer import verify_refresh_tv
    await _mk_user(db_session, username="frank", token_version=3)
    assert await verify_refresh_tv(db_session, username="frank", tv=3) is True
    assert await verify_refresh_tv(db_session, username="frank", tv=2) is False
