"""「记录已对外生效」的两道门（TODO-082）。

## 原来这两道门**永远不触发**

`record.locked_by_deliverable` 全仓**只被读、从不被写 True** ⇒

- `record_cancellation_service.obsolete` 的「已绑定记录必须先建
  RECORD_CANCELLATION 变更单」⇒ **不存在**；
- `reversal_approval_service.request_reversal` 的「已对外生效只能走
  CHANGE_REVERSAL」⇒ **不存在**。

⇒ 任何记录都可以被**直接弃用**、被**直接撤销** ⇒ 「作废/撤销都要有凭证」这条
业务约束事实上不存在。

## 换成**真实可判定**的条件

「记录被一张 **APPROVED** 的交付物绑定」（`deliverable_record_bindings` ⋈
`deliverable_versions` ⋈ `deliverables`）。

⚠️ 判「APPROVED」而不是「有绑定」：一张**还没签完**的变更单也绑了记录 ⇒
用它当门禁 ⇒ 用户在变更单还没批准时就被挡住 ⇒ 流程走不动。

## 覆盖的行为

| # | 行为 |
|---|---|
| 1 | 记录被**已批准**的交付物绑定 ⇒ 直接弃用被拒（409） |
| 2 | 没有已批准的绑定 ⇒ 直接弃用**照常**（门不误伤） |
| 3 | 记录被**已批准**的交付物绑定 ⇒ 普通撤销被拒（409，只能走 CHANGE_REVERSAL） |
| 4 | 绑定**还没批准** ⇒ 普通撤销**放行**（门不误伤） |
"""
from __future__ import annotations

import uuid

import pytest

from app.models.calc import ReliefResult
from app.models.deliverable import (
    Deliverable,
    DeliverableRecordBinding,
    DeliverableVersion,
    SignatureMatrix,
)
from app.models.enums import (
    DeliverableSignStatus,
    RecordSignStatus9,
    ReliefScenario,
)
from app.models.project import Project, Workspace
from app.services.exceptions import PcsError
from app.services.record_cancellation_service import RecordCancellationService
from app.services.reversal_approval_service import ReversalApprovalService

pytestmark = pytest.mark.asyncio


class _Actor:
    def __init__(self, user_id: uuid.UUID) -> None:
        self.user_id = user_id
        self.role = "DESIGNER"
        self.username = "tester"


async def _make_project(db) -> Project:
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="对外生效门禁测试项目",
        owner_company="测试业主",
        location="测试地点",
        project_type="CHEMICAL",
        design_phase="FEED",
        unit_system="SI",
        workspace_id=ws.workspace_id,
    )
    db.add(proj)
    await db.flush()
    return proj


async def _make_record(db, project: Project, *, sign_status: str) -> ReliefResult:
    rec = ReliefResult(
        project_id=project.project_id,
        workspace_id=uuid.uuid4(),
        source_equipment_id=uuid.uuid4(),
        relief_scenario=ReliefScenario.FIRE,
        sign_status=RecordSignStatus9(sign_status),
        record_hash="h1",
    )
    db.add(rec)
    await db.flush()
    return rec


async def _bind_record_to_deliverable(
    db, project: Project, rec: ReliefResult, *, approved: bool
) -> Deliverable:
    """把记录绑到一张交付物（变更单）上；`approved` 决定那张单批没批。"""
    matrix = SignatureMatrix(
        matrix_name=f"矩阵-{uuid.uuid4().hex[:8]}",
        module="CHANGE_NOTICE",
        doc_type="CHANGE_NOTICE",
        version_purpose="ISSUED_FOR_CHANGE",
        steps_json=[{"step_order": 1, "sign_role": "APPROVER"}],
        status="ACTIVE",
    )
    db.add(matrix)
    await db.flush()
    deliverable = Deliverable(
        matrix_id=matrix.matrix_id,
        project_id=project.project_id,
        deliverable_type="CHANGE_NOTICE",
        scope_type="CUSTOM",
        scope_value=f"CHANGE_NOTICE:ReliefResult:{rec.relief_id}:{uuid.uuid4().hex[:8]}",
        doc_no=f"CN-{uuid.uuid4().hex.upper()}",
        doc_no_mode="MANUAL",
        title="变更单",
        current_rev="0",
        version_purpose="ISSUED_FOR_CHANGE",
        sign_status=(
            DeliverableSignStatus.APPROVED
            if approved
            else DeliverableSignStatus.PENDING
        ),
    )
    db.add(deliverable)
    await db.flush()
    version = DeliverableVersion(
        deliverable_id=deliverable.deliverable_id,
        rev="1",
        version_purpose="ISSUED_FOR_CHANGE",
        description="变更单版本",
        record_snapshot_json={},
        signature_summary_json={},
    )
    db.add(version)
    await db.flush()
    db.add(
        DeliverableRecordBinding(
            deliverable_version_id=version.version_id,
            record_type="ReliefResult",
            record_id=rec.relief_id,
            record_hash=rec.record_hash,
        )
    )
    await db.commit()
    return deliverable


async def test_obsolete_is_blocked_when_the_record_is_effectively_published(db):
    """RF-1：记录被**已批准**的交付物绑定 ⇒ 直接弃用被拒。"""
    project = await _make_project(db)
    rec = await _make_record(db, project, sign_status="CHECKED")
    await _bind_record_to_deliverable(db, project, rec, approved=True)

    with pytest.raises(PcsError) as exc_info:
        await RecordCancellationService.obsolete(
            db,
            record_id=rec.relief_id,
            actor=_Actor(uuid.uuid4()),
            reason="要弃用",
            record_table=ReliefResult,
        )
    assert exc_info.value.code == "RECORD_BOUND_USE_CHANGE_NOTICE"
    assert exc_info.value.status == 409


async def test_obsolete_is_allowed_when_no_approved_binding_exists(db):
    """RF-2：没有已批准的绑定 ⇒ 直接弃用**照常**（门不误伤）。"""
    project = await _make_project(db)
    rec = await _make_record(db, project, sign_status="CHECKED")

    result = await RecordCancellationService.obsolete(
        db,
        record_id=rec.relief_id,
        actor=_Actor(uuid.uuid4()),
        reason="要弃用",
        record_table=ReliefResult,
    )
    assert result["to"] == "OBSOLETE"


async def test_obsolete_is_allowed_when_the_binding_is_not_approved_yet(db):
    """RF-2b：绑定**还没批准** ⇒ 直接弃用照常（门不误伤）。

    ⚠️ 这条是「判 APPROVED 而不是『有绑定』」的理由：一张**还没签完**的变更单
    也绑了记录 ⇒ 用「有绑定」当门禁 ⇒ 用户在变更单还没批准时就被挡住。
    """
    project = await _make_project(db)
    rec = await _make_record(db, project, sign_status="CHECKED")
    await _bind_record_to_deliverable(db, project, rec, approved=False)

    result = await RecordCancellationService.obsolete(
        db,
        record_id=rec.relief_id,
        actor=_Actor(uuid.uuid4()),
        reason="要弃用",
        record_table=ReliefResult,
    )
    assert result["to"] == "OBSOLETE"


async def test_reversal_is_blocked_when_the_record_is_effectively_published(db):
    """RF-3：记录被**已批准**的交付物绑定 ⇒ 普通撤销被拒（只能走 CHANGE_REVERSAL）。"""
    project = await _make_project(db)
    rec = await _make_record(db, project, sign_status="CHANGED")
    await _bind_record_to_deliverable(db, project, rec, approved=True)

    with pytest.raises(PcsError) as exc_info:
        await ReversalApprovalService.request_reversal(
            db,
            record_id=rec.relief_id,
            actor=_Actor(uuid.uuid4()),
            reason="改错了",
            record_table=ReliefResult,
        )
    assert exc_info.value.code == "REVERSAL_LOCKED_USE_CHANGE_REVERSAL"
    assert exc_info.value.status == 409
    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHANGED.value, "被拒后状态不变"


async def test_reversal_is_allowed_when_the_binding_is_not_approved(db):
    """RF-4：绑定**还没批准** ⇒ 普通撤销放行（门不误伤）。"""
    project = await _make_project(db)
    rec = await _make_record(db, project, sign_status="CHANGED")
    await _bind_record_to_deliverable(db, project, rec, approved=False)

    result = await ReversalApprovalService.request_reversal(
        db,
        record_id=rec.relief_id,
        actor=_Actor(uuid.uuid4()),
        reason="改错了",
        record_table=ReliefResult,
    )
    assert result["to"] == "REVERSAL_PENDING"
