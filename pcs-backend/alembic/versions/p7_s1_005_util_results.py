"""util_results 表 + 2 索引（P7-Sprint 1 T3 / S1-5）。

创建 util_results 表：
- util_result_id UUID PK
- project_id / workspace_id FK
- business_date (折标煤按年查询需要)
- consumption_json JSONB 13 类 flat {category: float}
- jsonb_deprecated BOOL DEFAULT false（Sprint 1 JSONB 权威）
- source VARCHAR(200)（数据来源描述）
- created_by / created_at / updated_at（TimestampMixin）

索引：
- ix_util_results_project (project_id)
- ix_util_results_workspace (workspace_id)
- ix_util_results_project_workspace (project_id, workspace_id) — 复合

Sprint 2 Task S2-1~6 会在 util.py 追加 5 张独立表（utility_power_items /
utility_fuel_gas / utility_heat_exchange / utility_energy_summary /
catalyst_loading），本 migration 仅落 V1.3 基线单表。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID

# revision identifiers, used by Alembic.
revision: str = "p7_s1_005"
down_revision: str | None = "p7_s1_001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    op.create_table(
        "util_results",
        sa.Column("util_result_id", UUID(as_uuid=True), primary_key=True),
        sa.Column("project_id", UUID(as_uuid=True), sa.ForeignKey("projects.project_id"), nullable=False),
        sa.Column("workspace_id", UUID(as_uuid=True), sa.ForeignKey("workspaces.workspace_id"), nullable=False),
        sa.Column("business_date", sa.Date(), nullable=True),
        sa.Column("consumption_json", JSONB(), nullable=False, comment="13 类 flat {category: float}"),
        sa.Column("jsonb_deprecated", sa.Boolean(), nullable=False, server_default=sa.text("false"), comment="Sprint 1 False JSONB 权威；Sprint 2 起 True 表示已迁移 5 表"),
        sa.Column("source", sa.String(200), nullable=True, comment="数据来源描述"),
        sa.Column("created_by", UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_util_results_project", "util_results", ["project_id"])
    op.create_index("ix_util_results_workspace", "util_results", ["workspace_id"])
    op.create_index("ix_util_results_project_workspace", "util_results", ["project_id", "workspace_id"])


def downgrade() -> None:
    op.drop_index("ix_util_results_project_workspace", table_name="util_results")
    op.drop_index("ix_util_results_workspace", table_name="util_results")
    op.drop_index("ix_util_results_project", table_name="util_results")
    op.drop_table("util_results")
