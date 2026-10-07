"""交付物读端点（P1-7+ D 模块 / P8 前置）。

P8 REPORT 依赖「从 `deliverables` / `deliverable_versions` 读数据」，而此前该表族
**无任何 HTTP 入口**（只有模型与 ChangeNoticeService）。本模块补上读面。

P1 spec §3.2 定义的 5 个端点中，写的那三个（`POST /deliverables`、
`POST /deliverables/{id}/issue`、`POST /deliverables/{id}/customer-approval/proxy`）
**尚未实现** —— 它们服务 P9 签署流程，需先有签署矩阵消费方
（`SignatureMatrix.steps_json` 目前无 service）。见 TODOS.md 的 P8 前置项 ②。

ACL：读 = DESIGNER + PROCESS_CONTROLLER + REVIEWER + APPROVER + SYSTEM_ADMIN
（与 user_projects 同源的项目访问权校验：`check_project_access_or_404` 用 404
而非 403，不向攻击者泄漏项目存在性）。
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.deliverable import (
    DeliverableListResponse,
    DeliverableResponse,
    DeliverableSnapshotResponse,
    DeliverableVersionResponse,
    RecordBindingResponse,
)
from app.services.deliverable_service import DeliverableService

router = APIRouter(tags=["deliverables"])

# 读取交付物需要的角色 —— 签署流程的各环节都要能看交付物列表与快照。
_READ_ROLES = (
    "DESIGNER",
    "PROCESS_CONTROLLER",
    "REVIEWER",
    "APPROVER",
    "SYSTEM_ADMIN",
)


async def _authorize(
    db: AsyncSession, actor: _Actor, deliverable_id: uuid.UUID
) -> None:
    """按交付物所属项目做访问权校验（无权 404）。"""
    deliverable = await DeliverableService.get_or_404(
        db, deliverable_id=deliverable_id
    )
    await check_project_access_or_404(
        db,
        user_id=actor.user_id,
        project_id=deliverable.project_id,
        actor_roles=actor.roles,
    )


@router.get(
    "/deliverables",
    response_model=DeliverableListResponse,
    summary="列项目下交付物",
)
async def list_deliverables(
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
    project_id: uuid.UUID = Query(..., description="项目 UUID"),
    deliverable_type: str | None = Query(
        None, description="按类型过滤，如 CHANGE_NOTICE；不传则含全部"
    ),
    sign_status: str | None = Query(None, description="按签署状态过滤"),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DeliverableListResponse:
    """列项目下的交付物。

    报表生成中心要按类型分组（计算书/数据表/委托条件表），
    故提供 `deliverable_type` 过滤。
    """
    require_roles(actor, *_READ_ROLES)
    await check_project_access_or_404(
        db, user_id=actor.user_id, project_id=project_id, actor_roles=actor.roles
    )
    items, total = await DeliverableService.list_by_project(
        db,
        project_id=project_id,
        deliverable_type=deliverable_type,
        sign_status=sign_status,
        limit=limit,
        offset=offset,
    )
    return DeliverableListResponse(
        items=[DeliverableResponse.model_validate(i) for i in items],
        total=total,
    )


@router.get(
    "/deliverables/{deliverable_id}",
    response_model=DeliverableResponse,
    summary="交付物详情",
)
async def get_deliverable(
    deliverable_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> DeliverableResponse:
    """取单个交付物。"""
    require_roles(actor, *_READ_ROLES)
    await _authorize(db, actor, deliverable_id)
    deliverable = await DeliverableService.get_or_404(
        db, deliverable_id=deliverable_id
    )
    return DeliverableResponse.model_validate(deliverable)


@router.get(
    "/deliverables/{deliverable_id}/versions",
    response_model=list[DeliverableVersionResponse],
    summary="Rev 历史",
)
async def list_deliverable_versions(
    deliverable_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> list[DeliverableVersionResponse]:
    """交付物的 Rev 列表，当前 Rev 在最前。

    Rev 元信息不含记录绑定明细 —— 那是 snapshot 端点的职责，避免列表响应过大。
    """
    require_roles(actor, *_READ_ROLES)
    await _authorize(db, actor, deliverable_id)
    versions = await DeliverableService.list_versions(
        db, deliverable_id=deliverable_id
    )
    return [DeliverableVersionResponse.model_validate(v) for v in versions]


@router.get(
    "/deliverables/{deliverable_id}/versions/{rev}/snapshot",
    response_model=DeliverableSnapshotResponse,
    summary="某 Rev 的快照（含记录绑定明细）",
)
async def get_deliverable_snapshot(
    deliverable_id: uuid.UUID,
    rev: str,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> DeliverableSnapshotResponse:
    """取某 Rev 的完整快照。

    报表的二维码溯源与「哪些记录在这版被锁定」都从这里取 ——
    `record_snapshot_json` 是记录ID+哈希汇总，`bindings` 是逐条明细。
    """
    require_roles(actor, *_READ_ROLES)
    await _authorize(db, actor, deliverable_id)
    data = await DeliverableService.get_snapshot(
        db, deliverable_id=deliverable_id, rev=rev
    )
    deliverable = data["deliverable"]
    version = data["version"]
    return DeliverableSnapshotResponse(
        deliverable_id=deliverable.deliverable_id,
        rev=version.rev,
        version_purpose=version.version_purpose,
        description=version.description,
        doc_no=deliverable.doc_no,
        sign_status=str(deliverable.sign_status),
        record_snapshot_json=version.record_snapshot_json or {},
        signature_summary_json=version.signature_summary_json or {},
        bindings=[
            RecordBindingResponse.model_validate(b) for b in data["bindings"]
        ],
    )