"""UserProject 管理 API（P7-7+ BLOCKER-3 admin 端点）。

POST   /api/v1/user-projects/grant     授予用户项目访问权
POST   /api/v1/user-projects/revoke    撤销用户项目访问权
GET    /api/v1/user-projects/me        当前用户可见项目列表
GET    /api/v1/user-projects/{user_id} 管理员查看某用户项目列表

ACL: 全部 require_roles SYSADMIN（grant/revoke/{user_id}）;
     me 接口需 DESIGNER+ 即可（任何人可看自己的可见项目列表）。

P7-7+ 范围：admin 全权管理 + audit 落 audit_logs (后续 Sprint 7.1 接)。
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import current_actor, require_roles
from app.db.session import get_db
from app.models.project import UserProject
from app.services.user_project_service import UserProjectService

router = APIRouter(prefix="/user-projects", tags=["user-projects"])


class GrantRequest(BaseModel):
    """grant 请求 body."""

    user_id: uuid.UUID = Field(..., description="目标用户 UUID")
    project_id: uuid.UUID = Field(..., description="目标项目 UUID")
    role_in_project: str = Field(
        ...,
        description="项目内角色 (DESIGNER/CHECKER/APPROVER/REVIEWER/VIEWER)",
    )


class RevokeRequest(BaseModel):
    """revoke 请求 body."""

    user_id: uuid.UUID = Field(..., description="目标用户 UUID")
    project_id: uuid.UUID = Field(..., description="目标项目 UUID")


class UserProjectResponse(BaseModel):
    """UserProject 单条响应."""

    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID
    role_in_project: str
    granted_by: uuid.UUID | None = None
    granted_at: str | None = None
    revoked_at: str | None = None
    revoked_by: uuid.UUID | None = None


def _to_response(record: UserProject) -> UserProjectResponse:
    return UserProjectResponse(
        id=record.id,
        user_id=record.user_id,
        project_id=record.project_id,
        role_in_project=record.role_in_project,
        granted_by=record.granted_by,
        granted_at=record.granted_at.isoformat() if record.granted_at else None,
        revoked_at=record.revoked_at.isoformat() if record.revoked_at else None,
        revoked_by=record.revoked_by,
    )


@router.post(
    "/grant",
    response_model=UserProjectResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_user_project_access(
    body: GrantRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor=Depends(current_actor),
) -> UserProjectResponse:
    """授予用户项目访问权 (SYSADMIN only)."""
    require_roles(actor, "SYSADMIN")
    try:
        record = await UserProjectService.grant_project_access(
            db,
            user_id=body.user_id,
            project_id=body.project_id,
            role_in_project=body.role_in_project,
            granted_by=actor.user_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return _to_response(record)


@router.post("/revoke", response_model=UserProjectResponse | None)
async def revoke_user_project_access(
    body: RevokeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor=Depends(current_actor),
):
    """撤销用户项目访问权 (SYSADMIN only)."""
    require_roles(actor, "SYSADMIN")
    record = await UserProjectService.revoke_project_access(
        db,
        user_id=body.user_id,
        project_id=body.project_id,
        revoked_by=actor.user_id,
    )
    return _to_response(record) if record else None


@router.get("/me", response_model=list[UserProjectResponse])
async def list_my_projects(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor=Depends(current_actor),
) -> list[UserProjectResponse]:
    """当前用户可见项目列表 (DESIGNER+ 即可)."""
    require_roles(actor, "DESIGNER", "CHECKER", "APPROVER", "REVIEWER", "SYSADMIN")
    records = await UserProjectService.list_user_projects(
        db, user_id=actor.user_id
    )
    return [_to_response(r) for r in records]


@router.get("/{user_id}", response_model=list[UserProjectResponse])
async def list_user_projects(
    user_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor=Depends(current_actor),
) -> list[UserProjectResponse]:
    """管理员查看某用户项目列表 (SYSADMIN only)."""
    require_roles(actor, "SYSADMIN")
    records = await UserProjectService.list_user_projects(
        db, user_id=user_id, include_revoked=False
    )
    return [_to_response(r) for r in records]
