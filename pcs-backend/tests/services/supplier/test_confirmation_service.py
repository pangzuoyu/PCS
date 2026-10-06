"""供应商核算与更新流程 (P7 Sprint 4 Task S4-3 / SPEC V1.4 §3.2.4(4)(5)(6)).

SPEC §3.2.4(4) 的流程：
    设计人录入实际数据 → 自动比对 → 设计人勾选确认满足工艺要求 → 提交校核
    → 校核人校核 → 通过后标记"已确认" → 系统更新（UTIL 引用实际值 + 变更影响分析）

本 Task 锁四件事：
1. **不合格/不可判项禁止确认**（§3.2.4(4)，风险 #4）
2. **实际数据不进门禁哈希**（§3.2.4(5)）—— 确认不动 sign_status 的哈希
3. **已确认的实际数据修改需校核人退回**（§3.2.4(5)）
4. **D4 裁决 4A**：Supplier 只 `emit_event`，**不直调 state_machine**；
   且 `actual_data_replaces_design` 事件**必带 `before`** —— P8 反向恢复的前提
"""

from __future__ import annotations

import uuid

import pytest

from app.core.errors import PcsError
from app.services.events import (
    register_listener,
    restore_listeners,
    snapshot_listeners,
)

pytestmark = pytest.mark.asyncio

CHECK_SUBMITTED = "actual_data_check_submitted"
REPLACES_DESIGN = "actual_data_replaces_design"

DESIGN = {"扬程": {"value": 32.0, "unit": "m"}, "轴功率": {"value": 55.0, "unit": "kW"}}
ACTUAL_OK = {"扬程": {"value": 33.0, "unit": "m"}, "电机额定功率": {"value": 75.0, "unit": "kW"}}
ACTUAL_BAD = {"扬程": {"value": 33.0, "unit": "m"}, "电机额定功率": {"value": 48.0, "unit": "kW"}}


@pytest.fixture(autouse=True)
def _clean_registry():
    """listener 注册表是进程级的 —— 隔离本文件的注册, 别漏进别的测试。"""
    snap = snapshot_listeners()
    yield
    restore_listeners(snap)


async def _make_equipment(db_session, *, actual=ACTUAL_OK, design=DESIGN, status="PENDING_CONFIRM", sign_status="DRAFT"):
    from app.models.equipment import EquipmentList

    eq = EquipmentList(
        project_id=uuid.uuid4(), workspace_id=uuid.uuid4(),
        tag_number=f"P-{uuid.uuid4().hex[:6]}",
        equipment_name="原料泵", type_code="P-100",
        design_parameters_json=design, actual_data_json=actual,
        actual_data_status=status, sign_status=sign_status,
    )
    db_session.add(eq)
    await db_session.commit()
    await db_session.refresh(eq)
    return eq


_ACTOR = type("A", (), {"user_id": uuid.uuid4(), "role": "DESIGNER", "roles": ["DESIGNER"]})()
_CHECKER = type("A", (), {"user_id": uuid.uuid4(), "role": "REVIEWER", "roles": ["REVIEWER"]})()


# ---------------------------------------------------------------------------
# 1. 确认门禁（§3.2.4(4) + 风险 #4）
# ---------------------------------------------------------------------------


async def test_confirm_rejected_when_unqualified(db_session):
    """存在不合格项 → 禁止确认."""
    from app.services.supplier.confirmation_service import confirm_actual_data

    eq = await _make_equipment(db_session, actual=ACTUAL_BAD)
    with pytest.raises(PcsError) as exc:
        await confirm_actual_data(db_session, eq, _ACTOR, reason="设计人确认")
    assert exc.value.status == 422
    assert exc.value.code == "DEVIATION_BLOCKS_CONFIRMATION"


async def test_confirm_rejected_when_unverdictable(db_session):
    """缺设计值 → 全部不可判 → 同样禁止确认（fail-closed）."""
    from app.services.supplier.confirmation_service import confirm_actual_data

    eq = await _make_equipment(db_session, design=None)
    with pytest.raises(PcsError) as exc:
        await confirm_actual_data(db_session, eq, _ACTOR, reason="设计人确认")
    assert exc.value.code == "DEVIATION_BLOCKS_CONFIRMATION"


async def test_confirm_succeeds_when_all_qualified(db_session):
    from app.services.supplier.confirmation_service import confirm_actual_data

    eq = await _make_equipment(db_session)
    out = await confirm_actual_data(db_session, eq, _ACTOR, reason="设计人确认")
    assert out.actual_data_status == "PENDING_CONFIRM"  # 已提交校核，待校核


async def test_confirm_requires_actual_data(db_session):
    """没录数据不能确认 —— 空报告 can_confirm=False."""
    from app.services.supplier.confirmation_service import confirm_actual_data

    eq = await _make_equipment(db_session, actual=None)
    with pytest.raises(PcsError):
        await confirm_actual_data(db_session, eq, _ACTOR, reason="x")


async def test_confirm_rejected_when_already_confirmed(db_session):
    """已确认的再确认 → 幂等拒绝，不静默重跑校核链."""
    from app.services.supplier.confirmation_service import confirm_actual_data

    eq = await _make_equipment(db_session, status="CONFIRMED")
    with pytest.raises(PcsError) as exc:
        await confirm_actual_data(db_session, eq, _ACTOR, reason="x")
    assert exc.value.code == "ACTUAL_DATA_ALREADY_CONFIRMED"


# ---------------------------------------------------------------------------
# 2. 校核人校核
# ---------------------------------------------------------------------------


async def test_pass_check_marks_confirmed(db_session):
    from app.services.supplier.confirmation_service import pass_check

    eq = await _make_equipment(db_session)
    out = await pass_check(db_session, eq, _CHECKER, reason="校核通过")
    assert out.actual_data_status == "CONFIRMED"


async def test_pass_check_emits_event_with_before(db_session):
    """⚠️ `before` 必带 —— P8 反向恢复的唯一来源（§3.2.4(6) + D4 裁决）.

    漏了 before, P8 拿不回被覆盖前的设计值, 反向恢复无法实现。
    """
    from app.services.supplier.confirmation_service import pass_check

    seen: list[dict] = []
    register_listener(REPLACES_DESIGN, lambda e: _append(seen, e))
    eq = await _make_equipment(db_session)
    await pass_check(db_session, eq, _CHECKER, reason="校核通过")

    assert len(seen) == 1
    assert seen[0]["before"] == DESIGN, "before 快照丢失 → P8 反向恢复无从下手"
    assert seen[0]["after"] == ACTUAL_OK
    assert seen[0]["event_id"]


async def test_pass_check_does_not_touch_sign_status_hash(db_session):
    """§3.2.4(5)：实际数据不参与设备记录门禁哈希 —— 确认不得改 sign_status."""
    from app.services.supplier.confirmation_service import pass_check

    eq = await _make_equipment(db_session, sign_status="DRAFT")
    before_hash = eq.record_hash
    await pass_check(db_session, eq, _CHECKER, reason="校核通过")
    await db_session.refresh(eq)
    assert eq.sign_status == "DRAFT"
    assert eq.record_hash == before_hash


async def test_reject_check_reopens_entry(db_session):
    """校核退回 → 回到 PENDING_CONFIRM，可重新录入."""
    from app.services.supplier.confirmation_service import pass_check, reject_check

    eq = await _make_equipment(db_session)
    await pass_check(db_session, eq, _CHECKER, reason="通过")
    out = await reject_check(db_session, eq, _CHECKER, reason="数据存疑，退回")
    assert out.actual_data_status == "PENDING_CONFIRM"


# ---------------------------------------------------------------------------
# 3. 已确认的数据修改需校核人退回（§3.2.4(5)）
# ---------------------------------------------------------------------------


async def test_reentry_blocked_while_confirmed(db_session):
    from app.services.supplier.actual_data_service import record_actual_data

    eq = await _make_equipment(db_session, status="CONFIRMED")
    with pytest.raises(PcsError) as exc:
        await record_actual_data(
            db_session, eq, [{"name": "扬程", "value": 34.0, "unit": "m"}]
        )
    assert exc.value.code == "ACTUAL_DATA_LOCKED"
    assert exc.value.status == 422


async def test_reentry_allowed_after_reject(db_session):
    from app.services.supplier.actual_data_service import record_actual_data
    from app.services.supplier.confirmation_service import reject_check

    eq = await _make_equipment(db_session, status="CONFIRMED")
    await reject_check(db_session, eq, _CHECKER, reason="退回")
    out = await record_actual_data(
        db_session, eq, [{"name": "扬程", "value": 34.0, "unit": "m"}]
    )
    assert out.actual_data_status == "PENDING_CONFIRM"


# ---------------------------------------------------------------------------
# 4. D4 裁决 4A：Supplier 不直调 state_machine
# ---------------------------------------------------------------------------


async def test_supplier_emits_event_not_state_machine(db_session):
    """校核通过走 emit_event（spy 收到），而非静默改状态."""
    from app.services.supplier.confirmation_service import pass_check

    seen: list[dict] = []
    register_listener(REPLACES_DESIGN, lambda e: _append(seen, e))
    eq = await _make_equipment(db_session)
    await pass_check(db_session, eq, _CHECKER, reason="通过")
    assert [e["event_type"] for e in seen] == [REPLACES_DESIGN]


async def test_supplier_source_has_no_direct_fsm_transition_calls():
    """静态守卫: confirmation_service.py 不得 import state_machine 或调 .transition(.

    防止将来有人图省事把直调加回来 —— 那正是 D4 4A 要禁止的模式。

    走 AST 而非字符串匹配: 字符串匹配会被 docstring 里的「不直调 state_machine」
    这类说明文字误报（既有的 cia 守卫就有这个隐患 —— 它的注释声称剥掉 docstring，
    实际只剥了 `#` 行）。
    """
    import ast
    from pathlib import Path

    import app.services.supplier.confirmation_service as mod

    tree = ast.parse(Path(mod.__file__).read_text(encoding="utf-8"))

    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module and "state_machine" in node.module:
            offenders.append(f"import {node.module}")
        elif isinstance(node, ast.Import):
            offenders.extend(
                f"import {a.name}" for a in node.names if "state_machine" in a.name
            )
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr in ("transition", "register_listener"):
                offenders.append(f".{node.func.attr}() @line {node.lineno}")

    assert not offenders, f"D4 4A 回归（须走 emit_event）: {offenders}"


async def test_check_submitted_event_emitted_on_confirm(db_session):
    """设计人提交校核也应发事件，供审计/通知消费."""
    from app.services.supplier.confirmation_service import confirm_actual_data

    seen: list[dict] = []
    register_listener(CHECK_SUBMITTED, lambda e: _append(seen, e))
    eq = await _make_equipment(db_session)
    await confirm_actual_data(db_session, eq, _ACTOR, reason="设计人确认")
    assert [e["event_type"] for e in seen] == [CHECK_SUBMITTED]


async def _append(sink: list, event: dict) -> None:
    sink.append(event)


# ---------------------------------------------------------------------------
# 4. 事件幂等与事务边界（审查 #2 / #3）
# ---------------------------------------------------------------------------


async def test_pass_check_concurrent_collision_is_idempotent(db_session):
    """#3：**并发**双击（两事务都在对方提交前读到 PENDING_CONFIRM）→ 同一 event_id.

    这不是顺序重复 —— 顺序重复会被 #5 的状态守卫直接 409 拦掉。uuid5 防的
    是并发：两个事务都过了守卫，第二个的 claim 撞主键，被幂等吞掉。

    改 uuid5 前这里是 RED：每次 `uuid.uuid4()` 都发一个新事件，第二个事件的
    `before` 等于第一个的 `after` —— P8 按序反向恢复会把实际数据写回设计位。
    """
    from app.services.supplier.confirmation_service import pass_check

    seen: list[dict] = []
    register_listener(REPLACES_DESIGN, lambda e: _append(seen, e))
    eq = await _make_equipment(db_session)
    await pass_check(db_session, eq, _CHECKER, reason="校核通过")
    first_id = seen[0]["event_id"]

    # 模拟并发：另一事务在本事务提交前就读到了 PENDING_CONFIRM，故也过了守卫。
    # event_id 的派生输入只有 event_type + before + after（不含 status），
    # 故回拨状态不会改变 id —— 这正是「同一业务事实」的定义。
    eq.actual_data_status = "PENDING_CONFIRM"
    await db_session.flush()
    await pass_check(db_session, eq, _CHECKER, reason="并发双击")

    assert [e["event_id"] for e in seen] == [first_id], (
        f"并发重复校核多派发了 {len(seen) - 1} 个事件 —— event_id 非确定性，"
        "幂等去重结构性不可达"
    )


@pytest.mark.parametrize("status", ["NOT_ENTERED", "CONFIRMED", "NEED_RECALC"])
async def test_pass_check_requires_pending_confirm(db_session, status):
    """#5：只有 PENDING_CONFIRM 能校核通过，其余三态一律 409.

    修复前 `pass_check` 第一条语句就是置 CONFIRMED，端点侧唯一闸是
    `require_roles(_CHECK_ROLES)` —— 持项目访问权的 REVIEWER 可把从未录入的
    设备直推 CONFIRMED，而那正是 `record_actual_data` 认定的锁
    （ACTUAL_DATA_LOCKED），本该填数据的设计人被永久冻结。reject_check 是
    镜像缺口：能把 CONFIRMED 无条件退回，重新打开录入通道。
    """
    from app.services.supplier.confirmation_service import pass_check

    eq = await _make_equipment(db_session, status=status)
    with pytest.raises(PcsError) as exc:
        await pass_check(db_session, eq, _CHECKER, reason="校核通过")
    assert exc.value.status == 409
    assert eq.actual_data_status == status, "被拒后状态不得被改写"


@pytest.mark.parametrize("status", ["NOT_ENTERED", "PENDING_CONFIRM", "NEED_RECALC"])
async def test_reject_check_requires_confirmed(db_session, status):
    """#5：reject_check 只有在 CONFIRMED 上才成立。"""
    from app.services.supplier.confirmation_service import reject_check

    eq = await _make_equipment(db_session, status=status)
    with pytest.raises(PcsError) as exc:
        await reject_check(db_session, eq, _CHECKER, reason="退回")
    assert exc.value.status == 409
    assert eq.actual_data_status == status, "被拒后状态不得被改写"


async def test_pass_check_rejects_when_deviation_not_confirmable(db_session):
    """#5：状态对了也不够 —— 门禁须在 `pass_check` 侧重跑一次.

    四眼控制的意义在于校核人看到的必须是引擎判过的那份数据。修复前
    `can_confirm` 只在 `confirm_actual_data` 里跑，`pass_check` 直通 CONFIRMED，
    于是「录入→校核」之间任何改动都不再被复判。
    """
    from app.services.supplier.confirmation_service import pass_check

    eq = await _make_equipment(db_session, actual=ACTUAL_BAD)  # 电机额定功率 48 < 地板 63.25
    with pytest.raises(PcsError) as exc:
        await pass_check(db_session, eq, _CHECKER, reason="校核通过")
    assert exc.value.code == "DEVIATION_BLOCKS_CONFIRMATION"
    assert eq.actual_data_status == "PENDING_CONFIRM"


def _force_claim_collision(db_session, monkeypatch, *, visible_row):
    """让 _claim 内那次 flush 抛 IntegrityError, 并控制其后的重查结果.

    单连接内存 SQLite 造不出真并发双 INSERT（StaticPool 共享一条连接）, 故故障注入。

    `visible_row`:
      None                 → 撞主键但重查看不到该行（对方事务尚未提交/已回滚）
      带 .payload_hash 对象  → 重查看到一行, hash 可控
    """
    from types import SimpleNamespace

    from sqlalchemy.exc import IntegrityError

    real_flush = db_session.flush
    real_execute = db_session.execute
    calls = {"n": 0}
    state = {"armed": False}
    if visible_row is not None and not hasattr(visible_row, "payload_hash"):
        raise AssertionError("visible_row 需带 payload_hash")

    async def flaky_flush(*a, **kw):
        calls["n"] += 1
        if calls["n"] == 2:
            # pass_check 的 flush 是 #1；_claim 里 INSERT claim 行那次是 #2
            state["armed"] = True
            raise IntegrityError("INSERT ...", {}, Exception("forced collision"))
        return await real_flush(*a, **kw)

    class _FakeResult:
        def __init__(self, row: object) -> None:
            self._row = row

        def first(self):
            return self._row

    async def fake_execute(stmt, *a, **kw):
        # 只在 claim 已被冲刷之后才拦截, 否则连 _claim 顶部的 existing 查询也被替换
        return _FakeResult(visible_row) if state["armed"] else await real_execute(stmt, *a, **kw)

    monkeypatch.setattr(db_session, "flush", flaky_flush)
    monkeypatch.setattr(db_session, "execute", fake_execute)
    return SimpleNamespace(armed=state)


async def test_claim_collision_keeps_caller_write(db_session, monkeypatch):
    """#2：_claim 撞主键时，调用方已 flush 的 CONFIRMED 不得被 rollback 吞掉.

    故障注入下检验该 except 分支的可观测后果。修复前 `_claim` 调
    `session.rollback()` 回滚整个事务：调用方 `actual_data_status=CONFIRMED`
    一起丢，设备退回 PENDING_CONFIRM。
    """
    from app.services.supplier.confirmation_service import pass_check

    eq = await _make_equipment(db_session)
    _force_claim_collision(db_session, monkeypatch, visible_row=None)
    try:
        with pytest.raises(PcsError):
            await pass_check(db_session, eq, _CHECKER, reason="校核通过")
    finally:
        monkeypatch.undo()

    await db_session.refresh(eq)
    assert eq.actual_data_status == "CONFIRMED", (
        "claim 冲突把调用方已 flush 的 CONFIRMED 一起回滚了 —— 数据丢失"
    )


async def test_claim_collision_invisible_row_is_retryable(db_session, monkeypatch):
    """#2 后半段：撞主键但重查看不到行 → 可能对方事务尚未提交，**重试有意义**.

    这才是唯一值得让上游重试的情形，文案与 retryable 标记必须如实表达，
    否则运维会把可恢复的并发直接判成失败。
    """
    from app.services.supplier.confirmation_service import pass_check

    eq = await _make_equipment(db_session)
    _force_claim_collision(db_session, monkeypatch, visible_row=None)
    try:
        with pytest.raises(PcsError) as exc:
            await pass_check(db_session, eq, _CHECKER, reason="校核通过")
    finally:
        monkeypatch.undo()

    assert exc.value.detail["retryable"] is True, "行暂不可见的并发冲突应标为可重试"
    assert "重试" in exc.value.message


async def test_claim_collision_different_payload_is_not_retryable(db_session, monkeypatch):
    """#2 后半段：撞主键且重查到 hash 不同 → 上游 bug，**重试无用**.

    与 _claim 顶部早返回分支是同一条件。绝不能标 retryable —— 否则真正的
    上游 bug 会被当成瞬时并发，无限重试把日志刷爆、该查的根因被埋掉。
    """
    from types import SimpleNamespace

    from app.services.supplier.confirmation_service import pass_check

    eq = await _make_equipment(db_session)
    _force_claim_collision(
        db_session, monkeypatch,
        visible_row=SimpleNamespace(payload_hash="0" * 64),
    )
    try:
        with pytest.raises(PcsError) as exc:
            await pass_check(db_session, eq, _CHECKER, reason="校核通过")
    finally:
        monkeypatch.undo()

    assert exc.value.detail["retryable"] is False
    assert "上游 bug" in exc.value.message
