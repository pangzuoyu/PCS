import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
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
from app.models.mixins import TaggedRecordMixin, TimestampMixin


class EquipmentTypeCode(Base):
    """字典表40（V3.1 ADR-0023）：复合 PK (project_id, type_code)；
    project_id NULL = 公司级默认；项目级覆写 P2+ 模板导入后启用。"""

    __tablename__ = "equipment_type_codes"
    __table_args__ = (
        UniqueConstraint(
            "project_id", "type_code", name="uq_equipment_type_codes_project_type"
        ),
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.project_id"), primary_key=True, nullable=True
    )
    type_code: Mapped[str] = mapped_column(String(5), primary_key=True)
    equipment_description: Mapped[str] = mapped_column(String(200))
    description_cn: Mapped[str | None] = mapped_column(String(100))
    category: Mapped[str] = mapped_column(
        String(30),
        comment="STATIC/ROTATING/PACKAGE/ELECTRICAL/INSTRUMENT/OTHER",
    )
    is_process_equipment: Mapped[bool] = mapped_column(Boolean, default=True)
    is_pressure_vessel: Mapped[bool] = mapped_column(Boolean, default=False)
    source: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE", comment="ACTIVE/OBSOLETE")


class EquipmentList(TaggedRecordMixin, Base):
    """字典表39。type_code + project_id 复合 FK → equipment_type_codes。"""

    __tablename__ = "equipment_list"
    __table_args__ = (
        ForeignKeyConstraint(
            ["equipment_type_project_id", "type_code"],
            ["equipment_type_codes.project_id", "equipment_type_codes.type_code"],
            name="fk_equipment_list_type_code",
        ),
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipment_type_project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    type_code: Mapped[str] = mapped_column(String(5))
    equipment_name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(String(500))
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, comment="多态 source"
    )
    source_module: Mapped[str | None] = mapped_column(String(30))
    vendor_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    vendor_model: Mapped[str | None] = mapped_column(String(100))
    design_parameters_json: Mapped[dict | None] = mapped_column(JSONB)
    procurement_status: Mapped[str | None] = mapped_column(String(30))
    drawing_no: Mapped[str | None] = mapped_column(String(100))
    deliverable_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    install_location: Mapped[str | None] = mapped_column(String(200))
    weight_kg: Mapped[float | None] = mapped_column(Float)
    paint_spec: Mapped[str | None] = mapped_column(String(100))
    engineering_notes: Mapped[str | None] = mapped_column(Text)


class EquipmentLib(TimestampMixin, Base):
    __tablename__ = "equipment_lib"
    equip_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    type_code: Mapped[str] = mapped_column(String(5))
    size: Mapped[str | None] = mapped_column(String(100))
    weight: Mapped[float | None] = mapped_column(Float)
    material: Mapped[str | None] = mapped_column(String(100))
    standard_drawing_no: Mapped[str | None] = mapped_column(String(100))
    process_description: Mapped[str | None] = mapped_column(Text)
    cost: Mapped[float | None] = mapped_column(Numeric(18, 2))
    cost_currency: Mapped[str | None] = mapped_column(String(10))
    cost_year: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"
    supplier_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    supplier_name: Mapped[str] = mapped_column(String(200))
    supplier_type: Mapped[str] = mapped_column(String(30), comment="MANUFACTURER/AGENT/TRADER")
    contact_json: Mapped[dict | None] = mapped_column(JSONB)
    qualification_json: Mapped[list | None] = mapped_column(JSONB)
    rating: Mapped[str] = mapped_column(String(10), comment="A/B/C/UNRATED")
    approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    approved_date: Mapped[date | None] = mapped_column(Date)
