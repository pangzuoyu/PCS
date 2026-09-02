"""FormulaEngine.evaluate_preconditions 单元测试（Task 1.8.1）。

覆盖：
- input.T / params.K 必须存在
- pre 阶段禁止 result.*
- context.* 一律 REJECT（V1.6 §2.3）
- params.* 溯源校验
- 表达式求值（pre/post）
- 嵌套路径解析
"""

from __future__ import annotations

import pytest

from app.services.formula_engine import FormulaEngine
from app.services.exceptions import PreconditionViolation


def test_preconditions_input_required():
    """input.T 必须存在于 context，否则 REJECT"""
    preconds = [{"id": "PRE-001", "target": "input.T", "expression": "T > 0"}]
    with pytest.raises(PreconditionViolation):
        FormulaEngine.evaluate_preconditions(preconds, {"input": {}})


def test_preconditions_params_required():
    """params.K 必须存在于 context，否则 REJECT"""
    preconds = [{"id": "PRE-002", "target": "params.K", "expression": "K > 0"}]
    with pytest.raises(PreconditionViolation):
        FormulaEngine.evaluate_preconditions(preconds, {"params": {}})


def test_preconditions_result_forbidden_pre():
    """pre 阶段 result.* 必须不存在，否则 REJECT"""
    preconds = [{"id": "PRE-003", "target": "result.x", "expression": "x > 0"}]
    with pytest.raises(PreconditionViolation):
        FormulaEngine.evaluate_preconditions(preconds, {}, phase="pre")


def test_preconditions_context_forbidden():
    """context.* 引用一律 REJECT（V1.6 §2.3 边界）"""
    preconds = [{"id": "PRE-004", "target": "context.db", "expression": "db is not None"}]
    with pytest.raises(PreconditionViolation):
        FormulaEngine.evaluate_preconditions(preconds, {"context": {"db": "x"}})


def test_preconditions_constant_trace_fail():
    """params.* 必须能溯源到 CoefficientTables，否则 REJECT"""
    preconds = [{"id": "PRE-005", "target": "params.K", "expression": "K > 0"}]
    with pytest.raises(PreconditionViolation):
        FormulaEngine.evaluate_preconditions(
            preconds, {"params": {"K": 1.0}}, trace_table={"K": None}  # 溯源失败
        )


def test_preconditions_pre_violation():
    """pre 阶段违规抛 PreconditionViolation"""
    preconds = [{"id": "PRE-006", "target": "input.T", "expression": "T > 100"}]
    with pytest.raises(PreconditionViolation):
        FormulaEngine.evaluate_preconditions(preconds, {"input": {"T": 50}}, phase="pre")


def test_preconditions_post_check():
    """post 阶段 result.* 可访问且应满足 expression"""
    preconds = [{"id": "PRE-007", "target": "result.q", "expression": "q > 0"}]
    FormulaEngine.evaluate_preconditions(
        preconds, {"result": {"q": 1.5}}, phase="post"
    )  # 不抛错


def test_preconditions_nested_reference():
    """嵌套引用 input.subfield.field 应正确解析"""
    preconds = [{"id": "PRE-008", "target": "input.stream.temperature", "expression": "temperature > 0"}]
    FormulaEngine.evaluate_preconditions(
        preconds, {"input": {"stream": {"temperature": 100}}}, phase="pre"
    )  # 不抛错
