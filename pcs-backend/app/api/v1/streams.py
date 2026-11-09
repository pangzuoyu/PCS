"""P3.2 SIM-6 + SIM-8 + SIM-24：物流 / 状态点手工表单 API（spec V1.6 §3.2）。

物流端点（SIM-6）：
- POST   /api/v1/projects/{project_id}/streams          # 创建（201 + StreamResponse）
- POST   /api/v1/projects/{project_id}/streams/validate # 校验（SIM-24；不入库）
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
- /streams/validate：仅跑 SIM-3 物性补全 + SIM-7 冲突检测，不写库
"""
from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1._guard import check_project_access_or_404
from app.api.v1.config import _Actor, current_actor, require_roles
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.models.enums import StateTransition
from app.models.project import Project, Stream, StreamStatePoint
from app.schemas.stream import (
    StreamCreate,
    StreamPhase,
    StreamResponse,
    StreamSignStatus,
    StreamSource,
    StreamStatePointCreate,
    StreamStatePointUpdate,
    StreamUpdate,
)
from app.services.conflict_resolver import ConflictResolver
from app.services.exceptions import PcsError
from app.services.property_auto_complete import PropertyAutoCompleter
from app.services.stream_service import (
    StreamService,
    _to_parsed_stream,  # SIM-24
    composition_mole_fraction_total,  # P9B-3b T1：组成合计口径的**唯一来源**
)
from app.services.user_project_service import has_project_access

router = APIRouter(tags=["streams"])


class ValidateStreamResponse(BaseModel):
    """SIM-24 /streams/validate 响应：完整 ConflictReport + 是否可入库。"""

    valid: bool = Field(
        ...,
        description="True = 无 BLOCK 冲突；False = 至少一条 BLOCK。",
    )
    blocks: list[dict[str, Any]] = Field(
        default_factory=list,
        description="BLOCK 级冲突列表（code/message/field/stream_name/unit_id）。",
    )
    warnings: list[dict[str, Any]] = Field(
        default_factory=list,
        description="WARN 级冲突列表。",
    )
    infos: list[dict[str, Any]] = Field(
        default_factory=list,
        description="INFO 级冲突列表。",
    )
    stats: dict[str, int] = Field(
        default_factory=dict,
        description="分级计数 {BLOCK, WARN, INFO, TOTAL}。",
    )


def _conflict_to_dict(c) -> dict[str, Any]:
    """Conflict dataclass → JSON 友好 dict。"""
    return {
        "level": c.level.value if hasattr(c.level, "value") else str(c.level),
        "code": c.code,
        "message": c.message,
        "stream_name": c.stream_name,
        "unit_id": c.unit_id,
        "field": c.field,
    }


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
    """按 project_id 取 Project 行（不存在 → 404）。

    业务：薄包装 db.get；streams 路由层取项目时的统一 404 出口。
    """

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
# 项目守卫（P9B-4 紧急批次 T2）
# ---------------------------------------------------------------------------
#
# ⚠️ **为什么不用 `check_record_access_or_404`**
#
# 它无权时抛 `HTTPException(404, "Project not found: <id>")` ⇒ 全局 handler
# 渲染成信封 **`code="HTTP_404"` / `message="Project not found: …"`**；
# 而「物流不存在」走 `PcsError(SIM_STREAM_NOT_FOUND)` ⇒ 信封
# **`code="SIM_STREAM_NOT_FOUND"` / `message="Stream … 不存在"`**。
#
# ⇒ **两个 404 的信封完全不同** ⇒ 攻击者能靠 `code`/message 区分
# 「这个 UUID 不存在」与「这个 UUID 存在但不属于我」⇒ **可枚举 UUID**。
#
# ⇒ 所以这里**自己抛**：无权 ⇒ 抛**与「不存在」逐字相同**的 `PcsError`
# ⇒ 「无权 ≡ 不存在」。


async def _load_stream_guarded(
    db: AsyncSession, stream_id: uuid.UUID, user: _Actor
) -> Stream:
    """加载物流 + **项目守卫**。

    ⚠️ **不存在**与**无权**抛**逐字相同**的 404（`SIM_STREAM_NOT_FOUND`）
    ⇒ 攻击者无法靠响应差异枚举出某个 UUID 是否存在。

    ⚠️ 文案沿用 `StreamService.get` 的措辞（`Stream {id} 不存在`）⇒
    「不存在」与「无权」两条路径的 `code` 与 `message` **逐字相同**
    ⇒ 同形性不靠「两处写一样的话」，靠**同一个 helper**。

    ⚠️ 用 `db.get`（**不加锁**）—— 守卫只读项目归属；
    真正要加锁的写路径由 `StreamService.transition` 内部的
    `SELECT ... FOR UPDATE`（`populate_existing=True`）负责。
    """
    stream = await db.get(Stream, stream_id)
    if stream is None:
        raise PcsError(
            f"Stream {stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )
    if not await has_project_access(
        db,
        user_id=user.user_id,
        project_id=stream.project_id,
        actor_roles=user.roles,
    ):
        # ⚠️ **与「不存在」逐字同形** —— 不是 403、也不是别的 code。
        raise PcsError(
            f"Stream {stream_id} 不存在",
            code="SIM_STREAM_NOT_FOUND",
            status=404,
        )
    return stream


async def _load_state_point_guarded(
    db: AsyncSession, state_point_id: uuid.UUID, user: _Actor
) -> tuple[StreamStatePoint, Stream]:
    """加载状态点 + **经其 `stream_id` 解析**物流 + 项目守卫。

    ⚠️ 状态点表**没有** `project_id`（只有 `stream_id` FK）⇒ 守卫只能
    绕道物流拿项目归属。

    ⚠️ 跨项目 ⇒ 抛 `SIM_STATEPOINT_NOT_FOUND`（与「状态点不存在」**同码同形**
    ⇒ 同一条消息 ⇒ 攻击者无法区分「不存在」与「不是我的」）。
    """
    sp = await StreamService.get_state_point(db, state_point_id)
    stream = await db.get(Stream, sp.stream_id)
    if stream is None or not await has_project_access(
        db,
        user_id=user.user_id,
        project_id=stream.project_id,
        actor_roles=user.roles,
    ):
        raise PcsError(
            f"StreamStatePoint {state_point_id} 不存在",
            code="SIM_STATEPOINT_NOT_FOUND",
            status=404,
        )
    return sp, stream


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
    # BLOCKER-3 P7-7+: project_id 守卫（SYSTEM_ADMIN bypass via actor_roles 双写兼容）
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=actor_roles_list,
    )
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


@router.post(
    "/projects/{project_id}/streams/validate",
    response_model=ValidateStreamResponse,
)
async def validate_stream(
    project_id: uuid.UUID,
    req: CreateStreamRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ValidateStreamResponse:
    """校验物流不入库：SIM-3 物性补全 + SIM-7 冲突检测。

    仅做（SIM-3 + SIM-7）的离线回放——返回完整 ConflictReport，
    不写库、不发状态、不发信号事件。前端可在 submit 之前预览。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫（SYSTEM_ADMIN bypass via actor_roles 双写兼容）
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=actor_roles_list,
    )
    # 仅校验 project 存在 + 借用其 workspace_id，不留副作用
    project = await _load_project(db, project_id)
    workspace_id = req.workspace_id or project.workspace_id
    try:
        stream_create = StreamCreate(
            project_id=project_id,
            workspace_id=workspace_id,
            **req.payload,
        )
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"请求体不合法: {e}") from e
    data = stream_create.model_dump(exclude={"project_id", "workspace_id"})
    parsed = _to_parsed_stream(data, tag=stream_create.stream_name)
    report = ConflictResolver().resolve_batch([parsed], block_on_error=False)
    return ValidateStreamResponse(
        valid=not report.has_blocks,
        blocks=[_conflict_to_dict(c) for c in report.blocks],
        warnings=[_conflict_to_dict(c) for c in report.warnings],
        infos=[_conflict_to_dict(c) for c in report.infos],
        stats=report.stats,
    )


@router.get(
    "/projects/{project_id}/streams",
    response_model=list[StreamResponse],
)
async def list_project_streams(
    project_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
    case_type: str | None = Query(None, description="按工况过滤：NORMAL/..."),
    phase: StreamPhase | None = Query(None, description="按相态过滤：VAPOR/LIQUID/..."),
    sign_status: StreamSignStatus | None = Query(None, description="按签署状态过滤"),
    source: StreamSource | None = Query(
        None, description="按录入通道过滤：MANUAL/SIM_IMPORT/EXCEL/LAB"
    ),
) -> list[StreamResponse]:
    """项目下物流列表（工况 / 相态 / 状态 / 来源 四项筛选，AND 组合）。"""
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # BLOCKER-3 P7-7+: project_id 守卫（SYSTEM_ADMIN bypass via actor_roles 双写兼容）
    actor_roles_list = list(user.roles)
    await check_project_access_or_404(
        db, user_id=user.user_id, project_id=project_id,
        actor_roles=actor_roles_list,
    )
    streams = await StreamService.list_by_project(
        db,
        project_id,
        case_type=case_type,
        phase=phase,
        sign_status=sign_status,
        source=source,
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
    stream = await _load_stream_guarded(db, stream_id, user)
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
    # ⚠ **守卫是这里最外层的检查** —— 在**载荷校验之前**。
    #    理由：守卫之前的一切（422 载荷错、422 业务门禁……）都是「这条物流
    #    存在且我能看到」的副产物 ⇒ 跨项目用户绝不该先撞上它们
    #    （bug-2039 的同款：守卫写在写入之后 ⇒ 响应是 404 但行已经被改了）。
    await _load_stream_guarded(db, stream_id, user)
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
    # ⚠ **守卫先于删除** —— 跨项目用户不得删除别人的物流。
    await _load_stream_guarded(db, stream_id, user)
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
    # ⚠ **守卫是这里最外层的检查** —— 在**载荷校验之前**（理由同 `update_stream`）。
    await _load_stream_guarded(db, stream_id, user)
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
    await _load_stream_guarded(db, stream_id, user)
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
    # ⚠ 状态点**没有** `project_id` ⇒ 守卫**经物流解析**项目归属。
    sp, _stream = await _load_state_point_guarded(db, state_point_id, user)
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
    # ⚠ **守卫是这里最外层的检查** —— 在**载荷校验之前**（理由同 `update_stream`）。
    #    状态点没有 `project_id` ⇒ 经物流解析项目归属。
    await _load_state_point_guarded(db, state_point_id, user)
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
    # ⚠ **守卫先于删除** —— 状态点没有 `project_id` ⇒ 经物流解析项目归属。
    await _load_state_point_guarded(db, state_point_id, user)
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
    *,
    precheck: Callable[[Stream], Awaitable[None]] | None = None,
) -> dict[str, Any]:
    """6 状态机端点共用 helper：**项目守卫（404）→ precheck（422）→ 转移**。

    ## ⚠️ 顺序**不可换**

    - **守卫在前** ⇒ 跨项目用户只会拿到 **404**，**看不到**任何业务细节
      （组成百分比、当前状态……）⇒ 那些细节本身就是信息泄露
      （Review Focus #2：跨项目 submit 若返回 422「组成合计 87.3%」⇒
      存在性 + 组成数据**同时**泄露）。
    - **precheck 在守卫之后、转移之前** ⇒ 非法组成**不会**留下「已进校对」的
      半成品（门禁前置，SPEC §5.1）。

    Returns:
        dict 含 sign_status（最新态）便于前端更新展示
    """
    # ① 项目守卫 —— 不存在 / 跨项目 ⇒ **同一个** 404
    stream = await _load_stream_guarded(db, stream_id, user)
    # ② 业务门禁（组成合计）—— 只在**有权**的调用方身上才可能触发
    if precheck is not None:
        await precheck(stream)
    # ③ 真正的转移
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

    ⚠️ **组成合计门禁**（SPEC §7.7.2「100±0.5%」）—— 送审**前**校验，
    不合法不放进校对（门禁前置，SPEC §5.1）：校对人看到的组成必须是合法的。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")

    # ⚠️ 组成合计门禁**挪进** `_transition_endpoint` 的 `precheck` 钩子 ——
    #    顺序变成「项目守卫（404）→ 组成门禁（422）→ 转移」。
    #    为什么挪：门禁之前**必须**是项目守卫 ⇒ 跨项目用户拿到的是 404，
    #    而不是「组成合计 87.3%」这种**既泄露存在性又泄露数据**的 422。
    return await _transition_endpoint(
        stream_id,
        StateTransition.SUBMIT_FOR_CHECK,
        user,
        db,
        reason=None,
        precheck=_composition_gate,
    )


async def _composition_gate(stream: Stream) -> None:
    """组成合计门禁 —— 100±0.5%（SPEC §7.7.2）。

    ⚠️ `None` = 无组成（纯物质）⇒ **跳过**；`{}` = 未填写 ⇒ **拒绝**。
    （空对象 ⇒ total = 0.0 ⇒ 落在范围外 ⇒ 拒绝，与「未填写」语义一致。）

    ⚠️ 这个门禁**只在有权调用方的路径上**才可能触发 ⇒ 它抛出的 422 里
    含组成百分比 ⇒ **必须**在项目守卫之后。
    """
    composition = stream.composition_json
    if composition is None:
        return
    total = composition_mole_fraction_total(stream)
    if total is None or abs(total - 1.0) > 0.005:
        raise CorePcsError(
            code="SIM_STREAM_COMPOSITION_OUT_OF_RANGE",
            message=(
                f"物流 {stream.stream_id} 的组成摩尔分率合计 {total * 100:.2f}%，"
                "不在 100±0.5% 内 ⇒ 不能提交校对"
            ),
            status=422,
        )


@router.post("/streams/{stream_id}/approve")
async def approve_stream(
    stream_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """IN_APPROVAL → CHECKED（校对通过）。

    ACL：PROCESS_CONTROLLER / SYSTEM_ADMIN（StateMachineService 强制 CHECKER/SYSTEM_ADMIN）
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


# ---------------------------------------------------------------------------
# SIM-26：物性 JSON 字段查询 + 物性补全估算（不入库）
# ---------------------------------------------------------------------------


class EstimatePropertiesRequest(BaseModel):
    """POST /streams/{id}/properties/estimate 请求：CAS 列表（必填，可空）。"""

    cas_list: list[str] = Field(
        default_factory=list,
        description="CAS 号列表（每条调用 PropertyAutoCompleter.complete）",
    )


@router.get("/streams/{stream_id}/properties")
async def get_stream_properties(
    stream_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """SIM-26：返回 stream 的 4 JSON 物性字段。

    字段：
    - user_provided：用户提供（手工/Excel 入口）
    - calculated：SIM-3 自动补全（Joback/Lee-Kesler/Rackett/CoolProp）
    - effective：实际生效（user_provided > calculated > default）
    - conflict_resolutions：PropertyConflictResolver 输出
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    stream = await _load_stream_guarded(db, stream_id, user)
    return {
        "stream_id": str(stream.stream_id),
        "user_provided": stream.user_provided_properties_json,
        "calculated": stream.calculated_properties_json,
        "effective": stream.effective_properties_json,
        "conflict_resolutions": stream.conflict_resolutions_json,
    }


@router.post("/streams/{stream_id}/properties/estimate")
async def estimate_properties(
    stream_id: uuid.UUID,
    req: EstimatePropertiesRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    """SIM-26：物性补全估算（不入库）。

    调用 PropertyAutoCompleter.batch_complete，对 req.cas_list 中每个 CAS
    独立跑一次补全（COMMON 库 + chemicals + CoolProp），返回每 CAS 的 dict。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    # 先校验 stream 存在 + 项目守卫 → 不存在 / 无权都是 404
    await _load_stream_guarded(db, stream_id, user)
    completer = PropertyAutoCompleter()
    raw = completer.batch_complete(req.cas_list)
    # 注入 cas 字段（PropertyAutoCompleter 不返回 cas）
    results = [
        {"cas": cas, **data}
        for cas, data in zip(req.cas_list, raw, strict=True)
    ]
    return {"results": results}


__all__ = ["router"]