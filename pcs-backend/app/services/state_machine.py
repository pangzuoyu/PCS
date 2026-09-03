"""状态机（Sprint 2 核心）。

ALLOWED_TRANSITIONS：13 事件 × RecordSignStatus9 9 态 → to_status。
所有转移走 StateMachineService.transition：守卫 → 写 audit → 必要时快照。
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import (
    AuditAction,
    RecordSignStatus9,
    SnapshotStatus,
    StateTransition,
)

if TYPE_CHECKING:
    from app.models.mixins import RecordMixin


def _record_pk(record: RecordMixin) -> uuid.UUID:
    """Extract PK UUID via mapper inspection (RecordMixin 不自带 __tablename__)。"""
    mapper = inspect(record.__class__)
    if mapper is None:
        raise TypeError(f"cannot inspect mapper for {record.__class__.__name__}")
    pk = mapper.primary_key[0]
    val = getattr(record, pk.name)
    if not isinstance(val, uuid.UUID):
        raise TypeError(f"record PK must be UUID, got {type(val).__name__}")
    return val


def _record_table_name(record: RecordMixin) -> str:
    """Extract __tablename__ via mapper inspection。"""
    mapper = inspect(record.__class__)
    if mapper is None or mapper.local_table is None:
        raise TypeError(f"cannot resolve table for {record.__class__.__name__}")
    return mapper.local_table.name


ALLOWED_TRANSITIONS: dict[
    tuple[RecordSignStatus9, StateTransition], RecordSignStatus9
] = {
    (RecordSignStatus9.DRAFT, StateTransition.SUBMIT_FOR_CHECK):
        RecordSignStatus9.IN_APPROVAL,
    (RecordSignStatus9.CHECK_REJECTED, StateTransition.SUBMIT_FOR_CHECK):
        RecordSignStatus9.IN_APPROVAL,
    (RecordSignStatus9.IN_APPROVAL, StateTransition.PASS_CHECK):
        RecordSignStatus9.CHECKED,
    (RecordSignStatus9.IN_APPROVAL, StateTransition.REJECT_CHECK):
        RecordSignStatus9.CHECK_REJECTED,
    # ADR-0002：CHECKED → CHANGE_PENDING 主动变更路径（不经 STALE 中转）
    (RecordSignStatus9.CHECKED, StateTransition.INITIATE_CHANGE):
        RecordSignStatus9.CHANGE_PENDING,
    # ADR-0012：撤销仅对 CHANGED 状态发起
    (RecordSignStatus9.CHANGED, StateTransition.REQUEST_REVERSAL):
        RecordSignStatus9.REVERSAL_PENDING,
    # 批准撤销 = 恢复快照 → CHECKED；拒绝撤销 = 维持 CHANGED
    (RecordSignStatus9.REVERSAL_PENDING, StateTransition.APPROVE_REVERSAL):
        RecordSignStatus9.CHECKED,
    (RecordSignStatus9.REVERSAL_PENDING, StateTransition.REJECT_REVERSAL):
        RecordSignStatus9.CHANGED,
    (RecordSignStatus9.CHECKED, StateTransition.MARK_STALE):
        RecordSignStatus9.STALE,
    (RecordSignStatus9.CHANGE_PENDING, StateTransition.APPLY_CHANGE):
        RecordSignStatus9.CHANGED,
    (RecordSignStatus9.CHANGE_PENDING, StateTransition.ABANDON_CHANGE):
        RecordSignStatus9.CHECKED,
    (RecordSignStatus9.STALE, StateTransition.RESOLVE_STALE_NO_CHANGE):
        RecordSignStatus9.CHECKED,
    (RecordSignStatus9.STALE, StateTransition.RESOLVE_STALE_CHANGED):
        RecordSignStatus9.CHANGE_PENDING,
    # OBSOLETE：任意态
    (RecordSignStatus9.DRAFT, StateTransition.OBSOLETE): RecordSignStatus9.OBSOLETE,
    (RecordSignStatus9.IN_APPROVAL, StateTransition.OBSOLETE):
        RecordSignStatus9.OBSOLETE,
    (RecordSignStatus9.CHECKED, StateTransition.OBSOLETE): RecordSignStatus9.OBSOLETE,
    (RecordSignStatus9.CHECK_REJECTED, StateTransition.OBSOLETE):
        RecordSignStatus9.OBSOLETE,
    (RecordSignStatus9.STALE, StateTransition.OBSOLETE): RecordSignStatus9.OBSOLETE,
    (RecordSignStatus9.CHANGE_PENDING, StateTransition.OBSOLETE):
        RecordSignStatus9.OBSOLETE,
    (RecordSignStatus9.CHANGED, StateTransition.OBSOLETE): RecordSignStatus9.OBSOLETE,
    (RecordSignStatus9.REVERSAL_PENDING, StateTransition.OBSOLETE):
        RecordSignStatus9.OBSOLETE,
}


# 角色权限：transition → 允许的角色集合
TRANSITION_ROLES: dict[StateTransition, set[str]] = {
    StateTransition.SUBMIT_FOR_CHECK: {"DESIGNER", "CHECKER", "APPROVER", "SYSADMIN"},
    StateTransition.PASS_CHECK: {"CHECKER", "APPROVER", "SYSADMIN"},
    StateTransition.REJECT_CHECK: {"CHECKER", "APPROVER", "SYSADMIN"},
    StateTransition.REQUEST_REVERSAL: {"DESIGNER", "CHECKER", "APPROVER", "SYSADMIN"},
    StateTransition.APPROVE_REVERSAL: {"APPROVER", "SYSADMIN"},
    StateTransition.REJECT_REVERSAL: {"APPROVER", "SYSADMIN"},
    StateTransition.MARK_STALE: {"DESIGNER", "CHECKER", "SYSADMIN"},
    StateTransition.INITIATE_CHANGE: {"DESIGNER", "SYSADMIN"},  # ADR-0002 主动变更
    StateTransition.APPLY_CHANGE: {"DESIGNER", "CHECKER", "SYSADMIN"},
    StateTransition.ABANDON_CHANGE: {"DESIGNER", "SYSADMIN"},
    StateTransition.RESOLVE_STALE_NO_CHANGE: {"CHECKER", "SYSADMIN"},
    StateTransition.RESOLVE_STALE_CHANGED: {"CHECKER", "DESIGNER", "SYSADMIN"},
    StateTransition.OBSOLETE: {"DESIGNER", "CHECKER", "APPROVER", "SYSADMIN"},
}


# 转移后写 audit 动作：transition → AuditAction
TRANSITION_AUDIT_ACTION: dict[StateTransition, AuditAction] = {
    StateTransition.SUBMIT_FOR_CHECK: AuditAction.RECORD_TRANSITION,
    StateTransition.PASS_CHECK: AuditAction.APPROVAL_STEP_PASSED,
    StateTransition.REJECT_CHECK: AuditAction.APPROVAL_STEP_REJECTED,
    StateTransition.REQUEST_REVERSAL: AuditAction.CHANGE_REVERSAL_REQUESTED,
    StateTransition.APPROVE_REVERSAL: AuditAction.CHANGE_REVERSAL_APPROVED,
    StateTransition.REJECT_REVERSAL: AuditAction.CHANGE_REVERSAL_REJECTED,
    StateTransition.MARK_STALE: AuditAction.RECORD_TRANSITION,
    StateTransition.INITIATE_CHANGE: AuditAction.CHANGE_INITIATED,
    StateTransition.APPLY_CHANGE: AuditAction.CHANGE_RESOLVED,
    StateTransition.ABANDON_CHANGE: AuditAction.CHANGE_ABANDONED,
    StateTransition.RESOLVE_STALE_NO_CHANGE: AuditAction.STALE_RESOLVED_NO_CHANGE,
    StateTransition.RESOLVE_STALE_CHANGED: AuditAction.STALE_RESOLVED_CHANGED,
    StateTransition.OBSOLETE: AuditAction.RECORD_OBSOLETED,
}


# 转移触发创建 record_change_snapshots 的事件
# ADR-0024：仅"数据即将被改"的转移写快照；MARK_STALE 不写（CHECKED→STALE 数据未变）。
# APPLY_CHANGE 是保留已有快照（不是新建，是快照仍为 ACTIVE）；
# ABANDON_CHANGE / APPROVE_REVERSAL 是消费快照（恢复数据 + 标记 CONSUMED）。
SNAPSHOT_TRIGGERS: set[StateTransition] = {
    StateTransition.INITIATE_CHANGE,  # CHECKED → CHANGE_PENDING 主动变更
    StateTransition.RESOLVE_STALE_CHANGED,  # STALE → CHANGE_PENDING 上游变更确认
}

# 转移触发"恢复最新 ACTIVE 快照 + 标记 CONSUMED"的事件
SNAPSHOT_RESTORERS: set[StateTransition] = {
    StateTransition.ABANDON_CHANGE,  # 撤销变更 → 恢复 → CHECKED
    StateTransition.APPROVE_REVERSAL,  # 批准撤销 → 恢复 → CHECKED
}


class InvalidTransition(Exception):
    """状态机非法转移。"""

    def __init__(self, from_status: str, transition: str) -> None:
        super().__init__(f"Invalid transition {transition} from {from_status}")
        self.from_status = from_status
        self.transition = transition


class RoleForbidden(Exception):
    """角色无权执行该转移。"""


class StateMachineService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _write_audit(
        self,
        *,
        action: AuditAction,
        resource_type: str,
        resource_id: uuid.UUID,
        user_id: uuid.UUID | None,
        detail: dict | None,
    ) -> None:
        from app.services.audit_service import AuditService

        await AuditService(self.session).write(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            detail=detail,
        )

    async def _create_snapshot_if_needed(
        self,
        *,
        transition: StateTransition,
        record: RecordMixin,
        actor_user_id: uuid.UUID | None,
    ) -> None:
        if transition not in SNAPSHOT_TRIGGERS:
            return

        from app.models.deliverable import RecordChangeSnapshot

        # ADR-0024：MARK_STALE 已从 SNAPSHOT_TRIGGERS 移除；进入此函数的转移仅
        # APPLY_CHANGE / RESOLVE_STALE_CHANGED，统一 BEFORE_CHANGE。
        snapshot = RecordChangeSnapshot(
            record_type=record.__class__.__name__,
            record_id=_record_pk(record),
            record_hash=record.record_hash or "",
            data_snapshot_json={},
            snapshot_reason="BEFORE_CHANGE",
            snapshot_source="MANUAL_CHANGE",
            snapshot_status=SnapshotStatus.ACTIVE.value,
            created_by=actor_user_id,
        )
        self.session.add(snapshot)

    async def _restore_snapshot_if_needed(
        self,
        *,
        transition: StateTransition,
        record: RecordMixin,
    ) -> None:
        """ABANDON_CHANGE / APPROVE_REVERSAL：恢复最新 ACTIVE 快照 + 标记 CONSUMED。"""
        if transition not in SNAPSHOT_RESTORERS:
            return

        from sqlalchemy import select

        from app.models.deliverable import RecordChangeSnapshot

        pk = _record_pk(record)
        snap = (
            await self.session.execute(
                select(RecordChangeSnapshot)
                .where(
                    RecordChangeSnapshot.record_type == record.__class__.__name__,
                    RecordChangeSnapshot.record_id == pk,
                    RecordChangeSnapshot.snapshot_status == SnapshotStatus.ACTIVE.value,
                )
                .order_by(RecordChangeSnapshot.created_at.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
        if snap is None:
            return
        data = snap.data_snapshot_json or {}
        for col, val in data.items():
            if hasattr(record, col):
                setattr(record, col, val)
        snap.snapshot_status = SnapshotStatus.CONSUMED.value

    async def transition(
        self,
        *,
        record: RecordMixin,
        transition: StateTransition,
        actor_user_id: uuid.UUID,
        actor_role: str,
        reason: str | None = None,
    ) -> RecordMixin:
        from_status = RecordSignStatus9(record.sign_status)
        if actor_role not in TRANSITION_ROLES[transition]:
            raise RoleForbidden(
                f"role={actor_role} cannot perform {transition.value}"
            )
        key = (from_status, transition)
        if key not in ALLOWED_TRANSITIONS:
            raise InvalidTransition(from_status.value, transition.value)
        to_status = ALLOWED_TRANSITIONS[key]

        record.sign_status = to_status
        if transition == StateTransition.PASS_CHECK:
            record.approval_step = None
        if transition == StateTransition.MARK_STALE:
            record.change_pending_since = datetime.now(UTC)
        if transition == StateTransition.INITIATE_CHANGE:
            record.change_pending_since = datetime.now(UTC)
        if transition == StateTransition.APPLY_CHANGE:
            record.change_resolved_at = datetime.now(UTC)
            record.change_resolved_by = str(actor_user_id)
        if transition == StateTransition.ABANDON_CHANGE:
            record.change_abandoned_at = datetime.now(UTC)
            record.change_abandoned_reason = reason or ""
        if transition == StateTransition.REQUEST_REVERSAL:
            record.reversal_requested_at = datetime.now(UTC)
            record.reversal_requested_by = actor_user_id
            record.reversal_reason = reason or ""
        if transition == StateTransition.APPROVE_REVERSAL:
            record.reversal_approved_at = datetime.now(UTC)
            record.reversal_approved_by = actor_user_id
        if transition == StateTransition.OBSOLETE:
            record.obsoleted_at = datetime.now(UTC)
            record.obsoleted_by = actor_user_id
            record.obsoleted_reason = reason or ""

        await self.session.flush()
        await self._create_snapshot_if_needed(
            transition=transition,
            record=record,
            actor_user_id=actor_user_id,
        )
        await self._restore_snapshot_if_needed(
            transition=transition,
            record=record,
        )
        await self._write_audit(
            action=TRANSITION_AUDIT_ACTION[transition],
            resource_type=_record_table_name(record),
            resource_id=_record_pk(record),
            user_id=actor_user_id,
            detail={
                "from": from_status.value,
                "to": to_status.value,
                "transition": transition.value,
                "reason": reason,
                "role": actor_role,
            },
        )
        return record