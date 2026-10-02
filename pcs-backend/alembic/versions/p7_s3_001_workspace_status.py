"""F-P3-003 Sprint 3: workspaces.status 列 + 索引 (2-state ACTIVE/ARCHIVED).

Revision ID: p7_s3_001
Revises: p7_s2_002
Create Date: 2026-10-03

down_revision 来源: git log -- pcs-backend/alembic/versions/p7_s2_002_workspace_fk_restrict.py
→ commit 498b8e7 "fix(p7-s2): F-P3-003 workspace FK CASCADE → RESTRICT"
PCS Sprint 3 主分支 head = p7_s2_002.

alembic 1.7+ 支持 if_not_exists (PCS 当前 1.19.1, ✅ — 通过 `uv run alembic --version` 确认).
F-P3-002 教训: 索引必须显式 op.create_index, ORM 层 index=True 只对 create_all() 生效.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s3_001"
down_revision = "p7_s2_002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """加 workspaces.status 列 (server_default=ACTIVE 兼容历史行) + 索引."""
    op.add_column(
        "workspaces",
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="ACTIVE",
            comment="F-P3-003: ACTIVE / ARCHIVED 2-state",
        ),
    )
    op.create_index(
        "ix_workspaces_status",
        "workspaces",
        ["status"],
        if_not_exists=True,
    )


def downgrade() -> None:
    """回滚: 删索引 + 删列."""
    op.drop_index("ix_workspaces_status", table_name="workspaces", if_exists=True)
    op.drop_column("workspaces", "status")