"""P5-3-6 PSV 项目标准配置 API。

按 SUP-P5-PSV-001 §3.1 + ADR-0028 V1.1：

端点：
- GET /api/v1/projects/{project_id}/psv/standard-profile
    查项目当前默认 PSV discipline 的标准配置（is_default=TRUE + migrated_default=FALSE
    + effective_to IS NULL）。无 → 200 with null body（前端按"未配置"展示）。

- POST /api/v1/projects/{project_id}/psv/standard-profile
    body: {
        profile_code: API / GB / CUSTOM,
        standard_refs_json: {fire_case, relief_area, orifice, ...}，
        approval_json?: CUSTOM 必填，
        approved_by?: UUID
    }
    作用：将现有默认 is_default 标 False（不显式迁移）；新增 is_default=TRUE；
    CUSTOM 必须填 approval_json（DB CHECK 已锁定）。

设计要点：
- ACL：
  - GET  → DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
  - POST → PROCESS_CONTROLLER / SYSTEM_ADMIN（配置项需更高权限）
- 不显式处理 EXCLUDE USING gist 冲突（DB 层兜底 → 422/IntegrityError → 转 PcsError）
- effective_to 留 NULL（V1 锁定即时生效；预排程留 P5-3-7）
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.models.psv_standards import ProjectCalculationStandardProfile
from app.services.exceptions import PcsError

router = APIRouter(prefix="/projects/{project_id}/psv", tags=["psv-config"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


StandardProfileCodeLit = Literal["API", "GB", "CUSTOM"]


class StandardProfileResponse(BaseModel):
    """GET /standard-profile 响应。"""

    profile_id: uuid.UUID = Field(..., description="ProjectCalculationStandardProfile.id")
    project_id: uuid.UUID = Field(..., description="项目 UUID")
    discipline: str = Field(default="PSV", description="固定 PSV")
    profile_code: str = Field(..., description="API / GB / CUSTOM")
    standard_refs_json: dict[str, Any] = Field(
        ..., description="各子标准、版本、条款映射"
    )
    approval_json: dict[str, Any] | None = Field(
        default=None, description="CUSTOM 审批依据"
    )
    is_default: bool = Field(..., description="是否当前默认")
    migrated_default: bool = Field(..., description="是否迁移占位")
    effective_from: datetime = Field(..., description="生效起始时间")
    effective_to: datetime | None = Field(
        default=None, description="失效时间；NULL 表示当前生效"
    )
    approved_by: uuid.UUID | None = Field(
        default=None, description="审批人 UUID"
    )
    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime = Field(..., description="更新时间")


class UpsertStandardProfileRequest(BaseModel):
    """POST /standard-profile 请求体。"""

    profile_code: StandardProfileCodeLit = Field(
        ..., description="API / GB / CUSTOM"
    )
    standard_refs_json: dict[str, Any] = Field(
        ...,
        description="子标准引用（fire_case/relief_area/orifice 等子项）",
    )
    approval_json: dict[str, Any] | None = Field(
        default=None,
        description="CUSTOM 必填：审批人+依据",
    )
    approved_by: uuid.UUID | None = Field(
        default=None,
        description="审批人 UUID（CUSTOM 必填）",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


def _serialize_profile(p: ProjectCalculationStandardProfile) -> StandardProfileResponse:
    return StandardProfileResponse(
        profile_id=p.id,
        project_id=p.project_id,
        discipline=p.discipline,
        profile_code=p.profile_code,
        standard_refs_json=dict(p.standard_refs_json or {}),
        approval_json=dict(p.approval_json) if p.approval_json else None,
        is_default=p.is_default,
        migrated_default=p.migrated_default,
        effective_from=p.effective_from,
        effective_to=p.effective_to,
        approved_by=p.approved_by,
        created_at=p.created_at,
        updated_at=p.updated_at,
    )


# ---------------------------------------------------------------------------
# GET /standard-profile
# ---------------------------------------------------------------------------


@router.get(
    "/standard-profile",
    response_model=StandardProfileResponse | None,
)
async def get_psv_standard_profile(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StandardProfileResponse | None:
    """查项目当前默认 PSV 标准配置；无 → 200 null（前端按"未配置"展示）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    from sqlalchemy import select

    stmt = (
        select(ProjectCalculationStandardProfile)
        .where(
            ProjectCalculationStandardProfile.project_id == project_id,
            ProjectCalculationStandardProfile.discipline == "PSV",
            ProjectCalculationStandardProfile.is_default.is_(True),
            ProjectCalculationStandardProfile.migrated_default.is_(False),
            ProjectCalculationStandardProfile.effective_to.is_(None),
        )
        .limit(1)
    )
    profile = (await db.execute(stmt)).scalar_one_or_none()
    if profile is None:
        return None
    return _serialize_profile(profile)


# ---------------------------------------------------------------------------
# POST /standard-profile
# ---------------------------------------------------------------------------


@router.post(
    "/standard-profile",
    status_code=201,
    response_model=StandardProfileResponse,
)
async def upsert_psv_standard_profile(
    project_id: uuid.UUID,
    req: UpsertStandardProfileRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StandardProfileResponse:
    """创建/激活项目 PSV 标准配置（设 is_default=TRUE）。

    流程：
    1. 校验：CUSTOM 必填 approval_json + approved_by
    2. 旧默认 is_default=FALSE（不显式迁移；新行 is_default=TRUE）
    3. 新行 effective_to NULL（V1 即时生效）
    4. DB EXCLUDE USING gist 兜底冲突 → IntegrityError → 转 PcsError

    ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    # 1. CUSTOM 必填校验
    if req.profile_code == "CUSTOM":
        if req.approval_json is None or req.approved_by is None:
            raise _to_http(PcsError(
                "CUSTOM profile 必须填 approval_json + approved_by",
                code="PSV_INPUT_ERROR",
                status=422,
            ))

    # 2. 旧默认 → is_default=FALSE
    try:
        await db.execute(
            update(ProjectCalculationStandardProfile)
            .where(
                ProjectCalculationStandardProfile.project_id == project_id,
                ProjectCalculationStandardProfile.discipline == "PSV",
                ProjectCalculationStandardProfile.is_default.is_(True),
                ProjectCalculationStandardProfile.migrated_default.is_(False),
                ProjectCalculationStandardProfile.effective_to.is_(None),
            )
            .values(is_default=False, updated_at=datetime.now(UTC))
        )

        # 3. 新行
        new_profile = ProjectCalculationStandardProfile(
            project_id=project_id,
            discipline="PSV",
            profile_code=req.profile_code,
            standard_refs_json=dict(req.standard_refs_json),
            approval_json=dict(req.approval_json) if req.approval_json else None,
            is_default=True,
            migrated_default=False,
            approved_by=req.approved_by,
        )
        db.add(new_profile)
        await db.commit()
    except IntegrityError as e:
        await db.rollback()
        raise _to_http(PcsError(
            f"PSV 标准配置冲突：{str(e.orig)[:200]}",
            code="PSV_PROFILE_CONFLICT",
            status=422,
        )) from e

    # 4. 重读返序列化（DB now() 与 ORM 兜底；SQLite 测试环境下 refresh 会报
    # InvalidRequestError，改用 SELECT 重查）
    from sqlalchemy import select

    fresh = (
        await db.execute(
            select(ProjectCalculationStandardProfile).where(
                ProjectCalculationStandardProfile.id == new_profile.id
            )
        )
    ).scalar_one()
    return _serialize_profile(fresh)


__all__ = ["router"]