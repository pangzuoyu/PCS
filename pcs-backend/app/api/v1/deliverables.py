"""交付物读端点（P1-7+ D 模块 / P8 前置 / P9A B4d 动作时间线）。

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

import json
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
from app.schemas.deliverable_actions import (
    DeliverableActionResponse,
    DeliverableActionsListResponse,
)
from app.schemas.deliverable_write import (
    CustomerApprovalProxyRequest,
    CustomerApprovalProxyResponse,
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

# 签署步骤的角色闸 = 读角色 + CHECKER。CHECKER 必须单列：它是 9 态机里唯一的
# 「校核人」角色，而校核正是签署矩阵里的常见一步；漏了它，矩阵配 CHECKER 的
# 项目**谁都签不了**。每一步到底该谁签由 service 按 `steps_json.sign_role` 判定。
_SIGN_ROLES = (*_READ_ROLES, "CHECKER")


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
    require_roles(actor, *_SIGN_ROLES)
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


@router.post(
    "/deliverables/{deliverable_id}/customer-approval/proxy",
    response_model=CustomerApprovalProxyResponse,
    summary="代录客户批准（凭证 + 二次认证）",
)
async def proxy_customer_approval(
    deliverable_id: uuid.UUID,
    body: CustomerApprovalProxyRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> CustomerApprovalProxyResponse:
    """代录客户在系统外的批准，闭合 CUSTOMER 签署步骤（ADR-0007）。

    客户不会有公司 AD 账号，这一步物理上无人能在系统内执行，代录是唯一闭环。

    两条前置由 service 层强制（顺序不可交换）：
    ① **代录人不得是该交付物的设计人**（403）；
    ② **代录人二次认证**（401，MFA 决议路径 B：AD 密码二次输入）。

    凭证哈希由服务端从磁盘上的真实文件算，请求里不收哈希 —— 收了就是让
    客户端自证物证，而物证是客户批准唯一的存在性证明。
    """
    require_roles(actor, *_ISSUE_ROLES)
    await _authorize(db, actor, deliverable_id)
    outcome = await DeliverableService.record_customer_approval_proxy(
        db,
        deliverable_id=deliverable_id,
        version_id=body.version_id,
        file_path=body.file_path,
        file_name=body.file_name,
        file_type=body.file_type,
        approver_name=body.approver_name,
        approval_date=body.approval_date,
        approval_method=body.approval_method,
        secondary_username=body.secondary_username,
        secondary_password=body.secondary_password,
        actor_user_id=actor.user_id,
    )
    deliverable = outcome.deliverable
    # 响应字段取**请求体**的值而不是回读 ORM：`deliverable.customer_approval_*`
    # 在模型上是可空的，回读就得写 `or ""` 或 type: ignore，两者都会把
    # 「本该必填的代录结果」伪装成可选。落库是否真的成功由
    # `test_records_approval_fields` 单独断言（它 refresh 后回读 DB）。
    return CustomerApprovalProxyResponse(
        deliverable_id=deliverable.deliverable_id,
        version_id=outcome.version.version_id,
        attachment_id=outcome.attachment.attachment_id,
        customer_approver_name=body.approver_name,
        approval_date=body.approval_date,
        approval_method=body.approval_method,
        is_proxy=True,
        proxied_at=outcome.signed_at,
    )

@router.get(
    "/deliverables/{deliverable_id}/actions",
    response_model=DeliverableActionsListResponse,
    summary="交付物动作时间线（数据源 = 审计日志）",
)
async def list_deliverable_actions(
    deliverable_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
    limit: int = Query(200, ge=1, le=500),
    offset: int = Query(0, ge=0),
) -> DeliverableActionsListResponse:
    """列这个交付物上发生过的动作，最早在前。

    数据源是 `audit_logs` 而**不是**新表：动作已经逐条写进审计了
    （签发 / 签署 / 代录批准 / 变更单批准），再建一张表就是**第二份动作历史** ——
    两份会漂移，而漂移的那份没人会去对。

    要并进**版本级**动作：`sign-step` 的审计记的是版本 ID
    （`resource_type=deliverable_version`），只按交付物 ID 查会把签署历史
    整段漏掉 —— 而签署历史恰恰是这个端点的主要用途。

    ⚠️ 与 `workflow_progress` 是**两回事**：这里回答「谁做了什么」，
    观测层回答「流程到哪一步了」。拿 actions 当进度来源，
    甘特图会把「查过一眼」也算成活动。
    """
    require_roles(actor, *_READ_ROLES)
    await _authorize(db, actor, deliverable_id)
    items, total = await DeliverableService.list_actions(
        db, deliverable_id=deliverable_id, limit=limit, offset=offset
    )
    return DeliverableActionsListResponse(
        deliverable_id=deliverable_id,
        items=[
            DeliverableActionResponse(
                action=i.action,
                resource_type=i.resource_type,
                resource_id=i.resource_id,
                actor_user_id=i.actor_user_id,
                # detail_json 是 dict → 序列化成 JSON 文本再暴露。
                # 铺平成 dict 会让 OpenAPI 多一个无属性 object（P9A-DLV-010 的
                # 裸字段，基线 71 只拦倒退），也会把「结构随 action 变」
                # 变成前端要自己猜的第二个真相源。
                detail_json=json.dumps(i.detail, ensure_ascii=False)
                if i.detail is not None
                else None,
                created_at=i.created_at,
            )
            for i in items
        ],
        total=total,
    )
