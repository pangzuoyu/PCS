import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import INET, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class DataLineage(Base):
    """任何记录的修改都应落库；SUP-006 可追溯。"""

    __tablename__ = "data_lineage"
    lineage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    record_type: Mapped[str] = mapped_column(String(30), index=True)
    record_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    parent_lineage_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("data_lineage.lineage_id")
    )
    source: Mapped[str] = mapped_column(
        String(30),
        comment="USER/AI/UPLINK/IMPORT/REPLAY",
    )
    source_ref_type: Mapped[str | None] = mapped_column(String(30))
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    actor_ai_agent_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    change_summary: Mapped[str | None] = mapped_column(Text)
    change_diff_json: Mapped[dict | None] = mapped_column(JSONB)
    # P4-TASK0 D4/D5 扩展（ADR-0031 残余）
    # - record_hash_at_track：本次收口时 record.record_hash（16 hex）
    # - source_record_hash：上游 record_hash（无上游 → 退化 = record_hash）
    # - formula_version_at_track：本次公式版本
    # - config_version：上游配置版本（P4-TASK0 占位；CIA 引擎后续使用）
    record_hash_at_track: Mapped[str | None] = mapped_column(
        String(16), comment="收口时 record_hash（P4-TASK0 D4）"
    )
    source_record_hash: Mapped[str | None] = mapped_column(
        String(16), comment="上游 record_hash（P4-TASK0 D5）"
    )
    formula_version_at_track: Mapped[str | None] = mapped_column(
        String(50), comment="收口时公式版本（P4-TASK0 D4）"
    )
    config_version: Mapped[str | None] = mapped_column(
        String(50), comment="上游配置版本（P4-TASK0 占位）"
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class ProjectInputChecklist(TimestampMixin, Base):
    """项目级输入清单（前置完整性门禁，SUP-006 必备）。

    Sprint 1 升级：DICT-ALL-003 V3.1 表44 对齐——status 5态、source_type、
    verified_by/verified_at、assumption_reason、input_category、input_value_json。
    """

    __tablename__ = "project_input_checklist"
    checklist_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    item_key: Mapped[str] = mapped_column(String(100))
    item_label: Mapped[str] = mapped_column(String(200))
    required: Mapped[bool] = mapped_column(Boolean, default=True)
    note: Mapped[str | None] = mapped_column(Text)
    # === Sprint 1 新增字段（DICT-ALL-003 V3.1 表44 对齐）===
    module: Mapped[str | None] = mapped_column(String(30))
    input_category: Mapped[str | None] = mapped_column(
        String(20), comment="REQUIRED/CONDITIONAL/OPTIONAL"
    )
    input_value_json: Mapped[dict | None] = mapped_column(JSONB)
    source_type: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(
        String(20),
        default="NOT_STARTED",
        comment="NOT_STARTED/IN_PROGRESS/VERIFIED/ASSUMED/NOT_APPLICABLE",
    )
    verified_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assumption_reason: Mapped[str | None] = mapped_column(Text)


class AuditLog(Base):
    """认证/安全审计，与 data_lineage 分工（后者关注业务记录变更）。"""

    __tablename__ = "audit_logs"
    audit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    action: Mapped[str] = mapped_column(String(50), index=True)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(100))
    ip: Mapped[str | None] = mapped_column(INET)
    user_agent: Mapped[str | None] = mapped_column(String(500))
    request_id: Mapped[str | None] = mapped_column(String(50))
    detail_json: Mapped[dict | None] = mapped_column(JSONB)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class SystemSetting(Base):
    """全局键值（feature flag/限制阈值等）。"""

    __tablename__ = "system_settings"
    setting_key: Mapped[str] = mapped_column(String(100), primary_key=True)
    setting_value_json: Mapped[dict] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ReportDefinition(TimestampMixin, Base):
    """报表定义（模板+查询）。"""

    __tablename__ = "report_definitions"
    report_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    report_name: Mapped[str] = mapped_column(String(200))
    report_type: Mapped[str] = mapped_column(String(30))
    query_json: Mapped[dict] = mapped_column(JSONB)
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("template_files.template_id")
    )
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)


class ReportExecutionLog(Base):
    __tablename__ = "report_execution_logs"
    exec_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    report_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("report_definitions.report_id"), index=True
    )
    executed_by: Mapped[uuid.UUID] = mapped_column(Uuid)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    row_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), comment="OK/FAILED/RUNNING")
    error_message: Mapped[str | None] = mapped_column(Text)


class DocumentChunk(Base):
    """RAG 切片（ADR-0021）。"""

    __tablename__ = "document_chunks"
    chunk_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    source_type: Mapped[str] = mapped_column(
        String(30), comment="SPEC/ADR/PROCEDURE/REPORT"
    )
    source_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("projects.project_id"), index=True
    )
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding_vector: Mapped[list | None] = mapped_column(JSONB, comment="pgvector 落库后转 vector")
    token_count: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AiAuditLog(Base):
    """AI 决策与提示词审计（SUP-006 强制）。"""

    __tablename__ = "ai_audit_log"
    ai_log_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    agent_id: Mapped[uuid.UUID] = mapped_column(Uuid, index=True)
    session_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, index=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    operation: Mapped[str] = mapped_column(String(50))
    prompt_text: Mapped[str | None] = mapped_column(Text)
    response_text: Mapped[str | None] = mapped_column(Text)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer)
    response_tokens: Mapped[int | None] = mapped_column(Integer)
    model: Mapped[str | None] = mapped_column(String(50))
    cost_usd: Mapped[float | None] = mapped_column(Float)
    decision_ref_type: Mapped[str | None] = mapped_column(String(30))
    decision_ref_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    human_approved: Mapped[bool | None] = mapped_column(Boolean)
    human_approver_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )


class LicenseConfig(Base):
    """公司级 license；本期用单行 default = 'DEFAULT'。"""

    __tablename__ = "license_configs"
    __table_args__ = (
        UniqueConstraint("license_key", name="uq_license_configs_key"),
    )
    license_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    license_key: Mapped[str] = mapped_column(String(200))
    modules_json: Mapped[dict] = mapped_column(
        JSONB,
        comment='{"pipe":true,"pump":true,"psv":true,"flare":true,"heat":true,'
        '"vessel":true,"sep":true,"cool":true,"psychro":false,'
        '"cost":true,"ai":"ASSISTANT","max_users":50,"expiry":"2099-12-31"}',
    )
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")
