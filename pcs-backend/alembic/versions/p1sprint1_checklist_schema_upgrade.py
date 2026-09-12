"""Sprint 1：project_input_checklist schema 对齐 DICT-ALL-003 V3.1 表44。

P0 baseline（dd47298c9c38）只建了 status/note 三字段，偏离 V3.1：
- status 三态 PENDING/READY/BLOCKED → 五态 NOT_STARTED/IN_PROGRESS/
  VERIFIED/ASSUMED/NOT_APPLICABLE
- 缺 module / input_category / input_value_json / source_type /
  verified_by / verified_at / assumption_reason

约束：nullable=True + 不改 P0 已有数据 → 不破坏老记录，PUT 端点按 5 态实现。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision: str = "p1sprint1_checklist_schema_upgrade"
down_revision: str | None = "p1sprint1_workspace_checklist"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "project_input_checklist",
        sa.Column("module", sa.String(length=30), nullable=True),
    )
    op.add_column(
        "project_input_checklist",
        sa.Column(
            "input_category",
            sa.String(length=20),
            nullable=True,
            comment="REQUIRED/CONDITIONAL/OPTIONAL",
        ),
    )
    op.add_column(
        "project_input_checklist",
        sa.Column("input_value_json", JSONB, nullable=True),
    )
    op.add_column(
        "project_input_checklist",
        sa.Column("source_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "project_input_checklist",
        sa.Column("verified_by", UUID, nullable=True),
    )
    op.add_column(
        "project_input_checklist",
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "project_input_checklist",
        sa.Column("assumption_reason", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("project_input_checklist", "assumption_reason")
    op.drop_column("project_input_checklist", "verified_at")
    op.drop_column("project_input_checklist", "verified_by")
    op.drop_column("project_input_checklist", "source_type")
    op.drop_column("project_input_checklist", "input_value_json")
    op.drop_column("project_input_checklist", "input_category")
    op.drop_column("project_input_checklist", "module")