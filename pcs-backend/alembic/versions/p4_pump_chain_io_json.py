"""P4-4-4 PUMP 链：pump_results 加 input_json / output_json 两列（与 PIPE/PIPE_NET 一致）。

约束：与 P4-0-2 SUP-008 不冲突（仅增量加列，不改既有列语义）。
DOWN-REVISION = p4_sup008_result_fields（最新迁移基线）。
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "p4_pump_chain_io_json"
down_revision = "p4_sup008_result_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pump_results",
        sa.Column(
            "input_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="PUMP 链入参（P4-4-4）",
        ),
    )
    op.add_column(
        "pump_results",
        sa.Column(
            "output_json",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
            comment="PUMP 链出参（P4-4-4）",
        ),
    )


def downgrade() -> None:
    op.drop_column("pump_results", "output_json")
    op.drop_column("pump_results", "input_json")
