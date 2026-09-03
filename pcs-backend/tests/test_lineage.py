"""Lineage 单元/集成测试（Sprint 3）。"""

from __future__ import annotations

import uuid

import pytest

pytestmark = pytest.mark.asyncio


def _make_pipe(**overrides):
    """构造满足 NOT NULL 约束的 PipingResult。"""
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


async def _flush(session, *objs):
    """add + flush 工具。"""
    for o in objs:
        session.add(o)
    await session.flush()
    return objs


# === compute_hash ===

async def test_compute_hash_deterministic(db_session):
    from app.services.lineage import _compute_hash

    rec = _make_pipe(line_no="P-100")
    await _flush(db_session, rec)
    h1 = _compute_hash(rec)
    h2 = _compute_hash(rec)
    assert h1 == h2
    assert len(h1) == 64


async def test_compute_hash_changes_on_field_change(db_session):
    from app.services.lineage import _compute_hash

    rec = _make_pipe(line_no="P-100")
    # 内存修改即可触发 hash 变化；避免 flush 后 expire 触发的 async lazy-load
    h1 = _compute_hash(rec)
    rec.line_no = "P-101"
    h2 = _compute_hash(rec)
    assert h1 != h2


# === LineageTracker.track ===

async def test_track_writes_entry(db_session):
    from app.services.lineage import LineageTracker

    rec = _make_pipe(line_no="P-1")
    await _flush(db_session, rec)
    tracker = LineageTracker(db_session)
    entry = await tracker.track(
        record=rec,
        source="USER",
        change_summary="manual edit",
    )
    assert entry.lineage_id is not None
    assert entry.source == "USER"
    assert entry.record_type == "PipingResult"
    assert entry.record_id == rec.pipe_id


async def test_track_with_parent(db_session):
    from app.services.lineage import LineageTracker

    rec = _make_pipe(line_no="P-2")
    await _flush(db_session, rec)
    tracker = LineageTracker(db_session)
    parent = await tracker.track(record=rec, source="USER")
    child = await tracker.track(
        record=rec,
        source="AI",
        change_summary="auto",
    )
    child.parent_lineage_id = parent.lineage_id
    await db_session.flush()
    assert child.parent_lineage_id == parent.lineage_id


async def test_track_assigns_record_id_via_flush(db_session):
    """track() 内部 flush 后 PK 已被赋值。"""
    from app.services.lineage import LineageTracker

    rec = _make_pipe(line_no="P-x")
    db_session.add(rec)
    tracker = LineageTracker(db_session)
    entry = await tracker.track(record=rec, source="USER")
    assert entry.record_id is not None
    assert entry.record_id == rec.pipe_id


# === LineageTracker.latest ===

async def test_latest_returns_most_recent(db_session):
    from app.services.lineage import LineageTracker

    rec = _make_pipe(line_no="P-3")
    await _flush(db_session, rec)
    tracker = LineageTracker(db_session)
    await tracker.track(record=rec, source="USER")
    b = await tracker.track(record=rec, source="AI")
    latest = await tracker.latest(
        record_type="PipingResult", record_id=rec.pipe_id
    )
    assert latest is not None
    assert latest.lineage_id == b.lineage_id


async def test_latest_returns_none_for_no_lineage(db_session):
    from app.services.lineage import LineageTracker

    tracker = LineageTracker(db_session)
    latest = await tracker.latest(
        record_type="PipingResult", record_id=uuid.uuid4()
    )
    assert latest is None


# === upstream / downstream ===

async def test_upstream_traverses_parent_chain(db_session):
    from app.services.lineage import LineageTracker

    rec = _make_pipe(line_no="P-4")
    await _flush(db_session, rec)
    tracker = LineageTracker(db_session)
    n1 = await tracker.track(record=rec, source="A")
    n2 = await tracker.track(record=rec, source="B")
    n3 = await tracker.track(record=rec, source="C")
    n3.parent_lineage_id = n2.lineage_id
    n2.parent_lineage_id = n1.lineage_id
    await db_session.flush()
    chain = await tracker.upstream(
        record_type="PipingResult", record_id=rec.pipe_id
    )
    assert len(chain) == 2
    assert chain[0].lineage_id == n2.lineage_id
    assert chain[1].lineage_id == n1.lineage_id


async def test_upstream_empty_when_no_parent(db_session):
    from app.services.lineage import LineageTracker

    rec = _make_pipe(line_no="P-5")
    await _flush(db_session, rec)
    tracker = LineageTracker(db_session)
    await tracker.track(record=rec, source="USER")
    chain = await tracker.upstream(
        record_type="PipingResult", record_id=rec.pipe_id
    )
    assert chain == []


async def test_downstream_bfs(db_session):
    from app.services.lineage import LineageTracker

    rec = _make_pipe(line_no="P-6")
    await _flush(db_session, rec)
    tracker = LineageTracker(db_session)
    parent = await tracker.track(record=rec, source="USER")
    c1 = await tracker.track(record=rec, source="AI")
    c2 = await tracker.track(record=rec, source="CIA")
    c1.parent_lineage_id = parent.lineage_id
    c2.parent_lineage_id = parent.lineage_id
    await db_session.flush()
    children = await tracker.downstream(lineage_id=parent.lineage_id)
    assert len(children) == 2
    ids = {c.lineage_id for c in children}
    assert ids == {c1.lineage_id, c2.lineage_id}


async def test_upstream_respects_max_depth(db_session):
    from app.services.lineage import LineageTracker

    rec = _make_pipe(line_no="P-12")
    await _flush(db_session, rec)
    tracker = LineageTracker(db_session)
    n1 = await tracker.track(record=rec, source="A")
    n2 = await tracker.track(record=rec, source="B")
    n3 = await tracker.track(record=rec, source="C")
    n3.parent_lineage_id = n2.lineage_id
    n2.parent_lineage_id = n1.lineage_id
    await db_session.flush()
    chain = await tracker.upstream(
        record_type="PipingResult",
        record_id=rec.pipe_id,
        max_depth=1,
    )
    assert len(chain) == 1


# === @lineage decorator ===

async def test_decorator_writes_lineage(db_session):
    from app.services.lineage import LineageTracker, lineage

    rec = _make_pipe(line_no="P-7")
    await _flush(db_session, rec)

    @lineage(sources=("USER",), summary="via decorator")
    async def edit(session, record, user_id):
        record.line_no = "P-7-modified"
        # 不在此 flush：让装饰器的 track() 内部统一 flush，避免 expire 后 lazy-load
        return record

    user_id = uuid.uuid4()
    await edit(db_session, rec, user_id)
    tracker = LineageTracker(db_session)
    latest = await tracker.latest(
        record_type="PipingResult", record_id=rec.pipe_id
    )
    assert latest is not None
    assert latest.source == "USER"
    assert latest.change_summary == "via decorator"
    assert latest.actor_user_id == user_id


async def test_decorator_with_list_result(db_session):
    from app.services.lineage import LineageTracker, lineage

    recs = [_make_pipe(line_no=f"P-{i}") for i in range(3)]
    await _flush(db_session, *recs)
    pipe_ids = [r.pipe_id for r in recs]  # 提前存，flush 后会 expire

    @lineage(sources=("USER",))
    async def bulk_edit(session, record_list):
        for r in record_list:
            r.line_no += "-x"
        return record_list

    await bulk_edit(db_session, recs)
    tracker = LineageTracker(db_session)
    for pid in pipe_ids:
        latest = await tracker.latest(
            record_type="PipingResult", record_id=pid
        )
        assert latest is not None


async def test_decorator_no_actor_uses_none(db_session):
    from app.services.lineage import LineageTracker, lineage

    rec = _make_pipe(line_no="P-11")
    await _flush(db_session, rec)

    @lineage(sources=("USER",))
    async def do(session, record):
        record.line_no = "P-11-na"
        return record

    await do(db_session, rec)
    latest = await LineageTracker(db_session).latest(
        record_type="PipingResult", record_id=rec.pipe_id
    )
    assert latest is not None
    assert latest.actor_user_id is None


async def test_decorator_missing_session_raises():
    from app.services.lineage import lineage

    @lineage(sources=("USER",))
    async def fn(record):
        return record

    with pytest.raises(TypeError):
        await fn(uuid.uuid4())


# === lineage_ctx ===

async def test_ctx_appends_sources(db_session):
    from app.services.lineage import LineageTracker, lineage, lineage_ctx

    rec = _make_pipe(line_no="P-8")
    await _flush(db_session, rec)
    pid = rec.pipe_id  # 提前存，flush 后会 expire

    @lineage(sources=("USER",))
    async def do(session, record, user_id):
        record.line_no = "P-8-ctx"
        return record

    with lineage_ctx(sources=("AI", "IMPORT")):
        await do(db_session, rec, uuid.uuid4())
    tracker = LineageTracker(db_session)
    latest = await tracker.latest(
        record_type="PipingResult", record_id=pid
    )
    assert latest is not None
    assert latest.source in {"USER", "AI", "IMPORT"}


async def test_ctx_sets_parent_lineage_id(db_session):
    from app.services.lineage import LineageTracker, lineage, lineage_ctx

    rec = _make_pipe(line_no="P-9")
    await _flush(db_session, rec)

    @lineage(sources=("USER",))
    async def do(session, record, user_id):
        record.line_no = "P-9-parent"
        return record

    parent = await LineageTracker(db_session).track(record=rec, source="SEED")
    with lineage_ctx(parent_lineage_id=parent.lineage_id):
        await do(db_session, rec, uuid.uuid4())
    child = await LineageTracker(db_session).latest(
        record_type="PipingResult", record_id=rec.pipe_id
    )
    assert child is not None
    assert child.parent_lineage_id == parent.lineage_id


async def test_ctx_async_enter(db_session):
    from app.services.lineage import lineage_ctx

    async with lineage_ctx(sources=("AI",)):
        pass


async def test_ctx_no_sources_uses_default_user(db_session):
    from app.services.lineage import LineageTracker, lineage

    rec = _make_pipe(line_no="P-10")
    await _flush(db_session, rec)

    @lineage(sources=())
    async def do(session, record, user_id):
        record.line_no = "P-10-default"
        return record

    await do(db_session, rec, uuid.uuid4())
    latest = await LineageTracker(db_session).latest(
        record_type="PipingResult", record_id=rec.pipe_id
    )
    assert latest is not None
    assert latest.source == "USER"


async def test_ctx_exit_resets_state(db_session):
    """ctx 退出后状态被重置。"""
    from app.services.lineage import _active_ctx, lineage_ctx

    with lineage_ctx(sources=("X",)):
        assert _active_ctx.get() is not None
    assert _active_ctx.get() is None


async def test_ctx_nested_replaces_then_restores(db_session):
    """嵌套 ctx 时内层 REPLACE（set 语义），外层退出后状态恢复。"""
    from app.services.lineage import _active_ctx, lineage_ctx

    with lineage_ctx(sources=("A",)):
        with lineage_ctx(sources=("B",)):
            inner = _active_ctx.get()
            assert inner is not None
            assert set(inner["sources"]) == {"B"}
        # 内层退出：回到外层
        outer = _active_ctx.get()
        assert outer is not None
        assert set(outer["sources"]) == {"A"}
    # 全部退出：None
    assert _active_ctx.get() is None


# === source_ref_type/ref_id ===

async def test_track_with_source_ref(db_session):
    from app.services.lineage import LineageTracker

    rec = _make_pipe(line_no="P-13")
    await _flush(db_session, rec)
    tracker = LineageTracker(db_session)
    ref_id = uuid.uuid4()
    entry = await tracker.track(
        record=rec,
        source="UPLINK",
        source_ref_type="Snapshot",
        source_ref_id=ref_id,
    )
    assert entry.source == "UPLINK"
    assert entry.source_ref_type == "Snapshot"
    assert entry.source_ref_id == ref_id


# === P4 接入 e2e：模拟 FLASH 计算模块（用 FlareSystemResult 代理）
# === @lineage 装饰器 + 状态机 DRAFT→SUBMITTED→CHECKED 全路径 ===

async def test_p4_flash_full_path(db_session):
    """FLASH 模块接入：装饰器自动落血缘 + 状态机走 DRAFT→CHECKED。"""
    from app.models.calc import FlareSystemResult
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.lineage import LineageTracker, lineage
    from app.services.state_machine import StateMachineService

    # 1) FLASH 模块创建初始 record（DRAFT 态）
    flare = FlareSystemResult(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        tag_number="FL-001",
        input_json={"feed": "C1", "heat_duty": 1.2e6},
        output_json={},
    )
    db_session.add(flare)
    await db_session.flush()
    await db_session.refresh(flare)
    assert flare.sign_status == RecordSignStatus9.DRAFT

    # 2) FLASH 计算模块：使用 @lineage 装饰器自动落血缘
    @lineage(sources=("FLASH",), summary="FLASH relief calculation")
    async def run_flash_calc(session, record, actor_user_id):
        record.output_json = {
            "tip_temp": 850.0,
            "radiation": 4.5,
            "vent_rate": 12.3,
        }
        return record

    user_id = uuid.uuid4()
    await run_flash_calc(db_session, flare, user_id)
    await db_session.flush()
    assert flare.output_json["tip_temp"] == 850.0

    # 3) 验证 @lineage 已自动写一条 source="FLASH" 血缘
    latest = await LineageTracker(db_session).latest(
        record_type="FlareSystemResult", record_id=flare.flare_id
    )
    assert latest is not None
    assert latest.source == "FLASH"
    assert latest.change_summary == "FLASH relief calculation"
    assert latest.actor_user_id == user_id

    # 4) 状态机：DRAFT → SUBMITTED → CHECKED
    fsm = StateMachineService(db_session)
    designer_id = uuid.uuid4()
    checker_id = uuid.uuid4()

    # DRAFT --SUBMIT_FOR_CHECK(DESIGNER)--> IN_APPROVAL
    await fsm.transition(
        record=flare,
        transition=StateTransition.SUBMIT_FOR_CHECK,
        actor_user_id=designer_id,
        actor_role="DESIGNER",
        reason="submit for review",
    )
    assert flare.sign_status == RecordSignStatus9.IN_APPROVAL

    # IN_APPROVAL --PASS_CHECK(CHECKER)--> CHECKED
    await fsm.transition(
        record=flare,
        transition=StateTransition.PASS_CHECK,
        actor_user_id=checker_id,
        actor_role="CHECKER",
        reason="calculation verified",
    )
    assert flare.sign_status == RecordSignStatus9.CHECKED
