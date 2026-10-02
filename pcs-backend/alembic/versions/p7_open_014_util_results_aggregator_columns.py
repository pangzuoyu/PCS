"""P7 Sprint 2 T5 aggregator columns 同步 (F-P1-007): UtilResults 加 4 列.

Per ce-code-review/20261001-174422-16a356de/report.md F-P1-007:
- UtilResults 缺 4 聚合字段 (annual_total_energy / total_toe /
  total_standard_coal_kg / tolerance_status), 让客户端不需要二次聚合
- 加 4 nullable 列 (默认值 NULL, 不破坏存量数据)
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p7_open_014_util_results_aggregator_columns"
down_revision: str | tuple[str, ...] | None = "p7_open_013_drop_tolerance_status_default"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.add_column(
        "util_results",
        sa.Column(
            "annual_total_energy",
            sa.Float(),
            nullable=True,
            comment="年总能耗 (MJ/yr; F-P1-007 同步 UtilityEnergySummary)",
        ),
    )
    op.add_column(
        "util_results",
        sa.Column(
            "total_toe",
            sa.Float(),
            nullable=True,
            comment="年折标油 (toe; F-P1-007 同步 UtilityEnergySummary)",
        ),
    )
    op.add_column(
        "util_results",
        sa.Column(
            "total_standard_coal_kg",
            sa.Float(),
            nullable=True,
            comment="年折标煤 (kg 标煤; F-P1-007 同步 UtilityEnergySummary)",
        ),
    )
    op.add_column(
        "util_results",
        sa.Column(
            "tolerance_status",
            sa.String(length=16),
            nullable=True,
            comment="容差状态 NA/OK/EXCEEDED (F-P1-007 + F-P0-004 server_default='NA')",
        ),
    )


def downgrade() -> None:
    op.drop_column("util_results", "tolerance_status")
    op.drop_column("util_results", "total_standard_coal_kg")
    op.drop_column("util_results", "total_toe")
    op.drop_column("util_results", "annual_total_energy")