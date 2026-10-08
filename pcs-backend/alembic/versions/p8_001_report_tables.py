"""P8 报表 4 张表.

`report_definitions` / `report_execution_logs` 的表名沿用 bootstrap 迁移
`dd47298c9c38`（v3.1 全量 53 表），但那两张表**从未被使用**（无 service / API /
前端引用，0 行），且字段与 SPEC-P8 §3.2.2(2) 的报表定义结构完全不同（旧的只有
report_id / report_name / query_json / template_id / enabled）。用户 2026-10-08
裁决就地改造，drop 后按 SPEC 的 schema 重建。

**幂等**：4 张表全部先 `drop_table(if_exists=True)` 再 `create_table`。
⚠️ 这个 drop-then-create 模式**只适用于这 4 张表**（其中 2 张确为新建、2 张是
0 行的空壳）。禁止复制到有数据的表上 —— 那是一次 drop 全表。后续修改一律用
`op.add_column` / `op.alter_column`。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p8_001"
down_revision = "p7_s5_008"
branch_labels = None
depends_on = None

_TABLES = ("report_styles", "report_files", "report_definitions", "report_execution_logs")

# ⚠️ drop 顺序必须是 create 顺序的**逆序**。report_execution_logs 有 FK 指向
# report_definitions，Postgres 不允许在还有依赖子表时 drop 父表 —— 哪怕写了
# `IF EXISTS` 也一样报 `cannot drop table ... because other objects depend on it`。
# 这个坑只在**表已存在**时炸：首次跑（表还不存在）顺序也对，只有撞上 bootstrap
# 建出来的 legacy 空壳才暴露。别把它改回 `_TABLES` 的顺序。
_DROP_ORDER = tuple(reversed(_TABLES))


def upgrade() -> None:
    """删掉可能已存在的 4 张表（含 bootstrap 遗留空壳），再按 P8 schema 建."""
    for t in _DROP_ORDER:
        op.drop_table(t, if_exists=True)

    # --- report_styles -------------------------------------------------------
    op.create_table(
        "report_styles",
        sa.Column("style_id", sa.Uuid(), nullable=False),
        sa.Column("report_type", sa.String(64), nullable=False),
        # 公司级样式不属于任何项目 → nullable
        sa.Column("project_id", sa.Uuid(),
                  sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True),
        sa.Column("style_json", JSONB(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("style_id", name="pk_report_styles"),
        sa.UniqueConstraint("report_type", "project_id", "version",
                           name="uq_report_styles_scope_version"),
    )
    op.create_index("ix_report_styles_report_type", "report_styles", ["report_type"])

    # --- report_files --------------------------------------------------------
    op.create_table(
        "report_files",
        sa.Column("report_file_id", sa.Uuid(), nullable=False),
        # ⚠️ 刻意无 FK。ReportFile.project_id 在 ORM 侧同样无 FK，理由见
        # app/models/report.py 的 docstring：加了 CASCADE 会在项目删除后
        # 留下无记录的孤儿磁盘文件。**不要"顺手补上 FK"。**
        sa.Column("project_id", sa.Uuid(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("file_path", sa.String(500), nullable=False),
        sa.Column("file_format", sa.String(10), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("style_version", sa.String(32), nullable=True),
        sa.Column("data_version", sa.String(64), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("heartbeat_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("has_assumption_page", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("report_file_id", name="pk_report_files"),
        sa.UniqueConstraint("content_hash", name="uq_report_files_content_hash"),
    )
    op.create_index("ix_report_files_project_id", "report_files", ["project_id"])
    op.create_index("ix_report_files_status", "report_files", ["status"])

    # --- report_definitions --------------------------------------------------
    op.create_table(
        "report_definitions",
        sa.Column("def_id", sa.Uuid(), nullable=False),
        sa.Column("project_id", sa.Uuid(),
                  sa.ForeignKey("projects.project_id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category", sa.String(32), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("definition_json", JSONB(), nullable=False),
        sa.Column("output_format", sa.String(10), nullable=False),
        sa.Column("max_rows", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(32), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("shared_with", sa.String(20), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("def_id", name="pk_report_definitions"),
        sa.UniqueConstraint("project_id", "name", name="uq_report_definitions_project_name"),
    )
    op.create_index("ix_report_definitions_status", "report_definitions", ["status"])

    # --- report_execution_logs ----------------------------------------------
    op.create_table(
        "report_execution_logs",
        sa.Column("log_id", sa.Uuid(), nullable=False),
        sa.Column("def_id", sa.Uuid(),
                  sa.ForeignKey("report_definitions.def_id", ondelete="CASCADE"), nullable=False),
        sa.Column("def_version", sa.String(32), nullable=False),
        sa.Column("condition_snapshot", JSONB(), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("output_format", sa.String(10), nullable=False),
        sa.Column("executed_by", sa.Uuid(), nullable=True),
        sa.Column("is_temporary_adjust", sa.Boolean(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True),
                  server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("log_id", name="pk_report_execution_logs"),
    )
    op.create_index("ix_report_execution_logs_def_id", "report_execution_logs", ["def_id"])


def downgrade() -> None:
    """删除 4 张表，逆序同 upgrade."""
    for t in _DROP_ORDER:
        op.drop_table(t, if_exists=True)
