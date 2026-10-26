"""「已对外生效」的**逃生口**：CHANGE_REVERSAL 反向变更单（TODO-082 的已知代价）。

## 背景（裁决时已告知的代价）

TODO-082 把两道「已对外生效」的门换成**真实可判定**的条件（记录被一张
**APPROVED** 的交付物绑定）⇒ 门**真的会触发** ⇒

- 变更单**批准**后 ⇒ 记录「已对外生效」⇒ **普通撤销**（REVERSAL_APPROVAL）
  被拒（409 `REVERSAL_LOCKED_USE_CHANGE_REVERSAL`）；
- **直接弃用**也被拒（409 `RECORD_BOUND_USE_CHANGE_NOTICE`）。

⇒ 唯一出路 = **CHANGE_REVERSAL 反向变更单**（spec V1.0 §3.4）。

## 这条测试钉住的失败模式

| # | 失败模式 | 期望 |
|---|---|---|
| RF-1 | 门拒了普通撤销，但**错误消息没说该走哪条路** ⇒ 用户卡死 | 消息里点名 `CHANGE_REVERSAL` |
| RF-2 | 门拒了直接弃用，但**没给替代路径** | 消息里点名 `RECORD_CANCELLATION` |
| RF-3 | **逃生口本身不通**（CHANGE_REVERSAL 建单被 409/422 挡掉）⇒ 代价变成「死路」 | 建单**成功** |
| RF-4 | 逃生口的变更单批完后，记录**关不掉** | 记录回 `CHECKED` |

⚠️ 「逃生口」= 用户在 `CHANGE_PENDING` 里把数据**改回原值**（那本身就是一次
变更）⇒ 再用 CHANGE_REVERSAL 变更单走**正常的 3 级矩阵**审批 ⇒ 记录关闭。
⇒ 这条链路里的**每一步**都必须是真实路径（不是测试专用绕法）。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.calc import ReliefResult
from app.models.deliverable import Deliverable
from app.models.enums import (
    DeliverableSignStatus,
    RecordSignStatus9,
    ReliefScenario,
    StateTransition,
)
from app.models.project import Project, Workspace
from app.services.change_notice_service import (
    ChangeNoticeService,
    ChangeType,
    TriggeredBy,
)
from app.services.exceptions import PcsError
from app.services.record_cancellation_service import RecordCancellationService
from app.services.reversal_approval_service import ReversalApprovalService
from app.services.state_machine import StateMachineService

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
        project_name="逃生口测试项目",
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


async def _make_record(db, project: Project) -> ReliefResult:
    rec = ReliefResult(
        project_id=project.project_id,
        workspace_id=uuid.uuid4(),
        source_equipment_id=uuid.uuid4(),
        relief_scenario=ReliefScenario.FIRE,
        sign_status=RecordSignStatus9.CHECKED,
        record_hash="h0",
    )
    db.add(rec)
    await db.flush()
    return rec


async def _drive_change(db, rec: ReliefResult, *, new_hash: str) -> None:
    """走一次完整变更：CHECKED → CHANGE_PENDING →（改数据）→ CHANGED。"""
    sm = StateMachineService(db)
    actor_id = uuid.uuid4()
    await sm.transition(
        record=rec,
        transition=StateTransition.INITIATE_CHANGE,
        actor_user_id=actor_id,
        actor_role="DESIGNER",
        reason="改数据",
    )
    # ⚠️ **必须真的改过**（TODO-077：APPLY_CHANGE 拿当前哈希与 BEFORE_CHANGE
    #    快照的哈希比 ⇒ 相同 ⇒ 拒）
    rec.record_hash = new_hash
    await db.flush()
    await sm.transition(
        record=rec,
        transition=StateTransition.APPLY_CHANGE,
        actor_user_id=actor_id,
        actor_role="DESIGNER",
        reason="改完了",
    )
    await db.flush()


async def _create_and_approve_notice(
    db, project: Project, rec: ReliefResult, *, change_type: ChangeType
) -> Deliverable:
    """建一张变更单并**当场签完**（= APPROVED ⇒ 记录被绑 ⇒ 已对外生效）。"""
    created = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project.project_id,
        record_id=rec.relief_id,
        change_type=change_type,
        reason="变更原因",
        triggered_by=TriggeredBy.MANUAL,
        actor=_Actor(uuid.uuid4()),
        record_table=ReliefResult,
    )
    await db.commit()
    deliverable = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == created["deliverable_id"]
            )
        )
    ).scalar_one()
    # ⚠️ **真实路径**：`DeliverableService.sign_step` 签完最后一步 ⇒ 先把单
    #    推成 APPROVED ⇒ 再调 `close_on_approved`（这里照抄那一步）。
    deliverable.sign_status = DeliverableSignStatus.APPROVED
    await db.flush()
    await ChangeNoticeService.close_on_approved(
        db, deliverable=deliverable, actor_user_id=uuid.uuid4()
    )
    await db.commit()
    return deliverable


async def test_escape_hatch_end_to_end(db):
    """RF-1~RF-4：门拦住了普通路径 ⇒ CHANGE_REVERSAL 这条路**真的通**。"""
    project = await _make_project(db)
    rec = await _make_record(db, project)

    # ── 第一次变更：建单 + 签完 ⇒ 记录「已对外生效」 ────────────────────
    await _drive_change(db, rec, new_hash="h1")
    await _create_and_approve_notice(
        db, project, rec, change_type=ChangeType.DATA_CORRECTION
    )
    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED.value
    assert rec.locked_by_deliverable is True, "批准 ⇒ 已对外生效（TODO-090）"

    # ── 第二次变更（用户发现发布错了，要撤回） ─────────────────────────
    await _drive_change(db, rec, new_hash="h2")

    # RF-1：普通撤销被拒，且**消息点名** CHANGE_REVERSAL
    with pytest.raises(PcsError) as rev_exc:
        await ReversalApprovalService.request_reversal(
            db,
            record_id=rec.relief_id,
            actor=_Actor(uuid.uuid4()),
            reason="发布错了",
            record_table=ReliefResult,
        )
    assert rev_exc.value.code == "REVERSAL_LOCKED_USE_CHANGE_REVERSAL"
    assert rev_exc.value.status == 409
    assert "CHANGE_REVERSAL" in str(rev_exc.value), "必须说清该走哪条路"

    # RF-2：直接弃用也被拒，且**消息点名** RECORD_CANCELLATION
    with pytest.raises(PcsError) as obs_exc:
        await RecordCancellationService.obsolete(
            db,
            record_id=rec.relief_id,
            actor=_Actor(uuid.uuid4()),
            reason="要弃用",
            record_table=ReliefResult,
        )
    assert obs_exc.value.code == "RECORD_BOUND_USE_CHANGE_NOTICE"
    assert obs_exc.value.status == 409
    assert "RECORD_CANCELLATION" in str(obs_exc.value), "必须说清该走哪条路"

    # RF-3：**逃生口通** —— CHANGE_REVERSAL 反向变更单建得出来
    created = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project.project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.CHANGE_REVERSAL,
        reason="撤回已发布的内容",
        triggered_by=TriggeredBy.MANUAL,
        actor=_Actor(uuid.uuid4()),
        record_table=ReliefResult,
    )
    await db.commit()
    assert created["deliverable_id"]

    # RF-4：这张反向变更单签完 ⇒ 记录关闭（回 CHECKED）
    deliverable = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == created["deliverable_id"]
            )
        )
    ).scalar_one()
    await ChangeNoticeService.close_on_approved(
        db, deliverable=deliverable, actor_user_id=uuid.uuid4()
    )
    await db.commit()
    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED.value
