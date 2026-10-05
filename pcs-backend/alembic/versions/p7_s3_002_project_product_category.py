"""p7_s3_002: projects.product_category — GB 30251-2024 §6.1.5 电折标口径判据.

用户裁决 2026-10-05「按 project 产品类型强制」。

背景: electricity_value_type 此前默认 "EQUIVALENT" (当量值) 且由调用方任意传,
而 POST /util/energy-summary/aggregate 根本不传 → 炼油/乙烯项目静默用当量值
(0.086 vs 0.21 kg标油/kWh, 差 2.44 倍), 违反 GB 30251-2024 §6.1.5。

Revision ID: p7_s3_002
Revises: p7_s3_001
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s3_002"
down_revision = "p7_s3_001"
branch_labels = None
depends_on = None

_PRODUCT_CATEGORIES = ("REFINING", "ETHYLENE", "OTHER")


def upgrade() -> None:
    """加 product_category 列 (server_default OTHER) + CHECK 约束 + 索引."""
    # server_default 必带: 存量 projects 行无此列值, 无 default 则 NOT NULL 加列失败
    op.add_column(
        "projects",
        sa.Column(
            "product_category",
            sa.String(20),
            nullable=False,
            server_default="OTHER",
            comment=(
                "产品类别 (GB 30251-2024 §6.1.5): REFINING/ETHYLENE 电用等价值; "
                "其余当量值"
            ),
        ),
    )
    op.create_check_constraint(
        "ck_projects_product_category",
        "projects",
        "product_category IN ('REFINING', 'ETHYLENE', 'OTHER')",
    )
    # index=True 在 ORM 层声明, alembic 需显式建 (与 p7_s3_001 同一教训)
    op.create_index(
        "ix_projects_product_category",
        "projects",
        ["product_category"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """删索引 + CHECK 约束 + product_category 列."""
    op.drop_index(
        "ix_projects_product_category", table_name="projects", if_exists=True
    )
    op.drop_constraint(
        "ck_projects_product_category", "projects", type_="check", if_exists=True
    )
    op.drop_column("projects", "product_category")
