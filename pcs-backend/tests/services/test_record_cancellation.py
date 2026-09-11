"""P3.x SIM-39: 记录弃用 (RECORD_CANCELLATION) 闭环。

ADRS：
- ADR-0009：OBSOLETE 与位号终身唯一（(project_id, tag_number/line_no) UNIQUE 覆盖 OBSOLETE）
- ADR-0002：已绑定记录弃用须走变更单（change_type=RECORD_CANCELLATION）

本测试覆盖：
1. 未绑定记录（locked_by_deliverable=False）：直接 OBSOLETE，调用 _unbound_obsolete 路径
2. 已绑定记录（locked_by_deliverable=True）：拒绝直接 OBSOLETE，提示需 RECORD_CANCELLATION 变更单
3. 已绑定记录的弃用：经 deliverable APPROVED → 自动 OBSOLETE 联动（_bound_obsolete_via_change）
4. OBSOLETE 后位号不可复用（依赖 (project_id, tag_number) UNIQUE 约束；测试覆盖服务层契约）
5. OBSOLETE 状态机事件：obsoleted_at/obsoleted_by/obsoleted_reason/obsoleted_via_deliverable_id 写入
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from app.services.exceptions import PcsError
from app.services.record_cancellation_service import (
    BoundObsoleteError,
    RecordCancellationService,
)


@dataclass
class _Actor:
    user_id: uuid.UUID = None  # type: ignore[assignment]
    role: str = "DESIGNER"


def _actor() -> _Actor:
    return _Actor(user_id=uuid.uuid4(), role="DESIGNER")


# ============================================================================
# 占位：fake session / fake record（与 SIM-38 同模式）
# ============================================================================


class FakeRecordTable:
    """占位 ORM 模型类（让 db.get(FakeRecordTable, pk) 返回对应记录）。"""

    pass


class _FakeRecord:
    """模拟一条带 sign_status + locked_by_deliverable 的业务记录。"""

    def __init__(
        self,
        *,
        record_id: uuid.UUID | None = None,
        sign_status: str = "CHECKED",
        locked_by_deliverable: bool = False,
        tag_number: str | None = None,
        obsoleted_via_deliverable_id: uuid.UUID | None = None,
        obsoleted_at: Any = None,
        obsoleted_by: uuid.UUID | None = None,
        obsoleted_reason: str | None = None,
        project_id: uuid.UUID | None = None,
    ) -> None:
        self.record_id = record_id or uuid.uuid4()
        self.sign_status = sign_status
        self.locked_by_deliverable = locked_by_deliverable
        self.tag_number = tag_number
        self.obsoleted_via_deliverable_id = obsoleted_via_deliverable_id
        self.obsoleted_at = obsoleted_at
        self.obsoleted_by = obsoleted_by
        self.obsoleted_reason = obsoleted_reason
        self.project_id = project_id or uuid.uuid4()


class _FakeSession:
    """最小 AsyncSession 占位。"""

    def __init__(self) -> None:
        self.store: dict = {}
        self.commits = 0
        self.added: list = []

    async def get(self, model_cls: type, pk: Any) -> Any:
        return self.store.get((model_cls, pk))

    async def execute(self, stmt: Any) -> Any:
        # mock：占位（不实际执行查询）
        class _Result:
            def scalar_one_or_none(self) -> Any:
                return None

            def scalars(self) -> _Result:
                return self

            def all(self) -> list:
                return []

        return _Result()

    def add(self, obj: Any) -> None:
        self.added.append(obj)

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        return None


# ============================================================================
# 1. 未绑定记录：直接 OBSOLETE
# ============================================================================


@pytest.mark.asyncio
async def test_unbound_record_obsolete_directly():
    """未绑定记录（locked_by_deliverable=False）→ 直接 OBSOLETE。"""
    rec = _FakeRecord(sign_status="CHECKED", locked_by_deliverable=False)
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    actor = _actor()
    result = await RecordCancellationService.obsolete(
        db,
        record_id=rec.record_id,
        actor=actor,
        reason="重复录入",
        record_table=FakeRecordTable,
    )

    assert rec.sign_status == "OBSOLETE"
    assert rec.obsoleted_at is not None
    assert rec.obsoleted_by == actor.user_id
    assert rec.obsoleted_reason == "重复录入"
    assert rec.obsoleted_via_deliverable_id is None  # 未走变更单
    assert result["obsoleted_via"] == "DIRECT"


@pytest.mark.asyncio
async def test_unbound_record_obsolete_supported_from_any_status():
    """未绑定记录：任何状态都可 OBSOLETE（DRAFT/CHECKED/CHANGED 等均允许）。"""
    for start_status in ("DRAFT", "CHECKED", "CHANGED", "CHANGE_PENDING", "STALE"):
        rec = _FakeRecord(sign_status=start_status, locked_by_deliverable=False)
        db = _FakeSession()
        db.store[(FakeRecordTable, rec.record_id)] = rec

        await RecordCancellationService.obsolete(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="x",
            record_table=FakeRecordTable,
        )
        assert rec.sign_status == "OBSOLETE", f"{start_status} 应可 OBSOLETE"


# ============================================================================
# 2. 已绑定记录：拒绝直接 OBSOLETE
# ============================================================================


@pytest.mark.asyncio
async def test_bound_record_direct_obsolete_rejected():
    """已绑定记录（locked_by_deliverable=True）：拒绝直接 OBSOLETE → BoundObsoleteError。"""
    rec = _FakeRecord(sign_status="CHECKED", locked_by_deliverable=True)
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    with pytest.raises(BoundObsoleteError) as exc_info:
        await RecordCancellationService.obsolete(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="x",
            record_table=FakeRecordTable,
        )
    assert "RECORD_CANCELLATION" in str(exc_info.value)
    # 状态不变
    assert rec.sign_status == "CHECKED"


@pytest.mark.asyncio
async def test_bound_record_direct_obsolete_error_includes_deliverable_hint():
    """BoundObsoleteError 提示需走 RECORD_CANCELLATION 变更单。"""
    rec = _FakeRecord(sign_status="CHECKED", locked_by_deliverable=True)
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    with pytest.raises(PcsError) as exc_info:
        await RecordCancellationService.obsolete(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="x",
            record_table=FakeRecordTable,
        )
    assert exc_info.value.code == "RECORD_BOUND_USE_CHANGE_NOTICE"
    assert exc_info.value.status == 409


# ============================================================================
# 3. 已绑定记录：经变更单 APPROVED 联动 OBSOLETE
# ============================================================================


@pytest.mark.asyncio
async def test_bound_record_obsolete_via_change_notice_approval():
    """已绑定记录：经 RECORD_CANCELLATION 变更单 APPROVED → 联动 OBSOLETE。

    由 ChangeNoticeService.approve 路径触发；RecordCancellationService 提供
    bound_obsolete_via_deliverable 入口供 approve 阶段调用。
    """
    rec = _FakeRecord(sign_status="CHECKED", locked_by_deliverable=True)
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    actor = _actor()
    deliverable_id = uuid.uuid4()
    await RecordCancellationService.bound_obsolete_via_deliverable(
        db,
        record_id=rec.record_id,
        deliverable_id=deliverable_id,
        actor=actor,
        record_table=FakeRecordTable,
    )

    assert rec.sign_status == "OBSOLETE"
    assert rec.obsoleted_at is not None
    assert rec.obsoleted_by == actor.user_id
    assert rec.obsoleted_via_deliverable_id == deliverable_id
    # 锁定标志保留（OBSOLETE 后仍记录被哪份交付物绑过）
    assert rec.locked_by_deliverable is True


@pytest.mark.asyncio
async def test_bound_record_obsolete_via_change_notice_requires_bound_flag():
    """bound_obsolete_via_deliverable：未绑定记录拒绝（应走直接 OBSOLETE）。"""
    rec = _FakeRecord(sign_status="CHECKED", locked_by_deliverable=False)
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    with pytest.raises(PcsError) as exc_info:
        await RecordCancellationService.bound_obsolete_via_deliverable(
            db,
            record_id=rec.record_id,
            deliverable_id=uuid.uuid4(),
            actor=_actor(),
            record_table=FakeRecordTable,
        )
    assert exc_info.value.code == "RECORD_NOT_BOUND"
    assert exc_info.value.status == 422


# ============================================================================
# 4. 记录不存在 / 错误状态
# ============================================================================


@pytest.mark.asyncio
async def test_obsolete_record_not_found():
    """record_id 不存在 → 404。"""
    db = _FakeSession()

    with pytest.raises(PcsError) as exc_info:
        await RecordCancellationService.obsolete(
            db,
            record_id=uuid.uuid4(),
            actor=_actor(),
            reason="x",
            record_table=FakeRecordTable,
        )
    assert exc_info.value.status == 404
    assert exc_info.value.code == "RECORD_NOT_FOUND"


@pytest.mark.asyncio
async def test_obsolete_already_obsolete_rejected():
    """已 OBSOLETE 记录不可再次 OBSOLETE → 409。"""
    rec = _FakeRecord(sign_status="OBSOLETE", locked_by_deliverable=False)
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    with pytest.raises(PcsError) as exc_info:
        await RecordCancellationService.obsolete(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="x",
            record_table=FakeRecordTable,
        )
    assert exc_info.value.status == 409
    assert exc_info.value.code == "RECORD_ALREADY_OBSOLETE"


# ============================================================================
# 5. 位号终身唯一契约（依赖 (project_id, tag_number) UNIQUE 约束；服务层契约）
# ============================================================================


@pytest.mark.asyncio
async def test_obsolete_preserves_tag_number_for_lifetime_uniqueness():
    """OBSOLETE 后 tag_number 保留（不释放、永不复用）。

    实际唯一约束在 DB 层（(project_id, tag_number) UNIQUE 覆盖 OBSOLETE）。
    服务层契约：OBSOLETE 不清空 tag_number。
    """
    rec = _FakeRecord(
        sign_status="CHECKED",
        locked_by_deliverable=False,
        tag_number="P-1001",
    )
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec

    await RecordCancellationService.obsolete(
        db,
        record_id=rec.record_id,
        actor=_actor(),
        reason="替换",
        record_table=FakeRecordTable,
    )

    assert rec.sign_status == "OBSOLETE"
    # tag_number 保留（不释放）
    assert rec.tag_number == "P-1001"


# ============================================================================
# 6. audit 落库
# ============================================================================


@pytest.mark.asyncio
async def test_unbound_obsolete_writes_audit():
    """未绑定 OBSOLETE 写 audit：RECORD_OBSOLETED。"""
    rec = _FakeRecord(sign_status="CHECKED", locked_by_deliverable=False)
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
        await RecordCancellationService.obsolete(
            db,
            record_id=rec.record_id,
            actor=_actor(),
            reason="x",
            record_table=FakeRecordTable,
        )
    finally:
        audit_mod.AuditService.write = orig_write  # type: ignore[assignment]

    obs_audits = [w for w in audit_writes if "OBSOLETE" in w["action"].name]
    assert len(obs_audits) == 1
    aw = obs_audits[0]
    assert aw["detail"]["from"] == "CHECKED"
    assert aw["detail"]["to"] == "OBSOLETE"
    assert aw["detail"]["obsoleted_via"] == "DIRECT"


@pytest.mark.asyncio
async def test_bound_obsolete_via_deliverable_writes_audit():
    """已绑定 OBSOLETE 写 audit：obsoleted_via=DELIVERABLE。"""
    rec = _FakeRecord(sign_status="CHECKED", locked_by_deliverable=True)
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
        deliverable_id = uuid.uuid4()
        await RecordCancellationService.bound_obsolete_via_deliverable(
            db,
            record_id=rec.record_id,
            deliverable_id=deliverable_id,
            actor=_actor(),
            record_table=FakeRecordTable,
        )
    finally:
        audit_mod.AuditService.write = orig_write  # type: ignore[assignment]

    obs_audits = [w for w in audit_writes if "OBSOLETE" in w["action"].name]
    assert len(obs_audits) == 1
    aw = obs_audits[0]
    assert aw["detail"]["obsoleted_via"] == "DELIVERABLE"
    assert aw["detail"]["deliverable_id"] == str(deliverable_id)
