"""P3.x SIM-27：sim_imports 9 类查询端点（spec §5.5）。

5 GET 端点 + 9 维度过滤（query params）：
- GET /projects/{project_id}/imports（paginated list + 8 query param 过滤）
- GET /imports/{import_id}（单条 fetch）
- GET /imports/{import_id}/warnings（关联 warnings）
- GET /imports/{import_id}/preview-streams（status==PREVIEW 才可读）
- GET /imports/expired（批量列已过期）

9 维度：
    1. project_id（path 必填，强制 scope）
    2. status（PREVIEW/COMMITTED/EXPIRED）
    3. import_type（PROII/EXCEL）
    4. source_file_name（LIKE 模糊匹配）
    5. banner_version（精确匹配）
    6. created_by（UUID 精确）
    7. date_from + date_to（created_at 区间）
    8. has_warnings（bool，warnings_json 非空）
    9. convergence_status（精确匹配）

错误码：
- 401 missing bearer / 403 role forbidden
- 404 SIM_IMPORT_NOT_FOUND
- 410 SIM_IMPORT_NOT_PREVIEW（preview-streams 仅 PREVIEW 可读）
- 422 参数校验失败
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.models.sim_import import (
    SimImport,
    SimImportStatus,
    SimImportWarning,
)

router = APIRouter(prefix="/imports", tags=["imports"])

# 嵌套在 /projects/{project_id}/imports 的 list 端点（保持原 imports.py POST 端点路径）
project_router = APIRouter(prefix="/projects/{project_id}/imports", tags=["imports"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class SimImportListItem(BaseModel):
    """sim_import 列表项（精简字段）。"""

    import_id: uuid.UUID
    project_id: uuid.UUID
    import_type: str
    status: str
    source_file_name: str
    convergence_status: str | None
    banner_version: str | None
    created_at: datetime
    created_by: uuid.UUID
    committed_at: datetime | None
    committed_by: uuid.UUID | None
    has_warnings: bool
    warning_count: int


class SimImportListResponse(BaseModel):
    """分页响应。"""

    items: list[SimImportListItem]
    total: int
    limit: int
    offset: int


class SimImportDetailResponse(BaseModel):
    """单条详情（完整字段）。"""

    import_id: uuid.UUID
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    import_type: str
    status: str
    source_file_name: str
    convergence_status: str | None
    banner_version: str | None
    created_at: datetime
    created_by: uuid.UUID
    committed_at: datetime | None
    committed_by: uuid.UUID | None
    expires_at: datetime
    has_warnings: bool
    warning_count: int


class SimImportWarningItem(BaseModel):
    warning_id: uuid.UUID
    severity: str
    message: str
    unit_id: str | None = None


class SimImportWarningListResponse(BaseModel):
    items: list[SimImportWarningItem]
    total: int


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_list_item(imp: SimImport) -> SimImportListItem:
    return SimImportListItem(
        import_id=imp.import_id,
        project_id=imp.project_id,
        import_type=imp.import_type.value,
        status=imp.status.value,
        source_file_name=imp.source_file_name,
        convergence_status=imp.convergence_status,
        banner_version=imp.banner_version,
        created_at=imp.created_at,
        created_by=imp.created_by,
        committed_at=imp.committed_at,
        committed_by=imp.committed_by,
        has_warnings=bool(imp.warnings_json),
        warning_count=len(imp.warnings_json) if imp.warnings_json else 0,
    )


def _to_detail(imp: SimImport) -> SimImportDetailResponse:
    return SimImportDetailResponse(
        import_id=imp.import_id,
        project_id=imp.project_id,
        workspace_id=imp.workspace_id,
        import_type=imp.import_type.value,
        status=imp.status.value,
        source_file_name=imp.source_file_name,
        convergence_status=imp.convergence_status,
        banner_version=imp.banner_version,
        created_at=imp.created_at,
        created_by=imp.created_by,
        committed_at=imp.committed_at,
        committed_by=imp.committed_by,
        expires_at=imp.expires_at,
        has_warnings=bool(imp.warnings_json),
        warning_count=len(imp.warnings_json) if imp.warnings_json else 0,
    )


# ---------------------------------------------------------------------------
# 1) GET /projects/{project_id}/imports — paginated list + 8 filter params
# ---------------------------------------------------------------------------


@project_router.get("", response_model=SimImportListResponse)
async def list_imports(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status_filter: Annotated[
        SimImportStatus | None, Query(alias="status")
    ] = None,
    import_type: Annotated[
        Literal["PROII", "EXCEL"] | None, Query(alias="import_type")
    ] = None,
    source_file_name: Annotated[str | None, Query()] = None,
    banner_version: Annotated[str | None, Query()] = None,
    created_by: Annotated[uuid.UUID | None, Query()] = None,
    date_from: Annotated[datetime | None, Query()] = None,
    date_to: Annotated[datetime | None, Query()] = None,
    has_warnings: Annotated[bool | None, Query()] = None,
    convergence_status: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SimImportListResponse:
    """按 9 维度过滤的 sim_imports 列表（project_id 强制 scope）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN", "VIEWER")
    conditions = [SimImport.project_id == project_id]
    if status_filter is not None:
        conditions.append(SimImport.status == status_filter)
    if import_type is not None:
        conditions.append(SimImport.import_type == import_type)
    if source_file_name:
        conditions.append(SimImport.source_file_name.ilike(f"%{source_file_name}%"))
    if banner_version:
        conditions.append(SimImport.banner_version == banner_version)
    if created_by is not None:
        conditions.append(SimImport.created_by == created_by)
    if date_from is not None:
        conditions.append(SimImport.created_at >= date_from)
    if date_to is not None:
        conditions.append(SimImport.created_at <= date_to)
    if convergence_status:
        conditions.append(SimImport.convergence_status == convergence_status)
    # has_warnings 由 func.jsonb_array_length 实现；空数组长度=0

    where_clause = and_(*conditions)
    # total
    total_stmt = select(func.count()).select_from(SimImport).where(where_clause)
    total = (await db.execute(total_stmt)).scalar_one()
    # items
    items_stmt = (
        select(SimImport)
        .where(where_clause)
        .order_by(SimImport.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(items_stmt)).scalars().all()
    items = [_to_list_item(r) for r in rows]
    # has_warnings 后置过滤（避免 SQL JSON 函数复杂度）
    if has_warnings is True:
        items = [i for i in items if i.has_warnings]
    elif has_warnings is False:
        items = [i for i in items if not i.has_warnings]
    return SimImportListResponse(
        items=items,
        total=total if has_warnings is None else len(items),
        limit=limit,
        offset=offset,
    )


# ---------------------------------------------------------------------------
# 2) GET /imports/{import_id} — single fetch
# ---------------------------------------------------------------------------
# 5) GET /imports/expired — 必须在 /{import_id} 之前注册，否则会被路径参数吞掉
# ---------------------------------------------------------------------------


@router.get("/expired", response_model=SimImportListResponse)
async def list_expired(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> SimImportListResponse:
    """列 expires_at < now 的 imports（不限 project，所有角色可读）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN", "VIEWER")
    now = datetime.now(UTC)
    where_clause = SimImport.expires_at < now
    total_stmt = select(func.count()).select_from(SimImport).where(where_clause)
    total = (await db.execute(total_stmt)).scalar_one()
    items_stmt = (
        select(SimImport)
        .where(where_clause)
        .order_by(SimImport.expires_at.asc())
        .limit(limit)
        .offset(offset)
    )
    rows = (await db.execute(items_stmt)).scalars().all()
    items = [_to_list_item(r) for r in rows]
    return SimImportListResponse(
        items=items, total=total, limit=limit, offset=offset
    )


# ---------------------------------------------------------------------------
# 2) GET /imports/{import_id} — single fetch
# ---------------------------------------------------------------------------


@router.get("/{import_id}", response_model=SimImportDetailResponse)
async def get_import_by_id(
    import_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimImportDetailResponse:
    """按 import_id 单条 fetch。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN", "VIEWER")
    imp = (
        await db.execute(select(SimImport).where(SimImport.import_id == import_id))
    ).scalar_one_or_none()
    if imp is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SIM_IMPORT_NOT_FOUND",
                "message": f"sim_import {import_id} 不存在",
            },
        )
    return _to_detail(imp)


# ---------------------------------------------------------------------------
# 3) GET /imports/{import_id}/preview-streams — 仅 PREVIEW 可读
# ---------------------------------------------------------------------------


@router.get("/{import_id}/preview-streams")
async def get_preview_streams(
    import_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict:
    """返回 preview 阶段的 streams JSON（仅 PREVIEW 状态）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    imp = (
        await db.execute(select(SimImport).where(SimImport.import_id == import_id))
    ).scalar_one_or_none()
    if imp is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SIM_IMPORT_NOT_FOUND",
                "message": f"sim_import {import_id} 不存在",
            },
        )
    if imp.status != SimImportStatus.PREVIEW:
        raise HTTPException(
            status_code=410,
            detail={
                "code": "SIM_IMPORT_NOT_PREVIEW",
                "message": (
                    f"sim_import {import_id} 当前 status={imp.status.value}，"
                    "preview-streams 仅 PREVIEW 可读"
                ),
            },
        )
    return imp.preview_streams_json


# ---------------------------------------------------------------------------
# 4) GET /imports/{import_id}/warnings — 关联 warnings
# ---------------------------------------------------------------------------


@router.get("/{import_id}/warnings", response_model=SimImportWarningListResponse)
async def list_warnings_for_import(
    import_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SimImportWarningListResponse:
    """列出指定 import 的所有 warnings。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN", "VIEWER")
    # 校验 import 存在
    exists = (
        await db.execute(select(SimImport.import_id).where(SimImport.import_id == import_id))
    ).scalar_one_or_none()
    if exists is None:
        raise HTTPException(
            status_code=404,
            detail={
                "code": "SIM_IMPORT_NOT_FOUND",
                "message": f"sim_import {import_id} 不存在",
            },
        )
    rows = (
        (
            await db.execute(
                select(SimImportWarning)
                .where(SimImportWarning.import_id == import_id)
                .order_by(SimImportWarning.created_at.asc())
            )
        )
        .scalars()
        .all()
    )
    items = [
        SimImportWarningItem(
            warning_id=w.warning_id,
            severity=w.severity.value,
            message=w.message,
            unit_id=w.unit_id,
        )
        for w in rows
    ]
    return SimImportWarningListResponse(items=items, total=len(items))



__all__ = ["router", "project_router"]