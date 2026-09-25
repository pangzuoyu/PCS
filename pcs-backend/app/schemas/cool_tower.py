"""COOL_TOWER Pydantic 请求/响应模型。

按 Pydantic v2 + OpenAPI 一致性要求：
- 所有字段带 Field description（中文）+ example
- 默认值与 SPEC §3.2.4 P6-CT-001 保守口径一致

端点（Task 25）：
- POST /api/v1/cool-tower/heat-load-aggregator:
    req HeatLoadAggregatorRequest / resp HeatLoadAggregatorResponse
- POST /api/v1/cool-tower/fan-power:
    req FanPowerRequest / resp FanPowerResponse
- POST /api/v1/cool-tower/water-balance:
    req WaterBalanceRequest / resp WaterBalanceResponse
- CRUD /api/v1/cool-tower/results:
    Create/Update/Response/ListResponse
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ───────────────────────────── 1. heat-load-aggregator（§3.2.4.5）────


class HeatLoadAggregatorRequest(BaseModel):
    """HEAT 汇总请求（POST /cool-tower/heat-load-aggregator）。

    字段（按 §3.2.4.5 汇总需求）：
    - project_id: 项目 ID（必填；isolation key）
    - exchanger_categories_filter: 过滤的 exchanger_category 列表
      （默认 ['SHELL_TUBE', 'PLATE']；排除 'AIR_COOL'）
    - sign_status_filter: sign_status 白名单（默认 ['DRAFT', 'CHECKED']）
    """

    project_id: uuid.UUID = Field(
        ..., description="项目 ID（isolation key）"
    )
    exchanger_categories_filter: list[str] | None = Field(
        None,
        description="过滤的 exchanger_category 列表（默认 ['SHELL_TUBE','PLATE']）",
    )
    sign_status_filter: list[str] | None = Field(
        None,
        description="sign_status 白名单（默认 ['DRAFT', 'CHECKED']）",
    )


class HeatLoadAggregatorResponse(BaseModel):
    """HEAT 汇总响应（POST /cool-tower/heat-load-aggregator）。

    字段：
    - h_aggregate_kw: 总 kW（各 exchanger_category 求和）
    - heat_record_count: 命中的 HeatResult 行数
    - per_exchanger_category: 按类别细分
    - formula_ref: 公式溯源标记 "API_521_§3.2.4.5"
    """

    h_aggregate_kw: float = Field(..., description="总 kW（汇总后）")
    heat_record_count: int = Field(..., description="命中 HeatResult 行数")
    per_exchanger_category: dict[str, float] = Field(
        ..., description="按 exchanger_category 细分"
    )
    formula_ref: str = Field(
        ..., description="公式溯源标记（API_521_§3.2.4.5）"
    )


# ───────────────────────────── 2. fan-power（§3.2.4.6）───────────


class FanPowerRequest(BaseModel):
    """风机功率请求（POST /cool-tower/fan-power）。

    字段（按 §3.2.4.6 CTI 1492 经验值所需输入）：
    - q_air_m3_s: 风机风量 m³/s（>0）
    - delta_p_total_pa: 全压 Pa（>0）
    - fan_efficiency: 风机效率（0 < η_fan < 1）
    - motor_efficiency: 电机效率（0 < η_motor < 1）
    """

    q_air_m3_s: float = Field(..., gt=0, description="风机风量 m³/s")
    delta_p_total_pa: float = Field(..., gt=0, description="风机全压 Pa")
    fan_efficiency: float = Field(
        ...,
        gt=0,
        lt=1,
        description="风机效率（轴流式 typ. 0.7，离心式 typ. 0.65）",
    )
    motor_efficiency: float = Field(
        ..., gt=0, lt=1, description="电机效率（typ. 0.85~0.95）"
    )


class FanPowerResponse(BaseModel):
    """风机功率响应（POST /cool-tower/fan-power）。

    字段：
    - p_fan_kw: 风机功率 kW
    - formula_ref: 公式溯源标记 "API_521_§3.2.4.6"
    """

    p_fan_kw: float = Field(..., description="风机功率 kW")
    formula_ref: str = Field(
        ..., description="公式溯源标记（API_521_§3.2.4.6）"
    )


# ───────────────────────────── 3. water-balance（§3.2.4.4）────────


class WaterBalanceRequest(BaseModel):
    """补充水量请求（POST /cool-tower/water-balance）。

    字段（按 §3.2.4.4 循环水量 + 补充水量合并输入）：
    - q_w_m3_s: 循环水量 m³/s（>0）
    - delta_t_c: 温差 °C（>=0；与 Kelvin 等价差值）
    - cycle_ratio: 浓缩倍数 C_cycle（>1）
    - drift_fraction: 风吹损失系数（∈ [0, 0.1]）
    - h_vap_kj_kg: 蒸发潜热 kJ/kg（>0；默认 2400）
    - c_water_kj_kg_k: 水比热 kJ/kg·K（>0；默认 4.187）
    """

    q_w_m3_s: float = Field(..., gt=0, description="循环水量 m³/s")
    delta_t_c: float = Field(..., ge=0, description="温差 °C")
    cycle_ratio: float = Field(
        4.0, gt=1, description="浓缩倍数 C_cycle（典型 3~5，默认 4）"
    )
    drift_fraction: float = Field(
        0.001,
        ge=0,
        le=0.1,
        description="风吹损失系数（典型 0.001~0.002）",
    )
    h_vap_kj_kg: float = Field(
        2400.0, gt=0, description="蒸发潜热 kJ/kg（默认 2400）"
    )
    c_water_kj_kg_k: float = Field(
        4.187, gt=0, description="水比热 kJ/kg·K（默认 4.187）"
    )


class WaterBalanceResponse(BaseModel):
    """补充水量响应（POST /cool-tower/water-balance）。

    字段：
    - evaporation_m3_s: 蒸发损失 E m³/s
    - drift_m3_s: 风吹损失 D m³/s
    - blowdown_m3_s: 排污损失 B m³/s（工程下限 clamp 0）
    - makeup_m3_s: 总补充水 M m³/s
    - formula_ref: 公式溯源标记 "API_521_§3.2.4.4"
    """

    evaporation_m3_s: float = Field(..., description="蒸发损失 E m³/s")
    drift_m3_s: float = Field(..., description="风吹损失 D m³/s")
    blowdown_m3_s: float = Field(..., description="排污损失 B m³/s")
    makeup_m3_s: float = Field(..., description="总补充水 M m³/s")
    formula_ref: str = Field(
        ..., description="公式溯源标记（API_521_§3.2.4.4）"
    )


# ───────────────────────────── 4. CoolTowerResult CRUD ──────────────


class CoolTowerResultCreateRequest(BaseModel):
    """CoolingTowerResult 创建请求（POST /cool-tower/results）。

    字段按 CoolingTowerResult ORM 列名（Task 18，P6-2 实施）平铺 ——
    ``save_cool_tower_result`` service 直接 ``**payload`` 喂给 ORM，
    字段名必须与列名严格一致：

    - project_id: 项目 ID（RecordMixin FK → projects.project_id）
    - workspace_id: 工作区 ID（业务隔离）
    - tag_number: 位号（TaggedRecordMixin NOT NULL；项目内唯一）
    - standard_profile_code: 项目标准（默认 "CTI_ATC_105"；
      C-07 String(16) 锁定）
    - calc_type: 计算类型（MERKEL / WATER_BALANCE / FAN_POWER /
      HEAT_AGGREGATE；String(32) NOT NULL）
    - sign_status: 签审状态（默认 DRAFT）

    10 业务字段（CoolingTowerResult __table__ 排除 PK + mixin 字段）：
    - tower_type: COUNTERFLOW_MECH / CROSSFLOW_MECH / NATURAL_DRAFT
    - duty_kw: 热负荷 kW（来自 Task 25 heat_aggregator）
    - water_flow_m3h: 循环水量 m³/h（来自 Task 24 calc_water_flow）
    - makeup_water_m3h: 补充水量 m³/h（来自 Task 24 calc_water_balance）
    - fan_power_kw: 风机功率 kW（来自 Task 25 calc_fan_power）
    - merkel_integral: Merkel 积分值 KaV/L（来自 Task 24 calc_merkel）
    - data_sheet_json: PCS-DICT-007 SUP-012 §3 14 子结构 data sheet
    - input_json: 入参（业务子结构）
    - output_json: 出参（业务子结构）
    """

    # 溯源 + 隔离（mixin 必填）
    project_id: uuid.UUID = Field(..., description="项目 ID（FK → projects）")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID（业务隔离）")
    tag_number: str = Field(
        ..., min_length=1, max_length=50, description="位号（TaggedRecordMixin NOT NULL）"
    )
    standard_profile_code: str = Field(
        "CTI_ATC_105", description="项目标准（默认 CTI_ATC_105）"
    )
    calc_type: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="计算类型（MERKEL/WATER_BALANCE/FAN_POWER/HEAT_AGGREGATE）",
    )
    sign_status: str = Field(
        "DRAFT",
        description=(
            "签审状态（DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / "
            "STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE）"
        ),
    )

    # 10 业务字段（按 ORM 列名平铺；service layer **payload 喂给 ORM）
    tower_type: str | None = Field(
        None,
        description="塔型（COUNTERFLOW_MECH / CROSSFLOW_MECH / NATURAL_DRAFT）",
    )
    duty_kw: float | None = Field(None, description="热负荷 kW")
    water_flow_m3h: float | None = Field(None, description="循环水量 m³/h")
    makeup_water_m3h: float | None = Field(None, description="补充水量 m³/h")
    fan_power_kw: float | None = Field(None, description="风机功率 kW")
    merkel_integral: float | None = Field(
        None, description="Merkel 积分值 KaV/L"
    )
    data_sheet_json: dict | None = Field(
        None, description="PCS-DICT-007 SUP-012 §3 14 子结构 data sheet"
    )
    input_json: dict | None = Field(None, description="入参（业务子结构）")
    output_json: dict | None = Field(None, description="出参（业务子结构）")


class CoolTowerResultUpdateRequest(BaseModel):
    """CoolingTowerResult 更新请求（PATCH /cool-tower/results/{id}）。

    字段子集（PATCH 仅允许业务字段；不可改 sign_status / tag_number /
    溯源 / standard_profile_code / calc_type 等）。
    """

    tower_type: str | None = Field(
        None, description="塔型（COUNTERFLOW_MECH / CROSSFLOW_MECH / NATURAL_DRAFT）"
    )
    duty_kw: float | None = Field(None, description="热负荷 kW")
    water_flow_m3h: float | None = Field(None, description="循环水量 m³/h")
    makeup_water_m3h: float | None = Field(None, description="补充水量 m³/h")
    fan_power_kw: float | None = Field(None, description="风机功率 kW")
    merkel_integral: float | None = Field(
        None, description="Merkel 积分值 KaV/L"
    )
    data_sheet_json: dict | None = Field(
        None, description="PCS-DICT-007 SUP-012 §3 14 子结构 data sheet"
    )
    input_json: dict | None = Field(None, description="入参")
    output_json: dict | None = Field(None, description="出参")


class CoolTowerResultResponse(BaseModel):
    """CoolingTowerResult 单条响应（GET /cool-tower/results/{id} 与
    POST 201 body）。

    字段：溯源（id / project_id / workspace_id / tag_number /
    standard_profile_code / calc_type / sign_status / record_hash）+
    10 业务字段 + 时间戳。

    字段映射（ORM → schema）：
    - ORM cooling_tower_id → schema id（PK 重命名；前端统一用 id）
    """

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="ignore"
    )

    id: uuid.UUID = Field(..., description="cooling_tower_results.cooling_tower_id（PK）")
    project_id: uuid.UUID = Field(..., description="项目 ID")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    tag_number: str = Field(..., description="位号")
    standard_profile_code: str = Field(..., description="项目标准")
    calc_type: str = Field(..., description="计算类型")
    sign_status: str = Field(..., description="签审状态 9 态")
    record_hash: str | None = Field(
        None, description="record_hash（ADR-0028 §决策 4 reflection；16 hex）"
    )
    # 10 业务字段
    tower_type: str | None = Field(None, description="塔型")
    duty_kw: float | None = Field(None, description="热负荷 kW")
    water_flow_m3h: float | None = Field(None, description="循环水量 m³/h")
    makeup_water_m3h: float | None = Field(None, description="补充水量 m³/h")
    fan_power_kw: float | None = Field(None, description="风机功率 kW")
    merkel_integral: float | None = Field(
        None, description="Merkel 积分值 KaV/L"
    )
    data_sheet_json: dict | None = Field(
        None, description="PCS-DICT-007 SUP-012 §3 14 子结构 data sheet"
    )
    input_json: dict | None = Field(None, description="入参")
    output_json: dict | None = Field(None, description="出参")

    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    @model_validator(mode="before")
    @classmethod
    def _from_orm_rename(cls, data: Any) -> Any:
        """ORM → schema 字段映射：ORM cooling_tower_id → schema id。

        支持 dict 输入（来自 model_validate(record, from_attributes=True) 透传
        的 ORM 属性访问）；attr 输入（record.xxx）也走同样的 getattr。
        """
        if data is None:
            return data
        cooling_tower_id = getattr(data, "cooling_tower_id", None)
        if cooling_tower_id is not None and not isinstance(data, dict):
            try:
                data.id = cooling_tower_id  # noqa: B010
            except AttributeError:
                # 不可 set（如 MagicMock 已被 frozen）→ 转 dict 处理
                if hasattr(data, "__dict__"):
                    d = dict(data.__dict__)
                    d["id"] = cooling_tower_id
                    return d
        return data


class CoolTowerResultListResponse(BaseModel):
    """CoolingTowerResult 列表响应（GET /cool-tower/results）。

    字段：
    - items: CoolTowerResultResponse 列表
    - total: 命中条数（受 sign_status_filter 影响；OBSOLETE 等门禁态被过滤）
    - limit / offset: 分页参数回显
    """

    items: list[CoolTowerResultResponse] = Field(
        ..., description="CoolingTowerResult 列表"
    )
    total: int = Field(..., description="命中条数（默认 DRAFT/CHECKED filter）")
    limit: int = Field(..., description="分页上限")
    offset: int = Field(..., description="分页偏移")


__all__ = [
    "HeatLoadAggregatorRequest",
    "HeatLoadAggregatorResponse",
    "FanPowerRequest",
    "FanPowerResponse",
    "WaterBalanceRequest",
    "WaterBalanceResponse",
    "CoolTowerResultCreateRequest",
    "CoolTowerResultUpdateRequest",
    "CoolTowerResultResponse",
    "CoolTowerResultListResponse",
]