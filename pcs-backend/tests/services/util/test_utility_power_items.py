"""P7 Sprint 2 T1: utility_power_items 测试.

覆盖:
1. ORM 加载 (UtilityPowerItem 表创建 + 列定义正确)
2. 黄金 fixture 加载 (golden_utility_power_items.json 10 算例)
3. ORM round-trip (INSERT 10 行 → SELECT 全部回读 → 字段值校验)
4. UNIQUE(project_id, equipment_tag) 约束 (PG 端校验 via migration \d)

CHECK 约束 (motor_power > 0 / hours ∈ (0, 8760] / load_factor ∈ (0, 1]
/ consumption >= 0) 在 PG migration \d 校验中已验证 (PCS T1 落地验证),
本测试覆盖 ORM + fixture 路径。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.models.util import UtilityPowerItem

# ---------------------------------------------------------------------------
# Fixture 路径
# ---------------------------------------------------------------------------
_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "golden_utility_power_items.json"
)


@pytest.fixture(scope="module")
def golden_fixture() -> dict:
    """加载黄金 fixture JSON (per-case 字段)."""
    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_orm_tablename_and_columns():
    """UtilityPowerItem ORM 定义正确 (表名 + 12 列)."""
    assert UtilityPowerItem.__tablename__ == "utility_power_items"
    col_names = [c.name for c in UtilityPowerItem.__table__.columns]
    expected = {
        "id", "project_id", "workspace_id", "equipment_id", "equipment_tag",
        "motor_power_kw", "operating_hours_per_year", "load_factor",
        "annual_consumption_kwh", "source", "created_at", "updated_at",
    }
    assert set(col_names) == expected


def test_golden_fixture_loads_10_cases(golden_fixture):
    """黄金 fixture 加载 10 算例 (per P7-OPEN-009 §6.2 ≥10 算例要求)."""
    assert "cases" in golden_fixture
    cases = golden_fixture["cases"]
    assert len(cases) == 10

    # 每条算例必含字段
    required_keys = {
        "case_id", "equipment_tag", "motor_power_kw", "operating_hours_per_year",
        "load_factor", "annual_consumption_kwh", "source",
    }
    for case in cases:
        assert required_keys.issubset(case.keys()), f"{case['case_id']} 缺字段"


def test_golden_fixture_values_within_check_ranges(golden_fixture):
    """黄金 fixture 10 算例数值均落在 CHECK 约束范围内."""
    for case in golden_fixture["cases"]:
        # motor_power > 0
        assert case["motor_power_kw"] > 0, f"{case['case_id']} motor_power 非正"
        # hours ∈ (0, 8760]
        assert 0 < case["operating_hours_per_year"] <= 8760, (
            f"{case['case_id']} hours 越界 {case['operating_hours_per_year']}"
        )
        # load_factor ∈ (0, 1]
        assert 0 < case["load_factor"] <= 1, (
            f"{case['case_id']} load_factor 越界 {case['load_factor']}"
        )
        # consumption >= 0
        assert case["annual_consumption_kwh"] >= 0, (
            f"{case['case_id']} consumption 负值"
        )


@pytest.mark.asyncio
async def test_orm_roundtrip_all_10_cases(db_session, golden_fixture):
    """ORM round-trip: INSERT 10 算例 → SELECT 全部回读 → 字段值校验."""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # INSERT 全部 10 行
    inserted = []
    for case in golden_fixture["cases"]:
        item = UtilityPowerItem(
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_tag=case["equipment_tag"],
            motor_power_kw=case["motor_power_kw"],
            operating_hours_per_year=case["operating_hours_per_year"],
            load_factor=case["load_factor"],
            annual_consumption_kwh=case["annual_consumption_kwh"],
            source=case["source"],
        )
        db_session.add(item)
        inserted.append(item)

    await db_session.commit()
    for item in inserted:
        await db_session.refresh(item)

    # SELECT 全部 (按 equipment_tag 排序保证稳定)
    from sqlalchemy import select
    stmt = (
        select(UtilityPowerItem)
        .where(UtilityPowerItem.project_id == project_id)
        .order_by(UtilityPowerItem.equipment_tag)
    )
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    assert len(rows) == 10
    # 验证按 equipment_tag 升序第 1 行 (C-401 < P-* ASCII)
    assert rows[0].equipment_tag == "C-401"
    assert rows[0].motor_power_kw == 1500.0
    assert rows[0].load_factor == 0.92
    assert rows[0].annual_consumption_kwh == 11592000.0
    assert rows[0].source == "PMS"
    # 验证 P-101A 小泵 (按字典序在 C-* 之后)
    p101 = next(r for r in rows if r.equipment_tag == "P-101A")
    assert p101.motor_power_kw == 15.0
    assert p101.annual_consumption_kwh == 102000.0


@pytest.mark.asyncio
async def test_orm_unique_constraint_per_project_equipment_tag(db_session):
    """UNIQUE(project_id, equipment_tag) 约束: 同项目下 equipment_tag 重复抛 IntegrityError."""
    from sqlalchemy.exc import IntegrityError

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 第一条成功
    item1 = UtilityPowerItem(
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_tag="DUPLICATE-TAG",
        motor_power_kw=10.0,
        operating_hours_per_year=8000.0,
        load_factor=0.8,
        annual_consumption_kwh=64000.0,
    )
    db_session.add(item1)
    await db_session.commit()

    # 第二条同 tag 抛 IntegrityError
    item2 = UtilityPowerItem(
        project_id=project_id,
        workspace_id=workspace_id,
        equipment_tag="DUPLICATE-TAG",
        motor_power_kw=20.0,
        operating_hours_per_year=8000.0,
        load_factor=0.8,
        annual_consumption_kwh=128000.0,
    )
    db_session.add(item2)
    with pytest.raises(IntegrityError):
        await db_session.commit()