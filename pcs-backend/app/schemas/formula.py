"""公式参数 Pydantic schema（D16）。

锁定 FormulaDefinition.parameters_json 的结构：
formula.parameters_json -> FormulaParametersSchema -> list[FormulaParameter]
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class FormulaParameter(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    unit: str | None = None
    description: str | None = None
    min: float | None = None
    max: float | None = None
    default: float | None = None


class FormulaParametersSchema(BaseModel):
    parameters: list[FormulaParameter]
