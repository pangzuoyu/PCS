"""编辑冲突 guard 的**阶梯**测试 —— P9A-4 D2（ADR-0048 §⑥）。

## 本文件是阶梯的**唯一**测试处

阶梯（check_conflict）只在这里测一遍；调用点（6 个 PATCH 端点）只验
「guard 被正确调用 + 409 契约」，见 `tests/api/v1/test_edit_conflict.py`。

## 阶梯的形状

```
当前 record_hash != ""  → 比 hash：不等 ⇒ 409 (basis=record_hash)
当前 record_hash == ""  → 比 updated_at：不等 ⇒ 409 (basis=updated_at)
                          → 没有 updated_at / 客户端没给基线 ⇒ 409 (basis=no_baseline)
```

⚠️ **「客户端没给基线」⇒ 409**：服务端无法判定并发，放行等于「保护可以不存在」
（这正是 D0 修掉的假绿形状）。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import func, select

from app.models.calc import CoolingTowerResult, CostEstResult
from app.models.system import AuditLog
from app.services.edit_guard import (
    TABLE_CAPABILITIES,
    ConflictCheckResult,
    UnregisteredTableError,
    capability_of,
    check_conflict,
    record_edit_audit,
    scan_missing_record_hash,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _make_cool_tower(
    db,
    *,
    record_hash: str = "a1b2c3d4e5f60718",
    updated_at: datetime | None = None,
) -> CoolingTowerResult:
    rec = CoolingTowerResult(
        cooling_tower_id=uuid.uuid4(),
        calc_type="MERKEL",
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        tag_number=f"CT-{uuid.uuid4().hex[:8]}",
        duty_kw=100.0,
        record_hash=record_hash,
    )
    if updated_at is not None:
        rec.updated_at = updated_at
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


async def _make_cost_est(db, *, record_hash: str = "a1b2c3d4e5f60718") -> CostEstResult:
    rec = CostEstResult(
        equipment_id=uuid.uuid4(),
        # P9A-5 Task B：project_id NOT NULL（本测试不关心项目语义）
        project_id=uuid.uuid4(),
        estimated_cost=1000.0,
        currency="USD",
        cost_index_year=2019,
        created_at=datetime.now(UTC),
        record_hash=record_hash,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


# ---------------------------------------------------------------------------
# 1. 正常路径
# ---------------------------------------------------------------------------


async def test_matching_hash_passes(db_session):
    """基线 hash 与库中一致 ⇒ 放行。"""
    rec = await _make_cool_tower(db_session)
    r = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash=rec.record_hash,
        expected_updated_at=None,
    )
    assert isinstance(r, ConflictCheckResult)
    assert r.conflict is None
    assert r.overwrote_stale_baseline is False


async def test_stale_hash_conflicts_with_basis_record_hash(db_session):
    """基线 hash 过期 ⇒ 409，basis=record_hash（前端据此提示「刷新」）。"""
    rec = await _make_cool_tower(db_session, record_hash="1111111111111111")
    r = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash="2222222222222222",
        expected_updated_at=None,
    )
    assert r.conflict is not None
    assert r.conflict.basis == "record_hash"
    assert r.conflict.current_hash == "1111111111111111"
    assert r.conflict.your_expected_hash == "2222222222222222"


async def test_missing_baseline_is_no_baseline_not_a_pass(db_session):
    """**客户端没给基线 ⇒ 409**（不是放行）。"""
    rec = await _make_cool_tower(db_session)
    r = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash=None,
        expected_updated_at=None,
    )
    assert r.conflict is not None
    assert r.conflict.basis == "no_baseline"


# ---------------------------------------------------------------------------
# 2. 第二档：hash 为空 ⇒ 退到 updated_at
# ---------------------------------------------------------------------------


async def test_empty_hash_falls_to_updated_at(db_session):
    """hash 为空（从未计算过）⇒ 比 updated_at（第二档）。"""
    ts = datetime.now(UTC) - timedelta(minutes=5)
    rec = await _make_cool_tower(db_session, record_hash="", updated_at=ts)
    r = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash=None,
        expected_updated_at=ts,
    )
    assert r.conflict is None, "updated_at 一致 ⇒ 放行"
    assert r.overwrote_stale_baseline is True, "未经 hash 级比对 ⇒ 记「覆盖陈旧基线」"


async def test_empty_hash_and_stale_updated_at_conflicts(db_session):
    ts = datetime.now(UTC) - timedelta(minutes=5)
    rec = await _make_cool_tower(db_session, record_hash="", updated_at=ts)
    r = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash=None,
        expected_updated_at=ts - timedelta(minutes=1),
    )
    assert r.conflict is not None
    assert r.conflict.basis == "updated_at"


async def test_null_updated_at_is_no_baseline_not_equal(db_session):
    """⚠️ **NULL 当「相等」放行 ⇒ 从未计算过的记录完全无保护**。

    updated_at 为 NULL（刚 INSERT、还没被 UPDATE 过）⇒ 不能当成「一致」，
    必须 409。
    """
    rec = await _make_cool_tower(db_session, record_hash="")
    assert rec.updated_at is None
    r = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash=None,
        expected_updated_at=None,
    )
    assert r.conflict is not None
    assert r.conflict.basis == "no_baseline"


async def test_table_without_updated_at_falls_to_no_baseline(db_session):
    """cost_est_results 无 updated_at ⇒ 只剩 hash 一档；hash 为空 ⇒ no_baseline。"""
    rec = await _make_cost_est(db_session, record_hash="")
    r = await check_conflict(
        db_session,
        record_type="CostEstResult",
        record_id=rec.cost_est_id,
        expected_hash="1111111111111111",
        expected_updated_at=None,
    )
    assert r.conflict is not None
    assert r.conflict.basis == "no_baseline"


# ---------------------------------------------------------------------------
# 3. 契约约束
# ---------------------------------------------------------------------------


async def test_conflict_basis_has_three_values(db_session):
    """basis 只有三个取值（前端按它分流）。"""
    seen = set()
    rec = await _make_cool_tower(db_session, record_hash="1111111111111111")
    r1 = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash="2222222222222222",
        expected_updated_at=None,
    )
    seen.add(r1.conflict.basis)
    r2 = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash=None,
        expected_updated_at=None,
    )
    seen.add(r2.conflict.basis)
    ts = datetime.now(UTC) - timedelta(minutes=5)
    rec2 = await _make_cool_tower(db_session, record_hash="", updated_at=ts)
    r3 = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec2.cooling_tower_id,
        expected_hash=None,
        expected_updated_at=ts - timedelta(minutes=1),
    )
    seen.add(r3.conflict.basis)
    assert seen == {"record_hash", "updated_at", "no_baseline"}


async def test_check_conflict_is_pure(db_session):
    """约束 1：**纯检查** —— 调用前后 audit_logs 行数不变（不写审计）。"""
    rec = await _make_cool_tower(db_session)
    before = (
        await db_session.execute(select(func.count()).select_from(AuditLog))
    ).scalar_one()
    await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash="2222222222222222",
        expected_updated_at=None,
    )
    after = (
        await db_session.execute(select(func.count()).select_from(AuditLog))
    ).scalar_one()
    assert before == after, "check_conflict 写了审计（约束 1：纯检查）"


async def test_unregistered_table_raises(db_session):
    """约束 3：漏登记抛 `UnregisteredTableError`，**不得**静默走 no_baseline。"""
    with pytest.raises(UnregisteredTableError):
        await check_conflict(
            db_session,
            record_type="sim_tower_results",  # 无编辑端点的表
            record_id=uuid.uuid4(),
            expected_hash="1111111111111111",
            expected_updated_at=None,
        )
    with pytest.raises(UnregisteredTableError):
        capability_of("sim_tower_results")


async def test_capability_map_covers_exactly_the_editable_tables():
    """能力表登记的表 = 有编辑端点的表（不多不少）。"""
    assert set(TABLE_CAPABILITIES) == {
        "cooling_tower_result",
        "FiltrationResult",
        "flare_system_result",
        "OpenChannelResult",
        "psychro_result",
        "CostEstResult",
    }
    for cap in TABLE_CAPABILITIES.values():
        assert cap.has_record_hash is True, "D0 之后 6 张表都有 record_hash"
        assert hasattr(cap.model, cap.pk_attr)


# ---------------------------------------------------------------------------
# 4. 编辑审计
# ---------------------------------------------------------------------------


async def test_record_edit_audit_writes_changed_fields(db_session):
    """审计写 changed_fields（**字段名列表**，不是值）。"""
    rec = await _make_cool_tower(db_session)
    await record_edit_audit(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        user_id=uuid.uuid4(),
        changed_fields=["duty_kw", "fan_power_kw"],
    )
    await db_session.commit()
    row = (
        await db_session.execute(
            select(AuditLog).where(AuditLog.action == "RECORD_EDITED")
        )
    ).scalar_one()
    assert row.resource_type == "cooling_tower_result"
    assert row.detail_json["changed_fields"] == ["duty_kw", "fan_power_kw"]
    assert row.detail_json["overwrote_stale_baseline"] is False


async def test_overwrote_stale_baseline_writes_an_extra_audit(db_session):
    """未经 hash 级比对的保存 ⇒ 另写一条 RECORD_EDIT_OVERWROTE_STALE_BASELINE。"""
    rec = await _make_cool_tower(db_session)
    await record_edit_audit(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        user_id=uuid.uuid4(),
        changed_fields=["duty_kw"],
        overwrote_stale_baseline=True,
    )
    await db_session.commit()
    actions = (
        await db_session.execute(select(AuditLog.action))
    ).scalars().all()
    assert "RECORD_EDITED" in actions
    assert "RECORD_EDIT_OVERWROTE_STALE_BASELINE" in actions


async def test_changed_by_comes_from_the_edit_audit(db_session):
    """409 里的 changed_by / changed_at 取自**编辑审计**（不是泛匹配）。"""
    rec = await _make_cool_tower(db_session, record_hash="1111111111111111")
    editor = uuid.uuid4()
    await record_edit_audit(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        user_id=editor,
        changed_fields=["duty_kw"],
    )
    await db_session.commit()
    # 另一条无关审计不得被泛匹配
    db_session.add(
        AuditLog(
            user_id=uuid.uuid4(),
            action="RECORD_TRANSITION",
            resource_type="cooling_tower_result",
            resource_id=str(rec.cooling_tower_id),
        )
    )
    await db_session.commit()

    r = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash="2222222222222222",
        expected_updated_at=None,
    )
    assert r.conflict is not None
    assert r.conflict.changed_by == str(editor)
    assert r.conflict.changed_at is not None


async def test_changed_by_is_null_when_no_edit_audit(db_session):
    """没有编辑审计 ⇒ changed_by / changed_at 为 null（不拿 updated_at 冒充）。"""
    rec = await _make_cool_tower(db_session, record_hash="1111111111111111")
    r = await check_conflict(
        db_session,
        record_type="cooling_tower_result",
        record_id=rec.cooling_tower_id,
        expected_hash="2222222222222222",
        expected_updated_at=None,
    )
    assert r.conflict is not None
    assert r.conflict.changed_by is None
    assert r.conflict.changed_at is None


# ---------------------------------------------------------------------------
# 5. 自检扫描
# ---------------------------------------------------------------------------


async def test_scan_reports_rows_with_empty_hash(db_session):
    """自检：扫出 record_hash 为空的行（D0 的「提交了但没 finalize」信号）。"""
    await _make_cool_tower(db_session, record_hash="")
    await _make_cool_tower(db_session, record_hash="1111111111111111")
    out = await scan_missing_record_hash(db_session)
    assert out["cooling_tower_result"] == 1
    assert out["CostEstResult"] == 0
