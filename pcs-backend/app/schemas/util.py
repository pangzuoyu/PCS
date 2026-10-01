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

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class UtilResultsCreateRequest(BaseModel):
    """手动创建 UtilResults（带 consumption_json 13 类 flat map）。"""

    project_id: uuid.UUID = Field(..., description="项目 UUID")
    workspace_id: uuid.UUID = Field(..., description="workspace UUID")
    business_date: date | None = Field(None, description="业务日期（折标煤按年查询用）")
    consumption_json: dict[str, float] = Field(
        ...,
        description="13 类公用工程 flat {category: float_quantity} map",
    )
    source: str | None = Field(None, max_length=200, description="数据来源描述")


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
    """能源专项（5 类进 TOE：ELECTRICITY + STEAM×4 + FUEL_GAS）。"""

    by_category: dict[str, float] = Field(
        ...,
        description="5 能源类消耗量：ELECTRICITY / STEAM_HP / STEAM_MP / STEAM_LP / FUEL_GAS",
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
