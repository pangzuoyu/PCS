"""ToeConversionService — 折标煤系数组 CRUD（Task 1.10.1 / V1.4 P2-OPEN-005）。

配套 auxiliary_consumption + utility_energy_summary。fuel_type 枚举：
GAS / DIESEL / COAL / STEAM / ELECTRICITY / OTHER。effective_year +
effective_from / effective_to 控制生效区间。
"""
from __future__ import annotations

import datetime as dt

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config_domain import ToeConversionFactor
from app.services.exceptions import PcsError

VALID_FUEL_TYPES = {"GAS", "DIESEL", "COAL", "STEAM", "ELECTRICITY", "OTHER"}


class ToeConversionService:
    @classmethod
    async def seed_defaults(cls, session: AsyncSession) -> int:
        """幂等 seed 6 个 fuel_type 默认值（与 Alembic 迁移同步）。"""
        result = await session.execute(select(ToeConversionFactor))
        if result.first():
            return 0
        defaults = [
            ("GAS", 1.0000, 1.2143),
            ("DIESEL", 1.4571, 1.7714),
            ("COAL", 0.7143, 0.8667),
            ("STEAM", 0.1429, 0.1714),
            ("ELECTRICITY", 0.1229, 0.1486),
            ("OTHER", 1.0000, 1.2143),
        ]
        for fuel, toe, coal in defaults:
            session.add(
                ToeConversionFactor(
                    fuel_type=fuel,
                    toe_conversion_factor=toe,
                    standard_coal_factor=coal,
                    effective_year=2026,
                    effective_from=dt.date(2026, 1, 1),
                    source="GB 2589-2020 / 综合能耗计算通则",
                )
            )
        await session.commit()
        return len(defaults)

    @classmethod
    async def query_by_fuel_year(
        cls, session: AsyncSession, fuel_type: str, year: int
    ) -> ToeConversionFactor:
        """按 fuel_type + year 查询；year 超出时返回最近的已知年。"""
        if fuel_type not in VALID_FUEL_TYPES:
            raise PcsError(
                f"未知 fuel_type: {fuel_type}",
                code="TOE_INVALID_FUEL",
                status=422,
            )
        stmt = (
            select(ToeConversionFactor)
            .where(ToeConversionFactor.fuel_type == fuel_type)
            .where(ToeConversionFactor.effective_year <= year)
            .order_by(ToeConversionFactor.effective_year.desc())
            .limit(1)
        )
        result = (await session.execute(stmt)).scalar_one_or_none()
        if not result:
            raise PcsError(
                f"无 {fuel_type} 折标煤系数",
                code="TOE_NOT_FOUND",
                status=404,
            )
        return result

    @classmethod
    async def create(
        cls,
        session: AsyncSession,
        *,
        fuel_type: str,
        toe_conversion_factor: float,
        standard_coal_factor: float,
        effective_year: int,
    ) -> ToeConversionFactor:
        """新建 TOE 折算系数（按 fuel_type + effective_year 复合唯一）。

        - fuel_type 必须在 VALID_FUEL_TYPES 白名单内（否则 TOE_INVALID_FUEL 422）
        - 查重（fuel_type, effective_year），命中 → TOE_DUPLICATE（409）
        - effective_from 默认设为 effective_year-01-01（即该年度起点）
        - 写入由本函数负责（session.commit()）
        """
        if fuel_type not in VALID_FUEL_TYPES:
            raise PcsError(
                f"未知 fuel_type: {fuel_type}",
                code="TOE_INVALID_FUEL",
                status=422,
            )
        existing = (
            await session.execute(
                select(ToeConversionFactor)
                .where(ToeConversionFactor.fuel_type == fuel_type)
                .where(ToeConversionFactor.effective_year == effective_year)
            )
        ).scalar_one_or_none()
        if existing:
            raise PcsError(
                f"{fuel_type} {effective_year} 年系数已存在",
                code="TOE_DUPLICATE",
                status=409,
            )
        new_row = ToeConversionFactor(
            fuel_type=fuel_type,
            toe_conversion_factor=toe_conversion_factor,
            standard_coal_factor=standard_coal_factor,
            effective_year=effective_year,
            effective_from=dt.date(effective_year, 1, 1),
        )
        session.add(new_row)
        await session.commit()
        return new_row