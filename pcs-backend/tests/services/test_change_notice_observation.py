"""变更单的观测写入点（ADR-0047 §① 写入点 2a / 2b · TODO-057 · P9A-DLV-007）。

CHANGE_NOTICE 工作流回答的是「**这张变更单**走到哪了」（发起 → 关闭）——
那是一个**单步**业务流程 ⇒ 只写 1 行（`step_order=1`）。

⚠️ `workflow_id` 是**变更单自己的 deliverable_id**（不是版本 id）——
`workflow_progress_service._resolve` 对 CHANGE_NOTICE 走 `deliverables` 表。
（SIGN / CUSTOMER_APPROVAL_PROXY 走的是版本 id ⇒ 三类 id 语义不同，
这正是 TODO-065 聚合端点存在的原因。）

## 事务边界（ADR-0047 §②③）

观测写与业务变更**同一事务** ⇒ 观测写失败 ⇒ 建单一起回滚。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.calc import ReliefResult
from app.models.deliverable import Deliverable
from app.models.enums import WorkflowProgressState, WorkflowType
from app.models.workflow_progress import WorkflowProgress
from app.services import change_notice_service as cn_mod
from app.services.change_notice_service import (
    ChangeNoticeService,
    ChangeType,
    TriggeredBy,
)
from app.services.exceptions import PcsError


class _Actor:
    """触发者（只需 user_id）。"""

    def __init__(self) -> None:
        self.user_id = uuid.uuid4()
        self.role = "REVIEWER"


async def _make_changed_record(db, *, project_id: uuid.UUID) -> ReliefResult:
    """一条 CHANGED 状态的业务记录（真库行）。"""
    rec = ReliefResult(
        project_id=project_id,
        workspace_id=uuid.uuid4(),
        source_equipment_id=uuid.uuid4(),
        sign_status="CHANGED",
        relief_scenario="FIRE",
    )
    db.add(rec)
    await db.flush()
    return rec


async def _create_notice(db, *, project_id: uuid.UUID, record_id: uuid.UUID) -> dict:
    return await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=record_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="管径修正",
        triggered_by=TriggeredBy.MANUAL,
        actor=_Actor(),
        record_table=ReliefResult,
    )


async def _observation_rows(db, *, workflow_id: uuid.UUID) -> list[WorkflowProgress]:
    return (
        await db.execute(
            select(WorkflowProgress).where(
                WorkflowProgress.workflow_id == workflow_id
            )
        )
    ).scalars().all()


# ---------------------------------------------------------------------------
# 写入点 2a：创建
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_writes_one_pending_observation_row(db, project_id):
    """建单 ⇒ `workflow_progress` 有一行 CHANGE_NOTICE / PENDING。"""
    rec = await _make_changed_record(db, project_id=project_id)

    result = await _create_notice(
        db, project_id=project_id, record_id=rec.relief_id
    )

    rows = await _observation_rows(db, workflow_id=result["deliverable_id"])
    assert len(rows) == 1
    row = rows[0]
    assert row.workflow_type == WorkflowType.CHANGE_NOTICE
    assert row.step_order == 1
    assert row.step_role == "CHANGE_NOTICE"
    # ⚠️ 建单只是**发起**了流程 —— 不是完成（RF-5）
    assert row.step_status == WorkflowProgressState.PENDING
    assert row.project_id == project_id
    assert row.completed_at is None


@pytest.mark.asyncio
async def test_create_observation_failure_rolls_back_the_change_notice(
    db, project_id, monkeypatch
):
    """⚠️ 观测写失败 ⇒ 建单**整体回滚**（同一事务，RF-6）。

    观测层不可信的代价远高于「少一次 INSERT」——所以观测写失败必须
    把业务变更一起带走，绝不允许「业务成了但观测缺了」。
    """
    rec = await _make_changed_record(db, project_id=project_id)

    async def _boom(**kwargs):
        raise RuntimeError("观测写失败")

    monkeypatch.setattr(cn_mod, "record_step", _boom)

    with pytest.raises(RuntimeError):
        await _create_notice(db, project_id=project_id, record_id=rec.relief_id)

    await db.rollback()
    assert (await db.execute(select(Deliverable))).scalars().all() == []
    assert (await db.execute(select(WorkflowProgress))).scalars().all() == []


# ---------------------------------------------------------------------------
# 写入点 2b：自动关闭
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_approve_marks_observation_completed(db, project_id):
    """审批通过（自动关闭）⇒ 观测行变 COMPLETED 且 `completed_at` 非空。"""
    rec = await _make_changed_record(db, project_id=project_id)
    created = await _create_notice(
        db, project_id=project_id, record_id=rec.relief_id
    )

    await ChangeNoticeService.approve_change_notice(
        db,
        deliverable_id=created["deliverable_id"],
        actor=_Actor(),
        record_table=ReliefResult,
    )

    rows = await _observation_rows(db, workflow_id=created["deliverable_id"])
    assert len(rows) == 1
    assert rows[0].step_status == WorkflowProgressState.COMPLETED
    assert rows[0].completed_at is not None


@pytest.mark.asyncio
async def test_approve_failure_writes_no_observation(db, project_id):
    """⚠️ 审批失败 ⇒ **不**写观测（不能给没关闭的变更单标「已完成」）。"""
    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService.approve_change_notice(
            db,
            deliverable_id=uuid.uuid4(),
            actor=_Actor(),
            record_table=ReliefResult,
        )
    assert exc_info.value.status == 404
    assert (await db.execute(select(WorkflowProgress))).scalars().all() == []
