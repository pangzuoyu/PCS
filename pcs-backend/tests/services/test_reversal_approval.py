"""P3.x SIM-40: 反向签署 (REVERSAL_APPROVAL) 闭环。

ADRS：
- ADR-0010：分级撤销 REVERSAL_PENDING（3 级矩阵取 REVIEWER、4 级取 APPROVER）
- ADR-0002：撤销仅对 CHANGED 状态发起（CHECKED 不能直接 request_reversal）
- spec V1.0 §3.4：已凭生效的变更（locked_by_deliverable=True）只能发起反向新变更
  （CHANGE_REVERSAL），不能 REVERSAL_APPROVAL

状态机三事件（已在 state_machine.py 锁定）：
- CHANGED → REVERSAL_PENDING（REQUEST_REVERSAL）
- REVERSAL_PENDING → CHECKED（APPROVE_REVERSAL，恢复快照）
- REVERSAL_PENDING → CHANGED（REJECT_REVERSAL）

本测试覆盖：
1. request_reversal：CHANGED → REVERSAL_PENDING + reversal_* 字段写入
2. request_reversal：CHECKED/DRAFT/STALE/IN_APPROVAL 等不能发起（409）
3. request_reversal：locked_by_deliverable=True 拒绝（已对外生效 → 走 CHANGE_REVERSAL）
4. approve_reversal：REVERSAL_PENDING → CHECKED + 恢复最新 ACTIVE 快照 + 标记 CONSUMED
5. reject_reversal：REVERSAL_PENDING → CHANGED + reversal_rejected_* 字段写入
6. 边界：REVERSAL_PENDING 不能再次 request_reversal（409）
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import pytest

from app.services.exceptions import PcsError
from app.services.reversal_approval_service import ReversalApprovalService


@dataclass
class _Actor:
    user_id: uuid.UUID = None  # type: ignore[assignment]
    role: str = "REVIEWER"


def _actor(role: str = "REVIEWER") -> _Actor:
    return _Actor(user_id=uuid.uuid4(), role=role)


# ============================================================================
# 占位：fake session / fake record
# ============================================================================


class FakeRecordTable:
    """占位 ORM 模型类。"""

    pass


class _FakeRecord:
    """模拟一条带 sign_status + reversal_* 字段的业务记录。"""

    def __init__(
        self,
        *,
        sign_status: str = "CHANGED",
        locked_by_deliverable: bool = False,
        record_hash: str = "hash-initial",
        change_resolved_by: str | None = None,
        change_resolved_at: datetime | None = None,
    ) -> None:
        self.record_id = uuid.uuid4()
        self.sign_status = sign_status
        self.locked_by_deliverable = locked_by_deliverable
        self.record_hash = record_hash
        self.change_resolved_by = change_resolved_by
        self.change_resolved_at = change_resolved_at
        # reversal_* 组
        self.reversal_requested_at: datetime | None = None
        self.reversal_requested_by: uuid.UUID | None = None
        self.reversal_reason: str | None = None
        self.reversal_rejected_at: datetime | None = None
        self.reversal_rejected_by: uuid.UUID | None = None
        self.reversal_rejected_reason: str | None = None
        # 快照恢复目标：原本字段值
        self.before_value: str = "before-change-data"


class _FakeSnapshot:
    """模拟 ACTIVE 快照（service 恢复数据 + 标记 CONSUMED）。"""

    def __init__(
        self,
        *,
        record_id: uuid.UUID,
        snapshot_status: str = "ACTIVE",
        data: dict | None = None,
    ) -> None:
        self.snapshot_id = uuid.uuid4()
        self.record_id = record_id
        self.record_type = "FakeRecordTable"
        self.snapshot_status = snapshot_status
        self.data_snapshot_json = data or {"before_value": "snapshot-data"}
        self.created_at = datetime(2026, 9, 1, 12, 0, 0)


class _FakeSession:
    """最小 AsyncSession 占位。"""

    def __init__(self) -> None:
        self.store: dict = {}
        self.commits = 0
        self.added: list = []
        self.snapshots: list = []

    async def get(self, model_cls: type, pk: Any) -> Any:
        return self.store.get((model_cls, pk))

    async def execute(self, stmt: Any) -> Any:
        """模拟「查最新 ACTIVE 快照」查询（approve_reversal 用）。"""
        # 简化：返回 self.snapshots 中第一个 ACTIVE
        active = next(
            (s for s in self.snapshots if s.snapshot_status == "ACTIVE"),
            None,
        )

        class _Result:
            def __init__(self, value: Any) -> None:
                self._value = value

            def scalar_one_or_none(self) -> Any:
                return self._value

        return _Result(active)

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        if isinstance(obj, _FakeSnapshot):
            self.snapshots.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        return None


# ============================================================================
# 1. request_reversal：CHANGED → REVERSAL_PENDING
# ============================================================================


@pytest.mark.asyncio
async def test_request_reversal_changes_changed_to_reversal_pending():
    """CHANGED → REVERSAL_PENDING + reversal_* 字段写入 + audit。"""
    rec = _FakeRecord(sign_status="CHANGED")
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    actor = _actor()
    result = await ReversalApprovalService.request_reversal(
        db,
        record_id=rec.record_id,
        actor=actor,
        reason="数据录入错误，需恢复",
        record_table=FakeRecordTable,
    )

    assert rec.sign_status == "REVERSAL_PENDING"
    assert rec.reversal_requested_by == actor.user_id
    assert rec.reversal_requested_at is not None
    assert rec.reversal_reason == "数据录入错误，需恢复"
    assert result["from"] == "CHANGED"
    assert result["to"] == "REVERSAL_PENDING"


@pytest.mark.asyncio
async def test_request_reversal_rejects_non_changed_status():
    """仅 CHANGED 可发起 request_reversal；其他状态 409。"""
    for bad_status in ("CHECKED", "DRAFT", "STALE", "IN_APPROVAL", "REVERSAL_PENDING", "OBSOLETE"):
        rec = _FakeRecord(sign_status=bad_status)
        db = _FakeSession()
        db.store[(FakeRecordTable, rec.record_id)] = rec

        with pytest.raises(PcsError) as exc_info:
            await ReversalApprovalService.request_reversal(
                db,
                record_id=rec.record_id,
                actor=_actor(),
                reason="x",
                record_table=FakeRecordTable,
            )
        assert exc_info.value.status == 409
        assert exc_info.value.code == "REVERSAL_BAD_STATE"


@pytest.mark.asyncio
async def test_request_reversal_rejects_locked_by_deliverable():
    """locked_by_deliverable=True → 已对外生效，需走 CHANGE_REVERSAL 新变更单（不可 REVERSAL）。"""
    rec = _FakeRecord(sign_status="CHANGED", locked_by_deliverable=True)
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    with pytest.raises(PcsError) as exc_info:
        await ReversalApprovalService.request_reversal(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="x",
            record_table=FakeRecordTable,
        )
    assert exc_info.value.status == 409
    assert exc_info.value.code == "REVERSAL_LOCKED_USE_CHANGE_REVERSAL"
    # 状态不变
    assert rec.sign_status == "CHANGED"


@pytest.mark.asyncio
async def test_request_reversal_requires_reason():
    """request_reversal 必须有 reason（spec V1.0 §3.4 撤销理由）。"""
    rec = _FakeRecord(sign_status="CHANGED")
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    with pytest.raises(PcsError) as exc_info:
        await ReversalApprovalService.request_reversal(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="",
            record_table=FakeRecordTable,
        )
    assert exc_info.value.status == 422
    assert exc_info.value.code == "REVERSAL_REASON_REQUIRED"


@pytest.mark.asyncio
async def test_request_reversal_record_not_found():
    """record_id 不存在 → 404。"""
    db = _FakeSession()

    with pytest.raises(PcsError) as exc_info:
        await ReversalApprovalService.request_reversal(
            db,
            record_id=uuid.uuid4(),
            actor=_actor(),
            reason="x",
            record_table=FakeRecordTable,
        )
    assert exc_info.value.status == 404


# ============================================================================
# 2. approve_reversal：REVERSAL_PENDING → CHECKED + 快照恢复
# ============================================================================


@pytest.mark.asyncio
async def test_approve_reversal_restores_to_checked_and_recovers_snapshot():
    """approve_reversal：REVERSAL_PENDING → CHECKED + 恢复 ACTIVE 快照 + 标记 CONSUMED。"""
    rec = _FakeRecord(sign_status="REVERSAL_PENDING")
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    # 注入 ACTIVE 快照
    snap = _FakeSnapshot(record_id=rec.record_id, snapshot_status="ACTIVE")
    db.snapshots.append(snap)

    actor = _actor(role="REVIEWER")
    result = await ReversalApprovalService.approve_reversal(
        db,
        record_id=rec.record_id,
        actor=actor,
        record_table=FakeRecordTable,
    )

    # 状态：REVERSAL_PENDING → CHECKED
    assert rec.sign_status == "CHECKED"
    assert result["from"] == "REVERSAL_PENDING"
    assert result["to"] == "CHECKED"
    # 快照数据已恢复到 record 字段
    assert rec.before_value == "snapshot-data"
    # 快照已标记 CONSUMED
    assert snap.snapshot_status == "CONSUMED"


@pytest.mark.asyncio
async def test_approve_reversal_no_active_snapshot_still_resolves():
    """approve_reversal：无 ACTIVE 快照 → 直接 CHECKED（不阻断）。"""
    rec = _FakeRecord(sign_status="REVERSAL_PENDING")
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    await ReversalApprovalService.approve_reversal(
        db,
        record_id=rec.record_id,
        actor=_actor(),
        record_table=FakeRecordTable,
    )

    assert rec.sign_status == "CHECKED"
    assert rec.before_value == "before-change-data"  # 原值不变（无快照可恢复）


@pytest.mark.asyncio
async def test_approve_reversal_rejects_non_reversal_pending():
    """approve_reversal：仅 REVERSAL_PENDING 可批；其他状态 409。"""
    for bad_status in ("CHECKED", "CHANGED", "DRAFT", "STALE"):
        rec = _FakeRecord(sign_status=bad_status)
        db = _FakeSession()
        db.store[(FakeRecordTable, rec.record_id)] = rec

        with pytest.raises(PcsError) as exc_info:
            await ReversalApprovalService.approve_reversal(
                db,
                record_id=rec.record_id,
                actor=_actor(),
                record_table=FakeRecordTable,
            )
        assert exc_info.value.status == 409


# ============================================================================
# 3. reject_reversal：REVERSAL_PENDING → CHANGED
# ============================================================================


@pytest.mark.asyncio
async def test_reject_reversal_back_to_changed():
    """reject_reversal：REVERSAL_PENDING → CHANGED + rejection 字段写入。"""
    rec = _FakeRecord(sign_status="REVERSAL_PENDING")
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    actor = _actor(role="APPROVER")
    result = await ReversalApprovalService.reject_reversal(
        db,
        record_id=rec.record_id,
        actor=actor,
        reason="证据不足，维持变更",
        record_table=FakeRecordTable,
    )

    assert rec.sign_status == "CHANGED"
    assert rec.reversal_rejected_at is not None
    assert rec.reversal_rejected_by == actor.user_id
    assert rec.reversal_rejected_reason == "证据不足，维持变更"
    assert result["from"] == "REVERSAL_PENDING"
    assert result["to"] == "CHANGED"


@pytest.mark.asyncio
async def test_reject_reversal_requires_reason():
    """reject_reversal 必须有 reason。"""
    rec = _FakeRecord(sign_status="REVERSAL_PENDING")
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    with pytest.raises(PcsError) as exc_info:
        await ReversalApprovalService.reject_reversal(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="",
            record_table=FakeRecordTable,
        )
    assert exc_info.value.status == 422


@pytest.mark.asyncio
async def test_reject_reversal_rejects_non_reversal_pending():
    """reject_reversal：仅 REVERSAL_PENDING 可拒绝。"""
    rec = _FakeRecord(sign_status="CHECKED")
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    with pytest.raises(PcsError) as exc_info:
        await ReversalApprovalService.reject_reversal(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="x",
            record_table=FakeRecordTable,
        )
    assert exc_info.value.status == 409


# ============================================================================
# 4. audit 落库（3 个事件各自独立 audit）
# ============================================================================


@pytest.mark.asyncio
async def test_full_reversal_cycle_writes_three_audits():
    """完整周期：request → approve 写 3 条 audit（CHANGE_REVERSAL_REQUESTED/APPROVED）。"""
    rec = _FakeRecord(sign_status="CHANGED")
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    from app.services import audit_service as audit_mod

    audit_writes: list[dict] = []

    async def _capture(self, *, action, resource_type, resource_id, user_id, detail):
        audit_writes.append(
            {"action": action, "resource_type": resource_type,
             "resource_id": resource_id, "user_id": user_id, "detail": detail}
        )

    orig_write = audit_mod.AuditService.write
    audit_mod.AuditService.write = _capture  # type: ignore[assignment]
    try:
        await ReversalApprovalService.request_reversal(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="测试",
            record_table=FakeRecordTable,
        )
        snap = _FakeSnapshot(record_id=rec.record_id, snapshot_status="ACTIVE")
        db.snapshots.append(snap)
        await ReversalApprovalService.approve_reversal(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            record_table=FakeRecordTable,
        )
    finally:
        audit_mod.AuditService.write = orig_write  # type: ignore[assignment]

    actions = [w["action"].name for w in audit_writes]
    assert "CHANGE_REVERSAL_REQUESTED" in actions
    assert "CHANGE_REVERSAL_APPROVED" in actions
