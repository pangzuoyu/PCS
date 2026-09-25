"""PSYCHRO Pydantic 请求/响应模型（P6-2 Task 26）。

按 Pydantic v2 + OpenAPI 一致性要求：
- 所有字段带 Field description（中文）+ example
- 默认值与 SPEC §3.2.5 P6-PSY-001 保守口径一致

端点（Task 26）：
- POST /api/v1/psychro/humidity-ratio:
    req HumidityRatioRequest / resp HumidityRatioResponse
- POST /api/v1/psychro/dew-point:
    req DewPointRequest / resp DewPointResponse
- POST /api/v1/psychro/wet-bulb:
    req WetBulbRequest / resp WetBulbResponse
- POST /api/v1/psychro/enthalpy:
    req EnthalpyRequest / resp EnthalpyResponse
- POST /api/v1/psychro/specific-volume:
    req SpecificVolumeRequest / resp SpecificVolumeResponse
- POST /api/v1/psychro/cooling-coil:
    req CoolingCoilRequest / resp CoolingCoilResponse
- CRUD /api/v1/psychro/results:
    Create/Update/Response/ListResponse
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 6 calc 公共请求基础字段（Kelvin / RH / P_pa）：
# ASHRAE RP-1845 约定输入用 K / Pa；为方便前端使用，schema 用 °C 接收，
# endpoint 内部 +273.15 转 K 喂给 chedl_wrapper 6 函数。
_C_TO_K_OFFSET = 273.15

# ============================================================================
# 1. humidity-ratio（§3.2.5 P6-PSY-001 子项 1）
# ============================================================================


class HumidityRatioRequest(BaseModel):
    """湿度比请求（POST /psychro/humidity-ratio）。

    字段（按 SPEC §3.2.5 P6-PSY-001）：
    - t_c: 干球温度 °C（>-273.15）
    - rh: 相对湿度（0~1）
    - p_pa: 大气压力 Pa（>0；默认海平面 101325）
    """

    t_c: float = Field(
        ..., gt=-273.15, description="干球温度 °C（华氏参考 0~50°C）"
    )
    rh: float = Field(
        ..., ge=0.0, le=1.0, description="相对湿度（无量纲，0~1）"
    )
    p_pa: float = Field(
        101325.0, gt=0, description="大气压力 Pa（默认海平面 101325）"
    )


class HumidityRatioResponse(BaseModel):
    """湿度比响应（POST /psychro/humidity-ratio）。

    字段：
    - humidity_ratio_kg_kg: 湿度比 W（kg 水 / kg 干空气）
    - formula_ref: 公式溯源标记 "ASHRAE_RP-1845_CoolProp"
    """

    humidity_ratio_kg_kg: float = Field(..., description="湿度比 kg/kg")
    formula_ref: str = Field(
        ..., description="公式溯源标记（ASHRAE_RP-1845_CoolProp）"
    )


# ============================================================================
# 2. dew-point（§3.2.5 P6-PSY-001 子项 2）
# ============================================================================


class DewPointRequest(BaseModel):
    """露点请求（POST /psychro/dew-point）。"""

    t_c: float = Field(..., gt=-273.15, description="干球温度 °C")
    rh: float = Field(..., ge=0.0, le=1.0, description="相对湿度 0~1")
    p_pa: float = Field(
        101325.0, gt=0, description="大气压力 Pa（默认 101325）"
    )


class DewPointResponse(BaseModel):
    """露点响应（POST /psychro/dew-point）。

    字段：
    - dew_point_c: 露点温度 °C（chedl_wrapper 返回 K，本响应减 273.15）
    - formula_ref: 公式溯源标记
    """

    dew_point_c: float = Field(..., description="露点温度 °C")
    formula_ref: str = Field(
        ..., description="公式溯源标记（ASHRAE_RP-1845_CoolProp）"
    )


# ============================================================================
# 3. wet-bulb（§3.2.5 P6-PSY-001 子项 3）
# ============================================================================


class WetBulbRequest(BaseModel):
    """湿球请求（POST /psychro/wet-bulb）。"""

    t_c: float = Field(..., gt=-273.15, description="干球温度 °C")
    rh: float = Field(..., ge=0.0, le=1.0, description="相对湿度 0~1")
    p_pa: float = Field(
        101325.0, gt=0, description="大气压力 Pa（默认 101325）"
    )


class WetBulbResponse(BaseModel):
    """湿球响应（POST /psychro/wet-bulb）。

    字段：
    - wet_bulb_c: 湿球温度 °C（等焓饱和温度近似）
    - formula_ref: 公式溯源标记
    """

    wet_bulb_c: float = Field(..., description="湿球温度 °C")
    formula_ref: str = Field(
        ..., description="公式溯源标记（ASHRAE_RP-1845_CoolProp）"
    )


# ============================================================================
# 4. enthalpy（§3.2.5 P6-PSY-001 子项 4）
# ============================================================================


class EnthalpyRequest(BaseModel):
    """比焓请求（POST /psychro/enthalpy）。

    字段：
    - t_c: 干球温度 °C
    - rh: 相对湿度 0~1
    - p_pa: 大气压力 Pa（默认 101325）
    """

    t_c: float = Field(..., gt=-273.15, description="干球温度 °C")
    rh: float = Field(..., ge=0.0, le=1.0, description="相对湿度 0~1")
    p_pa: float = Field(
        101325.0, gt=0, description="大气压力 Pa（默认 101325）"
    )


class EnthalpyResponse(BaseModel):
    """比焓响应（POST /psychro/enthalpy）。

    字段：
    - enthalpy_kj_kg: 比焓 kJ/kg dry air（chedl_wrapper 返回 J/kg，本响应 ÷1000）
    - formula_ref: 公式溯源标记
    """

    enthalpy_kj_kg: float = Field(..., description="比焓 kJ/kg dry air")
    formula_ref: str = Field(
        ..., description="公式溯源标记（ASHRAE_RP-1845_CoolProp）"
    )


# ============================================================================
# 5. specific-volume（§3.2.5 P6-PSY-001 子项 5）
# ============================================================================


class SpecificVolumeRequest(BaseModel):
    """比容请求（POST /psychro/specific-volume）。"""

    t_c: float = Field(..., gt=-273.15, description="干球温度 °C")
    rh: float = Field(..., ge=0.0, le=1.0, description="相对湿度 0~1")
    p_pa: float = Field(
        101325.0, gt=0, description="大气压力 Pa（默认 101325）"
    )


class SpecificVolumeResponse(BaseModel):
    """比容响应（POST /psychro/specific-volume）。

    字段：
    - specific_volume_m3_kg: 比容 m³/kg dry air
    - formula_ref: 公式溯源标记
    """

    specific_volume_m3_kg: float = Field(..., description="比容 m³/kg dry air")
    formula_ref: str = Field(
        ..., description="公式溯源标记（ASHRAE_RP-1845_CoolProp）"
    )


# ============================================================================
# 6. cooling-coil（§3.2.5 P6-PSY-001 子项 6）
# ============================================================================


class CoolingCoilRequest(BaseModel):
    """冷却盘管显热/潜热请求（POST /psychro/cooling-coil）。

    字段（按 ASHRAE Handbook Fundamentals 2021 §1.2 拆分）：
    - t1_c / t2_c: 入口/出口干球温度 °C
    - rh1 / rh2: 入口/出口相对湿度 0~1
    - p_pa: 大气压力 Pa（默认 101325）
    - q_air_m3_s: 体积风量 m³/s（>0）
    """

    t1_c: float = Field(..., gt=-273.15, description="入口干球温度 °C")
    rh1: float = Field(..., ge=0.0, le=1.0, description="入口相对湿度 0~1")
    t2_c: float = Field(..., gt=-273.15, description="出口干球温度 °C")
    rh2: float = Field(..., ge=0.0, le=1.0, description="出口相对湿度 0~1")
    p_pa: float = Field(
        101325.0, gt=0, description="大气压力 Pa（默认 101325）"
    )
    q_air_m3_s: float = Field(..., gt=0, description="体积风量 m³/s")


class CoolingCoilResponse(BaseModel):
    """冷却盘管显热/潜热响应（POST /psychro/cooling-coil）。

    字段：
    - sensible_heat_kw: 显热 kW（m_dot × Q_sensible / 1000）
    - latent_heat_kw: 潜热 kW（m_dot × Q_latent / 1000）
    - formula_ref: 公式溯源标记
    """

    sensible_heat_kw: float = Field(..., description="显热 kW")
    latent_heat_kw: float = Field(..., description="潜热 kW")
    formula_ref: str = Field(
        ..., description="公式溯源标记（ASHRAE_HF2021_§1.2）"
    )


# ============================================================================
# 7. PsychroResult CRUD
# ============================================================================


class PsychroResultCreateRequest(BaseModel):
    """PsychroResult 创建请求（POST /psychro/results）。

    字段按 PsychroResult ORM 列名（Task 18，P6-2 实施）平铺 ——
    ``save_psychro_result`` service 直接 ``**payload`` 喂给 ORM，
    字段名必须与列名严格一致：

    - project_id: 项目 ID（RecordMixin FK → projects.project_id）
    - workspace_id: 工作区 ID（业务隔离）
    - tag_number: 位号（TaggedRecordMixin NOT NULL；项目内唯一）
    - standard_profile_code: 项目标准（默认 "ASHRAE_FUND_2021"；
      C-07 String(16) 锁定）
    - calc_type: 计算类型（HUMIDITY_RATIO / DEW_POINT / WET_BULB /
      ENTHALPY / SPECIFIC_VOLUME / COOLING_COIL；String(32) NOT NULL）
    - sign_status: 签审状态（默认 DRAFT）

    12 业务字段（PsychroResult __table__ 排除 PK + mixin 字段）：
    - coolprop_version: CoolProp 版本（payload 缺时 service 自动从
      get_coolprop_version() 写入；SPEC §3.2.5 coolprop_version 溯源）
    - humidity_ratio_kg_kg / dew_point_c / wet_bulb_c / enthalpy_kj_kg /
      specific_volume_m3_kg / sensible_heat_kw / latent_heat_kw
    - input_json / output_json
    """

    # 溯源 + 隔离（mixin 必填）
    project_id: uuid.UUID = Field(..., description="项目 ID（FK → projects）")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID（业务隔离）")
    tag_number: str = Field(
        ..., min_length=1, max_length=50, description="位号（TaggedRecordMixin NOT NULL）"
    )
    standard_profile_code: str = Field(
        "ASHRAE_FUND_2021",
        description="项目标准（默认 ASHRAE_FUND_2021；C-07 String(16) 锁定）",
    )
    calc_type: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description=(
            "计算类型（HUMIDITY_RATIO / DEW_POINT / WET_BULB / ENTHALPY / "
            "SPECIFIC_VOLUME / COOLING_COIL）"
        ),
    )
    sign_status: str = Field(
        "DRAFT",
        description=(
            "签审状态（DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / "
            "STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE）"
        ),
    )

    # 12 业务字段（按 ORM 列名平铺；service layer **payload 喂给 ORM）
    coolprop_version: str | None = Field(
        None,
        max_length=16,
        description=(
            "CoolProp 版本（如 '6.6.0'）；payload 缺时 service 自动从 "
            "get_coolprop_version() 写入（SPEC §3.2.5 溯源）"
        ),
    )
    humidity_ratio_kg_kg: float | None = Field(
        None, description="湿度比 kg/kg dry air"
    )
    dew_point_c: float | None = Field(None, description="露点温度 °C")
    wet_bulb_c: float | None = Field(None, description="湿球温度 °C")
    enthalpy_kj_kg: float | None = Field(None, description="比焓 kJ/kg dry air")
    specific_volume_m3_kg: float | None = Field(
        None, description="比容 m³/kg dry air"
    )
    sensible_heat_kw: float | None = Field(
        None, description="显热 kW（cooling_coil 专用）"
    )
    latent_heat_kw: float | None = Field(
        None, description="潜热 kW（cooling_coil 专用）"
    )
    input_json: dict | None = Field(None, description="入参（业务子结构）")
    output_json: dict | None = Field(None, description="出参（业务子结构）")


class PsychroResultUpdateRequest(BaseModel):
    """PsychroResult 更新请求（PATCH /psychro/results/{id}）。

    字段子集（PATCH 仅允许业务字段；不可改 sign_status / tag_number /
    溯源 / standard_profile_code / calc_type / coolprop_version 等）。
    """

    humidity_ratio_kg_kg: float | None = Field(
        None, description="湿度比 kg/kg dry air"
    )
    dew_point_c: float | None = Field(None, description="露点温度 °C")
    wet_bulb_c: float | None = Field(None, description="湿球温度 °C")
    enthalpy_kj_kg: float | None = Field(None, description="比焓 kJ/kg dry air")
    specific_volume_m3_kg: float | None = Field(
        None, description="比容 m³/kg dry air"
    )
    sensible_heat_kw: float | None = Field(
        None, description="显热 kW（cooling_coil 专用）"
    )
    latent_heat_kw: float | None = Field(
        None, description="潜热 kW（cooling_coil 专用）"
    )
    input_json: dict | None = Field(None, description="入参（业务子结构）")
    output_json: dict | None = Field(None, description="出参（业务子结构）")


class PsychroResultResponse(BaseModel):
    """PsychroResult 单条响应（GET /psychro/results/{id} 与 POST 201 body）。

    字段：溯源（id / project_id / workspace_id / tag_number /
    standard_profile_code / calc_type / coolprop_version / sign_status /
    record_hash）+ 10 业务字段 + 时间戳。

    字段映射（ORM → schema）：
    - ORM psychro_id → schema id（PK 重命名；前端统一用 id）
    """

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, extra="ignore"
    )

    id: uuid.UUID = Field(..., description="psychro_results.psychro_id（PK）")
    project_id: uuid.UUID = Field(..., description="项目 ID")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    tag_number: str = Field(..., description="位号")
    standard_profile_code: str = Field(..., description="项目标准")
    calc_type: str = Field(..., description="计算类型")
    coolprop_version: str | None = Field(
        None, description="CoolProp 版本（如 6.6.0）；record_hash 反射自动含"
    )
    sign_status: str = Field(..., description="签审状态 9 态")
    record_hash: str | None = Field(
        None, description="record_hash（ADR-0028 §决策 4 reflection；16 hex）"
    )
    # 10 业务字段
    humidity_ratio_kg_kg: float | None = Field(
        None, description="湿度比 kg/kg dry air"
    )
    dew_point_c: float | None = Field(None, description="露点温度 °C")
    wet_bulb_c: float | None = Field(None, description="湿球温度 °C")
    enthalpy_kj_kg: float | None = Field(None, description="比焓 kJ/kg dry air")
    specific_volume_m3_kg: float | None = Field(
        None, description="比容 m³/kg dry air"
    )
    sensible_heat_kw: float | None = Field(
        None, description="显热 kW（cooling_coil 专用）"
    )
    latent_heat_kw: float | None = Field(
        None, description="潜热 kW（cooling_coil 专用）"
    )
    input_json: dict | None = Field(None, description="入参（业务子结构）")
    output_json: dict | None = Field(None, description="出参（业务子结构）")

    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    @model_validator(mode="before")
    @classmethod
    def _from_orm_rename(cls, data: Any) -> Any:
        """ORM → schema 字段映射：ORM psychro_id → schema id。

        支持 dict 输入（来自 model_validate(record, from_attributes=True) 透传
        的 ORM 属性访问）；attr 输入（record.xxx）也走同样的 getattr。
        """
        if data is None:
            return data
        psychro_id = getattr(data, "psychro_id", None)
        if psychro_id is not None and not isinstance(data, dict):
            try:
                data.id = psychro_id  # noqa: B010
            except AttributeError:
                # 不可 set（如 MagicMock 已被 frozen）→ 转 dict 处理
                if hasattr(data, "__dict__"):
                    d = dict(data.__dict__)
                    d["id"] = psychro_id
                    return d
        return data


class PsychroResultListResponse(BaseModel):
    """PsychroResult 列表响应（GET /psychro/results）。

    字段：
    - items: PsychroResultResponse 列表
    - total: 命中条数（受 sign_status_filter 影响；OBSOLETE 等门禁态被过滤）
    - limit / offset: 分页参数回显
    """

    items: list[PsychroResultResponse] = Field(
        ..., description="PsychroResult 列表"
    )
    total: int = Field(..., description="命中条数（默认 DRAFT/CHECKED filter）")
    limit: int = Field(..., description="分页上限")
    offset: int = Field(..., description="分页偏移")


__all__ = [
    # 6 calc 子项
    "HumidityRatioRequest",
    "HumidityRatioResponse",
    "DewPointRequest",
    "DewPointResponse",
    "WetBulbRequest",
    "WetBulbResponse",
    "EnthalpyRequest",
    "EnthalpyResponse",
    "SpecificVolumeRequest",
    "SpecificVolumeResponse",
    "CoolingCoilRequest",
    "CoolingCoilResponse",
    # CRUD
    "PsychroResultCreateRequest",
    "PsychroResultUpdateRequest",
    "PsychroResultResponse",
    "PsychroResultListResponse",
]
