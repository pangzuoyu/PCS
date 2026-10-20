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

## `record_type` 必须是注册表键，且**必须校验**（P9A-5 Task A · TODO-060）

⚠️ 本模块原先**完全不校验** `record_type` ⇒ 前端传错拼写会 **200 成功**，锁写进
`lock:edit:{错拼写}:{id}` ⇒ 与正确拼写的锁**互不可见** ⇒ 两个人用不同拼写可以
**同时编辑同一条记录**。且 `has_conflict_detection(错拼写)` 返回 False ⇒ 降级
横幅会**错误地**说「本次编辑无冲突检测」。

⇒ 三个端点都在碰 Redis **之前**校验，未登记 ⇒ **404**（与 `/change-impact`
未知 `record_type` 的处理一致）。

⚠️ 键取自 `RECORD_TYPE_REGISTRY`（`CostEstResult`），**不是**表名
（`cost_est_results`）—— 同一个 URL 空间不许出现两套词表。
"""
from __future__ import annotations

import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor
from app.db.session import get_db
from app.models.enums import AuditAction
from app.schemas.lock import LockHolderResponse, LockResponse
from app.services.audit_service import AuditService
from app.services.edit_guard import TABLE_CAPABILITIES, UnregisteredTableError, capability_of
from app.services.edit_lock import EditLockService, get_edit_lock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/locks", tags=["locks"])

#: `{record_type}` 的取值 = **已登记的可编辑表的注册表键**。
#: ⚠️ 写进 OpenAPI 的 `enum` 是**给前端的词表** —— 否则前端只能靠读 SPEC 或
#: 读后端源码才知道该传什么（实测 `openapi.snapshot.json` 里该参数原本只有
#: `{"type": "string"}`，无 enum 无 description）。
_RECORD_TYPE_PATH = Path(
    description=(
        "记录类型：`RECORD_TYPE_REGISTRY` 的键（如 `CostEstResult`）—— "
        "**不是**表名（`cost_est_results`），全仓只有这一套词表（TODO-060）"
    ),
    json_schema_extra={"enum": sorted(TABLE_CAPABILITIES)},
)

_409 = {
    409: {
        "model": LockResponse,
        "description": "他人持锁（或已过期）：响应体带持锁人信息",
    }
}


def _require_editable_record_type(record_type: str) -> str:
    """`record_type` 必须是已登记的编辑表 ⇒ 否则 **404**。

    ⚠️ 校验**发生在碰 Redis 之前** —— 否则一个错拼写就已经把锁写进
    Redis 了（那正是本函数要堵的洞）。
    ⚠️ 抛 **404 而不是 422**：调用方拿到「这个记录类型不可编辑」与
    `/change-impact` 的既有处理一致（那里也是 404）。
    """
    try:
        capability_of(record_type)
    except UnregisteredTableError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                f"record_type {record_type} not supported —— 键必须是 "
                "RECORD_TYPE_REGISTRY 的键（如 CostEstResult），不是表名"
            ),
        ) from exc
    return record_type


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
    record_type: Annotated[str, _RECORD_TYPE_PATH],
    record_id: str,
    response: Response,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LockResponse:
    """取编辑锁。

    已被他人持有 ⇒ **409 + 持锁人信息**（前端显示「XX 正在编辑」）。
    Redis 不可用 ⇒ **降级放行**（200 + `degraded=true` + 横幅文案）。
    """
    _require_editable_record_type(record_type)
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
    record_type: Annotated[str, _RECORD_TYPE_PATH],
    record_id: str,
    response: Response,
    user: Annotated[_Actor, Depends(current_actor)],
) -> LockResponse:
    """续期（compare-and-expire）。

    ⚠️ **他人的心跳不得延长我的锁**（§②）—— 不是持有者 ⇒ 409。
    ⚠️ **本端点不碰数据库**（连 session 都不开）：续期是纯 Redis 操作，
    且不写审计（60s 一次的心跳会把 audit_logs 灌爆）。
    ⚠️ `_require_editable_record_type` 查的是**内存里的能力表**，不是 DB
    ⇒ 加了它不违反「不碰数据库」。
    """
    _require_editable_record_type(record_type)
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
    record_type: Annotated[str, _RECORD_TYPE_PATH],
    record_id: str,
    response: Response,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> LockResponse:
    """释放编辑锁。

    ⚠️ **仅持有者可释放**（非持有者 ⇒ 409，且**不得**动别人的锁）。
    """
    _require_editable_record_type(record_type)
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
