"""公式参数与单测 Pydantic schema（D16）。

锁定 FormulaDefinition.parameters_json 与 unit_tests_json 的结构：
formula.parameters_json -> FormulaParametersSchema -> list[FormulaParameter]
formula.unit_tests_json -> UnitTestsSchema -> list[UnitTestCase]
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FormulaParameter(BaseModel):
    name: str = Field(
        ..., min_length=1, max_length=100, description="参数名（公式内引用）"
    )
    unit: str | None = Field(None, max_length=20, description="单位（如 MPa、°C、kg/h）")
    description: str | None = Field(None, description="参数说明")
    min: float | None = Field(None, description="合法下限")
    max: float | None = Field(None, description="合法上限")
    default: float | None = Field(None, description="默认值")


class FormulaParametersSchema(BaseModel):
    parameters: list[FormulaParameter] = Field(..., description="公式参数列表")


class UnitTestCase(BaseModel):
    params: dict[str, float] = Field(..., description="测试输入参数 {name: value}")
    expected: float = Field(..., description="期望输出值")
    tolerance: float = Field(0.01, ge=0, description="误差容忍度（绝对值或相对值）")


class UnitTestsSchema(BaseModel):
    unit_tests: list[UnitTestCase] = Field(..., description="单元测试用例列表")
