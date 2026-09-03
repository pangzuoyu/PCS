"""ToeConversionService 折标煤系数组测试（Task 1.10.1 / V1.4 P2-OPEN-005）。

测试覆盖：
- seed_defaults 幂等性（6 个 fuel_type）
- query_by_fuel_year 按年查询
- 超出年份返回最近已知年
- 唯一约束（fuel_type + effective_year）
"""
from __future__ import annotations

from collections.abc import AsyncIterator

import pytest
import pytest_asyncio
from sqlalchemy import distinct, select

from app.db.session import dispose_engines_async, get_async_session_factory
from app.models.config_domain import ToeConversionFactor
from app.services.exceptions import PcsError
from app.services.toe_conversion_service import ToeConversionService


@pytest_asyncio.fixture(autouse=True)
async def _reset_async_engine() -> AsyncIterator[None]:
    """每个用例 reset 全局 async engine（绑定当前 event loop）。

    ``get_async_session_factory()`` 是模块级单例，跨 event loop 复用会触发
    "Event loop is closed"。每次用例前 dispose 一次即可。
    """
    await dispose_engines_async()
    yield
    await dispose_engines_async()


@pytest_asyncio.fixture(autouse=True)
async def seed_toe() -> AsyncIterator[None]:
    """每个用例前幂等 seed 6 个 fuel_type 默认值（与 Alembic 迁移同步）。"""
    factory = get_async_session_factory()
    async with factory() as session:
        await ToeConversionService.seed_defaults(session)
    yield


@pytest.mark.asyncio
async def test_seed_defaults_creates_six_fuels():
    """默认 seed 6 个 fuel_type（GAS/DIESEL/COAL/STEAM/ELECTRICITY/OTHER）"""
    factory = get_async_session_factory()
    async with factory() as session:
        await ToeConversionService.seed_defaults(session)
        result = await session.execute(select(distinct(ToeConversionFactor.fuel_type)))
        fuels = result.scalars().all()
    assert len(fuels) == 6


@pytest.mark.asyncio
async def test_query_by_fuel_year_returns_latest():
    """按 fuel_type + year 查询返回该年份生效值"""
    factory = get_async_session_factory()
    async with factory() as session:
        result = await ToeConversionService.query_by_fuel_year(session, "GAS", 2026)
    assert result.toe_conversion_factor > 0
    assert result.standard_coal_factor > 0


@pytest.mark.asyncio
async def test_query_missing_year_returns_latest_known():
    """未来年份无 seed 时返回已知的最近一年"""
    factory = get_async_session_factory()
    async with factory() as session:
        result = await ToeConversionService.query_by_fuel_year(session, "GAS", 2099)
    assert result.effective_year <= 2026


@pytest.mark.asyncio
async def test_unique_constraint_on_fuel_year():
    """同一 fuel_type + effective_year 唯一"""
    factory = get_async_session_factory()
    async with factory() as session:
        with pytest.raises(PcsError) as exc:
            await ToeConversionService.create(
                session,
                fuel_type="GAS",
                toe_conversion_factor=1.0,
                standard_coal_factor=1.5,
                effective_year=2026,
            )
    assert exc.value.code == "TOE_DUPLICATE"