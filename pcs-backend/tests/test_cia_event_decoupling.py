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
    """静态守卫: cia_engine.py 不得 import state_machine 或直调 `.transition(`.

    防止将来有人图省事把直调加回来 —— 那正是 D4 4A 要禁止的模式。

    ⚠️ 走 AST 而非字符串匹配（审查 #22）。原实现 grep 字面量 `self.fsm.transition(`，
    而该字面量在重构后的 cia_engine.py 中**一次都不出现**（类已不持有 fsm 属性，
    唯一调用是局部变量形式 `fsm = StateMachineService(session)` /
    `await fsm.transition(...)`）—— 守卫从写下那天起就不可失败，断言恒为真，
    给人虚假的安全感。有人真把直调加回来时最自然的两种写法都不含那个字面量。
    同时修掉注释声称剥 docstring、实现只剥 `#` 行的不符。
    """
    import ast
    from pathlib import Path

    import app.services.cia_engine as mod

    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))

    # 本守卫的规则与 supplier 侧那份**不同**，别照抄：
    # - supplier 域永不接触 FSM，故禁 import 也禁调用；
    # - CIA 域**拥有** `cia_mark_stale` 的唯一 listener，模块级 import state_machine
    #   是合法的（listener 需要 StateMachineService / StateTransition）。
    #   真正的红线只有一条：FSM 转移**只能**发生在 `_mark_stale_via_fsm` 里。
    exempt_lines: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name == "_mark_stale_via_fsm"
        ):
            exempt_lines = {n.lineno for n in ast.walk(node) if hasattr(n, "lineno")}
    assert exempt_lines, (
        "未找到 _mark_stale_via_fsm —— listener 改名/删除会让本守卫静默失效, "
        "请同步更新豁免名单"
    )

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("transition", "register_listener"):
                if node.lineno not in exempt_lines:
                    offenders.append(f".{node.func.attr}() @line {node.lineno}")

    assert not offenders, (
        f"D4 4A 回归（FSM 转移只能经 emit_event -> listener）: {offenders}"
    )


async def _append(sink: list, event: dict) -> None:
    sink.append(event)


async def test_scan_stale_does_not_count_when_no_listener(db_session):
    """#28: 无 listener 时 `scan_stale` 不得报「已标记 N 台」.

    修复前 `_mark_stale` 返回 `emit_event` 的结果，而 `emit_event` 在 claim 成功后
    无论有没有 listener 都返回 True —— `scan_stale` 再无条件 `marked += 1`。
    于是注册表里没有 `cia_mark_stale` 的 listener 时：FSM 转移没发生、无异常抛出、
    事件照样被 claim 为已处理，而操作者拿到的「已标记 N 台」是错的，且无任何提示。

    这正是 `clear_listeners()` 文档里说的「模拟进程重启」能到达的状态。
    """
    from app.models.enums import RecordSignStatus9
    from app.services.cia_engine import CIAEngine
    from app.services.events import clear_listeners
    from app.services.lineage import LineageTracker

    pipe, _child = await _seed_parent_child(db_session)
    pipe.sign_status = RecordSignStatus9.CHECKED
    pipe.record_hash = "h2"
    await db_session.flush()
    await LineageTracker(db_session).track(
        record=pipe, source="SEED", change_summary="baseline",
        change_diff={"hash": "stale_hash_xxx"},
    )
    await db_session.flush()

    clear_listeners()  # 事件发出但无人处理 —— 转移不会发生
    n = await CIAEngine(db_session).scan_stale()

    assert n == 0, (
        f"无 listener 却报已标记 {n} 台 —— 操作者据此判断隔离了多少陈旧数据，"
        "该数字是错的"
    )
    assert pipe.sign_status == RecordSignStatus9.CHECKED, "转移确实没发生"


async def test_claim_only_events_do_not_require_listener(db_session):
    """#28 反向: `actual_data_replaces_design` 在 P8 挂反向恢复 listener 前本就是
    claim-only —— 无 listener 不构成错误。勿一刀切地把「无 listener」判为 bug。"""
    from app.services.events import CLAIM_ONLY_EVENTS, has_listener

    # 快照态下 cia_mark_stale 的 listener 是注册着的
    assert has_listener(CIA_MARK_STALE) is True
    # 而 replaces_design / check_submitted 在 P8 之前不需要 listener
    assert "actual_data_replaces_design" in CLAIM_ONLY_EVENTS
    assert "actual_data_check_submitted" in CLAIM_ONLY_EVENTS
    assert CIA_MARK_STALE not in CLAIM_ONLY_EVENTS
