import datetime
import uuid

from sqlalchemy import (
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
    comments: Mapped[str | None] = mapped_column(Text)


class FormulaDefinition(TimestampMixin, Base):
    __tablename__ = "formula_definitions"
    formula_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    module: Mapped[str] = mapped_column(String(30))
    category: Mapped[str] = mapped_column(String(30))
    expression: Mapped[str] = mapped_column(Text)
    variables_json: Mapped[dict] = mapped_column(JSONB)
    unit_tests_json: Mapped[dict | None] = mapped_column(JSONB)
    version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class CoefficientTable(TimestampMixin, Base):
    __tablename__ = "coefficient_tables"
    table_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    domain: Mapped[str] = mapped_column(String(50))
    data_json: Mapped[dict] = mapped_column(JSONB)
    version: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


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


class PipeClass(TimestampMixin, Base):
    """管道等级。class_id=等级代码（string PK，字典表11）。"""

    __tablename__ = "pipe_classes"
    class_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    class_name: Mapped[str] = mapped_column(String(200))
    material_standard: Mapped[str] = mapped_column(String(100))
    corrosion_allowance: Mapped[float] = mapped_column(Float, comment="mm")
    design_pressure: Mapped[float] = mapped_column(Float, comment="MPaG")
    design_temperature: Mapped[float] = mapped_column(Float, comment="°C")
    fluid_service: Mapped[str | None] = mapped_column(String(100))
    allowable_stress_json: Mapped[dict] = mapped_column(
        JSONB, comment="引用 COMMON 可覆写"
    )
    dn_series_json: Mapped[dict] = mapped_column(JSONB, comment="{min,max}")
    sch_series_json: Mapped[list] = mapped_column(JSONB)
    flange_class: Mapped[str] = mapped_column(String(20))
    fitting_type: Mapped[str | None] = mapped_column(String(50), comment="FittingType")
    branch_table_json: Mapped[dict | None] = mapped_column(JSONB)
    source: Mapped[str] = mapped_column(String(20), comment="COMPANY_STD/PROJECT")
    version: Mapped[str] = mapped_column(
        String(50), comment="配置版本（非记录层 Rev）"
    )
    status: Mapped[str] = mapped_column(String(20), comment="DRAFT/ACTIVE/OBSOLETE")


class ProjectPipeClass(TimestampMixin, Base):
    """项目启用管道等级（复合 PK project_id+class_id）。"""

    __tablename__ = "project_pipe_classes"
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), primary_key=True
    )
    class_id: Mapped[str] = mapped_column(
        ForeignKey("pipe_classes.class_id"), primary_key=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    custom_override_json: Mapped[dict | None] = mapped_column(JSONB)


class NumberingTemplate(TimestampMixin, Base):
    __tablename__ = "numbering_templates"
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(200))
    scope: Mapped[str] = mapped_column(String(30), comment="PIPE/EQUIP/DELIVERABLE/...")
    segments_json: Mapped[dict] = mapped_column(JSONB)
    separator: Mapped[str] = mapped_column(String(5), default="-")
    revision_separate: Mapped[bool] = mapped_column(Boolean, default=True)
    deliverable_mappings_json: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class DocNoSequence(TimestampMixin, Base):
    __tablename__ = "doc_no_sequences"
    sequence_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
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
