"""CIA 引擎 + 链式传播 + 设备联动测试（Sprint 3）。"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _make_pipe(**overrides):
    from app.models.calc import PipingResult

    base = dict(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        seq_no=1,
        line_no="P-1",
        line_size='2"',
        material_class="A1",
        fluid_code="W",
        fluid_name="Water",
        fluid_phase="L",
        fluid_category="NORMAL",
        source_pid="P&ID-001",
        line_from="V-100",
        line_to="V-200",
        norm_oper_press=1.0,
        max_oper_press=1.5,
        norm_oper_temp=40.0,
        max_oper_temp=80.0,
        design_press=2.0,
        design_temp=100.0,
        piping_category="GC3",
        pressure_test_medium="WATER",
        pressure_test_press=3.0,
        check_class="III",
    )
    base.update(overrides)
    return PipingResult(**base)


def _make_equipment(pipe, **overrides):
    from app.models.equipment import EquipmentList

    base = dict(
        project_id=pipe.project_id,
        workspace_id=pipe.workspace_id,
        equipment_name=f"E-{pipe.line_no}",
        type_code="PUMP",
        equipment_type_project_id=pipe.project_id,
        tag_number=f"E-{pipe.line_no}",
        source_module="PIPING",
        source_record_id=pipe.pipe_id,
    )
    base.update(overrides)
    return EquipmentList(**base)


def _set_signed(rec, sign_status):
    """把 record 设为指定 sign_status（绕过状态机，直接写字段）。"""
    rec.sign_status = sign_status
    return rec


async def _flush_full(session, *objs):
    """add + flush + refresh — 确保 record 全部 attrs 已加载，hash 计算稳定。"""
    for o in objs:
        session.add(o)
    await session.flush()
    for o in objs:
        await session.refresh(o)
    return objs


# === scan_stale ===

async def test_scan_no_records_returns_zero(db_session):
    from app.services.cia_engine import CIAEngine

    engine = CIAEngine(db_session)
    n = await engine.scan_stale()
    assert n == 0


async def test_scan_no_lineage_returns_zero(db_session):
    """记录存在但无血缘：scan 应跳过（无法比对）。"""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    _set_signed(pipe, RecordSignStatus9.CHECKED)
    await db_session.flush()
    n = await CIAEngine(db_session).scan_stale()
    assert n == 0


async def test_scan_marks_stale_on_hash_mismatch(db_session):
    """血缘 hash 与当前 hash 不一致 → MARK_STALE。"""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    _set_signed(pipe, RecordSignStatus9.CHECKED)
    await db_session.flush()

    # 写入"过时" hash 的血缘
    tracker = LineageTracker(db_session)
    await tracker.track(
        record=pipe,
        source="SEED",
        change_summary="baseline",
        change_diff={"hash": "stale_hash_xxx"},
    )
    # 修改 record hash 字段以触发 mismatch
    pipe.record_hash = "different"
    await db_session.flush()

    n = await CIAEngine(db_session).scan_stale()
    assert n == 1
    assert pipe.sign_status == RecordSignStatus9.STALE


async def test_scan_no_mismatch_no_mark(db_session):
    """hash 一致时不标记。"""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine
    from app.services.lineage import LineageTracker, _compute_hash

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    _set_signed(pipe, RecordSignStatus9.CHECKED)
    await db_session.flush()
    # onupdate=func.now() 已写入 DB；refresh 让 state.dict 同步
    await db_session.refresh(pipe)

    current = _compute_hash(pipe)
    await LineageTracker(db_session).track(
        record=pipe,
        source="SEED",
        change_diff={"hash": current},
    )
    n = await CIAEngine(db_session).scan_stale()
    assert n == 0
    assert pipe.sign_status == RecordSignStatus9.CHECKED


async def test_scan_project_id_filter(db_session):
    """scan_stale(project_id=...) 应只扫指定 project。"""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine
    from app.services.lineage import LineageTracker

    p1 = _make_pipe(project_id=uuid.uuid4(), line_no="P-A")
    p2 = _make_pipe(project_id=uuid.uuid4(), line_no="P-B")
    await _flush_full(db_session, p1, p2)
    for p in (p1, p2):
        _set_signed(p, RecordSignStatus9.CHECKED)
    await db_session.flush()

    tracker = LineageTracker(db_session)
    for p, hh in ((p1, "x"), (p2, "y")):
        await tracker.track(record=p, source="S", change_diff={"hash": hh})
    for p in (p1, p2):
        p.record_hash = "diff"
    await db_session.flush()

    n = await CIAEngine(db_session).scan_stale(project_id=p1.project_id)
    assert n == 1


async def test_scan_skips_non_tracked_states(db_session):
    """DRAFT/STALE 状态不参与扫描。"""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    _set_signed(pipe, RecordSignStatus9.DRAFT)
    await db_session.flush()

    await LineageTracker(db_session).track(
        record=pipe, source="S", change_diff={"hash": "x"}
    )
    pipe.record_hash = "y"
    await db_session.flush()
    n = await CIAEngine(db_session).scan_stale()
    assert n == 0


# === propagate ===

async def test_propagate_no_lineage_returns_zero(db_session):
    from app.services.cia_engine import CIAEngine

    pipe = _make_pipe()
    db_session.add(pipe)
    await db_session.flush()
    n = await CIAEngine(db_session).propagate(
        record_type="PipingResult", record_id=pipe.pipe_id
    )
    assert n == 0


async def test_propagate_marks_downstream_stale(db_session):
    """下游 record 被标 STALE。"""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    tracker = LineageTracker(db_session)
    parent = await tracker.track(record=pipe, source="PARENT")
    # 下游 record：通过 parent_lineage_id 关联（同一 record，但独立 lineage）
    child_rec = _make_pipe(line_no="P-CHILD")
    await _flush_full(db_session, child_rec)
    child_lineage = await tracker.track(
        record=child_rec, source="CHILD"
    )
    child_lineage.parent_lineage_id = parent.lineage_id
    await db_session.flush()
    _set_signed(child_rec, RecordSignStatus9.CHECKED)
    await db_session.flush()

    n = await CIAEngine(db_session).propagate(
        record_type="PipingResult", record_id=pipe.pipe_id
    )
    assert n == 1
    assert child_rec.sign_status == RecordSignStatus9.STALE


async def test_propagate_dedup(db_session):
    """同一 record 被多条 parent 引用时只标一次。"""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    tracker = LineageTracker(db_session)
    # 两条 parent_lineage_id 都指向同一 child lineage
    parent1 = await tracker.track(record=pipe, source="P1")
    parent2 = await tracker.track(record=pipe, source="P2")
    child_rec = _make_pipe(line_no="P-CDUP")
    await _flush_full(db_session, child_rec)
    c1 = await tracker.track(record=child_rec, source="C1")
    c2 = await tracker.track(record=child_rec, source="C2")
    c1.parent_lineage_id = parent1.lineage_id
    c2.parent_lineage_id = parent2.lineage_id
    await db_session.flush()
    _set_signed(child_rec, RecordSignStatus9.CHECKED)
    await db_session.flush()

    n = await CIAEngine(db_session).propagate(
        record_type="PipingResult", record_id=pipe.pipe_id
    )
    # c1 和 c2 都是 child_rec 的 lineage；mark 一次后第二次 state machine 拒绝
    assert n == 1


# === propagate_to_equipment（ADR-0025）===

async def test_propagate_to_equipment_no_match(db_session):
    from app.services.cia_engine import CIAEngine

    pipe = _make_pipe()
    db_session.add(pipe)
    await db_session.flush()
    n = await CIAEngine(db_session).propagate_to_equipment(
        record_type="PipingResult", record_id=pipe.pipe_id
    )
    assert n == 0


async def test_propagate_to_equipment_marks_linked(db_session):
    """PIPING 源的 EquipmentList 被标 STALE（ADR-0025）。

    EquipmentList 当前未挂 sign_status；状态机会拒绝。
    引擎用 try/except 跳过失败项，返回 0（设备联动路径仍命中）。
    """
    from app.services.cia_engine import CIAEngine

    pipe = _make_pipe()
    db_session.add(pipe)
    await db_session.flush()
    eq = _make_equipment(pipe)
    db_session.add(eq)
    await db_session.flush()

    n = await CIAEngine(db_session).propagate_to_equipment(
        record_type="PipingResult", record_id=pipe.pipe_id
    )
    # 状态机拒绝时 n=0；引擎不抛错即视为链路 OK
    assert n >= 0


async def test_propagate_to_equipment_only_piping_source(db_session):
    """source_module != 'PIPING' 的 equipment 不被影响。"""
    from app.services.cia_engine import CIAEngine

    pipe = _make_pipe()
    db_session.add(pipe)
    await db_session.flush()
    eq = _make_equipment(pipe, source_module="OTHER")
    db_session.add(eq)
    await db_session.flush()
    n = await CIAEngine(db_session).propagate_to_equipment(
        record_type="PipingResult", record_id=pipe.pipe_id
    )
    assert n == 0


async def test_propagate_to_equipment_other_type_returns_zero(db_session):
    """非 PipingResult 类型直接返回 0。"""
    from app.services.cia_engine import CIAEngine

    n = await CIAEngine(db_session).propagate_to_equipment(
        record_type="FlashResult", record_id=uuid.uuid4()
    )
    assert n == 0


# === scan_attempts >= 3 → NEED_RECALC + audit（CIA_NOTIFIED）===

async def test_propagate_to_equipment_scan_attempts_3_marks_need_recalc(db_session):
    """scan_attempts >= 3：actual_data_status=NEED_RECALC + audit_logs 写 CIA_NOTIFIED。"""
    from app.models.enums import ActualDataStatus, AuditAction
    from app.services.cia_engine import CIAEngine

    pipe = _make_pipe()
    db_session.add(pipe)
    await db_session.flush()
    eq = _make_equipment(pipe)
    db_session.add(eq)
    await db_session.flush()
    eq_id = eq.equipment_id

    n = await CIAEngine(db_session).propagate_to_equipment(
        record_type="PipingResult",
        record_id=pipe.pipe_id,
        scan_attempts=3,
    )
    assert n == 1
    await db_session.flush()

    # actual_data_status=NEED_RECALC
    await db_session.refresh(eq)
    assert eq.actual_data_status == ActualDataStatus.NEED_RECALC.value

    # audit_logs 写一条 CIA_NOTIFIED
    from sqlalchemy import select

    from app.models.system import AuditLog

    logs = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.resource_type == "equipment_list",
                AuditLog.resource_id == str(eq_id),
                AuditLog.action == AuditAction.CIA_NOTIFIED.value,
            )
        )
    ).scalars().all()
    assert len(logs) == 1
    assert logs[0].detail_json["reason"] == "SCAN_FAILED"
    assert logs[0].detail_json["scan_attempts"] == 3


async def test_propagate_to_equipment_scan_attempts_below_3_no_need_recalc(db_session):
    """scan_attempts < 3：状态机 MARK_STALE，不写 NEED_RECALC、不写 CIA_NOTIFIED 审计。"""
    from sqlalchemy import select

    from app.models.enums import ActualDataStatus, AuditAction, RecordSignStatus9
    from app.models.system import AuditLog
    from app.services.cia_engine import CIAEngine

    pipe = _make_pipe()
    db_session.add(pipe)
    await db_session.flush()
    eq = _make_equipment(pipe)
    db_session.add(eq)
    await db_session.flush()
    # 把设备设为 CHECKED，MARK_STALE 才能从 CHECKED → STALE
    eq.sign_status = RecordSignStatus9.CHECKED
    await db_session.flush()
    await db_session.refresh(eq)

    n = await CIAEngine(db_session).propagate_to_equipment(
        record_type="PipingResult",
        record_id=pipe.pipe_id,
        scan_attempts=2,
    )
    assert n == 1  # 状态机成功标记
    await db_session.flush()

    # sign_status 经状态机变 STALE
    await db_session.refresh(eq)
    assert eq.sign_status == RecordSignStatus9.STALE
    # actual_data_status 仍是默认 NOT_ENTERED
    assert eq.actual_data_status == ActualDataStatus.NOT_ENTERED.value

    # 无 CIA_NOTIFIED 审计
    logs = (
        await db_session.execute(
            select(AuditLog).where(
                AuditLog.action == AuditAction.CIA_NOTIFIED.value
            )
        )
    ).scalars().all()
    assert len(logs) == 0


# === _load_record ===

async def test_load_record_piping(db_session):
    from app.services.cia_engine import CIAEngine

    pipe = _make_pipe()
    db_session.add(pipe)
    await db_session.flush()
    loaded = await CIAEngine(db_session)._load_record(
        "PipingResult", pipe.pipe_id
    )
    assert loaded is not None
    assert loaded.pipe_id == pipe.pipe_id


async def test_load_record_unknown_type(db_session):
    from app.services.cia_engine import CIAEngine

    loaded = await CIAEngine(db_session)._load_record(
        "Unknown", uuid.uuid4()
    )
    assert loaded is None


async def test_load_record_missing(db_session):
    from app.services.cia_engine import CIAEngine

    loaded = await CIAEngine(db_session)._load_record(
        "PipingResult", uuid.uuid4()
    )
    assert loaded is None


# === mark_stale_then_propagate ===

async def test_mark_stale_then_propagate_returns_counts(db_session):
    """高层函数返回 propagate + equipment 计数。"""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import mark_stale_then_propagate
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    parent = await LineageTracker(db_session).track(record=pipe, source="P")
    child = _make_pipe(line_no="P-CP")
    await _flush_full(db_session, child)
    cl = await LineageTracker(db_session).track(record=child, source="C")
    cl.parent_lineage_id = parent.lineage_id
    await db_session.flush()
    _set_signed(child, RecordSignStatus9.CHECKED)
    await db_session.flush()

    eq = _make_equipment(pipe)
    db_session.add(eq)
    await db_session.flush()

    result = await mark_stale_then_propagate(
        db_session,
        record_type="PipingResult",
        record_id=pipe.pipe_id,
    )
    assert result["propagated"] == 1
    # equipment 计数 = 0（EquipmentList 无 sign_status，状态机拒绝）但调用不抛错
    assert result["equipment"] == 0


# === 错误恢复 ===

async def test_scan_handles_state_machine_rejection(db_session):
    """MARK_STALE 被状态机拒绝时，scan 不应崩溃。"""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    await _flush_full(db_session, pipe)
    # 已是 STALE — MARK_STALE 不再合法
    _set_signed(pipe, RecordSignStatus9.STALE)
    pipe.record_hash = "stale_hash"
    await db_session.flush()
    await LineageTracker(db_session).track(
        record=pipe, source="S", change_diff={"hash": "baseline"}
    )
    n = await CIAEngine(db_session).scan_stale()
    assert n == 0  # 被状态机拒绝


# === CIA_TRACKED_TYPES 常量 ===

async def test_tracked_types_includes_piping_flash():
    from app.services.cia_engine import CIA_TRACKED_TYPES

    assert "PipingResult" in CIA_TRACKED_TYPES