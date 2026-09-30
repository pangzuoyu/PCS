"""P6-3 Task 34：filtration_results 补 3 列（审计列护栏 + P6-OPEN-009 模式).

依据：
- P6 计划 §Task 34（filtration persist + api 8 endpoints）
- ticket 091500e P6-OPEN-009（psv_results alembic drift 缺 3 列模式）
- Task 32 已落 p6_3_003_open_channel_audit_columns 同模式（open_channel_results
  补 3 列）；本迁移对 filtration_results 复用同模式。

设计要点：
- v3.1 schema migration（``dd47298c9c38_v3_1_full_schema_53_tables``）已创建
  filtration_results 表，但当时未含 P4-0-1 审计列（stale_resolution_path /
  hash_changed / changed_fields）。P6-2 flare/cool_tower/psychro 落地时
  p6_2_001 在 create_table 阶段补全 3 列（"扁平 + 3 audit"模式）；P6-3
  filtration 走的是 v3.1 既有表，需追加迁移。
- FiltrationResult ORM（app/models/calc.py）继承 TaggedRecordMixin →
  RecordMixin，mapped_column 含 stale_resolution_path / hash_changed /
  changed_fields（mixin 字段）；若 DB 缺列，INSERT 会触发
  UndefinedColumnError（Task 34 G-07 实测命中）。
- 本迁移补 3 列以 ``ADD COLUMN IF NOT EXISTS`` 追加；幂等多次 upgrade no-op。
- DOWN 走 DROP COLUMN IF EXISTS 逆序删除；alembic 标记前移但 DDL 幂等。

DOWN-REVISION = p6_3_003_open_channel_audit_columns（Task 32 末态）。
"""
from __future__ import annotations

from alembic import op

revision = "p6_3_004_filtration_audit_columns"
down_revision = "p6_3_003_open_channel_audit_columns"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """filtration_results 补 3 列（P6-OPEN-009 模式 + RecordMixin 补齐).

    列定义参考 p6_2_001 / p6_3_003：stale_resolution_path String(30) /
    hash_changed Bool server_default FALSE / changed_fields JSONB。
    """
    op.execute(
        "ALTER TABLE filtration_results "
        "ADD COLUMN IF NOT EXISTS stale_resolution_path VARCHAR(30)"
    )
    op.execute(
        "ALTER TABLE filtration_results "
        "ADD COLUMN IF NOT EXISTS hash_changed BOOLEAN "
        "NOT NULL DEFAULT FALSE"
    )
    op.execute(
        "ALTER TABLE filtration_results "
        "ADD COLUMN IF NOT EXISTS changed_fields JSONB"
    )


def downgrade() -> None:
    """逆序删除 3 列（DDL 幂等：IF EXISTS）."""
    op.execute(
        "ALTER TABLE filtration_results DROP COLUMN IF EXISTS changed_fields"
    )
    op.execute(
        "ALTER TABLE filtration_results DROP COLUMN IF EXISTS hash_changed"
    )
    op.execute(
        "ALTER TABLE filtration_results "
        "DROP COLUMN IF EXISTS stale_resolution_path"
    )


__all__ = ["revision", "down_revision", "upgrade", "downgrade"]