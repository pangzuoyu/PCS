import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import StreamSignStatus, UserStatus
from app.models.mixins import TimestampMixin


class Project(TimestampMixin, Base):
    __tablename__ = "projects"
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_no: Mapped[str] = mapped_column(String(50), unique=True)
    project_name: Mapped[str] = mapped_column(String(200))
    project_name_cn: Mapped[str | None] = mapped_column(String(200))
    owner_company: Mapped[str] = mapped_column(String(200))
    contractor_company: Mapped[str | None] = mapped_column(String(200))
    engineer_name: Mapped[str | None] = mapped_column(String(200))
    dd_contractor_name: Mapped[str | None] = mapped_column(String(200))
    feed_contractor_name: Mapped[str | None] = mapped_column(String(200))
    location: Mapped[str] = mapped_column(String(500))
    site_address: Mapped[str | None] = mapped_column(String(500))
    project_type: Mapped[str] = mapped_column(String(30))
    design_phase: Mapped[str] = mapped_column(String(30))
    total_capacity: Mapped[float | None] = mapped_column(Float)
    total_capacity_unit: Mapped[str | None] = mapped_column(String(20))
    plant_count: Mapped[int | None] = mapped_column(Integer)
    single_plant_capacity: Mapped[float | None] = mapped_column(Float)
    single_plant_capacity_unit: Mapped[str | None] = mapped_column(String(20))
    reference_plant: Mapped[str | None] = mapped_column(String(200))
    unit_system: Mapped[str] = mapped_column(String(20))
    bedd_json: Mapped[dict | None] = mapped_column(JSONB)
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey(
            "workspaces.workspace_id", use_alter=True, name="fk_projects_workspace_id"
        ),
        comment="项目所属 FORMAL 工作区；use_alter 破解 projects↔workspaces 循环",
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class Workspace(Base):
    __tablename__ = "workspaces"
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    workspace_type: Mapped[str] = mapped_column(String(20))  # WorkspaceType
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    name: Mapped[str] = mapped_column(String(200))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_active_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retention_days: Mapped[int | None] = mapped_column(
        Integer, comment="个人 90 / 临时 7"
    )


class User(Base):
    __tablename__ = "users"
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(String(100), unique=True)
    display_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    department: Mapped[str | None] = mapped_column(String(200))
    roles: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        comment="ApprovalRole 7 值：DESIGNER/CHECKER/REVIEWER/APPROVER/SYSADMIN/PROCESS_CONTROLLER/DATA_ADMIN",  # noqa: E501
    )
    ad_groups: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE.value)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Stream(TimestampMixin, Base):
    """物流=管段（ADR-0019）。4 态简化门禁（ADR-0014）。字典表2 逐字。"""

    __tablename__ = "streams"
    __table_args__ = (
        UniqueConstraint("project_id", "stream_name", name="uq_streams_project_stream_name"),
        CheckConstraint(
            "case_type IN ('NORMAL','END_OF_RUN','START_OF_RUN','TURN_DOWN')",
            name="ck_streams_case_type",
        ),
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("workspaces.workspace_id"), index=True
    )
    stream_name: Mapped[str] = mapped_column(String(100), comment="管段物流号，如 S-101")
    description: Mapped[str | None] = mapped_column(String(500))
    phase: Mapped[str | None] = mapped_column(String(20), comment="StreamPhase")
    temp: Mapped[float | None] = mapped_column(Float, comment="基准工况 °C")
    press: Mapped[float | None] = mapped_column(Float)
    mass_flow: Mapped[float | None] = mapped_column(Float, comment="kg/h")
    molar_flow: Mapped[float | None] = mapped_column(Float, comment="kmol/h")
    volumetric_flow: Mapped[float | None] = mapped_column(Float, comment="m³/h")
    std_gas_flow: Mapped[float | None] = mapped_column(Float, comment="Nm³/h")
    composition_json: Mapped[dict | None] = mapped_column(JSONB)
    vapor_composition_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="两相流必填"
    )
    liquid_composition_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="两相流必填"
    )
    # density / viscosity_dynamic / viscosity_kinematic / thermal_conductivity /
    # specific_heat / surface_tension / compressibility_factor 已在 SIM-33 重命名为
    # liquid_* 前缀（spec §3.6 命名对齐）
    molecular_weight: Mapped[float | None] = mapped_column(
        Float, comment="分子量（通用，气液相同，SIM-33 不重命名）"
    )
    vapor_fraction: Mapped[float | None] = mapped_column(Float)
    liquid_fraction: Mapped[float | None] = mapped_column(
        Float, comment="SIM-31 §1.2.1: 液相分率 (0~1)，对称 vapor_fraction"
    )
    # === P3.x SIM-33: 液相物性命名对齐（spec §3.6 liquid_ 前缀；7 列 RENAME）===
    liquid_density: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相密度 kg/m³（原 density）"
    )
    liquid_viscosity_dynamic: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相动力粘度 Pa·s（原 viscosity_dynamic）"
    )
    liquid_viscosity_kinematic: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相运动粘度 m²/s（原 viscosity_kinematic）"
    )
    liquid_thermal_conductivity: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相导热系数 W/(m·K)（原 thermal_conductivity）"
    )
    liquid_specific_heat: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相比热容 kJ/(kg·K)（原 specific_heat）"
    )
    liquid_surface_tension: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相表面张力 N/m（原 surface_tension）"
    )
    liquid_compressibility_factor: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相压缩因子 Z（与 vapor_z 对称；原 compressibility_factor）"
    )
    # === P3.x SIM-33: SIM-31 JSONB → ORM 迁移（避免气液不对称）===
    liquid_std_density: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相标况密度 kg/m³（SIM-31 std_liq_density 迁 ORM）"
    )
    liquid_mass_rate: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相质量流量 kg/h（SIM-31 JSONB 迁 ORM）"
    )
    liquid_actual_m3hr: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相实际体积流量 m³/h（SIM-31 liq_actual_m3hr 迁 ORM）"
    )
    # === P3.x SIM-33: 气相物性 9 字段（spec §3.5 C/O，与 vapor_fraction ORM 对称）===
    vapor_mass_rate: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相质量流量 kg/h"
    )
    vapor_actual_m3hr: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相实际体积流量 m³/h"
    )
    vapor_normal_m3hr: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相标况体积流量 Nm³/h"
    )
    vapor_mw: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相分子量（与 molecular_weight 同义；专气相显示）"
    )
    vapor_density: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相密度 kg/m³（与 liquid_density 对称）"
    )
    vapor_z: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相压缩因子 Z（与 liquid_compressibility_factor 对称）"
    )
    vapor_cp: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相比热容 kJ/(kg·K)"
    )
    vapor_viscosity: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相动力粘度 Pa·s"
    )
    vapor_thermal_cond: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相导热系数 W/(m·K)"
    )
    # === P3.x SIM-33: SIM-31 JSONB → ORM 迁移（避免气液不对称）===
    liquid_std_density: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相标况密度 kg/m³（SIM-31 std_liq_density 迁 ORM）"
    )
    liquid_mass_rate: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相质量流量 kg/h（SIM-31 JSONB 迁 ORM）"
    )
    liquid_actual_m3hr: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.6: 液相实际体积流量 m³/h（SIM-31 liq_actual_m3hr 迁 ORM）"
    )
    # === P3.x SIM-33: 气相物性 9 字段（spec §3.5 C/O，与 vapor_fraction ORM 对称）===
    vapor_mass_rate: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相质量流量 kg/h"
    )
    vapor_actual_m3hr: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相实际体积流量 m³/h"
    )
    vapor_normal_m3hr: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相标况体积流量 Nm³/h"
    )
    vapor_mw: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相分子量（与 molecular_weight 同义；专气相显示）"
    )
    vapor_density: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相密度 kg/m³（与 liquid_density 对称）"
    )
    vapor_z: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相压缩因子 Z（与 liquid_compressibility_factor 对称）"
    )
    vapor_cp: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相比热容 kJ/(kg·K)"
    )
    vapor_viscosity: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相动力粘度 Pa·s"
    )
    vapor_thermal_cond: Mapped[float | None] = mapped_column(
        Float, comment="SIM-33 §3.5: 气相导热系数 W/(m·K)"
    )
    enthalpy: Mapped[float | None] = mapped_column(Float)
    entropy: Mapped[float | None] = mapped_column(Float)
    bulk_density_min: Mapped[float | None] = mapped_column(Float)
    bulk_density_max: Mapped[float | None] = mapped_column(Float)
    true_density: Mapped[float | None] = mapped_column(Float)
    particle_size_avg: Mapped[float | None] = mapped_column(Float)
    particle_size_range: Mapped[str | None] = mapped_column(String(100))
    particle_shape: Mapped[str | None] = mapped_column(String(100))
    repose_angle: Mapped[float | None] = mapped_column(Float)
    vessel_cone_angle: Mapped[float | None] = mapped_column(Float)
    distillation_json: Mapped[dict | None] = mapped_column(JSONB, comment="馏程 IBP→FBP")
    sara_json: Mapped[dict | None] = mapped_column(JSONB)
    elemental_json: Mapped[dict | None] = mapped_column(JSONB)
    metals_json: Mapped[dict | None] = mapped_column(JSONB)
    feedstock_specs_json: Mapped[dict | None] = mapped_column(JSONB)
    product_specs_json: Mapped[dict | None] = mapped_column(JSONB)
    data_mode: Mapped[str] = mapped_column(
        String(20), comment="StreamDataMode：CHEMICAL/PETROLEUM/SOLID"
    )
    property_estimation_json: Mapped[dict | None] = mapped_column(JSONB)
    pseudo_components_json: Mapped[list | None] = mapped_column(JSONB)
    lab_report_ref: Mapped[str | None] = mapped_column(String(200))
    upstream_stream_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("streams.stream_id")
    )
    upstream_equipment_type: Mapped[str | None] = mapped_column(
        String(30), comment="PUMP/CV/PIPE/HEAT/RESTRICTION/FLASH"
    )
    upstream_equipment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, comment="设备记录 ID（多态，不强 FK）"
    )
    change_type: Mapped[str | None] = mapped_column(
        String(30),
        comment="StreamChangeType：ISOENTHALPIC/FRICTION_PRESSURE_DROP/HEAT_EXCHANGE/PUMP_WORK",
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        comment="SIM_IMPORT/MANUAL_ENTRY/LAB_REPORT/FLASH_CALCULATED/DEVICE_CALCULATED",
    )
    source_file: Mapped[str | None] = mapped_column(String(200))
    sign_status: Mapped[StreamSignStatus] = mapped_column(
        Enum(StreamSignStatus, name="streamsignstatus", native_enum=True),
        nullable=False,
        default=StreamSignStatus.DRAFT,
        index=True,
    )
    approval_step: Mapped[int | None] = mapped_column(comment="当前校对步骤")
    approval_depth: Mapped[int] = mapped_column(
        Integer, nullable=False, comment="校对深度 1~2"
    )
    checked_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    last_change_reason: Mapped[str | None] = mapped_column(
        String(30),
        comment="StreamChangeReason：SIM_REIMPORT/CLIENT_DATA_UPDATE/DESIGN_CONFIRMATION/IMPORT_ERROR_FIX/OTHER",
    )
    last_change_note: Mapped[str | None] = mapped_column(String(500))
    last_changed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    last_changed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # === P3.2 SIM 新增字段（spec V1.6 §3.2.2 + §3.2.3，2026-09-08）===
    case_type: Mapped[str | None] = mapped_column(
        String(20),
        comment="物流级 case_type：NORMAL/END_OF_RUN/START_OF_RUN/TURN_DOWN（设计工况）",
    )
    # surface_tension 已在 SIM-33 重命名为 liquid_surface_tension（spec §3.6）
    api_gravity: Mapped[float | None] = mapped_column(
        Float, comment="API 度（°API），石油馏分专用"
    )
    specific_gravity: Mapped[float | None] = mapped_column(
        Float, comment="SIM-31 §1.2.1: 比重（water=1.0），对称 api_gravity"
    )
    # === P3.x SIM-34: 炼油专用 5 字段（ADD-001 §3.8-3.9）===
    rvp: Mapped[float | None] = mapped_column(
        Float, comment="SIM-34 §3.8: Reid Vapor Pressure psi"
    )
    tvp: Mapped[float | None] = mapped_column(
        Float, comment="SIM-34 §3.8: True Vapor Pressure psi"
    )
    watson_k: Mapped[float | None] = mapped_column(
        Float, comment="SIM-34 §3.8: Watson characterization K-factor (UOP K)"
    )
    flash_point: Mapped[float | None] = mapped_column(
        Float, comment="SIM-34 §3.8: 闪点 °C"
    )
    distillation_curves: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="SIM-34 §3.9: 蒸馏曲线 8 种 schema（D86/TBP/EFV/D86_CRACKING/D1160/D2887/D5236/D7169）",
    )
    critical_temp: Mapped[float | None] = mapped_column(
        Float, comment="临界温度 K"
    )
    critical_press: Mapped[float | None] = mapped_column(
        Float, comment="临界压力 Pa"
    )
    actual_vol_flow: Mapped[float | None] = mapped_column(
        Float, comment="工况体积流量 m³/h（≠ 已有 volumetric_flow 标准体积）"
    )
    viscosity_temperature_curve: Mapped[dict | None] = mapped_column(
        JSONB, comment="粘度-温度曲线 [{temp_k, viscosity_cp}, ...]"
    )
    import_original_row: Mapped[int | None] = mapped_column(
        Integer, comment="PRO/II 原始行号（溯源）"
    )
    import_source_version: Mapped[str | None] = mapped_column(
        String(20),
        comment="PRO/II 解析器版本：V2.71/V4.17/V8.x",
    )
    is_unreliable: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment="PRO/II 不可靠流标记（NULL=未设/False；TRUE=NOT_CONVERGED/ABORTED 单元产品）",
    )
    is_mixed_phase: Mapped[bool | None] = mapped_column(
        Boolean,
        nullable=True,
        comment=(
            "PRO/II 原始相态 MIXED 标记（TRUE=汽液混相，phase 因 MVP 未抽组成置 None；"
            "NULL=未设/False，多用于手工/Excel 入口或 PRO/II 非 MIXED）"
        ),
    )
    # === P3.2 SIM-13：状态机字段（被 StateMachineService.transition() setattr）===
    change_pending_since: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        comment="INITIATE_CHANGE / MARK_STALE 触发时间",
    )
    change_resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), comment="APPLY_CHANGE 完成时间（pass_change 闭环）"
    )
    change_resolved_by: Mapped[str | None] = mapped_column(
        String(64), comment="APPLY_CHANGE 审批人 ID（str(uuid) 形式）"
    )

    # === P3.x SIM-17: streams 4 字段 ===
    # simulation_status / tear_stream / estimated / stream_properties_json
    simulation_status: Mapped[str | None] = mapped_column(
        String(30),
        comment="SIM-17 §3.2.4: SOLVED/ESTIMATED/MEASURED/MANUAL/UNKNOWN（PRO/II 导入标记）",
    )
    tear_stream: Mapped[bool | None] = mapped_column(
        Boolean,
        comment="SIM-17 §3.2.4: TRUE=撕裂流（收敛循环起点；下游计算模块需特殊处理）",
    )
    estimated: Mapped[bool | None] = mapped_column(
        Boolean,
        comment="SIM-17 §3.2.4: TRUE=物性被估算（SIM-21 CoolProp/Joback 等自动补全）",
    )
    stream_properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="SIM-17 §3.2.4: 流物性包（MW/Tc/Pc/Vc/Zc/acentric + VLE/HV 系数）",
    )

    # === P3.x SIM-18: streams 4 JSON 字段 ===
    # user_provided/calculated/effective/conflict_resolutions_json
    user_provided_properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="SIM-18 §3.6 ADD-002: 用户提供的物性（手工/Excel 入口）",
    )
    calculated_properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="SIM-18 §3.6 ADD-002: SIM-3 自动补全的物性（Joback/Lee-Kesler/Rackett/CoolProp）",
    )
    effective_properties_json: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="SIM-18 §3.6 ADD-002: 实际生效的物性（user_provided > calculated > default）",
    )
    conflict_resolutions_json: Mapped[dict | None] = mapped_column(
        JSONB,
        comment="SIM-18: PropertyConflictResolver 输出（用户值 vs 计算值冲突解决记录）",
    )

    # SIM-13 D-3 闭环：selectinload 防 N+1 — 状态点反向关系
    state_points: Mapped[list["StreamStatePoint"]] = relationship(  # noqa: F821
        "StreamStatePoint",
        back_populates="stream",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class StreamStatePoint(Base):
    """工况状态点（ADR-0020）。无 sign_status（跟随所属物流）。字典表3 逐字。

    (stream_id, case_type, state_label) 三元组唯一（SIM-10 闭环 bug-062）：
    同 stream 不同 case_type 可并存（NORMAL/MAX/MIN/ALTERNATE），同 case_type
    重复 state_label 由 DB 兜底，service 层 IntegrityError 转 SIM_STATEPOINT_BLOCKED。
    """

    __tablename__ = "stream_state_points"
    __table_args__ = (
        CheckConstraint(
            "case_type IN ('NORMAL','MIN','MAX','ALTERNATE')",
            name="ck_stream_state_points_case_type",
        ),
        UniqueConstraint(
            "stream_id",
            "case_type",
            "state_label",
            name="uq_stream_state_points_label",
        ),
    )
    state_point_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    stream_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("streams.stream_id"), index=True
    )
    state_label: Mapped[str] = mapped_column(String(50))
    case_type: Mapped[str] = mapped_column(
        String(20), comment="NORMAL/MIN/MAX/ALTERNATE"
    )
    temp: Mapped[float] = mapped_column(Float)
    press: Mapped[float] = mapped_column(Float)
    phase: Mapped[str] = mapped_column(String(20))
    vapor_fraction: Mapped[float | None] = mapped_column(Float)
    mass_flow: Mapped[float] = mapped_column(Float)
    composition_json: Mapped[dict] = mapped_column(JSONB)
    vapor_composition_json: Mapped[dict | None] = mapped_column(JSONB)
    liquid_composition_json: Mapped[dict | None] = mapped_column(JSONB)
    density: Mapped[float | None] = mapped_column(Float)
    viscosity_dynamic: Mapped[float | None] = mapped_column(Float)
    enthalpy: Mapped[float | None] = mapped_column(Float)
    entropy: Mapped[float | None] = mapped_column(Float)
    record_hash: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    estimated_flags_json: Mapped[dict | None] = mapped_column(JSONB)
    profile_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="沿程剖面 distance/pressures/temperatures"
    )
    source_type: Mapped[str] = mapped_column(
        String(30),
        comment="SIM_IMPORT/MANUAL_ENTRY/FLASH_CALCULATED/DEVICE_CALCULATED（无 LAB_REPORT）",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # SIM-13 D-3 闭环：selectinload 防 N+1 — 反向关系
    stream: Mapped["Stream"] = relationship(  # noqa: F821
        "Stream", back_populates="state_points"
    )
