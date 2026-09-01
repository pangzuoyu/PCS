"""Pydantic schema 契约测试：formula.parameters_json（D16）。

锁定公式参数的 JSON 结构，便于后续 FormulaDefinition.parameters_json 列
写入/读取时进行结构化校验（避免游离 dict 字段）。
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.formula import (
    FormulaParameter,
    FormulaParametersSchema,
    UnitTestCase,
    UnitTestsSchema,
)


def test_parameters_json_schema_valid():
    schema = FormulaParametersSchema.model_validate({
        "parameters": [
            {"name": "f", "unit": "dimensionless", "description": "摩擦因子",
             "min": 0.0, "max": 1.0, "default": None}
        ]
    })
    assert schema.parameters[0].name == "f"
    assert isinstance(schema.parameters[0], FormulaParameter)


def test_parameters_json_schema_rejects_missing_name():
    with pytest.raises(ValidationError):
        FormulaParametersSchema.model_validate({
            "parameters": [{"unit": "x"}]
        })


def test_unit_tests_json_schema_valid():
    schema = UnitTestsSchema.model_validate({
        "unit_tests": [
            {"params": {"a": 1.0, "b": 2.0}, "expected": 3.0, "tolerance": 0.001}
        ]
    })
    assert schema.unit_tests[0].expected == 3.0
    assert schema.unit_tests[0].tolerance == 0.001
    assert schema.unit_tests[0].params == {"a": 1.0, "b": 2.0}
    assert isinstance(schema.unit_tests[0], UnitTestCase)


def test_unit_tests_json_schema_rejects_missing_expected():
    with pytest.raises(ValidationError):
        UnitTestsSchema.model_validate({
            "unit_tests": [{"params": {"a": 1.0}}]
        })
