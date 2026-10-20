"""编辑锁 API（ADR-0048 §①⑤ · SPEC §6.21 EditLockIndicator）。

三个端点：

- ``POST /locks/{record_type}/{record_id}/acquire`` —— 取锁
- ``POST /locks/{record_type}/{record_id}/renew`` —— 续期（心跳 60s）
- ``POST /locks/{record_type}/{record_id}/release`` —— 释放（仅持有者）

## 三条纪律

1. **锁判定不查库**（§① 的两层锁前提）：判定全部在 Redis 里做完。
   本模块里唯一的 DB 用途是**事后写审计**（§①「DB 保留审计留痕」），
   写审计失败**不得**让锁请求失败 —— 锁已经拿到了。
2. **他人持锁 ⇒ 409 + 持锁人信息**（不是裸 409）：体验层的全部价值在于
   「告诉用户谁在改」。前端据此显示「张三 正在编辑」。
3. **Redis 挂 ⇒ 降级放行 + 横幅**，不是 503（§⑤）：放行的是**体验**，
   拦住并发的是 DB 层（record_hash 比对，D2）。
"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor
from app.db.session import get_db
from app.models.enums import AuditAction
from app.schemas.lock import LockHolderResponse, LockResponse
from app.services.audit_service import AuditService
from app.services.edit_lock import EditLockService, get_edit_lock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/locks", tags=["locks"])

_409 = {
    409: {
        "model": LockResponse,
        "description": "他人持锁（或已过期）：响应体带持锁人信息",
    }
}


def _to_response(
    *,
    operation: str,
    record_type: str,
    record_id: str,
    state,
) -> LockResponse:
    holder = None
    if state.holder is not None:
        holder = LockHolderResponse(
            user_id=str(state.holder.user_id),
            acquired_at=state.holder.acquired_at,
            username=state.holder.username,
        )
    return LockResponse(
        record_type=record_type,
        record_id=record_id,
        operation=operation,  # type: ignore[arg-type]
        success=state.success,
        holder=holder,
        ttl_seconds=state.ttl_seconds,
        degraded=state.degraded,
        message=state.message,
    )


async def _write_lock_audit(
    db: AsyncSession,
    *,
    action: AuditAction,
    user_id: uuid.UUID,
    record_type: str,
    record_id: str,
    success: bool,
    degraded: bool,
) -> None:
    """写一条锁审计（ADR-0048 §①）。

    ⚠️ **best-effort**：审计失败**不得**让锁请求失败 —— 锁已经拿到了，
    审计只是留痕。失败记 ERROR。
    """
    try:
        await AuditService(db).write(
            action=action,
            resource_type=record_type,
            resource_id=record_id,
            user_id=user_id,
            detail={
                "record_type": record_type,
                "record_id": record_id,
                "success": success,
                "degraded": degraded,
            },
        )
        await db.commit()
    except Exception:  # noqa: BLE001 — 审计失败不该影响锁
        logger.error("写编辑锁审计失败（不阻断锁响应）", exc_info=True)
        await db.rollback()


@router.post(
    "/{record_type}/{record_id}/acquire",
    response_model=LockResponse,
    responses=_409,
)
async def acquire_edit_lock(
    record_type: str,
    record_id: str,
    response: Response,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LockResponse:
    """取编辑锁。

    已被他人持有 ⇒ **409 + 持锁人信息**（前端显示「XX 正在编辑」）。
    Redis 不可用 ⇒ **降级放行**（200 + `degraded=true` + 横幅文案）。
    """
    svc: EditLockService = get_edit_lock()
    state = await svc.acquire(
        record_type=record_type,
        record_id=record_id,
        user_id=user.user_id,
        username=user.username,
    )
    if not state.success:
        response.status_code = 409
    await _write_lock_audit(
        db,
        action=AuditAction.EDIT_LOCK_ACQUIRED,
        user_id=user.user_id,
        record_type=record_type,
        record_id=record_id,
        success=state.success,
        degraded=state.degraded,
    )
    return _to_response(
        operation="acquire",
        record_type=record_type,
        record_id=record_id,
        state=state,
    )


@router.post(
    "/{record_type}/{record_id}/renew",
    response_model=LockResponse,
    responses=_409,
)
async def renew_edit_lock(
    record_type: str,
    record_id: str,
    response: Response,
    user: Annotated[_Actor, Depends(current_actor)],
) -> LockResponse:
    """续期（compare-and-expire）。

    ⚠️ **他人的心跳不得延长我的锁**（§②）—— 不是持有者 ⇒ 409。
    ⚠️ **本端点不碰数据库**（连 session 都不开）：续期是纯 Redis 操作，
    且不写审计（60s 一次的心跳会把 audit_logs 灌爆）。
    """
    svc: EditLockService = get_edit_lock()
    state = await svc.renew(
        record_type=record_type, record_id=record_id, user_id=user.user_id
    )
    if not state.success:
        response.status_code = 409
    return _to_response(
        operation="renew",
        record_type=record_type,
        record_id=record_id,
        state=state,
    )


@router.post(
    "/{record_type}/{record_id}/release",
    response_model=LockResponse,
    responses=_409,
)
async def release_edit_lock(
    record_type: str,
    record_id: str,
    response: Response,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LockResponse:
    """释放编辑锁。

    ⚠️ **仅持有者可释放**（非持有者 ⇒ 409，且**不得**动别人的锁）。
    """
    svc: EditLockService = get_edit_lock()
    state = await svc.release(
        record_type=record_type, record_id=record_id, user_id=user.user_id
    )
    if not state.success:
        response.status_code = 409
    await _write_lock_audit(
        db,
        action=AuditAction.EDIT_LOCK_RELEASED,
        user_id=user.user_id,
        record_type=record_type,
        record_id=record_id,
        success=state.success,
        degraded=state.degraded,
    )
    return _to_response(
        operation="release",
        record_type=record_type,
        record_id=record_id,
        state=state,
    )


__all__ = ["router"]
