"""P7 Sprint 2 T3: utility_heat_exchange 测试.

覆盖:
1. ORM 加载 (UtilityHeatExchange 15 列)
2. 黄金 fixture 加载 (6 算例, 4 蒸汽等级 LP/MP/HP/ULTRA_HIGH)
3. ORM round-trip (INSERT 6 行 → SELECT 全部回读)
4. UNIQUE(project_id, equipment_tag) 约束
5. temperature_class enum CHECK 约束 (PG migration \d 校验)
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest

from app.models.util import UtilityHeatExchange

_FIXTURE_PATH = (
    Path(__file__).resolve().parent / "fixtures" / "golden_utility_heat_exchange.json"
)


@pytest.fixture(scope="module")
def golden_fixture() -> dict:
    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


def test_orm_tablename_and_columns():
    assert UtilityHeatExchange.__tablename__ == "utility_heat_exchange"
    col_names = [c.name for c in UtilityHeatExchange.__table__.columns]
    expected = {
        "id", "project_id", "workspace_id", "equipment_id", "equipment_tag",
        "steam_pressure_mpa_gauge", "steam_quality_pct",
        "return_condensate_pct", "temperature_class",
        "steam_consumption_t_h", "operating_hours_per_year",
        "annual_consumption_t", "source", "created_at", "updated_at",
    }
    assert set(col_names) == expected


def test_golden_fixture_loads_6_cases(golden_fixture):
    cases = golden_fixture["cases"]
    assert len(cases) == 6
    required_keys = {
        "case_id", "equipment_tag", "temperature_class",
        "steam_pressure_mpa_gauge", "steam_quality_pct",
        "return_condensate_pct", "steam_consumption_t_h",
        "operating_hours_per_year", "annual_consumption_t", "source",
    }
    for case in cases:
        assert required_keys.issubset(case.keys()), f"{case['case_id']} 缺字段"


def test_golden_fixture_temperature_class_enum(golden_fixture):
    valid_classes = {"LP", "MP", "HP", "ULTRA_HIGH"}
    for case in golden_fixture["cases"]:
        assert case["temperature_class"] in valid_classes, (
            f"{case['case_id']} temperature_class 越界"
        )


def test_golden_fixture_values_within_check_ranges(golden_fixture):
    for case in golden_fixture["cases"]:
        # pressure > 0
        assert case["steam_pressure_mpa_gauge"] > 0
        # quality ∈ [0, 100]
        assert 0 <= case["steam_quality_pct"] <= 100
        # return_condensate ∈ [0, 100]
        assert 0 <= case["return_condensate_pct"] <= 100
        # hours ∈ (0, 8760]
        assert 0 < case["operating_hours_per_year"] <= 8760
        # annual_consumption >= 0
        assert case["annual_consumption_t"] >= 0


@pytest.mark.asyncio
async def test_orm_roundtrip_all_6_cases(db_session, golden_fixture):
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    for case in golden_fixture["cases"]:
        item = UtilityHeatExchange(
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_tag=case["equipment_tag"],
            steam_pressure_mpa_gauge=case["steam_pressure_mpa_gauge"],
            steam_quality_pct=case["steam_quality_pct"],
            return_condensate_pct=case["return_condensate_pct"],
            temperature_class=case["temperature_class"],
            steam_consumption_t_h=case["steam_consumption_t_h"],
            operating_hours_per_year=case["operating_hours_per_year"],
            annual_consumption_t=case["annual_consumption_t"],
            source=case["source"],
        )
        db_session.add(item)

    await db_session.commit()

    from sqlalchemy import select
    stmt = (
        select(UtilityHeatExchange)
        .where(UtilityHeatExchange.project_id == project_id)
        .order_by(UtilityHeatExchange.equipment_tag)
    )
    result = await db_session.execute(stmt)
    rows = result.scalars().all()

    assert len(rows) == 6
    # ST-HP-301 中间档
    hp = next(r for r in rows if r.equipment_tag == "ST-HP-301")
    assert hp.temperature_class == "HP"
    assert hp.steam_pressure_mpa_gauge == 4.0
    assert hp.steam_consumption_t_h == 8.0
    # ST-UH-401 超高压
    uh = next(r for r in rows if r.equipment_tag == "ST-UH-401")
    assert uh.temperature_class == "ULTRA_HIGH"
    assert uh.steam_pressure_mpa_gauge == 13.5
    assert uh.annual_consumption_t == 120000.0


@pytest.mark.asyncio
async def test_orm_unique_constraint_per_project_equipment_tag(db_session):
    from sqlalchemy.exc import IntegrityError

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    base = {
        "project_id": project_id,
        "workspace_id": workspace_id,
        "equipment_tag": "ST-DUP",
        "steam_pressure_mpa_gauge": 1.0,
        "steam_quality_pct": 99.0,
        "return_condensate_pct": 80.0,
        "temperature_class": "MP",
        "steam_consumption_t_h": 5.0,
        "operating_hours_per_year": 8000.0,
        "annual_consumption_t": 40000.0,
    }

    item1 = UtilityHeatExchange(**base)
    db_session.add(item1)
    await db_session.commit()

    item2 = UtilityHeatExchange(**base)
    db_session.add(item2)
    with pytest.raises(IntegrityError):
        await db_session.commit()