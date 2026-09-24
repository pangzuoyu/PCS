"""FLARE_SYS Pydantic 请求/响应模型。

按 Pydantic v2 + OpenAPI 一致性要求：
- 所有字段带 Field description（中文） + example
- 默认值与 API 521 §5.15.4 / §5.15.3 / §5.15.5 / §7.4.2.2 / §7.4.2.3
  保守口径一致

端点：
- Task 20：POST /api/v1/flare/header-sizing：req HeaderSizingRequest / resp HeaderSizingResponse
- Task 21：POST /api/v1/flare/kod-sizing：req KodSizingRequest / resp KodSizingResponse
- Task 22：POST /api/v1/flare/stack-design：req StackDesignRequest / resp StackDesignResponse
- Task 23：POST /api/v1/flare/tip + CRUD /api/v1/flare/results

不写 DB（header_sizing / kod_sizing / stack_design 是计算，落库由 Task 23
flare_persist 统一处理）。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


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


# ───────────────────────────── Task 21 kod_sizing ─────────────────────────────


class KodSizingRequest(BaseModel):
    """FLARE_SYS kod_sizing 请求（KOD + Water Seal 合并调用）。

    字段（按 API 521 §5.15.3 Souders-Brown + §5.15.5 Water Seal 所需输入）：

    - project_id: 项目 ID（与 Task 19/20 隔离键一致）
    - standard_profile_code: 项目标准（默认 API_521；GB/T 暂不开放）

    KOD（Souders-Brown）：
    - vapor_mass_flow_kgs: 闪蒸气质量流量 kg/s（来自 Task 19）
    - vapor_density_kg_m3: 蒸气密度 kg/m³（工况下）
    - liquid_density_kg_m3: 液滴密度 kg/m³（必须 > vapor_density 否则无气液分离）
    - k_sb_m_s: Souders-Brown 系数 m/s（默认 0.3 保守，范围 (0, 2.0]）

    Water Seal：
    - header_pressure_pa: 总管在 water seal 处压力 Pa（来自 Task 20）
    - seal_pot_pressure_pa: seal pot 下游压力 Pa（大气压常 101325）
    - water_density_kg_m3: 水封液密度 kg/m³（默认 1000 纯水）
    - gravity_m_s2: 重力加速度 m/s²（默认 9.81）
    - safety_factor: 设计安全系数（默认 1.5；API 521 推荐 1.25–2.0）
    - surge_pressure_pa: 浪涌工况额外压力 Pa（默认 0）
    """

    project_id: uuid.UUID = Field(
        ..., description="项目 ID（与 Task 19/20 隔离键一致）"
    )
    standard_profile_code: str = Field(
        "API_521", description="项目标准（API_521 / GB/T）"
    )
    # KOD 输入
    vapor_mass_flow_kgs: float = Field(
        ..., gt=0, description="闪蒸气质量流量 kg/s（来自 Task 19）"
    )
    vapor_density_kg_m3: float = Field(
        ..., gt=0, description="蒸气密度 kg/m³（工况下）"
    )
    liquid_density_kg_m3: float = Field(..., gt=0, description="液滴密度 kg/m³")
    k_sb_m_s: float = Field(
        0.3,
        gt=0,
        le=2.0,
        description="Souders-Brown 系数 m/s（典型 0.1–0.4，默认 0.3 保守）",
    )
    # Water Seal 输入
    header_pressure_pa: float = Field(
        ..., gt=0, description="总管在 water seal 处压力 Pa（来自 Task 20）"
    )
    seal_pot_pressure_pa: float = Field(
        ..., ge=0, description="seal pot 下游压力 Pa（大气压常 101325）"
    )
    water_density_kg_m3: float = Field(
        1000.0, gt=0, description="水封液密度 kg/m³（默认 1000 纯水）"
    )
    gravity_m_s2: float = Field(
        9.81, gt=0, description="重力加速度 m/s²（默认 9.81）"
    )
    safety_factor: float = Field(
        1.5,
        ge=1.0,
        description="设计安全系数（API 521 推荐 1.25–2.0，默认 1.5）",
    )
    surge_pressure_pa: float = Field(
        0.0, ge=0, description="浪涌工况额外压力 Pa（默认 0）"
    )


class WaterSealInfo(BaseModel):
    """Water Seal 子结果（API 521 §5.15.5）。"""

    h_seal_m: float = Field(..., description="最小液封高度 m")
    h_design_m: float = Field(..., description="设计液封高度 m（含 safety_factor）")
    delta_pressure_pa: float = Field(..., description="有效压差 Pa")
    formula_ref: str = Field(..., description="公式溯源标记（API_521_§5.15.5）")


class KodInfo(BaseModel):
    """KOD 子结果（API 521 §5.15.3 Souders-Brown）。"""

    diameter_m: float = Field(..., description="KOD 直径 m")
    area_m2: float = Field(..., description="KOD 流通截面积 m²")
    u_perm_m_s: float = Field(..., description="允许蒸气速度 m/s")
    u_actual_m_s: float = Field(
        ..., description="实际蒸气速度 m/s（数学恒等 u_perm，合规自检）"
    )
    limit_ratio: float = Field(
        ..., description="Souders-Brown 极限比 u_actual / u_perm（应 == 1.0）"
    )
    formula_ref: str = Field(..., description="公式溯源标记（API_521_§5.15.3）")


class KodSizingResponse(BaseModel):
    """FLARE_SYS kod_sizing 响应（KOD + Water Seal 综合）。

    字段：

    - kod: KOD 子结果（KodInfo；API 521 §5.15.3）
    - water_seal: Water Seal 子结果（WaterSealInfo；API 521 §5.15.5）
    - project_id: 回显请求 project_id（前端 audit）
    - standard_profile_code: 回显请求 standard_profile_code
    - formula_ref: 综合公式溯源标记 "API_521_§5.15.3+§5.15.5"
    """

    kod: KodInfo = Field(..., description="KOD 子结果")
    water_seal: WaterSealInfo = Field(..., description="Water Seal 子结果")
    project_id: uuid.UUID = Field(..., description="回显请求 project_id")
    standard_profile_code: str = Field(..., description="回显请求 standard_profile_code")
    formula_ref: str = Field(
        ..., description="公式溯源标记（API_521_§5.15.3+§5.15.5）"
    )


# ───────────────────────────── Task 22 stack_design ─────────────────────────────


class StackDesignRequest(BaseModel):
    """FLARE_SYS stack_design 请求（stack_height + radiation_check 合并调用）。

    字段（按 API 521 §7.4.2.2 Stack Height + §7.4.2.3 Thermal Radiation +
    BEDD 限值校验所需输入）：

    - project_id: 项目 ID（与 Task 19/20/21 隔离键一致）
    - standard_profile_code: 项目标准（默认 API_521；GB/T 暂不开放）

    Stack Height 输入（API 521 §7.4.2.2）：
    - total_heat_release_mw: 总热释放速率 MW（来自 Task 19 推导）
    - stability_class: Pasquill-Gifford 大气稳定度（A–F，默认 D 中性）
    - h_min_engineering_m: 工程最小高度 m（默认 10，范围 [5, 200]）
    - wind_speed_m_s: 设计风速 m/s（默认 5，范围 [0, 50]）

    Radiation Check 输入（API 521 §7.4.2.3 + BEDD）：
    - q_radiated_mw: 火焰辐射热释放 MW（Q_total × fraction_rad，>0）
    - receptor_distance_m: 受体距火炬底水平距离 m（property line，>0）
    - flame_height_m: 火焰长度 m（None 则自动 0.5×H_stack，ge=0）
    - tilt_angle_deg: 火焰倾斜角 度（默认 0 无风，范围 [0, 90]）
    - bedd_limit_kw_m2: BEDD 限值 kW/m²（property line 4.73 / personnel 6.31 /
      emergency 12.6，默认 4.73）
    """

    project_id: uuid.UUID = Field(
        ..., description="项目 ID（与 Task 19/20/21 隔离键一致）"
    )
    standard_profile_code: str = Field(
        "API_521", description="项目标准（API_521 / GB/T）"
    )
    # Stack Height 输入
    total_heat_release_mw: float = Field(
        ..., gt=0, description="总热释放速率 MW（来自 Task 19 aggregate_flare_load）"
    )
    stability_class: str = Field(
        "D", description="Pasquill-Gifford 大气稳定度等级（A-F，默认 D 中性）"
    )
    h_min_engineering_m: float = Field(
        10.0, ge=5.0, le=200.0, description="工程最小高度 m（默认 10，范围 [5, 200]）"
    )
    wind_speed_m_s: float = Field(
        5.0, ge=0, le=50.0, description="设计风速 m/s（默认 5，范围 [0, 50]）"
    )
    # Radiation Check 输入
    q_radiated_mw: float = Field(
        ..., gt=0, description="火焰辐射热释放 MW（Q_total × fraction_rad）"
    )
    receptor_distance_m: float = Field(
        ..., gt=0, description="受体距火炬底水平距离 m（property line）"
    )
    flame_height_m: float | None = Field(
        None, ge=0, description="火焰长度 m（None 则自动 0.5×H_stack）"
    )
    tilt_angle_deg: float = Field(
        0.0, ge=0, le=90.0, description="火焰倾斜角 度（默认 0 无风）"
    )
    bedd_limit_kw_m2: float = Field(
        4.73,
        gt=0,
        description=(
            "BEDD 限值 kW/m²（property line 4.73 / personnel 6.31 / "
            "emergency 12.6，默认 4.73）"
        ),
    )


class StackHeightInfo(BaseModel):
    """Stack Height 子结果（API 521 §7.4.2.2）。"""

    h_stack_m: float = Field(..., description="推荐火炬高度 m（max(h_min, h_eff)）")
    h_effective_m: float = Field(..., description="有效高度 m（含 dispersion_factor）")
    buoyancy_rise_m: float = Field(
        ..., description="浮升抬升 ΔH_buoy m（1.5 × √Q_total）"
    )
    dispersion_factor: float = Field(
        ..., description="Pasquill-Gifford 修正因子（依 stability_class）"
    )
    formula_ref: str = Field(..., description="公式溯源标记（API_521_§7.4.2.2）")


class RadiationCheckInfo(BaseModel):
    """Radiation Check 子结果（API 521 §7.4.2.3 + BEDD）。"""

    q_at_receptor_w_m2: float = Field(..., description="受体处辐射强度 W/m²")
    q_at_receptor_kw_m2: float = Field(..., description="受体处辐射强度 kW/m²（常用）")
    bedd_compliant: bool = Field(
        ..., description="是否满足 BEDD 限值（True = q ≤ bedd_limit）"
    )
    bedd_limit_kw_m2: float = Field(..., description="BEDD 限值 kW/m²（输入阈值）")
    flame_center_height_m: float = Field(..., description="火焰中心高度 m")
    slant_distance_m: float = Field(..., description="受体处斜距 R m")
    formula_ref: str = Field(
        ..., description="公式溯源标记（API_521_§7.4.2.3+BEDD）"
    )


class StackDesignResponse(BaseModel):
    """FLARE_SYS stack_design 响应（stack_height + radiation_check 综合）。

    字段：
    - stack_height: Stack Height 子结果（StackHeightInfo；API 521 §7.4.2.2）
    - radiation: Radiation Check 子结果（RadiationCheckInfo；API 521 §7.4.2.3 + BEDD）
    - project_id: 回显请求 project_id（前端 audit）
    - standard_profile_code: 回显请求 standard_profile_code
    - formula_ref: 综合公式溯源标记 "API_521_§7.4.2.2+§7.4.2.3"
    """

    stack_height: StackHeightInfo = Field(..., description="Stack Height 子结果")
    radiation: RadiationCheckInfo = Field(..., description="Radiation Check 子结果")
    project_id: uuid.UUID = Field(..., description="回显请求 project_id")
    standard_profile_code: str = Field(..., description="回显请求 standard_profile_code")
    formula_ref: str = Field(
        ..., description="公式溯源标记（API_521_§7.4.2.2+§7.4.2.3）"
    )


__all__ = [
    "HeaderSizingRequest",
    "HeaderSizingResponse",
    "KodSizingRequest",
    "KodSizingResponse",
    "KodInfo",
    "WaterSealInfo",
    "StackDesignRequest",
    "StackDesignResponse",
    "StackHeightInfo",
    "RadiationCheckInfo",
    # Task 23 — flare_tip + flare_persist
    "FlareTipRequest",
    "FlareTipResponse",
    "FlareResultCreateRequest",
    "FlareResultUpdateRequest",
    "FlareResultResponse",
    "FlareResultListResponse",
]

# ───────────────────────────── Task 23 flare_tip ──────────────────────────────


class FlareTipRequest(BaseModel):
    """FLARE_SYS flare_tip 请求（API 521 §5.15.6）。

    字段（按 API 521 §5.15.6 火炬尖端 tip 速度计算输入）：

    - project_id: 项目 ID（与 Task 19/20/21/22 隔离键一致）
    - standard_profile_code: 项目标准（默认 API_521）
    - header_diameter_m: 火炬总管直径 m（>0；来自 Task 20 header_sizing）
    - mw_kg_kmol: 气体分子量 kg/kmol（>0）
    - tip_temperature_k: 尖端温度 K（>0，工况下）
    - tip_pressure_pa: 尖端压力 Pa（>0，火炬入口压力）
    - specific_heat_ratio: 比热比 k = cp/cv（>1.0）
    - target_mach: 目标 Mach 数（默认 0.2 尖端亚音速，范围 [0.05, 1.0]）
    """

    project_id: uuid.UUID = Field(
        ..., description="项目 ID（与 Task 19/20/21/22 隔离键一致）"
    )
    standard_profile_code: str = Field(
        "API_521", description="项目标准（API_521 / GB/T）"
    )
    header_diameter_m: float = Field(
        ..., gt=0, description="火炬总管直径 m（来自 Task 20 header_sizing）"
    )
    mw_kg_kmol: float = Field(..., gt=0, description="气体分子量 kg/kmol")
    tip_temperature_k: float = Field(..., gt=0, description="尖端温度 K（工况下）")
    tip_pressure_pa: float = Field(
        ..., gt=0, description="尖端压力 Pa（火炬入口压力）"
    )
    specific_heat_ratio: float = Field(
        ..., gt=1.0, description="比热比 k = cp/cv"
    )
    target_mach: float = Field(
        0.2,
        ge=0.05,
        le=1.0,
        description="目标 Mach 数（尖端亚音速默认 0.2，范围 [0.05, 1.0]）",
    )


class FlareTipResponse(BaseModel):
    """FLARE_SYS flare_tip 响应（API 521 §5.15.6）。

    字段（按 API 521 §5.15.6 输出）：
    - tip_diameter_m: 尖端直径 m（与 header 同径；单点 tip 假设）
    - tip_area_m2: 尖端流通面积 m²
    - tip_velocity_m_s: 尖端目标速度 m/s（= M_target × a）
    - actual_mach: 实际 Mach 数（恒等于 target_mach）
    - sound_speed_m_s: 等温声速 m/s
    - gas_density_kg_m3: 管内气体密度 kg/m³
    - mass_flux_kgs_m2: 质量流速 G kg/(s·m²)
    - formula_ref: 公式溯源标记 "API_521_§5.15.6"
    - project_id: 回显请求 project_id（前端 audit）
    - standard_profile_code: 回显请求 standard_profile_code
    """

    tip_diameter_m: float = Field(..., description="尖端直径 m")
    tip_area_m2: float = Field(..., description="尖端流通面积 m²")
    tip_velocity_m_s: float = Field(..., description="尖端目标速度 m/s")
    actual_mach: float = Field(
        ..., description="实际 Mach 数（恒等于 target_mach）"
    )
    sound_speed_m_s: float = Field(..., description="等温声速 m/s")
    gas_density_kg_m3: float = Field(..., description="管内气体密度 kg/m³")
    mass_flux_kgs_m2: float = Field(..., description="质量流速 G kg/(s·m²)")
    formula_ref: str = Field(
        ..., description="公式溯源标记（API_521_§5.15.6）"
    )
    project_id: uuid.UUID = Field(..., description="回显请求 project_id")
    standard_profile_code: str = Field(
        ..., description="回显请求 standard_profile_code"
    )


# ───────────────────────────── Task 23 flare_persist ───────────────────────────


class FlareResultCreateRequest(BaseModel):
    """FlareSystemResult 创建请求（POST /flare/results）。

    字段按 FlareSystemResult ORM 列名（Task 18，P6-2 实施）平铺 —— save_flare_result
    service 直接 ``**payload`` 喂给 ORM，字段名必须与列名严格一致：

    - project_id: 项目 ID（RecordMixin FK → projects.project_id）
    - workspace_id: 工作区 ID（业务隔离）
    - tag_number: 位号（TaggedRecordMixin NOT NULL；项目内唯一）
    - standard_profile_code: 项目标准（默认 "API_521"；C-07 String(16) 锁定）
    - calc_type: 计算类型（RELIEF_SUMMARY/HEADER_SIZING/KOD_SIZING/STACK_HEIGHT/
      RADIATION/FLARE_TIP；String(32) NOT NULL）
    - sign_status: 签审状态（默认 DRAFT）

    18 业务字段（FlareSystemResult __table__ 排除 PK + mixin 字段）：
    - total_relief_load_kg_h: 总泄放质量流量 kg/h
    - header_diameter_mm: 总管直径 mm（来自 Task 20）
    - header_mach: 总管实际 Mach 数（应等于 target_mach）
    - header_pressure_drop_kpa: 总管压降 kPa
    - kod_diameter_mm: KOD 直径 mm（来自 Task 21）
    - water_seal_height_mm: 水封高度 mm（来自 Task 21）
    - stack_height_m: 火炬高度 m（来自 Task 22）
    - stack_diameter_m: 火炬直径 m
    - radiation_at_grade_kw_m2: 地面辐射 kW/m²（来自 Task 22）
    - radiation_limit_kw_m2: BEDD 限值 kW/m²（来自 Task 22）
    - pass_: 辐射校验 PASS/FAIL（SPEC §3.2.3）
    - flare_tip_diameter_mm: 尖端直径 mm（来自 tip 计算）
    - steam_for_smokeless_kg_h: 无烟蒸汽消耗 kg/h
    - radiation_check_json: 辐射校验完整产物（PCS-DICT-005 §3.1）
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
        "API_521", description="项目标准（默认 API_521）"
    )
    calc_type: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="计算类型（RELIEF_SUMMARY/HEADER_SIZING/KOD_SIZING/STACK_HEIGHT/RADIATION/FLARE_TIP）",
    )
    sign_status: str = Field(
        "DRAFT",
        description=(
            "签审状态（DRAFT / IN_APPROVAL / CHECKED / CHECK_REJECTED / "
            "STALE / CHANGE_PENDING / CHANGED / REVERSAL_PENDING / OBSOLETE）"
        ),
    )

    # 18 业务字段（按 ORM 列名平铺；service layer **payload 喂给 ORM）
    total_relief_load_kg_h: float | None = Field(
        None, description="总泄放质量流量 kg/h"
    )
    header_diameter_mm: float | None = Field(None, description="总管直径 mm")
    header_mach: float | None = Field(None, description="总管 Mach 数")
    header_pressure_drop_kpa: float | None = Field(None, description="总管压降 kPa")
    kod_diameter_mm: float | None = Field(None, description="KOD 直径 mm")
    water_seal_height_mm: float | None = Field(None, description="水封高度 mm")
    stack_height_m: float | None = Field(None, description="火炬高度 m")
    stack_diameter_m: float | None = Field(None, description="火炬直径 m")
    radiation_at_grade_kw_m2: float | None = Field(
        None, description="地面辐射 kW/m²"
    )
    radiation_limit_kw_m2: float | None = Field(
        None, description="BEDD 限值 kW/m²"
    )
    pass_: bool | None = Field(
        None,
        alias="pass",
        description="辐射校验 PASS/FAIL（SPEC §3.2.3）",
    )
    flare_tip_diameter_mm: float | None = Field(
        None, description="尖端直径 mm（来自 tip 计算）"
    )
    steam_for_smokeless_kg_h: float | None = Field(
        None, description="无烟蒸汽消耗 kg/h"
    )
    radiation_check_json: dict | None = Field(
        None, description="辐射校验完整产物（PCS-DICT-005 §3.1）"
    )
    input_json: dict | None = Field(None, description="入参（业务子结构）")
    output_json: dict | None = Field(None, description="出参（业务子结构）")

    model_config = ConfigDict(populate_by_name=True)


class FlareResultUpdateRequest(BaseModel):
    """FlareSystemResult 更新请求（PATCH /flare/results/{id}）。

    字段子集（PATCH 仅允许业务字段；不可改 sign_status / tag_number / 溯源等）
    """

    calc_type: str | None = Field(None, max_length=32, description="计算类型")
    total_relief_load_kg_h: float | None = Field(
        None, description="总泄放质量流量 kg/h"
    )
    header_diameter_mm: float | None = Field(None, description="总管直径 mm")
    header_mach: float | None = Field(None, description="总管 Mach 数")
    header_pressure_drop_kpa: float | None = Field(
        None, description="总管压降 kPa"
    )
    kod_diameter_mm: float | None = Field(None, description="KOD 直径 mm")
    water_seal_height_mm: float | None = Field(None, description="水封高度 mm")
    stack_height_m: float | None = Field(None, description="火炬高度 m")
    stack_diameter_m: float | None = Field(None, description="火炬直径 m")
    radiation_at_grade_kw_m2: float | None = Field(
        None, description="地面辐射 kW/m²"
    )
    radiation_limit_kw_m2: float | None = Field(
        None, description="BEDD 限值 kW/m²"
    )
    pass_: bool | None = Field(
        None, alias="pass", description="辐射校验 PASS/FAIL"
    )
    flare_tip_diameter_mm: float | None = Field(None, description="尖端直径 mm")
    steam_for_smokeless_kg_h: float | None = Field(
        None, description="无烟蒸汽消耗 kg/h"
    )
    radiation_check_json: dict | None = Field(
        None, description="辐射校验完整产物"
    )
    input_json: dict | None = Field(None, description="入参")
    output_json: dict | None = Field(None, description="出参")

    model_config = ConfigDict(populate_by_name=True)


class FlareResultResponse(BaseModel):
    """FlareSystemResult 单条响应（GET /flare/results/{id} 与 POST 201 body）。

    字段：溯源（id / project_id / workspace_id / tag_number / standard_profile_code
    / calc_type / sign_status / record_hash）+ 18 业务字段 + 时间戳。

    字段映射（ORM → schema）：
    - ORM flare_id → schema id（PK 重命名；前端统一用 id）
    - ORM pass → schema pass_（保留 ORM 别名）
    """

    model_config = ConfigDict(
        from_attributes=True, populate_by_name=True, serialize_by_alias=True
    )

    id: uuid.UUID = Field(..., description="flare_system_results.flare_id（PK）")
    project_id: uuid.UUID = Field(..., description="项目 ID")
    workspace_id: uuid.UUID = Field(..., description="工作区 ID")
    tag_number: str = Field(..., description="位号")
    standard_profile_code: str = Field(..., description="项目标准")
    calc_type: str = Field(..., description="计算类型")
    sign_status: str = Field(..., description="签审状态 9 态")
    record_hash: str | None = Field(
        None, description="record_hash（ADR-0028 §决策 4 reflection；16 hex）"
    )
    # 18 业务字段
    total_relief_load_kg_h: float | None = Field(None, description="kg/h")
    header_diameter_mm: float | None = Field(None, description="总管直径 mm")
    header_mach: float | None = Field(None, description="总管 Mach 数")
    header_pressure_drop_kpa: float | None = Field(None, description="总管压降 kPa")
    kod_diameter_mm: float | None = Field(None, description="KOD 直径 mm")
    water_seal_height_mm: float | None = Field(None, description="水封高度 mm")
    stack_height_m: float | None = Field(None, description="火炬高度 m")
    stack_diameter_m: float | None = Field(None, description="火炬直径 m")
    radiation_at_grade_kw_m2: float | None = Field(
        None, description="地面辐射 kW/m²"
    )
    radiation_limit_kw_m2: float | None = Field(None, description="BEDD kW/m²")
    pass_: bool | None = Field(
        None,
        validation_alias="pass",
        serialization_alias="pass",
        description="辐射校验 PASS/FAIL",
    )
    flare_tip_diameter_mm: float | None = Field(None, description="尖端直径 mm")
    steam_for_smokeless_kg_h: float | None = Field(
        None, description="无烟蒸汽消耗 kg/h"
    )
    radiation_check_json: dict | None = Field(
        None, description="辐射校验完整产物"
    )
    input_json: dict | None = Field(None, description="入参")
    output_json: dict | None = Field(None, description="出参")

    created_at: datetime = Field(..., description="创建时间")
    updated_at: datetime | None = Field(None, description="更新时间")

    @model_validator(mode="before")
    @classmethod
    def _from_orm_rename(cls, data: Any) -> Any:
        """ORM → schema 字段映射：ORM flare_id → schema id。

        支持 dict 输入（来自 model_validate(record, from_attributes=True) 透传
        的 ORM 属性访问）；attr 输入（record.xxx）也走同样的 getattr。
        """
        if data is None:
            return data
        # from_attributes=True 时，data 可能是 ORM 对象或 dict
        flare_id = getattr(data, "flare_id", None)
        if flare_id is not None and not isinstance(data, dict):
            # ORM 对象：直接 setattr 等价于属性赋值（常量字符串 by ruff B010）
            try:
                data.id = flare_id  # noqa: B010
            except AttributeError:
                # 不可 set（如 MagicMock 已被 frozen）→ 转 dict 处理
                if hasattr(data, "__dict__"):
                    d = dict(data.__dict__)
                    d["id"] = flare_id
                    return d
        return data


class FlareResultListResponse(BaseModel):
    """FlareSystemResult 列表响应（GET /flare/results）。

    字段：
    - items: FlareResultResponse 列表
    - total: 命中条数（受 sign_status_filter 影响；OBSOLETE 等门禁态被过滤）
    - limit / offset: 分页参数回显
    """

    items: list[FlareResultResponse] = Field(
        ..., description="FlareSystemResult 列表"
    )
    total: int = Field(..., description="命中条数（默认 DRAFT/CHECKED filter）")
    limit: int = Field(..., description="分页上限")
    offset: int = Field(..., description="分页偏移")