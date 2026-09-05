"""CATEGORY_3 默认系数表 seed 测试（Task 1.8.3 六表 + Task 1.9.4 炼油三表）。

幂等 seed：按 name 增量写入缺失表；二次调用 no-op。
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import delete, select

from app.db.session import dispose_engines_async, get_async_session_factory
from app.models.config_domain import CoefficientTable
from app.services.coefficient_service import CoefficientService

EXPECTED_TABLES = [
    "souders_brown_k",
    "recommended_velocity",
    "pump_power_safety_factor",
    "pipe_roughness_default",
    "heat_exchanger_weight_factor",
    "fitting_resistance_mapping",
]

V12_PETROLEUM_TABLES = [
    "petroleum_correlations",
    "property_estimation_params",
    "pseudo_component_cutting",
]


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine() -> AsyncIterator[None]:
    """每个用例 reset 全局 async engine（绑定当前 event loop）。

    `get_async_session_factory()` 是模块级单例，跨 event loop 复用会触发
    "Event loop is closed"。每次用例前 dispose 一次即可。
    """
    await dispose_engines_async()
    yield
    await dispose_engines_async()


@pytest_asyncio.fixture
async def clean_seed_tables() -> AsyncIterator[None]:
    """每次用例前清掉 SEED-V1.0 行，保证测试可重复。"""
    factory = get_async_session_factory()
    async with factory() as session:
        await session.execute(
            delete(CoefficientTable).where(CoefficientTable.version == "SEED-V1.0")
        )
        await session.commit()
    yield


@pytest.mark.asyncio
async def test_seed_default_tables_creates_six(clean_seed_tables):
    factory = get_async_session_factory()
    async with factory() as session:
        created = await CoefficientService.seed_default_tables(session)
    assert len(created) == len(EXPECTED_TABLES) + len(V12_PETROLEUM_TABLES)
    for name in EXPECTED_TABLES:
        assert name in created


@pytest.mark.asyncio
async def test_seed_default_tables_idempotent(clean_seed_tables):
    factory = get_async_session_factory()
    async with factory() as session:
        await CoefficientService.seed_default_tables(session)
        second = await CoefficientService.seed_default_tables(session)
    assert second == []  # 第二次幂等无新增


@pytest.mark.asyncio
@pytest.mark.parametrize("table_name", EXPECTED_TABLES)
async def test_seed_table_queryable(clean_seed_tables, table_name):
    factory = get_async_session_factory()
    async with factory() as session:
        await CoefficientService.seed_default_tables(session)
        result = await session.execute(
            select(CoefficientTable).where(
                CoefficientTable.name == table_name,
                CoefficientTable.version == "SEED-V1.0",
            )
        )
        row = result.scalar_one()
    assert row.applicable_range
    assert len(row.data_json["rows"]) >= 1


@pytest.mark.asyncio
async def test_seed_adds_v12_petroleum_tables(clean_seed_tables):
    factory = get_async_session_factory()
    async with factory() as session:
        await CoefficientService.seed_default_tables(session)
        names = {n for (n,) in await session.execute(select(CoefficientTable.name))}
    assert "petroleum_correlations" in names
    assert "property_estimation_params" in names
    assert "pseudo_component_cutting" in names