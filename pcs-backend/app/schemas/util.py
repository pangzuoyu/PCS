"""S1-5b UTIL API schemas。

Per R5 ruling 补 API 层；与 summary_service (S1-5) 协同：

- UtilResultsCreateRequest: 手动创建 UtilResults（带 consumption_json）
- UtilResultsResponse: 单条记录响应（含 jsonb_deprecated 标记）
- UtilSummaryResponse: 13 类聚合 + toe_total + standard_coal_total（来自 summary_service）
- UtilEnergyConsumptionResponse: 仅能源类（5 类进 TOE）
- UtilWaterBalanceResponse: 仅水类（COOLING/CHILLED/MAKEUP）
- UtilAggregationRequest: 触发 source_aggregator 聚合 + 自动写入 UtilResults
"""

from __future__ import annotations

import math
import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class UtilResultsCreateRequest(BaseModel):
    """手动创建 UtilResults（带 consumption_json 13 类 flat map）。

    F-P1-013 fix: 拒绝 NaN/Inf — 防止下游 toe_total 计算被污染
    (math.nan × factor = nan, math.inf × factor = inf).
    """

    project_id: uuid.UUID = Field(..., description="项目 UUID")
    workspace_id: uuid.UUID = Field(..., description="workspace UUID")
    business_date: date | None = Field(None, description="业务日期（折标煤按年查询用）")
    consumption_json: dict[str, float] = Field(
        ...,
        description="13 类公用工程 flat {category: float_quantity} map",
    )
    source: str | None = Field(None, max_length=200, description="数据来源描述")

    @field_validator("consumption_json")
    @classmethod
    def _reject_nan_inf(cls, v: dict[str, float]) -> dict[str, float]:
        for cat, qty in v.items():
            if not math.isfinite(qty):
                raise ValueError(
                    f"consumption_json[{cat!r}]={qty} 不是 finite "
                    f"(NaN/Inf 拒绝 — 污染下游 toe_total)"
                )
        return v


class UtilResultsResponse(BaseModel):
    """UtilResults 单条记录响应。"""

    util_result_id: uuid.UUID
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    business_date: date | None = None
    consumption_json: dict
    jsonb_deprecated: bool
    source: str | None = None
    created_at: str | None = None
    updated_at: str | None = None


class UtilSummaryResponse(BaseModel):
    """13 类聚合 + 折标煤响应（来自 summary_service.summarize）。"""

    by_category: dict[str, float] = Field(
        ..., description="13 类公用工程消耗量 {category: float}"
    )
    toe_total: float = Field(..., description="折标油当量总和（仅 6 类能源）")
    standard_coal_total: float = Field(..., description="标煤总和")
    jsonb_deprecated: bool = Field(..., description="Sprint 1 False JSONB 权威")
    year: int = Field(..., description="折标煤查询年份")


class UtilEnergyConsumptionResponse(BaseModel):
    """能源专项（6 类进 TOE：ELECTRICITY + STEAM×3 + FUEL_GAS + CONDENSATE）。

    F-P1-015 fix: 由 5 类扩展到 6 类 — 与 toe_total 计算口径一致 (CONDENSATE 按
    STEAM 折标计算入 toe_total 但 by_category 之前漏掉, 致客户端无法解释)。
    """

    by_category: dict[str, float] = Field(
        ...,
        description="6 能源类消耗量：ELECTRICITY / STEAM_HP / STEAM_MP / STEAM_LP / FUEL_GAS / CONDENSATE",
    )
    toe_total: float
    standard_coal_total: float
    year: int


class UtilWaterBalanceResponse(BaseModel):
    """水平衡专项（3 类：COOLING_WATER + CHILLED_WATER + MAKEUP_WATER）。"""

    by_category: dict[str, float] = Field(
        ...,
        description="3 水类消耗量：COOLING_WATER / CHILLED_WATER / MAKEUP_WATER",
    )
    total_water_t: float = Field(..., description="3 类总和")
    year: int


class UtilAggregationRequest(BaseModel):
    """触发 source_aggregator + 写入 UtilResults。"""

    project_id: uuid.UUID = Field(..., description="项目 UUID")
    workspace_id: uuid.UUID = Field(..., description="workspace UUID")
    modules: list[Literal["PUMP", "HEAT", "COOL_TOWER", "OPEN_CHANNEL"]] | None = Field(
        None,
        description="要聚合的 SourceModule；默认全部 4 个",
    )
    business_date: date | None = Field(None, description="业务日期")
    source: str | None = Field(
        None, max_length=200, description="数据来源描述（默认 'source_aggregator'）"
    )


# ============================================================================
# P7 Sprint 2 T1-T5 schemas (UTIL 5 表 API 整合)
# ============================================================================


class UtilPowerItemCreateRequest(BaseModel):
    """手动创建 UtilityPowerItem (T1 电耗设备清单)."""

    project_id: uuid.UUID = Field(..., description="项目 UUID")
    workspace_id: uuid.UUID = Field(..., description="workspace UUID")
    equipment_tag: str = Field(..., min_length=1, max_length=64, description="设备位号")
    motor_power_kw: float = Field(..., gt=0, description="电机额定功率 (kW)")
    operating_hours_per_year: float = Field(
        ..., gt=0, le=8760, description="年运行小时 (h/yr)"
    )
    load_factor: float = Field(..., gt=0, le=1, description="负荷率")
    annual_consumption_kwh: float | None = Field(
        None, ge=0, description="年用电量 (kWh/yr; 缺省=service 计算)"
    )
    source: str | None = Field(
        "MANUAL", max_length=32, description="数据来源 PMS/MANUAL/CALC"
    )


class UtilPowerItemResponse(BaseModel):
    """UtilityPowerItem 单条响应 (T1)."""

    id: uuid.UUID
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    equipment_id: uuid.UUID | None = None
    equipment_tag: str
    motor_power_kw: float
    operating_hours_per_year: float
    load_factor: float
    annual_consumption_kwh: float
    source: str
    created_at: str | None = None
    updated_at: str | None = None


class UtilFuelGasCreateRequest(BaseModel):
    """手动创建 UtilityFuelGas (T2 燃料气).

    R1 §7.3 新增 gas_source 3 类 (OILFIELD_GAS/GASFIELD_GAS/REFINERY_FUEL_GAS)
    GB 30251-2024 附录A 油气源分类.
    """

    project_id: uuid.UUID = Field(..., description="项目 UUID")
    workspace_id: uuid.UUID = Field(..., description="workspace UUID")
    equipment_tag: str = Field(..., min_length=1, max_length=64, description="设备位号")
    fuel_type: str = Field("NATURAL_GAS", max_length=32, description="燃料类型 (R0 字段, R1 deprecated)")
    gas_source: str | None = Field(
        None, max_length=32,
        description=(
            "气源分类 (R1 §7.3): OILFIELD_GAS (油田气 0.93) / "
            "GASFIELD_GAS (气田气 0.85) / REFINERY_FUEL_GAS (炼厂燃料气 950 kg/t)"
        ),
    )
    calorific_value_kcal_nm3: float = Field(
        ..., gt=0, le=20000, description="低位热值 (kcal/Nm³)"
    )
    consumption_nm3_h: float = Field(..., gt=0, description="小时消耗量 (Nm³/h)")
    operating_phase: str = Field(
        ..., max_length=16, description="INITIAL/STEADY/MAX"
    )
    operating_hours_per_year: float = Field(
        8000.0, gt=0, le=8760, description="年运行小时"
    )
    annual_consumption_nm3: float | None = Field(
        None, ge=0, description="年消耗量 (Nm³/yr; 缺省=service 计算)"
    )
    source: str | None = Field(
        "MANUAL", max_length=32, description="数据来源"
    )


class UtilFuelGasResponse(BaseModel):
    """UtilityFuelGas 单条响应 (T2)."""

    id: uuid.UUID
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    equipment_id: uuid.UUID | None = None
    equipment_tag: str
    fuel_type: str
    calorific_value_kcal_nm3: float
    consumption_nm3_h: float
    operating_phase: str
    operating_hours_per_year: float
    annual_consumption_nm3: float
    source: str
    created_at: str | None = None
    updated_at: str | None = None


class UtilHeatExchangeCreateRequest(BaseModel):
    """手动创建 UtilityHeatExchange (T3 蒸汽/冷凝水).

    R1 §7.1 + §7.2 新增 pressure_level 9 档 + medium_type 10 类.
    """

    project_id: uuid.UUID = Field(..., description="项目 UUID")
    workspace_id: uuid.UUID = Field(..., description="workspace UUID")
    equipment_tag: str = Field(..., min_length=1, max_length=64, description="设备位号")
    steam_pressure_mpa_gauge: float = Field(
        ..., gt=0, description="蒸汽压力 (MPa gauge; R0 字段, R1 deprecated)"
    )
    steam_quality_pct: float = Field(
        ..., ge=0, le=100, description="蒸汽干度"
    )
    return_condensate_pct: float = Field(
        ..., ge=0, le=100, description="冷凝水回收率"
    )
    temperature_class: str = Field(
        ..., max_length=16, description="LP/MP/HP/ULTRA_HIGH (R0 字段, R1 deprecated)"
    )
    pressure_level: str | None = Field(
        None, max_length=32,
        description=(
            "压力等级 (R1 §7.1 GB 30251-2024 9 档): "
            "GE_7_0_MPA / 4_5_TO_7_0_MPA / 3_0_TO_4_5_MPA / 2_0_TO_3_0_MPA / "
            "1_2_TO_2_0_MPA / 0_8_TO_1_2_MPA / 0_6_TO_0_8_MPA / 0_3_TO_0_6_MPA / LT_0_3_MPA"
        ),
    )
    medium_type: str | None = Field(
        None, max_length=32,
        description=(
            "介质类型 (R1 §7.2): STEAM / FRESH_WATER / CIRCULATING_WATER / "
            "SOFTENED_WATER / DEMINERALIZED_WATER / LP_DEAERATED_WATER / "
            "HP_DEAERATED_WATER / TURBINE_CONDENSATE / 120C_CONDENSATE_TREATED / "
            "120C_CONDENSATE_REUSABLE"
        ),
    )
    steam_consumption_t_h: float = Field(..., gt=0, description="小时消耗 (t/h)")
    operating_hours_per_year: float = Field(
        8000.0, gt=0, le=8760, description="年运行小时"
    )
    annual_consumption_t: float | None = Field(
        None, ge=0, description="年消耗量 (t/yr; 缺省=service 计算)"
    )
    source: str | None = Field("MANUAL", max_length=32, description="数据来源")


class UtilHeatExchangeResponse(BaseModel):
    """UtilityHeatExchange 单条响应 (T3)."""

    id: uuid.UUID
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    equipment_id: uuid.UUID | None = None
    equipment_tag: str
    steam_pressure_mpa_gauge: float
    steam_quality_pct: float
    return_condensate_pct: float
    temperature_class: str
    steam_consumption_t_h: float
    operating_hours_per_year: float
    annual_consumption_t: float
    source: str
    created_at: str | None = None
    updated_at: str | None = None


class UtilEnergySummaryAggregateRequest(BaseModel):
    """触发 T5 综合能耗汇总 (utility_energy_summary_service.summarize_energy_year).

    R1 §5: electricity_value_type 选择当量值/等价值.
    """

    project_id: uuid.UUID = Field(..., description="项目 UUID")
    workspace_id: uuid.UUID = Field(..., description="workspace UUID")
    business_year: int = Field(2026, ge=2020, le=2100, description="业务年度")
    electricity_value_type: str = Field(
        "EQUIVALENT",
        max_length=16,
        description=(
            "电当量值/等价值 (R1 §5 GB 30251-2024 §6.1.1): "
            "EQUIVALENT (当量值 0.086 kg标油/kWh - 其他产品用; 默认) / "
            "EQUIVALENT_VALUE (等价值 0.21 kg标油/kWh - 炼油/乙烯用)"
        ),
    )


class UtilEnergySummaryResponse(BaseModel):
    """UtilityEnergySummary 单条响应 (T5)."""

    id: uuid.UUID
    project_id: uuid.UUID
    workspace_id: uuid.UUID
    business_year: int
    source: str
    electricity_kwh_yr: float | None = None
    fuel_gas_nm3_yr: float | None = None
    steam_t_yr: float | None = None
    water_t_yr: float | None = None
    gas_nm3_yr: float | None = None
    low_temp_heat_gj_yr: float | None = None
    annual_total_energy: float
    toe_conversion_factor: float
    standard_coal_factor: float
    total_toe: float
    total_standard_coal_kg: float
    tolerance_pct: float | None = None
    tolerance_status: str
    computed_at: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
