"""P7-7+ BLOCKER-3 修复: user_projects 关联表 (cross-project IDOR 守卫)。

Per BLOCKER-3-cross-project-IDOR.md (registered 2026-10-01):
- 每用户每项目 1 行 (user_id, project_id, role_in_project)
- granted_by + granted_at + revoked_at 审计 trail
- 3 个 index: user_id / project_id / (user_id, project_id, revoked_at) active lookup

支持 _check_user_project_access 守卫覆盖全 23+ API endpoints。

F-P0-004 + F-P1-014 + F-P1-005 (Sprint 2 review 同源) 修复载体。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "p7_open_010_user_projects_blocker3"
down_revision: str | tuple[str, ...] | None = "p7_open_009_005_utility_energy_summary"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "user_projects",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", UUID(as_uuid=True), nullable=False),
        sa.Column("project_id", UUID(as_uuid=True), nullable=False),
        sa.Column("role_in_project", sa.String(32), nullable=False),
        sa.Column("granted_by", UUID(as_uuid=True), nullable=True),
        sa.Column("granted_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_by", UUID(as_uuid=True), nullable=True),
        # Timestamps from TimestampMixin
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKey("users.user_id", ondelete="CASCADE", name="fk_user_projects_user_id"),
        sa.ForeignKey("projects.project_id", ondelete="CASCADE", name="fk_user_projects_project_id"),
        sa.ForeignKey("users.user_id", name="fk_user_projects_granted_by"),
        sa.ForeignKey("users.user_id", name="fk_user_projects_revoked_by"),
    )
    op.create_index("ix_user_projects_user", "user_projects", ["user_id"])
    op.create_index("ix_user_projects_project", "user_projects", ["project_id"])
    op.create_index(
        "ix_user_projects_active",
        "user_projects",
        ["user_id", "project_id", "revoked_at"],
    )
    op.create_unique_constraint(
        "uq_user_projects_user_project",
        "user_projects",
        ["user_id", "project_id"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_user_projects_user_project", "user_projects")
    op.drop_index("ix_user_projects_active", "user_projects")
    op.drop_index("ix_user_projects_project", "user_projects")
    op.drop_index("ix_user_projects_user", "user_projects")
    op.drop_table("user_projects")
