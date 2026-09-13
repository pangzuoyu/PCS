import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Uuid,
    false,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, declared_attr, mapped_column

from app.models.enums import RecordSignStatus9


class TimestampMixin:
    created_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class RecordMixin(TimestampMixin):
    """业务记录统一字段（DICT-ALL-003 V3.1 §1.3，逐字对齐）。

    tag_number 可空入 mixin（§1.3 模板适用于全部 16 计算表 + equipment_list）；
    需要位号的表在类体重声明 NOT NULL 覆盖；piping_results 用 line_no，tag_number 留空。
    """

    tag_number: Mapped[str | None] = mapped_column(
        String(50), comment="位号/管道号，终身唯一；piping_results 用 line_no 此处留空"
    )
    sign_status: Mapped[RecordSignStatus9] = mapped_column(
        Enum(RecordSignStatus9, name="recordsignstatus", native_enum=True),
        nullable=False,
        default=RecordSignStatus9.DRAFT,
        index=True,
        comment="记录门禁 9 态（SUP-007 §3.1）",
    )
    record_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="",
        comment="SHA-256，数值规范化舍入 6 位有效数字，仅设计参数参与；未计算时空串",
    )
    approval_step: Mapped[int | None] = mapped_column(comment="IN_APPROVAL 当前步骤(1-based)")
    approval_depth: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1,
        comment="该记录类型批准深度快照(1-4)，默认最低 1",
    )
    approval_role: Mapped[str | None] = mapped_column(
        String(30), comment="当前待批角色 ApprovalRole"
    )
    locked_by_deliverable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, comment="被交付物快照绑定即锁定"
    )

    # change_* 组（ADR-0002，字典 §1.3 逐字）
    change_pending_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_resolved_by: Mapped[str | None] = mapped_column(String(64))
    change_resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_abandoned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    change_abandoned_reason: Mapped[str | None] = mapped_column(String(500))

    # obsoleted_* 组（ADR-0009，字典 §1.3 逐字）
    obsoleted_reason: Mapped[str | None] = mapped_column(String(200))
    obsoleted_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    obsoleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    obsoleted_via_deliverable_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, comment="已绑定记录经 RECORD_CANCELLATION 变更单弃用"
    )

    # reversal_* 组（ADR-0010，字典 §1.3 逐字）
    reversal_requested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    reversal_requested_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reversal_reason: Mapped[str | None] = mapped_column(String(500))
    reversal_approved_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reversal_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # P4-0-1 审计列（ADR-0031）：只经 calc_lineage.finalize_calc_record /
    # CIA 引擎写，业务模块禁止直写；streams 表同构列在 Stream 模型显式声明
    stale_resolution_path: Mapped[str | None] = mapped_column(
        String(30), comment="STALE 后走的重算路径（CIA 审计）"
    )
    hash_changed: Mapped[bool | None] = mapped_column(
        Boolean,
        server_default=false(),
        comment="record_hash 相对上版是否实质变化",
    )
    changed_fields: Mapped[dict | None] = mapped_column(
        JSONB, comment="实质变化字段清单（6 位规范化后仍发散的字段）"
    )

    @declared_attr
    def project_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("projects.project_id"), index=True)

    @declared_attr
    def workspace_id(cls) -> Mapped[uuid.UUID]:
        return mapped_column(ForeignKey("workspaces.workspace_id"), index=True)


class TaggedRecordMixin(RecordMixin):
    """需要位号的记录表（eng-review Issue 5）：tag_number NOT NULL。

    15 张计算表 + equipment_list 用；piping_results 直接用 RecordMixin（line_no）。
    (project_id, tag_number) 唯一性由服务层强制（避免 SQLAlchemy 命名约定在
    declared_attr mixin + autogenerate 下的跨表错挂 bug）。
    """

    tag_number: Mapped[str] = mapped_column(String(50))
