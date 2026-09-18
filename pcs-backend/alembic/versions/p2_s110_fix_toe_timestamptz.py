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
    """pcs_toe_conversion_factors 时间戳列矫正（P2 Sprint1 §110 / 终审 F3）。

    步骤：
    - created_at：DateTime → DateTime(timezone=True)（PG AT TIME ZONE 'UTC' 转）
    - updated_at：DateTime → DateTime(timezone=True) + 改 nullable=True

    不改历史：pcs_test DB 已应用 2026_09_03_0800_add_toe_conversion，本迁移
    仅矫正不回改原文件。

    业务：与 ORM TimestampMixin + 兄弟迁移 2026_09_03_1000_add_htri_template_schemas
    对齐（timezone=True + updated_at nullable），保证 application 层时区语义一致。
    """
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
    """pcs_toe_conversion_factors 时区列矫正回退（P2 S110 终审 F3 逆向）。

    步骤：
    - ALTER COLUMN updated_at SET NOT NULL
    - ALTER COLUMN updated_at TYPE DateTime（去掉 timezone）+
      postgresql_using AT TIME ZONE 'UTC'（剥离 tz）
    - ALTER COLUMN created_at TYPE DateTime + AT TIME ZONE 'UTC'

    业务：与 upgrade 互逆；S110 终审 F3 把 PCS 表 timestamptz → datetime 的矫正
    落地逆向。AT TIME ZONE 'UTC' 把 timestamptz 转回 naive datetime（按 UTC
    落表）。注意：updated_at NOT NULL 回退意味着 NULL 行会被违例报错；如有 NULL
    行需先 UPDATE。
    """
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
