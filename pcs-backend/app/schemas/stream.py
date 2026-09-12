"""P3.2 SIM Stream / StreamStatePoint Pydantic v2 Schema（spec V1.6 §3.2 + §5.3）。

三套：
- StreamBase/Create/Update/Response（CRUD）
- StreamStatePointBase/Create/Update/Response（状态点 CRUD，共享事务）
- StreamImportPreview/Result（PRO/II + Excel 导入预览/落库）

spec V1.6 §5.3 强制：每字段必含中文 Field(description=...)。

下游 SIM-2..12 直接 import 本模块。Schema 字段名/可空/类型变更需同步
SIM-3 物性补全接口签名。

注意（plan vs 现状差异，2026-09-08 修正）：
- sign_status 字段不暴露给 Schema（API 层用 RecordMixin 9 态全集约束，
  StreamSignStatus 仅 DB 层 4 态）。
- 物流级 case_type（StreamCaseType）≠ 状态点级 case_type（StatePointCaseType），
  独立两枚举。
"""
from __future__ import annotations

import uuid
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class StreamCaseType(str, Enum):
    """物流级 case_type（spec V1.6 §3.2.2）：设计工况 4 值。"""

    NORMAL = "NORMAL"
    END_OF_RUN = "END_OF_RUN"
    START_OF_RUN = "START_OF_RUN"
    TURN_DOWN = "TURN_DOWN"


class StatePointCaseType(str, Enum):
    """状态点级 case_type（spec V1.6 §3.2.2）：操作边界 4 值。"""

    NORMAL = "NORMAL"
    MIN = "MIN"
    MAX = "MAX"
    ALTERNATE = "ALTERNATE"


class StreamBase(BaseModel):
    """Stream 基础字段。stream_name + case_type + data_mode 必填。"""

    stream_name: str = Field(..., min_length=1, max_length=100, description="管段物流号")
    case_type: StreamCaseType = Field(
        ...,
        description="物流级工况：NORMAL/END_OF_RUN/START_OF_RUN/TURN_DOWN",
    )
    data_mode: str = Field(
        ...,
        min_length=1,
        max_length=20,
        description="数据模式：CHEMICAL/PETROLEUM/SOLID",
    )
    description: str | None = Field(None, max_length=500, description="物流描述")

    # === 物流操作参数（spec V1.6 §3.2.3） ===
    phase: str | None = Field(None, max_length=20, description="相态：VAPOR/LIQUID/MIXED/SOLID")
    temp: float | None = Field(None, description="温度 °C")
    press: float | None = Field(None, description="压力 kPa")
    mass_flow: float | None = Field(None, description="质量流量 kg/h")
    molar_flow: float | None = Field(None, description="摩尔流量 kmol/h")
    volumetric_flow: float | None = Field(None, description="标准体积流量 m³/h")
    actual_vol_flow: float | None = Field(None, description="工况体积流量 m³/h（≠ 标准体积）")
    std_gas_flow: float | None = Field(None, description="标况气体流量 Nm³/h")
    vapor_fraction: float | None = Field(None, ge=0.0, le=1.0, description="气相分率")
    liquid_fraction: float | None = Field(
        None, ge=0.0, le=1.0, description="SIM-31: 液相分率 (0~1)，对称 vapor_fraction"
    )

    # === 物性（spec V1.6 §3.2.3 表 2 + SIM-33 命名对齐 spec §3.6） ===
    molecular_weight: float | None = Field(None, description="分子量（通用，气液相同）")
    # === SIM-33: 液相物性命名对齐（spec §3.6 liquid_ 前缀）===
    liquid_density: float | None = Field(
        None, description="SIM-33 §3.6: 液相密度 kg/m³（原 density）"
    )
    liquid_viscosity_dynamic: float | None = Field(
        None, description="SIM-33 §3.6: 液相动力粘度 Pa·s（原 viscosity_dynamic）"
    )
    liquid_viscosity_kinematic: float | None = Field(
        None, description="SIM-33 §3.6: 液相运动粘度 m²/s（原 viscosity_kinematic）"
    )
    liquid_thermal_conductivity: float | None = Field(
        None, description="SIM-33 §3.6: 液相导热系数 W/(m·K)（原 thermal_conductivity）"
    )
    liquid_specific_heat: float | None = Field(
        None, description="SIM-33 §3.6: 液相比热容 kJ/(kg·K)（原 specific_heat）"
    )
    liquid_surface_tension: float | None = Field(
        None, description="SIM-33 §3.6: 液相表面张力 N/m（原 surface_tension）"
    )
    liquid_compressibility_factor: float | None = Field(
        None, description=(
            "SIM-33 §3.6: 液相压缩因子 Z（与 vapor_z 对称；原 compressibility_factor）"
        )
    )
    # === SIM-33: SIM-31 JSONB → ORM 3 字段（避免气液不对称）===
    liquid_std_density: float | None = Field(
        None, description="SIM-33 §3.6: 液相标况密度 kg/m³（SIM-31 std_liq_density 迁 ORM）"
    )
    liquid_mass_rate: float | None = Field(
        None, description="SIM-33 §3.6: 液相质量流量 kg/h（SIM-31 JSONB 迁 ORM）"
    )
    liquid_actual_m3hr: float | None = Field(
        None, description="SIM-33 §3.6: 液相实际体积流量 m³/h（SIM-31 liq_actual_m3hr 迁 ORM）"
    )
    # === SIM-33: 气相物性 9 字段（spec §3.5 C/O）===
    vapor_mass_rate: float | None = Field(
        None, description="SIM-33 §3.5: 气相质量流量 kg/h"
    )
    vapor_actual_m3hr: float | None = Field(
        None, description="SIM-33 §3.5: 气相实际体积流量 m³/h"
    )
    vapor_normal_m3hr: float | None = Field(
        None, description="SIM-33 §3.5: 气相标况体积流量 Nm³/h"
    )
    vapor_mw: float | None = Field(
        None, description="SIM-33 §3.5: 气相分子量（专气相显示）"
    )
    vapor_density: float | None = Field(
        None, description="SIM-33 §3.5: 气相密度 kg/m³（与 liquid_density 对称）"
    )
    vapor_z: float | None = Field(
        None, description="SIM-33 §3.5: 气相压缩因子 Z（与 liquid_compressibility_factor 对称）"
    )
    vapor_cp: float | None = Field(
        None, description="SIM-33 §3.5: 气相比热容 kJ/(kg·K)"
    )
    vapor_viscosity: float | None = Field(
        None, description="SIM-33 §3.5: 气相动力粘度 Pa·s"
    )
    vapor_thermal_cond: float | None = Field(
        None, description="SIM-33 §3.5: 气相导热系数 W/(m·K)"
    )
    api_gravity: float | None = Field(None, description="API 度（°API），石油馏分专用")
    specific_gravity: float | None = Field(
        None, description="SIM-31: 比重（water=1.0），对称 api_gravity"
    )
    # === SIM-34: 炼油专用 5 字段（ADD-001 §3.8-3.9）===
    rvp: float | None = Field(
        None, description="SIM-34 §3.8: 雷德蒸气压 RVP（psi）"
    )
    tvp: float | None = Field(
        None, description="SIM-34 §3.8: 真实蒸气压 TVP（psi）"
    )
    watson_k: float | None = Field(
        None, description="SIM-34 §3.8: 沃森特性因子 K（UOP K，无量纲）"
    )
    flash_point: float | None = Field(
        None, description="SIM-34 §3.8: 闪点 °C"
    )
    distillation_curves: dict[str, Any] | None = Field(
        None,
        description=(
            "SIM-34 §3.9: 蒸馏曲线 8 种 schema"
            "（D86/TBP/EFV/D86_CRACKING/D1160/D2887/D5236/D7169）"
        ),
    )
    critical_temp: float | None = Field(None, description="临界温度 K")
    critical_press: float | None = Field(None, description="临界压力 Pa")
    enthalpy: float | None = Field(None, description="焓 kJ/kg")
    entropy: float | None = Field(None, description="熵 kJ/(kg·K)")
    viscosity_temperature_curve: dict[str, Any] | None = Field(
        None, description="粘度-温度曲线 [{temp_k, viscosity_cp}, ...]"
    )

    # === 组成（JSONB） ===
    composition_json: dict[str, Any] | None = Field(None, description="总组成 CAS→摩尔分率")
    vapor_composition_json: dict[str, Any] | None = Field(
        None, description="气相组成（两相流必填）"
    )
    liquid_composition_json: dict[str, Any] | None = Field(
        None, description="液相组成（两相流必填）"
    )

    # === 油品/固体特性 ===
    distillation_json: dict[str, Any] | None = Field(None, description="馏程 IBP→FBP")
    sara_json: dict[str, Any] | None = Field(None, description="四组分 SARA")
    elemental_json: dict[str, Any] | None = Field(None, description="元素分析 C/H/O/N/S")
    metals_json: dict[str, Any] | None = Field(None, description="金属含量")
    feedstock_specs_json: dict[str, Any] | None = Field(None, description="原料规格")
    product_specs_json: dict[str, Any] | None = Field(None, description="产品规格")
    property_estimation_json: dict[str, Any] | None = Field(None, description="物性估算方法")
    pseudo_components_json: list[dict[str, Any]] | None = Field(None, description="假组分")
    bulk_density_min: float | None = Field(None, description="堆积密度下限 kg/m³")
    bulk_density_max: float | None = Field(None, description="堆积密度上限 kg/m³")
    true_density: float | None = Field(None, description="真实密度 kg/m³")
    particle_size_avg: float | None = Field(None, description="平均粒径 mm")
    particle_size_range: str | None = Field(None, max_length=100, description="粒径范围")
    particle_shape: str | None = Field(None, max_length=100, description="颗粒形状")
    repose_angle: float | None = Field(None, description="休止角 °")
    vessel_cone_angle: float | None = Field(None, description="料仓锥角 °")

    # === 上游/溯源（spec V1.6 §3.2.3） ===
    upstream_stream_id: uuid.UUID | None = Field(None, description="上游物流 ID")
    upstream_equipment_type: str | None = Field(
        None,
        max_length=30,
        description="上游设备类型：PUMP/CV/PIPE/HEAT/RESTRICTION/FLASH",
    )
    upstream_equipment_id: uuid.UUID | None = Field(None, description="上游设备记录 ID")
    change_type: str | None = Field(
        None,
        max_length=30,
        description="变化类型：ISOENTHALPIC/FRICTION_PRESSURE_DROP/HEAT_EXCHANGE/PUMP_WORK",
    )
    source_type: str = Field(
        ...,
        max_length=30,
        description="来源类型：SIM_IMPORT/MANUAL_ENTRY/LAB_REPORT/FLASH_CALCULATED/DEVICE_CALCULATED",
    )
    source_file: str | None = Field(None, max_length=200, description="源文件路径")
    lab_report_ref: str | None = Field(None, max_length=200, description="实验报告编号")

    # === P3.2 SIM 导入溯源（plan 修正版新增） ===
    import_original_row: int | None = Field(None, description="PRO/II 原始行号（溯源）")
    import_source_version: str | None = Field(
        None, max_length=20, description="PRO/II 解析器版本：V2.71/V4.17/V8.x"
    )
    is_unreliable: bool | None = Field(
        None,
        description=(
            "PRO/II 不可靠流标记：NULL=未设（手工/Excel 默认，等价 False）；"
            "TRUE=NOT_CONVERGED/ABORTED 单元产品；FALSE=CONVERGED/WARNINGS 流显式标"
        ),
    )
    is_mixed_phase: bool | None = Field(
        None,
        description=(
            "PRO/II 原始相态 MIXED 标记：TRUE=汽液混相（MVP 未抽组成，phase 置 None）；"
            "FALSE/NULL=其他入口（手工/Excel）或 PRO/II 非 MIXED 流"
        ),
    )


class StreamCreate(StreamBase):
    """创建请求：必填 project_id + workspace_id。"""

    project_id: uuid.UUID = Field(..., description="所属项目 ID")
    workspace_id: uuid.UUID = Field(..., description="所属工作区 ID")


class StreamUpdate(BaseModel):
    """更新请求：所有字段可选，支持部分更新。"""

    stream_name: str | None = Field(None, min_length=1, max_length=100, description="管段物流号")
    case_type: StreamCaseType | None = Field(None, description="物流级工况")
    data_mode: str | None = Field(None, min_length=1, max_length=20, description="数据模式")
    description: str | None = Field(None, max_length=500, description="物流描述")
    phase: str | None = Field(None, max_length=20, description="相态")
    temp: float | None = Field(None, description="温度 °C")
    press: float | None = Field(None, description="压力 kPa")
    mass_flow: float | None = Field(None, description="质量流量 kg/h")
    molar_flow: float | None = Field(None, description="摩尔流量 kmol/h")
    actual_vol_flow: float | None = Field(None, description="工况体积流量 m³/h")
    source_type: str | None = Field(None, max_length=30, description="来源类型")


class StreamResponse(StreamBase):
    """完整响应：含 sign_status + 审计字段。"""

    stream_id: uuid.UUID = Field(..., description="物流 ID")
    sign_status: str = Field(..., description="签署门禁：DRAFT/IN_APPROVAL/CHECKED/OBSOLETE")
    approval_step: int | None = Field(None, description="当前校对步骤")
    approval_depth: int = Field(..., description="校对深度 1~4")
    record_hash: str = Field(..., description="SHA-256 实质变更判别")
    last_change_reason: str | None = Field(None, description="最近变更原因")
    last_changed_at: str | None = Field(None, description="最近变更时间")
    created_at: str = Field(..., description="创建时间")
    updated_at: str | None = Field(None, description="更新时间")

    model_config = {"from_attributes": True}


# ============================================================================
# 状态点
# ============================================================================


class StreamStatePointBase(BaseModel):
    """状态点基础字段。state_label + case_type 必填。"""

    state_label: str = Field(
        ..., min_length=1, max_length=50, description="状态点标签，如 设计工况/最大负荷"
    )
    case_type: StatePointCaseType = Field(
        ..., description="状态点级工况：NORMAL/MIN/MAX/ALTERNATE"
    )
    temp: float = Field(..., description="温度 °C")
    press: float = Field(..., description="压力 kPa")
    phase: str = Field(..., min_length=1, max_length=20, description="相态")
    vapor_fraction: float | None = Field(None, ge=0.0, le=1.0, description="气相分率")
    mass_flow: float = Field(..., description="质量流量 kg/h")
    composition_json: dict[str, Any] = Field(..., description="组成 CAS→摩尔分率")
    vapor_composition_json: dict[str, Any] | None = Field(None, description="气相组成")
    liquid_composition_json: dict[str, Any] | None = Field(None, description="液相组成")
    density: float | None = Field(None, description="密度 kg/m³")
    viscosity_dynamic: float | None = Field(None, description="动力粘度 Pa·s")
    enthalpy: float | None = Field(None, description="焓 kJ/kg")
    entropy: float | None = Field(None, description="熵 kJ/(kg·K)")
    estimated_flags_json: dict[str, Any] | None = Field(
        None, description="估算标记 {field: true if estimated}"
    )
    profile_json: dict[str, Any] | None = Field(
        None, description="沿程剖面 distance/pressures/temperatures"
    )
    source_type: str = Field(
        ...,
        max_length=30,
        description="来源：SIM_IMPORT/MANUAL_ENTRY/FLASH_CALCULATED/DEVICE_CALCULATED",
    )


class StreamStatePointCreate(StreamStatePointBase):
    """创建请求：必填 stream_id。"""

    stream_id: uuid.UUID = Field(..., description="所属物流 ID")


class StreamStatePointUpdate(BaseModel):
    """更新请求：所有字段可选。"""

    state_label: str | None = Field(None, min_length=1, max_length=50, description="状态点标签")
    case_type: StatePointCaseType | None = Field(None, description="状态点级工况")
    temp: float | None = Field(None, description="温度 °C")
    press: float | None = Field(None, description="压力 kPa")
    mass_flow: float | None = Field(None, description="质量流量 kg/h")
    source_type: str | None = Field(None, max_length=30, description="来源类型")


class StreamStatePointResponse(StreamStatePointBase):
    """完整响应：含 ID + 审计字段。"""

    state_point_id: uuid.UUID = Field(..., description="状态点 ID")
    stream_id: uuid.UUID = Field(..., description="所属物流 ID")
    record_hash: str = Field(..., description="SHA-256 实质变更判别")
    created_at: str = Field(..., description="创建时间")

    model_config = {"from_attributes": True}


# ============================================================================
# 导入预览 / 落库
# ============================================================================


class StreamImportPreview(BaseModel):
    """PRO/II / Excel 导入预览（commit 前 dry-run）。"""

    convergence_status: str = Field(
        ..., description="收敛状态：CONVERGED/WARNINGS/NOT_CONVERGED/ABORTED/NOT_SOLVED"
    )
    unreliable_stream_names: list[str] = Field(
        default_factory=list, description="不可靠流名（NOT_CONVERGED/ABORTED 单元产品）"
    )
    warnings: list[str] = Field(default_factory=list, description="parser 警告")
    preview_streams: list[dict[str, Any]] = Field(
        default_factory=list, description="预览物流数据（未持久化）"
    )
    conflict_report: dict[str, Any] | None = Field(
        None, description="冲突检测报告（BLOCK/WARN/INFO）"
    )


class StreamImportResult(BaseModel):
    """PRO/II / Excel 导入落库结果。"""

    committed_count: int = Field(..., ge=0, description="成功落库数")
    unreliable_count: int = Field(..., ge=0, description="不可靠数（unreliable=True 标记）")
    skipped_count: int = Field(default=0, ge=0, description="跳过数（BLOCK 冲突）")
    stream_ids: list[uuid.UUID] = Field(default_factory=list, description="落库物流 ID 列表")
    warnings: list[str] = Field(default_factory=list, description="落库过程警告")
