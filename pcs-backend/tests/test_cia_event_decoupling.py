"""CIAEngine 3 处直调 state_machine 改走事件触发 (P7 Sprint 4 S4-0 Step 5).

D4 裁决 4A: 业务模块**不直接调 state_machine**, 通过 emit_event 发事件。
状态机保持**单一权威** —— listener 内部仍调 fsm, 只是触发路径事件化。

本文件锁定两件事:
1. `CIAEngine` 标 STALE 时走 `emit_event` (而非直接 `self.fsm.transition`)
2. 事件确实被派发到 listener, 且 listener 完成状态转移 (单一权威未被绕过)

既有 `tests/test_cia.py` 的 18 个用例覆盖三条 STALE 路径的行为,
本文件只锁「触发路径」这一层, 不重复行为断言。
"""

from __future__ import annotations

import uuid

import pytest

from app.services.events import register_listener, restore_listeners, snapshot_listeners

pytestmark = pytest.mark.asyncio

CIA_MARK_STALE = "cia_mark_stale"


@pytest.fixture(autouse=True)
def _clean_registry():
    snap = snapshot_listeners()
    yield
    restore_listeners(snap)


def _make_pipe(**overrides):
    from app.models.calc import PipingResult

    base = dict(
        project_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
        seq_no=1, line_no="P-1", line_size='2"', material_class="A1",
        fluid_code="W", fluid_name="Water", fluid_phase="L",
        fluid_category="NORMAL", source_pid="P&ID-001",
        line_from="V-100", line_to="V-200",
        norm_oper_press=1.0, max_oper_press=1.5,
        norm_oper_temp=40.0, max_oper_temp=80.0,
        design_press=2.0, design_temp=100.0,
        piping_category="GC3", pressure_test_medium="WATER",
        pressure_test_press=3.0, check_class="III",
    )
    base.update(overrides)
    return PipingResult(**base)


def _set_signed(rec, status):
    rec.sign_status = status
    rec.record_hash = "h1"
    rec.changed_fields = ["sign_status"]


async def _seed_parent_child(db_session):
    """建 parent + child 血缘, child 已 CHECKED (propagate 的前提)."""
    from app.models.enums import RecordSignStatus9
    from app.services.lineage import LineageTracker

    pipe = _make_pipe()
    db_session.add(pipe)
    await db_session.flush()
    tracker = LineageTracker(db_session)
    parent = await tracker.track(record=pipe, source="PARENT")

    child = _make_pipe(line_no="P-CHILD")
    db_session.add(child)
    await db_session.flush()
    child_lineage = await tracker.track(record=child, source="CHILD")
    child_lineage.parent_lineage_id = parent.lineage_id
    _set_signed(child, RecordSignStatus9.CHECKED)
    await db_session.flush()
    return pipe, child


# ---------------------------------------------------------------------------
# 触发路径: 走 emit_event 而非直调 fsm
# ---------------------------------------------------------------------------


async def test_cia_emits_event_instead_of_calling_fsm_directly(db_session):
    """CIAEngine 标 STALE 必经 emit_event (D4 4A 的解耦点)."""
    from app.services.cia_engine import CIAEngine

    seen: list[dict] = []

    async def spy(event):  # noqa: RUF029
        seen.append(event)

    register_listener(CIA_MARK_STALE, spy)
    pipe, child = await _seed_parent_child(db_session)
    await CIAEngine(db_session).propagate(
        record_type="PipingResult", record_id=pipe.pipe_id
    )

    assert len(seen) == 1
    assert seen[0]["event_type"] == CIA_MARK_STALE


async def test_event_carries_record_and_reason(db_session, monkeypatch):
    """事件必须带上目标 record 与 reason, 否则 listener 无从执行转移."""
    from app.services.cia_engine import CIAEngine

    seen: list[dict] = []
    register_listener(CIA_MARK_STALE, lambda e: _append(seen, e))
    pipe, child = await _seed_parent_child(db_session)

    await CIAEngine(db_session).propagate(
        record_type="PipingResult", record_id=pipe.pipe_id
    )

    assert seen
    assert seen[0]["record"] is child
    assert "PipingResult" in seen[0]["reason"]


# ---------------------------------------------------------------------------
# 单一权威: listener 内部仍调 fsm, 状态转移照常发生
# ---------------------------------------------------------------------------


async def test_state_transition_still_happens_via_listener(db_session):
    """事件化只是改触发路径 —— sign_status 仍须真的变 STALE."""
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine

    pipe, child = await _seed_parent_child(db_session)
    n = await CIAEngine(db_session).propagate(
        record_type="PipingResult", record_id=pipe.pipe_id
    )
    await db_session.flush()
    assert n == 1
    assert child.sign_status == RecordSignStatus9.STALE


async def test_cia_source_has_no_direct_fsm_transition_calls():
    """静态守卫: cia_engine.py 不得再出现 self.fsm.transition(...).

    防止将来有人图省事把直调加回来 —— 那正是 D4 4A 要禁止的模式。
    """
    from pathlib import Path

    import app.services.cia_engine as mod

    src = Path(mod.__file__).read_text(encoding="utf-8")
    # 去掉 docstring/注释后再查, 否则示例代码会误报
    code = "\n".join(
        line for line in src.splitlines()
        if not line.lstrip().startswith("#")
    )
    assert "self.fsm.transition(" not in code, (
        "cia_engine.py 仍直调 self.fsm.transition — D4 4A 回归"
    )


async def _append(sink: list, event: dict) -> None:
    sink.append(event)
