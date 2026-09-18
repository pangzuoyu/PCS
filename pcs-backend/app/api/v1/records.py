"""Records API（Sprint 2）。

6 端点：列表/详情/创建/转移/废弃/快照查询。

注意：
- POST /piping 是 Sprint 2 dev-only，临时用于驱动状态机集成测试；
  Sprint 3 由 `app.services.record_service.RecordService.create_piping` 替换。
- GET /piping、POST /{id}/transition、DELETE /{id}、GET /{id}/snapshots 为正式功能。
"""

from __future__ import annotations

import uuid
from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_workspace, require_formal_workspace
from app.db.session import get_db
from app.models.calc import PipingResult
from app.models.deliverable import RecordChangeSnapshot
from app.models.enums import StateTransition
from app.models.project import Workspace
from app.schemas.records import RecordTransitionRequest
from app.services.state_machine import StateMachineService

router = APIRouter(prefix="/records", tags=["records"])


@router.get("/piping", response_model=list[dict])
async def list_piping(
    workspace_id: uuid.UUID = Query(...),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_db),
):
    ws = await get_workspace(workspace_id, session)
    rows = (
        await session.execute(
            select(PipingResult)
            .where(PipingResult.workspace_id == ws.workspace_id)
            .order_by(PipingResult.seq_no)
            .limit(limit)
            .offset(offset)
        )
    ).scalars().all()
    return [
        {
            "pipe_id": str(r.pipe_id),
            "line_no": r.line_no,
            "sign_status": (
                r.sign_status.value if hasattr(r.sign_status, "value") else r.sign_status
            ),
            "approval_step": r.approval_step,
            "locked_by_deliverable": r.locked_by_deliverable,
        }
        for r in rows
    ]


@router.get("/piping/{pipe_id}", response_model=dict)
async def get_piping(
    pipe_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db),
):
    ws = await get_workspace(workspace_id, session)
    rec = (
        await session.execute(
            select(PipingResult).where(
                PipingResult.pipe_id == pipe_id,
                PipingResult.workspace_id == ws.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if rec is None:
        raise HTTPException(404, "piping record not found")
    return {
        "pipe_id": str(rec.pipe_id),
        "line_no": rec.line_no,
        "sign_status": (
            rec.sign_status.value if hasattr(rec.sign_status, "value") else rec.sign_status
        ),
        "approval_step": rec.approval_step,
        "locked_by_deliverable": rec.locked_by_deliverable,
        "seq_no": rec.seq_no,
        "source_pid": rec.source_pid,
    }


@router.post("/piping", response_model=dict)
async def create_piping(
    payload: dict,
    workspace: Workspace = Depends(require_formal_workspace),
    user_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db),
):
    """Sprint 2 dev-only：测试驱动用。Sprint 3 替换为 RecordService.create_piping。"""
    rec = PipingResult(
        project_id=uuid.UUID(payload["project_id"]),
        workspace_id=workspace.workspace_id,
        seq_no=payload.get("seq_no", 0),
        line_no=payload["line_no"],
        line_size=payload.get("line_size", ""),
        material_class=payload.get("material_class", "A1"),
        fluid_code=payload.get("fluid_code", ""),
        fluid_name=payload.get("fluid_name", ""),
        fluid_phase=payload.get("fluid_phase", "L"),
        fluid_category=payload.get("fluid_category", "NORMAL"),
        source_pid=payload.get("source_pid", ""),
        line_from=payload.get("line_from", ""),
        line_to=payload.get("line_to", ""),
        norm_oper_press=float(payload.get("norm_oper_press", 1.0)),
        max_oper_press=float(payload.get("max_oper_press", 1.0)),
        norm_oper_temp=float(payload.get("norm_oper_temp", 40.0)),
        max_oper_temp=float(payload.get("max_oper_temp", 80.0)),
        design_press=float(payload.get("design_press", 1.0)),
        design_temp=float(payload.get("design_temp", 100.0)),
        piping_category=payload.get("piping_category", "GC2"),
        pressure_test_medium=payload.get("pressure_test_medium", "WATER"),
        pressure_test_press=float(payload.get("pressure_test_press", 1.0)),
        check_class=payload.get("check_class", "II"),
        created_by=user_id,
    )
    session.add(rec)
    await session.flush()
    await session.commit()
    return {"pipe_id": str(rec.pipe_id), "sign_status": rec.sign_status.value}


@router.post("/piping/{pipe_id}/transition", response_model=dict)
async def transition_piping(
    pipe_id: uuid.UUID,
    payload: RecordTransitionRequest,
    workspace_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Query(...),
    actor_role: str = Query("DESIGNER"),
    session: AsyncSession = Depends(get_db),
):
    """管路记录状态机迁移（DRAFT → REVIEWED → APPROVED → ...）。

    约束：
    1. 仅允许 FORMAL workspace（require_formal_workspace 强校验）
    2. workspace_id + pipe_id 双键查 PipingResult（不存在 → 404）
    3. 调 StateMachineService.transition，非法迁移 → 409
    4. 提交由本端点负责（session.commit()）

    actor_role 默认 DESIGNER（审核/批准时由调用方传 APPROVER 等）。
    """
    ws = await require_formal_workspace(await get_workspace(workspace_id, session))
    rec = (
        await session.execute(
            select(PipingResult).where(
                PipingResult.pipe_id == pipe_id,
                PipingResult.workspace_id == ws.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if rec is None:
        raise HTTPException(404, "piping record not found")
    svc = StateMachineService(session)
    try:
        await svc.transition(
            record=rec,
            transition=cast(StateTransition, payload.transition),
            actor_user_id=user_id,
            actor_role=actor_role,
            reason=payload.reason,
        )
    except Exception as e:
        raise HTTPException(status_code=409, detail=str(e)) from e
    await session.commit()
    return {"pipe_id": str(rec.pipe_id), "sign_status": rec.sign_status.value}


@router.delete("/piping/{pipe_id}", response_model=dict)
async def obsolete_piping(
    pipe_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(...),
    user_id: uuid.UUID = Query(...),
    actor_role: str = Query("DESIGNER"),
    reason: str = Query(""),
    session: AsyncSession = Depends(get_db),
):
    """管路记录作废（DELETE，状态机迁移至 OBSOLETE）。

    - 仅允许 FORMAL workspace
    - workspace_id + pipe_id 双键查 PipingResult（不存在 → 404）
    - 调 StateMachineService.transition(OBSOLETE)，失败 → 409
    - reason 必传 Query（默认空串），记录到状态机迁移 reason 字段供审计追溯
    - 提交由本端点负责（session.commit()）

    与 `transition_piping` 区别：本端点固定 transition=OBSOLETE，semantically 是
    "软删除"，不真删 PipingResult 行（保留审计快照）。
    """
    ws = await require_formal_workspace(await get_workspace(workspace_id, session))
    rec = (
        await session.execute(
            select(PipingResult).where(
                PipingResult.pipe_id == pipe_id,
                PipingResult.workspace_id == ws.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if rec is None:
        raise HTTPException(404, "piping record not found")
    svc = StateMachineService(session)
    await svc.transition(
        record=rec,
        transition=StateTransition.OBSOLETE,
        actor_user_id=user_id,
        actor_role=actor_role,
        reason=reason,
    )
    await session.commit()
    return {"pipe_id": str(rec.pipe_id), "sign_status": rec.sign_status.value}


@router.get("/piping/{pipe_id}/snapshots", response_model=list[dict])
async def list_snapshots(
    pipe_id: uuid.UUID,
    workspace_id: uuid.UUID = Query(...),
    session: AsyncSession = Depends(get_db),
):
    """列出管路记录的所有变更快照（按 created_at desc）。

    步骤：
    1. 校验 workspace + 查 PipingResult（不存在 → 404 piping record not found）
    2. 列 RecordChangeSnapshot（record_type='PipingResult' + record_id=pipe_id）
    3. 按 created_at desc 排序，返回 {snapshot_id, snapshot_reason, snapshot_status,
       snapshot_source, created_at} 列表

    workspace 隔离：仅查询 workspace_id 下的 PipingResult，越权访问 → 404。
    """
    ws = await get_workspace(workspace_id, session)
    rec = (
        await session.execute(
            select(PipingResult).where(
                PipingResult.pipe_id == pipe_id,
                PipingResult.workspace_id == ws.workspace_id,
            )
        )
    ).scalar_one_or_none()
    if rec is None:
        raise HTTPException(404, "piping record not found")
    snaps = (
        await session.execute(
            select(RecordChangeSnapshot)
            .where(
                RecordChangeSnapshot.record_type == "PipingResult",
                RecordChangeSnapshot.record_id == pipe_id,
            )
            .order_by(RecordChangeSnapshot.created_at.desc())
        )
    ).scalars().all()
    return [
        {
            "snapshot_id": str(s.snapshot_id),
            "snapshot_reason": s.snapshot_reason,
            "snapshot_status": s.snapshot_status,
            "snapshot_source": s.snapshot_source,
            "created_at": s.created_at.isoformat() if s.created_at else None,
        }
        for s in snaps
    ]