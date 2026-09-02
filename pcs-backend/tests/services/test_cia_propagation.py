"""CIAEngine 反向传播测试（P2 Sprint 3 Task 4.1）。

覆盖：
- 1 个 source → 1 个下游被标 STALE
- 环防护（visited set）
- MAX_DEPTH=8 深度截断
- 1 个 source → 多下游全标
- 幽灵记录（lineage 指向不存在的 record_id）静默跳过

实施技巧（避免与 brief 防御性 fix 冲突）：
- 用 `make_asset` (services/conftest.py) 建 source (asset + version bundle)
- 用 `DataLineage` 直接 `db.add(...)` 造测试血缘
- 用 `EquipmentList` 直接 `db.add(...)` 造下游（带 sign_status via mixin）
- 与 STALE 比较用 `RecordSignStatus9.STALE.value`（mixin 字段类型是 Enum，
  直接 == 字符串字面量会被 SQLAlchemy 比较器报错）
"""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import RecordSignStatus9
from app.models.equipment import EquipmentList
from app.models.system import DataLineage

pytestmark = pytest.mark.asyncio


# === helpers（tests/services 局部） =====================================


def _make_equipment(**overrides) -> EquipmentList:
    """最小 EquipmentList 行（含 project_id/workspace_id 等 NOT NULL）。"""
    base = dict(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        type_code="PUMP",
        equipment_name=f"E-{uuid.uuid4().hex[:8]}",
        tag_number=f"T-{uuid.uuid4().hex[:8]}",
    )
    base.update(overrides)
    return EquipmentList(**base)


def _lineage(
    *,
    source_ref_type: str,
    source_ref_id: uuid.UUID,
    record_type: str,
    record_id: uuid.UUID,
    source: str = "TEST",
) -> DataLineage:
    return DataLineage(
        source_ref_type=source_ref_type,
        source_ref_id=source_ref_id,
        record_type=record_type,
        record_id=record_id,
        source=source,
    )


async def _flush(db, *objs):
    """add + flush + refresh，确保下游 sign_status 字段已加载。"""
    for o in objs:
        db.add(o)
    await db.flush()
    for o in objs:
        await db.refresh(o)
    return objs


# === tests ==============================================================


async def test_propagate_marks_downstream_stale(db, make_asset):
    """1 个 config_version 触发 1 条血缘 → 下游 record.sign_status 变 STALE。"""
    from app.services.cia_engine import CIAEngine

    bundle = await make_asset(status="PUBLISHED")
    cfg_v = bundle.version

    eq = _make_equipment()
    await _flush(db, eq)

    db.add(_lineage(
        source_ref_type="config_version",
        source_ref_id=cfg_v.version_id,
        record_type="equipment_list",
        record_id=eq.equipment_id,
    ))
    await db.flush()

    n = await CIAEngine(db).propagate_from_source(
        "config_version", cfg_v.version_id
    )
    assert n == 1
    await db.refresh(eq)
    assert eq.sign_status == RecordSignStatus9.STALE


async def test_propagate_handles_cycle(db, make_asset):
    """A→B→A 循环：visited set 防递归死循环；不应崩、不应死循环。"""
    from app.services.cia_engine import CIAEngine

    bundle = await make_asset(status="PUBLISHED")
    cfg_v = bundle.version

    eq_a = _make_equipment()
    eq_b = _make_equipment()
    await _flush(db, eq_a, eq_b)

    db.add_all([
        _lineage(
            source_ref_type="config_version",
            source_ref_id=cfg_v.version_id,
            record_type="equipment_list",
            record_id=eq_a.equipment_id,
        ),
        _lineage(
            source_ref_type="equipment_list",
            source_ref_id=eq_a.equipment_id,
            record_type="equipment_list",
            record_id=eq_b.equipment_id,
        ),
        _lineage(
            source_ref_type="equipment_list",
            source_ref_id=eq_b.equipment_id,
            record_type="equipment_list",
            record_id=eq_a.equipment_id,  # cycle: B → A
        ),
    ])
    await db.flush()

    # 不应崩、不应死循环
    n = await CIAEngine(db).propagate_from_source(
        "config_version", cfg_v.version_id
    )
    # A 标一次（cfg → A）；B 标一次（A → B）；再次访问 A 被 visited 跳过
    assert n == 2
    await db.refresh(eq_a)
    await db.refresh(eq_b)
    assert eq_a.sign_status == RecordSignStatus9.STALE
    assert eq_b.sign_status == RecordSignStatus9.STALE


async def test_propagate_respects_max_depth(db, make_asset):
    """MAX_DEPTH=8 截断：10 层链中 d1-d8 应被标 STALE，d9/d10 不应被标。

    实现行为：
    - propagate_from_source 入口 depth=0（source）
    - d7 的递归调用 depth=7 时，遍历 d7 的下游：先标 d8 STALE，再 depth=8 递归
    - depth=8 进入函数时首行 return，不再访问 d9/d10
    """
    from app.services.cia_engine import CIAEngine

    bundle = await make_asset(status="PUBLISHED")
    cfg_v = bundle.version

    chain = [_make_equipment() for _ in range(10)]  # d1..d10
    await _flush(db, *chain)

    rows = [
        _lineage(
            source_ref_type="config_version",
            source_ref_id=cfg_v.version_id,
            record_type="equipment_list",
            record_id=chain[0].equipment_id,
        ),
    ]
    for i in range(9):  # d_i → d_{i+1}，i = 0..8 (9 edges)
        rows.append(_lineage(
            source_ref_type="equipment_list",
            source_ref_id=chain[i].equipment_id,
            record_type="equipment_list",
            record_id=chain[i + 1].equipment_id,
        ))
    db.add_all(rows)
    await db.flush()

    n = await CIAEngine(db).propagate_from_source(
        "config_version", cfg_v.version_id
    )
    assert n == 8  # d1..d8 marked

    for i, eq in enumerate(chain, start=1):
        await db.refresh(eq)
        if i <= 8:
            assert eq.sign_status == RecordSignStatus9.STALE, (
                f"d{i} should be STALE"
            )
        else:
            assert eq.sign_status != RecordSignStatus9.STALE, (
                f"d{i} should NOT be STALE (depth truncation)"
            )


async def test_propagate_marks_multiple_downstream_records(db, make_asset):
    """1 source 5 下游：全部被标 STALE。"""
    from app.services.cia_engine import CIAEngine

    bundle = await make_asset(status="PUBLISHED")
    cfg_v = bundle.version

    records = [_make_equipment() for _ in range(5)]
    await _flush(db, *records)

    rows = [
        _lineage(
            source_ref_type="config_version",
            source_ref_id=cfg_v.version_id,
            record_type="equipment_list",
            record_id=r.equipment_id,
        )
        for r in records
    ]
    db.add_all(rows)
    await db.flush()

    n = await CIAEngine(db).propagate_from_source(
        "config_version", cfg_v.version_id
    )
    assert n == 5
    for r in records:
        await db.refresh(r)
        assert r.sign_status == RecordSignStatus9.STALE


async def test_propagate_skips_missing_record(db, make_asset):
    """lineage 指向不存在的 record_id：静默跳过，不抛错。"""
    from app.services.cia_engine import CIAEngine

    bundle = await make_asset(status="PUBLISHED")
    cfg_v = bundle.version

    db.add(_lineage(
        source_ref_type="config_version",
        source_ref_id=cfg_v.version_id,
        record_type="equipment_list",
        record_id=uuid.uuid4(),  # 幽灵 record
    ))
    await db.flush()

    # 不应崩
    n = await CIAEngine(db).propagate_from_source(
        "config_version", cfg_v.version_id
    )
    assert n == 0  # 找不到 record，不标记任何东西
