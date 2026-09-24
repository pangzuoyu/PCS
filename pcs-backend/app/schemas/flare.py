"""FLARE_SYS Pydantic 请求/响应模型。

按 Pydantic v2 + OpenAPI 一致性要求：
- 所有字段带 Field description（中文） + example
- 默认值与 API 521 §5.15.4 保守口径一致

端点（Task 20 — 仅 header_sizing）：
- POST /api/v1/flare/header-sizing：req HeaderSizingRequest / resp HeaderSizingResponse

不写 DB（header_sizing 是计算，落库由 Task 23 flare_persist 统一处理）。
"""
from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class HeaderSizingRequest(BaseModel):
    """FLARE_SYS header_sizing 请求。

    字段（按 API 521 §5.15.4 火炬总管 Mach 数法 + 等温可压缩管流所需输入）：

    - project_id: 项目 ID（与 Task 19 aggregate_flare_load 隔离键一致）
    - standard_profile_code: 项目标准（默认 API_521；GB/T 暂不开放）
    - relief_mass_flow_kgs: 总泄放质量流量 kg/s（>0）
    - avg_temperature_k: 管内平均温度 K（>0）
    - avg_pressure_pa: 管内平均压力 Pa（>0）
    - mw_kg_kmol: 气体分子量 kg/kmol（>0）
    - specific_heat_ratio: 比热比 k = cp/cv（>1.0）
    - target_mach: 目标 Mach 数（默认 0.5 保守，范围 [0.05, 1.0]）
    """

    project_id: uuid.UUID = Field(
        ..., description="项目 ID（来自 Task 19 aggregate_flare_load 隔离键）"
    )
    standard_profile_code: str = Field(
        "API_521", description="项目标准（API_521 / GB/T）"
    )
    relief_mass_flow_kgs: float = Field(
        ..., gt=0, description="总泄放质量流量 kg/s"
    )
    avg_temperature_k: float = Field(..., gt=0, description="管内平均温度 K")
    avg_pressure_pa: float = Field(..., gt=0, description="管内平均压力 Pa")
    mw_kg_kmol: float = Field(..., gt=0, description="气体分子量 kg/kmol")
    specific_heat_ratio: float = Field(
        ..., gt=1.0, description="比热比 k = cp/cv"
    )
    target_mach: float = Field(
        0.5, ge=0.05, le=1.0, description="目标 Mach 数（默认 0.5 保守）"
    )


class HeaderSizingResponse(BaseModel):
    """FLARE_SYS header_sizing 响应。

    字段（按 API 521 §5.15.4 反算输出）：

    - diameter_m: 总管直径 m
    - area_m2: 总管截面积 m²
    - actual_mach: 实际 Mach 数（应等于 target_mach）
    - mass_flux_kgs_m2: 质量流速 G kg/(s·m²)
    - velocity_m_s: 气流速度 m/s
    - sound_speed_m_s: 等温声速 m/s
    - gas_density_kg_m3: 管内气体密度 kg/m³（等温理想气体）
    - formula_ref: 公式溯源标记
    - project_id: 回显请求 project_id（前端 audit）
    - standard_profile_code: 回显请求 standard_profile_code
    """

    diameter_m: float = Field(..., description="总管直径 m")
    area_m2: float = Field(..., description="总管截面积 m²")
    actual_mach: float = Field(..., description="实际 Mach 数（应等于 target_mach）")
    mass_flux_kgs_m2: float = Field(
        ..., description="质量流速 G kg/(s·m²)"
    )
    velocity_m_s: float = Field(..., description="气流速度 m/s")
    sound_speed_m_s: float = Field(..., description="等温声速 m/s")
    gas_density_kg_m3: float = Field(
        ..., description="管内气体密度 kg/m³（等温理想气体）"
    )
    formula_ref: str = Field(..., description="公式溯源标记（API_521_§5.15.4）")
    project_id: uuid.UUID = Field(..., description="回显请求 project_id")
    standard_profile_code: str = Field(..., description="回显请求 standard_profile_code")


__all__ = [
    "HeaderSizingRequest",
    "HeaderSizingResponse",
]