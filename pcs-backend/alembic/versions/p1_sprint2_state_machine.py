"""Sprint 2：状态机快照字段。

- record_change_snapshots.snapshot_status：ADR-0024 V3.3 引入
  ACTIVE/CONSUMED/ABANDONED；nullable=True 不破坏 P0 老快照。
- equipment_type_codes.project_id 已在 P0 baseline（dd47298c9c38）实现，
  作为复合 PK 的一部分；本迁移不再添加。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p1_sprint2_state_machine"
down_revision: str | None = "p1sprint1_checklist_schema_upgrade"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "record_change_snapshots",
        sa.Column(
            "snapshot_status",
            sa.String(length=20),
            nullable=True,
            comment="ADR-0024：ACTIVE/CONSUMED/ABANDONED",
        ),
    )
    op.create_index(
        "ix_record_change_snapshots_snapshot_status",
        "record_change_snapshots",
        ["snapshot_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_record_change_snapshots_snapshot_status",
        table_name="record_change_snapshots",
    )
    op.drop_column("record_change_snapshots", "snapshot_status")