"""P7 Sprint 2 T2: utility_fuel_gas 测试.

覆盖:
1. ORM 加载 (UtilityFuelGas 表 13 列)
2. 黄金 fixture 加载 (8 算例, 3 设备 × INITIAL/STEADY/MAX 工况 + 燃料类型变体)
3. ORM round-trip (INSERT 8 行 → SELECT 全部回读 → 字段值校验)
4. UNIQUE(project_id, equipment_tag, operating_phase) 约束
5. operating_phase enum CHECK 约束 (PG 端校验 via migration \d)

CHECK 约束 (calorific_value ∈ (0, 20000] / consumption > 0 / hours ∈
(0, 8760] / annual_consumption >= 0 / operating_phase enum) 在 PG migration
\d 校验中已验证 (PCS T2 落地验证), 本测试覆盖 ORM + fixture 路径。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.models.util import UtilityFuelGas

_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "golden_utility_fuel_gas.json"
)


@pytest.fixture(scope="module")
def golden_fixture() -> dict:
    """加载黄金 fixture JSON (per-case 字段)."""
    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_orm_tablename_and_columns():
    """UtilityFuelGas ORM 定义正确 (表名 + 14 列).

    R1 §7.3 新增 gas_source 字段 (气源分类).
    """
    assert UtilityFuelGas.__tablename__ == "utility_fuel_gas"
    col_names = [c.name for c in UtilityFuelGas.__table__.columns]
    expected = {
        "id", "project_id", "workspace_id", "equipment_id", "equipment_tag",
        "fuel_type", "gas_source", "calorific_value_kcal_nm3", "consumption_nm3_h",
        "operating_phase", "operating_hours_per_year", "annual_consumption_nm3",
        "source", "created_at", "updated_at",
    }
    assert set(col_names) == expected


def test_golden_fixture_loads_8_cases(golden_fixture):
    """黄金 fixture 加载 8 算例 (per P7-OPEN-009 §6.2 ≥5 算例要求)."""
    assert "cases" in golden_fixture
    cases = golden_fixture["cases"]
    assert len(cases) == 8
    required_keys = {
        "case_id", "equipment_tag", "fuel_type", "calorific_value_kcal_nm3",
        "consumption_nm3_h", "operating_phase", "operating_hours_per_year",
        "annual_consumption_nm3", "source",
    }
    for case in cases:
        assert required_keys.issubset(case.keys()), f"{case['case_id']} 缺字段"


def test_golden_fixture_operating_phase_enum(golden_fixture):
    """8 算例 operating_phase 全部在 INITIAL/STEADY/MAX 枚举内."""
    valid_phases = {"INITIAL", "STEADY", "MAX"}
    for case in golden_fixture["cases"]:
        assert case["operating_phase"] in valid_phases, (
            f"{case['case_id']} operating_phase={case['operating_phase']} 越界"
        )


def test_golden_fixture_values_within_check_ranges(golden_fixture):
    """8 算例数值均落在 CHECK 约束范围内."""
    for case in golden_fixture["cases"]:
        # calorific_value ∈ (0, 20000]
        assert 0 < case["calorific_value_kcal_nm3"] <= 20000, (
            f"{case['case_id']} calorific_value 越界 {case['calorific_value_kcal_nm3']}"
        )
        # consumption > 0
        assert case["consumption_nm3_h"] > 0
        # hours ∈ (0, 8760]
        assert 0 < case["operating_hours_per_year"] <= 8760
        # annual_consumption >= 0
        assert case["annual_consumption_nm3"] >= 0


@pytest.mark.asyncio
async def test_orm_roundtrip_all_8_cases(db_session, golden_fixture):
    """ORM round-trip: INSERT 8 算例 → SELECT 全部回读 → 字段值校验."""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # INSERT 全部 8 行
    inserted = []
    for case in golden_fixture["cases"]:
        item = UtilityFuelGas(
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_tag=case["equipment_tag"],
            fuel_type=case["fuel_type"],
            calorific_value_kcal_nm3=case["calorific_value_kcal_nm3"],
            consumption_nm3_h=case["consumption_nm3_h"],
            operating_phase=case["operating_phase"],
            operating_hours_per_year=case["operating_hours_per_year"],
            annual_consumption_nm3=case["annual_consumption_nm3"],
            source=case["source"],
        )
        db_session.add(item)
        inserted.append(item)

    await db_session.commit()
    for item in inserted:
        await db_session.refresh(item)

    # SELECT 全部
    from sqlalchemy import select
    stmt = (
        select(UtilityFuelGas)
        .where(UtilityFuelGas.project_id == project_id)
        .order_by(
            UtilityFuelGas.equipment_tag,
            UtilityFuelGas.operating_phase,
        )
    )
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    assert len(rows) == 8
    # 第 1 行应 H-101 INITIAL (字典序最小)
    assert rows[0].equipment_tag == "H-101"
    assert rows[0].operating_phase == "INITIAL"
    assert rows[0].calorific_value_kcal_nm3 == 8500.0
    assert rows[0].consumption_nm3_h == 200.0
    # H-202 STEADY (REFINERY_GAS)
    h202_steady = next(
        r for r in rows
        if r.equipment_tag == "H-202" and r.operating_phase == "STEADY"
    )
    assert h202_steady.fuel_type == "REFINERY_GAS"
    assert h202_steady.calorific_value_kcal_nm3 == 9500.0
    # H-404 LPG
    h404 = next(r for r in rows if r.equipment_tag == "H-404")
    assert h404.fuel_type == "LPG"
    assert h404.calorific_value_kcal_nm3 == 12000.0


@pytest.mark.asyncio
async def test_orm_unique_constraint_per_project_equipment_phase(db_session):
    """UNIQUE(project_id, equipment_tag, operating_phase) 约束."""
    from sqlalchemy.exc import IntegrityError

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    base_kwargs = {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "equipment_tag": "H-DUP",
        "fuel_type": "NATURAL_GAS",
        "calorific_value_kcal_nm3": 8500.0,
        "consumption_nm3_h": 100.0,
        "operating_hours_per_year": 8000.0,
        "annual_consumption_nm3": 800000.0,
    }

    # 第一条 INITIAL 成功
    item1 = UtilityFuelGas(operating_phase="INITIAL", **base_kwargs)
    db_session.add(item1)
    await db_session.commit()

    # 第二条同 (project, equipment_tag, phase) = INITIAL 重复抛 IntegrityError
    item2 = UtilityFuelGas(operating_phase="INITIAL", **base_kwargs)
    db_session.add(item2)
    with pytest.raises(IntegrityError):
        await db_session.commit()