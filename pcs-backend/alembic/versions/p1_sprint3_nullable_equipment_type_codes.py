"""Sprint 3：equipment_type_codes.project_id 改 nullable。

V3.3 字典语义：project_id NULL = 公司级默认；项目级覆写 P2+ 模板导入后启用。

技术约束：PG 不允许主键列可空。需把 (project_id, type_code) 由 PRIMARY KEY 改为
UNIQUE 约束（保持唯一性 + 允许 NULL）。同时索引保留。
"""

from __future__ import annotations

from typing import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "p1_sprint3_nullable_equipment_type_codes"
down_revision: str | None = "p1_sprint3_bootstrap_alembic_version"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. 丢弃复合主键（CASCADE：会级联删 equipment_list.type_code FK）
    op.execute("ALTER TABLE equipment_type_codes DROP CONSTRAINT pk_equipment_type_codes CASCADE")
    # 2. project_id 改 nullable
    op.alter_column(
        "equipment_type_codes",
        "project_id",
        existing_type=sa.Uuid(),
        nullable=True,
    )
    # 3. 用 UNIQUE 约束保持原 PK 的唯一性语义
    op.create_unique_constraint(
        "uq_equipment_type_codes_project_type",
        "equipment_type_codes",
        ["project_id", "type_code"],
    )
    # 4. 重建 equipment_list → equipment_type_codes 复合 FK（CASCADE 掉的）
    op.create_foreign_key(
        "fk_equipment_list_type_code_composite",
        "equipment_list",
        "equipment_type_codes",
        ["equipment_type_project_id", "type_code"],
        ["project_id", "type_code"],
    )


def downgrade() -> None:
    # 回滚顺序与 upgrade 相反
    op.drop_constraint(
        "fk_equipment_list_type_code_composite",
        "equipment_list",
        type_="foreignkey",
    )
    op.drop_constraint(
        "uq_equipment_type_codes_project_type",
        "equipment_type_codes",
        type_="unique",
    )
    op.alter_column(
        "equipment_type_codes",
        "project_id",
        existing_type=sa.Uuid(),
        nullable=False,
    )
    op.create_primary_key(
        "pk_equipment_type_codes",
        "equipment_type_codes",
        ["project_id", "type_code"],
    )
    # 重建原 equipment_list FK（与 P0 baseline 一致）
    op.create_foreign_key(
        "fk_equipment_list_type_code",
        "equipment_list",
        "equipment_type_codes",
        ["equipment_type_project_id", "type_code"],
        ["project_id", "type_code"],
    )