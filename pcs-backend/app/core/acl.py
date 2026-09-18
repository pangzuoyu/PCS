"""ACL 工具（基于 user 对象的 duck-typing）。

提供：
- PermissionDeniedError — 鉴权失败异常
- _user_attr(user, name) — 安全取属性，user=None/缺属性/空集合 → None

契约（V1.5 P0-MED-001，2026-09-18）：
- 真实鉴权走内联 `require_roles(user, *roles)` 调用（app.api.v1.config 末尾），
  不再用装饰器（functools.wraps 替换函数签名，与 FastAPI Depends 冲突）。
- 本模块仅保留 PermissionDeniedError + _user_attr 辅助。

user 对象需具备 `.roles: Iterable[str]` 与 `.workspace_ids: Iterable[uuid.UUID]`
属性；ORM User（app.models.project.User）只有 .roles，.workspace_ids 由调用方
按业务上下文组装（ACL 模块不耦合 ORM）。
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any


class PermissionDeniedError(Exception):
    """ACL 鉴权失败（缺角色 / 缺项目访问权 / user 缺失）。"""


def _user_attr(user: Any, name: str) -> Iterable[Any] | None:
    """安全取 user 属性。

    P0-MED-007 fix（2026-09-18）：
    - user=None 或缺属性 → None
    - 空集合 → None（避免误判"无属性"，与"空集合"统一为空权限语义）
    - 非空集合 → 真实引用

    调用方对 None 与空集合语义等同（"无授权"），下游统一处理。
    """
    if user is None:
        return None
    value = getattr(user, name, None)
    if not value:
        return None
    return value