"""二次认证单测（MFA 决议 §4：路径 B = AD 密码二次输入 + `SIGN_2FA_FALLBACK`）。

## 为什么这些测试**不走** mock 登录路径

MFA 决议 §4 把 mock 豁免的**范围限定在登录层**：「谁来登录」这一步豁免，
`verify_secondary_auth()` 函数本身不得豁免。所以本文件直接调函数，
不经过 `/auth/mock-login`。

理由写死在决议里：**若只测经 mock 的链路，mock 全绿会被读成「二次认证验证过了」，
而它其实没跑过** —— mock 用户根本没有 AD 密码可输。

## 审计 action 是这层唯一能保证的事

`SIGN_2FA_FALLBACK` 而不是 `SIGN_2FA_OK`：后者会掩盖「我们没上真 MFA」这个事实，
使日后审计读不出当前用的是降级方案。故断言 action 名，且断言 `SIGN_2FA_OK` 不出现。
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.errors import PcsError
from app.models.system import AuditLog
from app.services import ldap_client
from app.services.secondary_auth import verify_secondary_auth

pytestmark = pytest.mark.asyncio


def _ok_authenticator(monkeypatch):
    """把 LDAP bind 换成「恒成功」，记录被调用参数。"""
    calls: list[tuple[str, str]] = []

    def _fake(username: str, password: str) -> ldap_client.LdapUser:
        calls.append((username, password))
        return ldap_client.LdapUser(
            username=username, dn=f"CN={username}", groups=("CN=PCS-DESIGNER",)
        )

    monkeypatch.setattr(ldap_client, "authenticate", _fake)
    return calls


def _failing_authenticator(monkeypatch):
    def _fake(username: str, password: str):
        raise ldap_client.LdapAuthError("bind failed")

    monkeypatch.setattr(ldap_client, "authenticate", _fake)


async def _actions(db) -> list[str]:
    rows = (await db.execute(select(AuditLog))).scalars().all()
    return [r.action for r in rows]


class TestSecondaryAuth:
    async def test_succeeds_with_valid_password(self, db_session, monkeypatch):
        _ok_authenticator(monkeypatch)

        await verify_secondary_auth(
            session=db_session, username="alice", password="correct-password"
        )

    async def test_writes_sign_2fa_fallback_audit(self, db_session, monkeypatch):
        """成功也写审计 —— 成功与失败都是「谁在什么时候做了二次认证」的证据。"""
        _ok_authenticator(monkeypatch)

        await verify_secondary_auth(
            session=db_session, username="alice", password="correct-password"
        )
        await db_session.commit()

        actions = await _actions(db_session)
        assert "SIGN_2FA_FALLBACK" in actions, actions
        assert "SIGN_2FA_OK" not in actions, (
            "复用了 SIGN_2FA_OK —— 审计会读成「已上真 MFA」，"
            "而路径 B 明确是降级方案（MFA 决议落地约束 1）"
        )

    async def test_raises_on_wrong_password(self, db_session, monkeypatch):
        """失败抛 PcsError —— **不经 mock 登录路径**。

        mock 用户没有 AD 密码；若这条测试走 mock 登录，它会全绿而二次认证
        一次都没跑过 —— 那正是 MFA 决议 §4 要防的误读。
        """
        _failing_authenticator(monkeypatch)

        with pytest.raises(PcsError):
            await verify_secondary_auth(
                session=db_session, username="alice", password="wrong"
            )

    async def test_rejects_empty_credentials(self, db_session, monkeypatch):
        """空用户名/密码必须在**进 LDAP 之前**就拒。

        空密码在某些 LDAP 配置下会被当作匿名绑定并**成功返回** ——
        那样二次认证就成了永远绿的摆设。断言 LDAP 一次都没被调用。
        """
        calls = _ok_authenticator(monkeypatch)

        with pytest.raises(PcsError):
            await verify_secondary_auth(
                session=db_session, username="alice", password=""
            )

        assert calls == [], "空凭据仍打到了 LDAP"

    async def test_does_not_commit(self, db_session, monkeypatch):
        """写入方不自己 commit —— 审计与业务同生共死，同 ADR-0047 §③。"""
        _ok_authenticator(monkeypatch)

        await verify_secondary_auth(
            session=db_session, username="alice", password="correct-password"
        )
        await db_session.rollback()

        assert await _actions(db_session) == []

    async def test_password_is_never_written_to_audit(self, db_session, monkeypatch):
        """审计里不得出现密码 —— 审计表会被导出、被翻查。"""
        _ok_authenticator(monkeypatch)

        await verify_secondary_auth(
            session=db_session, username="alice", password="super-secret-pw"
        )
        await db_session.commit()

        rows = (await db_session.execute(select(AuditLog))).scalars().all()
        for row in rows:
            assert "super-secret-pw" not in str(row.detail_json)
