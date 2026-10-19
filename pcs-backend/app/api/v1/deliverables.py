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
from app.models.deliverable import Deliverable
from app.schemas.deliverable import (
    DeliverableListResponse,
    DeliverableResponse,
    DeliverableSnapshotResponse,
    DeliverableVersionResponse,
    RecordBindingResponse,
)
from app.schemas.deliverable_write import (
    DeliverableIssueRequest,
    DeliverableIssueResponse,
    SignStepRequest,
    SignStepResponse,
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

# 签发（issue）需要的角色 —— **只有作者侧能签发**。
# 签发 = 把这一版送进签署矩阵，若审方（REVIEWER/APPROVER）也能签发，
# 就能自己签发自己审，签署矩阵的职责分离形同虚设。
_ISSUE_ROLES = ("DESIGNER", "SYSTEM_ADMIN")


async def _authorize(
    db: AsyncSession, actor: _Actor, deliverable_id: uuid.UUID
) -> Deliverable:
    """按交付物所属项目做访问权校验（无权 404），返回该交付物行。

    返回行而不只是校验：写端点（`issue`）在鉴权后要拿同一行继续用，
    再查一次既多一次查询，又让「鉴权用的行」和「改的行」可能不是同一行。
    """
    deliverable = await DeliverableService.get_or_404(
        db, deliverable_id=deliverable_id
    )
    await check_project_access_or_404(
        db,
        user_id=actor.user_id,
        project_id=deliverable.project_id,
        actor_roles=actor.roles,
    )
    return deliverable


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


@router.post(
    "/deliverables/{deliverable_id}/issue",
    response_model=DeliverableIssueResponse,
    summary="签发交付物版本（送审）",
)
async def issue_deliverable(
    deliverable_id: uuid.UUID,
    body: DeliverableIssueRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> DeliverableIssueResponse:
    """签发一个新版本：建版本行 + 定 doc_no + DRAFT → PENDING。

    只有签发出的版本才能进 sign-step（B2）—— `deliverable_versions` 是签署
    流程唯一的进度载体，草稿态的交付物没有版本行可供推进。

    重复签发同一版本目的返 409（不是静默产生第 2 个版本）：那会让签署矩阵
    的步骤序号对不上，用户看到「已签发」却没有任何一版进入签署。
    """
    require_roles(actor, *_ISSUE_ROLES)
    await _authorize(db, actor, deliverable_id)
    version = await DeliverableService.issue(
        db,
        deliverable_id=deliverable_id,
        version_purpose=body.version_purpose,
        actor_user_id=actor.user_id,
        description=body.description,
    )
    deliverable = await DeliverableService.get_or_404(db, deliverable_id=deliverable_id)
    return DeliverableIssueResponse(
        deliverable_id=deliverable.deliverable_id,
        version_id=version.version_id,
        rev=version.rev,
        doc_no=deliverable.doc_no,
        version_purpose=version.version_purpose,
        sign_status=str(deliverable.sign_status.value),
        issued_at=version.created_at,
    )


@router.post(
    "/deliverables/{deliverable_id}/sign-step",
    response_model=SignStepResponse,
    summary="推进签署矩阵的一步（签 / 退 / 跳）",
)
async def sign_step(
    deliverable_id: uuid.UUID,
    body: SignStepRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> SignStepResponse:
    """按签署矩阵推进一步，并同步写一行观测（ADR-0047 §①）。

    步骤只能顺序推进（越步 409）—— 否则矩阵的职责分离失效。
    `SIGN` / `RETURN` / `SKIP` 三个分支**都要能走通**：只接通 SIGN 的半成品
    会让「退回」永远 500，而退回是签署流程里唯一能纠错的路径。

    观测写入在 service 层而非这里（ADR-0047 §① 🔒）：cron / 事件驱动的调用
    路径完全不过 API 层，写在这一层会让它们在观测层里系统性隐形且不报错。
    """
    require_roles(actor, *_READ_ROLES)
    await _authorize(db, actor, deliverable_id)
    outcome = await DeliverableService.sign_step(
        db,
        deliverable_id=deliverable_id,
        version_id=body.version_id,
        step_index=body.step_index,
        decision=body.decision,
        actor_user_id=actor.user_id,
        actor_role=actor.role,
    )
    return SignStepResponse(
        deliverable_id=outcome.deliverable.deliverable_id,
        version_id=outcome.version.version_id,
        step_index=outcome.step_index,
        step_role=outcome.step_role,
        # 用 `body.decision`（请求侧的 Literal）而不是 `outcome.decision`（service 侧的 str）：
        # service 不该知道 schema 层，响应模型的类型约束在请求侧已经保证了取值合法。
        decision=body.decision,
        state=outcome.state.value,
        deliverable_sign_status=outcome.deliverable.sign_status.value,
        signed_at=outcome.signed_at,
    )