"""ACL 工具测试（P0-MED-001/007 V1.5，2026-09-18）。

V1.4 装饰器（require_role / require_workspace_member）已下线（functools.wraps
替换函数签名，与 FastAPI Depends 冲突；真实鉴权走内联 require_roles）。
本文件仅覆盖现役 _user_attr 辅助 + PermissionDeniedError 导入可达性。

P0-MED-007 fix（2026-09-18）：_user_attr 对空集合统一返回 None，
避免"空集合"与"无属性"语义分歧导致的 false-deny。
"""

from __future__ import annotations

from types import SimpleNamespace

from app.core.acl import PermissionDeniedError, _user_attr


class _User:
    """最小 user duck-type：仅暴露 roles/workspace_ids。"""


def test_user_attr_none_user_returns_none():
    assert _user_attr(None, "roles") is None


def test_user_attr_missing_attribute_returns_none():
    user = _User()
    assert _user_attr(user, "roles") is None


def test_user_attr_empty_list_returns_none():
    """P0-MED-007 fix：空集合 → None（与无属性统一为空权限语义）。"""
    user = SimpleNamespace(roles=[])
    assert _user_attr(user, "roles") is None


def test_user_attr_non_empty_list_returns_reference():
    user = SimpleNamespace(roles=["DESIGNER"])
    result = _user_attr(user, "roles")
    assert result == ["DESIGNER"]
    assert result is user.roles  # 引用透传


def test_user_attr_workspace_ids_empty_set_returns_none():
    user = SimpleNamespace(workspace_ids=set())
    assert _user_attr(user, "workspace_ids") is None


def test_permission_denied_error_importable():
    """PermissionDeniedError 仍可导入（兼容历史 catch 点）。"""
    assert issubclass(PermissionDeniedError, Exception)