"""FormulaEngine.parse() 单元测试（Task 2.3）。

验证：
- 简单算术表达式正确求值
- math.* 函数调用正确解析
- 拒绝包含禁止节点/名称的表达式（安全边界）
- compute_version_hash 符合 D33 规范（SHA-256[:16]、payload 拼接、参数排序）
"""

from __future__ import annotations

import pytest

from app.services.formula_engine import FormulaEngine, FormulaSecurityError


def test_parse_simple_arithmetic():
    f = FormulaEngine.parse("a + b", {"a": 1.0, "b": 2.0})
    assert f({"a": 1.0, "b": 2.0}) == 3.0


def test_parse_math_function():
    f = FormulaEngine.parse("math.sqrt(x)", {"x": 4.0})
    assert f({"x": 4.0}) == 2.0


# === 防御性补充（brief 之外，确保白名单真的阻断 RCE）===


def test_parse_rejects_import_statement():
    """AST 白名单必须阻断 import 节点。"""
    with pytest.raises(FormulaSecurityError):
        FormulaEngine.parse("__import__('os').system('id')", {"x": 1.0})


def test_parse_rejects_dunder_access():
    """FORBIDDEN_NAMES 含 '__'，任何含 __ 子串的名称被拒。"""
    with pytest.raises(FormulaSecurityError):
        FormulaEngine.parse("a.__class__", {"a": 1.0})


def test_compute_version_hash_is_16_hex():
    """D33: SHA-256 截前 16 hex chars（64-bit 碰撞空间）。"""
    h = FormulaEngine.compute_version_hash("a + b", {"a": 1.0})
    assert len(h) == 16
    int(h, 16)  # 必须能解析为十六进制整数


def test_compute_version_hash_param_order_invariant():
    """参数 dict 顺序不影响 hash（JSON sort_keys=True）。"""
    h1 = FormulaEngine.compute_version_hash("a + b", {"a": 1.0, "b": 2.0})
    h2 = FormulaEngine.compute_version_hash("a + b", {"b": 2.0, "a": 1.0})
    assert h1 == h2


def test_compute_version_hash_different_params_differ():
    """参数内容不同 → hash 不同。"""
    h1 = FormulaEngine.compute_version_hash("a + b", {"a": 1.0})
    h2 = FormulaEngine.compute_version_hash("a + b", {"a": 2.0})
    assert h1 != h2


def test_compute_version_hash_different_expression_differ():
    """表达式不同 → hash 不同。"""
    h1 = FormulaEngine.compute_version_hash("a + b", {"a": 1.0})
    h2 = FormulaEngine.compute_version_hash("a * b", {"a": 1.0})
    assert h1 != h2


# === Task 2.4: run_unit_tests 100% pass 硬门槛 ===


def test_run_unit_tests_all_pass():
    """3 个用例全部通过 → (3, 3)。"""
    passed, total = FormulaEngine.run_unit_tests(
        "a + b",
        {"a": 0.0, "b": 0.0},
        [
            {"params": {"a": 1.0, "b": 2.0}, "expected": 3.0},
            {"params": {"a": 0.0, "b": 0.0}, "expected": 0.0},
            {"params": {"a": -1.0, "b": 1.0}, "expected": 0.0},
        ],
    )
    assert (passed, total) == (3, 3)


def test_run_unit_tests_some_fail():
    """1 个通过 + 1 个期望值错误 → (1, 2)。"""
    passed, total = FormulaEngine.run_unit_tests(
        "a + b",
        {"a": 0.0, "b": 0.0},
        [
            {"params": {"a": 1.0, "b": 2.0}, "expected": 3.0},
            {"params": {"a": 1.0, "b": 2.0}, "expected": 999.0},  # 错误期望
        ],
    )
    assert (passed, total) == (1, 2)


def test_run_unit_tests_exception_counted_as_fail():
    """用例求值抛异常 → 不计入 passed。"""
    # 公式只用 a + b，但用例缺 a 键（evaluator 合并 namespace 后仍缺 a）
    passed, total = FormulaEngine.run_unit_tests(
        "a + b",
        {"a": 0.0, "b": 0.0},
        [
            {"params": {"a": 1.0, "b": 2.0}, "expected": 3.0},  # 通过
            {"params": {"b": 2.0}, "expected": 0.0},  # 缺 a → KeyError → 不计 passed
        ],
    )
    assert (passed, total) == (1, 2)
