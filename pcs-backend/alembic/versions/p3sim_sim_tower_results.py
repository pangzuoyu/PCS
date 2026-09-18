"""P3.x SIM-16: sim_tower_results 表（COLUMN SUMMARY 存档）。

spec §5.5 + audit V2.0 E-1：
- 每条 COLUMN 单元操作 → 1 行
- 基础元数据：tower_uid / tower_name / tower_type / num_stages / condenser_type /
  reboiler_type / feed_stages_json / product_streams_json
- 4 类 JSON 数据：tray_data_json / compositions_json / loading_json / rating_json
- FK：sim_tower_results.import_id → sim_imports.import_id（ON DELETE CASCADE）
- 索引：import_id（SIM-27 查询加速）

Revision ID: p3sim_sim_tower_results
Revises: p3sim_sim_imports
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "p3sim_sim_tower_results"
down_revision = "p3sim_sim_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """sim_tower_results 主表创建（SIM-16 / spec §5.5 COLUMN SUMMARY 存档）。

    步骤：
    - 主表 sim_tower_results：tower_id (PK UUID) + import_id (FK→sim_imports ON DELETE CASCADE)
    - 元数据：tower_uid / tower_name / tower_type / num_stages /
      condenser_type / reboiler_type / feed_stages_json / product_streams_json
    - 4 类 JSON 数据：tray_data_json（塔板水力学）+ compositions_json（组分）+
      loading_json（负荷）+ rating_json（额定）
    - 索引：import_id（SIM-27 按批次反查）
    - is_unreliable bool default false（不可靠标记，audit V2.0 E-1）

    业务：每条 COLUMN 单元操作 → 1 行塔存档；4 JSON 列承载完整水力学 +
    组分 + 负荷 + 额定数据，是 SIM-1 列计算核心存储。
    """
    op.create_table(
        "sim_tower_results",
        sa.Column("tower_id", sa.Uuid(), primary_key=True),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("tower_uid", sa.String(length=100), nullable=False),
        sa.Column("tower_name", sa.String(length=200), nullable=True),
        sa.Column("tower_type", sa.String(length=30), nullable=False),
        sa.Column("num_stages", sa.Integer(), nullable=True),
        sa.Column("condenser_type", sa.String(length=30), nullable=True),
        sa.Column("reboiler_type", sa.String(length=30), nullable=True),
        sa.Column(
            "feed_stages_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "product_streams_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "tray_data_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "compositions_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "loading_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "rating_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "is_unreliable", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
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
    op.create_index("ix_sim_tower_results_import_id", "sim_tower_results", ["import_id"])


def downgrade() -> None:
    op.drop_index("ix_sim_tower_results_import_id", table_name="sim_tower_results")
    op.drop_table("sim_tower_results")
