"""LDAP 简易封装。Task 9 用，Task 10 引入 mock 旁路。"""

from __future__ import annotations

from dataclasses import dataclass

import ldap3
from ldap3.core.exceptions import LDAPException

from app.core.config import get_settings


@dataclass(frozen=True)
class LdapUser:
    username: str
    dn: str
    groups: tuple[str, ...]
    display_name: str | None = None


class LdapAuthError(Exception):
    """绑定失败 / 用户不存在 / 凭据错。"""


def authenticate(username: str, password: str) -> LdapUser:
    """bind 用户，成功返回 LdapUser。失败抛 LdapAuthError。

    settings.ldap_user_dn_template 含 {username} 占位符；组信息以 memberOf 读取。
    """
    settings = get_settings()
    if not username or not password:
        raise LdapAuthError("empty credentials")
    user_dn = settings.ldap_user_dn_template.format(username=username)

    server = ldap3.Server(settings.ldap_url, get_info=ldap3.NONE)
    try:
        conn = ldap3.Connection(
            server, user=user_dn, password=password, auto_bind=True, read_only=True
        )
    except LDAPException as e:
        raise LdapAuthError(str(e)) from e

    try:
        conn.search(
            search_base=user_dn,
            search_filter="(objectClass=*)",
            attributes=["memberOf", "displayName", "cn"],
        )
        groups: list[str] = []
        display_name: str | None = None
        if conn.entries:
            entry = conn.entries[0]
            if "memberOf" in entry:
                groups = [str(g) for g in entry.memberOf.values]
            if "displayName" in entry:
                display_name = str(entry.displayName)
    finally:
        conn.unbind()

    return LdapUser(
        username=username, dn=user_dn, groups=tuple(groups), display_name=display_name
    )


def resolve_role(groups: tuple[str, ...]) -> str:
    """按 Settings.ldap_group_role_map 反查角色。空 → DESIGNER（最小权限默认）。"""
    mapping = get_settings().group_role_map()
    group_cns = {_extract_cn(g) for g in groups}
    for group_cn, role in mapping.items():
        if group_cn in group_cns:
            return role
    return "DESIGNER"


def _extract_cn(group_dn: str) -> str:
    """从 'cn=DESIGNER_GROUP,ou=Groups,dc=test,dc=local' 提取 'DESIGNER_GROUP'。"""
    for part in group_dn.split(","):
        part = part.strip()
        if part.lower().startswith("cn="):
            return part[3:]
    return group_dn
