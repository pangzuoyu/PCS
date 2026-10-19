"""LDAP 简易封装。Task 9 用，Task 10 引入 mock 旁路。"""

from __future__ import annotations

from dataclasses import dataclass

import ldap3
from ldap3.core.exceptions import LDAPException

from app.core.config import get_settings
from app.core.errors import PcsError

# RFC 4514 §2.4 DN 转义字符。反斜杠必须最先转义避免双重转义。
_LDAP_DN_ESCAPE_MAP = {
    "\\": r"\\",
    '"': r"\"",
    "#": r"\#",
    "+": r"\+",
    ",": r"\,",
    ";": r"\;",
    "<": r"\<",
    "=": r"\=",
    ">": r"\>",
    "\x00": r"\00",
}


def _sanitize_dn_component(value: str) -> str:
    """RFC 4514 §2.4 DN 组件转义：防止 DN injection（`,` `=` `+` 等破坏 DN 边界）。

    NUL（`\\x00`）按 RFC 4514 编码为多字符序列 `\\00`，与其它单字符转义不同，
    因此先跑单字符转表（NUL 不在表中保持原样），最后再单独替换 `\\x00` → `\\00`，
    避免 pre-replace 后又被反斜杠转义二次翻倍。
    """
    escaped = "".join(_LDAP_DN_ESCAPE_MAP.get(ch, ch) for ch in value)
    if "\x00" in escaped:
        escaped = escaped.replace("\x00", "\\00")
    return escaped


@dataclass(frozen=True)
class LdapUser:
    """LDAP 认证返回的用户（username + dn + 所属组 + 可选显示名）。

    dn：RFC 4514 §2.4 转义后的 distinguished name；groups：所属 LDAP 组的 cn 列表
    （用于映射 PCS 角色 ROLE_ADMIN/ROLE_ENGINEER/ROLE_VIEWER 等）。
    """

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
    safe_username = _sanitize_dn_component(username)
    user_dn = settings.ldap_user_dn_template.format(username=safe_username)

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


#: 目录里 username 的候选属性（OpenLDAP `uid` / AD `sAMAccountName`）。
_USERNAME_ATTRS = ("uid", "sAMAccountName")


@dataclass(frozen=True)
class DirectoryUser:
    """目录里的一条用户（AD 同步的输入，`enumerate_users` 的返回项）。

    与 `LdapUser` 分开：那个是「某个人的 bind 结果」（含 dn），
    这个是「扫目录得到的条目」（无 dn，且 username 可能来自 `uid`/`sAMAccountName`）。
    """

    username: str
    display_name: str | None
    email: str | None
    department: str | None
    groups: tuple[str, ...]


def _first(entry: object, attr: str) -> str | None:
    """ldap3 的多值属性取第一个；属性缺失或空 → None。"""
    values = getattr(entry, attr, None)
    if not values:
        return None
    return str(values[0])


def enumerate_users() -> list[DirectoryUser]:
    """用**服务账号**枚举目录用户（SPEC P9A-USR-002）。

    为什么不能用 `authenticate()`：那条路是以终端用户身份 bind，
    只能读到自己 —— 枚举、离职检测、每日全量都需要读别人的条目。

    filter 与属性名走 `ldap_user_filter` / `ldap_user_attrs` 配置：
    AD 与 OpenLDAP 的属性名不同，写死换目录就得改代码。

    Raises:
        PcsError: 配置缺失或 bind/search 失败。**必须抛，不能返回空列表** ——
            调用方靠异常区分「目录连不上」与「目录里没人」，而这两者的
            处置完全相反（前者 no-op，后者全员离职）。
    """
    settings = get_settings()
    if not settings.ldap_bind_dn:
        raise PcsError(
            code="LDAP_SYNC_NOT_CONFIGURED",
            message="LDAP_BIND_DN 未配置，无法枚举目录",
            status=503,
        )
    attributes = [a.strip() for a in settings.ldap_user_attrs.split(",") if a.strip()]
    # ldap3 **只返回请求过的属性**。username 是同步的主键，不能靠运维记得
    # 把它写进 LDAP_USER_ATTRS —— 漏了会得到一批 username=None 的条目，
    # 而那些行既建不出来也匹配不上，且**不报错**。两个候选都带上（OpenLDAP=uid，
    # AD=sAMAccountName），取到哪个算哪个。
    for attr in _USERNAME_ATTRS:
        if attr not in attributes:
            attributes.append(attr)
    server = ldap3.Server(settings.ldap_url, get_info=ldap3.NONE)
    try:
        conn = ldap3.Connection(
            server,
            user=settings.ldap_bind_dn,
            password=settings.ldap_bind_password,
            auto_bind=True,
            read_only=True,
        )
    except LDAPException as e:
        raise PcsError(
            code="LDAP_BIND_FAILED", message=str(e), status=503
        ) from e

    try:
        conn.search(
            search_base=settings.ldap_base_dn,
            search_filter=settings.ldap_user_filter,
            attributes=attributes,
        )
        users: list[DirectoryUser] = []
        for entry in conn.entries:
            # uid 在 OpenLDAP；sAMAccountName 在 AD。都没有就跳过该条目 ——
            # 没有 username 的行无法与 users 表对应，写进去只会造垃圾行。
            username = next(
                (u for u in (_first(entry, a) for a in _USERNAME_ATTRS) if u), None
            )
            if not username:
                continue
            groups = getattr(entry, "memberOf", None)
            users.append(
                DirectoryUser(
                    username=username,
                    display_name=_first(entry, "displayName"),
                    email=_first(entry, "mail"),
                    department=_first(entry, "department"),
                    groups=tuple(str(g) for g in groups) if groups else (),
                )
            )
    except LDAPException as e:
        raise PcsError(
            code="LDAP_SEARCH_FAILED", message=str(e), status=503
        ) from e
    finally:
        conn.unbind()
    return users


def resolve_role(groups: tuple[str, ...]) -> str:
    """按 Settings.ldap_group_role_map 反查角色。

    F-P3-001 Sprint 3 (改动 2): production fail-closed.
    - production: 找不到映射 → raise LdapAuthError (拒绝无角色登录)
    - dev/test: 找不到映射 → DESIGNER fallback (mock 友好)
    """
    mapping = get_settings().group_role_map()
    group_cns = {_extract_cn(g) for g in groups}
    for group_cn, role in mapping.items():
        if group_cn in group_cns:
            return role
    if get_settings().is_production:
        raise LdapAuthError(
            "no role mapping for LDAP groups in production",
        )
    return "DESIGNER"


def _extract_cn(group_dn: str) -> str:
    """从 'cn=DESIGNER_GROUP,ou=Groups,dc=test,dc=local' 提取 'DESIGNER_GROUP'。"""
    for part in group_dn.split(","):
        part = part.strip()
        if part.lower().startswith("cn="):
            return part[3:]
    return group_dn
