"""变更单的**可读编号**（TODO-073）。

## 为什么

变更单的 `doc_no` 此前是 `CN-{变更单自己的 32 位 uuid hex}` ⇒ 它只保证
**唯一**，但它是给用户看的编号 ⇒ 一串 32 位 hex **不可读**、不可口述、不可
检索 ⇒ 用户报「变更单 CN-3F2A…」时谁都对不上。

⇒ 走**编号模板**（`numbering_templates` + `segments_json`）⇒ 编号形如
`P-20261026-0001-CHANGE_NOTICE-1`（项目号 + 文档类型 + 序号）⇒ 可读、可
口述、可检索。

## 覆盖的行为

| # | 行为 |
|---|---|
| 1 | 编号**可读**（含项目号 / 文档类型 / 序号），不再是 32 位 hex |
| 2 | 同一项目的两张变更单 ⇒ 序号**递增**（1、2） |
| 3 | 变更单**绑了**编号模板（`numbering_template_id` 非空） |
| 4 | 编号模板**幂等**（两次建单 ⇒ 同一个模板 ⇒ 同一号段） |
"""
from __future__ import annotations

import uuid

import pytest
from sqlalchemy import select

from app.models.calc import ReliefResult
from app.models.config_domain import NumberingTemplate
from app.models.enums import RecordSignStatus9, ReliefScenario
from app.models.project import Project, Workspace
from app.services.change_notice_service import (
    ChangeNoticeService,
    ChangeType,
    TriggeredBy,
)

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
        project_name="变更单编号测试项目",
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


async def test_change_notice_doc_no_is_readable(db):
    """RF-1：编号**可读** —— 项目号 + 文档类型 + 序号。"""
    project = await _make_project(db)
    rec = await _make_changed_record(db, project)
    created = await _create_notice(db, project, rec)

    doc_no = created["doc_no"]
    assert project.project_no in doc_no, f"编号必须含项目号：{doc_no!r}"
    assert "CHANGE_NOTICE" in doc_no, f"编号必须含文档类型：{doc_no!r}"
    assert doc_no.endswith("-1"), f"首张变更单的序号必须是 1：{doc_no!r}"
    assert "CN-" not in doc_no, f"不能再用 uuid hex 编号：{doc_no!r}"


async def test_change_notice_doc_no_sequence_increments(db):
    """RF-2：同一项目的两张变更单 ⇒ 序号**递增**。"""
    project = await _make_project(db)
    rec1 = await _make_changed_record(db, project)
    first = await _create_notice(db, project, rec1)

    rec2 = await _make_changed_record(db, project)
    second = await _create_notice(db, project, rec2)

    assert first["doc_no"].endswith("-1")
    assert second["doc_no"].endswith("-2")


async def test_change_notice_binds_the_numbering_template(db):
    """RF-3：变更单**绑了**编号模板（否则下次签发版本时不会重新取号）。"""
    project = await _make_project(db)
    rec = await _make_changed_record(db, project)
    created = await _create_notice(db, project, rec)

    from app.models.deliverable import Deliverable

    deliverable = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == created["deliverable_id"]
            )
        )
    ).scalar_one()
    assert deliverable.numbering_template_id is not None, "变更单必须绑编号模板"
    assert deliverable.doc_no_mode == "TEMPLATE"


async def test_change_notice_numbering_template_is_reused(db):
    """RF-4：编号模板**幂等**（两张单 ⇒ 同一个模板 ⇒ 同一号段）。"""
    project = await _make_project(db)
    rec1 = await _make_changed_record(db, project)
    first = await _create_notice(db, project, rec1)
    rec2 = await _make_changed_record(db, project)
    second = await _create_notice(db, project, rec2)

    from app.models.deliverable import Deliverable

    rows = (
        await db.execute(
            select(Deliverable.numbering_template_id).where(
                Deliverable.deliverable_id.in_(
                    [first["deliverable_id"], second["deliverable_id"]]
                )
            )
        )
    ).scalars().all()
    assert len(set(rows)) == 1, "两张变更单必须用同一个编号模板（否则号段各走各的）"

    templates = (await db.execute(select(NumberingTemplate))).scalars().all()
    assert len(templates) == 1, f"编号模板必须**只有一份**（幂等）：{len(templates)}"
