"""二次认证（MFA 决议路径 B：AD 密码二次输入）。

## 为什么是路径 B 而不是真 MFA

`docs/PCS-NOTE-P9-Prep-MFA决议-2026-10-19.md` §3 已裁决：本版用 AD 密码二次输入，
复用既有 `ldap_client.authenticate`，**不新增凭据通道**。路径 B 是**明确的过渡态**
（SPEC §2.2.4 原文即「MFA 后续替换」）。

## 审计 action 只能是 `SIGN_2FA_FALLBACK`

裁决落地约束 1：**不得**复用 `SIGN_2FA_OK`。后者会让审计读成「已上真 MFA」，
从而掩盖「我们没上真 MFA」这个事实 —— 日后排查时无从知道当前用的是降级方案。
`test_writes_sign_2fa_fallback_audit` 同时断言 FALLBACK 出现、`SIGN_2FA_OK` 不出现。

## ⚠️ 本函数**不豁免** mock

裁决落地约束 4 + §4：mock 豁免的范围**限定在登录层**（「谁来登录」这一步），
`verify_secondary_auth()` 函数本身照常校验。

理由是可核实的，不是「测试环境有豁免、生产没有」那种危险形态：
`app/main.py` 只在 `not is_production` 时挂 mock 路由（且 `mock_auth.py` 内有第二道
`if is_production: raise`），**mock 会话在生产上无法产生**，豁免没有生产面可绕。

⇒ 本模块的单测**直接调函数**，不经 `/auth/mock-login`。若只测经 mock 的链路，
mock 全绿会被读成「二次认证验证过了」，而它其实一次都没跑过。
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import PcsError
from app.models.enums import AuditAction
from app.services import ldap_client
from app.services.audit_service import AuditService


async def verify_secondary_auth(
    *, session: AsyncSession, username: str, password: str
) -> None:
    """校验操作者本人的 AD 密码。失败抛 401 `SECONDARY_AUTH_FAILED`。

    成功也写审计 —— 「谁在什么时候做了二次认证」本身就是要留痕的事实，
    排查代录争议时需要的是「做过」而不只是「成功过」。

    **不 commit**：审计与业务同生共死（同 ADR-0047 §③ 的理由）。

    Args:
        username: 被验证的用户名（代录人本人，不是被代录的客户的）。
        password: 其 AD 密码。**绝不写入审计或日志。**
    """
    if not username or not password:
        # 在进 LDAP 之前就拒：空密码在某些 LDAP 配置下会被当作匿名绑定并
        # 成功返回，那样二次认证就成了永远绿的摆设。
        raise PcsError(
            code="SECONDARY_AUTH_FAILED",
            message="二次认证需要用户名与密码",
            status=401,
        )

    try:
        ldap_client.authenticate(username, password)
    except ldap_client.LdapAuthError as e:
        raise PcsError(
            code="SECONDARY_AUTH_FAILED",
            message="二次认证失败：用户名或密码错误",
            status=401,
        ) from e

    await AuditService(session).write(
        action=AuditAction.SIGN_2FA_FALLBACK,
        resource_type="secondary_auth",
        resource_id=username,
        user_id=None,
        # 刻意不记密码，也不记成功与否之外的任何凭据字段。
        detail={"mechanism": "LDAP_PASSWORD_REAUTH", "fallback": True},
    )
