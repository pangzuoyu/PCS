"""管道代码模板 ORM（SUP-002 §11.1/§11.2）。

公司级模板 pipe_code_templates：template_id UUID PK + asset_id FK→
config_assets（asset_subtype=PIPE_CODE_TEMPLATE）+ template_name str100 UNIQUE +
5 态 status + version。

项目级配置 project_pipe_code_configs：config_id UUID PK + source_template_id
FK 可空 + UNIQUE(project_id, config_name) + snapshot_json（fork 时公司级快照）
+ 5 态 status。

FMT-3 阶段会追加 ProjectPipeCodeSequence（auto_increment 并发计数器）。
"""
from __future__ import annotations

import uuid

from sqlalchemy import JSON, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.mixins import TimestampMixin


class PipeCodeTemplate(TimestampMixin, Base):
    __tablename__ = "pipe_code_templates"
    template_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    asset_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("config_assets.asset_id"), nullable=True,
    )
    template_name: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(String(500))
    format_definition_json: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")
    version: Mapped[str] = mapped_column(String(50), default="1")


class ProjectPipeCodeConfig(TimestampMixin, Base):
    __tablename__ = "project_pipe_code_configs"
    __table_args__ = (
        UniqueConstraint("project_id", "config_name", name="uq_project_pipe_code_config"),
    )
    config_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4,
    )
    project_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("projects.project_id"),
    )
    source_template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("pipe_code_templates.template_id"), nullable=True,
    )
    config_name: Mapped[str] = mapped_column(String(100))
    format_definition_json: Mapped[dict] = mapped_column(JSON)
    snapshot_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="DRAFT")


class ProjectPipeCodeSequence(Base):
    """FMT-3：auto_increment 并发计数器表。

    复合 PK (config_id, scope_key)。FMT-OPEN-01：scope_key 默认
    ``project_id + stream_symbol`` 组合键（service 层组装为字符串）。
    """

    __tablename__ = "project_pipe_code_sequences"
    config_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("project_pipe_code_configs.config_id"),
        primary_key=True,
    )
    scope_key: Mapped[str] = mapped_column(String(50), primary_key=True)
    next_value: Mapped[int] = mapped_column(Integer, default=1)
