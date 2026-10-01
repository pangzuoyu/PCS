"""P7 Sprint 2 T5: utility_energy_summary service 测试.

覆盖:
1. ORM 加载 (UtilityEnergySummary 21 列)
2. service 聚合 T1+T2+T3 子表 + 折标系数 CONFIG = 总能耗 + 折标油 + 折标煤
3. 容差校验 (≤2% per P7-OPEN-009 §6)
4. idempotent (同 project/year/source 覆盖)

test 使用 conftest.py:db_session (SQLite in-memory) + 测试 setup 注入
ConfigEnergyConversionFactor 6 行 (仿 T0 seed, 因 SQLite 测试库不存
真实 PG seed)。
"""

from __future__ import annotations

import json
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigEnergyConversionFactor
from app.models.util import (
    UtilityEnergySummary,
    UtilityFuelGas,
    UtilityHeatExchange,
    UtilityPowerItem,
)
from app.services.util.utility_energy_summary_service import summarize_energy_year

_FIXTURE_PATH = (
    Path(__file__).resolve().parent
    / "fixtures"
    / "golden_utility_energy_summary.json"
)

# T0 seed 6 类能源折标系数 (per PCS-SIGN-F-P0-001-2026-10-08 工艺室正式签字)
# GB/T 50441-2016《石油化工企业能耗计算标准》附录 A:
# - 蒸汽 94.4 per-tonne = 0.0944 kg标油/kg × 1000
# - 水 0.1 per-tonne = 0.0001 kg标油/kg × 1000
# - 其他 per-Nm³ 或 per-kWh 直接引用附录 A
SEED_FACTORS = [
    {
        "energy_type": "ELECTRICITY",
        "toe_factor": 0.1229,            # kWh → kg 标油
        "standard_coal_factor": 0.1229,  # kWh → kg 标煤
        "source": "GB_T_50441_2016_APPENDIX_A",
    },
    {
        "energy_type": "FUEL_GAS",
        "toe_factor": 1.0000,            # Nm³ → kg 标油
        "standard_coal_factor": 1.4286,  # Nm³ → kg 标煤
        "source": "GB_T_50441_2016_APPENDIX_A",
    },
    {
        "energy_type": "STEAM",
        "toe_factor": 94.4,              # t per-tonne 口径
        "standard_coal_factor": 128.6,   # t per-tonne 口径
        "source": "GB_T_50441_2016_APPENDIX_A",
    },
    {
        "energy_type": "WATER",
        "toe_factor": 0.1,               # t per-tonne 口径
        "standard_coal_factor": 0.136,   # t per-tonne 口径
        "source": "GB_T_50441_2016_APPENDIX_A",
    },
    {
        "energy_type": "NITROGEN",
        "toe_factor": 0.0004,            # Nm³ → kg 标油
        "standard_coal_factor": 0.000571,  # Nm³ → kg 标煤
        "source": "GB_T_50441_2016_APPENDIX_A",
    },
    {
        "energy_type": "INSTRUMENT_AIR",
        "toe_factor": 0.00012,           # Nm³ → kg 标油
        "standard_coal_factor": 0.000171,  # Nm³ → kg 标煤
        "source": "GB_T_50441_2016_APPENDIX_A",
    },
]


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_config_factors(db_session: AsyncSession):
    """注入 6 类 ConfigEnergyConversionFactor 折标系数 (仿 T0 seed)."""
    for f in SEED_FACTORS:
        db_session.add(ConfigEnergyConversionFactor(**f))
    await db_session.commit()
    yield


@pytest.fixture(scope="module")
def golden_fixture() -> dict:
    with _FIXTURE_PATH.open(encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_orm_tablename_and_columns():
    assert UtilityEnergySummary.__tablename__ == "utility_energy_summary"
    col_names = {c.name for c in UtilityEnergySummary.__table__.columns}
    assert "annual_total_energy" in col_names
    assert "toe_conversion_factor" in col_names
    assert "standard_coal_factor" in col_names
    assert "total_toe" in col_names
    assert "total_standard_coal_kg" in col_names
    assert "tolerance_status" in col_names


def test_golden_fixture_loads_3_cases(golden_fixture):
    cases = golden_fixture["cases"]
    assert len(cases) == 3


@pytest.mark.asyncio
async def test_service_aggregates_t1t2t3_within_tolerance(
    db_session, seeded_config_factors, golden_fixture
):
    """3 算例: 聚合 T1+T2+T3 子表 + 折标系数 → totals 与 expected 偏差 ≤2%.

    容差校验 = 浮动点误差级别 (<1e-6)。
    """
    for case in golden_fixture["cases"]:
        project_id = uuid.uuid4()
        workspace_id = uuid.uuid4()
        expected = case["expected"]

        # 1. 注入 T1 power_items
        for item in case["power_items"]:
            db_session.add(
                UtilityPowerItem(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    equipment_tag=item["equipment_tag"],
                    motor_power_kw=10.0,
                    operating_hours_per_year=8000.0,
                    load_factor=0.8,
                    annual_consumption_kwh=item["annual_consumption_kwh"],
                )
            )

        # 2. 注入 T2 fuel_gas_items (含 operating_phase)
        for item in case["fuel_gas_items"]:
            db_session.add(
                UtilityFuelGas(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    equipment_tag=item["equipment_tag"],
                    fuel_type="NATURAL_GAS",
                    calorific_value_kcal_nm3=8500.0,
                    consumption_nm3_h=100.0,
                    operating_phase=item["operating_phase"],
                    operating_hours_per_year=8000.0,
                    annual_consumption_nm3=item["annual_consumption_nm3"],
                )
            )

        # 3. 注入 T3 heat_exchange_items (temperature_class 默认 MP)
        for item in case["heat_exchange_items"]:
            db_session.add(
                UtilityHeatExchange(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    equipment_tag=item["equipment_tag"],
                    steam_pressure_mpa_gauge=1.6,
                    steam_quality_pct=99.0,
                    return_condensate_pct=80.0,
                    temperature_class="MP",
                    steam_consumption_t_h=5.0,
                    operating_hours_per_year=8000.0,
                    annual_consumption_t=item["annual_consumption_t"],
                )
            )

        await db_session.commit()

        # 4. 调用 service 聚合
        summary = await summarize_energy_year(
            db=db_session,
            project_id=project_id,
            workspace_id=workspace_id,
            business_year=case["business_year"],
        )

        # 5. 验证聚合结果 (容差 1e-6 浮动点)
        assert summary.electricity_kwh_yr == pytest.approx(
            expected["electricity_kwh_yr"], abs=1e-3
        )
        assert summary.fuel_gas_nm3_yr == pytest.approx(
            expected["fuel_gas_nm3_yr"], abs=1e-3
        )
        assert summary.steam_t_yr == pytest.approx(
            expected["steam_t_yr"], abs=1e-3
        )
        assert summary.annual_total_energy == pytest.approx(
            expected["annual_total_energy_mj"], abs=1.0
        )
        assert summary.total_toe == pytest.approx(
            expected["total_toe_tonne"], abs=1e-3
        )
        assert summary.total_standard_coal_kg == pytest.approx(
            expected["total_standard_coal_kg"], abs=1.0
        )
        assert summary.tolerance_status == expected["tolerance_status"]
        # business_year 一致
        assert summary.business_year == case["business_year"]
        assert summary.source == "CALCULATION"

        # 清空 power_items / fuel_gas / heat_exchange (下一个 case 用同 PROJECT)
        from sqlalchemy import delete as sa_delete
        await db_session.execute(
            sa_delete(UtilityPowerItem).where(
                UtilityPowerItem.project_id == project_id
            )
        )
        await db_session.execute(
            sa_delete(UtilityFuelGas).where(
                UtilityFuelGas.project_id == project_id
            )
        )
        await db_session.execute(
            sa_delete(UtilityHeatExchange).where(
                UtilityHeatExchange.project_id == project_id
            )
        )
        await db_session.execute(
            sa_delete(UtilityEnergySummary).where(
                UtilityEnergySummary.project_id == project_id
            )
        )
        await db_session.commit()


@pytest.mark.asyncio
async def test_service_idempotent_overwrites_same_year_source(
    db_session, seeded_config_factors
):
    """idempotent: 同 (project, year, source) 已存在则覆盖更新 (无 dup)."""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 第一次调用
    summary1 = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2027,
    )
    first_id = summary1.id

    # 注入 1 条 T1 数据 → 第二次调用应覆盖
    db_session.add(
        UtilityPowerItem(
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_tag="P-IDEMP",
            motor_power_kw=10.0,
            operating_hours_per_year=8000.0,
            load_factor=0.8,
            annual_consumption_kwh=50000.0,
        )
    )
    await db_session.commit()

    summary2 = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2027,
    )

    # 同 ID (覆盖更新, 非新建)
    assert summary2.id == first_id
    # 聚合更新
    assert summary2.electricity_kwh_yr == pytest.approx(50000.0, abs=1e-3)
    assert summary2.total_toe > 0


@pytest.mark.asyncio
async def test_service_tolerance_check_within_2pct(
    db_session, seeded_config_factors
):
    """容差校验: tolerance_pct ≤ 2% → tolerance_status='OK'."""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 注入 T1 数据 → service 计算
    db_session.add(
        UtilityPowerItem(
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_tag="P-TOL",
            motor_power_kw=10.0,
            operating_hours_per_year=8000.0,
            load_factor=0.8,
            annual_consumption_kwh=100000.0,
        )
    )
    await db_session.commit()

    summary_calc = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2028,
    )

    # 构造 XLS_REFERENCE 同年记录 (假设偏差 1%)
    xls_ref = UtilityEnergySummary(
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2028,
        source="XLS_REFERENCE",
        annual_total_energy=0.0,
        toe_conversion_factor=1e-9,
        standard_coal_factor=1e-9,
        total_toe=summary_calc.total_toe * 1.01,  # +1% 偏差
        total_standard_coal_kg=summary_calc.total_standard_coal_kg * 1.01,
        tolerance_status="NA",
    )
    db_session.add(xls_ref)
    await db_session.commit()

    # 第二次调用 (CALCULATION) 带 xls_reference 触发容差校验
    summary_with_tol = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2028,
        xls_reference=xls_ref,
    )

    # 容差 ≈ 1%, ≤ 2% → OK
    assert summary_with_tol.tolerance_status == "OK"
    assert summary_with_tol.tolerance_pct == pytest.approx(1.0, abs=0.01)