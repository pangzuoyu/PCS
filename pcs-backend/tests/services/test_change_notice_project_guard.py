"""变更单 service 层的**项目一致性**守卫（TODO-084 第 2 条）。

## 为什么 service 层要自己查

`create_change_notice(db, project_id=..., record_id=...)` 是**对外入口**
（不只是端点的内部实现）⇒ 端点层传对了**不等于** service 层传对了。
今天端点传的是 `record.project_id`（对），但 service **不查** ⇒ 将来任何
调用方传错 project_id ⇒ 变更单会建到**别的项目**名下，而它的 binding 指向
一条**不属于该项目的记录** ⇒ 关闭凭证跨项目 ⇒ 审计链断。

⇒ service 层自查：`record.project_id != project_id` ⇒ 422
`CHANGE_NOTICE_PROJECT_MISMATCH`，**且一行都不写**。

## 为什么用**真库**而不是假 Session

这个守卫要验的是「**没写任何行**」⇒ 假 Session 看不见写没写 ⇒ 必须真库
（`tests/services/test_change_notice_service.py` 那批假 Session 用例正是
TODO-080 第 2 条记的「零覆盖」）。
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.calc import ReliefResult
from app.models.deliverable import Deliverable
from app.models.enums import RecordSignStatus9, ReliefScenario
from app.models.project import Project, Workspace
from app.services.change_notice_service import (
    ChangeNoticeService,
    ChangeType,
    TriggeredBy,
)
from app.services.exceptions import PcsError

pytestmark = pytest.mark.asyncio


class _Actor:
    """最小 actor（service 只用 user_id / role）。"""

    def __init__(self, user_id: uuid.UUID) -> None:
        self.user_id = user_id
        self.role = "DESIGNER"
        self.username = "tester"


async def _make_project(db, name: str) -> Project:
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name=name,
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


async def test_create_change_notice_rejects_a_foreign_project_id(db):
    """⚠️ `project_id` 与记录所属项目**不一致** ⇒ 422，且**一行都不写**。"""
    owner = await _make_project(db, "记录所属项目")
    other = await _make_project(db, "别的项目")
    rec = await _make_changed_record(db, owner)

    with pytest.raises(PcsError) as exc:
        await ChangeNoticeService.create_change_notice(
            db,
            project_id=other.project_id,  # ⚠️ 错的
            record_id=rec.relief_id,
            change_type=ChangeType.DATA_CORRECTION,
            reason="跨项目建单",
            triggered_by=TriggeredBy.MANUAL,
            actor=_Actor(uuid.uuid4()),
            record_table=ReliefResult,
        )

    assert exc.value.code == "CHANGE_NOTICE_PROJECT_MISMATCH"
    assert exc.value.status == 422

    rows = (
        await db.execute(select(Deliverable).where(Deliverable.project_id == other.project_id))
    ).scalars().all()
    assert rows == [], "校验失败 ⇒ 不许留下任何行"


async def test_create_change_notice_accepts_the_own_project_id(db):
    """反向对照：项目一致 ⇒ 正常建单（别把守卫修成永远拒绝）。"""
    owner = await _make_project(db, "记录所属项目")
    rec = await _make_changed_record(db, owner)

    result = await ChangeNoticeService.create_change_notice(
        db,
        project_id=owner.project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="正常建单",
        triggered_by=TriggeredBy.MANUAL,
        actor=_Actor(uuid.uuid4()),
        record_table=ReliefResult,
    )
    assert result["deliverable_id"]
    await db.commit()
