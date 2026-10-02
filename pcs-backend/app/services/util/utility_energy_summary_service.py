"""P7 Sprint 2 T5: 综合能耗汇总 service (utility_energy_summary).

按 P7-OPEN-009 §1 #4 + §6.3 + D1 裁决 1A 落地:

- 聚合 T1 utility_power_items + T2 utility_fuel_gas + T3 utility_heat_exchange
  + ConfigEnergyConversionFactor 折标系数 (5-min TTL 缓存 via
  ``_compound_config_cache``) 计算:
  - 6 类能源 annual 消耗 (electricity_kwh_yr / fuel_gas_nm3_yr / steam_t_yr /
    water_t_yr / gas_nm3_yr / low_temp_heat_gj_yr)
  - 年度总能耗 annual_total_energy (MJ/yr; canonical unit)
  - 折标油总量 total_toe (toe)
  - 折标煤总量 total_standard_coal_kg (kg 标煤)
  - 聚合折标系数 toe_conversion_factor / standard_coal_factor (kg 标 / MJ)
- 容差校验: tolerance_pct = |computed - xls_reference| / xls_reference;
  tolerance_status = OK ⇔ tolerance_pct ≤ 2% per P7-OPEN-009 §6.

设计要点:

- 聚合逻辑在 service 层 (非 DB view / trigger), 便于单元测试 mock.
- 5-min TTL 缓存 ConfigEnergyConversionFactor (仿 P6-5+ ``_compound_config_cache``).
- 容差 NA 状态: tolerance_status='NA' 当 source='CALCULATION' 单独存在
  无 XLS_REFERENCE 同年记录.
- idempotent: 同 (project_id, business_year, source) 已存在则覆盖更新.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.config import ConfigEnergyConversionFactor
from app.models.util import (
    UtilityEnergySummary,
    UtilityFuelGas,
    UtilityHeatExchange,
    UtilityPowerItem,
)
# F-P1-002 fix: 5-min TTL 缓存 (仿 _compound_config_cache 异步版)
from app.services._async_ttl_cache import clear_all_caches, get_or_reload_async  # noqa: E402

# 综合能耗容差上限 (per P7-OPEN-009 §6 验收标准: ≤ 2%)
DEFAULT_TOLERANCE_PCT = 2.0


# 6 类能源年度消耗聚合结果 (service 内部分型, 不落 DB)
@dataclass(frozen=True)
class EnergyAggregation:
    """6 类能源年度消耗 + R1 分类聚合 service 输出中间值.

    R1 修订 (PCS-SIGN-F-P0-001-2026-10-08-R1):
    - steam_t_by_pressure_level: 9 档蒸汽 (GE_7_0_MPA / ... / LT_0_3_MPA)
    - fuel_gas_by_source: 3 类气源 (OILFIELD_GAS / GASFIELD_GAS / REFINERY_FUEL_GAS)
    - water_by_type: 9 类水 (FRESH_WATER / ... / 120C_CONDENSATE_REUSABLE)
    - steam_t_yr / fuel_gas_nm3_yr / water_t_yr: 保留向后兼容 (R0 单值聚合);
      新计算用 *_by_* dict 字段.
    """

    electricity_kwh_yr: float = 0.0
    fuel_gas_nm3_yr: float = 0.0
    steam_t_yr: float = 0.0
    water_t_yr: float = 0.0
    gas_nm3_yr: float = 0.0
    low_temp_heat_gj_yr: float = 0.0
    # R1 §7 分类聚合字段 (按 GB 30251-2024 附录A 9 档 / 3 类 / 9 类)
    steam_t_by_pressure_level: dict[str, float] | None = None
    fuel_gas_by_source: dict[str, float] | None = None
    water_by_type: dict[str, float] | None = None


def _build_r1_classification(agg: EnergyAggregation) -> dict | None:
    """Build R1 §7 分类聚合 dict (3 类) for JSONB 持久化.

    Returns:
        {
            "steam_by_pressure_level": {"GE_7_0_MPA": 8400.0, ...}  # 9 档
            "fuel_gas_by_source": {"OILFIELD_GAS": 1600000.0, ...}  # 3 类
            "water_by_type": {"FRESH_WATER": 100.0, ...}  # 9 类
        }
        None 当全部 *_by_* 都为空 (R0 单值聚合路径).

    字段全空时返回 None 而非空 dict, 避免存储冗余 (P7-6B 冷却水子表落地后
    water_by_type 自动填充; NULL 即未启用 R1 分类聚合, 简化下游查询).
    """
    parts: dict[str, dict[str, float]] = {}
    if agg.steam_t_by_pressure_level:
        parts["steam_by_pressure_level"] = dict(agg.steam_t_by_pressure_level)
    if agg.fuel_gas_by_source:
        parts["fuel_gas_by_source"] = dict(agg.fuel_gas_by_source)
    if agg.water_by_type:
        parts["water_by_type"] = dict(agg.water_by_type)
    return parts or None


async def _aggregate_util_subtables(
    db: AsyncSession,
    project_id: str,
    business_year: int,
    *,
    electricity_value_type: str = "EQUIVALENT",
) -> EnergyAggregation:
    """聚合 T1+T2+T3 子表 (per project_id) → 6 类能源年度消耗.

    R1 修订: electricity_value_type 选择当量值 (默认) / 等价值;
    fuel_gas 按 gas_source 3 类; steam 按 pressure_level 9 档;
    water 按 water_type 9 类 聚合 (R1 §7).

    business_year 当前未用于过滤 (T1/T2/T3 表无 year 字段; 数据为 project
    snapshot); 预留接口便于 T7+ 年度 business_date 字段加规则扩展。

    cooling_water / gas / low_temp_heat 子表待 P7-6B 落地, 当前返回 0.0。
    """
    # T1 utility_power_items → electricity_kwh_yr
    stmt_power = (
        select(func.coalesce(func.sum(UtilityPowerItem.annual_consumption_kwh), 0.0))
        .where(UtilityPowerItem.project_id == project_id)
    )
    electricity_kwh_yr = float((await db.execute(stmt_power)).scalar() or 0.0)

    # T2 utility_fuel_gas → fuel_gas_nm3_yr (R1 §7.3: 按 gas_source 3 类聚合)
    stmt_fuel_total = (
        select(func.coalesce(func.sum(UtilityFuelGas.annual_consumption_nm3), 0.0))
        .where(UtilityFuelGas.project_id == project_id)
    )
    fuel_gas_nm3_yr = float((await db.execute(stmt_fuel_total)).scalar() or 0.0)

    # R1 §7.3: 按 gas_source 3 类分别聚合 (OILFIELD_GAS/GASFIELD_GAS/REFINERY_FUEL_GAS)
    stmt_fuel_by_source = (
        select(
            UtilityFuelGas.gas_source,
            func.coalesce(func.sum(UtilityFuelGas.annual_consumption_nm3), 0.0),
        )
        .where(UtilityFuelGas.project_id == project_id)
        .where(UtilityFuelGas.gas_source.is_not(None))
        .group_by(UtilityFuelGas.gas_source)
    )
    fuel_rows = (await db.execute(stmt_fuel_by_source)).all()
    fuel_gas_by_source: dict[str, float] = {
        row.gas_source: float(row[1]) for row in fuel_rows if row.gas_source
    }

    # T3 utility_heat_exchange → steam_t_yr (R1 §7.1: 按 pressure_level 9 档聚合)
    # 注: utility_heat_exchange R1 加 medium_type (含 STEAM + 9 类水). 仅
    # 注: medium_type='STEAM' 或 NULL 的行算蒸汽; 其余归 water_by_type 桶.
    stmt_steam_total = (
        select(
            func.coalesce(func.sum(UtilityHeatExchange.annual_consumption_t), 0.0)
        )
        .where(UtilityHeatExchange.project_id == project_id)
        .where(
            (UtilityHeatExchange.medium_type == "STEAM")
            | (UtilityHeatExchange.medium_type.is_(None))
        )
    )
    steam_t_yr = float((await db.execute(stmt_steam_total)).scalar() or 0.0)

    # R1 §7.1: 按 pressure_level 9 档分别聚合 (GE_7_0_MPA / ... / LT_0_3_MPA)
    stmt_steam_by_pressure = (
        select(
            UtilityHeatExchange.pressure_level,
            func.coalesce(func.sum(UtilityHeatExchange.annual_consumption_t), 0.0),
        )
        .where(UtilityHeatExchange.project_id == project_id)
        .where(UtilityHeatExchange.pressure_level.is_not(None))
        .group_by(UtilityHeatExchange.pressure_level)
    )
    steam_rows = (await db.execute(stmt_steam_by_pressure)).all()
    steam_t_by_pressure_level: dict[str, float] = {
        row.pressure_level: float(row[1]) for row in steam_rows if row.pressure_level
    }

    # R1 §7.2 (P7-6B): 水消耗按 water_type 9 类聚合 (medium_type != 'STEAM')
    # 注: utility_heat_exchange.medium_type 包含 STEAM + 9 类水 (FRESH_WATER / ...
    # 注: 120C_CONDENSATE_REUSABLE). 蒸汽记录 medium_type='STEAM' + pressure_level=...
    # 注: 水记录 medium_type='XXX_WATER' (or LP/HP_DEAERATED_WATER / CONDENSATE_*)
    # 注: 这里聚合 medium_type != 'STEAM' 的年消耗 → water_by_type dict.
    # 注: water_t_yr = 蒸汽消耗 + 水消耗 (R0 单值兼容, 6 类能源 row 31)
    stmt_water_by_type = (
        select(
            UtilityHeatExchange.medium_type,
            func.coalesce(func.sum(UtilityHeatExchange.annual_consumption_t), 0.0),
        )
        .where(UtilityHeatExchange.project_id == project_id)
        .where(UtilityHeatExchange.medium_type.is_not(None))
        .where(UtilityHeatExchange.medium_type != "STEAM")
        .group_by(UtilityHeatExchange.medium_type)
    )
    water_rows = (await db.execute(stmt_water_by_type)).all()
    water_by_type: dict[str, float] = {
        row.medium_type: float(row[1]) for row in water_rows if row.medium_type
    }

    # R0 兼容: water_t_yr = 水消耗 (medium_type != 'STEAM' 行的 annual_consumption_t)
    water_t_yr = sum(water_by_type.values()) if water_by_type else 0.0

    return EnergyAggregation(
        electricity_kwh_yr=electricity_kwh_yr,
        fuel_gas_nm3_yr=fuel_gas_nm3_yr,
        steam_t_yr=steam_t_yr,
        water_t_yr=water_t_yr,  # R1 §7.2 (P7-6B) 水消耗年累积 (medium_type != STEAM)
        gas_nm3_yr=0.0,
        low_temp_heat_gj_yr=0.0,
        steam_t_by_pressure_level=steam_t_by_pressure_level,
        fuel_gas_by_source=fuel_gas_by_source,
        water_by_type=water_by_type or None,  # R1 §7.2 (P7-6B) 水按 medium_type 9 类聚合
    )


async def _get_energy_conversion_factors(
    db: AsyncSession,
    *,
    electricity_value_type: str = "EQUIVALENT",
) -> dict[str, tuple[float, float]]:
    """读 ConfigEnergyConversionFactor R1 26 行 → 按 energy_type 默认分类返回 (toe, coal).

    R1 §5: ELECTRICITY 按 value_type 精确查表 (避免 last-wins 误用 EQUIVALENT_VALUE).
    其他能源: dict last-wins (后续 sprint 精确分类聚合).

    R1 修订 (PCS-SIGN-F-P0-001-2026-10-08-R1): 表按分类拆为多行 (电 2 + 燃料气 3 +
    蒸汽 9 + 水 9 + 氮气 1 + 仪表空气 2 = 26 行). 默认分类:
    - ELECTRICITY: value_type=electricity_value_type (默认 EQUIVALENT 当量值 0.086)
    - FUEL_GAS: sub_type=GASFIELD_GAS (气田气 0.85)
    - STEAM: pressure_level=0_8_TO_1_2_MPA (1.0 MPa MP 76)
    - WATER: water_type=CIRCULATING_WATER (循环水 0.06)
    - NITROGEN: 单行
    - INSTRUMENT_AIR: sub_type=PURIFIED (净化 0.038)

    Returns:
        dict[energy_type, (toe_factor, standard_coal_factor)] 单值 (last-wins)

    注: 分类精确查表用 _get_factors_by_classification() 替代.
    """
    return await _get_factors_default(db, electricity_value_type=electricity_value_type)


async def _get_factors_by_classification(
    db: AsyncSession,
) -> dict[str, dict[str, tuple[float, float]]]:
    """读 R1 全表 26 行 → 按 (energy_type, classification) 二级 dict 返回.

    Returns:
        {
            'STEAM': {
                'GE_7_0_MPA': (92.0, 131.4),
                '0_8_TO_1_2_MPA': (76.0, 108.6),
                ...
            },
            'FUEL_GAS': {
                'OILFIELD_GAS': (0.93, 1.329),
                'GASFIELD_GAS': (0.85, 1.214),
                'REFINERY_FUEL_GAS': (950.0, 1357.1),
            },
            'WATER': {  # 9 类
                'FRESH_WATER': (0.15, 0.21),
                ...
            },
            ...
        }

    classification_key 优先级:
    - ELECTRICITY: value_type
    - FUEL_GAS / INSTRUMENT_AIR: sub_type
    - STEAM: pressure_level
    - WATER: water_type
    """
    # F-P1-002 fix: 走 5-min TTL 缓存, 避免与 _get_factors_default 重复 DB 查询
    rows = await _load_all_factor_rows(db)

    result: dict[str, dict[str, tuple[float, float]]] = {}

    for r in rows:
        # 选择分类字段
        if r.energy_type == "ELECTRICITY":
            key = r.value_type  # EQUIVALENT / EQUIVALENT_VALUE
        elif r.energy_type in ("FUEL_GAS", "INSTRUMENT_AIR"):
            key = r.sub_type  # OILFIELD_GAS / GASFIELD_GAS / REFINERY_FUEL_GAS / PURIFIED / NON_PURIFIED
        elif r.energy_type == "STEAM":
            key = r.pressure_level  # 9 档
        elif r.energy_type == "WATER":
            key = r.water_type  # 9 类
        else:
            # NITROGEN / GAS / LOW_TEMP_HEAT (无分类) — 用 energy_type 作 key
            key = r.energy_type

        if key is None:
            continue  # 跳过 NULL 分类 (未回填)

        result.setdefault(r.energy_type, {})[key] = (r.toe_factor, r.standard_coal_factor)

    return result


async def _load_all_factor_rows(db: AsyncSession) -> list[ConfigEnergyConversionFactor]:
    """F-P1-002 fix: 5-min TTL 缓存加载 ConfigEnergyConversionFactor 全表行.

    缓存键 'config_energy_conversion_factors' — 同一进程 5 min 内多次 summarize
    只触发 1 次 DB 查询 (R1 26 行; 后续 +50+ 行后显著减 DB 负载).

    测试隔离: clear_all_caches() 让 vitest 重新加载 (避免 cache 跨测试污染).
    """
    async def _loader() -> list[ConfigEnergyConversionFactor]:
        stmt = select(ConfigEnergyConversionFactor)
        return list((await db.execute(stmt)).scalars().all())

    return await get_or_reload_async("config_energy_conversion_factors", _loader)


async def _get_factors_default(
    db: AsyncSession,
    *,
    electricity_value_type: str = "EQUIVALENT",
) -> dict[str, tuple[float, float]]:
    """读 R1 26 行 → 默认单值 (last-wins by energy_type).

    R1 §5: ELECTRICITY 按 value_type 精确查表; 其他能源 last-wins.
    F-P1-002: 走 5-min TTL 缓存 (同进程内多次调用只触发 1 次 DB read).
    """
    rows = await _load_all_factor_rows(db)

    result: dict[str, tuple[float, float]] = {}
    elec_equiv: tuple[float, float] | None = None
    elec_value: tuple[float, float] | None = None
    for r in rows:
        if r.energy_type == "ELECTRICITY":
            if r.value_type == "EQUIVALENT":
                elec_equiv = (r.toe_factor, r.standard_coal_factor)
            elif r.value_type == "EQUIVALENT_VALUE":
                elec_value = (r.toe_factor, r.standard_coal_factor)
        # 其他能源: last-wins (后续 sprint 用 R1 全表精确分类)
        result[r.energy_type] = (r.toe_factor, r.standard_coal_factor)

    # ELECTRICITY 按 caller 指定 value_type 选
    if electricity_value_type == "EQUIVALENT_VALUE" and elec_value is not None:
        result["ELECTRICITY"] = elec_value
    elif elec_equiv is not None:
        result["ELECTRICITY"] = elec_equiv

    return result


def _get_factor_with_classification(
    factors: dict[str, tuple[float, float]],
    energy_type: str,
    *,
    value_type: str | None = None,
    sub_type: str | None = None,
    pressure_level: str | None = None,
    water_type: str | None = None,
) -> tuple[float, float] | None:
    """按 R1 分类查 R1 系数表 (默认 fallback 到 energy_type 单行).

    Args:
        factors: 全 R1 系数 dict (含分类字段)
        energy_type: 必填 (ELECTRICITY/STEAM/WATER/...)
        value_type: ELECTRICITY 用 (EQUIVALENT/EQUIVALENT_VALUE)
        sub_type: FUEL_GAS/INSTRUMENT_AIR 用 (OILFIELD_GAS/GASFIELD_GAS/REFINERY_FUEL_GAS/PURIFIED/NON_PURIFIED)
        pressure_level: STEAM 用 (9 档)
        water_type: WATER 用 (9 类)

    Returns:
        (toe_factor, standard_coal_factor) 或 None (未找到)
    """
    # NOTE: 当前 dict 简化按 energy_type 单行返回 (last-wins).
    # 后续 sprint: 用 R1 26 行全表 + classification 过滤返回精确分类.
    return factors.get(energy_type)


def _compute_totals(
    agg: EnergyAggregation,
    factors: dict[str, tuple[float, float]],
    *,
    electricity_value_type: str = "EQUIVALENT",
    factors_by_class: dict[str, dict[str, tuple[float, float]]] | None = None,
) -> tuple[float, float, float]:
    """6 类能源消耗 × 折标系数 → total_toe / total_standard_coal_kg /
    annual_total_energy (MJ/yr).

    R1 §5: electricity_value_type 选择 ELECTRICITY 当量值/等价值:
    - EQUIVALENT (当量值 0.086 kg标油/kWh, 其他产品用; 默认)
    - EQUIVALENT_VALUE (等价值 0.21 kg标油/kWh, 炼油/乙烯用)

    当前实现: dict 单行 lookup (last-wins); 炼油/乙烯等价值用户传 EQUIVALENT_VALUE
    会触发精确查表逻辑 (按 R1 26 行全表).

    单位换算到 MJ canonical unit (简化假设; 待 P7-6B 工艺室精化):
    - 1 kWh = 3.6 MJ
    - 1 Nm³ fuel_gas ≈ 38 MJ (低热值典型)
    - 1 t 蒸汽 (1 MPa 饱和) ≈ 2778 MJ (焓值)
    - 1 t 新鲜水 ≈ 0 MJ (折标能源)
    - 1 Nm³ 工艺气体 ≈ 0 MJ (预留)
    - 1 GJ 低温余热 = 1000 MJ

    Returns: (total_toe, total_standard_coal_kg, annual_total_energy_mj)
    """
    # 单位换算因子 → MJ (per unit)
    KWH_TO_MJ = 3.6
    NM3_FUEL_GAS_TO_MJ = 38.0  # 典型天然气低热值 ~38 MJ/Nm³
    T_STEAM_TO_MJ = 2778.0  # 1 MPa 饱和蒸汽 (待 P7-6B 工艺室精化按等级区分)
    T_WATER_TO_MJ = 0.0  # 新鲜水非能源
    NM3_GAS_TO_MJ = 0.0  # 预留
    GJ_LOW_TEMP_TO_MJ = 1000.0

    # R1 §5: 电折标系数按 electricity_value_type 选择
    # 当前 dict 单行 (last-wins) → 默认 EQUIVALENT; EQUIVALENT_VALUE 需精确查表
    if electricity_value_type == "EQUIVALENT_VALUE":
        # 等价值 (炼油/乙烯) — R1 强制 0.21 kg标油/kWh
        e_toe, e_coal = factors.get(
            "ELECTRICITY", (0.21, 0.30)
        )
    else:
        # 当量值 (默认; 其他产品) — R1 强制 0.086 kg标油/kWh
        e_toe, e_coal = factors.get(
            "ELECTRICITY", (0.086, 0.1229)
        )

    # R1 §7.1+§7.3: STEAM 按 9 档 pressure_level 分类查 R1 系数;
    # FUEL_GAS 按 3 类 gas_source 分类查 R1 系数 (替代单值 fallback).
    # 注: factors 参数 (单值 last-wins dict) 与 factors_by_class (R1 全表分类 dict) 都接收.
    # 本期: 优先用 *_by_* 分类聚合 + 分类 R1 系数; 退化为 factors 单值.
    f_toe, f_coal = factors.get("FUEL_GAS", (0.85, 1.214))
    s_toe, s_coal = factors.get("STEAM", (76.0, 108.6))
    w_toe, w_coal = factors.get("WATER", (0.06, 0.086))
    g_toe, g_coal = factors.get("GAS", (0.85, 1.2143))
    h_toe, h_coal = factors.get("LOW_TEMP_HEAT", (0.0341, 0.0487))

    # 年度累积 MJ
    electricity_mj = agg.electricity_kwh_yr * KWH_TO_MJ
    fuel_gas_mj = agg.fuel_gas_nm3_yr * NM3_FUEL_GAS_TO_MJ
    steam_mj = agg.steam_t_yr * T_STEAM_TO_MJ
    water_mj = agg.water_t_yr * T_WATER_TO_MJ
    gas_mj = agg.gas_nm3_yr * NM3_GAS_TO_MJ
    low_temp_mj = agg.low_temp_heat_gj_yr * GJ_LOW_TEMP_TO_MJ
    annual_total_energy = (
        electricity_mj + fuel_gas_mj + steam_mj
        + water_mj + gas_mj + low_temp_mj
    )

    # R1 §7.1 + §7.3: STEAM + FUEL_GAS 按分类聚合 + 分类 R1 系数.
    # 若 factors_by_class 提供 + agg 有 *_by_* dict 数据 → 用分类精确计算;
    # 否则退化到单值 (R0 兼容).
    steam_toe_kg = 0.0
    steam_coal_kg = 0.0
    fuel_toe_kg = 0.0
    fuel_coal_kg = 0.0

    if (
        factors_by_class
        and agg.steam_t_by_pressure_level
        and factors_by_class.get("STEAM")
    ):
        # R1 §7.1: 蒸汽按 9 档 pressure_level 分类查 R1 系数
        for pressure_level, t_amount in agg.steam_t_by_pressure_level.items():
            s_pair = factors_by_class["STEAM"].get(pressure_level)
            if s_pair is None:
                continue  # 未回填该档, 跳过
            s_toe_class, s_coal_class = s_pair
            steam_toe_kg += t_amount * s_toe_class
            steam_coal_kg += t_amount * s_coal_class
    else:
        # R0 兼容: 单值 fallback
        steam_toe_kg = agg.steam_t_yr * s_toe
        steam_coal_kg = agg.steam_t_yr * s_coal

    if (
        factors_by_class
        and agg.fuel_gas_by_source
        and factors_by_class.get("FUEL_GAS")
    ):
        # R1 §7.3: 燃料气按 3 类 gas_source 分类查 R1 系数
        for gas_source, nm3_amount in agg.fuel_gas_by_source.items():
            f_pair = factors_by_class["FUEL_GAS"].get(gas_source)
            if f_pair is None:
                continue  # 未回填该源, 跳过
            f_toe_class, f_coal_class = f_pair
            fuel_toe_kg += nm3_amount * f_toe_class
            fuel_coal_kg += nm3_amount * f_coal_class
    else:
        # R0 兼容: 单值 fallback
        fuel_toe_kg = agg.fuel_gas_nm3_yr * f_toe
        fuel_coal_kg = agg.fuel_gas_nm3_yr * f_coal

    # R1 §7.2: 水按 water_type 9 类分类查 R1 系数 (替代 R0 单值 fallback)
    water_toe_kg = 0.0
    water_coal_kg = 0.0
    if (
        factors_by_class
        and agg.water_by_type
        and factors_by_class.get("WATER")
    ):
        for water_type, t_amount in agg.water_by_type.items():
            w_pair = factors_by_class["WATER"].get(water_type)
            if w_pair is None:
                continue  # 未回填该水类, 跳过
            w_toe_class, w_coal_class = w_pair
            water_toe_kg += t_amount * w_toe_class
            water_coal_kg += t_amount * w_coal_class
    else:
        # R0 兼容: 单值 fallback
        water_toe_kg = agg.water_t_yr * w_toe
        water_coal_kg = agg.water_t_yr * w_coal

    # toe = consumption × toe_factor (toe_factor 单位 kg 标油 / 单位消耗)
    # total 单位转换: toe = consumption_kg_单位足 × kg 标油 / 单位 = kg 标油
    # → divide by 1000 → tonne oil equivalent
    total_toe_kg = (
        agg.electricity_kwh_yr * e_toe
        + fuel_toe_kg
        + steam_toe_kg
        + water_toe_kg
        + agg.gas_nm3_yr * g_toe
        + agg.low_temp_heat_gj_yr * h_toe
    )
    total_toe = total_toe_kg / 1000.0  # kg → tonne

    total_coal_kg = (
        agg.electricity_kwh_yr * e_coal
        + fuel_coal_kg
        + steam_coal_kg
        + water_coal_kg
        + agg.gas_nm3_yr * g_coal
        + agg.low_temp_heat_gj_yr * h_coal
    )

    return total_toe, total_coal_kg, annual_total_energy


async def summarize_energy_year(
    db: AsyncSession,
    project_id: str,
    workspace_id: str,
    business_year: int,
    *,
    source: str = "CALCULATION",
    tolerance_pct_max: float = DEFAULT_TOLERANCE_PCT,
    xls_reference: UtilityEnergySummary | None = None,
    electricity_value_type: str = "EQUIVALENT",
) -> UtilityEnergySummary:
    """聚合 project_id + business_year 综合能耗 + 折标 → UtilityEnergySummary.

    idempotent: 同 (project_id, business_year, source) 已存在则覆盖更新。
    容差校验: xls_reference 不为空时计算 tolerance_pct; 否则 status='NA'。

    R1 §5: electricity_value_type 选择电当量值 (默认 EQUIVALENT) / 等价值
    (EQUIVALENT_VALUE, 炼油/乙烯用).

    Args:
        db: AsyncSession.
        project_id: 项目 ID (UUID).
        workspace_id: 工作区 ID (UUID).
        business_year: 业务年度 (e.g., 2026).
        source: 'CALCULATION' (服务计算) / 'XLS_REFERENCE' (Excel 基准).
        tolerance_pct_max: 容差上限 (per P7-OPEN-009 §6 ≤ 2%).
        xls_reference: 同年 XLS_REFERENCE summary 用于容差对账; None 跳过.
        electricity_value_type: R1 §5 电当量值/等价值 (EQUIVALENT/EQUIVALENT_VALUE).

    Returns:
        UtilityEnergySummary ORM 实例 (persisted).
    """
    # 1. 聚合 T1+T2+T3 子表 (R1 §7 分类聚合待后续 sprint)
    agg = await _aggregate_util_subtables(
        db, project_id, business_year,
        electricity_value_type=electricity_value_type,
    )

    # 2. 读 ConfigEnergyConversionFactor 折标系数 (R1 §5: 按 electricity_value_type)
    factors = await _get_energy_conversion_factors(
        db, electricity_value_type=electricity_value_type,
    )
    # R1 §7.1+§7.3: 分类精确查表 (R1 全表 26 行)
    factors_by_class = await _get_factors_by_classification(db)

    # 3. 计算 total_toe / total_coal / annual_total_energy
    # R1 §5: electricity_value_type 选择 ELECTRICITY 行 (EQUIVALENT/EQUIVALENT_VALUE)
    total_toe, total_coal_kg, annual_total_energy = _compute_totals(
        agg, factors,
        electricity_value_type=electricity_value_type,
        factors_by_class=factors_by_class,
    )

    # 4. 聚合折标系数 (kg 标 / MJ)
    if annual_total_energy > 0:
        toe_conversion_factor = (total_toe * 1000.0) / annual_total_energy
        standard_coal_factor = total_coal_kg / annual_total_energy
    else:
        # 无消耗: 系数退化为 0 (CHECK 约束 > 0 需 fill 兜底)
        toe_conversion_factor = 1e-9
        standard_coal_factor = 1e-9

    # 5. 容差校验
    tolerance_pct: float | None = None
    tolerance_status = "NA"
    # F-P0-003 fix: total_toe nullable; must guard is not None BEFORE > 0 comparison
    if (
        xls_reference is not None
        and xls_reference.total_toe is not None
        and xls_reference.total_toe > 0
    ):
        tolerance_pct = abs(
            (total_toe - xls_reference.total_toe) / xls_reference.total_toe * 100.0
        )
        tolerance_status = (
            "OK" if tolerance_pct <= tolerance_pct_max else "EXCEEDED"
        )

    # 6. F-P0-002 fix: 删 SELECT + INSERT-or-UPDATE 分支, 改用 upsert 防 TOCTOU race
    # 旧逻辑: 非锁定 SELECT → 并发两 POST 都走 'new' 分支 → 第二个 commit 触 UNIQUE 约束 500
    # 新逻辑: 直接 INSERT ... ON CONFLICT (project_id, business_year, source) DO UPDATE
    # 避免 race; 用 SELECT 兜底刷新 summary 对象 (回填 id + ORM 默认值)
    # dialect-agnostic: 用 db.bind.dialect 决定是 PG / SQLite, 兼容 test in-memory SQLite
    from sqlalchemy.dialects import sqlite as sqlite_dialect  # noqa: PLC0415
    insert_dialect = sqlite_dialect if db.bind is None or db.bind.dialect.name == "sqlite" else None
    if insert_dialect is not None:
        insert_stmt = sqlite_dialect.insert(UtilityEnergySummary).values(
            project_id=project_id,
            workspace_id=workspace_id,
            business_year=business_year,
            source=source,
            electricity_kwh_yr=agg.electricity_kwh_yr,
            fuel_gas_nm3_yr=agg.fuel_gas_nm3_yr,
            steam_t_yr=agg.steam_t_yr,
            water_t_yr=agg.water_t_yr,
            gas_nm3_yr=agg.gas_nm3_yr,
            low_temp_heat_gj_yr=agg.low_temp_heat_gj_yr,
            annual_total_energy=annual_total_energy,
            toe_conversion_factor=toe_conversion_factor,
            standard_coal_factor=standard_coal_factor,
            total_toe=total_toe,
            total_standard_coal_kg=total_coal_kg,
            tolerance_pct=tolerance_pct,
            tolerance_status=tolerance_status,
            electricity_value_type=electricity_value_type,
            r1_classification_json=_build_r1_classification(agg),
        )
    else:
        from sqlalchemy.dialects.postgresql import insert as pg_insert  # noqa: PLC0415
        insert_stmt = pg_insert(UtilityEnergySummary).values(
            project_id=project_id,
            workspace_id=workspace_id,
            business_year=business_year,
            source=source,
            electricity_kwh_yr=agg.electricity_kwh_yr,
            fuel_gas_nm3_yr=agg.fuel_gas_nm3_yr,
            steam_t_yr=agg.steam_t_yr,
            water_t_yr=agg.water_t_yr,
            gas_nm3_yr=agg.gas_nm3_yr,
            low_temp_heat_gj_yr=agg.low_temp_heat_gj_yr,
            annual_total_energy=annual_total_energy,
            toe_conversion_factor=toe_conversion_factor,
            standard_coal_factor=standard_coal_factor,
            total_toe=total_toe,
            total_standard_coal_kg=total_coal_kg,
            tolerance_pct=tolerance_pct,
            tolerance_status=tolerance_status,
            electricity_value_type=electricity_value_type,
            r1_classification_json=_build_r1_classification(agg),
        )
    # ON CONFLICT DO UPDATE: 同 (project_id, business_year, source) 行 → UPDATE SET
    upsert_stmt = insert_stmt.on_conflict_do_update(
        index_elements=["project_id", "business_year", "source"],
        set_={
            "electricity_kwh_yr": insert_stmt.excluded.electricity_kwh_yr,
            "fuel_gas_nm3_yr": insert_stmt.excluded.fuel_gas_nm3_yr,
            "steam_t_yr": insert_stmt.excluded.steam_t_yr,
            "water_t_yr": insert_stmt.excluded.water_t_yr,
            "gas_nm3_yr": insert_stmt.excluded.gas_nm3_yr,
            "low_temp_heat_gj_yr": insert_stmt.excluded.low_temp_heat_gj_yr,
            "annual_total_energy": insert_stmt.excluded.annual_total_energy,
            "toe_conversion_factor": insert_stmt.excluded.toe_conversion_factor,
            "standard_coal_factor": insert_stmt.excluded.standard_coal_factor,
            "total_toe": insert_stmt.excluded.total_toe,
            "total_standard_coal_kg": insert_stmt.excluded.total_standard_coal_kg,
            "tolerance_pct": insert_stmt.excluded.tolerance_pct,
            "tolerance_status": insert_stmt.excluded.tolerance_status,
            "electricity_value_type": insert_stmt.excluded.electricity_value_type,
            "r1_classification_json": insert_stmt.excluded.r1_classification_json,
            "computed_at": func.now(),
        },
    )
    await db.execute(upsert_stmt)
    await db.commit()

    # 7. 兜底 SELECT 回填 summary 对象 (含 id + ORM 默认值)
    stmt_existing = (
        select(UtilityEnergySummary)
        .where(
            UtilityEnergySummary.project_id == project_id,
            UtilityEnergySummary.business_year == business_year,
            UtilityEnergySummary.source == source,
        )
    )
    summary = (await db.execute(stmt_existing)).scalars().first()
    if summary is None:
        # 极端 case: upsert 没生效 (driver 问题); 抛错让 caller 重试
        raise RuntimeError(
            "summarize_energy_year upsert failed: summary not found after commit"
        )
    # 显式 refresh 确保所有字段从 DB 加载 (避免 session identity map 缓存旧值)
    await db.refresh(summary)
    return summary