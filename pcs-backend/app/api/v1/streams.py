"""P3.2 SIM-6 + SIM-8：物流 / 状态点手工表单 API（spec V1.6 §3.2）。

物流端点（SIM-6）：
- POST   /api/v1/projects/{project_id}/streams          # 创建（201 + StreamResponse）
- GET    /api/v1/projects/{project_id}/streams          # 列表（按 case_type 可选过滤）
- GET    /api/v1/streams/{stream_id}                    # 单条
- PATCH  /api/v1/streams/{stream_id}                    # 部分更新
- DELETE /api/v1/streams/{stream_id}                    # 删除（204）

状态点端点（SIM-8）：
- POST   /api/v1/streams/{stream_id}/state-points       # 创建（201 + StreamStatePointResponse）
- GET    /api/v1/streams/{stream_id}/state-points       # 列表
- GET    /api/v1/state-points/{state_point_id}          # 单条
- PATCH  /api/v1/state-points/{state_point_id}          # 部分更新
- DELETE /api/v1/state-points/{state_point_id}          # 删除（204）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
- Stream BLOCK → 422 SIM_STREAM_BLOCKED；StatePoint BLOCK → 422 SIM_STATEPOINT_BLOCKED
- 同 (project, stream_name) 重复 → 422 SIM_STREAM_DUPLICATE_NAME
- 单查/更新/删除 → 404 SIM_STREAM_NOT_FOUND / SIM_STATEPOINT_NOT_FOUND
- ORM datetime → ISO str（API 层 _to_response_dict）
- 业务错走 core.errors.PcsError envelope；HTTPException 仅用于 401/403/404 project 不存在
"""
from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.models.enums import StateTransition
from app.models.project import Project, Stream, StreamStatePoint
from app.schemas.stream import (
    StreamCreate,
    StreamResponse,
    StreamStatePointCreate,
    StreamStatePointUpdate,
    StreamUpdate,
)
from app.services.exceptions import PcsError
from app.services.stream_service import StreamService

router = APIRouter(tags=["streams"])


# ---------------------------------------------------------------------------
# 请求/响应封装
# ---------------------------------------------------------------------------


class CreateStreamRequest(BaseModel):
    """精简创建请求：project_id 从 URL 取；workspace_id 可缺省。"""

    workspace_id: uuid.UUID | None = Field(
        None, description="所属工作区 ID（缺省取 Project.workspace_id）"
    )
    payload: dict[str, Any] = Field(
        ..., description="StreamBase 字段（stream_name/case_type/data_mode/...）"
    )


class UpdateStreamRequest(BaseModel):
    """精简更新请求：StreamUpdate 字段的可选子集。"""

    payload: dict[str, Any] = Field(..., description="StreamUpdate 字段子集")


class TransitionRequest(BaseModel):
    """SIM-13 状态机转移请求体（reason 可选）。"""

    reason: str | None = Field(
        None, max_length=500, description="转移原因（部分事件需填，audit 落库）"
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _to_http(err: Exception) -> CorePcsError:
    """service PcsError → core PcsError 转换，保留 status/code/message。

    走全局 envelope：HTTP 响应为 {code, message, detail, trace_id} 而非
    FastAPI 默认的 {detail}。
    """
    code = getattr(err, "code", "PCS_ERROR")
    status = getattr(err, "status", 422)
    message = str(err)
    details = getattr(err, "details", None) or None
    return CorePcsError(code=code, message=message, status=status, detail=details)


async def _load_project(db: AsyncSession, project_id: uuid.UUID) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail=f"Project {project_id} 不存在")
    return project


def _to_response_dict(stream: Stream) -> dict[str, Any]:
    """ORM Stream → 响应 dict：datetime 字段先转 ISO 字符串再 model_validate。

    StreamResponse 的 created_at/updated_at/last_changed_at 字段声明为 str，
    直接 model_validate(orm) 会因 datetime 类型不匹配抛 ValidationError。
    """
    skip = {
        "stream_id",
        "sign_status",
        "approval_step",
        "checked_by",
        "checked_at",
        "record_hash",
        "last_change_reason",
        "last_change_note",
        "last_changed_by",
        "last_changed_at",
        "created_at",
        "updated_at",
    }
    data: dict[str, Any] = {}
    for col in Stream.__table__.columns:
        if col.name in skip:
            continue
        data[col.name] = getattr(stream, col.name)
    # 审计字段 + 时间字段
    data["stream_id"] = stream.stream_id
    data["sign_status"] = stream.sign_status
    data["approval_step"] = stream.approval_step
    data["approval_depth"] = stream.approval_depth
    data["record_hash"] = stream.record_hash
    data["last_change_reason"] = stream.last_change_reason
    data["created_at"] = stream.created_at.isoformat() if stream.created_at else None
    data["updated_at"] = stream.updated_at.isoformat() if stream.updated_at else None
    data["last_changed_at"] = (
        stream.last_changed_at.isoformat() if stream.last_changed_at else None
    )
    return data


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/projects/{project_id}/streams",
    status_code=201,
    response_model=StreamResponse,
)
async def create_stream(
    project_id: uuid.UUID,
    req: CreateStreamRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamResponse:
    """创建物流：SIM-3 物性补全 + SIM-7 冲突检测，BLOCK 拒绝。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    project = await _load_project(db, project_id)
    workspace_id = req.workspace_id or project.workspace_id
    try:
        # 构造 StreamCreate：把 body 字段与 URL project_id 合并
        stream_create = StreamCreate(
            project_id=project_id,
            workspace_id=workspace_id,
            **req.payload,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"请求体不合法: {e}") from e
    try:
        stream, _report = await StreamService.create(
            db, stream_create, actor=user.user_id
        )
    except PcsError as e:
        raise _to_http(e) from e
    return _to_response_dict(stream)


@router.get(
    "/projects/{project_id}/streams",
    response_model=list[StreamResponse],
)
async def list_project_streams(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    case_type: str | None = Query(None, description="按工况过滤：NORMAL/..."),
) -> list[StreamResponse]:
    """项目下物流列表。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    streams = await StreamService.list_by_project(
        db, project_id, case_type=case_type
    )
    return [_to_response_dict(s) for s in streams]


@router.get("/streams/{stream_id}", response_model=StreamResponse)
async def get_stream(
    stream_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamResponse:
    """单条物流查询。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        stream = await StreamService.get(db, stream_id)
    except PcsError as e:
        raise _to_http(e) from e
    return _to_response_dict(stream)


@router.patch("/streams/{stream_id}", response_model=StreamResponse)
async def update_stream(
    stream_id: uuid.UUID,
    req: UpdateStreamRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> StreamResponse:
    """部分更新：字段子集 → StreamUpdate。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        update_payload = StreamUpdate(**req.payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"请求体不合法: {e}") from e
    try:
        stream, _report = await StreamService.update(
            db, stream_id, update_payload, actor=user.user_id
        )
    except PcsError as e:
        raise _to_http(e) from e
    return _to_response_dict(stream)


@router.delete("/streams/{stream_id}", status_code=204)
async def delete_stream(
    stream_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """删除物流。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        await StreamService.delete(db, stream_id, actor=user.user_id)
    except PcsError as e:
        raise _to_http(e) from e
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# StatePoint 端点（SIM-8）
# ---------------------------------------------------------------------------


def _state_point_to_response(sp: StreamStatePoint) -> dict[str, Any]:
    """ORM StreamStatePoint → 响应 dict（datetime → ISO str）。"""
    data: dict[str, Any] = {}
    for col in StreamStatePoint.__table__.columns:
        data[col.name] = getattr(sp, col.name)
    if data.get("created_at") is not None:
        data["created_at"] = data["created_at"].isoformat()
    return data


@router.post(
    "/streams/{stream_id}/state-points",
    status_code=201,
)
async def create_state_point(
    stream_id: uuid.UUID,
    payload: dict[str, Any],
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """创建状态点：SIM-9 冲突检测，BLOCK 拒绝。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        sp_create = StreamStatePointCreate(stream_id=stream_id, **payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"请求体不合法: {e}") from e
    try:
        sp, _report = await StreamService.create_state_point(
            db, stream_id, sp_create, actor=user.user_id
        )
    except PcsError as e:
        raise _to_http(e) from e
    return _state_point_to_response(sp)


@router.get("/streams/{stream_id}/state-points")
async def list_state_points(
    stream_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, Any]]:
    """某物流下状态点列表（按 case_type 排序）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        sps = await StreamService.list_state_points(db, stream_id)
    except PcsError as e:
        raise _to_http(e) from e
    return [_state_point_to_response(sp) for sp in sps]


@router.get("/state-points/{state_point_id}")
async def get_state_point(
    state_point_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """单条状态点查询。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        sp = await StreamService.get_state_point(db, state_point_id)
    except PcsError as e:
        raise _to_http(e) from e
    return _state_point_to_response(sp)


@router.patch("/state-points/{state_point_id}")
async def update_state_point(
    state_point_id: uuid.UUID,
    payload: dict[str, Any],
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """部分更新：state_label/case_type/temp/press/phase/mass_flow/source_type。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        update = StreamStatePointUpdate(**payload)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"请求体不合法: {e}") from e
    try:
        sp, _report = await StreamService.update_state_point(
            db, state_point_id, update, actor=user.user_id
        )
    except PcsError as e:
        raise _to_http(e) from e
    return _state_point_to_response(sp)


@router.delete("/state-points/{state_point_id}", status_code=204)
async def delete_state_point(
    state_point_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Response:
    """删除状态点。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        await StreamService.delete_state_point(
            db, state_point_id, actor=user.user_id
        )
    except PcsError as e:
        raise _to_http(e) from e
    return Response(status_code=204)


# ---------------------------------------------------------------------------
# 状态机端点（SIM-13，闭环审计 D-1）
# ---------------------------------------------------------------------------


async def _transition_endpoint(
    stream_id: uuid.UUID,
    event: StateTransition,
    user: _Actor,
    db: AsyncSession,
    reason: str | None,
) -> dict[str, Any]:
    """6 状态机端点共用 helper：SELECT FOR UPDATE → StateMachineService。

    Returns:
        dict 含 sign_status（最新态）便于前端更新展示
    """
    try:
        stream = await StreamService.transition(
            db,
            stream_id,
            transition=event,
            actor_user_id=user.user_id,
            actor_role=user.role,
            reason=reason,
        )
    except PcsError as e:
        raise _to_http(e) from e
    return {
        "stream_id": str(stream.stream_id),
        "sign_status": stream.sign_status.value
        if hasattr(stream.sign_status, "value")
        else str(stream.sign_status),
        "approval_step": stream.approval_step,
        "change_pending_since": (
            stream.change_pending_since.isoformat()
            if stream.change_pending_since
            else None
        ),
        "change_resolved_at": (
            stream.change_resolved_at.isoformat()
            if stream.change_resolved_at
            else None
        ),
    }


@router.post("/streams/{stream_id}/submit")
async def submit_stream(
    stream_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """DRAFT → IN_APPROVAL（提交校对）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    （具体角色权限由 StateMachineService.TRANSITION_ROLES 校验）
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await _transition_endpoint(
        stream_id, StateTransition.SUBMIT_FOR_CHECK, user, db, reason=None
    )


@router.post("/streams/{stream_id}/approve")
async def approve_stream(
    stream_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """IN_APPROVAL → CHECKED（校对通过）。

    ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN（StateMachineService 强制 CHECKER/SYSADMIN）
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await _transition_endpoint(
        stream_id, StateTransition.PASS_CHECK, user, db, reason=None
    )


@router.post("/streams/{stream_id}/reject")
async def reject_stream(
    stream_id: uuid.UUID,
    req: TransitionRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """IN_APPROVAL → CHECK_REJECTED（校对驳回）。

    body.reason 必填（驳回理由写入 audit）。
    ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await _transition_endpoint(
        stream_id, StateTransition.REJECT_CHECK, user, db, reason=req.reason
    )


@router.post("/streams/{stream_id}/initiate-change")
async def initiate_change_stream(
    stream_id: uuid.UUID,
    req: TransitionRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """CHECKED → CHANGE_PENDING（ADR-0002 主动变更）。

    body.reason 可选（变更理由写入 audit）。
    ACL：DESIGNER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "SYSTEM_ADMIN")
    return await _transition_endpoint(
        stream_id, StateTransition.INITIATE_CHANGE, user, db, reason=req.reason
    )


@router.post("/streams/{stream_id}/pass-change")
async def pass_change_stream(
    stream_id: uuid.UUID,
    req: TransitionRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """CHANGE_PENDING → CHANGED（变更通过，闭环为 CHANGED 态）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await _transition_endpoint(
        stream_id, StateTransition.APPLY_CHANGE, user, db, reason=req.reason
    )


@router.post("/streams/{stream_id}/mark-stale")
async def mark_stale_stream(
    stream_id: uuid.UUID,
    req: TransitionRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """CHECKED → STALE（标记上游变更，ADR-0024 不写 snapshot）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    return await _transition_endpoint(
        stream_id, StateTransition.MARK_STALE, user, db, reason=req.reason
    )


__all__ = ["router"]