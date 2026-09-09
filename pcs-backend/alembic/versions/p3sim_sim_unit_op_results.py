"""P3.x SIM-15: sim_unit_op_results + 6 专用结果表。

spec §5.5 + audit V2.0 E-1：
- sim_unit_op_results 主表：13 类单元公共字段（unit_uid/unit_type/iterations/convergence/raw_summary_json）
- 6 类专用表（1:1 FK → sim_unit_op_results.unit_op_id）：
  - sim_reactor_results / sim_cstr_results / sim_compressor_results /
    sim_splitter_results / sim_stca_results / sim_calculator_results
- FK：sim_unit_op_results.import_id → sim_imports.import_id（ON DELETE CASCADE）
- 索引：import_id + unit_type + (import_id, unit_uid) UNIQUE

Revision ID: p3sim_sim_unit_op_results
Revises: p3sim_sim_tower_results
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "p3sim_sim_unit_op_results"
down_revision = "p3sim_sim_tower_results"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 主表
    op.create_table(
        "sim_unit_op_results",
        sa.Column("unit_op_id", sa.Uuid(), primary_key=True),
        sa.Column("import_id", sa.Uuid(), nullable=False),
        sa.Column("unit_uid", sa.String(length=100), nullable=False),
        sa.Column("unit_type", sa.String(length=30), nullable=False),
        sa.Column("convergence_status", sa.String(length=30), nullable=True),
        sa.Column("iterations", sa.Integer(), nullable=True),
        sa.Column(
            "raw_summary_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "feed_streams_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "product_streams_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
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
        sa.UniqueConstraint("import_id", "unit_uid", name="uq_sim_unit_op_results_import_uid"),
    )
    op.create_index("ix_sim_unit_op_results_import_id", "sim_unit_op_results", ["import_id"])
    op.create_index("ix_sim_unit_op_results_unit_type", "sim_unit_op_results", ["unit_type"])

    # 6 专用表（PK 同时作 FK 到 sim_unit_op_results）
    op.create_table(
        "sim_reactor_results",
        sa.Column("unit_op_id", sa.Uuid(), primary_key=True),
        sa.Column("operation_mode", sa.String(length=30), nullable=True),
        sa.Column("rxset_id", sa.String(length=100), nullable=True),
        sa.Column("reactions_count", sa.Integer(), nullable=True),
        sa.Column(
            "conversions_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["unit_op_id"], ["sim_unit_op_results.unit_op_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "sim_cstr_results",
        sa.Column("unit_op_id", sa.Uuid(), primary_key=True),
        sa.Column("residence_time_min", sa.Float(), nullable=True),
        sa.Column("volume_m3", sa.Float(), nullable=True),
        sa.Column("outlet_temperature_k", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["unit_op_id"], ["sim_unit_op_results.unit_op_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "sim_compressor_results",
        sa.Column("unit_op_id", sa.Uuid(), primary_key=True),
        sa.Column("outlet_pressure_kpa", sa.Float(), nullable=True),
        sa.Column("polytropic_exponent", sa.Float(), nullable=True),
        sa.Column("work_kw", sa.Float(), nullable=True),
        sa.Column("efficiency", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(
            ["unit_op_id"], ["sim_unit_op_results.unit_op_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "sim_splitter_results",
        sa.Column("unit_op_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "outlets_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["unit_op_id"], ["sim_unit_op_results.unit_op_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "sim_stca_results",
        sa.Column("unit_op_id", sa.Uuid(), primary_key=True),
        sa.Column("ovhd_stream", sa.String(length=100), nullable=True),
        sa.Column("btms_stream", sa.String(length=100), nullable=True),
        sa.Column("actual_reflux_ratio", sa.Float(), nullable=True),
        sa.Column("min_reflux_ratio", sa.Float(), nullable=True),
        sa.Column("num_theoretical_stages", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(
            ["unit_op_id"], ["sim_unit_op_results.unit_op_id"], ondelete="CASCADE"
        ),
    )
    op.create_table(
        "sim_calculator_results",
        sa.Column("unit_op_id", sa.Uuid(), primary_key=True),
        sa.Column(
            "sequence_streams_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["unit_op_id"], ["sim_unit_op_results.unit_op_id"], ondelete="CASCADE"
        ),
    )


def downgrade() -> None:
    op.drop_table("sim_calculator_results")
    op.drop_table("sim_stca_results")
    op.drop_table("sim_splitter_results")
    op.drop_table("sim_compressor_results")
    op.drop_table("sim_cstr_results")
    op.drop_table("sim_reactor_results")
    op.drop_index("ix_sim_unit_op_results_unit_type", table_name="sim_unit_op_results")
    op.drop_index("ix_sim_unit_op_results_import_id", table_name="sim_unit_op_results")
    op.drop_table("sim_unit_op_results")
