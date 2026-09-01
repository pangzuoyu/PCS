"""ACL 装饰器（基于 user 对象的 duck-typing）。

提供：
- PermissionDeniedError — 鉴权失败异常
- require_role(*allowed_roles) — 检查 user.roles 是否命中任一允许角色
- require_workspace_member(project_id) — 检查 user.workspace_ids 是否包含

契约：
- 装饰器为同步包装；使用 functools.wraps 保留 __name__/__doc__。
- `user` 通过关键字参数注入（wrapper(*args, user=..., **kwargs)）；调用方负责
  把 user 放进来。FastAPI 集成：把 wrapper 注册为端点，路由层调用前注入 user。
- wrapper 仅消费 `user` 做 ACL 校验，不向底层 func 透传 user —— 让被装饰的
  函数可保持自身签名（避免与 fastapi Depends 重复注入冲突）。
- user 对象需具备 `.roles: Iterable[str]` 与 `.workspace_ids: Iterable[uuid.UUID]`
  属性；ORM User（app.models.project.User）只有 .roles，.workspace_ids 由调用方
  按业务上下文组装（ACL 模块不耦合 ORM）。
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable
from functools import wraps
from typing import Any


class PermissionDeniedError(Exception):
    """ACL 鉴权失败（缺角色 / 缺项目访问权 / user 缺失）。"""


def _user_attr(user: Any, name: str) -> Iterable[Any] | None:
    """安全取 user 属性；user 为 None 或缺属性时返回 None。"""
    if user is None:
        return None
    value = getattr(user, name, None)
    return value if value else None


def require_role(*allowed_roles: str) -> Callable[..., Any]:
    """要求 user.roles 至少匹配一个 allowed_roles（OR 语义）。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, user: Any = None, **kwargs: Any) -> Any:
            roles = _user_attr(user, "roles")
            if roles is None or not any(r in allowed_roles for r in roles):
                raise PermissionDeniedError(f"需要角色 {list(allowed_roles)}")
            return func(*args, **kwargs)

        return wrapper

    return decorator


def require_workspace_member(project_id: uuid.UUID) -> Callable[..., Any]:
    """要求 user.workspace_ids 包含给定 project_id。"""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, user: Any = None, **kwargs: Any) -> Any:
            workspace_ids = _user_attr(user, "workspace_ids")
            if workspace_ids is None or project_id not in workspace_ids:
                raise PermissionDeniedError(f"无项目 {project_id} 访问权限")
            return func(*args, **kwargs)

        return wrapper

    return decorator