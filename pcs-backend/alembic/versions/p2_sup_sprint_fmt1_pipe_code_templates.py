"""SUP Sprint FMT-1: pipe_code_templates + project_pipe_code_configs 两表（V1.4 §11.1/§11.2）。

公司级模板：template_id UUID PK + asset_id FK→config_assets（INT-OPEN-01
asset_subtype=PIPE_CODE_TEMPLATE）+ template_name str100 UNIQUE + 5 态 status。

项目级配置：config_id UUID PK + source_template_id FK 可空（V1.4 §0.5 项目级 fork）
+ UNIQUE(project_id, config_name) + snapshot_json + 5 态。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sup_sprint_fmt1_pipe_code_templates"
down_revision: str | None = "p2_sup_sprint_sym1_stream_symbols"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pipe_code_templates",
        sa.Column("template_id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("asset_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("template_name", sa.String(100), nullable=False, unique=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("format_definition_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("version", sa.String(50), nullable=False, server_default="1"),
        sa.Column("created_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
    )
    op.create_foreign_key(
        "fk_pipe_code_templates_asset_id_config_assets",
        "pipe_code_templates", "config_assets",
        ["asset_id"], ["asset_id"],
    )
    op.create_index("ix_pipe_code_templates_status", "pipe_code_templates", ["status"])

    op.create_table(
        "project_pipe_code_configs",
        sa.Column("config_id", sa.UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("source_template_id", sa.UUID(as_uuid=True), nullable=True),
        sa.Column("config_name", sa.String(100), nullable=False),
        sa.Column("format_definition_json", sa.JSON(), nullable=False),
        sa.Column("snapshot_json", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="DRAFT"),
        sa.Column("created_by", sa.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True),
            nullable=False, server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("project_id", "config_name", name="uq_project_pipe_code_config"),
    )
    op.create_foreign_key(
        "fk_project_pipe_code_configs_project_id_projects",
        "project_pipe_code_configs", "projects",
        ["project_id"], ["project_id"],
    )
    op.create_foreign_key(
        "fk_ppcc_source_template_id",
        "project_pipe_code_configs", "pipe_code_templates",
        ["source_template_id"], ["template_id"],
    )
    op.create_index(
        "ix_project_pipe_code_configs_project_id",
        "project_pipe_code_configs", ["project_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_pipe_code_configs_project_id", "project_pipe_code_configs")
    op.drop_table("project_pipe_code_configs")
    op.drop_index("ix_pipe_code_templates_status", "pipe_code_templates")
    op.drop_table("pipe_code_templates")
