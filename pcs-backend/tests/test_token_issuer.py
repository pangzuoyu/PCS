"""`issue_tokens()` 的测试 —— ADR-0046 §③ 的三条断言在两条路径上都要成立。

**mock 不落库**（§③b）：MOCK_USERS 的 alice 与真实 AD 的 alice 同名 + uuid5 以
username 为键 ⇒ 若落库会污染同一行；而 `app/core/acl.py:13` 明写 `User.roles`
是 ACL 的权威输入。
"""
import uuid

import pytest
from sqlalchemy.exc import IntegrityError


async def _mk_user(db_session, *, username="alice", roles=None,
                   token_version=1, status="ACTIVE"):
    from app.models.project import User
    u = User(user_id=uuid.uuid5(uuid.NAMESPACE_DNS, username),
             username=username, display_name=username,
             roles=["DESIGNER"] if roles is None else roles,
             ad_groups=[], status=status,
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


# === T0-E（TODO-134）：真实登录路径补写 `users.roles` ===


@pytest.mark.asyncio
async def test_real_login_fills_roles_of_existing_user(db_session):
    """⚠️ **已有行 `roles=[]` ⇒ 真实登录必须把它补上**（TODO-134）。

    缺陷形状：`ensure_user_row` 建行 `roles=[]`；真实登录**只在建行时**写 roles
    ⇒ 先被 seed 建出来、之后才走真实登录的用户 ⇒ `users.roles` **永远是 `[]`**
    ⇒ 按 `users.roles` 圈人的逻辑（`notification_recipients.py`）**永远选不到他**。
    """
    from app.models.project import User
    from app.services.token_issuer import issue_tokens

    await _mk_user(db_session, username="seeded", roles=[])

    await issue_tokens(
        session=db_session, username="seeded", role="DESIGNER", persist_user=True
    )

    row = (
        await db_session.execute(
            User.__table__.select()
            .with_only_columns(User.__table__.c.roles)
            .where(User.__table__.c.username == "seeded")
        )
    ).first()
    assert row is not None
    assert row.roles == ["DESIGNER"], f"真实登录没补 roles：{row.roles}"


@pytest.mark.asyncio
async def test_real_login_overwrites_roles_with_the_current_role(db_session):
    """⚠️ **真实登录按当前角色覆盖** `users.roles`（不是合并）。

    理由（整批评审 Important #1）：`users.roles` 的权威来源是**真实身份**
    （AD 同步 `ad_sync._apply` 也是**覆盖**：`roles=[role] if role else None`）
    ⇒ 只增不减会让**角色降级永不生效**（降级后仍带着旧角色 ⇒ 按 `users.roles`
    圈人的通知逻辑会**继续找**他 ⇒ 「待办里有、点进去说你不是」）。

    ⇒ 与 AD 同步**同口径**：覆盖。
    """
    from app.models.project import User
    from app.services.token_issuer import issue_tokens

    await _mk_user(db_session, username="seeded2", roles=["CHECKER"])

    await issue_tokens(
        session=db_session, username="seeded2", role="DESIGNER", persist_user=True
    )

    row = (
        await db_session.execute(
            User.__table__.select()
            .with_only_columns(User.__table__.c.roles)
            .where(User.__table__.c.username == "seeded2")
        )
    ).first()
    assert row is not None
    assert row.roles == ["DESIGNER"], f"角色降级没生效（旧角色还在）：{row.roles}"


@pytest.mark.asyncio
async def test_real_login_is_idempotent_about_roles(db_session):
    """重复登录**不重复追加**同一个角色。"""
    from app.models.project import User
    from app.services.token_issuer import issue_tokens

    await _mk_user(db_session, username="seeded3", roles=[])
    for _ in range(2):
        await issue_tokens(
            session=db_session, username="seeded3", role="DESIGNER", persist_user=True
        )

    row = (
        await db_session.execute(
            User.__table__.select()
            .with_only_columns(User.__table__.c.roles)
            .where(User.__table__.c.username == "seeded3")
        )
    ).first()
    assert row is not None
    assert row.roles == ["DESIGNER"], f"重复追加了：{row.roles}"


@pytest.mark.asyncio
async def test_mock_login_does_not_touch_roles(db_session):
    """⚠️ **对照组**：mock 登录**不得**改 `roles`（ADR-0046 §③b）。

    mock 与真实 AD **同名** ⇒ mock 写真实角色 ⇒ 污染同一行 ⇒ **权限污染且不报错**。
    """
    from app.models.project import User
    from app.services.token_issuer import issue_tokens

    await _mk_user(db_session, username="alice", roles=[])

    await issue_tokens(
        session=db_session, username="alice", role="SYSTEM_ADMIN", persist_user=False
    )

    row = (
        await db_session.execute(
            User.__table__.select()
            .with_only_columns(User.__table__.c.roles)
            .where(User.__table__.c.username == "alice")
        )
    ).first()
    assert row is not None
    assert row.roles == [], f"mock 改了 roles ⇒ 污染真实用户：{row.roles}"


# === 评审 #25：并发首次登录 ⇒ 不能变成 500 ===


class _FakeRow:
    """一行 `users` 的最小替身（只带被读到的字段）。"""

    def __init__(self, *, username, user_id, token_version=1, status="ACTIVE", roles=None):
        self.username = username
        self.user_id = user_id
        self.token_version = token_version
        self.status = status
        self.roles = roles if roles is not None else []


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def first(self):
        return self._row


class _RaceSession:
    """模拟「并发首次登录」：**第一次 SELECT 见空** ⇒ flush 撞唯一约束。

    ⚠️ 真库上：两个请求同时「SELECT 见空」⇒ 都 INSERT ⇒ **输家**撞
    `users.username` 唯一约束 ⇒ `IntegrityError`（**不是** `PcsError`）
    ⇒ 端点只捕 `PcsError` ⇒ 裸穿成 **500 INTERNAL_ERROR**
    ⇒ 用户看到一个无任何解释的 500（而且是**偶发**的 ⇒ 极难复现）。
    """

    def __init__(self, *, username, user_id):
        self.selects = 0
        self.added = []
        self.rolled_back = False
        self._row = _FakeRow(username=username, user_id=user_id)

    async def execute(self, stmt):
        self.selects += 1
        # ⚠️ **第一次** SELECT 见空（模拟「还没建行」）⇒ 走惰性建行分支
        return _FakeResult(None if self.selects == 1 else self._row)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        raise IntegrityError(
            "INSERT INTO users ...",
            params=None,
            orig=Exception(
                'violates unique constraint "users_username_key"'
            ),
        )

    async def rollback(self):
        self.rolled_back = True


@pytest.mark.asyncio
async def test_concurrent_first_login_race_does_not_become_a_500():
    """⚠️ **并发首次登录** ⇒ 撞唯一约束**不是** 500（评审 #25）。

    ⇒ 「另一个请求已经把行建好了」⇒ 回滚自己这次插入 ⇒ 重读那一行 ⇒ 照常签发。
    """
    from app.services.token_issuer import derive_user_id, issue_tokens

    username = "racer"
    session = _RaceSession(username=username, user_id=derive_user_id(username))

    pair = await issue_tokens(
        session=session, username=username, role="DESIGNER", persist_user=True
    )

    # ⚠️ 不抛 ⇒ 没变成 500
    assert pair.token_version == 1
    # ⚠️ 撞车后必须**回滚**自己那次插入（否则会话留在失败态 ⇒ 后续全挂）
    assert session.rolled_back is True
    # ⚠️ 签发用的是**那一行**的 tv（不是保留值 0）
    assert pair.token_version == session._row.token_version
