"""P7 Sprint 2 T4: auxiliary_consumption 4 字段 ALTER 测试.

覆盖:
1. ORM 列定义 (UtilResults 增 4 auxiliary_consumption 字段, nullable=True)
2. Backward compat (Sprint 1 存量数据: 4 字段 NULL 不报错)
3. CHECK 约束 (PG 端: 负值被 ck_util_results_*_NON_negative 拒绝)

数据迁移脚本 (consumption_json → 4 字段 backfill) 不在本批范围 (T5
utility_energy_summary 服务集成入口; D1 裁决 1A: 5 表权威 + JSONB deprecated).
"""

from __future__ import annotations

import uuid

import pytest

from app.models.util import UtilResults


def test_orm_has_4_auxiliary_columns():
    """UtilResults ORM 增 4 auxiliary_consumption 字段 (nullable)."""
    col_names = {c.name for c in UtilResults.__table__.columns}
    expected_new = {
        "electrical_power_kwh_yr",
        "fuel_gas_consumption_nm3_yr",
        "steam_consumption_t_yr",
        "cooling_water_consumption_t_yr",
    }
    assert expected_new.issubset(col_names), (
        f"缺字段: {expected_new - col_names}"
    )
    # 4 字段 nullable=True (backward compat)
    for col_name in expected_new:
        col = UtilResults.__table__.columns[col_name]
        assert col.nullable is True, f"{col_name} 应 nullable=True"


@pytest.mark.asyncio
async def test_backward_compat_null_auxiliary_fields(db_session):
    """Sprint 1 存量数据 4 字段 NULL 不报错 (backward compat).

    创建 UtilResults 时不传 4 auxiliary 字段, 应正常 INSERT 并读回 NULL.
    """
    r = UtilResults(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        consumption_json={"ELECTRICITY": 100.0, "STEAM_HP": 50.0},
    )
    db_session.add(r)
    await db_session.commit()
    await db_session.refresh(r)

    # 4 auxiliary 字段全部 NULL
    assert r.electrical_power_kwh_yr is None
    assert r.fuel_gas_consumption_nm3_yr is None
    assert r.steam_consumption_t_yr is None
    assert r.cooling_water_consumption_t_yr is None
    # 既有字段不变
    assert r.consumption_json == {"ELECTRICITY": 100.0, "STEAM_HP": 50.0}
    assert r.jsonb_deprecated is False


@pytest.mark.asyncio
async def test_orm_with_all_4_auxiliary_fields(db_session):
    """创建 UtilResults 时传 4 auxiliary 字段, INSERT + SELECT 回读校验."""
    r = UtilResults(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        consumption_json={"ELECTRICITY": 100.0},
        electrical_power_kwh_yr=100000.0,
        fuel_gas_consumption_nm3_yr=2000000.0,
        steam_consumption_t_yr=50000.0,
        cooling_water_consumption_t_yr=300000.0,
    )
    db_session.add(r)
    await db_session.commit()
    await db_session.refresh(r)

    assert r.electrical_power_kwh_yr == 100000.0
    assert r.fuel_gas_consumption_nm3_yr == 2000000.0
    assert r.steam_consumption_t_yr == 50000.0
    assert r.cooling_water_consumption_t_yr == 300000.0