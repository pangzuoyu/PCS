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

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_record_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError
from app.db.session import get_db
from app.models.enums import StateTransition
from app.schemas.records_actions import (
    ObsoleteRequest,
    RecordActionResponse,
    RequestReversalRequest,
    ReversalDecisionRequest,
)
from app.services.calc_lineage import RECORD_TYPE_REGISTRY
from app.services.record_cancellation_service import RecordCancellationService
from app.services.reversal_approval_service import ReversalApprovalService
from app.services.state_machine import TRANSITION_ROLES

router = APIRouter(tags=["records"])


def resolve_record_model(module: str) -> type[Any]:
    """`{module}` 路径段 → ORM 模型。注册表外 ⇒ 422 `RECORD_MODULE_UNKNOWN`。

    422 而不是 404：模块名是**请求形状**的一部分（不是资源 id），
    404 会让调用方以为「这个记录不存在」而重试同一个错请求。
    """
    model = RECORD_TYPE_REGISTRY.get(module)
    if model is None:
        raise PcsError(
            code="RECORD_MODULE_UNKNOWN",
            message=(
                f"未知记录类型 {module!r}；"
                f"可用值见 calc_lineage.RECORD_TYPE_REGISTRY（{len(RECORD_TYPE_REGISTRY)} 类）"
            ),
            status=422,
        )
    return model


async def _load_record(
    db: AsyncSession, *, module: str, record_id: uuid.UUID, actor: _Actor
) -> Any:
    """解析模块 → 取行 → 项目鉴权（无权 404）。"""
    model = resolve_record_model(module)
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
    await _load_record(db, module=module, record_id=record_id, actor=actor)
    model = resolve_record_model(module)
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
    await _load_record(db, module=module, record_id=record_id, actor=actor)
    model = resolve_record_model(module)
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
    await _load_record(db, module=module, record_id=record_id, actor=actor)
    model = resolve_record_model(module)
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
