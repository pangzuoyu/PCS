"""SUP Sprint FMT-3: project_pipe_code_sequences 计数器表（auto_increment 并发）。

FMT-OPEN-01：scope_key 默认 ``project_id + stream_symbol`` 组合键；用独立
计数器表防并发竞态（UPSERT 原子自增）。
"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2_sup_sprint_fmt1b_sequence_counter"
down_revision: str | None = "p2_sup_sprint_fmt1_pipe_code_templates"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "project_pipe_code_sequences",
        sa.Column("config_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("scope_key", sa.String(50), nullable=False),
        sa.Column("next_value", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint(
            "config_id", "scope_key", name="pk_project_pipe_code_sequences",
        ),
    )
    op.create_foreign_key(
        "fk_ppcs_config_id",
        "project_pipe_code_sequences",
        "project_pipe_code_configs",
        ["config_id"], ["config_id"],
    )


def downgrade() -> None:
    op.drop_table("project_pipe_code_sequences")
