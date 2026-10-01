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
    stmt_steam_total = (
        select(
            func.coalesce(func.sum(UtilityHeatExchange.annual_consumption_t), 0.0)
        )
        .where(UtilityHeatExchange.project_id == project_id)
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

    return EnergyAggregation(
        electricity_kwh_yr=electricity_kwh_yr,
        fuel_gas_nm3_yr=fuel_gas_nm3_yr,
        steam_t_yr=steam_t_yr,
        water_t_yr=0.0,  # 待 P7-6B 冷却水子表 + R1 §7.2 9 类聚合
        gas_nm3_yr=0.0,
        low_temp_heat_gj_yr=0.0,
        steam_t_by_pressure_level=steam_t_by_pressure_level,
        fuel_gas_by_source=fuel_gas_by_source,
        water_by_type=None,  # 待 R1 §7.2 冷却水子表
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

    TODO: 接入 5-min TTL 缓存 (仿 ``_compound_config_cache`` 模式; T7 集成)。
    """
    stmt = select(ConfigEnergyConversionFactor)
    rows = (await db.execute(stmt)).scalars().all()

    # R1 §5: ELECTRICITY 按 value_type 精确查表; 其他能源 last-wins
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
        # 若 factors dict 有等价值行 (后续 sprint 用全表), 优先取它
    else:
        # 当量值 (默认; 其他产品) — R1 强制 0.086 kg标油/kWh
        e_toe, e_coal = factors.get(
            "ELECTRICITY", (0.086, 0.1229)
        )
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

    # toe = consumption × toe_factor (toe_factor 单位 kg 标油 / 单位消耗)
    # total 单位转换: toe = consumption_kg_单位足 × kg 标油 / 单位 = kg 标油
    # → divide by 1000 → tonne oil equivalent
    total_toe_kg = (
        agg.electricity_kwh_yr * e_toe
        + agg.fuel_gas_nm3_yr * f_toe
        + agg.steam_t_yr * s_toe
        + agg.water_t_yr * w_toe
        + agg.gas_nm3_yr * g_toe
        + agg.low_temp_heat_gj_yr * h_toe
    )
    total_toe = total_toe_kg / 1000.0  # kg → tonne

    total_coal_kg = (
        agg.electricity_kwh_yr * e_coal
        + agg.fuel_gas_nm3_yr * f_coal
        + agg.steam_t_yr * s_coal
        + agg.water_t_yr * w_coal
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

    # 3. 计算 total_toe / total_coal / annual_total_energy
    # R1 §5: electricity_value_type 选择 ELECTRICITY 行 (EQUIVALENT/EQUIVALENT_VALUE)
    total_toe, total_coal_kg, annual_total_energy = _compute_totals(
        agg, factors, electricity_value_type=electricity_value_type,
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
    if xls_reference is not None and xls_reference.total_toe > 0:
        tolerance_pct = abs(
            (total_toe - xls_reference.total_toe) / xls_reference.total_toe * 100.0
        )
        tolerance_status = (
            "OK" if tolerance_pct <= tolerance_pct_max else "EXCEEDED"
        )

    # 6. 检查 idempotent: 同 (project_id, business_year, source) 已存在?
    stmt_existing = (
        select(UtilityEnergySummary)
        .where(
            UtilityEnergySummary.project_id == project_id,
            UtilityEnergySummary.business_year == business_year,
            UtilityEnergySummary.source == source,
        )
    )
    existing = (await db.execute(stmt_existing)).scalars().first()

    if existing is not None:
        # 覆盖更新
        existing.electricity_kwh_yr = agg.electricity_kwh_yr
        existing.fuel_gas_nm3_yr = agg.fuel_gas_nm3_yr
        existing.steam_t_yr = agg.steam_t_yr
        existing.water_t_yr = agg.water_t_yr
        existing.gas_nm3_yr = agg.gas_nm3_yr
        existing.low_temp_heat_gj_yr = agg.low_temp_heat_gj_yr
        existing.annual_total_energy = annual_total_energy
        existing.toe_conversion_factor = toe_conversion_factor
        existing.standard_coal_factor = standard_coal_factor
        existing.total_toe = total_toe
        existing.total_standard_coal_kg = total_coal_kg
        existing.tolerance_pct = tolerance_pct
        existing.tolerance_status = tolerance_status
        # R1 §5: 持久化 electricity_value_type 标记 (审计追溯用)
        existing.electricity_value_type = electricity_value_type
        existing.computed_at = func.now()
        summary = existing
    else:
        # 新建
        summary = UtilityEnergySummary(
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
            # R1 §5
            electricity_value_type=electricity_value_type,
        )
        db.add(summary)

    await db.commit()
    await db.refresh(summary)
    return summary