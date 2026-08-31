import uuid

from sqlalchemy import (
    Boolean,
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
    created_at = mapped_column(__import__("sqlalchemy").DateTime(timezone=True))
