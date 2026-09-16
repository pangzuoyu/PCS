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
    ReliefScenario,
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
    # P4-4-4 PUMP 链：链完整入出参 JSON（与 PIPE/PIPE_NET 同语义）
    input_json: Mapped[dict | None] = mapped_column(JSONB, comment="PUMP 链入参（P4-4-4）")
    output_json: Mapped[dict | None] = mapped_column(JSONB, comment="PUMP 链出参（P4-4-4）")


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


class ReliefResult(RecordMixin, Base):
    """泄放计算结果（SUP-008 §8.3.2 + P5-OPEN-005，psv_results 选型前置）。

    泄放量计算输入 source_equipment_id（多态：reactor/vessel/heat exchanger），
    输出 required_relief_area + selected_psv_id 反查 psv_results。relief_results
    自身不输出设备记录——只承载 API 521 / GB/T 150.1 附录 B 泄放量计算。

    design_stage 不下沉（§8.4 OPEN-009 限 VESSEL/PSV/COLUMN，relief_results 是
    PSV 选型上游，非 COLUMN）；psv_results 已带 design_stage。

    RecordMixin 全套：sign_status/record_hash/approval_* 与其他 16 张计算表一致；
    workspace_id 业务隔离（SUP-008 §8.3.2 未显式列出，按 P5-0-1a 决策 4 加）。
    """

    __tablename__ = "relief_results"
    relief_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    source_equipment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        index=True,
        comment="源设备（多态 FK：reactor/vessel/heat_exchanger，不加 DB 级 FK）",
    )
    relief_scenario: Mapped[ReliefScenario] = mapped_column(
        Enum(ReliefScenario, name="relief_scenario_enum", native_enum=True),
        nullable=False,
        comment="泄放工况（SUP-008 §8.3.2 + P5-OPEN-005 合并 6 态）",
    )
    reactor_volume: Mapped[float | None] = mapped_column(Float, comment="反应器/容器总体积 m³")
    reactor_diameter: Mapped[float | None] = mapped_column(Float, comment="直径 m")
    reactor_height: Mapped[float | None] = mapped_column(Float, comment="高度 m")
    gas_tight_pressure: Mapped[float | None] = mapped_column(Float, comment="气密试验压力 Bar")
    safety_factor: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.2, comment="安全系数（默认 1.2）"
    )
    relief_rate_tier_1: Mapped[float] = mapped_column(
        Float, nullable=False, default=0.7, comment="第一档泄放率 MPa/min（API 521 推荐 0.7）"
    )
    relief_rate_tier_2: Mapped[float] = mapped_column(
        Float, nullable=False, default=1.4, comment="第二档泄放率 MPa/min（API 521 推荐 1.4）"
    )
    relief_rate_tier_3: Mapped[float] = mapped_column(
        Float, nullable=False, default=2.1, comment="第三档泄放率 MPa/min（API 521 推荐 2.1）"
    )
    required_relief_area: Mapped[float | None] = mapped_column(
        Float, comment="所需泄放面积 cm²（API 521 公式输出）"
    )
    selected_psv_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid,
        ForeignKey("psv_results.psv_id"),
        comment="选型 PSV（反查 psv_results）；可空：未选型前",
    )


class ColumnSizingResult(RecordMixin, Base):
    """塔径核算结果（SUP-008 §8.3.3 + P5-OPEN-005，VESSEL/PSV/COLUMN 三表之一）。

    VESSEL/PSV/COLUMN §8.4 OPEN-009：design_stage 列下沉（P5-0-1a 决策）。

    决策说明：
    - RecordMixin 而非 TaggedRecordMixin（SUP-008 §8.3.3 业务位号字段是 column_tag
      非 tag_number；tag_number 留空；service 层强制 (project_id, column_tag) 唯一）
    - 与 vessel_results / psv_results 同构：design_stage(enum, NOT NULL default BASIC)
    """

    __tablename__ = "column_sizing"
    column_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    column_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    column_name: Mapped[str | None] = mapped_column(String(200))
    hysys_flooding_percent: Mapped[float | None] = mapped_column(Float, comment="HYSYS 泛点率 %")
    hysys_calc_diameter_mm: Mapped[float | None] = mapped_column(
        Float, comment="HYSYS 计算塔径 mm"
    )
    selected_diameter_mm: Mapped[float | None] = mapped_column(Float, comment="选取塔径 mm")
    reference_diameter_mm: Mapped[float | None] = mapped_column(Float, comment="参考塔径 mm")
    tray_spacing_mm: Mapped[float | None] = mapped_column(Float, comment="板间距 mm")
    tray_count: Mapped[int | None] = mapped_column(Integer, comment="实际塔板数")
    theoretical_tray_count: Mapped[int | None] = mapped_column(
        Integer, comment="理论塔板数"
    )
    overall_efficiency: Mapped[float | None] = mapped_column(Float, comment="总板效率 %")
    calc_date: Mapped[DateTime | None] = mapped_column(DateTime, comment="计算日期")
    # P5-OPEN-005 §8.4 OPEN-009：VESSEL/PSV/COLUMN 三表 design_stage 下沉
    design_stage: Mapped[DesignStage] = mapped_column(
        Enum(DesignStage, name="design_stage_enum", native_enum=True),
        nullable=False,
        default=DesignStage.BASIC,
        comment="设计阶段 BASIC/DETAIL（§8.4 OPEN-009）",
    )


class MixerResult(RecordMixin, Base):
    """混合器压降结果（SUP-008 §8.3.5 + P5-OPEN-005）。

    混合器（MI-101/MI-201 等）压降核算，2 路组分汇合 + check_result 校核。
    business 字段 mixer_tag 留 RecordMixin tag_number 空（与 column_sizing 同模式）；
    (project_id, mixer_tag) 唯一性由 service 层强制。
    """

    __tablename__ = "mixer_results"
    mixer_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    mixer_tag: Mapped[str] = mapped_column(String(50), nullable=False)
    mixer_name: Mapped[str | None] = mapped_column(String(200))
    component_1_name: Mapped[str | None] = mapped_column(String(100), comment="组分 1 名称")
    component_1_flow: Mapped[float | None] = mapped_column(Float, comment="流率 m³/h")
    component_2_name: Mapped[str | None] = mapped_column(String(100), comment="组分 2 名称")
    component_2_flow: Mapped[float | None] = mapped_column(Float, comment="流率 m³/h")
    pressure_drop_kpa: Mapped[float | None] = mapped_column(Float, comment="压降 kPa")
    check_result: Mapped[str | None] = mapped_column(
        String(20), comment="校核 PASS/WARNING/FAIL（与 check_result_enum 同语义字符串）"
    )


class TwoPhaseResult(Base):
    """两相流水力学结果（SUP-008 §8.3.4，P4-0-2 OPEN-008 + P4-TASK0 扩展）。

    P4-0-2 仅含 13 字段；P4-TASK0 补 record_hash 列以接入 calc_lineage 收口
    （RECORD_TYPE_REGISTRY 注册 + finalize_calc_record 可调）。其余门禁列
    （approval / change_* / obsoleted_*）暂不引入，避免破坏 P4-0-2 既有契约。
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
    # P4-TASK0：接入 calc_lineage 收口
    record_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="SHA-256 截断 16 hex；与 RecordMixin 同语义（P4-TASK0 扩展）",
    )


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
