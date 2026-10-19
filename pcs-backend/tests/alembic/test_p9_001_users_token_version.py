"""P9A 迁移基座的 schema 断言 —— 防「ORM 写了但没迁移」与「迁移写了但 ORM 没跟上」。

⚠️ 迁移与 ORM 漂移时，**单测照绿、真库会炸**（CLAUDE.md 漂移盲区）。
本文件断言的是**元数据与迁移产物一致**，不是运行时行为。
"""
from app.db.base import Base
import app.models  # noqa: F401  触发全部 model 注册


def _cols(table: str) -> set[str]:
    return set(Base.metadata.tables[table].columns.keys())


def _checks(table: str) -> list[str]:
    return [
        str(c.sqltext)
        for c in Base.metadata.tables[table].constraints
        if c.__class__.__name__ == "CheckConstraint"
    ]


def test_users_has_token_version():
    assert "token_version" in _cols("users")


def test_token_version_is_checked_ge_1():
    """0 是 mock 令牌的哨兵值 —— 真实用户永不为 0（ADR-0046 §③b）。"""
    checks = _checks("users")
    assert any(
        "token_version" in c and ">=1" in c.replace(" ", "") for c in checks
    ), f"users 缺 CHECK (token_version >= 1)，现有约束：{checks}"


def test_roles_comment_uses_current_role_vocabulary():
    """ADR-0046 带归属的待办：`roles` 注释仍写 SYSADMIN（2026-10-04 已收敛为
    SYSTEM_ADMIN）。惰性建行正往这一列写真值，照注释写会产出 ACL 不认的字符串
    —— `app/core/acl.py:13` 明写 `User.roles` 是 ACL 权威输入。"""
    comment = Base.metadata.tables["users"].columns["roles"].comment or ""
    assert "SYSADMIN" not in comment.replace("SYSTEM_ADMIN", ""), \
        f"roles 注释仍含旧词表 SYSADMIN：{comment}"
    assert "SYSTEM_ADMIN" in comment, f"roles 注释未写现行词表 SYSTEM_ADMIN：{comment}"
