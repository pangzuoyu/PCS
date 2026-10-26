"""**全仓只有一个 `PcsError`**（TODO-089）。

## 这组测试钉住的失败模式

| # | 失败模式 | 期望 |
|---|---|---|
| RF-1 | `except service.PcsError` **捕不到** core 变体抛出的错 ⇒ 跨模块业务错**静默变成 500**（bug-2079） | 捕得到 |
| RF-2 | `except core.PcsError` 捕不到 service 变体抛出的错 | 捕得到 |
| RF-3 | 合并后 **service 风格**的 `PcsError("消息", code=…)` 变了语义（code/status 缺省） | 缺省仍是 `PCS_ERROR` / `422` |
| RF-4 | 合并后 **core 风格**的 `PcsError("CODE", "消息")` 变了语义 | 缺省仍是 `400` |
| RF-5 | 子类自己声明的 `status` 被合并**覆盖成 422**（`WorkspaceNotFoundError` → 404） | 保持子类自己的值 |
| RF-6 | 子类自己声明的 `code` 被覆盖（`PreconditionViolation` → `PRECONDITION_VIOLATION`） | 保持子类自己的值 |
| RF-7 | 合并后**只剩一个 handler** ⇒ core / service 两种抛出方的响应信封一致 | 信封字段一致 |

⚠️ RF-1/RF-2 是**同一个类**的两种说法 —— 它们断言的是
`app.services.exceptions.PcsError is app.core.errors.PcsError`。
"""

from __future__ import annotations

import pytest

from app.core.errors import PcsError as CorePcsError
from app.services.exceptions import (
    PcsError as ServicePcsError,
    PreconditionViolation,
    WorkspaceNotFoundError,
    WorkspaceTypeNotAllowedError,
)


def test_rf1_service_except_catches_core_raised() -> None:
    """RF-1：`except service.PcsError` 捕得到 core 变体抛出的错。"""
    with pytest.raises(ServicePcsError):
        raise CorePcsError(code="X", message="boom", status=409)


def test_rf2_core_except_catches_service_raised() -> None:
    """RF-2：`except core.PcsError` 捕得到 service 变体抛出的错。"""
    with pytest.raises(CorePcsError):
        raise ServicePcsError("boom", code="X")


def test_rf1b_the_two_names_are_the_same_class() -> None:
    """RF-1/RF-2 的**根因**：两个 import 名字必须指向**同一个类**。"""
    assert ServicePcsError is CorePcsError


def test_rf3_service_style_defaults() -> None:
    """RF-3：service 风格（message 在前 + kwargs）的缺省不变。"""
    exc = ServicePcsError("出错了")
    assert exc.code == "PCS_ERROR"
    assert exc.status == 422
    assert exc.message == "出错了"
    assert exc.detail is None
    assert exc.details == {}


def test_rf3b_service_style_overrides() -> None:
    """RF-3：service 风格的 kwargs 覆盖仍然生效。"""
    exc = ServicePcsError("出错了", code="NOT_FOUND", status=404, details={"a": 1})
    assert exc.code == "NOT_FOUND"
    assert exc.status == 404
    assert exc.detail == {"a": 1}
    assert exc.details == {"a": 1}


def test_rf4_core_style_defaults() -> None:
    """RF-4：core 风格（code 在前）的缺省仍是 400。"""
    exc = CorePcsError("SOME_CODE", "出错了")
    assert exc.code == "SOME_CODE"
    assert exc.message == "出错了"
    assert exc.status == 400
    assert exc.detail is None


def test_rf4b_core_style_positional_status_and_detail() -> None:
    """RF-4：core 风格的 4 个位置参数照旧可用。"""
    exc = CorePcsError("SOME_CODE", "出错了", 409, {"k": "v"})
    assert exc.status == 409
    assert exc.detail == {"k": "v"}


def test_rf4c_core_style_keywords() -> None:
    """RF-4：core 风格的纯 kwargs 形式照旧可用。"""
    exc = CorePcsError(code="SOME_CODE", message="出错了", status=413)
    assert exc.code == "SOME_CODE"
    assert exc.status == 413


def test_rf5_subclass_status_survives_merge() -> None:
    """RF-5：子类自己声明的 status 不被合并覆盖。"""
    assert WorkspaceNotFoundError("没有这个工作区").status == 404
    assert WorkspaceTypeNotAllowedError("不是 FORMAL").status == 403


def test_rf6_subclass_code_survives_merge() -> None:
    """RF-6：子类自己声明的 code 不被合并覆盖。"""
    assert PreconditionViolation("违反前置条件").code == "PRECONDITION_VIOLATION"
    assert PreconditionViolation("违反前置条件").status == 422


def test_rf6b_subclass_code_can_be_overridden() -> None:
    """RF-6：子类也可以显式覆盖 code。"""
    exc = WorkspaceNotFoundError("没有这个工作区", code="OTHER")
    assert exc.code == "OTHER"
    assert exc.status == 404


def test_rf7_str_is_the_message() -> None:
    """RF-7：`str(exc)` 返回 message（不是位置参数的元组 repr）。"""
    assert str(ServicePcsError("出错了")) == "出错了"


def test_rf7b_details_alias_of_detail() -> None:
    """RF-7：`details` 与 `detail` 是同一份数据的两个名字。"""
    exc = CorePcsError(code="X", message="m", status=400, detail={"a": 1})
    assert exc.detail == {"a": 1}
    assert exc.details == {"a": 1}
