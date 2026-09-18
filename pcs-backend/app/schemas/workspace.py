"""Workspace Pydantic schemas（Sprint 1）。

仅用作 Pydantic 序列化与请求体校验，不与 ORM 模型耦合。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    workspace_type: str = Field(
        ...,
        pattern="^(FORMAL|PERSONAL|TEMPORARY)$",
        description="工作区类型：FORMAL 项目正式 / PERSONAL 个人 / TEMPORARY 临时",
    )
    name: str = Field(..., min_length=1, max_length=200, description="工作区名称")
    project_id: uuid.UUID | None = Field(None, description="所属项目 ID（PERSONAL 可空）")
    retention_days: int | None = Field(
        default=None, ge=1, le=365, description="数据保留天数（TEMPORARY 必填）"
    )


class WorkspaceOut(BaseModel):
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    workspace_type: str = Field(..., description="工作区类型")
    name: str = Field(..., description="工作区名称")
    project_id: uuid.UUID | None = Field(None, description="所属项目 ID")
    owner_id: uuid.UUID | None = Field(None, description="拥有者 ID")
    created_at: datetime = Field(..., description="创建时间")
    last_active_at: datetime | None = Field(None, description="最近活跃时间")
    retention_days: int | None = Field(None, description="数据保留天数")

    model_config = {"from_attributes": True}


class WorkspaceImportRequest(BaseModel):
    workspace_id: uuid.UUID = Field(..., description="源工作区 ID（PERSONAL/TEMPORARY）")
    project_id: uuid.UUID = Field(..., description="目标项目 ID（必须存在 FORMAL 工作区）")


class WorkspaceImportResponse(BaseModel):
    workspace_id: uuid.UUID = Field(..., description="目标工作区 ID")
    imported: bool = Field(..., description="是否成功导入")
    record_count: int = Field(..., ge=0, description="导入的记录数")