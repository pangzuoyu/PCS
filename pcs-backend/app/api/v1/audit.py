"""Audit Query API (F-P2-009 Sprint 3 / Issue 7 混合 RBAC).

端点 (混合 RBAC, source-verify 2026-10-03):
- GET /audit-logs: SYSTEM_ADMIN only (audit_logs 表无 project_id)
- GET /equipment-deletion-audit: DESIGNER+ + project_id filter (该表有 project_id)
- GET /config-audit: DESIGNER+ + 单一 resource_type 过滤 (公司级全局元数据)

rate limit: 无 (Issue 5 — 低频 admin 工具, 9-dim filter + RBAC + limit≤200 + F-P0-004 隔离).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.api.v1._guard import check_project_access_or_404
from app.db.session import get_db
from app.models.equipment import EquipmentDeletionAudit
from app.models.system import AuditLog
from app.schemas.audit import (
    AuditLogListResponse,
    AuditLogResponse,
    EquipmentDeletionAuditListResponse,
    EquipmentDeletionAuditResponse,
)

router = APIRouter(tags=["audit"])


# ---------------------------------------------------------------------------
# /audit-logs — 通用 audit (SYSTEM_ADMIN only, Issue 7 收窄)
# ---------------------------------------------------------------------------


@router.get("/audit-logs", response_model=AuditLogListResponse)
async def list_audit_logs(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    resource_type: str | None = Query(None, max_length=50),
    resource_id: str | None = Query(None, max_length=100),
    user_id: uuid.UUID | None = Query(None),
    action: str | None = Query(None, max_length=50),
    occurred_after: datetime | None = Query(None),
    occurred_before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AuditLogListResponse:
    """Audit logs 通用查询. SYSTEM_ADMIN only (Issue 7 / F-P0-004 收窄).

    F-P0-001 R1 签署痕迹查询: 走 GET /config-audit (独立端点, DESIGNER+);
    或 admin 代查.
    """
    require_roles(user, "SYSTEM_ADMIN")
    conditions = []
    if resource_type is not None:
        conditions.append(AuditLog.resource_type == resource_type)
    if resource_id is not None:
        conditions.append(AuditLog.resource_id == resource_id)
    if user_id is not None:
        conditions.append(AuditLog.user_id == user_id)
    if action is not None:
        conditions.append(AuditLog.action == action)
    if occurred_after is not None:
        conditions.append(AuditLog.occurred_at >= occurred_after)
    if occurred_before is not None:
        conditions.append(AuditLog.occurred_at < occurred_before)
    where_clause = conditions[0] if len(conditions) == 1 else (
        and_(*conditions) if conditions else True
    )
    total = (
        await db.execute(select(func.count()).select_from(AuditLog).where(where_clause))
    ).scalar_one()
    items = (
        await db.execute(
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(r) for r in items],
        total=total, limit=limit, offset=offset,
    )


# ---------------------------------------------------------------------------
# /equipment-deletion-audit — 该表有 project_id, DESIGNER+ 可查
# ---------------------------------------------------------------------------


@router.get("/equipment-deletion-audit", response_model=EquipmentDeletionAuditListResponse)
async def list_equipment_deletion_audit(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    project_id: uuid.UUID | None = Query(None, description="F-P0-004 IDOR: 非 admin 必传"),
    workspace_id: uuid.UUID | None = Query(None),
    equipment_id: uuid.UUID | None = Query(None),
    deleted_by: uuid.UUID | None = Query(None),
    occurred_after: datetime | None = Query(None),
    occurred_before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> EquipmentDeletionAuditListResponse:
    """设备删除 audit 查询 (F-P0-004 IDOR 防护).

    守卫链 (defense-in-depth, P7-7+ BLOCKER-3 集成):
    1. RBAC: DESIGNER+ (require_roles)
    2. IDOR: project_id filter (Issue 7)
    3. UserProject guard: 用户对该 project 有 grant (SYSADMIN bypass)
    """
    require_roles(
        user, "DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN",
    )
    # P7-7+: 强制 project_id + UserProject guard (非 admin 必传; 否则 403/404)
    if project_id is not None:
        # SYSADMIN bypass 在 _guard.py:37 (检查 "SYSADMIN"); 但 JWT role 是
        # "SYSTEM_ADMIN" — 同义两种写法都传以兼容.
        actor_roles_list = [user.role, "SYSADMIN"] if user.role == "SYSTEM_ADMIN" else [user.role]
        await check_project_access_or_404(
            db,
            user_id=user.user_id,
            project_id=project_id,
            actor_roles=actor_roles_list,
        )
    conditions = []
    if user.role != "SYSTEM_ADMIN":
        if project_id is None:
            raise HTTPException(
                status_code=403,
                detail="project_id required for non-system-admin",
            )
        conditions.append(EquipmentDeletionAudit.project_id == project_id)
    elif project_id is not None:
        conditions.append(EquipmentDeletionAudit.project_id == project_id)
    if workspace_id is not None:
        conditions.append(EquipmentDeletionAudit.workspace_id == workspace_id)
    if equipment_id is not None:
        conditions.append(EquipmentDeletionAudit.equipment_id == equipment_id)
    if deleted_by is not None:
        conditions.append(EquipmentDeletionAudit.deleted_by == deleted_by)
    if occurred_after is not None:
        conditions.append(EquipmentDeletionAudit.occurred_at >= occurred_after)
    if occurred_before is not None:
        conditions.append(EquipmentDeletionAudit.occurred_at < occurred_before)
    where_clause = conditions[0] if len(conditions) == 1 else (
        and_(*conditions) if conditions else True
    )
    total = (
        await db.execute(
            select(func.count())
            .select_from(EquipmentDeletionAudit)
            .where(where_clause)
        )
    ).scalar_one()
    items = (
        await db.execute(
            select(EquipmentDeletionAudit)
            .where(where_clause)
            .order_by(EquipmentDeletionAudit.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return EquipmentDeletionAuditListResponse(
        items=[EquipmentDeletionAuditResponse.model_validate(r) for r in items],
        total=total, limit=limit, offset=offset,
    )


# ---------------------------------------------------------------------------
# /config-audit — F-P0-001 R1 独立端点 (DESIGNER+, 公司级全局)
# ---------------------------------------------------------------------------


@router.get("/config-audit", response_model=AuditLogListResponse)
async def list_config_audit(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    asset_id: int | None = Query(
        None, ge=1, description="ConfigEnergyConversionFactor.id (BIGINT)"
    ),
    occurred_after: datetime | None = Query(None),
    occurred_before: datetime | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> AuditLogListResponse:
    """F-P0-001 R1 签署痕迹独立端点 (DESIGNER+, 全公司可查).

    source-verify 2026-10-03:
    - resource_type 实际值 = "config_energy_conversion_factors"
    - ConfigEnergyConversionFactor 公司级全局 (无 project_id) — F-P0-004 IDOR 不适用
    - audit_logs.resource_id 是 String(100), ConfigEnergyConversionFactor.id 是 BIGINT,
      需 str() 转换

    业务: 工艺室 / 设计 / 审查 / 审批 可查全公司 ConfigEnergyConversionFactor audit.
    F-P0-001 R1 修订 trace 是其中一类 action=CONFIG_R1_BACKFILL.
    """
    require_roles(
        user, "DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN",
    )
    conditions = [AuditLog.resource_type == "config_energy_conversion_factors"]
    if asset_id is not None:
        conditions.append(AuditLog.resource_id == str(asset_id))
    if occurred_after is not None:
        conditions.append(AuditLog.occurred_at >= occurred_after)
    if occurred_before is not None:
        conditions.append(AuditLog.occurred_at < occurred_before)
    where_clause = and_(*conditions)
    total = (
        await db.execute(select(func.count()).select_from(AuditLog).where(where_clause))
    ).scalar_one()
    items = (
        await db.execute(
            select(AuditLog)
            .where(where_clause)
            .order_by(AuditLog.occurred_at.desc())
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return AuditLogListResponse(
        items=[AuditLogResponse.model_validate(r) for r in items],
        total=total, limit=limit, offset=offset,
    )