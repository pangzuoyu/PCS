"""观测层读 API（P9A B5 / SPEC P9A-OBS-003）。

`GET /api/v1/workflow-progress/{workflow_type}/{workflow_id}` —— P9B 甘特图、
进度条、超时告警的唯一数据源。

写入面**不在这里**：ADR-0047 §① 🔒 要求观测写入必须在 service 层且经
`workflow_progress_writer.record_step` 这一个入口，写在路由里会让
ARQ cron 驱动的状态变更（`cia_mark_stale`）在观测层里系统性隐形且不报错。
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError
from app.db.session import get_db
from app.models.enums import WorkflowProgressState
from app.schemas.workflow_progress import (
    WorkflowProgressItemResponse,
    WorkflowProgressResponse,
)
from app.services.workflow_progress_service import (
    WorkflowProgressService,
    parse_workflow_type,
)

router = APIRouter(tags=["workflow-progress"])

# 计数键取自枚举本身，不写字面量字符串 —— 枚举加成员时这里会立刻红，
# 而写死字符串的话新成员会静默地在响应里缺席（甘特图少一种颜色，且没人知道）。
_PENDING = WorkflowProgressState.PENDING
_IN_PROGRESS = WorkflowProgressState.IN_PROGRESS
_COMPLETED = WorkflowProgressState.COMPLETED
_SKIPPED = WorkflowProgressState.SKIPPED
_FAILED = WorkflowProgressState.FAILED

# 与交付物读面同源：能看交付物/记录的人才能看流程进度。
_READ_ROLES = (
    "DESIGNER",
    "PROCESS_CONTROLLER",
    "REVIEWER",
    "APPROVER",
    "SYSTEM_ADMIN",
)


@router.get(
    "/workflow-progress/{workflow_type}/{workflow_id}",
    response_model=WorkflowProgressResponse,
    summary="工作流节点进度（甘特图数据源）",
)
async def get_workflow_progress(
    workflow_type: str,
    workflow_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    actor: Annotated[_Actor, Depends(current_actor)],
) -> WorkflowProgressResponse:
    """取一条工作流的节点进度，按 `step_order` 升序。

    未知工作流 ⇒ **404**，不是空数组 —— 空数组会被甘特图画成「这条流程
    一个节点都没有」，而真相是「你查错了 ID」，两者在界面上长得一样。

    5 态计数恒定存在（含 0）：甘特图按 5 态上色，缺一态前端要么画不出颜色、
    要么自己编一个，后者就是第二次真相源。
    """
    require_roles(actor, *_READ_ROLES)
    wf_type = parse_workflow_type(workflow_type)

    data = await WorkflowProgressService.get(
        db, workflow_type=wf_type, workflow_id=workflow_id
    )
    await check_project_access_or_404(
        db,
        user_id=actor.user_id,
        project_id=data["project_id"],
        actor_roles=actor.roles,
    )
    # 观测行的 project_id 是授权的唯一依据（workflow_id 多态，join 不回项目）。
    # 与反查出来的宿主项目不一致 ⇒ 当作不存在（不泄漏「存在但无权」）。
    if data["items"]:
        mismatched = [r for r in data["items"] if r.project_id != data["project_id"]]
        if mismatched:
            raise PcsError(
                code="WORKFLOW_NOT_FOUND",
                message=f"{wf_type.value} 工作流 {workflow_id} 不存在",
                status=404,
            )

    counts = data["counts"]
    return WorkflowProgressResponse(
        workflow_type=wf_type.value,
        workflow_id=workflow_id,
        project_id=data["project_id"],
        total=data["total"],
        pending=counts.get(_PENDING, 0),
        in_progress=counts.get(_IN_PROGRESS, 0),
        completed=counts.get(_COMPLETED, 0),
        skipped=counts.get(_SKIPPED, 0),
        failed=counts.get(_FAILED, 0),
        items=[WorkflowProgressItemResponse.model_validate(r) for r in data["items"]],
    )
