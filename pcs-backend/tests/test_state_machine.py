"""Sprint 2 状态机守卫测试（ALLOWED_TRANSITIONS 矩阵）。"""

from __future__ import annotations

import pytest


def test_state_transition_enum_has_13_entries():
    from app.models.enums import StateTransition

    assert len(StateTransition) == 13, sorted(s.value for s in StateTransition)


def test_snapshot_status_enum_has_3_entries():
    from app.models.enums import SnapshotStatus

    assert {s.value for s in SnapshotStatus} == {"ACTIVE", "CONSUMED", "ABANDONED"}


def test_allowed_transitions_complete_13_events():
    """ALLOWED_TRANSITIONS 应覆盖全部 13 个 StateTransition。"""
    from app.models.enums import StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    covered = {t for (_, t) in ALLOWED_TRANSITIONS.keys()}
    assert covered == set(StateTransition)


def test_draft_can_submit_for_check():
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    assert (
        RecordSignStatus9.DRAFT,
        StateTransition.SUBMIT_FOR_CHECK,
    ) in ALLOWED_TRANSITIONS
    assert ALLOWED_TRANSITIONS[
        (RecordSignStatus9.DRAFT, StateTransition.SUBMIT_FOR_CHECK)
    ] == RecordSignStatus9.IN_APPROVAL


def test_check_rejected_can_resubmit():
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    assert (
        RecordSignStatus9.CHECK_REJECTED,
        StateTransition.SUBMIT_FOR_CHECK,
    ) in ALLOWED_TRANSITIONS


def test_in_approval_pass_check_to_checked():
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    assert (
        RecordSignStatus9.IN_APPROVAL,
        StateTransition.PASS_CHECK,
    ) in ALLOWED_TRANSITIONS
    assert (
        ALLOWED_TRANSITIONS[
            (RecordSignStatus9.IN_APPROVAL, StateTransition.PASS_CHECK)
        ]
        == RecordSignStatus9.CHANGED
        or
        ALLOWED_TRANSITIONS[
            (RecordSignStatus9.IN_APPROVAL, StateTransition.PASS_CHECK)
        ]
        == RecordSignStatus9.CHECKED
    )


def test_changed_can_request_reversal():
    """ADR-0012：撤销仅对 CHANGED 发起；CHECKED 不能再 request_reversal。"""
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    assert (
        RecordSignStatus9.CHANGED,
        StateTransition.REQUEST_REVERSAL,
    ) in ALLOWED_TRANSITIONS
    assert (
        RecordSignStatus9.CHECKED,
        StateTransition.REQUEST_REVERSAL,
    ) not in ALLOWED_TRANSITIONS


def test_checked_can_initiate_change():
    """ADR-0002：CHECKED → CHANGE_PENDING 主动变更路径。"""
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    assert (
        RecordSignStatus9.CHECKED,
        StateTransition.INITIATE_CHANGE,
    ) in ALLOWED_TRANSITIONS


def test_reversal_pending_resolves_back_to_checked_or_changed():
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    targets = {
        ALLOWED_TRANSITIONS[
            (RecordSignStatus9.REVERSAL_PENDING, StateTransition.APPROVE_REVERSAL)
        ],
        ALLOWED_TRANSITIONS[
            (RecordSignStatus9.REVERSAL_PENDING, StateTransition.REJECT_REVERSAL)
        ],
    }
    assert targets == {RecordSignStatus9.CHANGED, RecordSignStatus9.CHECKED}


def test_checked_to_stale_to_change_pending():
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    assert (
        RecordSignStatus9.CHECKED,
        StateTransition.MARK_STALE,
    ) in ALLOWED_TRANSITIONS
    # CONFIRM_CHANGE_PENDING 已合并到 RESOLVE_STALE_CHANGED（同一 STALE→CHANGE_PENDING）
    assert (
        RecordSignStatus9.STALE,
        StateTransition.RESOLVE_STALE_CHANGED,
    ) in ALLOWED_TRANSITIONS
    assert (
        RecordSignStatus9.CHANGE_PENDING,
        StateTransition.APPLY_CHANGE,
    ) in ALLOWED_TRANSITIONS


def test_change_pending_can_abandon_to_checked():
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    assert (
        ALLOWED_TRANSITIONS[
            (RecordSignStatus9.CHANGE_PENDING, StateTransition.ABANDON_CHANGE)
        ]
        == RecordSignStatus9.CHECKED
    )


def test_stale_resolve_two_paths():
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    assert (
        ALLOWED_TRANSITIONS[
            (RecordSignStatus9.STALE, StateTransition.RESOLVE_STALE_NO_CHANGE)
        ]
        == RecordSignStatus9.CHECKED
    )
    assert (
        ALLOWED_TRANSITIONS[
            (RecordSignStatus9.STALE, StateTransition.RESOLVE_STALE_CHANGED)
        ]
        == RecordSignStatus9.CHANGE_PENDING
    )


def test_obsolete_from_any_state():
    """OBSOLETE 是终止态：可从任何 9 态发起。"""
    from app.models.enums import RecordSignStatus9, StateTransition
    from app.services.state_machine import ALLOWED_TRANSITIONS

    for status in RecordSignStatus9:
        if status == RecordSignStatus9.OBSOLETE:
            continue
        assert (
            status,
            StateTransition.OBSOLETE,
        ) in ALLOWED_TRANSITIONS


async def test_invalid_transition_raises(db_session):
    """DRAFT + APPLY_CHANGE 非法，应抛 InvalidTransition。"""
    import uuid

    from app.models.calc import PipingResult
    from app.models.enums import RecordSignStatus9
    from app.services.state_machine import InvalidTransition, StateMachineService

    rec = PipingResult(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        seq_no=1,
        line_no="P-100",
        line_size="2\"",
        material_class="A1",
        fluid_code="W",
        fluid_name="Water",
        fluid_phase="L",
        fluid_category="NORMAL",
        source_pid="P&ID-001",
        line_from="V-100",
        line_to="P-101",
        norm_oper_press=1.0,
        max_oper_press=1.5,
        norm_oper_temp=40.0,
        max_oper_temp=80.0,
        design_press=2.0,
        design_temp=100.0,
        piping_category="GC2",
        pressure_test_medium="WATER",
        pressure_test_press=3.0,
        check_class="II",
        sign_status=RecordSignStatus9.DRAFT,
    )
    db_session.add(rec)
    await db_session.flush()
    svc = StateMachineService(db_session)
    from app.models.enums import StateTransition

    with pytest.raises(InvalidTransition):
        await svc.transition(
            record=rec,
            transition=StateTransition.APPLY_CHANGE,
            actor_user_id=uuid.uuid4(),
            actor_role="DESIGNER",
        )