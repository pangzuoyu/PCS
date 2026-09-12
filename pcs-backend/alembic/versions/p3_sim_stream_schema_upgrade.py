"""P3.2 SIM streams schema 升级（修正版 10 字段，2026-09-08）。

净新增 9 列 + 2 个 CHECK 约束：

- streams.case_type VARCHAR(20) + CHECK（物流级 NORMAL/END_OF_RUN/START_OF_RUN/TURN_DOWN）
- streams.surface_tension / api_gravity / critical_temp / critical_press / actual_vol_flow FLOAT
- streams.viscosity_temperature_curve JSONB
- streams.import_original_row INT（PRO/II 原始行号溯源）
- streams.import_source_version VARCHAR(20)（V2.71/V4.17/V8.x）
- stream_state_points.case_type CHECK 约束（列已存在，仅补约束）

不动的列（plan vs 现状差异已修正）：
- streams.sign_status：已是 PG native enum streamsignstatus，**不动**；P4 扩展走
  ALTER TYPE streamsignstatus ADD VALUE（不可逆）。
- streams.vapor_fraction / source_type / data_mode：已存在，不重复添加。
- stream_state_points.case_type：列已存在 NOT NULL VARCHAR(20)，仅补 CHECK 约束。

Revision ID: p3sim_stream_upgrade
Revises: p2_sup_sprint_int1_project_template_integration
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "p3sim_stream_upgrade"
down_revision = "p2_sup_sprint_int1_project_template_integration"
branch_labels = ("p3.2-sim",)
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------------
    # streams 表：9 新字段
    # ------------------------------------------------------------------------
    op.add_column(
        "streams",
        sa.Column("case_type", sa.String(20), nullable=True),
    )
    op.add_column(
        "streams",
        sa.Column("surface_tension", sa.Float(), nullable=True),
    )
    op.add_column(
        "streams",
        sa.Column("api_gravity", sa.Float(), nullable=True),
    )
    op.add_column(
        "streams",
        sa.Column("critical_temp", sa.Float(), nullable=True),
    )
    op.add_column(
        "streams",
        sa.Column("critical_press", sa.Float(), nullable=True),
    )
    op.add_column(
        "streams",
        sa.Column("actual_vol_flow", sa.Float(), nullable=True),
    )
    op.add_column(
        "streams",
        sa.Column(
            "viscosity_temperature_curve",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "streams",
        sa.Column("import_original_row", sa.Integer(), nullable=True),
    )
    op.add_column(
        "streams",
        sa.Column("import_source_version", sa.String(20), nullable=True),
    )

    # streams.case_type CHECK 约束
    op.create_check_constraint(
        "ck_streams_case_type",
        "streams",
        "case_type IN ('NORMAL','END_OF_RUN','START_OF_RUN','TURN_DOWN')",
    )

    # ------------------------------------------------------------------------
    # stream_state_points 表：仅补 CHECK 约束（列已存在）
    # ------------------------------------------------------------------------
    op.create_check_constraint(
        "ck_stream_state_points_case_type",
        "stream_state_points",
        "case_type IN ('NORMAL','MIN','MAX','ALTERNATE')",
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_stream_state_points_case_type", "stream_state_points", type_="check"
    )
    op.drop_constraint("ck_streams_case_type", "streams", type_="check")
    op.drop_column("streams", "import_source_version")
    op.drop_column("streams", "import_original_row")
    op.drop_column("streams", "viscosity_temperature_curve")
    op.drop_column("streams", "actual_vol_flow")
    op.drop_column("streams", "critical_press")
    op.drop_column("streams", "critical_temp")
    op.drop_column("streams", "api_gravity")
    op.drop_column("streams", "surface_tension")
    op.drop_column("streams", "case_type")
