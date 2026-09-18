"""管道等级端点（Task 1.9.2 / P2-STD-001）。

spec §3.2.5 API 表 5 端点 + 验收派生的 DELETE（在用 409 仅可作废）与项目分配 POST。

ACL：读（list/get/project list）= DESIGNER + PROCESS_CONTROLLER + SYSTEM_ADMIN；
写（create/update/delete/assign）= PROCESS_CONTROLLER + SYSTEM_ADMIN。
`current_actor / require_roles / _Actor` 与 config.py 同源（该模块 `__all__` 导出）。

SUP-002 PC-4（V1.4 §2.4）：项目级 fork + 5 态轻量状态机端点：
- fork / create-new / override / submit / publish / obsolete → PROCESS_CONTROLLER + SYSTEM_ADMIN
- approve / reject                                        → REVIEWER + SYSTEM_ADMIN
- get_effective（读）            → DESIGNER + PROCESS_CONTROLLER + SYSTEM_ADMIN
"""
from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.pipe_class import (
    PipeClassCreate,
    PipeClassResponse,
    PipeClassUpdate,
)
from app.services.pipe_class_service import PipeClassService

router = APIRouter(tags=["pipe-classes"])


# ---------------------------------------------------------------------------
# SUP-002 PC-4 request/response schemas（项目级 fork）
# ---------------------------------------------------------------------------


class ProjectPipeClassForkRequest(BaseModel):
    class_id: str = Field(
        ..., min_length=1, max_length=50, description="公司级管号等级 ID"
    )


class ProjectPipeClassCreateRequest(BaseModel):
    class_name: str = Field(
        ..., min_length=1, max_length=100, description="项目级管号等级名"
    )
    data: dict = Field(
        default_factory=dict, description="项目级覆盖字段字典"
    )


class ProjectPipeClassOverrideRequest(BaseModel):
    override: dict = Field(
        default_factory=dict, description="覆盖字段字典（与公司级同名字段覆盖）"
    )


class ProjectPipeClassFullResponse(BaseModel):
    project_class_id: UUID
    project_id: UUID
    source_class_id: str | None
    class_name: str
    snapshot_json: dict | None
    override_json: dict
    status: str
    model_config = {"from_attributes": True}


class ProjectPipeClassEffectiveResponse(BaseModel):
    project_id: UUID
    class_name: str
    effective: dict


@router.get("/pipe-classes", response_model=list[PipeClassResponse])
async def list_pipe_classes(
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    status: str | None = Query(None), keyword: str | None = Query(None),
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.list_company(db, status=status, keyword=keyword)


@router.post("/pipe-classes", response_model=PipeClassResponse, status_code=201)
async def create_pipe_class(
    payload: PipeClassCreate,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """PC-3：公司级管道等级创建（同步挂 ConfigAsset + ConfigVersion v1）。

    Excel 批量导入端点 ``/pipe-classes/import`` 仍走 1.9 3 态契约 ``create()``
    （向后兼容 1.9 客户）。
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.create_with_config_asset(db, payload=payload, actor=user)


@router.get("/pipe-classes/import-template")
async def download_import_template(
    user: Annotated[_Actor, Depends(current_actor)],
):
    """导入模板下载（Task 1.9.6）。静态段：须注册在 /pipe-classes/{class_id} 之前。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return Response(
        content=PipeClassService.build_import_template(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=pipe_classes_template.xlsx"},
    )


@router.post("/pipe-classes/import")
async def import_pipe_classes(
    file: UploadFile,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Excel 批量导入（Task 1.9.6）。静态段：须注册在 /pipe-classes/{class_id} 之前。"""
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.import_from_excel(db, file.file)


@router.get("/pipe-classes/{class_id}", response_model=PipeClassResponse)
async def get_pipe_class(
    class_id: str,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.get(db, class_id)


@router.put("/pipe-classes/{class_id}", response_model=PipeClassResponse)
async def update_pipe_class(
    class_id: str, payload: PipeClassUpdate,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    if payload.class_id != class_id:
        # service 层 update 的 model_dump 含 class_id，不一致会覆写主键
        raise HTTPException(
            status_code=422,
            detail=f"payload.class_id {payload.class_id} 与路径 {class_id} 不一致",
        )
    return await PipeClassService.update(db, class_id, payload=payload)


@router.delete("/pipe-classes/{class_id}", status_code=204)
async def delete_pipe_class(
    class_id: str,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    await PipeClassService.delete(db, class_id)


# ---------------------------------------------------------------------------
# SUP-002 PC-3：5 态 transition 端点（公司级；ConfigAsset 驱动）
# ACL：
#   /submit   PROCESS_CONTROLLER, SYSTEM_ADMIN
#   /approve  REVIEWER,         SYSTEM_ADMIN
#   /publish  APPROVER,         SYSTEM_ADMIN
#   /obsolete PROCESS_CONTROLLER, REVIEWER, APPROVER, SYSTEM_ADMIN
# ---------------------------------------------------------------------------


@router.post("/pipe-classes/{class_id}/submit", response_model=PipeClassResponse)
async def submit_pipe_class(
    class_id: str,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.submit(db, class_id, actor=user)


@router.post("/pipe-classes/{class_id}/approve", response_model=PipeClassResponse)
async def approve_pipe_class(
    class_id: str,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "REVIEWER", "SYSTEM_ADMIN")
    return await PipeClassService.approve(db, class_id, actor=user)


@router.post("/pipe-classes/{class_id}/publish", response_model=PipeClassResponse)
async def publish_pipe_class(
    class_id: str,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "APPROVER", "SYSTEM_ADMIN")
    return await PipeClassService.publish(db, class_id, actor=user)


@router.post("/pipe-classes/{class_id}/obsolete", response_model=PipeClassResponse)
async def obsolete_pipe_class(
    class_id: str,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN")
    return await PipeClassService.obsolete(db, class_id, actor=user)


@router.get(
    "/projects/{project_id}/pipe-classes", response_model=list[ProjectPipeClassFullResponse]
)
async def list_project_pipe_classes(
    project_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.list_project(db, project_id)


# ---------------------------------------------------------------------------
# SUP-002 PC-4：项目级 fork + 5 态 transition 端点（V1.4 §2.4）
# ACL：
#   fork / create-new / override / submit / publish / obsolete → PC + SA
#   approve / reject                                            → REVIEWER + SA
#   effective (读)                                              → DESIGNER + PC + SA
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/pipe-classes/fork",
    response_model=ProjectPipeClassFullResponse, status_code=201,
)
async def fork_project_pipe_class(
    project_id: UUID, payload: ProjectPipeClassForkRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """项目级 fork：从公司级等级创建 ProjectPipeClass + snapshot_json 快照。"""
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.fork_to_project(
        db, project_id=project_id, class_id=payload.class_id, actor=user,
    )


@router.post(
    "/projects/{project_id}/pipe-classes/new",
    response_model=ProjectPipeClassFullResponse, status_code=201,
)
async def create_project_pipe_class(
    project_id: UUID, payload: ProjectPipeClassCreateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """项目全新创建管道等级（source_class_id=NULL）。"""
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.create_project_class(
        db,
        project_id=project_id,
        class_name=payload.class_name,
        data=payload.data,
        actor=user,
    )


@router.put(
    "/projects/{project_id}/pipe-classes/{project_class_id}/override",
    response_model=ProjectPipeClassFullResponse,
)
async def update_project_pipe_class_override(
    project_id: UUID, project_class_id: UUID,
    payload: ProjectPipeClassOverrideRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """修改项目级 override_json（仅 DRAFT/PENDING 可改）。"""
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.update_project_override(
        db,
        project_class_id=project_class_id,
        override=payload.override,
        actor=user,
    )


@router.post(
    "/projects/{project_id}/pipe-classes/{project_class_id}/submit",
    response_model=ProjectPipeClassFullResponse,
)
async def submit_project_pipe_class(
    project_id: UUID, project_class_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """DRAFT → PENDING。"""
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.submit_project_class(
        db, project_class_id=project_class_id, actor=user,
    )


@router.post(
    "/projects/{project_id}/pipe-classes/{project_class_id}/approve",
    response_model=ProjectPipeClassFullResponse,
)
async def approve_project_pipe_class(
    project_id: UUID, project_class_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """PENDING → APPROVED（CATEGORY_5 单层签）。"""
    require_roles(user, "REVIEWER", "SYSTEM_ADMIN")
    return await PipeClassService.approve_project_class(
        db, project_class_id=project_class_id, actor=user,
    )


@router.post(
    "/projects/{project_id}/pipe-classes/{project_class_id}/reject",
    response_model=ProjectPipeClassFullResponse,
)
async def reject_project_pipe_class(
    project_id: UUID, project_class_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """PENDING → DRAFT（拒绝，写 ConfigApproval decision=REJECTED）。"""
    require_roles(user, "REVIEWER", "SYSTEM_ADMIN")
    return await PipeClassService.reject_project_class(
        db, project_class_id=project_class_id, actor=user,
    )


@router.post(
    "/projects/{project_id}/pipe-classes/{project_class_id}/publish",
    response_model=ProjectPipeClassFullResponse,
)
async def publish_project_pipe_class(
    project_id: UUID, project_class_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """APPROVED → PUBLISHED。"""
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await PipeClassService.publish_project_class(
        db, project_class_id=project_class_id, actor=user,
    )


@router.post(
    "/projects/{project_id}/pipe-classes/{project_class_id}/obsolete",
    response_model=ProjectPipeClassFullResponse,
)
async def obsolete_project_pipe_class(
    project_id: UUID, project_class_id: UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """→ OBSOLETE（DRAFT/APPROVED/PUBLISHED 都可经 OBSOLETE 出局）。"""
    require_roles(user, "PROCESS_CONTROLLER", "REVIEWER", "SYSTEM_ADMIN")
    return await PipeClassService.obsolete_project_class(
        db, project_class_id=project_class_id, actor=user,
    )


@router.get(
    "/projects/{project_id}/pipe-classes/{class_name}/effective",
    response_model=ProjectPipeClassEffectiveResponse,
)
async def get_project_pipe_class_effective(
    project_id: UUID, class_name: str,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """返回项目级有效值（snapshot_json ⊕ override_json 递归深合并）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    effective = await PipeClassService.get_effective(
        db, project_id=project_id, class_name=class_name,
    )
    return ProjectPipeClassEffectiveResponse(
        project_id=project_id, class_name=class_name, effective=effective,
    )
