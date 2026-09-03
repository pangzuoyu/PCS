"""pcs_toe_conversion_factors 时间戳列矫正（终审 F3）

Revision ID: p2_s110_fix_toe_timestamptz
Revises: p2_s110_doc_no_project_id
Create Date: 2026-09-04

2026_09_03_0800_add_toe_conversion 把 created_at/updated_at 建成了无时区
sa.DateTime 且 updated_at NOT NULL，与 ORM TimestampMixin 及兄弟迁移
2026_09_03_1000_add_htri_template_schemas（DateTime(timezone=True) +
updated_at nullable）不一致。本迁移矫正（不回改 0800 文件——pcs_test DB
已应用，改历史不传播）。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2_s110_fix_toe_timestamptz"
down_revision: str | None = "p2_s110_doc_no_project_id"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "pcs_toe_conversion_factors",
        "created_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "pcs_toe_conversion_factors",
        "updated_at",
        type_=sa.DateTime(timezone=True),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column("pcs_toe_conversion_factors", "updated_at", nullable=True)


def downgrade() -> None:
    op.alter_column("pcs_toe_conversion_factors", "updated_at", nullable=False)
    op.alter_column(
        "pcs_toe_conversion_factors",
        "updated_at",
        type_=sa.DateTime(),
        postgresql_using="updated_at AT TIME ZONE 'UTC'",
    )
    op.alter_column(
        "pcs_toe_conversion_factors",
        "created_at",
        type_=sa.DateTime(),
        postgresql_using="created_at AT TIME ZONE 'UTC'",
    )
