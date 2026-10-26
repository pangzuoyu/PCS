"""签署矩阵管理面的 schema（TODO-070 · P9A-DLV-011 T3）。

## 为什么要显式声明（P9A-DLV-010 零裸字段）

前端 type 由 openapi-typescript 从 OpenAPI 生成 ⇒ 响应模型里出现裸
`object` / `array` ⇒ 前端只能拿 `object` / `any[]` ⇒ 「前端 type 全部
from './api'」的纪律在第一天就废了。

⇒ 这里每个响应模型都**逐字段声明**，且测试钉住字段集合。

## `steps` 的形状

`SignatureMatrix.steps_json` 的形状 =
`[{"step_order","sign_role","required","can_self_check","can_skip"}]`
（模型注释逐字）。**写入时严格校验**（`SignatureMatrixService.validate_steps`）
⇒ 坏配置进不来 ⇒ 读路径不必再替脏数据兜底。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

#: 矩阵状态 4 值（模型注释逐字：DRAFT/PENDING/ACTIVE/OBSOLETE）。
MatrixStatus = Literal["DRAFT", "PENDING", "ACTIVE", "OBSOLETE"]

#: 矩阵模块标识。`*` = 全部模块（模型注释逐字）。
MatrixModule = Literal[
    "*",
    "RECORD",
    "STREAM",
    "EQUIP",
    "CHANGE_NOTICE",
]


class MatrixStepInput(BaseModel):
    """矩阵的一步（写入形状）。"""

    step_order: int = Field(ge=1, description="步骤序号，1 起")
    sign_role: str = Field(
        min_length=1,
        max_length=30,
        description="该步要求的**全局角色**（与 token 的 role claim 比较）",
    )
    required: bool = Field(default=True, description="是否必签")
    can_self_check: bool = Field(
        default=True, description="提交人可否签自己这一步（false ⇒ 403）"
    )
    can_skip: bool = Field(default=False, description="可否跳过（false ⇒ 409）")


class MatrixStepResponse(MatrixStepInput):
    """矩阵的一步（读出形状；字段与写入形状同构）。"""


class SignatureMatrixRequest(BaseModel):
    """建/改矩阵模板的请求体。"""

    matrix_name: str = Field(min_length=1, max_length=200)
    module: MatrixModule = Field(description="模块；`*` = 全部模块")
    doc_type: str = Field(min_length=1, max_length=30)
    version_purpose: str = Field(
        min_length=1, max_length=40, description="版本目的（如 ISSUED_FOR_CHANGE）"
    )
    steps: list[MatrixStepInput] = Field(min_length=1, description="步骤定义（≥1 步）")
    status: MatrixStatus = Field(default="DRAFT")


class SignatureMatrixUpdateRequest(BaseModel):
    """改矩阵模板的请求体（**部分更新**：给了才改）。"""

    matrix_name: str | None = Field(default=None, min_length=1, max_length=200)
    module: MatrixModule | None = None
    doc_type: str | None = Field(default=None, min_length=1, max_length=30)
    version_purpose: str | None = Field(default=None, min_length=1, max_length=40)
    steps: list[MatrixStepInput] | None = Field(default=None, min_length=1)
    status: MatrixStatus | None = None


class SignatureMatrixResponse(BaseModel):
    """矩阵模板（显式声明，零裸字段）。"""

    matrix_id: uuid.UUID
    matrix_name: str
    module: str
    doc_type: str
    version_purpose: str
    status: str
    steps: list[MatrixStepResponse]
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SignatureMatrixListResponse(BaseModel):
    """矩阵列表 + 总数。"""

    items: list[SignatureMatrixResponse]
    total: int


class MatrixBindingRequest(BaseModel):
    """把矩阵绑到项目 × 模块。"""

    module: str = Field(min_length=1, max_length=30)
    matrix_id: uuid.UUID


class MatrixBindingResponse(BaseModel):
    """绑定结果。"""

    project_id: uuid.UUID
    module: str
    matrix_id: uuid.UUID
    matrix_name: str = Field(description="绑的矩阵名（回显，便于前端确认）")


class MatrixUnbindResponse(BaseModel):
    """解绑结果。"""

    project_id: uuid.UUID
    module: str
    unbound: bool = Field(description="是否真删了一行（本来就没绑 ⇒ False）")
