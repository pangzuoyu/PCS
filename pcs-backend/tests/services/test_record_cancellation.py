"""P3.x SIM-39: 记录弃用 (RECORD_CANCELLATION) 闭环。

ADRS：
- ADR-0009：OBSOLETE 与位号终身唯一（(project_id, tag_number/line_no) UNIQUE 覆盖 OBSOLETE）
- ADR-0002：已绑定记录弃用须走变更单（change_type=RECORD_CANCELLATION）

本测试覆盖：
1. 未对外生效的记录：直接 OBSOLETE（_unbound_obsolete 路径）
2. **已对外生效**的记录：拒绝直接 OBSOLETE，提示需 RECORD_CANCELLATION 变更单
   —— ⚠️ 「已对外生效」的判据在 TODO-082 换成了**真实可判定**的条件（记录被
   一张 **APPROVED** 的交付物绑定）⇒ 那两道门的**真库**用例在
   `tests/services/test_record_publication_gate.py`；本文件里依赖旧标志
   （`locked_by_deliverable`）的用例已随之删除
3. 已对外生效记录的弃用：经 deliverable APPROVED → 自动 OBSOLETE 联动
   （bound_obsolete_via_deliverable）
4. OBSOLETE 后位号不可复用（依赖 (project_id, tag_number) UNIQUE 约束；测试覆盖服务层契约）
5. OBSOLETE 状态机事件：obsoleted_at/obsoleted_by/obsoleted_reason/obsoleted_via_deliverable_id 写入
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from app.services.exceptions import PcsError
from app.services.record_cancellation_service import RecordCancellationService


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
    """模拟一条带 sign_status 的业务记录。"""

    def __init__(
        self,
        *,
        record_id: uuid.UUID | None = None,
        sign_status: str = "CHECKED",
        tag_number: str | None = None,
        obsoleted_via_deliverable_id: uuid.UUID | None = None,
        obsoleted_at: Any = None,
        obsoleted_by: uuid.UUID | None = None,
        obsoleted_reason: str | None = None,
        project_id: uuid.UUID | None = None,
    ) -> None:
        self.record_id = record_id or uuid.uuid4()
        self.sign_status = sign_status
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
        """ORM 主键查询占位：从 self.store[(model_cls, pk)] 返回。"""
        return self.store.get((model_cls, pk))

    async def execute(self, stmt: Any) -> Any:
        """execute 占位：不实际执行查询，返回空 _Result（依赖 db.get 主键查）。"""
        class _Result:
            def scalar_one_or_none(self) -> Any:
                """scalar_one_or_none 占位：返回 None（不影响 service 路径）。"""
                return None

            def scalars(self) -> _Result:
                """链式 .scalars() 占位（返回自身）。"""
                return self

            def all(self) -> list:
                """all 占位：返回空列表。"""
                return []

        return _Result()

    def add(self, obj: Any) -> None:
        """记录 add 调用，service 用 self.added 断言写入对象列表。"""
        self.added.append(obj)

    async def commit(self) -> None:
        """commit 计数自增（service 断言事务提交次数）。"""
        self.commits += 1

    async def flush(self) -> None:
        """flush 占位（无实际操作）。"""
        return None


# ============================================================================
# 1. 未绑定记录：直接 OBSOLETE
# ============================================================================


@pytest.mark.asyncio
async def test_unbound_record_obsolete_directly():
    """未绑定记录（locked_by_deliverable=False）→ 直接 OBSOLETE。"""
    rec = _FakeRecord(sign_status="CHECKED")
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
        rec = _FakeRecord(sign_status=start_status)
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
async def test_bound_record_obsolete_via_change_notice_requires_bound_flag():
    """bound_obsolete_via_deliverable：未绑定记录拒绝（应走直接 OBSOLETE）。"""
    rec = _FakeRecord(sign_status="CHECKED")
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
    rec = _FakeRecord(sign_status="OBSOLETE")
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
    rec = _FakeRecord(sign_status="CHECKED")
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


