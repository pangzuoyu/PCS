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
from sqlalchemy import select

from app.models.calc import ReliefResult
from app.models.deliverable import ChangeNoticeDetail, Deliverable
from app.models.enums import (
    DeliverableSignStatus,
    RecordSignStatus9,
    ReliefScenario,
)
from app.models.system import AuditLog
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


async def _make_changed_record(
    db, *, project_id: uuid.UUID, sign_status: str = "CHANGED"
) -> ReliefResult:
    """一条业务记录（真库行）。

    用 `ReliefResult`（`RecordMixin` 族）当记录：它是本仓少数几个
    必填列很少的记录表 —— 只差 `project_id` / `workspace_id` /
    `source_equipment_id` / `relief_scenario` 四个。

    ⚠️ 单测跑的是内存 SQLite，**外键不强制** ⇒ 不必先建
    `projects` / `workspaces` 行。
    """
    rec = ReliefResult(
        project_id=project_id,
        workspace_id=uuid.uuid4(),
        source_equipment_id=uuid.uuid4(),
        relief_scenario=ReliefScenario.FIRE,
        sign_status=RecordSignStatus9(sign_status),
    )
    db.add(rec)
    await db.flush()
    return rec


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
        """ORM 主键查询占位：先查 ORM 真类，失败再回退到 fake 类反向映射。"""
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
                """scalar_one_or_none 占位：返回构造时预设的 value（或 None）。"""
                return self._value

            def all(self) -> list:
                """收件人解析（`notification_recipients`）走这条路径。

                返回空 = 「这个 fake session 里没有用户」，对应「无人可通知」
                —— 正是本文件想覆盖的分支。真 DB 上的行为由
                `test_change_notice_notification.py` 覆盖。
                """
                return []

            def scalar_one(self) -> Any:
                return 0

        for (_m_cls, _), obj in self.store.items():
            if isinstance(obj, _FakeChangeNoticeDetail):
                return _Result(obj)
        return _Result(None)

    def add(self, obj: Any) -> None:
        """记录 add 调用 + 自动补 deliverable_id/detail_id PK + 同步 ORM 真类索引。"""
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
        """commit 计数自增（service 断言事务提交次数）。"""
        self.commits += 1

    async def flush(self) -> None:
        """flush 占位（无实际操作）。"""
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
@pytest.mark.parametrize("change_type", list(ChangeType))
async def test_create_change_notice_creates_both_rows(db, project_id, change_type):
    """建单 ⇒ **真库**里两行齐活（deliverables + change_notice_details）。

    ⚠️ 这批用例必须用**真 DB**（内存 SQLite）：要看见 DB 层的约束 ——
    `deliverables.matrix_id` NOT NULL（矩阵没绑 ⇒ 插不进去）、
    `uq_deliverables_scope`、`uq_deliverables_doc_no`。
    原来的假 DB（`_FakeSession`）只断言内存对象 ⇒ 结构性问题一律看不见
    （P9A-DLV-009 的「假 DB 把结构性问题藏起来」）。

    7 种 change_type 逐一覆盖：它们是 API 边界上的契约，全部必须能发起。
    """
    rec = await _make_changed_record(db, project_id=project_id)

    result = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec.relief_id,
        change_type=change_type,
        reason="管径修正",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=ReliefResult,
    )

    assert result["deliverable_id"]
    assert result["doc_no"].startswith("CN-")
    assert result["detail"]["change_type"] == change_type.value

    row = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == result["deliverable_id"]
            )
        )
    ).scalar_one()
    assert row.deliverable_type == "CHANGE_NOTICE"
    # ⚠️ 矩阵必须绑上 —— 否则变更单建出来了也**签不了**
    assert row.matrix_id is not None
    assert row.sign_status == DeliverableSignStatus.PENDING

    detail = (
        await db.execute(
            select(ChangeNoticeDetail).where(
                ChangeNoticeDetail.deliverable_id == result["deliverable_id"]
            )
        )
    ).scalar_one()
    assert detail.change_type == change_type.value
    assert detail.reason == "管径修正"
    assert detail.source_record_type == "ReliefResult"


@pytest.mark.asyncio
async def test_create_change_notice_writes_audit(db, project_id):
    """建单 ⇒ 写一条 CHANGE_NOTICE_CREATED 审计（原来这条断言是「不写」）。"""
    rec = await _make_changed_record(db, project_id=project_id)

    await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.PROCESS_CHANGE,
        reason="工艺调整",
        triggered_by=TriggeredBy.UPSTREAM_CHANGE,
        actor=_actor(),
        record_table=ReliefResult,
    )

    audits = (
        await db.execute(
            select(AuditLog).where(AuditLog.action == "CHANGE_NOTICE_CREATED")
        )
    ).scalars().all()
    assert len(audits) == 1
    assert audits[0].detail_json["change_type"] == ChangeType.PROCESS_CHANGE.value


@pytest.mark.asyncio
async def test_create_change_notice_second_for_other_record_ok(db, project_id):
    """⚠️ 同项目的**第二张**变更单要能建出来（RF-8）。

    `uq_deliverables_scope` = (project_id, deliverable_type, scope_type,
    scope_value) ⇒ 用 PROJECT_ALL/ALL 的话第二张直接撞唯一约束。
    """
    rec_a = await _make_changed_record(db, project_id=project_id)
    rec_b = await _make_changed_record(db, project_id=project_id)

    a = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec_a.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="a",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=ReliefResult,
    )
    b = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec_b.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="b",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=ReliefResult,
    )

    assert a["deliverable_id"] != b["deliverable_id"]
    assert a["doc_no"] != b["doc_no"]


@pytest.mark.asyncio
async def test_create_change_notice_same_record_twice_rejected(db, project_id):
    """⚠️ 同一条记录的**第二张**变更单 ⇒ 409（明说，不是约束报错）。

    `doc_no` 由记录派生 ⇒ 同记录不能再建；这条业务约束是 doc_no 唯一约束的
    副产品 ⇒ 已登记待 SPEC 确认。
    """
    rec = await _make_changed_record(db, project_id=project_id)

    await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="a",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=ReliefResult,
    )

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService.create_change_notice(
            db,
            project_id=project_id,
            record_id=rec.relief_id,
            change_type=ChangeType.DATA_CORRECTION,
            reason="b",
            triggered_by=TriggeredBy.MANUAL,
            actor=_actor(),
            record_table=ReliefResult,
        )
    assert exc_info.value.status == 409
    assert exc_info.value.code == "CHANGE_NOTICE_ALREADY_EXISTS"


@pytest.mark.asyncio
async def test_create_change_notice_rejects_non_changed_record(db, project_id):
    """记录不是 CHANGED ⇒ 422（既有契约不变，只是现在**真库**上也成立）。"""
    rec = await _make_changed_record(db, project_id=project_id, sign_status="CHECKED")

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService.create_change_notice(
            db,
            project_id=project_id,
            record_id=rec.relief_id,
            change_type=ChangeType.DATA_CORRECTION,
            reason="x",
            triggered_by=TriggeredBy.MANUAL,
            actor=_actor(),
            record_table=ReliefResult,
        )
    assert exc_info.value.status == 422
    assert exc_info.value.code == "CHANGE_NOTICE_BAD_STATE"


@pytest.mark.asyncio
async def test_create_change_notice_record_not_found(db, project_id):
    """记录不存在 ⇒ 404。"""
    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService.create_change_notice(
            db,
            project_id=project_id,
            record_id=uuid.uuid4(),
            change_type=ChangeType.DATA_CORRECTION,
            reason="x",
            triggered_by=TriggeredBy.MANUAL,
            actor=_actor(),
            record_table=ReliefResult,
        )
    assert exc_info.value.status == 404
    assert exc_info.value.code == "CHANGE_NOTICE_RECORD_NOT_FOUND"


# ---------------------------------------------------------------------------
# 记录状态校验 —— P9A 落地后 create_change_notice 仍要保留这两条行为，
# 现在它们经由 stub 不可达，故直接测底层校验器，让 P9A 继承这份覆盖。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_status", ("CHECKED", "DRAFT", "STALE",
                                         "CHANGE_PENDING", "OBSOLETE"))
async def test_record_state_validation_rejects_non_changed(bad_status):
    """仅 CHANGED 状态记录可发起变更单；CHECKED/DRAFT/STALE 等 422。"""
    db, rec = _build_record_signing_session(sign_status=bad_status)

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService._check_record_charged(
            db, rec.record_id, FakeRecordTable
        )
    assert exc_info.value.status == 422
    assert exc_info.value.code == "CHANGE_NOTICE_BAD_STATE"


@pytest.mark.asyncio
async def test_record_state_validation_record_not_found():
    """record_id 不存在 → 404。"""
    db = _FakeSession()

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService._check_record_charged(
            db, uuid.uuid4(), FakeRecordTable
        )
    assert exc_info.value.status == 404


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


# ============================================================================
# 通知触发（P9A C1b / 用户 2026-10-20 裁决的最小接线集合）
# ============================================================================


@pytest.mark.asyncio
async def test_approve_change_notice_notifies_project_designers(db, make_user):
    """审批通过 ⇒ 项目内的 DESIGNER 收到 CHANGE_NOTICE_APPROVED。

    收件人为什么是 DESIGNER 而不是「变更单的申请人」：`ChangeNoticeDetail`
    上**没有申请人字段**（`triggered_by` 是 `MANUAL`/`UPSTREAM_CHANGE` 这样的
    来源枚举，不是用户）。唯一有既定语义的受众是项目的设计人 ——
    记录状态因这次审批而变了，而他们要重新算。

    `_FakeSession.execute` 对任何语句都返回同一个 detail 对象，本测试补
    `.all()` 返回空，让收件人解析走「没人」分支；真实 DB 行为由
    `tests/api/v1/test_change_notice_notification.py` 覆盖。
    """
    from app.services.broadcaster import Broadcaster, set_broadcaster

    db, deliverable, _detail = _build_cn_session(sign_status="PENDING")
    dead = Broadcaster("redis://127.0.0.1:6399/0")
    set_broadcaster(dead)
    try:
        result = await ChangeNoticeService.approve_change_notice(
            db,
            deliverable_id=deliverable.deliverable_id,
            actor=_actor(),
            record_table=FakeRecordTable,
            deliverable_model=_FakeDeliverable,
            detail_model=_FakeChangeNoticeDetail,
        )
    finally:
        set_broadcaster(None)

    assert result["sign_status"] == "APPROVED"
    # 无人可通知时不额外 commit —— 既有测试断言 commits == 1
    assert db.commits == 1


@pytest.mark.asyncio
async def test_approve_change_notice_still_works_without_recipients(db):
    """收件人解析不出人时**不抛**。「没有 DESIGNER」是一种状态，不是一次失败。"""
    db, deliverable, _detail = _build_cn_session(sign_status="PENDING")

    result = await ChangeNoticeService.approve_change_notice(
        db,
        deliverable_id=deliverable.deliverable_id,
        actor=_actor(),
        record_table=FakeRecordTable,
        deliverable_model=_FakeDeliverable,
        detail_model=_FakeChangeNoticeDetail,
    )

    assert result["sign_status"] == "APPROVED"
    assert db.commits == 1
