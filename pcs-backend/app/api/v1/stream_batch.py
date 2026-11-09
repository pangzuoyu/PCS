"""批量「提交校对」的端点（P9B-3b）。

⚠️ **路径为什么是 `/streams/batch-submit`**（用户 2026-11-03 裁决）：本路径
**两段**，与三段的 `POST /streams/{stream_id}/submit` **不可能抢路由** ⇒
不需要任何路由顺序技巧。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.db.session import get_db
from app.schemas.stream_batch import (
    StreamBatchSubmitRequest,
    StreamBatchSubmitResponse,
)
from app.services.stream_batch_service import submit_batch

router = APIRouter()


@router.post(
    "/streams/batch-submit",
    status_code=207,
    response_model=StreamBatchSubmitResponse,
    summary="批量提交校对（DRAFT → IN_APPROVAL，207 Multi-Status）",
    # ⚠️ **只登记描述、不登记 model**：仓里**没有**通用错误信封 schema
    #    （只有 `ConflictEnvelope`，是 409 专用的）⇒ 登记 model 要新造一个
    #    ⇒ 那是 TODO-096 的活。本端点先用 `description` 把错误码写清楚。
    responses={
        403: {"description": "角色无权（需 DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN）"},
        422: {"description": "超过批次上限 —— SIM_STREAM_BATCH_LIMIT_EXCEEDED"},
    },
)
async def batch_submit_streams(
    req: StreamBatchSubmitRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamBatchSubmitResponse:
    """批量提交校对。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（与单条端点同口径）。

    ⚠️ **207 Multi-Status**：一条失败**不回滚**其它条 ⇒ 成功与失败**分两张清单**
    返回（`succeeded` / `failed`）。⚠️ 207 是 **2xx** ⇒ 客户端**不会**自动
    抛异常 ⇒ 必须自己看 `failed`。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLOR", "SYSTEM_ADMIN")

    # ⚠️ service 抛的 `PcsError`（如超限 422）**不用**在这里转 —— 全局
    # handler（`app/core/errors.py::install_exception_handlers`）已经把它
    # 渲染成统一信封 `{code, message, detail, trace_id}` ⇒ 在这里 try/except
    # 再 raise 只是把同一个异常抛两遍。
    return await submit_batch(
        db,
        req.stream_ids,
        actor_user_id=user.user_id,
        actor_role=user.role,
        # ⚠️ `actor_roles` 是项目守卫的 SYSTEM_ADMIN bypass（与单条端点同口径）
        actor_roles=list(user.roles),
        dry_run=req.dry_run,
    )
