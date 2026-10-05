"""工艺气体 / 低温热子表聚合 (P7-6B 收尾).

补上 T5 长期缺失的 4 个能源类别 —— 它们的 CONFIG 系数一直存在
(氮气 0.15、净化空气 0.038、非净化空气 0.028 kg标油/m³、低温热 0.012 kg标油/MJ,
均为 GB 30251-2024 附录A 表A.1 序号 31/32/33/34), 但 `_aggregate_util_subtables`
里 `gas_nm3_yr` / `low_temp_heat_gj_yr` 是**硬编码 None**, 从来没读过任何子表。

同时修订 SPEC V1.4 §4.4 的旧口径: `category_map.py` 的 13→6 映射写着
"NITROGEN / INSTRUMENT_AIR / PLANT_AIR → None（无 TOE 折算）", 但炼化强制国标
GB 30251-2024 给了折标系数 → 以标准为准。

映射 (gas_medium → CONFIG energy_type):
    PROCESS_GAS      → GAS
    NITROGEN         → NITROGEN
    PURIFIED_AIR     → INSTRUMENT_AIR / sub_type=PURIFIED
    NON_PURIFIED_AIR → INSTRUMENT_AIR / sub_type=NON_PURIFIED
    PLANT_AIR        → INSTRUMENT_AIR / sub_type=NON_PURIFIED (厂区空气按非净化)
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigEnergyConversionFactor
from app.models.project import Project, Workspace
from app.models.util import UtilityGasMedia, UtilityLowTempHeat
from app.services._async_ttl_cache import clear_all_caches
from app.services.util.utility_energy_summary_service import (
    _aggregate_util_subtables,
    summarize_energy_year,
)


@pytest.fixture(autouse=True)
def _clear_async_ttl_cache():
    """F-P1-002 fix: 每次测试清空 TTL 缓存, 防 CONFIG 行跨测试污染.

    `_load_all_factor_rows` 走 5-min TTL 全局缓存, 不清会让
    test_gas_medium_without_config_row_raises 读到上一个测试的 CONFIG 行。
    """
    clear_all_caches()
    yield
    clear_all_caches()

# GB 30251-2024 附录A 表A.1 折标系数 (kg标油/单位)
SEED = [
    # 电双口径 (Case 0 汇总其他类别时需要)
    {"energy_type": "ELECTRICITY", "value_type": "EQUIVALENT",
     "toe_factor": 0.086, "standard_coal_factor": 0.122857},
    {"energy_type": "ELECTRICITY", "value_type": "EQUIVALENT_VALUE",
     "toe_factor": 0.21, "standard_coal_factor": 0.30},
    # 工艺气体 (GAS 行, 与 R1 一致 0.85)
    {"energy_type": "GAS", "toe_factor": 0.85, "standard_coal_factor": 1.214},
    # 序号33 氮气 0.15 kg标油/m³
    {"energy_type": "NITROGEN", "toe_factor": 0.15,
     "standard_coal_factor": 0.214286},
    # 序号31/32 净化 / 非净化压缩空气
    {"energy_type": "INSTRUMENT_AIR", "sub_type": "PURIFIED",
     "toe_factor": 0.038, "standard_coal_factor": 0.054286},
    {"energy_type": "INSTRUMENT_AIR", "sub_type": "NON_PURIFIED",
     "toe_factor": 0.028, "standard_coal_factor": 0.040},
    # 序号34 低温热 0.012 kg标油/MJ
    {"energy_type": "LOW_TEMP_HEAT", "toe_factor": 0.012,
     "standard_coal_factor": 0.017143},
]
TOE_TO_MJ = 41.868


@pytest_asyncio.fixture
async def seeded(db_session: AsyncSession):
    for f in SEED:
        db_session.add(
            ConfigEnergyConversionFactor(source="GB_30251_2024_APPENDIX_A", **f)
        )
    await db_session.commit()
    yield


@pytest_asyncio.fixture
async def project(db_session: AsyncSession):
    workspace_id = uuid.uuid4()
    db_session.add(
        Workspace(workspace_id=workspace_id, workspace_type="FORMAL", name="WS")
    )
    project_id = uuid.uuid4()
    db_session.add(
        Project(
            project_id=project_id, workspace_id=workspace_id,
            project_no=f"P-{project_id.hex[:8]}", project_name="气体算例",
            owner_company="PCS", location="惠州", project_type="PETROLEUM",
            design_phase="EXECUTIVE_DESIGN", unit_system="SI",
            product_category="REFINING",
        )
    )
    await db_session.commit()
    return project_id, workspace_id


def _gas(db, pid, ws, medium: str, nm3: float, tag: str) -> None:
    db.add(
        UtilityGasMedia(
            project_id=pid, workspace_id=ws, equipment_tag=tag,
            gas_medium=medium, consumption_nm3_h=nm3 / 8000.0,
            operating_hours_per_year=8000.0, annual_consumption_nm3=nm3,
            source="MANUAL",
        )
    )


def _low_temp(db, pid, ws, gj: float, tag: str) -> None:
    db.add(
        UtilityLowTempHeat(
            project_id=pid, workspace_id=ws, equipment_tag=tag,
            heat_recovery_gj_h=gj / 8000.0, operating_hours_per_year=8000.0,
            annual_recovered_heat_gj=gj, source="MANUAL",
        )
    )


# ---------------------------------------------------------------------------
# 1. 聚合层接线
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gas_media_aggregated_by_medium(db_session, seeded, project):
    """gas_nm3_yr 不再是 None, 且按 gas_medium 分桶."""
    pid, ws = project
    _gas(db_session, pid, ws, "NITROGEN", 1000.0, "G-1")
    _gas(db_session, pid, ws, "PURIFIED_AIR", 2000.0, "G-2")
    _gas(db_session, pid, ws, "PROCESS_GAS", 500.0, "G-3")
    await db_session.commit()

    agg = await _aggregate_util_subtables(db_session, pid, 2026)
    assert agg.gas_nm3_by_medium == {
        "NITROGEN": 1000.0,
        "PURIFIED_AIR": 2000.0,
        "PROCESS_GAS": 500.0,
    }
    assert agg.gas_nm3_yr == pytest.approx(3500.0)


@pytest.mark.asyncio
async def test_low_temp_heat_aggregated(db_session, seeded, project):
    """low_temp_heat_gj_yr 不再是 None."""
    pid, ws = project
    _low_temp(db_session, pid, ws, 100.0, "LT-1")
    _low_temp(db_session, pid, ws, 50.0, "LT-2")
    await db_session.commit()

    agg = await _aggregate_util_subtables(db_session, pid, 2026)
    assert agg.low_temp_heat_gj_yr == pytest.approx(150.0)


@pytest.mark.asyncio
async def test_no_gas_rows_yields_none_not_zero(db_session, seeded, project):
    """无采集数据时仍返 None (区分「未采集」与「采集=0」, F-P2-002 契约)."""
    pid, _ws = project
    agg = await _aggregate_util_subtables(db_session, pid, 2026)
    assert agg.gas_nm3_yr is None
    assert agg.low_temp_heat_gj_yr is None


# ---------------------------------------------------------------------------
# 2. 折标: 各 gas_medium 走对应 CONFIG 行
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gas_medium_maps_to_correct_config_row(
    db_session, seeded, project
):
    """氮气 0.15 / 净化空气 0.038 — 不得串行 (净化空气用氮气系数 = 高估 4 倍)."""
    pid, ws = project
    _gas(db_session, pid, ws, "NITROGEN", 1000.0, "G-1")
    _gas(db_session, pid, ws, "PURIFIED_AIR", 1000.0, "G-2")
    _gas(db_session, pid, ws, "NON_PURIFIED_AIR", 1000.0, "G-3")
    _gas(db_session, pid, ws, "PLANT_AIR", 1000.0, "G-4")
    _gas(db_session, pid, ws, "PROCESS_GAS", 1000.0, "G-5")
    await db_session.commit()

    s = await summarize_energy_year(
        db=db_session, project_id=pid, workspace_id=ws, business_year=2026,
    )
    # 1000 Nm³ × (0.15 + 0.038 + 0.028 + 0.028 + 0.85) = 1094 kg标油
    assert s.total_toe == pytest.approx(1.094, rel=1e-6)


@pytest.mark.asyncio
async def test_low_temp_heat_toe_and_mj(db_session, seeded, project):
    """100 GJ 低温热 × 0.012 kg标油/MJ = 1200 kg标油 = 1.2 t; MJ = 100000."""
    pid, ws = project
    _low_temp(db_session, pid, ws, 100.0, "LT-1")
    await db_session.commit()

    s = await summarize_energy_year(
        db=db_session, project_id=pid, workspace_id=ws, business_year=2026,
    )
    assert s.low_temp_heat_gj_yr == pytest.approx(100.0)
    assert s.total_toe == pytest.approx(1.2, rel=1e-6)
    assert s.annual_total_energy == pytest.approx(100.0 * 1000.0 * 0.012 * TOE_TO_MJ)


@pytest.mark.asyncio
async def test_all_categories_stay_self_consistent(db_session, seeded, project):
    """6 类全接上后 MJ ↔ toe 仍严格自洽 (iso_self_consistent_pct 成立条件)."""
    pid, ws = project
    _gas(db_session, pid, ws, "NITROGEN", 3000.0, "G-1")
    _low_temp(db_session, pid, ws, 80.0, "LT-1")
    await db_session.commit()

    s = await summarize_energy_year(
        db=db_session, project_id=pid, workspace_id=ws, business_year=2026,
    )
    assert s.annual_total_energy == pytest.approx(
        s.total_toe * 1000.0 * TOE_TO_MJ, rel=1e-9
    )


# ---------------------------------------------------------------------------
# 3. fail-closed: 有数据但 CONFIG 缺行 ⇒ 报错, 不静默兜底
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gas_medium_without_config_row_raises(
    db_session, project
):
    """CONFIG 缺 NITROGEN 行却有氮气数据 ⇒ 500 CONFIG_FACTOR_MISSING.

    不得像 bug-135 那样静默用硬编码兜底。
    """
    pid, ws = project
    _gas(db_session, pid, ws, "NITROGEN", 1000.0, "G-1")
    await db_session.commit()

    from app.core.errors import PcsError

    with pytest.raises(PcsError) as exc:
        await summarize_energy_year(
            db=db_session, project_id=pid, workspace_id=ws, business_year=2026,
        )
    assert exc.value.code == "CONFIG_FACTOR_MISSING"
    assert "NITROGEN" in exc.value.message


# ---------------------------------------------------------------------------
# 4. SPEC V1.4 §4.4 旧口径修订
# ---------------------------------------------------------------------------


def test_category_map_keeps_legacy_none_mapping():
    """legacy util_results 13 类路径的映射**刻意保持** NITROGEN/INSTRUMENT_AIR/
    PLANT_AIR → None, 不改。

    GB 30251-2024 附录A 序号31/32/33 确实给了系数, 「一律不折标」在标准面前是错的
    —— 但本表只有 6 个 fuel_type, OTHER 的种子系数是 1.0000 toe/单位:
    氮气正确值 0.00015 toe/Nm³, 映射到 OTHER 会**高估约 6700 倍**, 比不计更糟。
    本表结构上无法表达「按介质取不同系数」。

    现行口径走 P7-6B 收尾新增的 5 表路径 (utility_gas_media + ConfigEnergy-
    ConversionFactor), 由本文件其余测试覆盖。此断言锁住「不要图省事改成 OTHER」。
    """
    from app.services.util.category_map import TOE_FUEL_TYPE_BY_CATEGORY

    assert TOE_FUEL_TYPE_BY_CATEGORY["NITROGEN"] is None
    assert TOE_FUEL_TYPE_BY_CATEGORY["INSTRUMENT_AIR"] is None
    assert TOE_FUEL_TYPE_BY_CATEGORY["PLANT_AIR"] is None
