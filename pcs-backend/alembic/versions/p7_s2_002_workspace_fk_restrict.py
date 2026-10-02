"""workspace_id FK ondelete CASCADE → RESTRICT (F-P3-003 fix).

历史: util_results / utility_power_items / utility_fuel_gas /
utility_heat_exchange 4 张表的 workspace_id FK 用 ondelete=CASCADE,
导致 workspace 删除时静默销毁业务数据 (不可逆).

本批改 CASCADE → RESTRICT:
- workspace 删除前必须显式 archive (status='ARCHIVED') 或先迁数据
- 防误删: 任何尝试 DELETE workspaces 行, 会被 FK 约束阻止
- workspace 归档流程: 提供独立 API (留 S1-5 follow-up, 当前 intentional 无 DELETE 端点)

执行步骤 (PostgreSQL):
1. DROP CONSTRAINT 4 个 FK (fk_util_results_workspace_id 等)
2. ADD CONSTRAINT 4 个 FK (ondelete=RESTRICT)
3. SQLite 测试环境: 重建表 (SQLite 不支持 ALTER FK), create_all 用新 schema

仅 schema 变更, 不动数据; 无破坏性.
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "p7_s2_002"
down_revision: str | None = "p7_s2_001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


# 4 张表 + 4 个 FK 名 (per NAMING_CONVENTION in app/db/base.py)
TABLES_FK = [
    ("util_results", "fk_util_results_workspace_id_workspaces"),
    ("utility_power_items", "fk_utility_power_items_workspace_id_workspaces"),
    ("utility_fuel_gas", "fk_utility_fuel_gas_workspace_id_workspaces"),
    ("utility_heat_exchange", "fk_utility_heat_exchange_workspace_id_workspaces"),
]


def upgrade() -> None:
    """CASCADE → RESTRICT for 4 util_* tables' workspace_id FK."""
    conn = op.get_bind()
    is_sqlite = conn.dialect.name == "sqlite"

    for table, fk_name in TABLES_FK:
        if is_sqlite:
            # SQLite 不支持 ALTER DROP/ADD CONSTRAINT, 跳过 (生产 PG 覆盖)
            # 测试环境由 create_all 用新 schema 自动应用
            continue
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            table,
            "workspaces",
            ["workspace_id"], ["workspace_id"],
            ondelete="RESTRICT",
        )


def downgrade() -> None:
    """RESTRICT → CASCADE (回滚)."""
    conn = op.get_bind()
    is_sqlite = conn.dialect.name == "sqlite"

    for table, fk_name in TABLES_FK:
        if is_sqlite:
            continue
        op.drop_constraint(fk_name, table, type_="foreignkey")
        op.create_foreign_key(
            fk_name,
            table,
            "workspaces",
            ["workspace_id"], ["workspace_id"],
            ondelete="CASCADE",
        )
