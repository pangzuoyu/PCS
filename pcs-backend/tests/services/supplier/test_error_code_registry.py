"""供应商域错误码必须出现在 meta 错误码注册表里（审查 #4）.

项目规则把 `GET /api/v1/meta/error-codes` 定为错误码权威源，客户端按它建
`code -> ui_behavior` 映射。注册表内容由 `meta_service._scan_error_codes()`
用 AST 扫 `app/` 全仓的 `raise PcsError(...)` 得出。

**该扫描器只认两种形态**：
1. `raise PcsError(code="X", ...)` —— 关键字且 code 是字面量
2. 其余一律漏掉

所以 `raise _error("X", ...)` 这种「工厂返回 PcsError 再 raise」的写法，会让
错误码**永远进不了注册表**，而它在 422/409 响应体里确实出现了 —— 客户端按
权威源建映射时这两个码直接掉进兜底分支。本文件锁住这一约束。
"""

from __future__ import annotations

import pytest

from app.services.meta_service import _scan_error_codes

# 供应商域本次新增/涉及的错误码
_SUPPLIER_CODES = (
    "ACTUAL_DATA_VALIDATION",
    "ACTUAL_DATA_LOCKED",
    "ACTUAL_DATA_ALREADY_CONFIRMED",
    "ACTUAL_DATA_STATE_CONFLICT",
    "DEVIATION_BLOCKS_CONFIRMATION",
)


def test_supplier_error_codes_are_registered() -> None:
    """全部供应商域错误码都应可从 meta 注册表查到。"""
    codes = {c.get("code") for c in _scan_error_codes()}
    missing = [c for c in _SUPPLIER_CODES if c not in codes]
    assert not missing, (
        f"错误码未进注册表: {missing} —— 客户端按 meta 权威源建 code->ui_behavior "
        "映射时会掉进兜底分支。检查是否用了 `raise _error(...)` 之类的工厂返回式"
        "PcsError（AST 扫描器只认 `raise PcsError(code=...)` 字面量形态）"
    )


@pytest.mark.parametrize("code", _SUPPLIER_CODES)
def test_supplier_error_code_has_message(code: str) -> None:
    """注册表条目须带非空 message —— 客户端据此渲染提示文案。"""
    entry = next(c for c in _scan_error_codes() if c.get("code") == code)
    assert entry.get("message")
