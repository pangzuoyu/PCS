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
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

# 6 calc 公共请求基础字段（Kelvin / RH / P_pa）：
# ASHRAE RP-1845 约定输入用 K / Pa；为方便前端使用，schema 用 °C 接收，
# endpoint 内部 +273.15 转 K 喂给 chedl_wrapper 6 函数。
_C_TO_K_OFFSET = 273.15

# 饱和水含量（§3.2.5 P6-PSY-001 子项 7 — P6-4 Task 4 C-17 显式水含量）
# 压力单位约定 kPa（公制 SI 默认；Imperial 转换由前端处理或调用方入参前换算）
_KPA_PER_PA = 0.001

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
      ENTHALPY / SPECIFIC_VOLUME / COOLING_COIL / SATURATION_W_CALC；
      String(32) NOT NULL）
    - sign_status: 签审状态（默认 DRAFT）

    16 业务字段（PsychroResult __table__ 排除 PK + mixin 字段）：
    - coolprop_version: CoolProp 版本（payload 缺时 service 自动从
      get_coolprop_version() 写入；SPEC §3.2.5 coolprop_version 溯源）
    - humidity_ratio_kg_kg / dew_point_c / wet_bulb_c / enthalpy_kj_kg /
      specific_volume_m3_kg / sensible_heat_kw / latent_heat_kw
    - P6-4 Task 4 C-17 4 列：
      saturation_w_kg_kg / saturation_w_mg_sm3 /
      saturation_w_lb_per_mmscf / saturation_T_c
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
            "SPECIFIC_VOLUME / COOLING_COIL / SATURATION_W_CALC）"
        ),
    )
    sign_status: str = Field(
        "DRAFT",
        description=(
            "签审状态（DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / "
            "STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE）"
        ),
    )

    # 16 业务字段（按 ORM 列名平铺；service layer **payload 喂给 ORM）
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
    # P6-4 Task 4 (C-17) — 饱和水含量 4 业务列
    saturation_w_kg_kg: float | None = Field(
        None, description="饱和水含量 kg 水/kg 干空气（SATURATION_W_CALC 专用）",
    )
    saturation_w_mg_sm3: float | None = Field(
        None, description="饱和水含量 mg 水/Sm³ 干空气（SATURATION_W_CALC；西欧常用）",
    )
    saturation_w_lb_per_mmscf: float | None = Field(
        None, description="饱和水含量 lb 水/MMscf 干空气（SATURATION_W_CALC；北美常用）",
    )
    saturation_T_c: float | None = Field(
        None, description="饱和温度 °C（SATURATION_W_CALC；service 入参回显）",
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
    # P6-4 Task 4 (C-17) — 饱和水含量 4 业务列
    saturation_w_kg_kg: float | None = Field(
        None, description="饱和水含量 kg 水/kg 干空气（SATURATION_W_CALC 专用）",
    )
    saturation_w_mg_sm3: float | None = Field(
        None, description="饱和水含量 mg 水/Sm³ 干空气（SATURATION_W_CALC；西欧常用）",
    )
    saturation_w_lb_per_mmscf: float | None = Field(
        None, description="饱和水含量 lb 水/MMscf 干空气（SATURATION_W_CALC；北美常用）",
    )
    saturation_T_c: float | None = Field(
        None, description="饱和温度 °C（SATURATION_W_CALC；service 入参回显）",
    )
    input_json: dict | None = Field(None, description="入参（业务子结构）")
    output_json: dict | None = Field(None, description="出参（业务子结构）")


class PsychroResultResponse(BaseModel):
    """PsychroResult 单条响应（GET /psychro/results/{id} 与 POST 201 body）。

    字段：溯源（id / project_id / workspace_id / tag_number /
    standard_profile_code / calc_type / coolprop_version / sign_status /
    record_hash）+ 14 业务字段 + 时间戳。

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
    # 14 业务字段（含 P6-4 Task 4 C-17 4 列）
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
    saturation_w_kg_kg: float | None = Field(
        None, description="饱和水含量 kg 水/kg 干空气（SATURATION_W_CALC 专用）",
    )
    saturation_w_mg_sm3: float | None = Field(
        None, description="饱和水含量 mg 水/Sm³ 干空气（SATURATION_W_CALC；西欧常用）",
    )
    saturation_w_lb_per_mmscf: float | None = Field(
        None, description="饱和水含量 lb 水/MMscf 干空气（SATURATION_W_CALC；北美常用）",
    )
    saturation_T_c: float | None = Field(
        None, description="饱和温度 °C（SATURATION_W_CALC；service 入参回显）",
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


# ============================================================================
# 8. 饱和水含量（§3.2.5 P6-PSY-001 §3.9.2 — P6-4 Task 4 C-17 显式水含量）
# ============================================================================


class SaturationWaterContentRequest(BaseModel):
    """饱和水含量请求（POST /psychro/saturation-water-content/calculate）。

    字段（按 SPEC §3.2.5 P6-PSY-001 §3.9.2 显式水含量）：
    - temperature_c: 干球温度 °C（SPEC 安全范围 -50~100°C；超界返 WARNING）
    - pressure_kpa: 大气压力 kPa（默认海平面 101.325；> 0）
    - acidic_gas_composition: 酸性气摩尔分率 dict（None → 无校正；ISO 18453
      简式校正仅在 CO2+H2S > 40 mol% 时触发）
    - units: 单位制（"METRIC" 公制 SI / "IMPERIAL" 英制；不影响算法，仅标注）
    """

    temperature_c: float = Field(
        ...,
        gt=-273.15,
        description=(
            "干球温度 °C（SPEC §3.2.5 安全范围 -50~100°C；超界返 WARNING + NaN）"
        ),
    )
    pressure_kpa: float = Field(
        101.325,
        gt=0,
        description=(
            "大气压力 kPa（默认海平面 101.325；> 0；超出 CoolProp 上限 ~100 atm 返 WARNING）"
        ),
    )
    acidic_gas_composition: dict[str, float] | None = Field(
        None,
        description=(
            "酸性气摩尔分率 dict（如 {\"CO2\": 0.30, \"H2S\": 0.20}）；"
            "None → 无校正；ISO 18453 简式校正仅在 CO2+H2S > 40 mol% 时触发"
        ),
    )
    units: str = Field(
        "METRIC",
        description="单位制（METRIC 公制 SI / IMPERIAL 英制；不影响算法，仅标注）",
    )


class SaturationWaterContentResponse(BaseModel):
    """饱和水含量响应（POST /psychro/saturation-water-content/calculate）。

    字段（按 SPEC §3.2.5 P6-PSY-001 §3.9.2）：
    - saturation_w_kg_kg: 饱和水含量 kg 水 / kg 干空气（摩尔比）
    - saturation_w_mg_sm3: 饱和水含量 mg 水 / Sm³ 干空气（西欧常用）
    - saturation_w_lb_per_mmscf: 饱和水含量 lb 水 / MMscf 干空气（北美常用）
    - saturation_T_c: 计算时实际使用的干球温度 °C
    - temperature_out_of_range: True/False（< -50°C 或 > 100°C）
    - warning_message: 越界警告（None 表示无警告）
    - acidic_gas_correction_applied: True/False（CO2+H2S > 40 mol%）
    - acidic_gas_correction_factor: ISO 18453 简式校正系数（默认 1.0）
    - formula_ref: 公式溯源标记 "ASHRAE_RP-1845_CoolProp"
    """

    saturation_w_kg_kg: float = Field(
        ..., description="饱和水含量 kg 水 / kg 干空气"
    )
    saturation_w_mg_sm3: float = Field(
        ..., description="饱和水含量 mg 水 / Sm³ 干空气"
    )
    saturation_w_lb_per_mmscf: float = Field(
        ..., description="饱和水含量 lb 水 / MMscf 干空气"
    )
    saturation_T_c: float = Field(
        ..., description="计算时实际使用的干球温度 °C"
    )
    temperature_out_of_range: bool = Field(
        ..., description="是否超出 SPEC §3.2.5 安全范围 [-50, 100]°C"
    )
    warning_message: str | None = Field(
        None, description="越界警告（None 表示无警告；CoolProp 拒绝时含错误细节）"
    )
    acidic_gas_correction_applied: bool = Field(
        ..., description="是否应用 ISO 18453 简式酸性气校正（CO2+H2S > 40 mol%）"
    )
    acidic_gas_correction_factor: float = Field(
        ..., description="ISO 18453 简式校正系数（默认 1.0；上限 1.05）"
    )
    formula_ref: str = Field(
        ..., description="公式溯源标记（ASHRAE_RP-1845_CoolProp）"
    )


# ============================================================================
# 9. P6-6A-6 (Ruling 5 closure, v4) FULL 甘醇脱水系统（SPEC §3.9.1）
# ============================================================================


class GlycolDehydrationRequest(BaseModel):
    """FULL 甘醇脱水系统请求（POST /psychro/glycol-dehydration/calculate）。

    字段（按 SPEC §3.9.1 + GPSA §20.4；P6-6A-6 v5.1 Ruling 5 closure）：

    - 既有 8 必填：gas_flow / inlet / outlet / tray_count / circulation /
      glycol_type / relative_volatility / imperial_units
    - 10 optional（v4 新增 acid gas）：temperature_f / pressure_psia /
      lean_glycol_concentration / vapour_space_ft / sump_height_ft /
      hetp_ft / approach_to_equilibrium_f / flooding_c_sb /
      co2_mol_pct / h2s_mol_pct
    """

    gas_flow_mmscfd: float = Field(
        ..., gt=0, le=500, description="干气流量 MMscf/day（>0；<=500）"
    )
    inlet_water_content_lb_per_mmscf: float = Field(
        ...,
        gt=0,
        le=100,
        description="入口水含量 lb water / MMscf dry gas（>0；<=100）",
    )
    outlet_water_content_lb_per_mmscf: float = Field(
        ...,
        ge=0,
        lt=100,
        description="出口水含量 lb water / MMscf dry gas（>=0 且 < inlet；<100）",
    )
    contactor_tray_count: int = Field(
        ..., ge=1, le=50, description="接触塔实际塔盘数（>=1；<=50）"
    )
    glycol_circulation_rate_gpm: float = Field(
        ...,
        gt=0,
        le=100,
        description="甘醇循环量 gal/min（GPSA 经验 3 gpm/MMscf；>0；<=100）",
    )
    glycol_type: Literal["TEG", "DEG"] = Field(
        "TEG",
        description="甘醇类型（TEG 三甘醇；DEG 二甘醇 — FULL system v5.1 Ruling 5 DEG 不支持）",
    )
    relative_volatility: float = Field(
        4.5,
        gt=1.0,
        le=50.0,
        description="TEG/H2O 相对挥发度 α（典型 4.5；DEG 较低 2.8；>1；<=50）",
    )
    imperial_units: bool = Field(
        False,
        description="True → dual-unit 输出（tegloss_gal_d + diameter_ft）；False → SI 基准仅",
    )
    # P6-6A-6 v5.1 — 10 optional（API 默认值 = dataclass 默认值 一一对应）
    temperature_f: float | None = Field(
        None,
        ge=60,
        le=200,
        description="接触塔温度 °F（Behr 反函数 / stripping gas 用；60~200）",
    )
    pressure_psia: float | None = Field(
        None,
        ge=14.7,
        le=3000,
        description="接触塔压力 psia（Behr 反函数 / stripping gas 用；14.7~3000）",
    )
    lean_glycol_concentration: float = Field(
        0.99,
        ge=0.95,
        le=0.999,
        description="贫甘醇浓度 质量分率（0.95~0.999；默认 0.99）",
    )
    vapour_space_ft: float | None = Field(
        None, ge=0, le=30, description="蒸汽空间 ft（column height 增量；0~30）"
    )
    sump_height_ft: float | None = Field(
        None, ge=0, le=20, description="集液段高度 ft（column height 增量；0~20）"
    )
    hetp_ft: float | None = Field(
        None,
        ge=1.0,
        le=20.0,
        description="等板高度 ft（column height = NTU × HETP；1.0~20.0）",
    )
    approach_to_equilibrium_f: float = Field(
        5.0,
        ge=0,
        le=20,
        description="露点接近度 °F（adjusted dewpoint；GPSA §20.4 typical 5.0）",
    )
    flooding_c_sb: float = Field(
        0.65,
        ge=0.30,
        le=0.80,
        description="Souders-Brown C_sb（v5.1 预留，v5 helper 不使用 — ADR-0045 Rev A；0.30~0.80）",
    )
    co2_mol_pct: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="CO2 摩尔百分比（acid gas correction；0~100；v4 新增 H-1）",
    )
    h2s_mol_pct: float = Field(
        0.0,
        ge=0.0,
        le=100.0,
        description="H2S 摩尔百分比（acid gas correction；0~100；v4 新增 H-1）",
    )
    # P6-8 T5 — OPEN-P6-6A-6 集成 2 optional inputs（向后兼容；默认值与 T1 helper 一致）
    reboiler_temperature_f: float = Field(
        400.0,
        ge=300.0,
        le=450.0,
        description="再沸器温度 °F（T1 完整焓平衡 + T4 GPSA Fig 20-4 用；默认 400.0；300~450）",
    )
    teg_circulation_rate_gal_lb: float | None = Field(
        None,
        gt=0,
        description="TEG 循环量 gal/lb 水（None → service 由 glycol_circulation_rate_gpm 推导）",
    )


class GlycolDehydrationResponse(BaseModel):
    """FULL 甘醇脱水系统响应（POST /psychro/glycol-dehydration/calculate）。

    字段（v4 Ruling 5 closure）：
    - 既有 8 字段（dehydration_efficiency / n_tray_minimum / is_tray_count_ok /
      teg_loss_gpd / contactor_diameter_in / imperial_conversion / formula_ref /
      glycol_type）
    - 12 optional（v4 含 acid_gas_corrected）：water_dewpoint_f /
      adjusted_dewpoint_f / lean_glycol_concentration /
      stripping_gas_scf_per_gal_teg / column_diameter_full_in /
      column_height_ft / number_of_transfer_units / mass_h2o_removed_lb_s /
      reboiler_duty_btu_hr / column_csa_ft2 / dewpoint_unavailable_reason /
      acid_gas_corrected
    """

    dehydration_efficiency: float = Field(
        ..., description="脱水效率 η = 1 - outlet/inlet（无量纲 0..1）"
    )
    n_tray_minimum: int = Field(
        ..., description="最小塔盘数（GPSA §20.4 Eq.20-4，含 L/V 修正）"
    )
    is_tray_count_ok: bool = Field(
        ..., description="实际塔盘数 ≥ N_min（bool）"
    )
    teg_loss_gpd: float = Field(
        ..., description="TEG 损失 gal/day（GPSA 经验 0.5 × Q）"
    )
    contactor_diameter_in: float = Field(
        ..., description="接触塔直径 inch（GPSA 经验 + L/V 修正）"
    )
    imperial_conversion: dict[str, float] | None = Field(
        None,
        description="dual-unit 输出（仅 imperial_units=True；None → 仅 SI）",
    )
    formula_ref: dict[str, str] = Field(
        ..., description="公式引用（GPSA §20.4 Eq.20-4 等）"
    )
    glycol_type: str = Field(
        ..., description="甘醇类型回显（TEG / DEG）"
    )
    # P6-6A-6 v5.1 — 12 optional fields（v4 含 acid_gas_corrected）
    water_dewpoint_f: float | None = Field(
        None,
        description="水的露点 °F（Behr 反函数；T<60°F 标记 extrapolated）",
    )
    adjusted_dewpoint_f: float | None = Field(
        None,
        description="调整后露点 °F（diff method；缺 T/P 时 None）",
    )
    lean_glycol_concentration: float = Field(
        ...,
        description="贫甘醇浓度回显（service 计算值；输入为 None 时使用 service 默认）",
    )
    stripping_gas_scf_per_gal_teg: float | None = Field(
        None,
        description="汽提气率 SCF/gal TEG（GPSA §20.4 Eq.20-5）",
    )
    column_diameter_full_in: float = Field(
        ...,
        description="接触塔全径 inch（K=7.1187 单点标定 ADR-0045 Rev A）",
    )
    column_height_ft: float = Field(
        ...,
        description="接触塔高度 ft（NTU × HETP + vapour space + sump）",
    )
    number_of_transfer_units: float = Field(
        ..., description="传质单元数 NTU（Kremser）"
    )
    mass_h2o_removed_lb_s: float = Field(
        ..., description="脱水速率 lb/s"
    )
    reboiler_duty_btu_hr: float = Field(
        ..., description="再沸器负荷 BTU/hr（简式焓平衡 3 项）"
    )
    column_csa_ft2: float = Field(
        ..., description="截面积 ft²"
    )
    dewpoint_unavailable_reason: str | None = Field(
        None,
        description="dewpoint 不可用原因（如缺 T/P 时填 'temperature_f required'）",
    )
    acid_gas_corrected: bool = Field(
        False,
        description="acid gas correction 是否生效（v4 新增 H-1；CO2 或 H2S > 0 时 True）",
    )
    # P6-8 T5 — OPEN-P6-6A-6 集成 4 outputs + WARNING 字段
    reboiler_duty_kw: float | None = Field(
        None,
        description="Reboiler Duty (kW); 1 BTU/hr = 0.000293071 kW",
    )
    stripping_gas_rate_scf_gal: float | None = Field(
        None,
        description="Stripping Gas Rate (scf/gal TEG); GPSA §20.4 Eq.20-5 + Antoine v5 plan",
    )
    lean_glycol_concentration_wt_pct: float | None = Field(
        None,
        description="Lean Glycol Concentration (wt%); GPSA Fig 20-4 4 数据点 + 插值",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="工艺未对账 warning 列表（如 TEG_CIRCULATION_RATE_UNVERIFIED 等）",
    )


# ============================================================================
# 10. P6-7 OPEN-P6-6A-11 — Hydrate gas composition schema v2
# ============================================================================


# 水合物抑制剂类型（与 services/psychro/hydrate_inhibition_service 字段一致）
_InhibitorType = Literal["MEOH", "EG", "DEG", "TEG", "NACL"]

# 支持的水合物形成组分（Nielsen 1988 Table 2-3）
HydrateGasComponent = Literal[
    "CH4", "C2H6", "C3H8", "i_C4H10", "N2", "CO2", "H2S"
]


class HydrateGasComposition(BaseModel):
    """水合物形成气体组分（Nielsen 1988 Table 2-3 组分库）。

    用于水合物抑制计算的组分加权（secondary correction）。
    工艺室 2026-10-15 签署（P6-7 OPEN-P6-6A-11）。

    默认 CH4=1.0 即纯甲烷（向后兼容 — 现有调用方无 breaking change）。
    """

    CH4: float = Field(1.0, ge=0.0, le=1.0, description="甲烷摩尔分数（默认纯甲烷）")
    C2H6: float = Field(0.0, ge=0.0, le=1.0, description="乙烷摩尔分数")
    C3H8: float = Field(0.0, ge=0.0, le=1.0, description="丙烷摩尔分数")
    i_C4H10: float = Field(0.0, ge=0.0, le=1.0, description="异丁烷摩尔分数")
    N2: float = Field(0.0, ge=0.0, le=1.0, description="氮气摩尔分数")
    CO2: float = Field(0.0, ge=0.0, le=1.0, description="二氧化碳摩尔分数")
    H2S: float = Field(0.0, ge=0.0, le=1.0, description="硫化氢摩尔分数")

    @model_validator(mode="after")
    def validate_sum_to_one(self) -> HydrateGasComposition:
        """校验 7 组分摩尔分数之和 = 1.0 ± 0.001。"""
        total = (
            self.CH4 + self.C2H6 + self.C3H8 + self.i_C4H10
            + self.N2 + self.CO2 + self.H2S
        )
        if not (0.999 <= total <= 1.001):
            raise ValueError(
                f"组分摩尔分数之和={total:.4f}，必须 = 1.0 ± 0.001"
            )
        return self


class HydrateInhibitionInput(BaseModel):
    """水合物抑制输入（Pydantic schema — P6-7 OPEN-P6-6A-11 schema v2）。

    与 services/psychro/hydrate_inhibition_service.HydrateInhibitionInput dataclass
    字段保持一致；T3 service 集成时由 API 层 Pydantic → dataclass 转换。

    新增字段：``gas_composition``（P6-7 OPEN-P6-6A-11；默认纯 CH4，向后兼容）。
    """

    gas_flow_mmscfd: float = Field(
        ..., gt=0, le=500, description="干气流量 MMscf/day（>0；<=500）"
    )
    operating_pressure_psia: float = Field(
        ..., gt=0, description="操作压力 psia（>0）"
    )
    operating_temperature_f: float = Field(
        ..., description="操作温度 °F（仅用于记录）"
    )
    hydrate_inhibitor_type: _InhibitorType = Field(
        ..., description="抑制剂类型（MEOH/EG/DEG/TEG/NACL）"
    )
    inhibitor_concentration_in_water_wt_pct: float = Field(
        ...,
        gt=0,
        lt=100,
        description="抑制剂在水溶液中的质量分数 wt%（>0 且 <100）",
    )
    water_content_inlet_lb_per_mmscf: float = Field(
        20.0,
        ge=0,
        le=100,
        description="入口水含量 lb water/MMscf dry gas（默认 20.0；>=0；<=100）",
    )
    water_content_target_lb_per_mmscf: float = Field(
        1.0,
        ge=0,
        lt=100,
        description="目标出口水含量 lb water/MMscf dry gas（默认 1.0；>=0；<100）",
    )
    imperial_units: bool = Field(
        False,
        description=(
            "True → dual-unit 输出（hydrate_depression_f + injection_rate_gal_d）；"
            "False（默认，L-3 v1 BLOCKER）→ SI 基准仅"
        ),
    )
    gas_composition: HydrateGasComposition = Field(
        default_factory=lambda: HydrateGasComposition(CH4=1.0),
        description="水合物形成气体组分（默认纯甲烷；富 C2H6/C3H8 气田可扩展）",
    )


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
    # 饱和水含量（P6-4 Task 4 / C-17 显式水含量）
    "SaturationWaterContentRequest",
    "SaturationWaterContentResponse",
    # P6-6A-6 (Ruling 5 closure, v4) FULL 甘醇脱水系统
    "GlycolDehydrationRequest",
    "GlycolDehydrationResponse",
    # CRUD
    "PsychroResultCreateRequest",
    "PsychroResultUpdateRequest",
    "PsychroResultResponse",
    "PsychroResultListResponse",
    # P6-7 OPEN-P6-6A-11 — 水合物气体组分 schema v2
    "HydrateGasComponent",
    "HydrateGasComposition",
    "HydrateInhibitionInput",
]
