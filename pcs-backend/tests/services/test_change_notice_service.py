"""P3.x SIM-38: 一键变更单 (RECORD_CHANGE) 闭环。

变更单 = deliverables 表中 deliverable_type=CHANGE_NOTICE 的一行；
1:1 扩展表 change_notice_details（change_type/reason/triggered_by/source_record_type）。

ADRS：
- ADR-0008：变更单 = 交付物子类型
- ADR-0002：CHANGED 生命周期与变更单

本测试覆盖：
1. ChangeType 7 值枚举契约
2. create_change_notice 创建 deliverable + change_notice_details 双表
3. create_change_notice CHECKED 校验（仅 CHANGED 状态记录可发起变更单）
4. approve_change_notice 自动联动：CHANGED → CHECKED + 写 change_resolved_by
5. approve_change_notice 重复审批 409
6. create_change_notice 7 种 change_type 全枚举可写入
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from app.models.deliverable import ChangeNoticeDetail, Deliverable
from app.services.change_notice_service import (
    ChangeNoticeService,
    ChangeType,
    TriggeredBy,
)
from app.services.exceptions import PcsError


@dataclass
class _Actor:
    user_id: uuid.UUID = None  # type: ignore[assignment]
    role: str = "REVIEWER"


def _actor() -> _Actor:
    return _Actor(user_id=uuid.uuid4(), role="REVIEWER")


# ============================================================================
# ChangeType 7 值枚举契约（spec V1.0 §4）
# ============================================================================


def test_change_type_seven_values_contract():
    """ChangeType 7 值：D/P/U/C/R/R/O（与 spec V1.0 §4 字面一致）。"""
    assert ChangeType.DATA_CORRECTION.value == "DATA_CORRECTION"
    assert ChangeType.PROCESS_CHANGE.value == "PROCESS_CHANGE"
    assert ChangeType.UPSTREAM_CHANGE.value == "UPSTREAM_CHANGE"
    assert ChangeType.CLIENT_COMMENT.value == "CLIENT_COMMENT"
    assert ChangeType.RECORD_CANCELLATION.value == "RECORD_CANCELLATION"
    assert ChangeType.CHANGE_REVERSAL.value == "CHANGE_REVERSAL"
    assert ChangeType.OTHER.value == "OTHER"
    assert len(ChangeType) == 7


def test_triggered_by_two_values_contract():
    """TriggeredBy 2 值：MANUAL/UPSTREAM_CHANGE。"""
    assert TriggeredBy.MANUAL.value == "MANUAL"
    assert TriggeredBy.UPSTREAM_CHANGE.value == "UPSTREAM_CHANGE"
    assert len(TriggeredBy) == 2


# ============================================================================
# create_change_notice — 双表创建 + 校验
# ============================================================================


class _FakeDeliverable(Deliverable):
    """继承 Deliverable 的最小 fake：用于 SQLAlchemy select() / db.get() 兼容。

    测试只关心字段读写，不触发实际 ORM 持久化（fake session 不持久化）。
    """

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)


class _FakeChangeNoticeDetail(ChangeNoticeDetail):
    """继承 ChangeNoticeDetail 的最小 fake：用于 SQLAlchemy select() 兼容。"""

    def __init__(self, **kw: Any) -> None:
        super().__init__(**kw)


class _FakeRecord:
    """模拟一条带 sign_status 的业务记录（service 端通过 db.get 拿到）。"""

    def __init__(self, sign_status: str = "CHANGED", record_hash: str = "abc123") -> None:
        self.record_id = uuid.uuid4()
        self.sign_status = sign_status
        self.record_hash = record_hash
        self.change_resolved_by: str | None = None
        self.change_resolved_at: Any = None


class FakeRecordTable:
    """占位 ORM 模型类（让 db.get(FakeRecordTable, pk) 返回对应记录）。"""

    pass


class _FakeSession:
    """最小 AsyncSession：按 (model_class, pk) 索引到对应存储。

    支持 ORM 真类（Deliverable/ChangeNoticeDetail）与 fake 类（_FakeDeliverable/
    _FakeChangeNoticeDetail/FakeRecordTable）的双向映射：
    - 注册 fake 对象时存为 fake 类；查找 ORM 类时从 fake 类映射回 ORM 类。
    - add() 自动按 fake 类映射到对应 ORM 真类。
    """

    def __init__(self) -> None:
        # store[(model_cls, pk)] = obj
        self.store: dict = {}
        self.commits = 0
        self.added: list = []
        # fake 类 → ORM 真类的映射（实例化 add() 时使用）
        self._class_map: dict[type, type] = {}

    def register_class_map(self, fake_cls: type, orm_cls: type) -> None:
        """注册 fake → ORM 真类映射。"""
        self._class_map[fake_cls] = orm_cls

    async def get(self, model_cls: type, pk: Any) -> Any:
        # 1. 先查 ORM 真类
        obj = self.store.get((model_cls, pk))
        if obj is not None:
            return obj
        # 2. 再查 fake 类（通过反向映射：fake_cls → orm_cls）
        # 注入：当查询的 model_cls 是某个 fake_cls 映射的目标时，从 fake_cls 索引
        for fake_cls, orm_cls in self._class_map.items():
            if orm_cls is model_cls:
                obj = self.store.get((fake_cls, pk))
                if obj is not None:
                    return obj
            elif fake_cls is model_cls:
                obj = self.store.get((fake_cls, pk))
                if obj is not None:
                    return obj
        return None

    async def execute(self, stmt: Any) -> Any:
        # 模拟 ChangeNoticeDetail 查询（返回首个已注册的 detail）
        class _Result:
            def __init__(self, value: Any) -> None:
                self._value = value

            def scalar_one_or_none(self) -> Any:
                return self._value

        for (_m_cls, _), obj in self.store.items():
            if isinstance(obj, _FakeChangeNoticeDetail):
                return _Result(obj)
        return _Result(None)

    def add(self, obj: Any) -> None:
        self.added.append(obj)
        # 自动设置 PK
        if isinstance(obj, _FakeDeliverable) and not getattr(obj, "deliverable_id", None):
            obj.deliverable_id = uuid.uuid4()
        if isinstance(obj, _FakeChangeNoticeDetail) and not getattr(obj, "detail_id", None):
            obj.detail_id = uuid.uuid4()
        # 同步按 ORM 真类索引（service 用 db.get(Deliverable, pk) 时能找到）
        orm_cls = self._class_map.get(type(obj))
        if orm_cls is not None:
            pk = getattr(obj, "deliverable_id", None) or getattr(obj, "detail_id", None)
            if pk is not None:
                self.store[(orm_cls, pk)] = obj

    async def commit(self) -> None:
        self.commits += 1

    async def flush(self) -> None:
        return None


def _build_record_signing_session(sign_status: str = "CHANGED") -> tuple[_FakeSession, _FakeRecord]:
    rec = _FakeRecord(sign_status=sign_status)
    db = _FakeSession()
    db.store[(FakeRecordTable, rec.record_id)] = rec
    return db, rec


def _build_cn_session(
    sign_status: str = "PENDING",
) -> tuple[_FakeSession, _FakeDeliverable, _FakeChangeNoticeDetail]:
    """构造一个含 deliverable + change_notice_detail 的 fake session。"""
    deliverable_id = uuid.uuid4()
    deliverable = _FakeDeliverable(
        deliverable_id=deliverable_id,
        project_id=uuid.uuid4(),
        deliverable_type="CHANGE_NOTICE",
        version_purpose="ISSUED_FOR_CHANGE",
        sign_status=sign_status,
    )
    detail = _FakeChangeNoticeDetail(
        detail_id=uuid.uuid4(),
        deliverable_id=deliverable_id,
        change_type="DATA_CORRECTION",
        reason="r",
        triggered_by="MANUAL",
        source_record_type="FakeRecordTable",
    )
    db = _FakeSession()
    # fake → ORM 真类映射：service 用 db.get(Deliverable, pk) 时能找到 _FakeDeliverable
    db.register_class_map(_FakeDeliverable, Deliverable)
    db.register_class_map(_FakeChangeNoticeDetail, ChangeNoticeDetail)
    db.store[(_FakeDeliverable, deliverable_id)] = deliverable
    db.store[(_FakeChangeNoticeDetail, detail.detail_id)] = detail
    return db, deliverable, detail


@pytest.mark.asyncio
async def test_create_change_notice_creates_both_tables():
    """create_change_notice 同时写 deliverables + change_notice_details。"""
    db, rec = _build_record_signing_session(sign_status="CHANGED")
    # fake → ORM 真类映射（add() 自动按真类索引，get() 反查）
    db.register_class_map(_FakeDeliverable, Deliverable)
    db.register_class_map(_FakeChangeNoticeDetail, ChangeNoticeDetail)
    project_id = uuid.uuid4()
    actor = _actor()

    cn = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec.record_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="管径修正",
        triggered_by=TriggeredBy.MANUAL,
        actor=actor,
        record_table=FakeRecordTable,
    )

    # deliverables 行
    assert cn["deliverable_type"] == "CHANGE_NOTICE"
    assert cn["version_purpose"] == "ISSUED_FOR_CHANGE"
    assert cn["project_id"] == project_id
    assert cn["title"]
    assert cn["doc_no"]

    # change_notice_details 1:1 扩展
    cnd = cn["detail"]
    assert cnd["change_type"] == "DATA_CORRECTION"
    assert cnd["reason"] == "管径修正"
    assert cnd["triggered_by"] == "MANUAL"

    # 写入 deliverable + detail（不含 audit）
    domain_added = [
        x for x in db.added
        if isinstance(x, (Deliverable, ChangeNoticeDetail))
    ]
    assert len(domain_added) == 2
    assert db.commits == 1


@pytest.mark.asyncio
async def test_create_change_notice_rejects_non_changed_status():
    """仅 CHANGED 状态记录可发起变更单；CHECKED/DRAFT/STALE 等 422。"""
    for bad_status in ("CHECKED", "DRAFT", "STALE", "CHANGE_PENDING", "OBSOLETE"):
        db, rec = _build_record_signing_session(sign_status=bad_status)

        with pytest.raises(PcsError) as exc_info:
            await ChangeNoticeService.create_change_notice(
                db,
                project_id=uuid.uuid4(),
                record_id=rec.record_id,
                change_type=ChangeType.DATA_CORRECTION,
                reason="x",
                triggered_by=TriggeredBy.MANUAL,
                actor=_actor(),
                record_table=FakeRecordTable,
            )
        assert exc_info.value.status == 422
        assert exc_info.value.code == "CHANGE_NOTICE_BAD_STATE"


@pytest.mark.asyncio
async def test_create_change_notice_record_not_found():
    """record_id 不存在 → 404。"""
    db = _FakeSession()

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService.create_change_notice(
            db,
            project_id=uuid.uuid4(),
            record_id=uuid.uuid4(),
            change_type=ChangeType.DATA_CORRECTION,
            reason="x",
            triggered_by=TriggeredBy.MANUAL,
            actor=_actor(),
            record_table=FakeRecordTable,
        )
    assert exc_info.value.status == 404


@pytest.mark.asyncio
@pytest.mark.parametrize("change_type", list(ChangeType))
async def test_create_change_notice_all_seven_change_types_accepted(change_type):
    """7 种 change_type 全部可创建变更单。"""
    db, rec = _build_record_signing_session(sign_status="CHANGED")

    cn = await ChangeNoticeService.create_change_notice(
        db,
        project_id=uuid.uuid4(),
        record_id=rec.record_id,
        change_type=change_type,
        reason="test",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=FakeRecordTable,
    )
    assert cn["detail"]["change_type"] == change_type.value


# ============================================================================
# _apply_record_resolution — 自动联动 CHANGED → CHECKED + change_resolved_by
# ============================================================================


@pytest.mark.asyncio
async def test_apply_record_resolution_changes_changed_to_checked():
    """_apply_record_resolution：CHANGED → CHECKED + change_resolved_by 写入。"""
    db, rec = _build_record_signing_session(sign_status="CHANGED")
    actor = _actor()

    result = await ChangeNoticeService._apply_record_resolution(
        db,
        record_table=FakeRecordTable,
        record_id=rec.record_id,
        actor=actor,
    )

    assert rec.sign_status == "CHECKED"
    assert rec.change_resolved_by == str(actor.user_id)
    assert result["from"] == "CHANGED"
    assert result["to"] == "CHECKED"
    assert result["record_id"] == str(rec.record_id)


@pytest.mark.asyncio
async def test_apply_record_resolution_rejects_non_changed():
    """_apply_record_resolution：仅 CHANGED 可 resolve；其他 409。"""
    db, rec = _build_record_signing_session(sign_status="CHECKED")

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService._apply_record_resolution(
            db,
            record_table=FakeRecordTable,
            record_id=rec.record_id,
            actor=_actor(),
        )
    assert exc_info.value.status == 409


@pytest.mark.asyncio
async def test_apply_record_resolution_record_not_found():
    """_apply_record_resolution：record 不存在 → 404。"""
    db = _FakeSession()

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService._apply_record_resolution(
            db,
            record_table=FakeRecordTable,
            record_id=uuid.uuid4(),
            actor=_actor(),
        )
    assert exc_info.value.status == 404


# ============================================================================
# approve_change_notice — PENDING → APPROVED（联动记录走 _apply_record_resolution）
# ============================================================================


@pytest.mark.asyncio
async def test_approve_change_notice_changes_pending_to_approved():
    """approve_change_notice：PENDING → APPROVED + 写 audit。"""
    db, deliverable, _detail = _build_cn_session(sign_status="PENDING")

    result = await ChangeNoticeService.approve_change_notice(
        db,
        deliverable_id=deliverable.deliverable_id,
        actor=_actor(),
        record_table=FakeRecordTable,
        deliverable_model=_FakeDeliverable,
        detail_model=_FakeChangeNoticeDetail,
    )

    assert deliverable.sign_status == "APPROVED"
    assert result["sign_status"] == "APPROVED"
    assert db.commits == 1


@pytest.mark.asyncio
async def test_approve_change_notice_double_approval_rejected():
    """重复审批（已 APPROVED）→ 409。"""
    db, deliverable, _detail = _build_cn_session(sign_status="APPROVED")

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService.approve_change_notice(
            db,
            deliverable_id=deliverable.deliverable_id,
            actor=_actor(),
            record_table=FakeRecordTable,
            deliverable_model=_FakeDeliverable,
            detail_model=_FakeChangeNoticeDetail,
        )
    assert exc_info.value.status == 409


@pytest.mark.asyncio
async def test_approve_change_notice_not_found():
    """deliverable_id 不存在 → 404。"""
    db = _FakeSession()
    db.register_class_map(_FakeDeliverable, Deliverable)

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService.approve_change_notice(
            db,
            deliverable_id=uuid.uuid4(),
            actor=_actor(),
            record_table=FakeRecordTable,
            deliverable_model=_FakeDeliverable,
            detail_model=_FakeChangeNoticeDetail,
        )
    assert exc_info.value.status == 404


# ============================================================================
# audit 落库
# ============================================================================


@pytest.mark.asyncio
async def test_create_change_notice_writes_audit():
    """create_change_notice 写 audit：CHANGE_NOTICE_CREATED。"""
    db, rec = _build_record_signing_session(sign_status="CHANGED")
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
        await ChangeNoticeService.create_change_notice(
            db,
            project_id=uuid.uuid4(),
            record_id=rec.record_id,
            change_type=ChangeType.PROCESS_CHANGE,
            reason="工艺调整",
            triggered_by=TriggeredBy.UPSTREAM_CHANGE,
            actor=_actor(),
            record_table=FakeRecordTable,
        )
    finally:
        audit_mod.AuditService.write = orig_write  # type: ignore[assignment]

    cn_audits = [w for w in audit_writes if "CHANGE_NOTICE" in w["action"].name]
    assert len(cn_audits) >= 1
    aw = cn_audits[0]
    assert aw["resource_type"] == "DELIVERABLE"
    assert aw["detail"]["change_type"] == "PROCESS_CHANGE"
    assert aw["detail"]["source_record_id"] == str(rec.record_id)


@pytest.mark.asyncio
async def test_approve_change_notice_writes_audit():
    """approve_change_notice 写 audit：CHANGE_NOTICE_APPROVED。"""
    db, deliverable, _detail = _build_cn_session(sign_status="PENDING")

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
        await ChangeNoticeService.approve_change_notice(
            db,
            deliverable_id=deliverable.deliverable_id,
            actor=_actor(),
            record_table=FakeRecordTable,
            deliverable_model=_FakeDeliverable,
            detail_model=_FakeChangeNoticeDetail,
        )
    finally:
        audit_mod.AuditService.write = orig_write  # type: ignore[assignment]

    cn_audits = [w for w in audit_writes if "CHANGE_NOTICE" in w["action"].name]
    assert len(cn_audits) == 1
    aw = cn_audits[0]
    assert aw["action"].name == "CHANGE_NOTICE_APPROVED"
    assert aw["detail"]["from"] == "PENDING"
    assert aw["detail"]["to"] == "APPROVED"
