"""P7 Sprint 2 T5 容差修复 (F-P0-004): 删 tolerance_status server_default='OK' 假阴性.

Per ce-code-review/20261001-174422-16a356de/report.md F-P0-004:
- 旧: tolerance_status server_default='OK' (compliance audit 误读为 'computed and within 2%')
- 新: server_default='NA' (无 XLS 参考) — 必须 service 显式写入 OK/EXCEEDED 才表示已计算
- 加 CHECK 约束: tolerance_status='OK' ⟹ tolerance_pct IS NOT NULL AND tolerance_pct <= 2.0
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "p7_open_013_drop_tolerance_status_default"
down_revision: str | tuple[str, ...] | None = "p7_open_012_r1_classification_persist"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # 1. 先把所有现存 'OK' 默认值改成 'NA' (那些只是 server_default 副作用, 真实未计算)
    op.execute(
        "UPDATE utility_energy_summary "
        "SET tolerance_status = 'NA' "
        "WHERE tolerance_pct IS NULL AND tolerance_status = 'OK'"
    )

    # 2. 删 server_default='OK', 改 server_default='NA'
    op.alter_column(
        "utility_energy_summary",
        "tolerance_status",
        server_default="NA",
        existing_type=sa.String(length=16),
        nullable=False,
    )

    # 3. 加 CHECK 约束: tolerance_status='OK' 必有 tolerance_pct IS NOT NULL AND <= 2.0
    op.create_check_constraint(
        "ck_utility_energy_summary_tolerance_status_ok_has_pct",
        "utility_energy_summary",
        (
            "tolerance_status != 'OK' OR "
            "(tolerance_pct IS NOT NULL AND tolerance_pct <= 2.0)"
        ),
    )

    # 4. 加 CHECK 约束: tolerance_status='EXCEEDED' 必有 tolerance_pct IS NOT NULL AND > 2.0
    op.create_check_constraint(
        "ck_utility_energy_summary_tolerance_status_exceeded_has_pct",
        "utility_energy_summary",
        (
            "tolerance_status != 'EXCEEDED' OR "
            "(tolerance_pct IS NOT NULL AND tolerance_pct > 2.0)"
        ),
    )


def downgrade() -> None:
    op.drop_constraint(
        "ck_utility_energy_summary_tolerance_status_exceeded_has_pct",
        "utility_energy_summary",
        type_="check",
    )
    op.drop_constraint(
        "ck_utility_energy_summary_tolerance_status_ok_has_pct",
        "utility_energy_summary",
        type_="check",
    )
    op.alter_column(
        "utility_energy_summary",
        "tolerance_status",
        server_default="OK",
        existing_type=sa.String(length=16),
        nullable=False,
    )