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
4. （原 4/5：approve_change_notice 的自动联动与重复审批）—— **该方法已删除**
   （TODO-081 选项①：它是**绕过矩阵**的第二条关闭路径，且**连记录都不关**
   ⇒ 用了它记录就永远停在 CHANGED）⇒ 真覆盖改在
   `tests/services/test_change_notice_close_real_db.py`（真库）与
   `tests/api/v1/test_change_notice_api.py`（端到端）

⚠️ 本文件**已无假 Session**（原先的 `_FakeSession` + 假模型全删 —— TODO-080
第 2 条：假 Session 结构上看不见 DB 层的约束/唯一性/外键 ⇒ 那批用例是
**零覆盖**）。
6. create_change_notice 7 种 change_type 全枚举可写入
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

import pytest
from sqlalchemy import select

from app.models.calc import ReliefResult
from app.models.deliverable import (
    ChangeNoticeDetail,
    Deliverable,
    DeliverableRecordBinding,
    DeliverableVersion,
    RecordChangeSnapshot,
    SignatureMatrix,
)
from app.models.enums import (
    DeliverableSignStatus,
    RecordSignStatus9,
    ReliefScenario,
)
from app.models.system import AuditLog
from app.services import change_notice_service
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
# 建单 = 交付物 + **版本行** + **记录绑定**（P9A-DLV-011 · T1）
#
# ⚠️ 为什么必须有版本行：`sign_step` 要 `version_id` ⇒ 没有版本，变更单
# **进不了签署流程** ⇒ ADR-0008「一套版本历史」对变更单不成立。
# ⚠️ 为什么必须有 binding：ADR-0008 明写「deliverable_record_bindings 增加
# old_record_hash_before_change 承载新旧哈希对比（替代原
# change_notice_record_bindings）」⇒ 记录↔变更单的**权威**关联在 binding，
# 不是 scope_value 字符串。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_change_notice_creates_signable_version(db, project_id):
    """建单 ⇒ 有版本行（ISSUED_FOR_CHANGE）+ 交付物进 PENDING。"""
    rec = await _make_changed_record(db, project_id=project_id)

    result = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="管径修正",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=ReliefResult,
    )

    versions = (
        await db.execute(
            select(DeliverableVersion).where(
                DeliverableVersion.deliverable_id == result["deliverable_id"]
            )
        )
    ).scalars().all()
    assert len(versions) == 1
    assert versions[0].version_purpose == "ISSUED_FOR_CHANGE"
    assert versions[0].rev == "1"

    row = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == result["deliverable_id"]
            )
        )
    ).scalar_one()
    # 交付物进了签署中 ⇒ 矩阵的 3 级校审对它生效
    assert row.sign_status == DeliverableSignStatus.PENDING
    assert row.current_rev == "1"
    # 响应里要能拿到版本 id —— 前端签第一步时要用
    assert result["version_id"] == versions[0].version_id


@pytest.mark.asyncio
async def test_create_change_notice_binds_the_record(db, project_id):
    """建单 ⇒ `deliverable_record_bindings` 有一行（记录↔变更单的权威关联）。"""
    rec = await _make_changed_record(db, project_id=project_id)
    rec.record_hash = "hash-after-change"

    result = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="管径修正",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=ReliefResult,
    )

    bindings = (
        await db.execute(
            select(DeliverableRecordBinding).where(
                DeliverableRecordBinding.deliverable_version_id == result["version_id"]
            )
        )
    ).scalars().all()
    assert len(bindings) == 1
    binding = bindings[0]
    assert binding.record_type == "ReliefResult"
    assert binding.record_id == rec.relief_id
    assert binding.record_hash == "hash-after-change"
    # 没有 INITIATE_CHANGE 快照 ⇒ 没有「变更前哈希」
    assert binding.old_record_hash_before_change is None


@pytest.mark.asyncio
async def test_create_change_notice_carries_pre_change_hash(db, project_id):
    """⚠️ 有 BEFORE_CHANGE 快照 ⇒ binding 带上**变更前**的哈希（新旧对比）。

    ADR-0008：`deliverable_record_bindings` 的 `old_record_hash_before_change`
    承载新旧哈希对比 ⇒ 没有它就看不出「改了什么」。
    """
    rec = await _make_changed_record(db, project_id=project_id)
    rec.record_hash = "hash-before"
    db.add(
        RecordChangeSnapshot(
            snapshot_id=uuid.uuid4(),
            record_type="ReliefResult",
            record_id=rec.relief_id,
            record_hash="hash-before",
            data_snapshot_json={},
            snapshot_reason="BEFORE_CHANGE",
            snapshot_source="MANUAL_CHANGE",
            snapshot_status="ACTIVE",
        )
    )
    await db.flush()
    rec.record_hash = "hash-after"

    result = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="管径修正",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=ReliefResult,
    )

    binding = (
        await db.execute(
            select(DeliverableRecordBinding).where(
                DeliverableRecordBinding.deliverable_version_id == result["version_id"]
            )
        )
    ).scalar_one()
    assert binding.old_record_hash_before_change == "hash-before"
    assert binding.record_hash == "hash-after"


@pytest.mark.asyncio
async def test_create_change_notice_doc_no_uses_full_uuid(db, project_id):
    """⚠️ `doc_no` 用**完整 32 位 hex** —— 前 8 位（32 bit）在同项目 ~65k 张单
    时就会撞 `uq_deliverables_doc_no` ⇒ 撞了是未捕获的 IntegrityError（500）。"""
    rec = await _make_changed_record(db, project_id=project_id)

    result = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="x",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=ReliefResult,
    )
    # ⚠️ 编号取**变更单自己的** uuid（一条记录可以有多张单 ⇒ 记录派生的会撞）
    assert result["doc_no"] == f"CN-{result['deliverable_id'].hex.upper()}"


@pytest.mark.asyncio
async def test_scope_value_matches_record_binding(db, project_id):
    """⚠️ RF-8：`scope_value` 与 binding 的记录身份**必须一致**。

    两处都表达「这张变更单针对哪条记录」⇒ 两处可能漂 ⇒ 用测试钉住。
    """
    rec = await _make_changed_record(db, project_id=project_id)

    result = await ChangeNoticeService.create_change_notice(
        db,
        project_id=project_id,
        record_id=rec.relief_id,
        change_type=ChangeType.DATA_CORRECTION,
        reason="x",
        triggered_by=TriggeredBy.MANUAL,
        actor=_actor(),
        record_table=ReliefResult,
    )

    row = (
        await db.execute(
            select(Deliverable).where(
                Deliverable.deliverable_id == result["deliverable_id"]
            )
        )
    ).scalar_one()
    binding = (
        await db.execute(
            select(DeliverableRecordBinding).where(
                DeliverableRecordBinding.deliverable_version_id == result["version_id"]
            )
        )
    ).scalar_one()
    assert row.scope_type == "CUSTOM"
    # ⚠️ scope **以记录身份开头**（记录身份必须一致）**+ 逐单后缀**
    #    （一条记录可以有多张变更单 ⇒ scope 必须逐单唯一 ⇒ 后缀 = 本单 uuid 前 8 位）
    assert row.scope_value.startswith(
        f"CHANGE_NOTICE:{binding.record_type}:{binding.record_id}:"
    )



# ---------------------------------------------------------------------------
# 记录状态校验 —— P9A 落地后 create_change_notice 仍要保留这两条行为，
# 现在它们经由 stub 不可达，故直接测底层校验器，让 P9A 继承这份覆盖。
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_status", ("CHECKED", "DRAFT", "STALE",
                                         "CHANGE_PENDING", "OBSOLETE"))
async def test_record_state_validation_rejects_non_changed(db, project_id, bad_status):
    """仅 CHANGED 状态记录可发起变更单；CHECKED/DRAFT/STALE 等 422。

    ⚠️ **真库**（原先用假 Session ⇒ 结构性问题看不见 —— TODO-080 第 2 条）。
    """
    rec = await _make_changed_record(db, project_id=project_id, sign_status=bad_status)

    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService._check_record_charged(db, rec.relief_id, ReliefResult)
    assert exc_info.value.status == 422
    assert exc_info.value.code == "CHANGE_NOTICE_BAD_STATE"


@pytest.mark.asyncio
async def test_record_state_validation_record_not_found(db, project_id):
    """record_id 不存在 → 404（真库）。"""
    with pytest.raises(PcsError) as exc_info:
        await ChangeNoticeService._check_record_charged(
            db, uuid.uuid4(), ReliefResult
        )
    assert exc_info.value.status == 404


# ============================================================================
# 通知触发（P9A C1b / 用户 2026-10-20 裁决的最小接线集合）
# ============================================================================


@pytest.mark.asyncio
async def test_create_change_notice_rejects_matrix_without_steps(
    db, project_id, monkeypatch
):
    """⚠️ 矩阵**没有可用步骤** ⇒ 建单 422（否则变更单永远签不了）。

    变更单建出来了、观测行也写了 PENDING，但它**一步都签不了**
    （`sign_step` 越界 404 / 全非法 422）⇒ 变更单永远停在「进行中」，
    而甘特图上却会一路走到 COMPLETED —— 「看起来走完了，其实一步没签」。
    ⇒ 建单时就说清楚。
    """
    rec = await _make_changed_record(db, project_id=project_id)

    async def _empty_matrix(db, *, project_id):  # noqa: ANN001
        return SignatureMatrix(
            matrix_id=uuid.uuid4(),
            matrix_name="EMPTY",
            module="CHANGE_NOTICE",
            doc_type="CHANGE_NOTICE",
            version_purpose="ISSUED_FOR_CHANGE",
            steps_json=[],
            status="ACTIVE",
        )

    monkeypatch.setattr(
        change_notice_service.SignatureMatrixService,
        "ensure_change_notice_matrix",
        _empty_matrix,
    )

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
    assert exc_info.value.code == "SIGNATURE_MATRIX_INVALID"
