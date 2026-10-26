"""变更单**关闭路径**的真库用例（TODO-080 第 2 条 · TODO-081）。

## 为什么单独立一个文件

原先这批行为由 `tests/services/test_change_notice_service.py` 里的
**假 Session**（`_FakeSession` + 假模型）覆盖 ⇒ 那批用例**零覆盖**：
假 Session 结构上看不见 DB 层的唯一约束 / 外键 / NOT NULL ⇒ 断言「写了两行」
其实只证明了「往内存 dict 里塞了两行」（TODO-080 第 2 条）。

⇒ 现在这些行为由**真库**（`sqlite+aiosqlite` + `SA_Base.metadata.create_all`）
覆盖，并且**已弃用的** `approve_change_notice`（绕过矩阵的第二条关闭路径，
且**连记录都不关**）已**删除**（TODO-081 选项①）。

## 覆盖的行为

| # | 行为 |
|---|---|
| 1 | 签完最后一步 ⇒ 记录 CHANGED → CHECKED + `change_resolved_by` + 观测 COMPLETED |
| 2 | 关闭 ⇒ **通知行**写在同一事务里（收件人 = 项目的 DESIGNER） |
| 3 | 没人可通知时**不抛**（「没有 DESIGNER」是一种状态，不是一次失败） |
| 4 | 关闭失败（找不到绑定记录）⇒ **不**写观测、**不**关记录 |
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
    WorkflowProgressState,
    WorkflowType,
)
from app.models.notification import Notification, NotificationKind
from app.models.project import Project, UserProject, Workspace
from app.models.workflow_progress import WorkflowProgress
from app.services.change_notice_service import (
    ChangeNoticeService,
    ChangeType,
    TriggeredBy,
)
from app.services.exceptions import PcsError

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
        project_name="关闭路径测试项目",
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


async def _make_changed_record(db, project: Project) -> ReliefResult:
    rec = ReliefResult(
        project_id=project.project_id,
        workspace_id=uuid.uuid4(),
        source_equipment_id=uuid.uuid4(),
        relief_scenario=ReliefScenario.FIRE,
        sign_status=RecordSignStatus9.CHANGED,
        record_hash="h1",
    )
    db.add(rec)
    await db.flush()
    return rec


async def _create_notice(db, project: Project, rec: ReliefResult) -> dict:
    result = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project.project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="管径修正",
        triggered_by=TriggeredBy.MANUAL,
        actor=_Actor(uuid.uuid4()),
        record_table=ReliefResult,
    )
    await db.commit()
    return result


async def test_close_on_approved_closes_the_record_and_the_observation(db):
    """签完最后一步（= `close_on_approved`）⇒ 记录 CHECKED + 观测 COMPLETED。"""
    project = await _make_project(db)
    rec = await _make_changed_record(db, project)
    created = await _create_notice(db, project, rec)

    deliverable = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == created["deliverable_id"]
            )
        )
    ).scalar_one()

    result = await ChangeNoticeService.close_on_approved(
        db, deliverable=deliverable, actor_user_id=uuid.uuid4()
    )
    await db.commit()

    assert result["from"] == "CHANGED"
    assert result["to"] == "CHECKED"
    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED.value
    assert rec.change_resolved_by

    rows = (
        await db.execute(
            select(WorkflowProgress).where(
                WorkflowProgress.workflow_type == WorkflowType.CHANGE_NOTICE,
                WorkflowProgress.workflow_id == created["deliverable_id"],
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].step_status == WorkflowProgressState.COMPLETED


async def test_close_on_approved_writes_the_notification_row(db, make_user):
    """⚠️ 关闭 ⇒ **通知行**写在同一事务里（收件人 = 项目的 DESIGNER）。

    ⚠️ 这段逻辑原先在**已弃用**的 `approve_change_notice` 里 ⇒ **真实路径**
    （sign_step → close_on_approved）**不通知任何人** ⇒ 用户永远不知道
    「变更被批准了」⇒ 随该方法删除而迁到真实路径上（TODO-080 第 2 条）。

    ⇒ 收件人 = 全局角色是 DESIGNER **且** 有项目授权的人；**复核人不是受众**
    （复核人不需要重算这条记录）。
    """
    project = await _make_project(db)
    # ⚠️ 收件人解析要读 **`users.roles`** ⇒ 必须有**真的**用户行
    #    （只写 user_projects 不够 —— 见 conftest 的 make_user 注释）。
    designer_id = await make_user("designer-for-cn", ["DESIGNER"])
    reviewer_id = await make_user("reviewer-for-cn", ["REVIEWER"])
    db.add(
        UserProject(
            user_id=designer_id,
            project_id=project.project_id,
            role_in_project="DESIGNER",
        )
    )
    db.add(
        UserProject(
            user_id=reviewer_id,
            project_id=project.project_id,
            role_in_project="VIEWER",
        )
    )
    rec = await _make_changed_record(db, project)
    created = await _create_notice(db, project, rec)

    deliverable = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == created["deliverable_id"]
            )
        )
    ).scalar_one()
    result = await ChangeNoticeService.close_on_approved(
        db, deliverable=deliverable, actor_user_id=uuid.uuid4()
    )
    await db.commit()

    # 通知**载荷**由调用方在 commit 之后推送 ⇒ 这里断言「载荷非空」+
    # 「通知行已落库」（推送在 sign_step 里做）。
    assert result["pending_notifications"], "关闭变更单必须有待推的通知载荷"

    rows = (
        await db.execute(
            select(Notification).where(Notification.recipient_id == designer_id)
        )
    ).scalars().all()
    assert rows, "关闭变更单必须写通知行（收件人 = 项目的 DESIGNER）"
    mine = rows[0]
    assert mine.kind == NotificationKind.CHANGE_NOTICE_APPROVED
    assert mine.detail_json["deliverable_id"] == str(deliverable.deliverable_id)

    reviewer_rows = (
        await db.execute(
            select(Notification).where(Notification.recipient_id == reviewer_id)
        )
    ).scalars().all()
    assert not reviewer_rows, "复核人不是受众（只有要重算的设计人需要知道）"


async def test_close_on_approved_without_recipients_does_not_raise(db):
    """⚠️ 没人可通知时**不抛**（「没有 DESIGNER」是一种状态，不是一次失败）。"""
    project = await _make_project(db)
    rec = await _make_changed_record(db, project)
    created = await _create_notice(db, project, rec)

    deliverable = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == created["deliverable_id"]
            )
        )
    ).scalar_one()
    result = await ChangeNoticeService.close_on_approved(
        db, deliverable=deliverable, actor_user_id=uuid.uuid4()
    )
    await db.commit()

    assert result["to"] == "CHECKED"
    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHECKED.value


async def test_close_without_binding_writes_no_observation(db):
    """⚠️ 关闭失败（找不到绑定记录）⇒ **不**写观测、**不**关记录。"""
    project = await _make_project(db)
    rec = await _make_changed_record(db, project)

    deliverable = Deliverable(
        deliverable_id=uuid.uuid4(),
        project_id=project.project_id,
        deliverable_type="CHANGE_NOTICE",
        scope_type="CUSTOM",
        scope_value=f"CHANGE_NOTICE:ReliefResult:{rec.relief_id}:deadbeef",
        doc_no="CN-" + uuid.uuid4().hex.upper(),
        doc_no_mode="MANUAL",
        title="没有绑定的变更单",
        current_rev="0",
        version_purpose="ISSUED_FOR_CHANGE",
        sign_status=DeliverableSignStatus.PENDING,
        matrix_id=uuid.uuid4(),
    )
    db.add(deliverable)
    await db.flush()

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService.close_on_approved(
            db, deliverable=deliverable, actor_user_id=uuid.uuid4()
        )
    assert exc_info.value.code == "CHANGE_NOTICE_RECORD_LINK_MISSING"

    await db.refresh(rec)
    assert rec.sign_status == RecordSignStatus9.CHANGED.value, "关闭失败不许动记录"
    rows = (
        await db.execute(
            select(WorkflowProgress).where(
                WorkflowProgress.workflow_type == WorkflowType.CHANGE_NOTICE
            )
        )
    ).scalars().all()
    assert rows == [], "关闭失败不许写观测"
