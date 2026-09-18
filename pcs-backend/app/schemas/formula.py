"""公式参数与单测 Pydantic schema（D16）。

锁定 FormulaDefinition.parameters_json 与 unit_tests_json 的结构：
formula.parameters_json -> FormulaParametersSchema -> list[FormulaParameter]
formula.unit_tests_json -> UnitTestsSchema -> list[UnitTestCase]
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FormulaParameter(BaseModel):
    """公式单个参数定义（formula.parameters_json 内嵌项）。

    业务：name 用于公式表达式内引用，unit/description 提示 UI 输入，
    min/max/default 约束合法性 + 前端预填；与 FormulaDefinition.parameters_json 锁版。
    """

    name: str = Field(
        ..., min_length=1, max_length=100, description="参数名（公式内引用）"
    )
    unit: str | None = Field(None, max_length=20, description="单位（如 MPa、°C、kg/h）")
    description: str | None = Field(None, description="参数说明")
    min: float | None = Field(None, description="合法下限")
    max: float | None = Field(None, description="合法上限")
    default: float | None = Field(None, description="默认值")


class FormulaParametersSchema(BaseModel):
    """公式参数列表容器（formula.parameters_json 整体 schema 校验入口）。

    业务：保证 parameters_json 是 list[FormulaParameter]；formula_service 解析
    时强制走此 schema 校验后再执行 eval/compile。
    """

    parameters: list[FormulaParameter] = Field(..., description="公式参数列表")


class UnitTestCase(BaseModel):
    """公式单元测试用例（formula.unit_tests_json 内嵌项）。

    业务：params 与公式参数 name 对应映射，expected 为预期输出，
    tolerance 默认 0.01（绝对值）；执行时按 |actual-expected| ≤ tolerance 判定通过。
    """

    params: dict[str, float] = Field(..., description="测试输入参数 {name: value}")
    expected: float = Field(..., description="期望输出值")
    tolerance: float = Field(0.01, ge=0, description="误差容忍度（绝对值或相对值）")


class UnitTestsSchema(BaseModel):
    """公式单测用例列表容器（formula.unit_tests_json 整体 schema 校验入口）。

    业务：保证 unit_tests_json 是 list[UnitTestCase]；formula_service 解析
    时按此 schema 校验，再依次执行每个用例并汇总 pass/fail。
    """

    unit_tests: list[UnitTestCase] = Field(..., description="单元测试用例列表")
