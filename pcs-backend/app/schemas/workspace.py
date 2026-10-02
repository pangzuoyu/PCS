"""Workspace Pydantic schemas（Sprint 1）。

仅用作 Pydantic 序列化与请求体校验，不与 ORM 模型耦合。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    """创建工作区请求体（POST /workspaces）。

    业务：workspace_type 锁定 FORMAL/PERSONAL/TEMPORARY 三类；retention_days
    1~365 天（仅 TEMPORARY 必填）；project_id PERSONAL 可空。
    """

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
    """工作区出参（GET /workspaces 响应体）。

    业务：含 workspace_id + workspace_type + name + owner_id + retention_days
    + last_active_at + status（F-P3-003 Sprint 3 新增）；
    from_attributes=True 直接绑 ORM 行（Workspace）。
    """

    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    workspace_type: str = Field(..., description="工作区类型")
    name: str = Field(..., description="工作区名称")
    project_id: uuid.UUID | None = Field(None, description="所属项目 ID")
    owner_id: uuid.UUID | None = Field(None, description="拥有者 ID")
    created_at: datetime = Field(..., description="创建时间")
    last_active_at: datetime | None = Field(None, description="最近活跃时间")
    retention_days: int | None = Field(None, description="数据保留天数")
    status: str = Field(
        default="ACTIVE",
        description="F-P3-003: ACTIVE / ARCHIVED 2-state",
    )

    model_config = {"from_attributes": True}


class WorkspaceImportRequest(BaseModel):
    """工作区导入请求体（POST /workspaces/import）。

    业务：源工作区必须 PERSONAL/TEMPORARY，目标项目必须存在对应 FORMAL 工作区；
    后端 import_records 走 zip 序列化复制记录到目标。
    """

    workspace_id: uuid.UUID = Field(..., description="源工作区 ID（PERSONAL/TEMPORARY）")
    project_id: uuid.UUID = Field(..., description="目标项目 ID（必须存在 FORMAL 工作区）")


class WorkspaceImportResponse(BaseModel):
    """工作区导入响应体（POST /workspaces/import 响应）。

    业务：workspace_id 目标工作区 ID，imported 是否成功，record_count 复制的
    记录数（前端用此触发路由跳转 + 提示）。
    """

    workspace_id: uuid.UUID = Field(..., description="目标工作区 ID")
    imported: bool = Field(..., description="是否成功导入")
    record_count: int = Field(..., ge=0, description="导入的记录数")