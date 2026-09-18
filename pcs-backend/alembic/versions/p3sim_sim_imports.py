"""P3.x SIM-14：sim_imports + sim_import_warnings 表（stateful preview，D-4 等价闭环）。

spec §5.5 + 用户 2026-09-09 裁决（D-4 闭环条件）：
- preview 阶段：解析后写入 sim_imports（status=PREVIEW，含 preview_streams_json +
  conflict_report_json + warnings_json），返回 import_id
- commit 阶段：通过 import_id 读取 sim_imports，校验 expires_at > now，
  落库后更新 status=COMMITTED + committed_at + committed_by
- 24h 过期：expires_at = created_at + 24h（业务可调）

设计要点：
- simimporttype enum：PROII / EXCEL
- simimportstatus enum：PREVIEW / COMMITTED / EXPIRED
- simimportwarningseverity enum：BLOCK / WARN / INFO
- FK：sim_imports.project_id → projects；sim_imports.workspace_id → workspaces
- FK：sim_import_warnings.import_id → sim_imports（ON DELETE CASCADE）
- 索引：(project_id, status) 联合 + expires_at 单列（过期清理用）

Revision ID: p3sim_sim_imports
Revises: p3sim_stream_sign_status_extend
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "p3sim_sim_imports"
down_revision = "p3sim_stream_sign_status_extend"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """SIM 导入批次主表 sim_imports + 4 enum 创建（P3.2 SIM 批次）。

    步骤：
    - 3 个 PG enum：simimporttype (PROII/EXCEL) + simimportstatus (PREVIEW/COMMITTED/EXPIRED)
      + simimportwarningseverity (BLOCK/WARN/INFO)
    - 主表 sim_imports：import_id (PK UUID) + project_id (FK) + workspace_id (FK) +
      import_type + status + source_file_path + source_file_hash (SHA-256) +
      source_file_size + parser_version + warnings_json (JSONB) +
      created_by + created_at + committed_at + expires_at
    - 索引：project_id + workspace_id（项目级 / 工作区级查询）
    - 派生表：sim_import_warnings（独立记录每条 warning，便于回查）

    业务：PRO/II + Excel 导入批次管理（PREVIEW 预览 → COMMITTED 提交 → EXPIRED 过期）。
    与 sim_unit_op_results 关系：本表为批次头；sim_unit_op_results 行为项。
    """
    # PG enum: simimporttype
    simimporttype = postgresql.ENUM(
        "PROII", "EXCEL", name="simimporttype", create_type=True
    )
    simimporttype.create(op.get_bind(), checkfirst=True)
    # PG enum: simimportstatus
    simimportstatus = postgresql.ENUM(
        "PREVIEW", "COMMITTED", "EXPIRED", name="simimportstatus", create_type=True
    )
    simimportstatus.create(op.get_bind(), checkfirst=True)
    # PG enum: simimportwarningseverity
    simimportwarningseverity = postgresql.ENUM(
        "BLOCK", "WARN", "INFO", name="simimportwarningseverity", create_type=True
    )
    simimportwarningseverity.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "sim_imports",
        sa.Column("import_id", sa.Uuid(), primary_key=True),
        sa.Column("project_id", sa.Uuid(), nullable=False),
        sa.Column("workspace_id", sa.Uuid(), nullable=False),
        sa.Column(
            "import_type",
            postgresql.ENUM(
                "PROII",
                "EXCEL",
                name="simimporttype",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "status",
            postgresql.ENUM(
                "PREVIEW",
                "COMMITTED",
                "EXPIRED",
                name="simimportstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("source_file_name", sa.String(length=500), nullable=False),
        sa.Column("convergence_status", sa.String(length=30), nullable=True),
        sa.Column("banner_version", sa.String(length=20), nullable=True),
        sa.Column(
            "preview_streams_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("conflict_report_json", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "warnings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("committed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("committed_by", sa.Uuid(), nullable=True),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.project_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["workspace_id"], ["workspaces.workspace_id"], ondelete="RESTRICT"
        ),
    )
    op.create_index(
        "ix_sim_imports_project_status", "sim_imports", ["project_id", "status"]
    )
    op.create_index("ix_sim_imports_expires_at", "sim_imports", ["expires_at"])

    op.create_table(
        "sim_import_warnings",
        sa.Column("warning_id", sa.Uuid(), primary_key=True),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column(
            "severity",
            postgresql.ENUM(
                "BLOCK",
                "WARN",
                "INFO",
                name="simimportwarningseverity",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("unit_id", sa.String(length=100), nullable=True),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["import_id"], ["sim_imports.import_id"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("sim_import_warnings")
    op.drop_index("ix_sim_imports_expires_at", table_name="sim_imports")
    op.drop_index("ix_sim_imports_project_status", table_name="sim_imports")
    op.drop_table("sim_imports")
    op.execute("DROP TYPE IF EXISTS simimportwarningseverity")
    op.execute("DROP TYPE IF EXISTS simimportstatus")
    op.execute("DROP TYPE IF EXISTS simimporttype")
