"""FormulaEngine fuzz 测试（Task 2.3 Step 5）。

Goal: 任意字符串输入都不能触发 RCE/任意求值。
成功标准：所有输入要么成功 parse（合法算术），要么抛 FormulaSecurityError/SyntaxError/ValueError，
绝不允许突破 AST 白名单执行任意代码。
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from app.services.formula_engine import FormulaEngine, FormulaSecurityError


@given(st.text(min_size=1, max_size=100))
def test_no_rce_on_garbage(s: str):
    try:
        FormulaEngine.parse(s, {"x": 1.0})
    except (FormulaSecurityError, SyntaxError, ValueError):
        pass  # expected
