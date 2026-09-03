import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.enums import DeliverableSignStatus
from app.models.mixins import TimestampMixin


class Deliverable(TimestampMixin, Base):
    """交付物（含变更单，ADR-0008）。字典表31 逐字。"""

    __tablename__ = "deliverables"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "deliverable_type",
            "scope_type",
            "scope_value",
            name="uq_deliverables_scope",
        ),
        UniqueConstraint("project_id", "doc_no", name="uq_deliverables_doc_no"),
    )
    deliverable_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    deliverable_type: Mapped[str] = mapped_column(
        String(30),
        comment="DeliverableType：PIPE_LIST/EQUIP_LIST/CALC_BOOK/PUMP_DATASHEET/PSV_DATASHEET/"
        "HEAT_DATASHEET/VESSEL_DATASHEET/UTIL_SUMMARY/CHANGE_NOTICE/CUSTOM_REPORT",
    )
    scope_type: Mapped[str] = mapped_column(
        String(20), comment="PROJECT_ALL/UNIT/SUB_PROJECT/CUSTOM"
    )
    scope_value: Mapped[str] = mapped_column(String(100), comment="ALL 或 '5000'/'ISBL'")
    parent_deliverable_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("deliverables.deliverable_id")
    )
    doc_no: Mapped[str] = mapped_column(String(200), index=True)
    doc_no_mode: Mapped[str] = mapped_column(String(20), comment="MANUAL/WORLEY_STD/CUSTOM")
    numbering_template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("numbering_templates.template_id")
    )
    segment_values_json: Mapped[dict | None] = mapped_column(JSONB)
    discipline_code: Mapped[str | None] = mapped_column(String(2))
    doc_identifier_code: Mapped[str | None] = mapped_column(String(3))
    sequence_no: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str] = mapped_column(String(500))
    current_rev: Mapped[str] = mapped_column(String(20), comment="A/B/0/1/AS-BUILT/X")
    version_purpose: Mapped[str] = mapped_column(
        String(40), comment="VersionPurpose 13 值，含 ISSUED_FOR_CHANGE"
    )
    sign_status: Mapped[DeliverableSignStatus] = mapped_column(
        Enum(DeliverableSignStatus, name="deliverablesignstatus", native_enum=True),
        nullable=False,
        default=DeliverableSignStatus.DRAFT,
        index=True,
    )
    matrix_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signature_matrices.matrix_id")
    )
    customer_approval_date: Mapped[date | None] = mapped_column(Date)
    customer_approver_name: Mapped[str | None] = mapped_column(String(100))
    customer_approval_method: Mapped[str | None] = mapped_column(
        String(20), comment="EMAIL/LETTER/EDMS/SIGNED_DOC"
    )
    customer_approval_proxy_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, comment="代录人"
    )
    customer_approval_proxy_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    customer_approval_attachment_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    customer_approval_is_proxy: Mapped[bool | None] = mapped_column(Boolean)


class DeliverableVersion(TimestampMixin, Base):
    __tablename__ = "deliverable_versions"
    version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    deliverable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deliverables.deliverable_id"), index=True
    )
    rev: Mapped[str] = mapped_column(String(20))
    version_purpose: Mapped[str] = mapped_column(String(40))
    description: Mapped[str] = mapped_column(Text)
    record_snapshot_json: Mapped[dict] = mapped_column(JSONB, comment="记录ID+哈希汇总")
    signature_summary_json: Mapped[dict] = mapped_column(JSONB)
    customer_approval_date: Mapped[date | None] = mapped_column(Date)
    pdf_file_path: Mapped[str | None] = mapped_column(String(500))
    affected_status: Mapped[str | None] = mapped_column(
        String(10), comment="NONE/AFFECTED"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class DeliverableRecordBinding(Base):
    """快照绑定：仅 CHECKED 记录可绑（ADR-0012），record_hash 固化。"""

    __tablename__ = "deliverable_record_bindings"
    binding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    deliverable_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deliverable_versions.version_id"), index=True
    )
    record_type: Mapped[str] = mapped_column(
        String(30), comment="PIPE_RESULT/PUMP_RESULT 等（多态）"
    )
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    record_hash: Mapped[str] = mapped_column(String(64))
    old_record_hash_before_change: Mapped[str | None] = mapped_column(String(64))


class SignatureMatrix(TimestampMixin, Base):
    """签署矩阵（SUP-005 机制，V3.1 表34 新增入册）。"""

    __tablename__ = "signature_matrices"
    matrix_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    matrix_name: Mapped[str] = mapped_column(String(200))
    module: Mapped[str] = mapped_column(String(30), comment="* 表示全部")
    doc_type: Mapped[str] = mapped_column(String(30))
    version_purpose: Mapped[str] = mapped_column(String(40))
    steps_json: Mapped[list] = mapped_column(
        JSONB,
        comment='[{"step_order","sign_role","required","can_self_check","can_skip"}]',
    )
    status: Mapped[str] = mapped_column(
        String(20), comment="DRAFT/PENDING/ACTIVE/OBSOLETE"
    )


class ProjectSignatureMatrixBinding(TimestampMixin, Base):
    __tablename__ = "project_signature_matrix_bindings"
    binding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    module: Mapped[str] = mapped_column(String(30))
    matrix_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("signature_matrices.matrix_id"), index=True
    )


class CustomerApprovalAttachment(Base):
    __tablename__ = "customer_approval_attachments"
    attachment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    deliverable_version_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deliverable_versions.version_id"), index=True
    )
    file_path: Mapped[str] = mapped_column(String(500))
    file_name: Mapped[str] = mapped_column(String(200))
    file_type: Mapped[str] = mapped_column(String(10), comment="PDF/JPG/PNG/EML")
    file_size: Mapped[int] = mapped_column(Integer)
    uploaded_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    file_hash: Mapped[str] = mapped_column(String(64), comment="SHA-256 防篡改")


class ChangeNoticeDetail(TimestampMixin, Base):
    __tablename__ = "change_notice_details"
    detail_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    deliverable_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("deliverables.deliverable_id"), unique=True
    )
    change_type: Mapped[str] = mapped_column(String(30), comment="7 值")
    reason: Mapped[str] = mapped_column(Text)
    triggered_by: Mapped[str] = mapped_column(String(20), comment="MANUAL/UPSTREAM_CHANGE")
    source_record_type: Mapped[str | None] = mapped_column(String(30))


class RecordChangeSnapshot(Base):
    __tablename__ = "record_change_snapshots"
    snapshot_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    record_type: Mapped[str] = mapped_column(String(30), index=True)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    record_hash: Mapped[str] = mapped_column(String(64))
    data_snapshot_json: Mapped[dict] = mapped_column(JSONB)
    snapshot_reason: Mapped[str] = mapped_column(
        String(20),
        comment="BEFORE_CHANGE/BEFORE_DRAFT（BEFORE_STALE 保留枚举值不写）",
    )
    snapshot_source: Mapped[str] = mapped_column(
        String(20), comment="MANUAL_CHANGE/UPSTREAM_CHANGE/MANUAL_ROLLBACK"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    snapshot_status: Mapped[str | None] = mapped_column(
        String(20), index=True, comment="ADR-0024：ACTIVE/CONSUMED/ABANDONED"
    )
