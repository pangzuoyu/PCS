"""登录签发的**唯一**路径（ADR-0046 §③）。

`/auth/login`（真实 LDAP）与 `/auth/mock-login`（开发 mock）都经 `issue_tokens()`，
差别只在 `persist_user` 一个布尔：

- `persist_user=True`（真实）：查 `users` 行 —— `DISABLED` → 401 + 审计；
  无行则**惰性建** ACTIVE 行；`tv` = 行内 `token_version`。
- `persist_user=False`（mock）：**不查不写** `users` 表，`tv` = 保留值 0。

## 为什么 mock 必须不落库（§③b）

`MOCK_USERS` 的 alice 与真实 AD 的 alice **同名**，而 user_id 用
`uuid5(NAMESPACE_DNS, username)` 派生 ⇒ 两者会落进同一行。mock 的角色会经惰性建行
写进 `users.roles`，而 `app/core/acl.py:13` 明写 `User.roles` 是 ACL 的权威输入
⇒ mock 污染 = 权限污染，且**不报错**。

## 为什么 `tv` 的真值只能是行内 `token_version`

`token_version` 是 DB 里的整数，任何进程都能读到；内存黑名单做不到
（多 worker 静默失效 —— 与 TODO-047 的 `advisory_lock` 同构陷阱）。
因此本模块**不提供**任何覆盖 tv 的入参：想改吊销版本只能 UPDATE 那一行。
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.core.security import create_access_token, create_refresh_token
from app.models.enums import UserStatus

#: 保留值：mock 令牌的 `tv` 哨兵。真实用户 `token_version >= 1`
#: （DB 层 `ck_users_token_version_ge_1` 兜住，ADR-0046 §③b）。
MOCK_TV_SENTINEL = 0


@dataclass(frozen=True)
class IssuedTokens:
    """一次签发的结果。`token_version` 是**盖进 refresh token 的那个 tv**。

    单独返回它，是为了让调用方与测试都能断言「签发时用的 tv」，
    而不必去 decode JWT 再猜。
    """

    access_token: str
    refresh_token: str
    token_version: int
    user_id: uuid.UUID


def derive_user_id(username: str) -> uuid.UUID:
    """user_id 的**唯一**派生点：`uuid5(NAMESPACE_DNS, username)`。

    单点派生是刻意的：`auth.py` 的 login、JWT 的 `user_id` claim、惰性建行
    三处必须算出同一个 id，分开写就有分叉风险。
    """
    return uuid.uuid5(uuid.NAMESPACE_DNS, username)


async def issue_tokens(
    *,
    username: str,
    role: str,
    persist_user: bool,
    session: AsyncSession | None = None,
) -> IssuedTokens:
    """签发 access/refresh 对（ADR-0046 §③ 的三条断言都在这里落地）。

    Args:
        persist_user: True = 真实登录（需要 `session`）；False = mock（不碰 DB）。
        session: 仅 `persist_user=True` 时使用 —— mock 路径刻意不要求它，
            这样 mock 端点不必为了「证明不落库」而先建立一个 DB 会话。

    Raises:
        PcsError: 401 —— 用户已停用（仅 `persist_user=True` 可能）。
    """
    user_id = derive_user_id(username)

    if not persist_user:
        # mock 路径：一次 DB 往返都没有 —— 连 SELECT 都不能有，
        # 否则「不落库」的保证会退化成「不 INSERT 但会读」。
        return sign_with_tv(username, role, user_id, tv=MOCK_TV_SENTINEL)

    if session is None:
        raise ValueError("persist_user=True 时 session 必填")
    from app.models.project import User

    row = (
        await session.execute(
            User.__table__.select().where(User.username == username)
        )
    ).first()

    if row is not None and row.status == UserStatus.DISABLED.value:
        await _record_denied_login(session, username=username, user_id=user_id)
        raise PcsError(
            code="USER_DISABLED",
            message=f"user disabled: {username}",
            status=401,
        )

    if row is None:
        session.add(
            User(
                user_id=user_id,
                username=username,
                display_name=username,
                roles=[role],
                ad_groups=[],
                status=UserStatus.ACTIVE.value,
            )
        )
        await session.flush()
        # flush 后 server_default '1' 才会落到 python 侧对象上
        row = (
            await session.execute(
                User.__table__.select().where(User.username == username)
            )
        ).first()
        assert row is not None, "惰性建行后仍查不到 —— session 状态异常"

    return sign_with_tv(username, role, user_id, tv=row.token_version)


async def effective_token_version(session: AsyncSession, *, username: str) -> int:
    """该用户名**当前**应当匹配的 tv。

    无 `users` 行 ⇒ 保留值 0（mock 路径按定义不落库）。
    有行 ⇒ 行内 `token_version`。

    单独抽出来是因为 refresh 端点需要它**两次**：比对一次、重签时写进
    新令牌一次。分成两个函数（一个返回 bool、一个再查一次）会多一次往返，
    且「tv 到底以谁为准」在两处各写一遍 —— 那正是这个 bug 的形状。
    """
    from app.models.project import User

    row = (
        await session.execute(
            User.__table__.select()
            .with_only_columns(User.__table__.c.token_version)
            .where(User.username == username)
        )
    ).first()
    return MOCK_TV_SENTINEL if row is None else row.token_version


async def verify_refresh_tv(session: AsyncSession, *, username: str, tv: int) -> bool:
    """refresh 时比对 claim 的 `tv` 与行内 `token_version`。

    无 `users` 行 + `tv == 0` ⇒ 放行（mock 路径，按定义不落库）。
    有行 ⇒ 必须相等；不等说明用户被停用过，已发的 refresh 全部作废。
    """
    return tv == await effective_token_version(session, username=username)


def sign_with_tv(username: str, role: str, user_id: uuid.UUID, *, tv: int) -> IssuedTokens:
    """按给定 `tv` 签发一对令牌。**`/auth/login` 与 `/auth/refresh` 都必须走它**。

    两处若各签一次，refresh 那条迟早会漏掉 `tv` —— 而漏掉的症状是
    「第二次刷新必 401」（`tv` 缺失被当作 0，与行内 `>= 1` 不等），
    分段测试很容易全部漏过。

    `tv` **只写进 refresh**（ADR-0046 §④）：access 保持无状态，
    吊销粒度是「refresh 时生效」，不是秒级 —— SPEC P9A-USR-007 明确接受。
    写进 access 不会更安全，只会让「在手 access 仍可用至过期」这条边界
    的表述与代码对不上。
    """
    return IssuedTokens(
        access_token=create_access_token(
            subject=username, role=role, extra={"user_id": str(user_id)}
        ),
        refresh_token=create_refresh_token(
            subject=username, role=role,
            extra={"user_id": str(user_id), "tv": tv},
        ),
        token_version=tv,
        user_id=user_id,
    )


async def _record_denied_login(
    session: AsyncSession, *, username: str, user_id: uuid.UUID
) -> None:
    """停用拒绝也要留痕 —— 没有失败记录，停用策略就完全无痕。

    单独 commit：随后要抛异常，不 commit 这条审计会随事务一起回滚，
    等于「拒绝了但没记录」。
    """
    from app.models.enums import AuditAction
    from app.services.audit_service import AuditService

    await AuditService(session).write(
        action=AuditAction.USER_LOGIN_DENIED_DISABLED,
        resource_type="AUTH",
        resource_id=username,
        user_id=user_id,
        detail={"username": username},
    )
    await session.commit()
