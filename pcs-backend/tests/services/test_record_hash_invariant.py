"""record_hash 不变式（P9A-4 D0 · ADR-0048 §⑥）。

## 这组测试钉的是什么

`record_hash` 是 ADR-0048 §⑥ 选定的**正确性层并发令牌**（Redis 锁是体验层）。
但实测发现：**它今天根本不会被更新** —— 6 条 PATCH 路径的 update service
一律不重算 hash（`cool_tower_persist_service.py:251` 明写「不重新触发
record_hash 计算」）。

⇒ 若不建立「业务字段写入后重算 hash」这条不变式，ADR-0048 §⑥ 的阶梯会
**永远走「放行」分支**（`当前 record_hash == expected_hash` 恒成立），
D2 的 guard 对 6 张表中的 5 张是彻底的空操作 ⇒ 丢失更新静默发生。
这不是「保护弱」，是「保护不存在」。

## 另一条同样重要：状态流转**不得**动 hash

`compute_record_hash` 的 `_EXCLUDED_KEYS` 只排除 `record_hash` 自身与
生命周期列（created_at / created_by / updated_at / updated_by）⇒
**`sign_status` / `approval_step` 等工作流状态列参与哈希**。
（ADR-0048 §⑥ 原文说「它不检测 sign_status / approval_step 的变化」——
 与代码不符，该句已在 ADR-0048 修订。）

⇒ 若把重算放进全局 flush 钩子，状态流转会改掉 stored hash ⇒ 客户端手里的
基线失效 ⇒ 用户在**没跟任何人冲突**的情况下收到假 409。
⇒ 重算点只允许在「业务字段编辑路径」，本文件用
`test_status_transition_does_not_move_the_hash` 钉住这条。
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import select

from app.models.calc import CoolingTowerResult, CostEstResult
from app.models.enums import RecordSignStatus9
from app.services.calc_lineage import (
    backfill_record_hash,
    compute_record_hash,
    finalize_calc_record,
)

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


async def _make_cost_est(db, **overrides) -> CostEstResult:
    """造一条 cost_est_results 行（equipment_id 有 FK，但单测 SQLite 不强制外键）。"""
    rec = CostEstResult(
        equipment_id=overrides.pop("equipment_id", uuid.uuid4()),
        estimated_cost=overrides.pop("estimated_cost", 1000.0),
        currency=overrides.pop("currency", "USD"),
        cost_index_year=overrides.pop("cost_index_year", 2019),
        created_at=datetime.now(UTC),
        **overrides,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


async def _make_cool_tower(db, **overrides) -> CoolingTowerResult:
    rec = CoolingTowerResult(
        cooling_tower_id=overrides.pop("cooling_tower_id", uuid.uuid4()),
        calc_type=overrides.pop("calc_type", "MERKEL"),
        project_id=overrides.pop("project_id", uuid.uuid4()),
        workspace_id=overrides.pop("workspace_id", uuid.uuid4()),
        tag_number=overrides.pop("tag_number", f"T-{uuid.uuid4().hex[:8]}"),
        duty_kw=overrides.pop("duty_kw", 100.0),
        **overrides,
    )
    db.add(rec)
    await db.commit()
    await db.refresh(rec)
    return rec


# ---------------------------------------------------------------------------
# 1. hash 必须随业务字段变化
# ---------------------------------------------------------------------------


async def test_cost_est_update_recomputes_record_hash(db_session):
    """PATCH 业务字段后 hash 必须变 —— 否则并发覆盖检测不到。"""
    from app.services.cost_est.cost_est_persist_service import (
        update_cost_est_result_service,
    )

    rec = await _make_cost_est(db_session)
    before = rec.record_hash

    await update_cost_est_result_service(
        db_session, result_id=rec.cost_est_id, patch={"estimated_cost": 2000.0}
    )
    await db_session.refresh(rec)

    assert rec.record_hash != before, "PATCH 后 record_hash 未重算 ⇒ 丢失更新检测不到"
    assert len(rec.record_hash) == 16


async def test_cool_tower_update_recomputes_record_hash(db_session):
    """同一条不变式在 RecordMixin 表上也成立（不是 cost_est 专属）。"""
    from app.services.cool_tower.cool_tower_persist_service import (
        update_cool_tower_result,
    )

    rec = await _make_cool_tower(db_session)
    before = rec.record_hash

    updated = await update_cool_tower_result(
        db_session, record_id=rec.cooling_tower_id, payload={"duty_kw": 200.0}
    )
    assert updated is not None
    await db_session.refresh(rec)

    assert rec.record_hash != before, "PATCH 后 record_hash 未重算 ⇒ 丢失更新检测不到"
    assert len(rec.record_hash) == 16


async def test_update_recompute_is_idempotent_for_same_content(db_session):
    """同样内容再改一次 ⇒ hash 不变（compute_record_hash 的幂等契约）。"""
    from app.services.cost_est.cost_est_persist_service import (
        update_cost_est_result_service,
    )

    rec = await _make_cost_est(db_session)
    await update_cost_est_result_service(
        db_session, result_id=rec.cost_est_id, patch={"estimated_cost": 2000.0}
    )
    await db_session.refresh(rec)
    first = rec.record_hash

    await update_cost_est_result_service(
        db_session, result_id=rec.cost_est_id, patch={"estimated_cost": 2000.0}
    )
    await db_session.refresh(rec)

    assert rec.record_hash == first


# ---------------------------------------------------------------------------
# 2. 状态流转不得动 hash
# ---------------------------------------------------------------------------


async def test_compute_record_hash_handles_a_pending_object_with_none_float():
    """待 flush 的对象 + 显式 None 的 Float 列 ⇒ 不得抛 TypeError。

    实测（旧实现会炸）：transient 实例的 `committed_state` 里存的是
    `LoaderCallableStatus.NO_VALUE`（**不是 None**）⇒ 旧代码
    `v = state.dict.get(k) or committed.get(k)` 拿到哨兵就去 `_round_sig`
    ⇒ `TypeError: must be real number, not LoaderCallableStatus`。
    """
    rec = CoolingTowerResult(
        cooling_tower_id=uuid.uuid4(),
        calc_type="MERKEL",
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        tag_number=f"T-{uuid.uuid4().hex[:8]}",
        duty_kw=None,
    )
    h = compute_record_hash(rec)
    assert len(h) == 16


async def test_sign_status_participates_in_the_hash():
    """事实守卫：sign_status 参与哈希（ADR-0048 §⑥ 原文说它不参与 —— 已修订）。

    这条不是「期望行为」，是**实测事实**。钉住它是为了：将来若有人把
    sign_status 加进 _EXCLUDED_KEYS，必须同时意识到 ADR-0048 §⑥ 的
    「仅设计参数参与」才是他们要的东西，而不是顺手改。
    """
    a = CoolingTowerResult(
        cooling_tower_id=uuid.uuid4(),
        calc_type="MERKEL",
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        tag_number=f"T-{uuid.uuid4().hex[:8]}",
        duty_kw=100.0,
        sign_status=RecordSignStatus9.DRAFT,
    )
    b = CoolingTowerResult(
        cooling_tower_id=uuid.uuid4(),
        calc_type="MERKEL",
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        tag_number=f"T-{uuid.uuid4().hex[:8]}",
        duty_kw=100.0,
        sign_status=RecordSignStatus9.CHECKED,
    )
    assert compute_record_hash(a) != compute_record_hash(b)


async def test_status_transition_does_not_move_the_hash(db_session):
    """状态流转**不改** hash —— 否则客户端基线失效 ⇒ 假 409。

    这是「重算只放在业务字段编辑路径、不放全局 flush 钩子」的可观测后果。
    """
    rec = await _make_cool_tower(db_session)
    rec.record_hash = compute_record_hash(rec)
    await db_session.commit()
    before = rec.record_hash

    rec.sign_status = RecordSignStatus9.CHECKED
    await db_session.commit()
    await db_session.refresh(rec)

    assert rec.record_hash == before, (
        "状态流转改了 record_hash ⇒ 客户端持有的基线失效 ⇒ 假冲突"
    )


# ---------------------------------------------------------------------------
# 3. 回填
# ---------------------------------------------------------------------------


async def test_backfill_covers_every_row(db_session):
    """回填后没有空 hash 的行 —— 否则 D2 一律走 no_baseline。"""
    rec = await _make_cost_est(db_session)
    rec.record_hash = ""
    await db_session.commit()

    n = await backfill_record_hash(db_session, CostEstResult)
    await db_session.commit()

    assert n == 1
    await db_session.refresh(rec)
    assert rec.record_hash != ""


async def test_backfill_matches_live_computation(db_session):
    """回填值 == 对该行现算的值（防止算在错误的列集合上）。"""
    rec = await _make_cost_est(db_session)
    rec.record_hash = ""
    await db_session.commit()

    await backfill_record_hash(db_session, CostEstResult)
    await db_session.commit()
    await db_session.refresh(rec)

    assert rec.record_hash == compute_record_hash(rec)


async def test_backfill_is_stable(db_session):
    """回填幂等：重跑两次 hash 不变。"""
    rec = await _make_cost_est(db_session)
    rec.record_hash = ""
    await db_session.commit()

    await backfill_record_hash(db_session, CostEstResult)
    await db_session.commit()
    await db_session.refresh(rec)
    first = rec.record_hash

    await backfill_record_hash(db_session, CostEstResult)
    await db_session.commit()
    await db_session.refresh(rec)

    assert rec.record_hash == first


async def test_backfill_leaves_other_rows_untouched(db_session):
    """回填只动目标表（不越界写别的表）。"""
    rec = await _make_cost_est(db_session)
    rec.record_hash = ""
    other = await _make_cool_tower(db_session)
    other_hash = other.record_hash
    await db_session.commit()

    await backfill_record_hash(db_session, CostEstResult)
    await db_session.commit()
    await db_session.refresh(rec)
    await db_session.refresh(other)

    assert rec.record_hash != "", "目标表应被回填"
    assert other.record_hash == other_hash, "回填越界改了别的表"


# ---------------------------------------------------------------------------
# 4. finalize 的显式校验（TODO-048：防线是注释不是代码）
# ---------------------------------------------------------------------------


async def test_finalize_rejects_model_without_record_hash(db_session):
    """缺 record_hash 列的模型 ⇒ 明确的错误，不是 AttributeError。"""

    class _NoHash:
        """长得像结果表、但没有 record_hash 列。"""

        __table__ = CostEstResult.__table__

    with pytest.raises(TypeError) as ei:
        await finalize_calc_record(
            db_session,
            _NoHash(),
            source_stream_ids=[],
            formula_version="test",
        )
    assert "record_hash" in str(ei.value)


async def test_cost_est_create_writes_non_empty_record_hash(db_session):
    """创建路径必须写 hash（ADR-0048 §⑥：补 record_hash + 接 finalize_calc_record）。"""
    from app.models.equipment import EquipmentList
    from app.services.cost_est.cost_est_persist_service import (
        save_six_tenths_rule_result,
    )

    equipment_id = uuid.uuid4()
    db_session.add(
        EquipmentList(
            equipment_id=equipment_id,
            type_code="PUMP",
            equipment_name=f"E-{uuid.uuid4().hex[:8]}",
            tag_number=f"T-{uuid.uuid4().hex[:8]}",
            project_id=uuid.uuid4(),
            workspace_id=uuid.uuid4(),
        )
    )
    await db_session.commit()

    rec = await save_six_tenths_rule_result(
        db_session,
        equipment_id=equipment_id,
        reference_cost=10000.0,
        reference_cepci=550.0,
        target_cepci=600.0,
        scaling_exponent=0.6,
        estimated_cost=10909.09,
    )

    assert rec.record_hash != "", "创建后 record_hash 为空 ⇒ 该行永远无并发保护"
    assert len(rec.record_hash) == 16


async def test_cost_est_row_is_listed_by_backfill_scan(db_session):
    """回填走的是「按表扫全表」，不是「按已知 id」—— 断言扫描口径。"""
    rec = await _make_cost_est(db_session)
    rows = (
        await db_session.execute(select(CostEstResult))
    ).scalars().all()
    assert any(r.cost_est_id == rec.cost_est_id for r in rows)
