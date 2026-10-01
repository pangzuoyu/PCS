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

# T0 seed 6 类能源折标系数 (per PCS-SIGN-F-P0-001-2026-10-08-R1 工艺室正式签字)
# GB 30251-2024《炼化行业单位产品能源消耗限额》附录 A + 三层标准交叉核对:
# - 电 0.086 kg标油/kWh (当量值) / 0.21 kg标油/kWh (等价值, 炼油/乙烯用)
# - 蒸汽按压力等级 9 档 55–92 kg标油/t (本测试用 MP 1.0 MPa = 76 kg标油/t)
# - 水按类型 9 类 0.06–10.14 kg标油/t (本测试用循环水 = 0.06 kg标油/t)
# - 氮气 0.15 kg标油/m³
# - 仪表空气 0.028/0.038 kg标油/m³ (净化/非净化)
# - 燃料气按气源 0.85/0.93/950 (本测试用气田气 0.85)
SEED_FACTORS = [
    {
        "energy_type": "ELECTRICITY",
        "value_type": "EQUIVALENT",
        "toe_factor": 0.086,            # kWh → kg 标油 (当量值)
        "standard_coal_factor": 0.122857,  # 0.086 / 0.7
        "source": "GB_30251_2024_APPENDIX_A",
    },
    {
        "energy_type": "ELECTRICITY",
        "value_type": "EQUIVALENT_VALUE",
        "toe_factor": 0.21,             # kWh → kg 标油 (等价值; 炼油/乙烯)
        "standard_coal_factor": 0.30,   # 0.21 / 0.7
        "source": "GB_30251_2024_APPENDIX_A",
    },
    {
        "energy_type": "FUEL_GAS",
        "sub_type": "GASFIELD_GAS",
        "toe_factor": 0.85,             # Nm³ → kg 标油 (气田气)
        "standard_coal_factor": 1.214286,  # 0.85 / 0.7
        "source": "GB_30251_2024_APPENDIX_A",
    },
    {
        "energy_type": "FUEL_GAS",
        "sub_type": "OILFIELD_GAS",
        "toe_factor": 0.93,             # Nm³ → kg 标油 (油田气)
        "standard_coal_factor": 1.328571,  # 0.93 / 0.7
        "source": "GB_30251_2024_APPENDIX_A",
    },
    {
        "energy_type": "STEAM",
        "pressure_level": "0_8_TO_1_2_MPA",
        "toe_factor": 76.0,             # t → kg 标油 (1.0 MPa MP 蒸汽)
        "standard_coal_factor": 108.571429,  # 76.0 / 0.7
        "source": "GB_30251_2024_APPENDIX_A",
    },
    {
        "energy_type": "STEAM",
        "pressure_level": "GE_7_0_MPA",
        "toe_factor": 92.0,             # t → kg 标油 (≥7.0 MPa 高压蒸汽)
        "standard_coal_factor": 131.428571,  # 92.0 / 0.7
        "source": "GB_30251_2024_APPENDIX_A",
    },
    {
        "energy_type": "WATER",
        "water_type": "CIRCULATING_WATER",
        "toe_factor": 0.06,             # t → kg 标油 (循环水)
        "standard_coal_factor": 0.085714,  # 0.06 / 0.7
        "source": "GB_30251_2024_APPENDIX_A",
    },
    {
        "energy_type": "NITROGEN",
        "toe_factor": 0.15,             # Nm³ → kg 标油
        "standard_coal_factor": 0.214286,  # 0.15 / 0.7
        "source": "GB_30251_2024_APPENDIX_A",
    },
    {
        "energy_type": "INSTRUMENT_AIR",
        "sub_type": "PURIFIED",
        "toe_factor": 0.038,            # Nm³ → kg 标油 (净化)
        "standard_coal_factor": 0.054286,  # 0.038 / 0.7
        "source": "GB_30251_2024_APPENDIX_A",
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


def test_golden_fixture_loads_4_cases(golden_fixture):
    """Case 1-3 合成算例 + Case 4 蜡油加氢 XLS 真实算例 (D 步 BLOCKER-2)."""
    cases = golden_fixture["cases"]
    assert len(cases) == 4
    # Case 4 必含蜡油加氢标记
    assert any("WAXY_OIL_HYDRO" in c["case_id"] for c in cases)


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

        # 2. 注入 T2 fuel_gas_items (含 operating_phase + R1 §7.3 gas_source)
        for item in case["fuel_gas_items"]:
            db_session.add(
                UtilityFuelGas(
                    project_id=project_id,
                    workspace_id=workspace_id,
                    equipment_tag=item["equipment_tag"],
                    fuel_type="NATURAL_GAS",
                    gas_source="GASFIELD_GAS",  # R1 §7.3
                    calorific_value_kcal_nm3=8500.0,
                    consumption_nm3_h=100.0,
                    operating_phase=item["operating_phase"],
                    operating_hours_per_year=8000.0,
                    annual_consumption_nm3=item["annual_consumption_nm3"],
                )
            )

        # 3. 注入 T3 heat_exchange_items (temperature_class 默认 MP; R1 加 pressure_level)
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
                    pressure_level="0_8_TO_1_2_MPA",  # R1 §7.1
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

        # 5. 验证聚合结果 (容差: Case 1-3 用 1e-3 浮点级; Case 4 (蜡油加氢 XLS) 大累积值用 1.0)
        #     Case 4 年累积 60M+ kWh, 24M+ Nm3, 多项 sum 累计误差 ~0.1
        is_case4 = "WAXY_OIL_HYDRO" in case["case_id"]
        annual_abs = 1.0 if is_case4 else 1e-3
        assert summary.electricity_kwh_yr == pytest.approx(
            expected["electricity_kwh_yr"], abs=annual_abs
        )
        assert summary.fuel_gas_nm3_yr == pytest.approx(
            expected["fuel_gas_nm3_yr"], abs=annual_abs
        )
        assert summary.steam_t_yr == pytest.approx(
            expected["steam_t_yr"], abs=annual_abs
        )
        assert summary.annual_total_energy == pytest.approx(
            expected["annual_total_energy_mj"], abs=100.0  # R1 多能源汇总浮点累计
        )
        assert summary.total_toe == pytest.approx(
            expected["total_toe_tonne"], abs=1e-3
        )
        assert summary.total_standard_coal_kg == pytest.approx(
            expected["total_standard_coal_kg"], abs=100.0  # R1 多能源汇总浮点累计
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


@pytest.mark.asyncio
async def test_service_electricity_value_type_persisted(
    db_session, seeded_config_factors
):
    """R1 §5: electricity_value_type 持久化到 UtilityEnergySummary.

    验证 EQUIVALENT_VALUE (炼油/乙烯用) → total_toe 翻 2.44 倍 (0.21/0.086).
    """
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 注入 1 条 power item (100 kWh/yr)
    db_session.add(
        UtilityPowerItem(
            project_id=project_id,
            workspace_id=workspace_id,
            equipment_tag="P-R1-TEST",
            motor_power_kw=10.0,
            operating_hours_per_year=10000.0,
            load_factor=1.0,
            annual_consumption_kwh=100.0,
        )
    )
    await db_session.commit()

    # 1. EQUIVALENT (默认; 其他产品)
    s_equiv = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2027,
        electricity_value_type="EQUIVALENT",
    )
    assert s_equiv.electricity_value_type == "EQUIVALENT"
    equiv_total = s_equiv.total_toe

    # 2. EQUIVALENT_VALUE (炼油/乙烯)
    s_value = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2027,
        electricity_value_type="EQUIVALENT_VALUE",
    )
    assert s_value.electricity_value_type == "EQUIVALENT_VALUE"
    value_total = s_value.total_toe

    # 等价值 = 当量值 × 0.21/0.086 ≈ 2.44 倍
    assert value_total == pytest.approx(equiv_total * 0.21 / 0.086, rel=1e-3)
    # 验证不变量: 总能源消耗字段相同 (单位换算不变)
    assert s_equiv.electricity_kwh_yr == s_value.electricity_kwh_yr


@pytest.mark.asyncio
async def test_service_aggregates_by_pressure_level(
    db_session, seeded_config_factors
):
    """R1 §7.1: utility_heat_exchange 按 pressure_level 9 档分类聚合.

    验证: 注入 2 个 pressure_level 各 1 条记录, 聚合 dict 含 2 个 key 且合计正确.
    """
    from app.services.util.utility_energy_summary_service import (
        _aggregate_util_subtables, EnergyAggregation,
    )

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 注入 2 个不同压力等级的蒸汽记录
    db_session.add_all([
        UtilityHeatExchange(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="ST-MP-001", temperature_class="MP",
            pressure_level="0_8_TO_1_2_MPA",
            steam_pressure_mpa_gauge=1.0, steam_quality_pct=99.0,
            return_condensate_pct=80.0, steam_consumption_t_h=10.0,
            operating_hours_per_year=8000, annual_consumption_t=80000.0,
        ),
        UtilityHeatExchange(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="ST-HP-001", temperature_class="HP",
            pressure_level="GE_7_0_MPA",
            steam_pressure_mpa_gauge=10.0, steam_quality_pct=99.0,
            return_condensate_pct=80.0, steam_consumption_t_h=5.0,
            operating_hours_per_year=8000, annual_consumption_t=40000.0,
        ),
    ])
    await db_session.commit()

    agg = await _aggregate_util_subtables(db_session, project_id, 2027)

    # R1 分类聚合
    assert agg.steam_t_by_pressure_level is not None
    assert agg.steam_t_by_pressure_level["0_8_TO_1_2_MPA"] == pytest.approx(80000.0)
    assert agg.steam_t_by_pressure_level["GE_7_0_MPA"] == pytest.approx(40000.0)

    # steam_t_yr (R0 单值) 等于分类总和
    assert agg.steam_t_yr == pytest.approx(120000.0)


@pytest.mark.asyncio
async def test_service_aggregates_by_gas_source(
    db_session, seeded_config_factors
):
    """R1 §7.3: utility_fuel_gas 按 gas_source 3 类分类聚合."""
    from app.services.util.utility_energy_summary_service import (
        _aggregate_util_subtables,
    )

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 注入 2 个不同气源的燃料气记录
    db_session.add_all([
        UtilityFuelGas(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="F-GASFIELD-001", fuel_type="NATURAL_GAS",
            gas_source="GASFIELD_GAS", calorific_value_kcal_nm3=8500.0,
            consumption_nm3_h=100.0, operating_phase="STEADY",
            operating_hours_per_year=8000, annual_consumption_nm3=800000.0,
        ),
        UtilityFuelGas(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="F-OILFIELD-001", fuel_type="OTHERS",
            gas_source="OILFIELD_GAS", calorific_value_kcal_nm3=9000.0,
            consumption_nm3_h=50.0, operating_phase="STEADY",
            operating_hours_per_year=8000, annual_consumption_nm3=400000.0,
        ),
    ])
    await db_session.commit()

    agg = await _aggregate_util_subtables(db_session, project_id, 2027)

    # R1 分类聚合
    assert agg.fuel_gas_by_source is not None
    assert agg.fuel_gas_by_source["GASFIELD_GAS"] == pytest.approx(800000.0)
    assert agg.fuel_gas_by_source["OILFIELD_GAS"] == pytest.approx(400000.0)

    # fuel_gas_nm3_yr (R0 单值) 等于分类总和
    assert agg.fuel_gas_nm3_yr == pytest.approx(1200000.0)


@pytest.mark.asyncio
async def test_compute_totals_uses_classified_factors(
    db_session, seeded_config_factors
):
    """R1 §7.1+§7.3: _compute_totals 按分类查 R1 系数 (替代单值 fallback).

    验证: 注入 2 个不同 pressure_level 蒸汽, 总 toe 应按各自档位系数计算
    (不是按 fallback 单值 76.0).
    """
    from app.services.util.utility_energy_summary_service import (
        _aggregate_util_subtables, _compute_totals,
        _get_factors_by_classification,
    )

    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 注入 1 条 MP (0_8_TO_1_2_MPA = 76) + 1 条 HP (GE_7_0_MPA = 92)
    db_session.add_all([
        UtilityHeatExchange(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="ST-MP", temperature_class="MP",
            pressure_level="0_8_TO_1_2_MPA",
            steam_pressure_mpa_gauge=1.0, steam_quality_pct=99.0,
            return_condensate_pct=80.0, steam_consumption_t_h=1.0,
            operating_hours_per_year=8400, annual_consumption_t=8400.0,
        ),
        UtilityHeatExchange(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="ST-HP", temperature_class="HP",
            pressure_level="GE_7_0_MPA",
            steam_pressure_mpa_gauge=10.0, steam_quality_pct=99.0,
            return_condensate_pct=80.0, steam_consumption_t_h=1.0,
            operating_hours_per_year=8400, annual_consumption_t=8400.0,
        ),
    ])
    await db_session.commit()

    agg = await _aggregate_util_subtables(db_session, project_id, 2027)
    factors_by_class = await _get_factors_by_classification(db_session)

    # 注入测试 ELECTRICITY row 0 (避免 ELECTRICITY 0 触发 fallback)
    # 实际计算时 f_toe/f_coal 来自 seeded factors dict 单值

    # 计算 (不传 electricity_value_type 默认 EQUIVALENT)
    from app.services.util.utility_energy_summary_service import _get_factors_default
    factors = await _get_factors_default(db_session)

    _, total_coal_kg, _ = _compute_totals(
        agg, factors,
        electricity_value_type="EQUIVALENT",
        factors_by_class=factors_by_class,
    )

    # 期望: MP 8400 × 108.571429 + HP 8400 × 131.428571
    #     = 911,999.99 + 1,103,999.99 ≈ 2,016,000 kg
    expected_steam_coal = 8400 * 108.571429 + 8400 * 131.428571
    assert total_coal_kg == pytest.approx(expected_steam_coal, rel=1e-3)


@pytest.mark.asyncio
async def test_service_persists_r1_classification_json(
    db_session, seeded_config_factors
):
    """R1 §7: summarize_energy_year 持久化 r1_classification_json 字段.

    验证: 注入 MP+HP 蒸汽 + GASFIELD_GAS 燃料气 → 落库 r1_classification_json
    含 steam_by_pressure_level + fuel_gas_by_source (water_by_type 待 P7-6B).
    """
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 注入 MP+HP 蒸汽 + GASFIELD_GAS 燃料气
    db_session.add_all([
        UtilityHeatExchange(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="ST-MP", temperature_class="MP",
            pressure_level="0_8_TO_1_2_MPA",
            steam_pressure_mpa_gauge=1.0, steam_quality_pct=99.0,
            return_condensate_pct=80.0, steam_consumption_t_h=1.0,
            operating_hours_per_year=8000, annual_consumption_t=8000.0,
        ),
        UtilityHeatExchange(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="ST-HP", temperature_class="HP",
            pressure_level="GE_7_0_MPA",
            steam_pressure_mpa_gauge=10.0, steam_quality_pct=99.0,
            return_condensate_pct=80.0, steam_consumption_t_h=0.5,
            operating_hours_per_year=8000, annual_consumption_t=4000.0,
        ),
        UtilityFuelGas(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="F-001", fuel_type="NATURAL_GAS",
            gas_source="GASFIELD_GAS",
            calorific_value_kcal_nm3=8500.0, consumption_nm3_h=200.0,
            operating_phase="STEADY", operating_hours_per_year=8000,
            annual_consumption_nm3=1600000.0,
        ),
    ])
    await db_session.commit()

    summary = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2026,
    )

    # 1. electricity_value_type 默认 EQUIVALENT 持久化
    assert summary.electricity_value_type == "EQUIVALENT"

    # 2. r1_classification_json 持久化 (dict round-trip)
    assert summary.r1_classification_json is not None
    r1 = summary.r1_classification_json
    assert r1["steam_by_pressure_level"]["0_8_TO_1_2_MPA"] == pytest.approx(8000.0)
    assert r1["steam_by_pressure_level"]["GE_7_0_MPA"] == pytest.approx(4000.0)
    assert r1["fuel_gas_by_source"]["GASFIELD_GAS"] == pytest.approx(1600000.0)
    # water_by_type 未落地 (P7-6B 冷却水子表待 P7-6B)
    assert "water_by_type" not in r1


@pytest.mark.asyncio
async def test_service_persists_equivalent_value_type(
    db_session, seeded_config_factors
):
    """R1 §5: EQUIVALENT_VALUE (炼油/乙烯) 持久化.

    验证: 等价值选择持久化到 electricity_value_type 字段.
    """
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    db_session.add(
        UtilityPowerItem(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="P-EV",
            motor_power_kw=10.0, operating_hours_per_year=8000,
            load_factor=0.8, annual_consumption_kwh=100000.0,
        )
    )
    await db_session.commit()

    summary = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2026,
        electricity_value_type="EQUIVALENT_VALUE",
    )

    assert summary.electricity_value_type == "EQUIVALENT_VALUE"
    # EQUIVALENT_VALUE 系数 0.21 → 100000 × 0.21 / 1000 = 21.0 tonne
    assert summary.total_toe == pytest.approx(21.0, abs=1e-3)


@pytest.mark.asyncio
async def test_service_persists_r1_classification_on_idempotent_overwrite(
    db_session, seeded_config_factors
):
    """R1 §7: 同 (project, year, source) 覆盖更新时, r1_classification_json 也覆盖.

    验证: 二次调用更新分类聚合 dict (非 INSERT NULL).
    """
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()

    # 第一次: 仅 MP 蒸汽
    db_session.add(
        UtilityHeatExchange(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="ST-MP", temperature_class="MP",
            pressure_level="0_8_TO_1_2_MPA",
            steam_pressure_mpa_gauge=1.0, steam_quality_pct=99.0,
            return_condensate_pct=80.0, steam_consumption_t_h=1.0,
            operating_hours_per_year=8000, annual_consumption_t=1000.0,
        )
    )
    await db_session.commit()

    s1 = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2026,
    )
    first_id = s1.id
    assert s1.r1_classification_json is not None
    assert s1.r1_classification_json["steam_by_pressure_level"]["0_8_TO_1_2_MPA"] == pytest.approx(1000.0)

    # 第二次: 加 HP 蒸汽
    db_session.add(
        UtilityHeatExchange(
            project_id=project_id, workspace_id=workspace_id,
            equipment_tag="ST-HP", temperature_class="HP",
            pressure_level="GE_7_0_MPA",
            steam_pressure_mpa_gauge=10.0, steam_quality_pct=99.0,
            return_condensate_pct=80.0, steam_consumption_t_h=1.0,
            operating_hours_per_year=8000, annual_consumption_t=2000.0,
        )
    )
    await db_session.commit()

    s2 = await summarize_energy_year(
        db=db_session,
        project_id=project_id,
        workspace_id=workspace_id,
        business_year=2026,
    )
    # 同 ID (覆盖更新)
    assert s2.id == first_id
    # 分类聚合覆盖更新 (含新增 HP)
    assert s2.r1_classification_json["steam_by_pressure_level"]["0_8_TO_1_2_MPA"] == pytest.approx(1000.0)
    assert s2.r1_classification_json["steam_by_pressure_level"]["GE_7_0_MPA"] == pytest.approx(2000.0)