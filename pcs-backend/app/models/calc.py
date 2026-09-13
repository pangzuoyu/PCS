import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import (
    CheckResult,
    DesignStage,
    FlowPattern,
    PipeType,
    PumpOperation,
    TwoPhaseCheck,
)
from app.models.mixins import RecordMixin, TaggedRecordMixin


class FlashResult(TaggedRecordMixin, Base):
    __tablename__ = "flash_results"
    flash_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    stream_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("streams.stream_id"), index=True)
    calc_type: Mapped[str] = mapped_column(String(30))
    method: Mapped[str] = mapped_column(String(20))
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class PipingResult(RecordMixin, Base):
    """管道记录（字典表16）。line_no 位号唯一含 OBSOLETE。"""

    __tablename__ = "piping_results"
    __table_args__ = (
        # unique constraint (project_id, line_no) is set via naming convention on declared_attr
    )
    pipe_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    seq_no: Mapped[int] = mapped_column(comment="一览表序号")
    line_no: Mapped[str] = mapped_column(String(50), unique=False)
    line_size: Mapped[str] = mapped_column(String(20))
    material_class: Mapped[str] = mapped_column(
        String(20), ForeignKey("pipe_classes.class_id"), comment="材料等级"
    )
    fluid_code: Mapped[str] = mapped_column(String(10))
    fluid_name: Mapped[str] = mapped_column(String(100))
    fluid_phase: Mapped[str] = mapped_column(String(20))
    fluid_category: Mapped[str] = mapped_column(String(10), comment="D/M/NORMAL")
    toxic_class: Mapped[str | None] = mapped_column(String(30))
    pipe_grade: Mapped[str | None] = mapped_column(String(30))
    insulation_code: Mapped[str | None] = mapped_column(String(20))
    insulation_thickness: Mapped[float | None] = mapped_column(Float, comment="mm")
    paint_code: Mapped[str | None] = mapped_column(String(20))
    tracing_type: Mapped[str | None] = mapped_column(String(10), comment="J/T/TE/NONE")
    holding_temp: Mapped[float | None] = mapped_column(Float, comment="°C")
    source_pid: Mapped[str] = mapped_column(String(50), comment="P&ID 引用")
    line_from: Mapped[str] = mapped_column(String(100))
    line_to: Mapped[str] = mapped_column(String(100))
    norm_oper_press: Mapped[float] = mapped_column(Float, comment="MPaG")
    max_oper_press: Mapped[float] = mapped_column(Float)
    norm_oper_temp: Mapped[float] = mapped_column(Float, comment="°C")
    max_oper_temp: Mapped[float] = mapped_column(Float)
    alt_norm_oper_press: Mapped[float | None] = mapped_column(Float)
    alt_max_oper_press: Mapped[float | None] = mapped_column(Float)
    alt_norm_oper_temp: Mapped[float | None] = mapped_column(Float)
    alt_max_oper_temp: Mapped[float | None] = mapped_column(Float)
    design_press: Mapped[float] = mapped_column(Float, comment="MPaG")
    design_vacuum: Mapped[float | None] = mapped_column(Float)
    design_temp: Mapped[float] = mapped_column(Float)
    design_min_temp: Mapped[float | None] = mapped_column(Float)
    piping_category: Mapped[str] = mapped_column(String(10), comment="GC1/GC2/GC3")
    pressure_test_medium: Mapped[str] = mapped_column(String(10), comment="WATER/AIR")
    pressure_test_press: Mapped[float] = mapped_column(Float)
    ndt_method: Mapped[str | None] = mapped_column(String(10), comment="RT/UT/MT/PT/NONE")
    ndt_ratio: Mapped[float | None] = mapped_column(Float, comment="%")
    ndt_tech_level: Mapped[str | None] = mapped_column(String(10))
    leak_test_medium: Mapped[str | None] = mapped_column(String(10), comment="AIR/WATER")
    leak_test_press: Mapped[float | None] = mapped_column(Float)
    check_class: Mapped[str] = mapped_column(String(5), comment="I~V")
    cleaning_method: Mapped[list | None] = mapped_column(JSONB, comment="PI/PA/DG/SO 多选")
    stress_analysis_level: Mapped[str | None] = mapped_column(String(10))
    remark: Mapped[str | None] = mapped_column(String(500))
    # P4-0-2 SUP-008 OPEN-008 字段（11 列）
    line_description: Mapped[str | None] = mapped_column(String(200))
    pipe_type: Mapped[PipeType | None] = mapped_column(
        Enum(PipeType, name="pipe_type_enum", native_enum=True)
    )
    max_flow_factor: Mapped[float | None] = mapped_column(Float)
    selected_diameter: Mapped[float | None] = mapped_column(Float, comment="mm")
    liquid_velocity_max: Mapped[float | None] = mapped_column(Float, comment="m/s")
    gas_velocity_max: Mapped[float | None] = mapped_column(Float, comment="m/s")
    pressure_drop_per_100m: Mapped[float | None] = mapped_column(
        Float, comment="kPa/100m"
    )
    selected_pipe_size: Mapped[str | None] = mapped_column(String(20))
    recommended_pipe_size: Mapped[str | None] = mapped_column(String(20))
    check_result: Mapped[CheckResult | None] = mapped_column(
        Enum(CheckResult, name="check_result_enum", native_enum=True)
    )
    velocity_range_reference: Mapped[str | None] = mapped_column(String(100))


class PipeNetworkResult(TaggedRecordMixin, Base):
    __tablename__ = "pipe_network_results"
    network_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class PumpResult(TaggedRecordMixin, Base):
    __tablename__ = "pump_results"
    pump_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    basic_info_json: Mapped[dict] = mapped_column(JSONB)
    fluid_properties_json: Mapped[dict] = mapped_column(JSONB)
    flow_rates_json: Mapped[dict] = mapped_column(JSONB)
    suction_calculation_json: Mapped[dict] = mapped_column(JSONB)
    discharge_calculation_json: Mapped[dict] = mapped_column(JSONB)
    differential_pressure_json: Mapped[dict] = mapped_column(JSONB)
    design_pressure_json: Mapped[dict] = mapped_column(JSONB)
    power_consumption_json: Mapped[dict] = mapped_column(JSONB)
    control_valve_json: Mapped[dict | None] = mapped_column(JSONB)
    equivalent_length_json: Mapped[dict | None] = mapped_column(JSONB)
    pressure_drop_details_json: Mapped[dict | None] = mapped_column(JSONB)
    line_references_json: Mapped[dict | None] = mapped_column(JSONB)
    actual_head: Mapped[float | None] = mapped_column(Float)
    actual_efficiency: Mapped[float | None] = mapped_column(Float)
    actual_motor_power: Mapped[float | None] = mapped_column(Float)
    actual_npshr: Mapped[float | None] = mapped_column(Float)
    vendor_model: Mapped[str | None] = mapped_column(String(100))
    actual_data_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    # P4-0-2 SUP-008 OPEN-008/009 字段（5 列：4 选型 + design_stage）
    selected_pump_model: Mapped[str | None] = mapped_column(String(100))
    selected_motor_model: Mapped[str | None] = mapped_column(String(100))
    selected_motor_power: Mapped[float | None] = mapped_column(Float, comment="kW")
    pump_operation: Mapped[PumpOperation | None] = mapped_column(
        Enum(PumpOperation, name="pump_operation_enum", native_enum=True)
    )
    design_stage: Mapped[DesignStage] = mapped_column(
        Enum(DesignStage, name="design_stage_enum", native_enum=True),
        nullable=False,
        default=DesignStage.BASIC,
        comment="设计阶段 BASIC/DETAIL（OPEN-009）",
    )


class PsvResult(TaggedRecordMixin, Base):
    __tablename__ = "psv_results"
    psv_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    set_pressure: Mapped[float] = mapped_column(Float)
    relief_capacity: Mapped[float] = mapped_column(Float)
    orifice_area: Mapped[float] = mapped_column(Float)
    blowdown: Mapped[float] = mapped_column(Float)
    orifice_designation: Mapped[str] = mapped_column(String(20))
    inlet_size: Mapped[str] = mapped_column(String(20))
    outlet_size: Mapped[str] = mapped_column(String(20))
    relief_scenario: Mapped[list] = mapped_column(JSONB, comment="enum[] 多选")
    # P4-0-2 OPEN-009 设计阶段
    design_stage: Mapped[DesignStage] = mapped_column(
        Enum(DesignStage, name="design_stage_enum", native_enum=True),
        nullable=False,
        default=DesignStage.BASIC,
        comment="设计阶段 BASIC/DETAIL（OPEN-009）",
    )


class FlareSystemResult(TaggedRecordMixin, Base):
    __tablename__ = "flare_system_results"
    flare_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class VesselResult(TaggedRecordMixin, Base):
    __tablename__ = "vessel_results"
    vessel_calc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)
    # P4-0-2 OPEN-009 设计阶段
    design_stage: Mapped[DesignStage] = mapped_column(
        Enum(DesignStage, name="design_stage_enum", native_enum=True),
        nullable=False,
        default=DesignStage.BASIC,
        comment="设计阶段 BASIC/DETAIL（OPEN-009）",
    )


class TwoPhaseResult(Base):
    """两相流水力学结果（SUP-008 §8.3.4，P4-0-2 OPEN-008）。

    仅含 brief 列出的 13 字段（PK + input/output JSONB + 业务 + 时间戳），
    不继承 TaggedRecordMixin：与其他新表（sim_tower_results / sim_unit_op_*）
    一致；bit_number / record_hash / 审批等门禁由后续 P4-TASK0 / 批次按需扩展。
    """

    __tablename__ = "two_phase_results"
    two_phase_calc_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    input_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    output_json: Mapped[dict] = mapped_column(JSONB, nullable=False)
    Bx: Mapped[float | None] = mapped_column(Float, comment="Lockhart-Martinelli 参数")
    By: Mapped[float | None] = mapped_column(Float, comment="Lockhart-Martinelli 参数")
    flow_pattern: Mapped[FlowPattern | None] = mapped_column(
        Enum(FlowPattern, name="flow_pattern_enum", native_enum=True)
    )
    two_phase_check: Mapped[TwoPhaseCheck | None] = mapped_column(
        Enum(TwoPhaseCheck, name="two_phase_check_enum", native_enum=True)
    )
    liquid_velocity: Mapped[float | None] = mapped_column(Float, comment="m/s")
    gas_velocity: Mapped[float | None] = mapped_column(Float, comment="m/s")
    pressure_gradient: Mapped[float | None] = mapped_column(Float, comment="kPa/m")
    void_fraction: Mapped[float | None] = mapped_column(Float)
    calc_method: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True))


class SepEquipResult(TaggedRecordMixin, Base):
    __tablename__ = "sep_equip_results"
    sep_calc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class HeatResult(TaggedRecordMixin, Base):
    __tablename__ = "heat_results"
    heat_calc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exchanger_category: Mapped[str] = mapped_column(String(30), comment="SHELL_TUBE/AIR_COOL/PLATE")
    air_side_json: Mapped[dict | None] = mapped_column(JSONB)
    design_conditions_json: Mapped[dict] = mapped_column(JSONB)
    enthalpy_table_json: Mapped[dict | None] = mapped_column(JSONB)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class CvResult(TaggedRecordMixin, Base):
    __tablename__ = "cv_results"
    cv_calc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    cv_value: Mapped[float] = mapped_column(Float)
    flow_rate: Mapped[float] = mapped_column(Float)
    pressure_drop: Mapped[float] = mapped_column(Float)
    choked_flow: Mapped[bool] = mapped_column(Boolean, default=False)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class RestrictionResult(TaggedRecordMixin, Base):
    __tablename__ = "restriction_results"
    orifice_calc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    restriction_type: Mapped[str] = mapped_column(String(30), comment="ORIFICE/PLATE/...")
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class CoolingTowerResult(TaggedRecordMixin, Base):
    __tablename__ = "cooling_tower_results"
    ct_calc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class PsychroResult(TaggedRecordMixin, Base):
    __tablename__ = "psychro_results"
    psychro_calc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    calc_type: Mapped[str] = mapped_column(String(30))
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class OpenChannelResult(TaggedRecordMixin, Base):
    __tablename__ = "open_channel_results"
    channel_calc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    channel_type: Mapped[str] = mapped_column(String(30))
    cross_section_json: Mapped[dict] = mapped_column(JSONB)
    flow_rate: Mapped[float] = mapped_column(Float)
    depth: Mapped[float] = mapped_column(Float)
    velocity: Mapped[float] = mapped_column(Float)
    slope: Mapped[float] = mapped_column(Float)


class FiltrationResult(TaggedRecordMixin, Base):
    __tablename__ = "filtration_results"
    filter_calc_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    filter_type: Mapped[str] = mapped_column(String(30))
    area: Mapped[float] = mapped_column(Float)
    cycle_time: Mapped[float] = mapped_column(Float, comment="h")
    pressure_drop: Mapped[float] = mapped_column(Float)


class CostEstResult(Base):
    """cost_est 与设备一对一，不带 sign_status（跟随所属设备）。"""

    __tablename__ = "cost_est_results"
    cost_est_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipment_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("equipment_list.equipment_id"), unique=True
    )
    estimated_cost: Mapped[float] = mapped_column(Numeric(18, 2))
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    cost_index_year: Mapped[int] = mapped_column(Integer)
    created_at = mapped_column(DateTime(timezone=True))
