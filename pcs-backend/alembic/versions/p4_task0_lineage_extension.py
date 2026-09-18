"""P4-TASK0 本体论扩展（ADR-0031 残余）。

两套增量：
1. data_lineage 表加 4 列：D4/D5 扩展
   - record_hash_at_track String(16) NULL
   - source_record_hash String(16) NULL
   - formula_version_at_track String(50) NULL
   - config_version String(50) NULL

2. two_phase_results 表加 1 列：record_hash String(64) NOT NULL default ''
   - 接入 calc_lineage 收口（P4-TASK0 RECORD_TYPE_REGISTRY 完整化）
   - default '' 与 RecordMixin.record_hash 一致

DOWN-REVISION = p4_pump_chain_io_json（最新迁移基线）。
"""
from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "p4_task0_lineage_extension"
down_revision = "p4_pump_chain_io_json"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """P4-TASK0 lineage 本体论扩展（ADR-0031 残余，D4/D5）。

    步骤：
    - A. data_lineage 加 4 列：record_hash_at_track(16) /
      source_record_hash(16) / formula_version_at_track(50) / config_version(50)
    - B. two_phase_results 加 1 列：record_hash(64) NOT NULL default ''
      接入 calc_lineage 收口（P4-TASK0 RECORD_TYPE_REGISTRY 完整化）

    业务：data_lineage 追踪收口时 record_hash（D4）+ 上游 hash（D5）+ 公式版本 +
    配置版本；two_phase_results 落入 record_hash 与 RecordMixin 一致。
    """
    # data_lineage D4/D5
    op.add_column(
        "data_lineage",
        sa.Column(
            "record_hash_at_track",
            sa.String(16),
            nullable=True,
            comment="收口时 record_hash（P4-TASK0 D4）",
        ),
    )
    op.add_column(
        "data_lineage",
        sa.Column(
            "source_record_hash",
            sa.String(16),
            nullable=True,
            comment="上游 record_hash（P4-TASK0 D5）",
        ),
    )
    op.add_column(
        "data_lineage",
        sa.Column(
            "formula_version_at_track",
            sa.String(50),
            nullable=True,
            comment="收口时公式版本（P4-TASK0 D4）",
        ),
    )
    op.add_column(
        "data_lineage",
        sa.Column(
            "config_version",
            sa.String(50),
            nullable=True,
            comment="上游配置版本（P4-TASK0 占位）",
        ),
    )

    # two_phase_results 接入 calc_lineage
    op.add_column(
        "two_phase_results",
        sa.Column(
            "record_hash",
            sa.String(64),
            nullable=False,
            server_default="",
            comment="SHA-256 截断 16 hex；与 RecordMixin 同语义（P4-TASK0 扩展）",
        ),
    )


def downgrade() -> None:
    op.drop_column("two_phase_results", "record_hash")
    op.drop_column("data_lineage", "config_version")
    op.drop_column("data_lineage", "formula_version_at_track")
    op.drop_column("data_lineage", "source_record_hash")
    op.drop_column("data_lineage", "record_hash_at_track")
