"""S1-5b SourceModule → 13 类公用工程 consumption_json 聚合。

Per brief Step 4 "consumes PUMP / HEAT / COOL_TOWER / OPEN_CHANNEL results"：
source_aggregator 读取 source module ORM 结果，转换为 flat
{UtilityCategory: float_quantity} consumption_json，供 UtilResults 写入。

聚合规则（per SPEC V1.4 §4.4）：

| UtilityCategory     | SourceModule      | Source Field(s)                          | Unit  | 年化约定       |
|---------------------|-------------------|------------------------------------------|-------|----------------|
| ELECTRICITY         | PUMP              | power_consumption_json.selected_motor_power_kw | kW → kWh | × 8000 hr/yr |
| STEAM_HP/MP/LP      | HEAT              | output_json.steam_pressure_mpa + duty_legacy    | t/h   | × 8000 hr/yr |
| CONDENSATE          | HEAT              | output_json.return_condensate_t                | t/h   | × 8000 hr/yr |
| COOLING_WATER       | COOL_TOWER        | water_flow (Float, m³/h)                  | t/h   | × 8000 hr/yr |
| MAKEUP_WATER        | OPEN_CHANNEL      | flow_rate (Float, m³/s → t/h)             | t/h   | × 8000 hr/yr |
| (CHILLED_WATER / FUEL_GAS / NITROGEN / INSTRUMENT_AIR / PLANT_AIR) — manual entry, 0.0 |

年化约定 8000 hr/yr 是 PCS 工艺工程师典型假设（与 SPEC §4.4 一致）。
后续工艺室提供 operating_hours_per_year 字段后可改 per-record 动态化。

设计要点：
- 每个 SourceModule 一个 _aggregate_<module>() helper（私有）
- 总入口 aggregate_consumption(db, project_id, modules) → dict
- 缺数据模块返回 0；不抛异常（partial aggregation）
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.models.calc import (
    CoolingTowerResult,
    HeatResult,
    OpenChannelResult,
    PumpResult,
)
from app.services.util.category_map import UtilityCategory

# PCS 工艺工程师典型年操作小时数；后续可改 per-record
_DEFAULT_OPERATING_HOURS_PER_YEAR = 8000


async def _aggregate_pump(
    project_id: UUID, db: AsyncSession
) -> dict[str, float]:
    """PUMP 结果 → ELECTRICITY kWh 聚合。

    每个 PUMP CHECKED 结果的 power_consumption_json 含 selected_motor_power_kw；
    annual_kwh = selected_motor_power_kw × 8000 hr/yr。
    """
    stmt = select(PumpResult.power_consumption_json).where(
        PumpResult.project_id == project_id,
        PumpResult.sign_status == "CHECKED",
    )
    rows = (await db.execute(stmt)).scalars().all()
    total_kwh = 0.0
    for pj in rows:
        if isinstance(pj, dict):
            motor_kw = float(pj.get("selected_motor_power_kw", 0.0))
            total_kwh += motor_kw * _DEFAULT_OPERATING_HOURS_PER_YEAR
    return {UtilityCategory.ELECTRICITY.value: total_kwh}


async def _aggregate_heat(
    project_id: UUID, db: AsyncSession
) -> dict[str, float]:
    """HEAT 结果 → STEAM_HP/MP/LP/CONDENSATE t/h 聚合。

    每个 HEAT CHECKED 结果的 output_json 含 steam_pressure_mpa + steam_consumption_t；
    按压力分级：≥4.0 → STEAM_HP; 1.0-4.0 → STEAM_MP; 0.1-1.0 → STEAM_LP; < 0.1 → CONDENSATE
    annual_t = consumption_t × 8000 hr/yr
    """
    stmt = select(
        HeatResult.output_json,
        HeatResult.duty_legacy,
    ).where(
        HeatResult.project_id == project_id,
        HeatResult.sign_status == "CHECKED",
    )
    rows = (await db.execute(stmt)).all()
    totals: dict[str, float] = {
        UtilityCategory.STEAM_HP.value: 0.0,
        UtilityCategory.STEAM_MP.value: 0.0,
        UtilityCategory.STEAM_LP.value: 0.0,
        UtilityCategory.CONDENSATE.value: 0.0,
    }
    for oj, duty_legacy in rows:
        if not isinstance(oj, dict):
            continue
        pressure = float(oj.get("steam_pressure_mpa", 0.0))
        # consumption_t 字段：output_json.steam_consumption_t 或 fallback duty_legacy
        consumption_per_hr = float(oj.get("steam_consumption_t", duty_legacy or 0.0))
        annual_t = consumption_per_hr * _DEFAULT_OPERATING_HOURS_PER_YEAR
        if pressure >= 4.0:
            totals[UtilityCategory.STEAM_HP.value] += annual_t
        elif pressure >= 1.0:
            totals[UtilityCategory.STEAM_MP.value] += annual_t
        elif pressure >= 0.1:
            totals[UtilityCategory.STEAM_LP.value] += annual_t
        else:
            totals[UtilityCategory.CONDENSATE.value] += annual_t
    return totals


async def _aggregate_cool_tower(
    project_id: UUID, db: AsyncSession
) -> dict[str, float]:
    """COOL_TOWER 结果 → COOLING_WATER t 聚合（年化）。

    water_flow 是 m³/h（瞬时流量）；annual_t = water_flow × 8000 hr/yr。
    """
    stmt = select(CoolingTowerResult.water_flow).where(
        CoolingTowerResult.project_id == project_id,
        CoolingTowerResult.sign_status == "CHECKED",
    )
    rows = (await db.execute(stmt)).scalars().all()
    total_t_per_hr = sum(float(wf or 0.0) for wf in rows)
    annual_t = total_t_per_hr * _DEFAULT_OPERATING_HOURS_PER_YEAR
    return {UtilityCategory.COOLING_WATER.value: annual_t}


async def _aggregate_open_channel(
    project_id: UUID, db: AsyncSession
) -> dict[str, float]:
    """OPEN_CHANNEL 结果 → MAKEUP_WATER t 聚合（年化）。

    flow_rate 是 m³/s；转换为 t/h（≈ m³/h × 1 density）再年化。
    annual_t = flow_rate × 3600 s/h × 8000 hr/yr。
    """
    stmt = select(OpenChannelResult.flow_rate).where(
        OpenChannelResult.project_id == project_id,
        OpenChannelResult.sign_status == "CHECKED",
    )
    rows = (await db.execute(stmt)).scalars().all()
    total_m3_per_s = sum(float(fr or 0.0) for fr in rows)
    # m³/s → t/h: × 3600 s/h (density = 1)
    total_t_per_hr = total_m3_per_s * 3600.0
    annual_t = total_t_per_hr * _DEFAULT_OPERATING_HOURS_PER_YEAR
    return {UtilityCategory.MAKEUP_WATER.value: annual_t}


_AGGREGATORS = {
    "PUMP": _aggregate_pump,
    "HEAT": _aggregate_heat,
    "COOL_TOWER": _aggregate_cool_tower,
    "OPEN_CHANNEL": _aggregate_open_channel,
}


async def aggregate_consumption(
    project_id: UUID,
    db: AsyncSession,
    *,
    modules: list[str] | None = None,
) -> dict[str, float]:
    """总入口：聚合指定 SourceModule → 13 类公用工程 flat {category: float}。

    Args:
        project_id: 项目 UUID
        db: AsyncSession
        modules: 要聚合的 SourceModule 列表；默认全部 4 个

    Returns:
        flat {UtilityCategory.value: float_quantity} 13 类（缺数据 = 0）
    """
    if modules is None:
        modules = list(_AGGREGATORS.keys())

    result: dict[str, float] = {}
    for module in modules:
        aggregator = _AGGREGATORS.get(module)
        if aggregator is None:
            # F-P1-003 fix: 不再 silent drop — 记 WARNING 让 feature-probing
            # / 配置错误可见（Sentry / log aggregator 可捕获）
            logger.warning(
                "source_aggregator: unknown SourceModule=%s skipped "
                "(available=%s)",
                module, sorted(_AGGREGATORS.keys()),
            )
            continue
        module_result = await aggregator(project_id, db)
        result.update(module_result)
    return result
