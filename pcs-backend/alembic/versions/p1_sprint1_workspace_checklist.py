"""Sprint 1：doc_no_sequences UNIQUE(template_id, scope_key) 约束。

为 P1.2 编号原子分配（pg_insert ... on_conflict_do_update）提供 DB 侧
并发安全约束。Sprint 1 期间 UNIQUE 已生效，fixture 默认填值防冲突。
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p1sprint1_workspace_checklist"
down_revision: str | None = "dd47298c9c38"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_doc_no_sequences_template_scope",
        "doc_no_sequences",
        ["template_id", "scope_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_doc_no_sequences_template_scope",
        "doc_no_sequences",
        type_="unique",
    )