"""S1-5 UTIL V1.3 基线测试（P7-Sprint 1 T3）。

覆盖：
1. UtilResults ORM — jsonb_deprecated marker defaults False（Sprint 1 JSONB 权威）
2. summary_service — 13 类公用工程聚合（per SPEC V1.4 §4.4）
3. 折标煤 — 13→6 fuel_type 映射（ELECTRICITY/STEAM_*/FUEL_GAS 进 TOE；其他类不进）
4. STEAM 4 子类（HP/MP/LP/CONDENSATE）共享 STEAM TOE 系数

设计：
- 用 conftest.py:118 db_session (AsyncSession, SQLite in-memory) 驱动
- ToeConversionFactor 用 ToeConversionService.seed_defaults (per task test_toe_conversion_service.py 模式)
- 13 类公用工程清单 per SPEC V1.4 §4.4 + plan brief Step 3
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.util import UtilResults
from app.services.toe_conversion_service import ToeConversionService
from app.services.util.category_map import UtilityCategory, utility_categories
from app.services.util.summary_service import summarize


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_toe(db_session: AsyncSession) -> AsyncIterator[None]:
    """幂等 seed ToeConversionFactor 6 defaults（GAS/DIESEL/COAL/STEAM/ELECTRICITY/OTHER）。"""
    await ToeConversionService.seed_defaults(db_session)
    yield


@pytest_asyncio.fixture
async def util_result(db_session: AsyncSession) -> AsyncIterator[UtilResults]:
    """最小 UtilResults：project_id + workspace_id + consumption_json (13 categories 全部填值)。"""
    project_id = uuid.uuid4()
    workspace_id = uuid.uuid4()
    r = UtilResults(
        project_id=project_id,
        workspace_id=workspace_id,
        consumption_json={
            "ELECTRICITY": 10000.0,      # kWh
            "STEAM_HP": 50.0,            # t/h
            "STEAM_MP": 30.0,
            "STEAM_LP": 20.0,
            "CONDENSATE": 90.0,
            "COOLING_WATER": 500.0,      # t/h
            "CHILLED_WATER": 200.0,
            "MAKEUP_WATER": 50.0,
            "FUEL_GAS": 10000.0,         # Nm3/h
            "NITROGEN": 10.0,
            "INSTRUMENT_AIR": 20.0,
            "PLANT_AIR": 30.0,
        },
    )
    db_session.add(r)
    await db_session.commit()
    await db_session.refresh(r)
    yield r


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_utility_categories_count_is_13():
    """SPEC V1.4 §4.4: 13 类公用工程（含总计）。"""
    cats = utility_categories()
    assert len(cats) == 13
    assert UtilityCategory.ELECTRICITY in cats
    assert UtilityCategory.STEAM_HP in cats
    assert UtilityCategory.PLANT_AIR in cats


@pytest.mark.asyncio
async def test_util_results_jsonb_deprecated_defaults_false(db_session):
    """Sprint 1 阶段 JSONB 仍权威；Sprint 2 起 jsonb_deprecated=True。"""
    r = UtilResults(
        project_id=uuid.uuid4(),
        workspace_id=uuid.uuid4(),
        consumption_json={"ELECTRICITY": 100.0},
    )
    db_session.add(r)
    await db_session.commit()
    await db_session.refresh(r)
    assert r.jsonb_deprecated is False


@pytest.mark.asyncio
async def test_summarize_aggregates_13_categories(
    db_session, seeded_toe, util_result
):
    """summary_service 聚合 13 类 + 折标煤（ELECTRICITY/STEAM_*/FUEL_GAS 进 TOE）。"""
    summary = await summarize(util_result, db=db_session, year=2026)

    # 13 keys 全部返回（value 是原始 consumption 或 0）
    assert set(summary["by_category"].keys()) == set(c.value for c in utility_categories())
    assert summary["by_category"]["ELECTRICITY"] == 10000.0
    assert summary["by_category"]["STEAM_HP"] == 50.0
    assert summary["by_category"]["FUEL_GAS"] == 10000.0

    # 折标煤（tonne oil equivalent, toe_total）
    # ELECTRICITY 10000 kWh × 0.1229 toe/kWh = 1229 toe
    # STEAM 4 subcategories aggregated 50+30+20+90 = 190 × 0.1429 = 27.151 toe
    # FUEL_GAS 10000 Nm3 × 1.0000 toe/(? — 实际是质量基础但 seed 用 1.0) = 10000 toe
    # TOTAL ≈ 11256 toe
    assert "toe_total" in summary
    assert summary["toe_total"] > 0  # 数值验证看下面 test_steam_subcategories

    # 标准煤（standard coal factor total）
    assert "standard_coal_total" in summary
    assert summary["standard_coal_total"] > 0


@pytest.mark.asyncio
async def test_summarize_steam_subcategories_share_steam_toe(
    db_session, seeded_toe, util_result
):
    """STEAM_HP/MP/LP/CONDENSATE 4 子类均使用 STEAM TOE 系数。"""
    # 单独提取 STEAM 子类总和 toe
    # STEAM 合计 = 50+30+20+90 = 190 × 0.1429 toe/(unit) = 27.151 toe
    summary = await summarize(util_result, db=db_session, year=2026)

    # 由 ELECTRICITY toe + STEAM 4 子 toe + FUEL_GAS toe 组成
    electricity_toe = 10000.0 * 0.1229
    steam_total = 50.0 + 30.0 + 20.0 + 90.0
    steam_toe = steam_total * 0.1429
    fuel_gas_toe = 10000.0 * 1.0000
    expected_toe = electricity_toe + steam_toe + fuel_gas_toe

    assert abs(summary["toe_total"] - expected_toe) < 1e-6


@pytest.mark.asyncio
async def test_summarize_non_energy_categories_excluded_from_toe(
    db_session, seeded_toe, util_result
):
    """7 类非能源（COOLING_WATER/CHILLED_WATER/MAKEUP_WATER/NITROGEN/INSTRUMENT_AIR/PLANT_AIR + 总计占位）
    不参与 TOE 折算（无 ToeConversionFactor 映射）。"""
    summary = await summarize(util_result, db=db_session, year=2026)

    # 仅 ELECTRICITY + STEAM(×4) + FUEL_GAS = 6 类进 TOE
    # 6 toe_factor × consumption 加总 = summary["toe_total"]
    # 验证 toe_total 不包含 COOLING_WATER (500) 等无映射值
    # 通过反向：toe_total 应等于上面 expected_toe，不应包含 500 × 任何
    # 直接算 toe_total = 10000×0.1229 + 190×0.1429 + 10000×1.0 = 1229 + 27.151 + 10000 = 11256.151
    expected = 10000.0 * 0.1229 + (50 + 30 + 20 + 90) * 0.1429 + 10000.0 * 1.0000
    assert abs(summary["toe_total"] - expected) < 1e-6
