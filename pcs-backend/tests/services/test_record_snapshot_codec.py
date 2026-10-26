"""记录快照**数据编解码**（TODO-087）。

## 钉住的失败模式

| # | 失败模式 | 期望 |
|---|---|---|
| RF-1 | 快照 `data_snapshot_json` **恒为 `{}`** ⇒ 撤销/放弃**不恢复**任何数据 | 快照装着业务数据 |
| RF-2 | 快照把**主键 / 归属 / 状态机列**也装进去 ⇒ 恢复时改了记录的状态/归属 | 这些列**不**采集 |
| RF-3 | UUID / datetime / 枚举塞进 JSONB ⇒ 存不进去或**还原成字符串** | 打标签 + 按标签还原真类型 |
| RF-4 | 快照里的列在表上不存在 ⇒ 还原时炸 | 跳过（老快照不炸） |
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.models.calc import ReliefResult
from app.models.deliverable import RecordChangeSnapshot
from app.models.enums import RecordSignStatus9, ReliefScenario, SnapshotStatus
from app.models.project import Project, Workspace
from app.services.record_snapshot_codec import (
    apply_snapshot_data,
    capture_record_data,
    record_pk,
)

pytestmark = pytest.mark.asyncio


async def _make_project(db) -> Project:
    ws = Workspace(workspace_type="FORMAL", name=f"ws-{uuid.uuid4().hex[:8]}")
    db.add(ws)
    await db.flush()
    proj = Project(
        project_no=f"P-{uuid.uuid4().hex[:8]}",
        project_name="快照编解码测试项目",
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
        record_hash="h1",
        reactor_volume=1.5,
        tag_number="PSV-001",
    )
    db.add(rec)
    await db.flush()
    return rec


async def test_capture_record_data_captures_business_columns(db):
    """RF-1：快照**装着**记录的业务数据（不是空 dict）。"""
    project = await _make_project(db)
    rec = await _make_record(db, project)

    data = capture_record_data(rec)

    assert data, "快照数据不能是空的"
    assert data["reactor_volume"] == 1.5
    assert data["record_hash"] == "h1"
    assert data["tag_number"] == "PSV-001"


async def test_capture_skips_pk_ownership_and_state_columns(db):
    """RF-2：主键 / 归属 / 状态机流程列**不**进快照。"""
    project = await _make_project(db)
    rec = await _make_record(db, project)

    data = capture_record_data(rec)

    assert "relief_id" not in data, "主键不许进快照"
    assert "project_id" not in data, "归属列不许进快照"
    assert "workspace_id" not in data, "归属列不许进快照"
    assert "sign_status" not in data, "状态列不许进快照"
    assert "change_pending_since" not in data, "变更流程列不许进快照"
    assert "created_at" not in data, "审计列不许进快照"


async def test_capture_encodes_types_jsonb_cannot_hold(db):
    """RF-3：UUID / 枚举 / datetime 被打标签（JSONB 装不下原值）。"""
    project = await _make_project(db)
    rec = await _make_record(db, project)
    rec.change_pending_since = datetime(2026, 10, 26, 8, 30, tzinfo=UTC)

    data = capture_record_data(rec)

    assert data["source_equipment_id"] == {
        "__t__": "uuid",
        "v": str(rec.source_equipment_id),
    }
    assert data["relief_scenario"] == {"__t__": "enum", "v": "FIRE"}


async def test_apply_snapshot_data_restores_values_and_types(db):
    """RF-3：还原回**真类型**（不是字符串）。"""
    project = await _make_project(db)
    rec = await _make_record(db, project)
    equipment_id = rec.source_equipment_id

    data = capture_record_data(rec)

    # 改数据 ⇒ 改哈希
    rec.reactor_volume = 9.9
    rec.record_hash = "h2"
    rec.relief_scenario = ReliefScenario.UPSET
    rec.source_equipment_id = uuid.uuid4()

    restored = apply_snapshot_data(rec, data)

    assert restored > 0
    assert rec.reactor_volume == 1.5
    assert rec.record_hash == "h1"
    assert rec.relief_scenario == ReliefScenario.FIRE
    assert rec.source_equipment_id == equipment_id


async def test_apply_snapshot_data_skips_unknown_columns(db):
    """RF-4：快照里的列在表上不存在 ⇒ 跳过，不炸。"""
    project = await _make_project(db)
    rec = await _make_record(db, project)

    restored = apply_snapshot_data(rec, {"no_such_column": 1, "reactor_volume": 2.0})

    assert restored == 1
    assert rec.reactor_volume == 2.0


async def test_record_pk_reads_the_real_primary_key(db):
    """各表 PK 列名不同 ⇒ 按 mapper 取（不是 `record_id`）。"""
    project = await _make_project(db)
    rec = await _make_record(db, project)

    assert record_pk(rec) == rec.relief_id


async def test_snapshot_row_round_trips_through_jsonb(db):
    """快照行**落库再读回** ⇒ 数据还在（JSONB 真能装下）。"""
    project = await _make_project(db)
    rec = await _make_record(db, project)

    snap = RecordChangeSnapshot(
        snapshot_id=uuid.uuid4(),
        record_type=type(rec).__name__,
        record_id=rec.relief_id,
        record_hash=rec.record_hash,
        data_snapshot_json=capture_record_data(rec),
        snapshot_reason="BEFORE_CHANGE",
        snapshot_source="MANUAL_CHANGE",
        snapshot_status=SnapshotStatus.ACTIVE.value,
    )
    db.add(snap)
    await db.commit()

    loaded = (
        await db.execute(
            select(RecordChangeSnapshot).where(
                RecordChangeSnapshot.snapshot_id == snap.snapshot_id
            )
        )
    ).scalar_one()
    assert loaded.data_snapshot_json["reactor_volume"] == 1.5
    assert loaded.data_snapshot_json["source_equipment_id"]["__t__"] == "uuid"


async def test_decimal_and_float_round_trip(db):
    """Decimal 也要能装进 JSONB 并还原（金额类字段）。"""
    from app.services.record_snapshot_codec import _decode, _encode

    encoded = _encode(Decimal("1.25"))
    assert encoded == {"__t__": "decimal", "v": "1.25"}
    assert _decode(encoded, None) == Decimal("1.25")
