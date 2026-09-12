"""Sprint 3：bootstrap 修复 alembic_version.version_num 列宽。

历史：Sprint 2 upgrade head 时发现 alembic_version.version_num 是 VARCHAR(32)，
装不下 'p1sprint1_checklist_schema_upgrade'（37 字符）。已手动 ALTER 到 VARCHAR(64)。

本迁移把手动修复落到代码中（条件 ALTER，已是 64 则跳过）。无业务影响。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p1_sprint3_bootstrap_alembic_version"
down_revision: str | None = "p1_sprint2_state_machine"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    conn = op.get_bind()
    # 条件：仅当列宽 < 64 时才扩
    res = conn.execute(
        sa.text(
            "SELECT character_maximum_length FROM information_schema.columns "
            "WHERE table_name='alembic_version' AND column_name='version_num'"
        )
    ).scalar()
    if res is not None and res < 64:
        op.alter_column(
            "alembic_version",
            "version_num",
            existing_type=sa.String(length=res),
            type_=sa.String(length=64),
            existing_nullable=False,
        )


def downgrade() -> None:
    # 不还原：Sprint 2 之前的 revision 名称都已 <32 字符，无回退必要
    pass