import uuid
from datetime import date

from sqlalchemy import (
    Boolean,
    Date,
    Enum,
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
from app.models.enums import ActualDataStatus, CalcStatus, EquipmentStatus
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
            name="fk_equipment_list_type_code_composite",
        ),
    )
    equipment_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    equipment_type_project_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    type_code: Mapped[str] = mapped_column(String(5))
    equipment_name: Mapped[str] = mapped_column(String(200))
    equipment_description: Mapped[str | None] = mapped_column(String(500))
    source_record_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, comment="多态 source"
    )
    source_module: Mapped[str | None] = mapped_column(String(30))
    vendor: Mapped[str | None] = mapped_column(String(200))
    vendor_model: Mapped[str | None] = mapped_column(String(100))
    design_parameters_json: Mapped[dict | None] = mapped_column(JSONB)
    procurement_status: Mapped[str | None] = mapped_column(String(30))
    flowsheet_drawing_number: Mapped[str | None] = mapped_column(String(100))
    deliverable_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    installation_location: Mapped[str | None] = mapped_column(String(200))
    net_weight: Mapped[float | None] = mapped_column(Float)
    paint: Mapped[str | None] = mapped_column(String(100))
    process_engineering_remarks: Mapped[str | None] = mapped_column(Text)
    # §四 采购（p2_sprint2_equipment_procurement_delivery，items 16-25）
    alternate_vendor: Mapped[str | None] = mapped_column(String(200))
    order_date: Mapped[date | None] = mapped_column(Date)
    purchase_order_number: Mapped[str | None] = mapped_column(String(100))
    cost: Mapped[float | None] = mapped_column(Numeric(18, 2))
    cost_currency: Mapped[str | None] = mapped_column(String(10))
    cost_source: Mapped[str | None] = mapped_column(String(200))
    cost_year: Mapped[int | None] = mapped_column(Integer)
    gpe_spec_number: Mapped[str | None] = mapped_column(String(100))
    gpe_spec_status: Mapped[str | None] = mapped_column(String(20))
    specification_priority: Mapped[str | None] = mapped_column(String(100))
    # §五 图纸（items 26-28）
    approval_drawing_received_date: Mapped[date | None] = mapped_column(Date)
    approval_drawing_return_date: Mapped[date | None] = mapped_column(Date)
    certified_drawing_received_date: Mapped[date | None] = mapped_column(Date)
    # §六 交付（items 29-33）
    delivery_date: Mapped[date | None] = mapped_column(Date)
    actual_received_date: Mapped[date | None] = mapped_column(Date)
    forecast_on_site: Mapped[date | None] = mapped_column(Date)
    actual_on_site: Mapped[date | None] = mapped_column(Date)
    storage_location: Mapped[str | None] = mapped_column(String(200))
    # §七 安装（items 34-38；item 39 installation_location 已存在，跳过）
    installation_contract_number: Mapped[str | None] = mapped_column(String(100))
    installation_notes: Mapped[str | None] = mapped_column(String(500))
    installation: Mapped[str | None] = mapped_column(
        String(50), comment="安装方式（MEI/吊装/现场组装）"
    )
    unloading: Mapped[str | None] = mapped_column(String(200))
    loading_by: Mapped[str | None] = mapped_column(String(100))
    # §八 重量（items 40-42；item 43 net_weight 已存在，跳过）
    empty_weight: Mapped[float | None] = mapped_column(Float)
    full_weight: Mapped[float | None] = mapped_column(Float)
    weigh_cells: Mapped[bool | None] = mapped_column(Boolean)
    # §一 来源（p2_sprint2_equipment_engineering，items 1-4）
    in_package: Mapped[bool | None] = mapped_column(Boolean)
    data_sources: Mapped[str | None] = mapped_column(String(200))
    tag_in_3d: Mapped[bool | None] = mapped_column(Boolean)
    tag_in_esr: Mapped[bool | None] = mapped_column(Boolean)
    # §二 标识（items 5-9；item 10 equipment_description 已存在，跳过）
    equipment_name_cn: Mapped[str | None] = mapped_column(String(100))
    package_no: Mapped[str | None] = mapped_column(String(50))
    sub_project: Mapped[str | None] = mapped_column(String(20))
    unit_no: Mapped[str | None] = mapped_column(String(20))
    unit_name: Mapped[str | None] = mapped_column(String(100))
    # §三 类型（items 11-14）
    equipment_sub_type: Mapped[str | None] = mapped_column(String(50))
    equipment_category: Mapped[str | None] = mapped_column(String(30))
    is_pressure_vessel: Mapped[bool | None] = mapped_column(Boolean)
    pressure_vessel_category: Mapped[str | None] = mapped_column(String(10))
    # §九 工程（items 44-45, 47-52；items 46/53 已存在，跳过）
    process_engineer: Mapped[str | None] = mapped_column(String(100))
    detail_engineer: Mapped[str | None] = mapped_column(String(100))
    pid_drawing_number: Mapped[str | None] = mapped_column(String(100))
    pid_status: Mapped[str | None] = mapped_column(String(10))
    dimensions: Mapped[str | None] = mapped_column(String(100))
    registration_number: Mapped[str | None] = mapped_column(String(100))
    emts_number: Mapped[str | None] = mapped_column(String(100))
    mst_number: Mapped[str | None] = mapped_column(String(100))
    equipment_status: Mapped[str] = mapped_column(
        String(1),
        nullable=False,
        server_default=EquipmentStatus.N.value,
        comment="设备生命周期分类：N=New新建/E=Existing已有/D=Delete删除/M=Modified修改/F=Future预留",
    )
    calc_status: Mapped[str] = mapped_column(
        Enum(CalcStatus, name="calcstatus", native_enum=True),
        nullable=False,
        server_default=CalcStatus.NOT_CALCULATED.value,
        comment="设备计算状态：NOT_CALCULATED/CALCULATING/COMPLETED/NEED_RECALC",
    )
    actual_data_status: Mapped[str] = mapped_column(
        Enum(ActualDataStatus, name="actualdatastatus", native_enum=True),
        nullable=False,
        server_default=ActualDataStatus.NOT_ENTERED.value,
        comment="供应商实际数据录入：NOT_ENTERED/PENDING_CONFIRM/CONFIRMED/NEED_RECALC（ADR-0025）",
    )


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
