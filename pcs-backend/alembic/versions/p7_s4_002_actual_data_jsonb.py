"""p7_s4_002: equipment_list.actual_data_json (供应商实测值本体).

P7 Sprint 4 Task S4-1 / ADR-0025。`EquipmentList` 此前只有 `actual_data_status`
状态列（NOT_ENTERED/PENDING_CONFIRM/CONFIRMED/NEED_RECALC）却**没有承载值本身
的字段** —— 状态可流转但无值可存。本迁移补上载体。

形状: ``{参数名: {"value": float, "unit": str}}``。参数名差异化, 故不拆成列:
S4-2 偏差报告按各设备自身的设计参数集逐项比对, 参数集本就不统一。

`op.add_column` 不带幂等 guard —— 与
`scripts/check_migration_idempotency.py` 的 SAFE_OPS 约定一致
（PG < 9.6 无 ADD COLUMN IF NOT EXISTS, 幂等靠 alembic 版本表保证）。

Revision ID: p7_s4_002
Revises: p7_s4_001
Create Date: 2026-10-05
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision = "p7_s4_002"
down_revision = "p7_s4_001"
branch_labels = None
depends_on = None

_TABLE = "equipment_list"


def upgrade() -> None:
    op.add_column(
        _TABLE,
        sa.Column(
            "actual_data_json",
            postgresql.JSONB().with_variant(sa.JSON(), "sqlite"),
            comment="供应商实测值 {参数名: {value: float, unit: str}}",
        ),
    )


def downgrade() -> None:
    op.drop_column(_TABLE, "actual_data_json")
