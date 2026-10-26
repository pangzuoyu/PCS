"""records 写端点（P9A B4）—— `/records/{module}/{id}/<action>`。

## 为什么新建文件而不是往 `records.py` 里加

`records.py` 的 6 个既有端点全是 **piping 专用**（`/piping/{pipe_id}/...`，
硬编码 `PipingResult`），而本 SPEC 的端点是 `/records/{module}/{id}/...`
**按模块参数化**（16+ 张结果表）。把新端点塞进去会让一个文件同时装
「piping 专用 + 模块参数化」两套形状，且那 6 个 `response_model=dict`
是 TODO-039/041 的既有债 —— 新代码贴着它放，容易被读成「这里也不保证零裸字段」。

## `{module}` 的唯一真值源

`calc_lineage.RECORD_TYPE_REGISTRY` 的键。**不另起注册表** —— 第二份
「模块 → 模型」映射就是第二个真相源，而它会与第一份漂移（本仓已吃过这类亏）。
⚠️ 该注册表的键风格不统一（`PipingResult` / `cv_result`）；不统一本身登记在
`TODOS.md`，但**不改** —— 改键名会让既有调用方（`finalize_calc_record` 等）一起断。

## 角色集从哪来

三个被接线的 service **都不做角色校验**（注释自陈「角色校验交给签名矩阵层」）。
既然不走签名矩阵，端点层就必须补，补的依据用 `state_machine.TRANSITION_ROLES`
—— 仓库里已有的、同一套状态机事件的角色词表，而不是另发明一套 ACL。
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import (
    check_record_access_or_404,
    require_formal_project_workspace,
)
from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError
from app.db.session import get_db
from app.models.enums import (
    AuditAction,
    RecordSignStatus9,
    StateTransition,
    to_value,
)
from app.models.record_comment import RecordComment
from app.schemas.records_actions import (
    ApprovalStepRequest,
    ApprovalStepResponse,
    ChangeActionRequest,
    ChangeNoticeCancelResponse,
    ChangeNoticeDetailResponse,
    ChangeNoticeRequest,
    ChangeNoticeResponse,
    CommentCreateRequest,
    CommentListResponse,
    CommentResponse,
    ObsoleteRequest,
    RecordActionResponse,
    RequestReversalRequest,
    ReversalDecisionRequest,
    SubmitApprovalRequest,
    SubmitApprovalResponse,
)
from app.services.audit_service import AuditService
from app.services.calc_lineage import RECORD_TYPE_REGISTRY
from app.services.change_notice_service import ChangeNoticeService
from app.services.record_cancellation_service import RecordCancellationService
from app.services.record_capabilities import (
    WORKFLOW_UNSUPPORTED,
    missing_workflow_columns,
    supports_state_workflow,
)
from app.services.reversal_approval_service import ReversalApprovalService
from app.services.state_machine import (
    TRANSITION_ROLES,
    InvalidTransition,
    NoModification,
    RoleForbidden,
    StateMachineService,
)

router = APIRouter(tags=["records"])

# 批注参与的角色 = 读记录的全部角色。批注是**任何能看这条记录的人**都能留的
# （评审、设计、专业负责人都会留意见），收窄到作者侧会让「发现问题却不能说」
# 变成绕过系统的私下沟通 —— 那正好是批注要解决的事。
_COMMENT_ROLES = ("DESIGNER", "PROCESS_CONTROLLER", "REVIEWER", "APPROVER", "SYSTEM_ADMIN")


def resolve_record_model(module: str, *, need_mixin: bool = True) -> type[Any]:
    """`{module}` 路径段 → ORM 模型。

    两道检查，缺一不可：

    1. **在不在注册表里** —— 不在 ⇒ 422 `RECORD_MODULE_UNKNOWN`。
       422 而不是 404：模块名是**请求形状**的一部分（不是资源 id），
       404 会让调用方以为「这个记录不存在」而重试同一个错请求。
    2. **列够不够** —— `RECORD_TYPE_REGISTRY` 混着几张**列不齐**的表
       （`CostEstResult` / `TwoPhaseResult` 连 `project_id` 都没有，
       `ProjectCalculationStandardProfile` 没有 `sign_status`）。
       只做第 1 道检查的话，它们会一路走到守卫再抛
       500「Record missing project_id (guard misconfigured)」——
       把开发者字符串端给用户，且不告诉他真正该说的话：
       「这种记录不参与 9 态工作流」。
       ⇒ 422 `RECORD_MODULE_UNSUPPORTED`，**并在报文里点名缺哪些列**。

    Args:
        need_mixin: True = 该端点建立在 9 态记录上（obsolete / 撤销 /
            放弃变更 / 送审 / 批步骤）；False = 只需要 `project_id`
            （批注：任何有归属项目的记录都能留言）。
    """
    model: Any = RECORD_TYPE_REGISTRY.get(module)
    if model is None:
        raise PcsError(
            code="RECORD_MODULE_UNKNOWN",
            message=(
                f"未知记录类型 {module!r}；"
                f"可用值见 calc_lineage.RECORD_TYPE_REGISTRY（{len(RECORD_TYPE_REGISTRY)} 类）"
            ),
            status=422,
        )
    if not supports_state_workflow(model, need_workflow=need_mixin):
        missing = missing_workflow_columns(model) or ["project_id"]
        hint = WORKFLOW_UNSUPPORTED.get(module)
        raise PcsError(
            code="RECORD_MODULE_UNSUPPORTED",
            message=(
                f"记录类型 {module!r} 不参与 9 态工作流"
                f"（缺列：{', '.join(missing)}）"
                + (f"；{hint}" if hint else "")
            ),
            status=422,
        )
    return model


async def _load_record(
    db: AsyncSession,
    *,
    module: str,
    record_id: uuid.UUID,
    actor: _Actor,
    need_mixin: bool = True,
) -> Any:
    """解析模块 → 取行 → 项目鉴权（无权 404）。"""
    model = resolve_record_model(module, need_mixin=need_mixin)
    record = await db.get(model, record_id)
    if record is None:
        raise PcsError(
            code="RECORD_NOT_FOUND",
            message=f"{module} 记录 {record_id} 不存在",
            status=404,
        )
    await check_record_access_or_404(
        db, user_id=actor.user_id, record=record, actor_roles=actor.roles
    )
    return record


def _roles_for(*transitions: StateTransition) -> tuple[str, ...]:
    """按状态机事件表取角色并集（service 层不校验，端点层必须补）。"""
    allowed: set[str] = set()
    for transition in transitions:
        allowed |= TRANSITION_ROLES[transition]
    return tuple(sorted(allowed))


async def _transition(
    db: AsyncSession,
    *,
    record: Any,
    transition: StateTransition,
    actor: _Actor,
    reason: str = "",
) -> None:
    """走 9 态状态机并把它的两个异常映射成 HTTP 语义。

    `RoleForbidden` → 403（角色不够）、`InvalidTransition` → 409（状态不对）。
    不映射的话它们会落到 FastAPI 的 500 兜底 —— 而「状态不对」是用户
    按错按钮的正常结果，不是系统故障；返回 500 会让前端弹「系统错误」
    而不是「这一步现在不能批」。
    """
    try:
        await StateMachineService(db).transition(
            record=record,
            transition=transition,
            actor_user_id=actor.user_id,
            actor_role=actor.role,
            reason=reason or None,
        )
    except RoleForbidden as e:
        raise PcsError(
            code="RECORD_ROLE_FORBIDDEN",
            message=f"角色 {actor.role} 不能执行 {transition.value}",
            status=403,
        ) from e
    except NoModification as e:
        # ⚠️ 「提交变更完成」但**什么都没改**（TODO-077）⇒ 409。
        # 不映射的话会落到 500 兜底 —— 而这是用户「忘了改数据」或「改完又改回去」
        # 的**正常结果**，不是系统故障（该做的是「放弃变更」，不是重试）。
        raise PcsError(
            code="CHANGE_NO_MODIFICATION",
            message=(
                f"记录自发起变更以来没有任何修改（哈希仍是 {e.baseline_hash}）"
                f"⇒ 不能提交变更完成；若确实无需修改，请改用「放弃变更」"
            ),
            status=409,
        ) from e
    except InvalidTransition as e:
        raise PcsError(
            code="RECORD_INVALID_TRANSITION",
            message=f"{e.from_status} 不能执行 {e.transition}",
            status=409,
        ) from e


def _response(module: str, record_id: uuid.UUID, result: dict[str, Any]) -> RecordActionResponse:
    return RecordActionResponse(
        record_type=module,
        record_id=record_id,
        from_status=str(result.get("from", "")),
        to_status=str(result.get("to", "")),
    )


@router.post(
    "/records/{module}/{record_id}/obsolete",
    response_model=RecordActionResponse,
    summary="弃用记录（已绑定者须走变更单）",
)
async def obsolete_record(
    module: str,
    record_id: uuid.UUID,
    body: ObsoleteRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> RecordActionResponse:
    """直接弃用记录（ADR-0009：未绑定免凭证 OBSOLETE）。

    已绑定记录（`locked_by_deliverable=True`）返 409 —— 它必须走
    `change_type=RECORD_CANCELLATION` 的变更单（ADR-0002）。
    弃用是状态迁移**不是删除**：行还在，只有 sign_status 变了 ——
    「这行曾经存在过、什么时候被谁作废的」要能查。
    """
    require_roles(actor, *_roles_for(StateTransition.OBSOLETE))
    model = resolve_record_model(module)
    await _load_record(db, module=module, record_id=record_id, actor=actor)
    result = await RecordCancellationService.obsolete(
        db,
        record_id=record_id,
        actor=actor,
        reason=body.reason,
        record_table=model,
    )
    await db.commit()
    return _response(module, record_id, result)


@router.post(
    "/records/{module}/{record_id}/request-reversal",
    response_model=RecordActionResponse,
    summary="发起撤销申请（CHANGED → REVERSAL_PENDING）",
)
async def request_reversal(
    module: str,
    record_id: uuid.UUID,
    body: RequestReversalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> RecordActionResponse:
    """发起撤销（ADR-0002：仅 CHANGED 且未锁定可发起）。

    已对外生效（锁定）的记录只能走变更单，不能走撤销。
    """
    require_roles(actor, *_roles_for(StateTransition.REQUEST_REVERSAL))
    model = resolve_record_model(module)
    await _load_record(db, module=module, record_id=record_id, actor=actor)
    result = await ReversalApprovalService.request_reversal(
        db,
        record_id=record_id,
        actor=actor,
        reason=body.reason,
        record_table=model,
    )
    await db.commit()
    return _response(module, record_id, result)


@router.post(
    "/records/{module}/{record_id}/reversal-decision",
    response_model=RecordActionResponse,
    summary="撤销裁决（批准 → CHECKED / 拒绝 → 维持 CHANGED）",
)
async def reversal_decision(
    module: str,
    record_id: uuid.UUID,
    body: ReversalDecisionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> RecordActionResponse:
    """批准或拒绝撤销申请（ADR-0010）。

    两个分支都实现：只接通 approve 的半成品会让「拒绝撤销」永远 500，
    记录卡在 REVERSAL_PENDING 谁也动不了，而用户只看到「按了拒绝，什么都没发生」。
    """
    require_roles(
        actor,
        *_roles_for(StateTransition.APPROVE_REVERSAL, StateTransition.REJECT_REVERSAL),
    )
    model = resolve_record_model(module)
    await _load_record(db, module=module, record_id=record_id, actor=actor)
    if body.decision == "APPROVE":
        result = await ReversalApprovalService.approve_reversal(
            db, record_id=record_id, actor=actor, record_table=model
        )
    else:
        result = await ReversalApprovalService.reject_reversal(
            db,
            record_id=record_id,
            actor=actor,
            reason=body.reason,
            record_table=model,
        )
    await db.commit()
    return _response(module, record_id, result)


@router.post(
    "/records/{module}/{record_id}/submit-approval",
    response_model=SubmitApprovalResponse,
    summary="提交送审（DRAFT / CHECK_REJECTED → IN_APPROVAL）",
)
async def submit_approval(
    module: str,
    record_id: uuid.UUID,
    body: SubmitApprovalRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> SubmitApprovalResponse:
    """提交记录进入审批（DRAFT / CHECK_REJECTED → IN_APPROVAL）。

    `approval_role` 由请求给出且**必须不等于提交人自己的角色**：`can_self_check`
    在记录侧没有配置源，本轮取其**最强形式**（恒不允许自审）—— 宽松形式
    （只在配置说 false 时才拒）在没有配置源时等于没有防护。

    `approval_depth` 缺省 1。⚠️ 多级批准的**角色链**在本仓没有定义来源，
    见 `records_actions.py` 顶注与 `TODOS.md`；本轮不发明角色链。
    """
    require_roles(actor, *_roles_for(StateTransition.SUBMIT_FOR_CHECK))
    record = await _load_record(db, module=module, record_id=record_id, actor=actor)
    if body.approval_role == actor.role:
        raise PcsError(
            code="APPROVAL_SELF_REVIEW_FORBIDDEN",
            message=(
                f"待批角色不能是提交人自己的角色（{body.approval_role}）："
                "记录侧没有 can_self_check 配置源，本端点一律不允许自审"
            ),
            status=403,
        )
    from_status = record.sign_status
    record.approval_role = body.approval_role
    record.approval_depth = body.approval_depth
    record.approval_step = 1
    await _transition(
        db, record=record, transition=StateTransition.SUBMIT_FOR_CHECK, actor=actor
    )
    await db.commit()
    return SubmitApprovalResponse(
        record_type=module,
        record_id=record_id,
        from_status=to_value(from_status),
        to_status=to_value(record.sign_status),
        approval_step=record.approval_step or 1,
        approval_depth=record.approval_depth,
        approval_role=record.approval_role or "",
    )


@router.post(
    "/records/{module}/{record_id}/approval-step",
    response_model=ApprovalStepResponse,
    summary="推进/退回当前批准步骤",
)
async def approval_step(
    module: str,
    record_id: uuid.UUID,
    body: ApprovalStepRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> ApprovalStepResponse:
    """批当前这一步。

    深度耗尽（`approval_step >= approval_depth`）时走 `PASS_CHECK` → CHECKED，
    再往后批 409 —— 不静默继续，因为「第 4 级」在本仓没有依据。

    只有记录上的 `approval_role` 那个角色能批：矩阵把待批角色写进行里就是为了
    这个，不校验等于那列是装饰。
    """
    require_roles(actor, *_roles_for(StateTransition.PASS_CHECK))
    record = await _load_record(db, module=module, record_id=record_id, actor=actor)
    if to_value(record.sign_status) != RecordSignStatus9.IN_APPROVAL.value:
        raise PcsError(
            code="APPROVAL_NOT_ACTIVE",
            message=(
                f"记录当前 {record.sign_status}，不在审批中"
                f"（只有 IN_APPROVAL 能批；DRAFT 请先 submit-approval）"
            ),
            status=409,
        )
    if record.approval_role and record.approval_role != actor.role:
        raise PcsError(
            code="APPROVAL_ROLE_MISMATCH",
            message=f"待批角色是 {record.approval_role}，当前角色 {actor.role}",
            status=403,
        )

    from_status = record.sign_status
    current_step = record.approval_step or 1
    depth = record.approval_depth or 1

    if body.decision == "REJECT":
        await _transition(
            db, record=record, transition=StateTransition.REJECT_CHECK,
            actor=actor, reason=body.reason,
        )
        final_step = current_step
    elif current_step >= depth:
        # 深度耗尽 ⇒ 整条记录 CHECKED。**先记 step 再转移**：
        # PASS_CHECK 会把 approval_step 清空，事后取就是 None，进度条会少一格。
        final_step = depth
        await _transition(
            db, record=record, transition=StateTransition.PASS_CHECK,
            actor=actor, reason=body.reason,
        )
    else:
        # 中间步骤：只推进计数器，不改 sign_status（仍是 IN_APPROVAL）。
        # 这里**不发状态机事件** —— 9 态里没有「审批中→审批中」这个转移，
        # 硬造一个会让 ALLOWED_TRANSITIONS 出现自环。审计另写一条。
        final_step = current_step + 1
        record.approval_step = final_step
        await db.flush()
        # 中间步骤不发状态机事件，但**必须留痕**：记录表上没有「第几步谁批的」列，
        # 审计是唯一去处。漏了它，深度 > 1 时中间批准人彻底无从追溯。
        await AuditService(db).write(
            action=AuditAction.APPROVAL_STEP_PASSED,
            resource_type="record",
            resource_id=record_id,
            user_id=actor.user_id,
            detail={
                "module": module,
                "approval_step": final_step,
                "approval_depth": depth,
                "role": actor.role,
            },
        )

    await db.commit()
    return ApprovalStepResponse(
        record_type=module,
        record_id=record_id,
        from_status=to_value(from_status),
        to_status=to_value(record.sign_status),
        approval_step=final_step,
        approval_depth=depth,
    )


@router.post(
    "/records/{module}/{record_id}/abandon-change",
    response_model=RecordActionResponse,
    summary="放弃变更（CHANGE_PENDING → CHECKED，恢复快照）",
)
async def abandon_change(
    module: str,
    record_id: uuid.UUID,
    body: ChangeActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> RecordActionResponse:
    """放弃一条待生效的变更。

    ⚠️ **不接线** `change_notice_service.approve_change_notice` —— 那个方法做的是
    「变更单 PENDING → APPROVED（批准、变更生效）」，与「放弃」**方向相反**，
    作用对象也不同（交付物 vs 记录）。接线会让用户点「放弃」而系统把变更批准。
    判定过程见 `docs/PCS-PLAN-P9A-2-交付物写面.md` B4 Step 0 与 B4a 的 commit。

    本端点转发既有状态机事件 `ABANDON_CHANGE`：CHANGE_PENDING → CHECKED +
    恢复最新 ACTIVE 快照（`SNAPSHOT_RESTORERS`）+ 写 `change_abandoned_at/reason`
    + 审计 `CHANGE_ABANDONED`。
    """
    require_roles(actor, *_roles_for(StateTransition.ABANDON_CHANGE))
    record = await _load_record(db, module=module, record_id=record_id, actor=actor)
    from_status = record.sign_status
    await _transition(
        db, record=record, transition=StateTransition.ABANDON_CHANGE,
        actor=actor, reason=body.reason,
    )
    await db.commit()
    return _response(
        module, record_id, {"from": to_value(from_status), "to": to_value(record.sign_status)}
    )


# ---------------------------------------------------------------------------
# 批注（SPEC §2.2.3 的 comments 端点）
# ---------------------------------------------------------------------------


@router.post(
    "/records/{module}/{record_id}/comments",
    response_model=CommentResponse,
    summary="新增记录批注",
)
async def create_comment(
    module: str,
    record_id: uuid.UUID,
    body: CommentCreateRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> CommentResponse:
    """给记录留一条批注。

    ⚠️ **不写** `workflow_progress`（ADR-0047 §①）：观测层记的是流程进度，
    「有人留言」不是流程活动。把它算进去会让甘特图上的活动看起来比实际多，
    而观测层一旦不可信就没人再信它 —— 那正是 ADR-0047 立观测层要防的失败。
    """
    require_roles(actor, *_COMMENT_ROLES)
    # 批注**不需要** 9 态列：任何有归属项目的记录都能留言。
    # need_mixin=False 让「没有 sign_status 的表」也能被留言，而不是被 422 挡掉。
    record = await _load_record(
        db, module=module, record_id=record_id, actor=actor, need_mixin=False
    )
    comment = RecordComment(
        project_id=record.project_id,
        record_type=module,
        record_id=record_id,
        body=body.body.strip(),
        author_id=actor.user_id,
        created_by=actor.user_id,
    )
    db.add(comment)
    await db.commit()
    await db.refresh(comment)
    return CommentResponse.model_validate(comment)


@router.get(
    "/records/{module}/{record_id}/comments",
    response_model=CommentListResponse,
    summary="列记录批注（按时间正序，分页）",
)
async def list_comments(
    module: str,
    record_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> CommentListResponse:
    """列一条记录的批注，最早在前。

    ⚠️ 排序必须带 `comment_id` 作 tiebreaker：`created_at` 是 `server_default=func.now()`，
    SQLite 下 CURRENT_TIMESTAMP 只有**秒级**粒度 —— 同一批写入的批注时间戳必然相同，
    只按 created_at 排序时并列行的返回顺序不确定 ⇒ 翻页会漏批注或重复。
    """
    require_roles(actor, *_COMMENT_ROLES)
    record = await _load_record(
        db, module=module, record_id=record_id, actor=actor, need_mixin=False
    )
    conditions = [
        RecordComment.record_type == module,
        RecordComment.record_id == record_id,
        # 项目隔离：即使 (record_type, record_id) 撞了，不属于本项目的批注也不出。
        RecordComment.project_id == record.project_id,
    ]
    total = await db.scalar(
        select(func.count()).select_from(RecordComment).where(*conditions)
    )
    rows = (
        await db.execute(
            select(RecordComment)
            .where(*conditions)
            .order_by(RecordComment.created_at, RecordComment.comment_id)
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return CommentListResponse(
        items=[CommentResponse.model_validate(r) for r in rows],
        total=int(total or 0),
    )


# ---------------------------------------------------------------------------
# 变更单闭环（TODO-068 · P9A-DLV-011 T4 · ADR-0002 / ADR-0008）
#
# 完整链路（ADR-0002 的 CHANGED 生命周期）：
#
#   CHECKED
#     --initiate-change-->  CHANGE_PENDING   （获准修改，正在改 + 重校核）
#     --apply-change-->    CHANGED           （校核完成，等待关闭）
#     --change-notice-->   变更单（3 级矩阵签署中）
#     --签完最后一步-->     记录自动回 CHECKED（change_resolved_by = 签完的人）
#
# ⚠️ **发起变更 / 提交变更完成两个端点此前完全不存在** ⇒ 记录永远到不了
# CHANGED ⇒ 变更单的建单端点即使写出来也不可达（`create_change_notice`
# 要求记录是 CHANGED）。
# ---------------------------------------------------------------------------


@router.post(
    "/records/{module}/{record_id}/initiate-change",
    response_model=RecordActionResponse,
    summary="发起变更（CHECKED → CHANGE_PENDING）",
)
async def initiate_change(
    module: str,
    record_id: uuid.UUID,
    body: ChangeActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> RecordActionResponse:
    """发起一条待生效的变更（ADR-0002：CHECKED → CHANGE_PENDING）。

    触发时状态机自动写 **BEFORE_CHANGE 快照**（变更前的数据 + 哈希）
    ⇒ 变更单建单时能把「变更前哈希」写进 `deliverable_record_bindings`
    ⇒ 新旧哈希可比对（ADR-0008）。
    """
    require_roles(actor, *_roles_for(StateTransition.INITIATE_CHANGE))
    record = await _load_record(db, module=module, record_id=record_id, actor=actor)
    from_status = record.sign_status
    await _transition(
        db,
        record=record,
        transition=StateTransition.INITIATE_CHANGE,
        actor=actor,
        reason=body.reason,
    )
    await db.commit()
    return _response(
        module,
        record_id,
        {"from": to_value(from_status), "to": to_value(record.sign_status)},
    )


@router.post(
    "/records/{module}/{record_id}/apply-change",
    response_model=RecordActionResponse,
    summary="提交变更完成（CHANGE_PENDING → CHANGED，等待变更单关闭）",
)
async def apply_change(
    module: str,
    record_id: uuid.UUID,
    body: ChangeActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> RecordActionResponse:
    """变更改完了、重校核过了 ⇒ 进入 CHANGED（等待变更单关闭它）。

    ADR-0002：CHANGED = 「校核完成、等待关闭」⇒ 关闭凭证是**变更单**
    （不是新版交付物）⇒ 记录要到变更单被签完才回 CHECKED。
    """
    require_roles(actor, *_roles_for(StateTransition.APPLY_CHANGE))
    record = await _load_record(db, module=module, record_id=record_id, actor=actor)
    from_status = record.sign_status
    await _transition(
        db,
        record=record,
        transition=StateTransition.APPLY_CHANGE,
        actor=actor,
        reason=body.reason,
    )
    # ⚠️ **刷新未关闭变更单的绑定哈希**（TODO-086）：记录在 CHANGE_PENDING 期间
    #    可能又被改过 ⇒ 变更单建单时记的哈希**不再**是被关那条数据的哈希
    #    ⇒ 关闭凭证会说错对象。与状态迁移**同一事务**（commit 在下面）。
    await ChangeNoticeService.refresh_open_bindings(
        db,
        record_type=type(record).__name__,
        record_id=record_id,
        record_hash=record.record_hash or "",
        actor_user_id=actor.user_id,
    )
    await db.commit()
    return _response(
        module,
        record_id,
        {"from": to_value(from_status), "to": to_value(record.sign_status)},
    )


@router.post(
    "/records/{module}/{record_id}/change-notice/cancel",
    response_model=ChangeNoticeCancelResponse,
    summary="作废该记录开着的变更单（记录本身不动）",
)
async def cancel_change_notice(
    module: str,
    record_id: uuid.UUID,
    body: ChangeActionRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> ChangeNoticeCancelResponse:
    """作废当前**开着**的那张变更单（TODO-069 第 2 条 / TODO-080 第 1 条）。

    ⚠️ **作废的是「单据」，不是「校核结论」** ⇒ **记录不动**（保持 CHANGED）：
    作废顺手把记录关成 CHECKED = **绕过 3 级校审** ⇒ 不做。
    ⇒ 作废后该记录**可以另起一张**变更单（作废的单不挡新单）。
    """
    require_roles(actor, *_roles_for(StateTransition.INITIATE_CHANGE))
    record = await _load_record(db, module=module, record_id=record_id, actor=actor)

    from app.services.change_notice_service import ChangeNoticeService

    result = await ChangeNoticeService.cancel_change_notice(
        db,
        record_type=type(record).__name__,
        record_id=record_id,
        actor_user_id=actor.user_id,
        reason=body.reason,
    )
    await db.commit()
    return ChangeNoticeCancelResponse(
        deliverable_id=result["deliverable_id"],
        doc_no=result["doc_no"],
        record_type=result["record_type"],
        record_id=result["record_id"],
        sign_status=result["sign_status"],
    )


@router.post(
    "/records/{module}/{record_id}/change-notice",
    response_model=ChangeNoticeResponse,
    summary="发起变更单（记录须为 CHANGED）",
)
async def create_change_notice(
    module: str,
    record_id: uuid.UUID,
    body: ChangeNoticeRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> ChangeNoticeResponse:
    """给一条 CHANGED 的记录发起变更单（ADR-0008）。

    建单 = 交付物（CHANGE_NOTICE）+ **版本行**（ISSUED_FOR_CHANGE）+
    **记录绑定**（`deliverable_record_bindings`）+ 观测行（PENDING），
    **同一事务**。

    之后的 3 级校审走**既有** `POST /deliverables/{id}/sign-step`
    （矩阵 `CHANGE_NOTICE_3_LEVEL`）⇒ 矩阵对变更单**真的生效**；
    最后一步签完 ⇒ 记录自动回 CHECKED。
    """
    require_roles(actor, *_roles_for(StateTransition.INITIATE_CHANGE))
    model = resolve_record_model(module)
    record = await _load_record(db, module=module, record_id=record_id, actor=actor)
    # ⚠️ 工作区门禁（UI-SPEC §5.3）：个人草稿区里的变更单没有工程效力。
    await require_formal_project_workspace(db, project_id=record.project_id)

    from app.services.change_notice_service import (
        ChangeType,
        TriggeredBy,
    )

    result = await ChangeNoticeService.create_change_notice(
        db,
        project_id=record.project_id,
        record_id=record_id,
        change_type=ChangeType(body.change_type),
        reason=body.reason,
        triggered_by=TriggeredBy(body.triggered_by),
        actor=actor,
        record_table=model,
        # ⚠️ **多记录变更**（TODO-078）：请求体可带本次变更影响的全部记录
        #    （必须包含路径里那条）⇒ binding 写多行 ⇒ 签完**批量**关。
        record_ids=body.record_ids,
    )
    detail = result["detail"]
    return ChangeNoticeResponse(
        deliverable_id=result["deliverable_id"],
        version_id=result["version_id"],
        workflow_id=result["workflow_id"],
        matrix_id=result["matrix_id"],
        project_id=result["project_id"],
        doc_no=result["doc_no"],
        title=result["title"],
        # ⚠️ **行里的真值**（service 从交付物行读出来），不是常量
        sign_status=result["sign_status"],
        detail=ChangeNoticeDetailResponse(
            detail_id=detail["detail_id"],
            change_type=detail["change_type"],
            reason=detail["reason"],
            triggered_by=detail["triggered_by"],
            source_record_type=detail["source_record_type"],
        ),
    )
