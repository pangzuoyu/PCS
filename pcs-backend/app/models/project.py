import uuid
from datetime import datetime

from sqlalchemy import (
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
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import StreamSignStatus, UserStatus
from app.models.mixins import RecordMixin, TimestampMixin


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
        comment="ApprovalRole 7 值：DESIGNER/CHECKER/REVIEWER/APPROVER/SYSADMIN/PROCESS_CONTROLLER/DATA_ADMIN",
    )
    ad_groups: Mapped[list[str]] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(20), default=UserStatus.ACTIVE.value)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Stream(TimestampMixin, Base):
    """物流=管段（ADR-0019）。4 态简化门禁（ADR-0014）。字典表2 逐字。"""

    __tablename__ = "streams"
    __table_args__ = (
        UniqueConstraint("project_id", "stream_name", name="uq_streams_project_stream_name"),
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
    density: Mapped[float | None] = mapped_column(Float)
    viscosity_dynamic: Mapped[float | None] = mapped_column(Float)
    viscosity_kinematic: Mapped[float | None] = mapped_column(Float)
    thermal_conductivity: Mapped[float | None] = mapped_column(Float)
    specific_heat: Mapped[float | None] = mapped_column(Float)
    molecular_weight: Mapped[float | None] = mapped_column(Float)
    compressibility_factor: Mapped[float | None] = mapped_column(Float)
    vapor_fraction: Mapped[float | None] = mapped_column(Float)
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


class StreamStatePoint(Base):
    """工况状态点（ADR-0020）。无 sign_status（跟随所属物流）。字典表3 逐字。"""

    __tablename__ = "stream_state_points"
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
