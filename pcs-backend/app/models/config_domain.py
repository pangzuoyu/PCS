import datetime
import uuid

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class ConfigAsset(TimestampMixin, Base):
    __tablename__ = "config_assets"
    asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    category: Mapped[str] = mapped_column(String(30), comment="CATEGORY_1~6")
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500))
    current_version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(
        String(20), default="DRAFT", comment="ConfigStatus"
    )
    content_json: Mapped[dict | None] = mapped_column(JSONB)
    asset_subtype: Mapped[str | None] = mapped_column(
        String(30), nullable=True,
        comment="PIPE_CLASS/STREAM_SYMBOL/PIPE_CODE_TEMPLATE（V1.4 §0.5/PC-3）",
    )


class ConfigVersion(TimestampMixin, Base):
    __tablename__ = "config_versions"
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("config_assets.asset_id"), index=True
    )
    version_code: Mapped[str] = mapped_column(String(50))
    parent_version_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("config_versions.version_id")
    )
    change_note: Mapped[str | None] = mapped_column(Text)
    content_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")


class ConfigApproval(TimestampMixin, Base):
    __tablename__ = "config_approvals"
    approval_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("config_versions.version_id"), index=True
    )
    approver_role: Mapped[str] = mapped_column(String(30))
    decision: Mapped[str] = mapped_column(String(20))
    comment: Mapped[str | None] = mapped_column(Text)
    approver_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    # SUP-002 PC-1：项目级三域（等级/符号/代码配置）审批关联占位（V1.4 §五、#1）
    project_class_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("project_pipe_classes.project_class_id"), nullable=True,
    )


class FormulaDefinition(TimestampMixin, Base):
    __tablename__ = "formula_definitions"
    formula_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    module: Mapped[str] = mapped_column(String(30))
    category: Mapped[str] = mapped_column(String(30))
    expression: Mapped[str] = mapped_column(Text)
    parameters_json: Mapped[dict] = mapped_column(JSONB)
    unit_tests_json: Mapped[dict | None] = mapped_column(JSONB)
    version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("config_assets.asset_id"), nullable=True
    )
    std_source: Mapped[str | None] = mapped_column(String(200))


class CoefficientTable(TimestampMixin, Base):
    __tablename__ = "coefficient_tables"
    table_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    applicable_range: Mapped[str] = mapped_column(String(50))
    data_json: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("config_assets.asset_id"), nullable=True
    )
    std_source: Mapped[str | None] = mapped_column(String(200))


class TemplateFile(TimestampMixin, Base):
    __tablename__ = "template_files"
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    file_type: Mapped[str] = mapped_column(String(10))
    file_path: Mapped[str] = mapped_column(String(500))
    placeholders_json: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[str] = mapped_column(String(50))
    template_version_seq: Mapped[int] = mapped_column(
        Integer, default=0,
        comment="V1.4 P2-OPEN-005：模板版本号字段纳入 CONFIG 模板版本序列（自增）",
    )
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("config_assets.asset_id"), nullable=True
    )


class ProjectTemplate(TimestampMixin, Base):
    __tablename__ = "project_templates"
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(50))
    default_config_json: Mapped[dict] = mapped_column(
        JSONB,
        comment=(
            "含 record_approval_config / stream_approval_config / signature_matrices / "
            "numbering_config / customer_approval_config / doc_no_config / "
            "equipment_type_codes_config"
        ),
    )
    version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("config_assets.asset_id"), nullable=True
    )
    checklist_json: Mapped[dict | None] = mapped_column(JSON)


class PipeClass(TimestampMixin, Base):
    """管道等级（SUP-002 PC-1）。

    class_id=等级代码（自然码 PK，varchar(50)，piping_results FK 引用）。
    asset_id 挂 ConfigAsset（CATEGORY_5，asset_subtype=PIPE_CLASS），状态机由 ConfigStateMachine 驱动。
    status 为 5 态镜像列：DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE。
    """

    __tablename__ = "pipe_classes"
    class_id: Mapped[str] = mapped_column(String(50), primary_key=True)
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("config_assets.asset_id"), nullable=True,
    )
    class_name: Mapped[str] = mapped_column(String(200))
    material_standard: Mapped[str] = mapped_column(String(100))
    base_material: Mapped[str | None] = mapped_column(
        String(100), comment="材料牌号；migration 已回填 material_standard"
    )
    corrosion_allowance: Mapped[float] = mapped_column(Float, comment="mm")
    design_pressure: Mapped[float] = mapped_column(Float, comment="MPaG")
    design_temperature: Mapped[float] = mapped_column(Float, comment="°C")
    fluid_service: Mapped[str | None] = mapped_column(String(100))
    allowable_stress_json: Mapped[dict] = mapped_column(
        JSONB, comment="引用 COMMON 可覆写"
    )
    dn_series_json: Mapped[dict] = mapped_column(JSONB, comment="{min,max,series?}")
    sch_series_json: Mapped[list] = mapped_column(JSONB)
    flange_class: Mapped[str] = mapped_column(String(20))
    fitting_type: Mapped[str | None] = mapped_column(String(50), comment="FittingType")
    branch_table_json: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(20), comment="COMPANY_STD/PROJECT")
    version: Mapped[str] = mapped_column(
        String(50), comment="配置版本（非记录层 Rev）"
    )
    status: Mapped[str] = mapped_column(
        String(20), default="DRAFT",
        comment="DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE",
    )


class ProjectPipeClass(TimestampMixin, Base):
    """项目级管道等级（SUP-002 PC-1，独立 UUID PK，5 态轻量审批）。

    snapshot_json 完整复制公司级 PUBLISHED 字段（fork 时锁定）；
    override_json 仅存被覆写字段；status 为项目级 5 态。
    """

    __tablename__ = "project_pipe_classes"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "class_name",
            name="uq_project_pipe_classes_project_id_class_name",
        ),
    )
    project_class_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.project_id"), index=True,
    )
    source_class_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    class_name: Mapped[str] = mapped_column(String(100))
    override_json: Mapped[dict] = mapped_column(JSONB, default=dict)
    snapshot_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), default="DRAFT",
        comment="DRAFT/PENDING/APPROVED/PUBLISHED/OBSOLETE",
    )


class NumberingTemplate(TimestampMixin, Base):
    __tablename__ = "numbering_templates"
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    template_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(30), comment="PIPE/EQUIP/DELIVERABLE/...")
    segments_json: Mapped[dict] = mapped_column(JSONB)
    separator: Mapped[str] = mapped_column(String(5), default="-")
    revision_separate: Mapped[bool] = mapped_column(Boolean, default=True)
    deliverable_mappings_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class DocNoSequence(TimestampMixin, Base):
    __tablename__ = "doc_no_sequences"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "template_id", "scope_key",
            name="uq_doc_no_sequences_proj_template_scope",
        ),
    )
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.project_id")
    )
    template_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("numbering_templates.template_id"), index=True
    )
    scope_key: Mapped[str] = mapped_column(String(50), comment="如 PE-LST")
    current_value: Mapped[int] = mapped_column(Integer, default=0)


class ToeConversionFactor(TimestampMixin, Base):
    """折标煤系数组（V1.4 P2-OPEN-005，配套 auxiliary_consumption + utility_energy_summary）。

    fuel_type 枚举：GAS/DIESEL/COAL/STEAM/ELECTRICITY/OTHER。
    effective_year + effective_from / effective_to 控制生效区间。
    """
    __tablename__ = "pcs_toe_conversion_factors"
    __table_args__ = (
        UniqueConstraint("fuel_type", "effective_year", name="uq_toe_fuel_year"),
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    fuel_type: Mapped[str] = mapped_column(String(30), index=True,
        comment="GAS/DIESEL/COAL/STEAM/ELECTRICITY/OTHER")
    toe_conversion_factor: Mapped[float] = mapped_column(Numeric(10, 4),
        comment="吨油当量折算系数")
    standard_coal_factor: Mapped[float] = mapped_column(Numeric(10, 4),
        comment="标煤折算系数")
    effective_year: Mapped[int] = mapped_column(Integer, index=True)
    effective_from: Mapped[datetime.date] = mapped_column(Date)
    effective_to: Mapped[datetime.date | None] = mapped_column(Date, nullable=True)
    source: Mapped[str | None] = mapped_column(String(200))
    version: Mapped[str] = mapped_column(String(50), default="TOE-V1.0")
