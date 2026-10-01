"""P6-3 OPEN_CHANNEL API（SPEC §3.2.6 + Task 32）。

端点（9 个）：
- POST /api/v1/open-channel/manning/calculate   POST §3.2.6 Manning 流量（201）
- POST /api/v1/open-channel/section/calculate   POST §3.2.6 最优水力断面（201）
- POST /api/v1/open-channel/critical/calculate  POST §3.2.6 临界水深 + Fr（201）
- POST /api/v1/open-channel/jump/calculate      POST §3.2.6 水跃 Bélanger（201）
- POST   /api/v1/open-channel/results         创建 OpenChannelResult（201）
- GET    /api/v1/open-channel/results         列出（分页）
- GET    /api/v1/open-channel/results/{id}    详情
- PATCH  /api/v1/open-channel/results/{id}    更新（仅 DRAFT/CHANGE_PENDING 可改）
- DELETE /api/v1/open-channel/results/{id}    软删除（→ OBSOLETE）

设计要点：
- ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN（6 endpoints 用
  ``require_roles``，CRUD 5 endpoints 同样）
- 业务异常 → 走 core.errors.PcsError envelope
- 4 calc 端点：endpoint 调 calc_* → save_*_result service 层构造 record，
  禁止 endpoint 直构 OpenChannelResult（红线 #1）
- PATCH 锁定态：CHECKED / IN_APPROVAL 等拒绝 PATCH（OPEN_CHANNEL_LOCKED）
"""
from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.config import _Actor, current_actor, require_roles
from app.api.v1._guard import check_record_access_or_404
from app.core.errors import PcsError as CorePcsError
from app.db.session import get_db
from app.schemas.open_channel import (
    CriticalCalcRequest,
    CriticalCalcResponse,
    JumpCalcRequest,
    JumpCalcResponse,
    ManningCalcRequest,
    ManningCalcResponse,
    OpenChannelCreateRequest,
    OpenChannelDeleteResponse,
    OpenChannelListResponse,
    OpenChannelResultResponse,
    OpenChannelUpdateRequest,
    SectionCalcRequest,
    SectionCalcResponse,
)
from app.services.exceptions import PcsError as ServicePcsError
from app.services.open_channel import (  # P6-3 Task 32
    CriticalInputError,
    JumpInputError,
    ManningInputError,
    OpenChannelPersistInputError,
    SectionInputError,
    calc_critical_depth,
    calc_froude_number,
    calc_hydraulic_jump,
    calc_manning_flow,
    calc_optimal_section,
    create_open_channel_result_direct,
    get_open_channel_result_service,
    list_open_channel_results_service,
    save_critical_result,
    save_jump_result,
    save_manning_result,
    save_section_result,
    soft_delete_open_channel_result_service,
    update_open_channel_result_service,
)
from app.services.open_channel.jump import JumpInput
from app.services.open_channel.manning import ManningInput
from app.services.open_channel.section import SectionInput

router = APIRouter(prefix="/open-channel", tags=["open-channel"])


def _to_http(err: ServicePcsError) -> CorePcsError:
    """service 层 PcsError → FastAPI HTTPException envelope。

    注：P6-OPEN-010 fix — CorePcsError 使用 ``status`` kwarg（非
    ``status_code``，避免与 HTTPException 混淆）。
    """
    return CorePcsError(
        code=err.code, message=str(err), status=err.status
    )


# ============================================================================
# 4 calc endpoints（POST /open-channel/{manning,section,critical,jump}/calculate）
# ============================================================================


@router.post(
    "/manning/calculate",
    response_model=ManningCalcResponse,
    status_code=201,
)
async def calculate_manning(
    req: ManningCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ManningCalcResponse:
    """Manning 流量计算（§3.2.6 第一项）。

    流程：endpoint 调 ``calc_manning_flow`` → save_manning_result service
    落 OpenChannelResult 行；禁止 endpoint 直构 ORM（红线 #1）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        # 1. 调 calc（ManningInput）
        inp = ManningInput(
            channel_type=req.channel_type,
            bottom_width=req.cross_section_json.get("bottom_width") or 0.0,
            side_slope=req.cross_section_json.get("side_slope"),
            diameter=req.cross_section_json.get("diameter"),
            depth=req.depth,
            manning_n=req.manning_n or 0.013,
            slope=req.slope,
        )
        calc_r = calc_manning_flow(inp)
    except ManningInputError as e:
        raise _to_http(e) from e

    # 2. save 服务层构造 record（endpoint 不直构 ORM）
    actor_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    try:
        record = await save_manning_result(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            channel_type=req.channel_type,
            cross_section_json=req.cross_section_json,
            flow_rate=calc_r.flow_rate,
            depth=req.depth,
            velocity=calc_r.velocity,
            slope=req.slope,
            hydraulic_radius=calc_r.hydraulic_radius,
            manning_n=req.manning_n,
            created_by=actor_id,
        )
    except OpenChannelPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return ManningCalcResponse(
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        tag_number=record.tag_number,
        channel_type=record.channel_type,
        cross_section_json=record.cross_section_json,
        flow_rate=record.flow_rate,
        depth=record.depth,
        velocity=record.velocity,
        slope=record.slope,
        manning_n=record.manning_n,
        hydraulic_radius=record.hydraulic_radius,
        result_id=record.open_channel_id,
        record_hash=record.record_hash,
        sign_status=record.sign_status.value,
        created_at=record.created_at,
    )


@router.post(
    "/section/calculate",
    response_model=SectionCalcResponse,
    status_code=201,
)
async def calculate_section(
    req: SectionCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> SectionCalcResponse:
    """最优水力断面（§3.2.6 第二项）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        inp = SectionInput(
            channel_type=req.channel_type,
            flow_rate=req.flow_rate,
            slope=req.slope,
            manning_n=req.manning_n or 0.013,
            side_slope=req.cross_section_json.get("side_slope"),
            diameter=req.cross_section_json.get("diameter"),
        )
        calc_r = calc_optimal_section(inp)
    except SectionInputError as e:
        raise _to_http(e) from e

    actor_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    try:
        record = await save_section_result(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            channel_type=req.channel_type,
            cross_section_json=req.cross_section_json,
            flow_rate=calc_r.flow_rate_check,
            depth=calc_r.depth,
            velocity=(
                calc_r.flow_rate_check / calc_r.area if calc_r.area > 0 else 0.0
            ),
            slope=req.slope,
            manning_n=req.manning_n,
            hydraulic_radius=calc_r.hydraulic_radius,
            created_by=actor_id,
        )
    except OpenChannelPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return SectionCalcResponse(
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        tag_number=record.tag_number,
        channel_type=record.channel_type,
        cross_section_json=record.cross_section_json,
        flow_rate=record.flow_rate,
        depth=record.depth,
        velocity=record.velocity,
        slope=record.slope,
        manning_n=record.manning_n,
        hydraulic_radius=record.hydraulic_radius,
        result_id=record.open_channel_id,
        record_hash=record.record_hash,
        sign_status=record.sign_status.value,
        created_at=record.created_at,
    )


@router.post(
    "/critical/calculate",
    response_model=CriticalCalcResponse,
    status_code=201,
)
async def calculate_critical(
    req: CriticalCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> CriticalCalcResponse:
    """临界水深 + Froude 数（§3.2.6 第三项）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    bottom_width = req.cross_section_json.get("bottom_width") or 0.0
    try:
        h_c = calc_critical_depth(req.flow_rate, bottom_width)
        fr, v_calc, _regime = calc_froude_number(
            req.flow_rate, bottom_width, req.depth
        )
    except CriticalInputError as e:
        raise _to_http(e) from e

    actor_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    try:
        record = await save_critical_result(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            channel_type=req.channel_type,
            cross_section_json=req.cross_section_json,
            flow_rate=req.flow_rate,
            depth=req.depth,
            velocity=v_calc,
            slope=req.slope,
            critical_depth=h_c,
            froude_number=fr,
            manning_n=req.manning_n,
            hydraulic_radius=req.hydraulic_radius,
            created_by=actor_id,
        )
    except OpenChannelPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return CriticalCalcResponse(
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        tag_number=record.tag_number,
        channel_type=record.channel_type,
        cross_section_json=record.cross_section_json,
        flow_rate=record.flow_rate,
        depth=record.depth,
        velocity=record.velocity,
        slope=record.slope,
        critical_depth=record.critical_depth,
        froude_number=record.froude_number,
        manning_n=record.manning_n,
        hydraulic_radius=record.hydraulic_radius,
        result_id=record.open_channel_id,
        record_hash=record.record_hash,
        sign_status=record.sign_status.value,
        created_at=record.created_at,
    )


@router.post(
    "/jump/calculate",
    response_model=JumpCalcResponse,
    status_code=201,
)
async def calculate_jump(
    req: JumpCalcRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> JumpCalcResponse:
    """水跃 Bélanger + 能量损失 + 跃型判定（§3.2.6 第四项）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        inp = JumpInput(h1=req.depth, v1=req.velocity)
        calc_r = calc_hydraulic_jump(inp)
    except JumpInputError as e:
        raise _to_http(e) from e

    actor_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    try:
        record = await save_jump_result(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            channel_type=req.channel_type,
            cross_section_json=req.cross_section_json,
            flow_rate=req.flow_rate,
            depth=req.depth,
            velocity=req.velocity,
            slope=req.slope,
            jump_type=calc_r.jump_type,
            conjugate_depth=calc_r.h2,
            energy_loss=calc_r.energy_loss,
            manning_n=req.manning_n,
            hydraulic_radius=req.hydraulic_radius,
            created_by=actor_id,
        )
    except OpenChannelPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return JumpCalcResponse(
        project_id=record.project_id,
        workspace_id=record.workspace_id,
        tag_number=record.tag_number,
        channel_type=record.channel_type,
        cross_section_json=record.cross_section_json,
        flow_rate=record.flow_rate,
        depth=record.depth,
        velocity=record.velocity,
        slope=record.slope,
        jump_type=record.jump_type,
        conjugate_depth=record.conjugate_depth,
        energy_loss=record.energy_loss,
        manning_n=record.manning_n,
        hydraulic_radius=record.hydraulic_radius,
        result_id=record.open_channel_id,
        record_hash=record.record_hash,
        sign_status=record.sign_status.value,
        created_at=record.created_at,
    )


# ============================================================================
# 5 CRUD endpoints（/open-channel/results）
# ============================================================================


@router.post(
    "/results", response_model=OpenChannelResultResponse, status_code=201
)
async def create_open_channel_result(
    req: OpenChannelCreateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OpenChannelResultResponse:
    """直接创建 OpenChannelResult 行（POST → 201，不走 calc）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    payload = req.model_dump(
        exclude={"project_id", "workspace_id", "tag_number"}
    )
    actor_id = getattr(user, "user_id", None) or getattr(user, "id", None)
    try:
        record = await create_open_channel_result_direct(
            db,
            project_id=req.project_id,
            workspace_id=req.workspace_id,
            tag_number=req.tag_number,
            created_by=actor_id,
            **payload,
        )
    except OpenChannelPersistInputError as e:
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return OpenChannelResultResponse.model_validate(record, from_attributes=True)


@router.get("/results", response_model=OpenChannelListResponse)
async def list_open_channel_results(
    project_id: Annotated[uuid.UUID, Query(...)],
    include_obsolete: Annotated[bool, Query()] = False,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    user: _Actor = Depends(current_actor),
    db: AsyncSession = Depends(get_db),
) -> OpenChannelListResponse:
    """按 project_id 列出 OpenChannelResult（GET list，分页）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    records = await list_open_channel_results_service(
        db,
        project_id=project_id,
        include_obsolete=include_obsolete,
        skip=skip,
        limit=limit,
    )
    items = [
        OpenChannelResultResponse.model_validate(r, from_attributes=True)
        for r in records
    ]
    return OpenChannelListResponse(
        items=items, total=len(items), skip=skip, limit=limit
    )


@router.get(
    "/results/{result_id}", response_model=OpenChannelResultResponse
)
async def get_open_channel_result(
    result_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OpenChannelResultResponse:
    """按 open_channel_id 取 OpenChannelResult（GET detail）。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    BLOCKER-3 守卫: record.project_id 必须属于 user。
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        record = await get_open_channel_result_service(
            db, result_id=result_id
        )
    except OpenChannelPersistInputError as e:
        if e.code == "OPEN_CHANNEL_NOT_FOUND":
            raise HTTPException(
                status_code=404, detail="OpenChannelResult not found"
            ) from e
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    # BLOCKER-3 守卫
    await check_record_access_or_404(
        db, user_id=user.user_id, record=record, actor_roles=user.roles,
    )

    return OpenChannelResultResponse.model_validate(record, from_attributes=True)


@router.patch(
    "/results/{result_id}", response_model=OpenChannelResultResponse
)
async def update_open_channel_result(
    result_id: uuid.UUID,
    req: OpenChannelUpdateRequest,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OpenChannelResultResponse:
    """更新 OpenChannelResult 业务字段（PATCH）。

    仅 DRAFT / CHANGE_PENDING 可改；CHECKED 等锁定态拒绝。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    patch = req.model_dump(exclude_unset=True)
    try:
        record = await update_open_channel_result_service(
            db, result_id=result_id, patch=patch
        )
    except OpenChannelPersistInputError as e:
        if e.code == "OPEN_CHANNEL_NOT_FOUND":
            raise HTTPException(
                status_code=404, detail="OpenChannelResult not found"
            ) from e
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return OpenChannelResultResponse.model_validate(record, from_attributes=True)


@router.delete(
    "/results/{result_id}", response_model=OpenChannelDeleteResponse
)
async def soft_delete_open_channel_result(
    result_id: uuid.UUID,
    user: Annotated[_Actor, Depends(current_actor)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> OpenChannelDeleteResponse:
    """软删除 OpenChannelResult（DELETE → sign_status=OBSOLETE）。

    位号加 ``__OBSOLETE_<ts>`` 后缀，stale_resolution_path 标记。

    ACL：DESIGNER / PROCESS_CONTROLLER / SYSTEM_ADMIN
    """
    require_roles(user, "DESIGNER", "PROCESS_CONTROLLER", "SYSTEM_ADMIN")
    try:
        record = await soft_delete_open_channel_result_service(
            db, result_id=result_id
        )
    except OpenChannelPersistInputError as e:
        if e.code == "OPEN_CHANNEL_NOT_FOUND":
            raise HTTPException(
                status_code=404, detail="OpenChannelResult not found"
            ) from e
        raise _to_http(
            CorePcsError(code=e.code, message=e.message, status=422)
        ) from e

    return OpenChannelDeleteResponse(
        result_id=record.open_channel_id,
        tag_number=record.tag_number,
        sign_status=record.sign_status.value,
        deleted_at=record.updated_at,
    )


__all__ = ["router"]