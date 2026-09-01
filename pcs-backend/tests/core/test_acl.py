"""ACL 装饰器测试（Task 1.4）。

覆盖：
- require_role 正/负 / user 缺失 / 多角色 OR 语义
- require_workspace_member 正/负 / user 缺失
- 装饰器保留原函数元数据（functools.wraps）

RED 阶段：app.core.acl 不存在时，模块顶部 import 即失败 → 全部测试报
ImportError。等实现（GREEN）后即可通过。
"""

from __future__ import annotations

import uuid

import pytest

from app.core.acl import (
    PermissionDeniedError,
    require_role,
    require_workspace_member,
)


def test_require_role_designer_can_create_draft(make_user):
    user = make_user(roles=["DESIGNER"])
    decorator = require_role("DESIGNER")
    assert decorator(lambda: "ok")(user=user) == "ok"


def test_require_role_process_controller_blocks_designer(make_user):
    user = make_user(roles=["DESIGNER"])
    decorator = require_role("PROCESS_CONTROLLER")
    with pytest.raises(PermissionDeniedError):
        decorator(lambda: "ok")(user=user)


def test_require_role_missing_user_raises():
    decorator = require_role("DESIGNER")
    with pytest.raises(PermissionDeniedError):
        decorator(lambda: "ok")(user=None)


def test_require_role_any_of_multiple_allowed(make_user):
    """任一角色匹配即放行（OR 语义）。"""
    user = make_user(roles=["REVIEWER"])
    decorator = require_role("DESIGNER", "REVIEWER", "APPROVER")
    assert decorator(lambda: "ok")(user=user) == "ok"


def test_require_workspace_member_allowed(make_user):
    pid = uuid.uuid4()
    user = make_user(roles=["DESIGNER"], workspace_ids=[pid])
    decorator = require_workspace_member(pid)
    assert decorator(lambda: "ok")(user=user) == "ok"


def test_require_workspace_member_blocked(make_user):
    pid = uuid.uuid4()
    other = uuid.uuid4()
    user = make_user(roles=["DESIGNER"], workspace_ids=[other])
    decorator = require_workspace_member(pid)
    with pytest.raises(PermissionDeniedError):
        decorator(lambda: "ok")(user=user)


def test_require_workspace_member_missing_user_raises():
    pid = uuid.uuid4()
    decorator = require_workspace_member(pid)
    with pytest.raises(PermissionDeniedError):
        decorator(lambda: "ok")(user=None)


def test_decorator_preserves_function_metadata():
    """functools.wraps 必须保留 __name__ 等元数据。"""
    decorator = require_role("DESIGNER")

    @decorator
    def my_endpoint():
        """端点说明。"""
        return 42

    assert my_endpoint.__name__ == "my_endpoint"
    assert "端点说明" in (my_endpoint.__doc__ or "")