"""tests/core fixtures — Task 1.4 ACL 装饰器。

make_user 是 pytest fixture：测试通过参数注入后可直接以函数形式调用，
与 brief 中的用法保持一致：user = make_user(roles=["DESIGNER"])。
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass, field

import pytest


@dataclass
class _StubUser:
    """ACL 测试桩 — duck-type 拥有 .roles 与 .workspace_ids。

    User ORM 模型（app.models.project.User）只有 .roles；workspace_ids 由
    ACL 装饰器契约定义（用户可访问的项目 ID 列表）。此处显式提供两者。
    """

    user_id: uuid.UUID = field(default_factory=uuid.uuid4)
    username: str = "stub"
    roles: list[str] = field(default_factory=list)
    workspace_ids: list[uuid.UUID] = field(default_factory=list)


@pytest.fixture
def make_user():
    """工厂：roles / workspace_ids 可选，缺省为空。"""

    def _factory(
        *,
        roles: Iterable[str] = (),
        workspace_ids: Iterable[uuid.UUID] = (),
        user_id: uuid.UUID | None = None,
    ) -> _StubUser:
        return _StubUser(
            user_id=user_id or uuid.uuid4(),
            roles=list(roles),
            workspace_ids=list(workspace_ids),
        )

    return _factory