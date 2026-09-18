"""LDAP DN 转义单元测试。H-P0-4 防回归。"""

from __future__ import annotations

import pytest

from app.services.ldap_client import _sanitize_dn_component


@pytest.mark.parametrize(
    "raw, expected",
    [
        # 普通字符不转义
        ("alice", "alice"),
        # RFC 4514 §2.4 必转义字符（每个单字符输入 → 2 字符输出）
        ("a\\b", "a\\\\b"),          # \ → \\
        ('a"b', 'a\\"b'),           # " → \"
        ("a#b", "a\\#b"),            # # → \#
        ("a+b", "a\\+b"),            # + → \+
        ("a,b", "a\\,b"),            # , → \, （DN injection 防御）
        ("a;b", "a\\;b"),            # ; → \;
        ("a<b", "a\\<b"),            # < → \<
        ("a=b", "a\\=b"),            # = → \= （DN injection 防御）
        ("a>b", "a\\>b"),            # > → \>
        ("a\x00b", "a\\00b"),        # NUL → \00（多字符序列）
        # 多重特殊字符组合
        ("a,b=c", "a\\,b\\=c"),       # , + = 同时出现
        ('x"y#z', 'x\\"y\\#z'),      # " + #
    ],
)
def test_sanitize_dn_component_escapes_special_chars(raw, expected):
    assert _sanitize_dn_component(raw) == expected


def test_sanitize_dn_component_backslash_first():
    """反斜杠必须最先转义：单 `\\` → `\\\\`（2 字符变 4 字符）。"""
    # 输入: 1 个反斜杠（Python `"\\"` = `\`）
    # 输出: 2 个反斜杠（Python `"\\\\"` = `\\`）
    assert _sanitize_dn_component("\\") == "\\\\"


def test_sanitize_dn_component_empty():
    assert _sanitize_dn_component("") == ""


def test_sanitize_dn_component_dn_injection_blocked():
    """集成：username 含 `,ou=admin` 不应破坏 DN 结构。

    模板 `cn={username},...` + 恶意输入 `alice,ou=admin`：
    未转义 → `cn=alice,ou=admin,...`（攻击者把自己的 ou 注入 DN）
    转义后 → `cn=alice\\,ou\\=admin,...`（`=` 也被转义，整个仍是 cn 的 RDN 值一部分）
    """
    from app.core.config import get_settings

    settings = get_settings()
    template = settings.ldap_user_dn_template
    malicious = "alice,ou=admin"
    escaped = _sanitize_dn_component(malicious)
    result = template.format(username=escaped)
    # 转义后 `,` 和 `=` 都是字面字符（带 \），DN 解析时属于 cn 的 RDN 值一部分
    assert "alice\\,ou\\=admin" in result
    # 未转义版本会出现 `ou=admin` 作为独立 RDN（注入成功标志）
    assert "ou=admin," not in result
