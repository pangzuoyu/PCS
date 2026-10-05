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
