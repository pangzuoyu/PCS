"""Audit Query Pydantic schemas (F-P2-009 Sprint 3 / Issue 5).

含:
- AuditLogResponse / AuditLogListResponse: 通用 audit_logs 表查询.
- EquipmentDeletionAuditResponse / List: 设备删除 audit (有 project_id).
"""
from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class AuditLogResponse(BaseModel):
    """audit_logs 表单行响应.

    source-verify (2026-10-03): AuditLog 9 列
    audit_id / user_id / action / resource_type / resource_id /
    ip / user_agent / request_id / detail_json / occurred_at.
    仅暴露 query 必要列 (ip/user_agent/request_id 内部用, 不入 list 响应).
    """

    audit_id: uuid.UUID = Field(..., description="audit 行 UUID")
    user_id: uuid.UUID | None = Field(None, description="操作者 user_id")
    action: str = Field(..., description="动作类型 (CREATE/UPDATE/DELETE/...)")
    resource_type: str | None = Field(None, description="资源类型 (config_energy_conversion_factors/...)")
    resource_id: str | None = Field(None, description="资源 ID (String, 表内 BIGINT/UUID 通用)")
    detail_json: dict | None = Field(None, description="详情 JSON")
    occurred_at: datetime = Field(..., description="发生时间 (UTC)")

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """audit_logs 列表响应 (含分页)."""

    items: list[AuditLogResponse] = Field(default_factory=list)
    total: int = Field(..., ge=0, description="满足条件的总行数")
    limit: int = Field(..., ge=1, le=200)
    offset: int = Field(..., ge=0)


class EquipmentDeletionAuditResponse(BaseModel):
    """equipment_deletion_audit 表单行响应.

    source-verify (2026-10-03): EquipmentDeletionAudit 9 列
    audit_id / equipment_id / project_id / workspace_id /
    equipment_tag / deleted_by / orphan_records / occurred_at / reason.
    """

    audit_id: uuid.UUID = Field(..., description="audit 行 UUID")
    equipment_id: uuid.UUID = Field(..., description="被删除设备 ID")
    project_id: uuid.UUID = Field(..., description="项目 ID")
    workspace_id: uuid.UUID = Field(..., description="workspace ID")
    equipment_tag: str = Field(..., description="设备位号快照")
    deleted_by: uuid.UUID = Field(..., description="删除操作者 user_id")
    orphan_records: dict = Field(..., description="被 SET NULL 的 utility_* 记录")
    occurred_at: datetime = Field(..., description="删除时间 (UTC)")
    reason: str | None = Field(None, description="删除原因 (可选)")

    model_config = {"from_attributes": True}


class EquipmentDeletionAuditListResponse(BaseModel):
    """equipment_deletion_audit 列表响应."""

    items: list[EquipmentDeletionAuditResponse] = Field(default_factory=list)
    total: int = Field(..., ge=0)
    limit: int = Field(..., ge=1, le=200)
    offset: int = Field(..., ge=0)