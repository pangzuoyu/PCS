"""计算结果 ORM 模型（P5-3 计算引擎持久化）。

含 8 类 Result 表（FlashResult / PsvResult / VesselResult / Cv / CoolingTower /
Psychro / OpenChannel / Filtration）+ 4 类反应/平衡支撑表（ConstCpResult 等）。
所有表继承 TaggedRecordMixin（强制 tag_number NOT NULL）。
"""

import uuid

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    text,
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
    """闪蒸计算结果（flash_results 表，继承 TaggedRecordMixin 强制 tag_number）。

    业务：T/P/PT_FLASH 三类闪蒸结果；input_json/output_json JSONB 双容器
    （输入条件 + 输出物性/组成）；stream_id 索引关联源 stream。
    """

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
    """管网压降计算结果（pipe_network_results 表，继承 TaggedRecordMixin）。

    业务：管道网络图节点/边的逐段压降计算结果；output_json 承载每段管径+流速
    +压降+汇合点压力；tag_number 关联位号（与 stream/pipe 同项目内唯一）。
    """

    __tablename__ = "pipe_network_results"
    network_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class PumpResult(TaggedRecordMixin, Base):
    """泵选型/校核结果（pump_results 表，tag_number 位号 P-xxx 唯一）。

    业务：单级/多级离心泵流量扬程+效率+轴功率+NPSHa；input_params/output_params
    JSONB 双容器；API 610 type（OH1/OH2/BB1/BB3/VS1 等）锁定驱动校验。
    """

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
    """PSV 安全阀选型/校核结果（psv_results 表，V1.14 扩展 19 列）。

    业务：PSV 计算结果持久化（relief_scenario + sizing 物性 + 阀体选型 15 字段 +
    orifice 候选 + warnings JSON）；OPEN-10 V1.14 加 valve_type/body_material/
    bellows_material/flange_class/back_pressure_* + kb_factor/cdtp_applied 等。
    """

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
    # P5-0-5 Task 24a：PSV 多标准配置（SUP-P5-PSV-001 §3.2 + ADR-0028 V1.1）
    # standard_profile_code + standard_refs_json 在 P5-3 实施后转 NOT NULL
    standard_profile_code: Mapped[str | None] = mapped_column(
        String(16), comment="API / GB / CUSTOM（来自 project_calculation_standard_profiles）"
    )
    standard_refs_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="各子标准、版本、条款映射（canonical JSON）"
    )
    formula_ref_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="公式溯源（标准/版本/条款，受控词表）"
    )
    pending_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        comment="标准配置变更后旧记录需复核（G5 门禁）",
    )
    migrated_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        comment="历史项目迁移默认值（G6 门禁）",
    )
    override_reason: Mapped[str | None] = mapped_column(
        Text, comment="覆盖项目默认标准的理由（G7 门禁）"
    )
    override_approval_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="覆盖审批依据（与 override_reason 成对）"
    )
    # P5-OPEN-10 SUP-P5-PSV-002 V1.14 §3.1 选型 19 字段（净增；inlet/outlet/blowdown 已存在）
    valve_type: Mapped[str | None] = mapped_column(
        String(32), comment="SPRING_LOADED/BALANCED_BELLOWS/PILOT/RUPTURE_DISC（§3.2）"
    )
    body_material: Mapped[str | None] = mapped_column(
        String(32), comment="阀体材料 CARBON_STEEL/SS304/SS316/SS316L/ALLOY（§3.2）"
    )
    bellows_material: Mapped[str | None] = mapped_column(
        String(32), comment="波纹管材料 6 种（§3.8 仅 BALANCED_BELLOWS 必填）"
    )
    flange_class: Mapped[str | None] = mapped_column(
        String(8), comment="150#/300#/600#/900#/1500#/2500#（§3.2）"
    )
    back_pressure_type: Mapped[str | None] = mapped_column(
        String(16), comment="BUILT_UP / SUPERIMPOSED（§3.2）"
    )
    back_pressure_pct: Mapped[float | None] = mapped_column(
        Float, comment="背压百分比 0-50（§3.5）"
    )
    overpressure_pct: Mapped[float | None] = mapped_column(
        Float, comment="超压百分比 10/16/21（API 520 §5.3.1；§3.2）"
    )
    kb_factor: Mapped[float | None] = mapped_column(
        Float, comment="背压修正系数 Kb（§4.3；4 阶段策略）"
    )
    kb_source: Mapped[str | None] = mapped_column(
        String(32), comment="Kb 来源（none/manufacturer:X/api520_fig30/en4126/mixed:X+Y；§4.3）"
    )
    valve_brand: Mapped[str | None] = mapped_column(
        String(32), comment="阀体品牌（自由字符串；V1.14 P2-1 修订；§4.3）"
    )
    cdtp_applied: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        comment="CDTP 修正是否生效（SUPERIMPOSED + BP>0；§4.4）",
    )
    orifice_overridden: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        comment="用户手动指定 orifice_override（与 orifice_manual 成对；§4.5）",
    )
    orifice_manual: Mapped[str | None] = mapped_column(
        String(8), comment="手动指定孔口字母 D-T（§4.5）"
    )
    rupture_disc_position: Mapped[str | None] = mapped_column(
        String(16), comment="爆破膜位置 UPSTREAM/DOWNSTREAM/NONE（ASME UG-127；§3.2）"
    )
    rupture_disc_kc: Mapped[float | None] = mapped_column(
        Float, comment="爆破膜组合 Kc（UPSTREAM=0.90 / DOWNSTREAM=1.00；ASME UG-127）"
    )
    pilot_temperature_c: Mapped[float | None] = mapped_column(
        Float, comment="先导温度 °C（PILOT_OPERATED 字段；P5 占位）"
    )
    pilot_temp_class: Mapped[str | None] = mapped_column(
        String(16), comment="GENERAL/HIGH_TEMP/CRYOGENIC（PILOT_OPERATED；P5 占位）"
    )
    fire_protection: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        comment="防火保护（影响 FIRE 工况计算；§3.2）",
    )
    __table_args__ = (
        CheckConstraint(
            "(override_reason IS NULL AND override_approval_json IS NULL) OR "
            "(override_reason IS NOT NULL AND override_approval_json IS NOT NULL)",
            name="psv_override_paired_chk",
        ),
        CheckConstraint(
            "valve_type IS NULL OR valve_type IN "
            "('SPRING_LOADED', 'BALANCED_BELLOWS', 'PILOT_OPERATED', 'RUPTURE_DISC')",
            name="psv_valve_type_chk",
        ),
        CheckConstraint(
            "NOT cdtp_applied OR back_pressure_type = 'SUPERIMPOSED'",
            name="psv_cdtp_check",
        ),
        CheckConstraint(
            "(NOT orifice_overridden AND orifice_manual IS NULL) OR "
            "(orifice_overridden AND orifice_manual IS NOT NULL)",
            name="psv_orifice_overridden_check",
        ),
        Index(
            "idx_psv_results_pending_review",
            "project_id",
            postgresql_where=text("pending_review = TRUE"),
        ),
        Index(
            "idx_psv_results_migrated_default",
            "project_id",
            postgresql_where=text("migrated_default = TRUE"),
        ),
    )


class FlareSystemResult(TaggedRecordMixin, RecordMixin, Base):
    """FLARE_SYS 火炬系统计算结果（flare_system_results 表，P6-2 Task 18 重构）。

    业务：泄放汇总 / 总管尺寸 / 分液罐尺寸 / 筒体高度 / 辐射校验 / 火炬头选型。
    SPEC §3.2.3 + PCS-DICT-005 §3（radiation_check_json）+ PCS-DICT-007 §第五部分。

    字段双轨：平铺 Float/Boolean 列（report 直接 SELECT）+ JSONB 容器
    （input_json/output_json 业务子结构；radiation_check_json 独立 JSONB 存
    PCS-DICT-005 §3.1 辐射校验完整产物）。
    standard_profile_code 默认 API_521（C-07 锁定 String(16)）。

    RECORD_TYPE_REGISTRY 注册键 = "flare_system_result"（P6-2 Task 18）。
    """

    __tablename__ = "flare_system_results"
    flare_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 溯源
    standard_profile_code: Mapped[str] = mapped_column(
        String(16), nullable=False, default="API_521",
        comment="API_521（SPEC §3.2.3 默认；C-07 String(16) 锁定）",
    )
    calc_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="RELIEF_SUMMARY/HEADER_SIZING/KOD_SIZING/STACK_HEIGHT/RADIATION/FLARE_TIP",
    )
    # 结果（平铺字段，SPEC §3.2.3 字段平铺）
    total_relief_load_kg_h: Mapped[float | None] = mapped_column(Float, comment="kg/h")
    header_diameter_mm: Mapped[float | None] = mapped_column(Float, comment="mm")
    header_mach: Mapped[float | None] = mapped_column(Float, comment="马赫数")
    header_pressure_drop_kpa: Mapped[float | None] = mapped_column(Float, comment="kPa")
    kod_diameter_mm: Mapped[float | None] = mapped_column(Float, comment="mm")
    water_seal_height_mm: Mapped[float | None] = mapped_column(Float, comment="mm")
    stack_height_m: Mapped[float | None] = mapped_column(Float, comment="m")
    stack_diameter_m: Mapped[float | None] = mapped_column(Float, comment="m")
    radiation_at_grade_kw_m2: Mapped[float | None] = mapped_column(Float, comment="kW/m²")
    radiation_limit_kw_m2: Mapped[float | None] = mapped_column(Float, comment="kW/m²")
    pass_: Mapped[bool | None] = mapped_column(
        "pass", Boolean, nullable=True, comment="辐射校验 PASS/FAIL（SPEC §3.2.3）",
    )
    flare_tip_diameter_mm: Mapped[float | None] = mapped_column(Float, comment="mm")
    steam_for_smokeless_kg_h: Mapped[float | None] = mapped_column(Float, comment="kg/h")
    # JSONB 容器（PCS-DICT-005 §3.1 辐射校验独立列 + 通用 input/output）
    radiation_check_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="PCS-DICT-005 §3.1 辐射校验完整产物",
    )
    input_json: Mapped[dict | None] = mapped_column(JSONB, comment="入参（业务子结构）")
    output_json: Mapped[dict | None] = mapped_column(JSONB, comment="出参（业务子结构）")


class VesselResult(TaggedRecordMixin, Base):
    """容器（V-）设计/校核结果（vessel_results 表）。

    业务：立式/卧式容器直径+长度+壁厚+封头类型+风载/地震载荷；
    input_json/output_json 双容器，含 TEMA 类型（仅换热器容器相关）。
    """

    __tablename__ = "vessel_results"
    vessel_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
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
    # P5-0-5 Task 24a：PSV 多标准配置（SUP-P5-PSV-001 §3.2 + ADR-0028 V1.1）
    standard_profile_code: Mapped[str | None] = mapped_column(
        String(16), comment="API / GB / CUSTOM"
    )
    standard_refs_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="各子标准、版本、条款映射"
    )
    formula_ref_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="公式溯源（标准/版本/条款）"
    )
    pending_review: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        comment="标准配置变更后旧记录需复核（G5 门禁）",
    )
    migrated_default: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("FALSE"),
        comment="历史项目迁移默认值（G6 门禁）",
    )
    override_reason: Mapped[str | None] = mapped_column(
        Text, comment="覆盖项目默认标准的理由（G7 门禁）"
    )
    override_approval_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="覆盖审批依据"
    )
    __table_args__ = (
        CheckConstraint(
            "(override_reason IS NULL AND override_approval_json IS NULL) OR "
            "(override_reason IS NOT NULL AND override_approval_json IS NOT NULL)",
            name="relief_override_paired_chk",
        ),
        Index(
            "idx_relief_results_pending_review",
            "project_id",
            postgresql_where=text("pending_review = TRUE"),
        ),
        Index(
            "idx_relief_results_migrated_default",
            "project_id",
            postgresql_where=text("migrated_default = TRUE"),
        ),
    )


class ColumnSizingResult(RecordMixin, Base):
    """塔径核算结果（SUP-008 §8.3.3 + P5-OPEN-005，VESSEL/PSV/COLUMN 三表之一）。

    VESSEL/PSV/COLUMN §8.4 OPEN-009：design_stage 列下沉（P5-0-1a 决策）。

    决策说明：
    - RecordMixin 而非 TaggedRecordMixin（SUP-008 §8.3.3 业务位号字段是 column_tag
      非 tag_number；tag_number 留空；service 层强制 (project_id, column_tag) 唯一）
    - 与 vessel_results / psv_results 同构：design_stage(enum, NOT NULL default BASIC)

    **过渡态**（P5-0 批约束 1，2026-09-16 用户裁决 Q2 路径 A）：
    column_tag 列是 P5-0-1a 临时命名。Task 4（P5-0-4 PK rename + flatten）将统一改造为
    tag_number mixin 字段，与 16 张计算表一致。改造方式：
    - alembic: ALTER TABLE column_sizing RENAME COLUMN column_tag TO tag_number
    - ORM: Mapped["column_tag"] → Mapped["tag_number"]（保留 column_tag 业务字段名作为兼容）
    - 影响面：迁移文件 + ORM + 任何引用 column_tag 的 service / test
    """

    __tablename__ = "column_sizing"
    column_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    tag_number: Mapped[str] = mapped_column(String(50), nullable=False)
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
    two_phase_id: Mapped[uuid.UUID] = mapped_column(
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
    """分离设备（旋风/丝网/重力）选型/校核结果（sep_equip_results 表）。

    业务：device_type ∈ {CYCLONE/MIST_ELIMINATOR/GRAVITY_SEPARATOR}；
    input_params/output_params JSONB 容器，含分离效率+压降+尺寸。
    """

    __tablename__ = "sep_equip_results"
    sep_equip_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)


class HeatResult(TaggedRecordMixin, Base):
    """换热器计算结果（P5-0-2 Task 2 双轨扩展，ADR-0027 V1.0）。

    **双轨结构**：
    - 9 旧标量：equipment_no/equipment_name/**duty**/effective_area/4 压力/u_overall
    - 5 现状 JSONB：air_side/design_conditions/enthalpy_table/input/output
    - 39 新标量 + 3 新 JSONB：详 SUP-009 V1.0 §3.1

    **duty 双轨**（ADR-0027 V1.0 决策 5 跟踪项 — P5-4 已落地）：
    - `duty`（9 旧共享列）：保留向后兼容；新写入同时落双轨
    - `duty_legacy`：P4 上游 duty（即 inp.duty 路径）
    - `duty_calc`：P5 计算 duty（即 htri.heat_duty_w 路径）
    现有 `duty` 默认按溯源未知处理，迁移回填至 `duty_calc`（详 p5_4_heat_duty_split 迁移）。

    PK rename（heat_exchanger_id → heat_calc_id，DICT V3.4 方向）待 Task 4a。
    """
    __tablename__ = "heat_results"
    heat_exchanger_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    exchanger_category: Mapped[str] = mapped_column(String(30), comment="SHELL_TUBE/AIR_COOL/PLATE")
    air_side_json: Mapped[dict | None] = mapped_column(JSONB)
    design_conditions_json: Mapped[dict] = mapped_column(JSONB)
    enthalpy_table_json: Mapped[dict | None] = mapped_column(JSONB)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)
    # === 9 旧标量（P5-OPEN-006 保留列，详 ADR-0027 决策 1）===
    equipment_no: Mapped[str | None] = mapped_column(String(30))
    equipment_name: Mapped[str | None] = mapped_column(String(100))
    duty: Mapped[float | None] = mapped_column(Float, comment="9 旧与新轨共享 1 列（向后兼容）")
    # === duty 双轨（ADR-0027 V1.0 决策 5 跟踪项 — P5-4 落地）===
    duty_legacy: Mapped[float | None] = mapped_column(Float, comment="P4 上游 duty")
    duty_calc: Mapped[float | None] = mapped_column(Float, comment="P5 计算 duty")
    effective_area: Mapped[float | None] = mapped_column(Float)
    hot_inlet_pressure: Mapped[float | None] = mapped_column(Float)
    hot_outlet_pressure: Mapped[float | None] = mapped_column(Float)
    cold_inlet_pressure: Mapped[float | None] = mapped_column(Float)
    cold_outlet_pressure: Mapped[float | None] = mapped_column(Float)
    u_overall: Mapped[float | None] = mapped_column(Float)
    # === 39 新标量（SUP-009 §3.1.1-3.1.6，详 ADR-0027 决策 5）===
    # §3.1.1 基础标识 7
    exchanger_type: Mapped[str | None] = mapped_column(String(20), comment="DEU/BEM/AEL/ACHE")
    orientation: Mapped[str | None] = mapped_column(String(20), comment="Horizontal/Vertical")
    units_series: Mapped[int | None] = mapped_column(Integer)
    units_parallel: Mapped[int | None] = mapped_column(Integer)
    shells_per_unit: Mapped[int | None] = mapped_column(Integer)
    total_area_gross: Mapped[float | None] = mapped_column(Float, comment="m²")
    total_area_eff: Mapped[float | None] = mapped_column(Float, comment="m²")
    # §3.1.2 通用热工 8（除 duty 共享 9 旧）
    lmtd: Mapped[float | None] = mapped_column(Float, comment="对数平均温差 °C")
    mtd_corrected: Mapped[float | None] = mapped_column(Float, comment="校正后平均温差 °C")
    emtd: Mapped[float | None] = mapped_column(Float, comment="有效平均温差 °C")
    overdesign_percent: Mapped[float | None] = mapped_column(Float, comment="%")
    u_service: Mapped[float | None] = mapped_column(Float, comment="W/m²·K")
    u_calculated: Mapped[float | None] = mapped_column(Float, comment="W/m²·K")
    u_clean: Mapped[float | None] = mapped_column(Float, comment="W/m²·K")
    heat_exchange_area: Mapped[float | None] = mapped_column(Float, comment="m²")
    # §3.1.4 通用几何 9
    tube_count: Mapped[int | None] = mapped_column(Integer)
    tube_od: Mapped[float | None] = mapped_column(Float, comment="mm")
    tube_id: Mapped[float | None] = mapped_column(Float, comment="mm")
    tube_wall_thickness: Mapped[float | None] = mapped_column(Float, comment="mm")
    tube_length: Mapped[float | None] = mapped_column(Float, comment="m")
    tube_pitch: Mapped[float | None] = mapped_column(Float, comment="mm")
    tube_layout: Mapped[str | None] = mapped_column(String(10), comment="30/45/60/90")
    tube_material: Mapped[str | None] = mapped_column(String(100))
    tube_passes: Mapped[int | None] = mapped_column(Integer)
    # §3.1.5 壳程几何 10
    shell_id: Mapped[float | None] = mapped_column(Float, comment="mm")
    shell_design_pressure: Mapped[float | None] = mapped_column(Float, comment="kPaG")
    shell_design_temp: Mapped[float | None] = mapped_column(Float, comment="°C")
    baffle_type: Mapped[str | None] = mapped_column(
        String(30), comment="PERPEND/SINGLE-SEG/DOUBLE-SEG/NO-TUBES-IN-WINDOW"
    )
    baffle_cut_percent: Mapped[float | None] = mapped_column(Float, comment="%")
    baffle_spacing: Mapped[float | None] = mapped_column(Float, comment="mm")
    baffle_inlet_spacing: Mapped[float | None] = mapped_column(Float, comment="mm")
    seal_strip_count: Mapped[int | None] = mapped_column(Integer)
    passlane_seal_rod_count: Mapped[int | None] = mapped_column(Integer)
    impingement_plate: Mapped[str | None] = mapped_column(String(10), comment="None/Yes")
    # §3.1.6 热阻分布 5
    thermal_resistance_shell: Mapped[float | None] = mapped_column(Float, comment="%")
    thermal_resistance_tube: Mapped[float | None] = mapped_column(Float, comment="%")
    thermal_resistance_fouling: Mapped[float | None] = mapped_column(Float, comment="%")
    thermal_resistance_metal: Mapped[float | None] = mapped_column(Float, comment="%")
    thermal_resistance_bond: Mapped[float | None] = mapped_column(Float, comment="% ACHE 专用")
    # === 3 新 JSONB（SUP-009 §3.1.3 + §3.1.7）===
    shell_params: Mapped[dict | None] = mapped_column(
        JSONB,
        comment=(
            "§3.1.3 壳程工艺物性"
            "（fluid_name/mass_flow/temp_in/out/density/viscosity/cp/k/"
            "pressure/pd/velocity/film_coef/fouling_res/...）"
        ),
    )
    tube_params: Mapped[dict | None] = mapped_column(
        JSONB, comment="§3.1.3 管程工艺物性（同 shell_params 结构）"
    )
    ache_params: Mapped[dict | None] = mapped_column(
        JSONB,
        comment=(
            "§3.1.7 ACHE 专属"
            "（fans/airside/fin/nozzle/airside_resistance_distribution）"
        ),
    )


class CvResult(TaggedRecordMixin, Base):
    """调节阀 Cv 选型/校核结果（cv_results 表，SPEC §3.2.1.6 + DICT V3.3）。

    业务：调节阀流量系数 Cv + 阀体口径 + 噪声 + 闪蒸判定（IEC 60534-2-1/8-3）；
    input_json/output_json JSONB 容器，含 sizing_method + 流体工况 +
    noise 完整 L_p/L_w 序列。

    PK 列名 = cv_id（DICT V3.3 §4.1，P5-0-4a rename 自 cv_calc_id）。
    v3_1 既有 stub 列（cv_value/flow_rate/pressure_drop/choked_flow）保留以防
    既有查询/测试引用；新字段由 cv_engine（Task 8）写入并启用。

    RECORD_TYPE_REGISTRY 注册键 = "cv_result"（P6-1 Task 7 / ADR-0031）。
    """

    __tablename__ = "cv_results"
    cv_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 既有 v3_1 stub 列（保留；不被 cv_engine 写入）
    cv_value: Mapped[float] = mapped_column(Float)
    flow_rate: Mapped[float] = mapped_column(Float)
    pressure_drop: Mapped[float] = mapped_column(Float)
    choked_flow: Mapped[bool] = mapped_column(Boolean, default=False)
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)
    # P6-1 Task 7: SPEC §3.2.1.6 字段平铺 21 列
    # 阀型 + 流体相（NOT NULL per SPEC §3.2.1.6）
    valve_type: Mapped[str] = mapped_column(
        String(32), comment="线性/等百分比/快开（SPEC §3.2.1.6）"
    )
    fluid_phase: Mapped[str] = mapped_column(
        String(16), comment="LIQUID/GAS/VAPOR/TWO_PHASE（SPEC §3.2.1.6）"
    )
    # 工况（NOT NULL per SPEC for P1/P2/T1）
    P1_pa: Mapped[float] = mapped_column(Float, comment="入口绝压 Pa（SPEC §3.2.1.6）")
    P2_pa: Mapped[float] = mapped_column(Float, comment="出口绝压 Pa（SPEC §3.2.1.6）")
    T1_k: Mapped[float] = mapped_column(Float, comment="入口温度 K（SPEC §3.2.1.6）")
    Q_m3_per_h: Mapped[float | None] = mapped_column(
        Float, comment="体积流量 m³/h（SPEC §3.2.1.6）"
    )
    # 物性（nullable per SPEC）
    rho: Mapped[float | None] = mapped_column(
        Float, comment="密度 kg/m³（SPEC §3.2.1.6，brief 短名）"
    )
    SG: Mapped[float | None] = mapped_column(
        Float, comment="相对密度（SPEC §3.2.1.6）"
    )
    FL: Mapped[float | None] = mapped_column(
        Float, comment="压力恢复系数（SPEC §3.2.1.6）"
    )
    xT: Mapped[float | None] = mapped_column(
        Float, comment="压差比系数（SPEC §3.2.1.6）"
    )
    gamma: Mapped[float | None] = mapped_column(
        Float, comment="比热比（SPEC §3.2.1.6）"
    )
    M: Mapped[float | None] = mapped_column(
        Float, comment="分子量 g/mol（SPEC §3.2.1.6，brief 短名）"
    )
    Z: Mapped[float | None] = mapped_column(
        Float, comment="压缩因子（SPEC §3.2.1.6）"
    )
    # 结果（NOT NULL per SPEC for Cv_calculated）
    Cv_calculated: Mapped[float] = mapped_column(
        Float, comment="计算 Cv（SPEC §3.2.1.6）"
    )
    Cv_selected: Mapped[float | None] = mapped_column(
        Float, comment="圆整到标准系列的 Cv（SPEC §3.2.1.6）"
    )
    # 状态 Boolean（NOT NULL per SPEC for choked）
    choked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False,
        comment="是否阻塞流（SPEC §3.2.1.6）",
    )
    cavitation: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="液体空化标记（SPEC §3.2.1.6）"
    )
    flashing: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="液体闪蒸标记（SPEC §3.2.1.6）"
    )
    noise_sil_db: Mapped[float | None] = mapped_column(
        Float, comment="简化法噪音 dB（SPEC §3.2.1.6）"
    )
    # 标准代码（NOT NULL per SPEC；SPEC §3.2.1.6 line 1283 VARCHAR(16)）
    # 默认值由 CvEngine 注入；ORM 层无 server_default（防止写空值）
    standard_profile_code: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default="IEC_60534",
        comment="IEC_60534（GB/T 4213 等同采用；C-07 评审委员会裁决 2026-09-24）",
    )
    # 设计阶段（OPEN-009 + PsvResult 同模式）
    design_stage: Mapped[DesignStage] = mapped_column(
        Enum(DesignStage, name="design_stage_enum", native_enum=True),
        nullable=False,
        default=DesignStage.BASIC,
        comment="设计阶段 BASIC/DETAIL（OPEN-009）",
    )


class RestrictionResult(TaggedRecordMixin, Base):
    """限流孔板计算结果（restriction_results 表，SPEC §3.2.2.6 + DICT V3.3）。

    业务：限流孔板孔径+压降+多孔板组合判定（ISO 5167-2/-3/-4）；
    input_json/output_json JSONB 容器，含 sizing_method + 流体工况 +
    阻塞流/闪蒸判定 + 多级降压级数 stages。

    PK 列名 = orifice_id（DICT V3.3 §4.1，P5-0-4a rename 自 orifice_calc_id）。
    v3_1 既有 stub 列 restriction_type 保留以防既有查询/测试引用；新字段由
    cv_engine（Task 8）写入并启用。

    RECORD_TYPE_REGISTRY 注册键 = "restriction_result"（P6-1 Task 7 / ADR-0031）。
    """

    __tablename__ = "restriction_results"
    orifice_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 既有 v3_1 stub 列（保留；不被 cv_engine 写入）
    restriction_type: Mapped[str] = mapped_column(String(30), comment="ORIFICE/PLATE/...")
    input_json: Mapped[dict] = mapped_column(JSONB)
    output_json: Mapped[dict] = mapped_column(JSONB)
    # P6-1 Task 7: SPEC §3.2.2.6 字段平铺 13 列
    # 装置类型（NOT NULL per SPEC §3.2.2.6）
    device_type: Mapped[str] = mapped_column(
        String(32), comment="ORIFICE/VENTURI/NOZZLE/MULTI_STAGE（§3.2.2.6）"
    )
    # 几何（NOT NULL per SPEC for D/d/beta/C）
    D_pipe_m: Mapped[float] = mapped_column(
        Float, comment="管道内径 m（SPEC §3.2.2.6）"
    )
    d_solved_m: Mapped[float] = mapped_column(
        Float, comment="求解的孔径 m（SPEC §3.2.2.6）"
    )
    beta_ratio: Mapped[float] = mapped_column(
        Float, comment="d/D（SPEC §3.2.2.6）"
    )
    C_discharge: Mapped[float] = mapped_column(
        Float, comment="流出系数（SPEC §3.2.2.6）"
    )
    # 可膨胀性 / 雷诺数（nullable per SPEC）
    epsilon: Mapped[float | None] = mapped_column(
        Float, comment="可膨胀性系数（SPEC §3.2.2.6）"
    )
    Re_D: Mapped[float | None] = mapped_column(
        Float, comment="雷诺数（SPEC §3.2.2.6）"
    )
    # 压差（NOT NULL per SPEC for delta_P_pa）
    delta_P_pa: Mapped[float] = mapped_column(
        Float, comment="压差 Pa（SPEC §3.2.2.6）"
    )
    delta_omega_pa: Mapped[float | None] = mapped_column(
        Float, comment="永久压损 Pa（SPEC §3.2.2.6）"
    )
    # 状态 Boolean / Integer
    choked: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="阻塞流（SPEC §3.2.2.6）"
    )
    flashing: Mapped[bool] = mapped_column(
        Boolean, default=False, comment="闪蒸（SPEC §3.2.2.6）"
    )
    stages: Mapped[int | None] = mapped_column(
        Integer, comment="多级时级数（SPEC §3.2.2.6）"
    )
    # 设计阶段（OPEN-009 + PsvResult 同模式）
    design_stage: Mapped[DesignStage] = mapped_column(
        Enum(DesignStage, name="design_stage_enum", native_enum=True),
        nullable=False,
        default=DesignStage.BASIC,
        comment="设计阶段 BASIC/DETAIL（OPEN-009）",
    )


class CoolingTowerResult(TaggedRecordMixin, RecordMixin, Base):
    """COOL_TOWER 冷却塔计算结果（cooling_tower_results 表，P6-2 Task 18 重构）。

    业务：Merkel 热力 / 循环水量 / 补充水量 / 风机功率。
    SPEC §3.2.4 + PCS-DICT-007 §SUP-012（data_sheet_json 14 子结构）。

    字段双轨：5 平铺 Float（duty/water_flow/makeup/fan_power/merkel_integral）
    + JSONB 容器（data_sheet_json 14 子结构 + 通用 input/output）。
    standard_profile_code 默认 CTI_ATC_105（C-07 锁定 String(16)）。

    RECORD_TYPE_REGISTRY 注册键 = "cooling_tower_result"（P6-2 Task 18）。
    """

    __tablename__ = "cooling_tower_results"
    cooling_tower_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 溯源
    standard_profile_code: Mapped[str] = mapped_column(
        String(16), nullable=False, default="CTI_ATC_105",
        comment="CTI_ATC_105（SPEC §3.2.4 默认；C-07 String(16) 锁定）",
    )
    calc_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="MERKEL / WATER_BALANCE / FAN_POWER / HEAT_AGGREGATE",
    )
    tower_type: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="COUNTERFLOW_MECH / CROSSFLOW_MECH / NATURAL_DRAFT",
    )
    # 结果（5 平铺字段 + SUP-012 §3）
    duty_kw: Mapped[float | None] = mapped_column(Float, comment="kW")
    water_flow_m3h: Mapped[float | None] = mapped_column(Float, comment="m³/h")
    makeup_water_m3h: Mapped[float | None] = mapped_column(Float, comment="m³/h")
    fan_power_kw: Mapped[float | None] = mapped_column(Float, comment="kW")
    merkel_integral: Mapped[float | None] = mapped_column(Float, comment="Merkel 积分值")
    # JSONB
    data_sheet_json: Mapped[dict | None] = mapped_column(
        JSONB, comment="PCS-DICT-007 SUP-012 §3 14 子结构 data sheet",
    )
    input_json: Mapped[dict | None] = mapped_column(JSONB, comment="入参（业务子结构）")
    output_json: Mapped[dict | None] = mapped_column(JSONB, comment="出参（业务子结构）")


class PsychroResult(TaggedRecordMixin, RecordMixin, Base):
    """PSYCHRO 湿空气计算结果（psychro_results 表，P6-2 Task 18 重构）。

    业务：CoolProp HumidAir 包装 — 含湿量 / 露点 / 湿球 / 焓 / 比容 / 冷却盘管。
    SPEC §3.2.5 + PCS-DICT-005 §4（6 calc_type）。

    字段双轨：7 平铺 Float（6 calc_type 各自 result + sensible/latent heat）+
    JSONB 容器。coolprop_version 字段溯源 CoolProp 库版本（如 "6.6.0"）。
    standard_profile_code 默认 ASHRAE_FUND_2021（C-07 锁定 String(16)）。

    RECORD_TYPE_REGISTRY 注册键 = "psychro_result"（P6-2 Task 18）。
    """

    __tablename__ = "psychro_results"
    psychro_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    # 溯源
    standard_profile_code: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ASHRAE_FUND_2021",
        comment="ASHRAE_FUND_2021（SPEC §3.2.5 默认；C-07 String(16) 锁定）",
    )
    calc_type: Mapped[str] = mapped_column(
        String(32), nullable=False,
        comment="HUMIDITY_RATIO / DEW_POINT / WET_BULB / ENTHALPY / SPECIFIC_VOLUME / COOLING_COIL",
    )
    coolprop_version: Mapped[str | None] = mapped_column(
        String(16), nullable=True, comment="CoolProp 版本（如 6.6.0）；record_hash 反射自动含",
    )
    # 结果（6 calc_type 各自的 result float + cooling_coil 双轨）
    humidity_ratio_kg_kg: Mapped[float | None] = mapped_column(Float, comment="kg/kg")
    dew_point_c: Mapped[float | None] = mapped_column(Float, comment="°C")
    wet_bulb_c: Mapped[float | None] = mapped_column(Float, comment="°C")
    enthalpy_kj_kg: Mapped[float | None] = mapped_column(Float, comment="kJ/kg")
    specific_volume_m3_kg: Mapped[float | None] = mapped_column(Float, comment="m³/kg")
    sensible_heat_kw: Mapped[float | None] = mapped_column(Float, comment="显热 kW（cooling_coil）")
    latent_heat_kw: Mapped[float | None] = mapped_column(Float, comment="潜热 kW（cooling_coil）")
    # JSONB
    input_json: Mapped[dict | None] = mapped_column(JSONB, comment="入参（业务子结构）")
    output_json: Mapped[dict | None] = mapped_column(JSONB, comment="出参（业务子结构）")


class OpenChannelResult(TaggedRecordMixin, Base):
    """明渠流计算结果（open_channel_results 表）。

    业务：矩形/梯形/圆形明渠均匀流+临界水深+水跃+能量损失；
    result_json 承载水深+流速+弗劳德数+水力坡度。
    """

    __tablename__ = "open_channel_results"
    open_channel_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    channel_type: Mapped[str] = mapped_column(String(30))
    cross_section_json: Mapped[dict] = mapped_column(JSONB)
    flow_rate: Mapped[float] = mapped_column(Float)
    depth: Mapped[float] = mapped_column(Float)
    velocity: Mapped[float] = mapped_column(Float)
    slope: Mapped[float] = mapped_column(Float)


class FiltrationResult(TaggedRecordMixin, Base):
    """过滤设备选型/校核结果（filtration_results 表）。

    业务：袋式/滤芯/砂滤等过滤器精度+压降+反吹周期+容尘量；
    result_json 承载型号+过滤面积+数量+材质。
    """

    __tablename__ = "filtration_results"
    filter_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
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
