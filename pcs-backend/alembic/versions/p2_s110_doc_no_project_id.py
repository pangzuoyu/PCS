"""doc_no_sequences 补 project_id + 三列 UQ（DICT V3.4）

DICT-ALL-003 V3.4 §68 要求 doc_no_sequences 含 project_id UUID FK +
UQ(project_id, template_id, scope_key)。此前 DB 缺 project_id 列、只有
P1 Sprint 1 的两列 UQ（uq_doc_no_sequences_template_scope）；NumberingService
已按 (project_id, template_id, scope_key) 查建，ORM/测试均已就位，本迁移补齐
DB 侧。
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "p2_s110_doc_no_project_id"
down_revision: str | None = "15421f7d5afb"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "doc_no_sequences",
        sa.Column("project_id", sa.Uuid(), nullable=True),
    )
    op.create_foreign_key(
        "fk_doc_no_sequences_project_id",
        "doc_no_sequences",
        "projects",
        ["project_id"],
        ["project_id"],
    )
    op.drop_constraint(
        "uq_doc_no_sequences_template_scope", "doc_no_sequences", type_="unique"
    )
    op.create_unique_constraint(
        "uq_doc_no_sequences_proj_template_scope",
        "doc_no_sequences",
        ["project_id", "template_id", "scope_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_doc_no_sequences_proj_template_scope", "doc_no_sequences", type_="unique"
    )
    op.create_unique_constraint(
        "uq_doc_no_sequences_template_scope",
        "doc_no_sequences",
        ["template_id", "scope_key"],
    )
    op.drop_constraint(
        "fk_doc_no_sequences_project_id", "doc_no_sequences", type_="foreignkey"
    )
    op.drop_column("doc_no_sequences", "project_id")
