"""Workspace Pydantic schemas（Sprint 1）。

仅用作 Pydantic 序列化与请求体校验，不与 ORM 模型耦合。
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    workspace_type: str = Field(..., pattern="^(FORMAL|PERSONAL|TEMPORARY)$")
    name: str = Field(min_length=1, max_length=200)
    project_id: uuid.UUID | None = None
    retention_days: int | None = Field(default=None, ge=1, le=365)


class WorkspaceOut(BaseModel):
    workspace_id: uuid.UUID
    workspace_type: str
    name: str
    project_id: uuid.UUID | None
    owner_id: uuid.UUID | None
    created_at: datetime
    last_active_at: datetime | None
    retention_days: int | None

    model_config = {"from_attributes": True}


class WorkspaceImportRequest(BaseModel):
    workspace_id: uuid.UUID
    project_id: uuid.UUID


class WorkspaceImportResponse(BaseModel):
    workspace_id: uuid.UUID
    imported: bool
    record_count: int