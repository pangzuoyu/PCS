"""P4-0-1: 计算链审计字段（5 表 × 3 列）。

streams / piping_results / pump_results / flash_results / pipe_network_results
五表各加 3 列：
- stale_resolution_path String(30) NULL：STALE 后走的重算路径（CIA 审计）
- hash_changed Boolean NULL default false：record_hash 相对上版是否实质变化
- changed_fields JSONB NULL：实质变化字段清单

护栏（ADR-0031）：审计列只经 app/services/calc_lineage.finalize_calc_record
与 CIA 引擎写，业务模块禁止直写。

down_revision = p3sim_streams_petroleum_fields
"""
from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "p4_calc_audit_fields"
down_revision = "p3sim_streams_petroleum_fields"
branch_labels = None
depends_on = None

_TABLES = (
    "streams",
    "piping_results",
    "pump_results",
    "flash_results",
    "pipe_network_results",
)


def upgrade() -> None:
    for table in _TABLES:
        op.add_column(
            table,
            sa.Column(
                "stale_resolution_path",
                sa.String(30),
                nullable=True,
                comment="STALE 后走的重算路径（CIA 审计）",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "hash_changed",
                sa.Boolean(),
                nullable=True,
                server_default=sa.false(),
                comment="record_hash 相对上版是否实质变化",
            ),
        )
        op.add_column(
            table,
            sa.Column(
                "changed_fields",
                JSONB(),
                nullable=True,
                comment="实质变化字段清单（6 位规范化后仍发散的字段）",
            ),
        )


def downgrade() -> None:
    for table in _TABLES:
        op.drop_column(table, "changed_fields")
        op.drop_column(table, "hash_changed")
        op.drop_column(table, "stale_resolution_path")
